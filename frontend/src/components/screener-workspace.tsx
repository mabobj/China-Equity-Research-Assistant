"use client";

import Link from "next/link";
import type { Dispatch, SetStateAction } from "react";
import { Fragment, useEffect, useMemo, useState } from "react";

import {
  getActiveScreenerRun,
  getLatestScreenerBatchSummary,
  getLatestScreenerWindowResults,
  getModelEvaluation,
  getWorkflowRunDetail,
  resetScreenerCursor,
  runDeepReviewWorkflow,
  runScreenerWorkflow,
} from "@/lib/api";
import {
  formatAction,
  formatDateTime,
  formatDecisionBriefAction,
  formatLabel,
  formatListType,
  formatModelRecommendation,
  formatPrice,
  formatPredictiveConfidenceLevel,
  formatPredictiveScoreLevel,
  formatRatioPercent,
  formatRange,
  formatScore,
} from "@/lib/format";
import type {
  DeepScreenerRunResponse,
  ModelEvaluationResponse,
  ScreenerListType,
  ScreenerLatestBatchResponse,
  ScreenerLatestBatchSummaryResponse,
  ScreenerSymbolResult,
  WorkflowRunDetailResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";
import { WorkflowRunSummary } from "./workflow-run-summary";

const POLL_MS = 1500;
const PAGE_SIZE_OPTIONS = [20, 50, 100, 200] as const;

type ResultFilters = {
  symbolQuery: string;
  listType: ScreenerListType | "ALL";
  minScore: string;
  maxScore: string;
  reasonQuery: string;
  calculatedFrom: string;
  calculatedTo: string;
  ruleVersion: string;
};

const INITIAL_FILTERS: ResultFilters = {
  symbolQuery: "",
  listType: "ALL",
  minScore: "",
  maxScore: "",
  reasonQuery: "",
  calculatedFrom: "",
  calculatedTo: "",
  ruleVersion: "",
};

export function ScreenerWorkspace() {
  const [batchSize, setBatchSize] = useState("50");
  const [deepMaxSymbols, setDeepMaxSymbols] = useState("50");
  const [deepTopN, setDeepTopN] = useState("20");
  const [deepTopK, setDeepTopK] = useState("8");
  const [screenerRun, setScreenerRun] = useState<WorkflowRunDetailResponse | null>(null);
  const [deepRun, setDeepRun] = useState<WorkflowRunDetailResponse | null>(null);
  const [screenerError, setScreenerError] = useState<string | null>(null);
  const [deepError, setDeepError] = useState<string | null>(null);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [batchResultsLoading, setBatchResultsLoading] = useState(false);
  const [batchResultsError, setBatchResultsError] = useState<string | null>(null);
  const [latestBatch, setLatestBatch] = useState<ScreenerLatestBatchResponse | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [filters, setFilters] = useState<ResultFilters>(INITIAL_FILTERS);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [reloadToken, setReloadToken] = useState(0);
  const [evaluationByVersion, setEvaluationByVersion] = useState<
    Record<string, ModelEvaluationResponse>
  >({});
  const [evaluationLoadingVersion, setEvaluationLoadingVersion] = useState<string | null>(null);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);

  const runningRunId = screenerRun?.status === "running" ? screenerRun.run_id : null;
  useWorkflowPolling(runningRunId, setScreenerRun);
  useWorkflowPolling(
    deepRun?.status === "running" ? deepRun.run_id : null,
    setDeepRun,
  );

  useEffect(() => {
    if (screenerRun?.status === "running") {
      return;
    }
    setReloadToken((value) => value + 1);
  }, [screenerRun?.status]);

  useEffect(() => {
    let active = true;
    const loadLatest = async () => {
      let summaryLoaded = false;
      setBatchLoading(true);
      setBatchError(null);
      setBatchResultsError(null);
      try {
        const activeRun = await getActiveScreenerRun();
        if (!active) return;
        if (activeRun?.status === "running") {
          setScreenerRun(activeRun);
          setLatestBatch(null);
          setSelectedSymbol(null);
          return;
        }
        const summary = await getLatestScreenerBatchSummary();
        if (!active) return;
        summaryLoaded = true;
        setLatestBatch(toLatestBatchFromSummary(summary));
        setSelectedSymbol(null);
        setBatchLoading(false);

        if (!summary.batch || summary.total_results === 0) {
          return;
        }

        setBatchResultsLoading(true);
        const response = await getLatestScreenerWindowResults();
        if (!active) return;
        setLatestBatch(response);
        setSelectedSymbol((previous) => {
          if (!response.results.length) return null;
          if (previous && response.results.some((item) => item.symbol === previous)) {
            return previous;
          }
          return response.results[0].symbol;
        });
      } catch (error) {
        if (!active) return;
        if (!summaryLoaded) {
          setBatchError(toErrorMessage(error));
        } else {
          setBatchResultsError(toErrorMessage(error));
        }
      } finally {
        if (active) {
          setBatchLoading(false);
          setBatchResultsLoading(false);
        }
      }
    };
    void loadLatest();
    return () => {
      active = false;
    };
  }, [reloadToken]);

  const isScreenerRunning =
    screenerRun?.status === "running" || latestBatch?.batch?.status === "running";
  const allResults = useMemo(
    () => latestBatch?.results ?? [],
    [latestBatch?.results],
  );

  const filteredResults = useMemo(() => {
    let results = [...allResults];
    if (filters.symbolQuery.trim()) {
      const query = filters.symbolQuery.trim().toUpperCase();
      results = results.filter(
        (item) =>
          item.symbol.toUpperCase().includes(query) || item.name.toUpperCase().includes(query),
      );
    }
    if (filters.listType !== "ALL") {
      results = results.filter((item) => item.list_type === filters.listType);
    }
    if (filters.minScore.trim()) {
      const min = Number.parseInt(filters.minScore, 10);
      if (Number.isFinite(min)) {
        results = results.filter((item) => item.screener_score >= min);
      }
    }
    if (filters.maxScore.trim()) {
      const max = Number.parseInt(filters.maxScore, 10);
      if (Number.isFinite(max)) {
        results = results.filter((item) => item.screener_score <= max);
      }
    }
    if (filters.reasonQuery.trim()) {
      const query = filters.reasonQuery.trim().toLowerCase();
      results = results.filter((item) => item.short_reason.toLowerCase().includes(query));
    }
    if (filters.calculatedFrom) {
      const from = new Date(`${filters.calculatedFrom}T00:00:00+08:00`).getTime();
      if (Number.isFinite(from)) {
        results = results.filter((item) => new Date(item.calculated_at).getTime() >= from);
      }
    }
    if (filters.calculatedTo) {
      const to = new Date(`${filters.calculatedTo}T23:59:59+08:00`).getTime();
      if (Number.isFinite(to)) {
        results = results.filter((item) => new Date(item.calculated_at).getTime() <= to);
      }
    }
    if (filters.ruleVersion.trim()) {
      results = results.filter((item) => item.rule_version === filters.ruleVersion.trim());
    }
    return results;
  }, [allResults, filters]);

  const selectedResult =
    selectedSymbol == null
      ? null
      : filteredResults.find((item) => item.symbol === selectedSymbol) ??
        allResults.find((item) => item.symbol === selectedSymbol) ??
        null;

  useEffect(() => {
    setCurrentPage(1);
  }, [filters, pageSize, latestBatch?.batch?.batch_id]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(filteredResults.length / pageSize)),
    [filteredResults.length, pageSize],
  );

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const pagedResults = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredResults.slice(start, start + pageSize);
  }, [currentPage, filteredResults, pageSize]);

  useEffect(() => {
    const modelVersion = selectedResult?.predictive_model_version;
    if (!modelVersion) {
      setEvaluationLoadingVersion(null);
      setEvaluationError(null);
      return;
    }
    if (evaluationByVersion[modelVersion]) {
      setEvaluationLoadingVersion(null);
      setEvaluationError(null);
      return;
    }

    let active = true;
    setEvaluationLoadingVersion(modelVersion);
    setEvaluationError(null);
    void getModelEvaluation(modelVersion)
      .then((value) => {
        if (!active) return;
        setEvaluationByVersion((previous) => ({
          ...previous,
          [modelVersion]: value,
        }));
      })
      .catch((cause) => {
        if (!active) return;
        setEvaluationError(
          cause instanceof Error ? cause.message : "模型评估建议加载失败，请稍后重试。",
        );
      })
      .finally(() => {
        if (!active) return;
        setEvaluationLoadingVersion(null);
      });

    return () => {
      active = false;
    };
  }, [evaluationByVersion, selectedResult?.predictive_model_version]);

  const ruleVersions = useMemo(() => {
    return [...new Set(allResults.map((item) => item.rule_version).filter(Boolean))];
  }, [allResults]);
  const bucketSummary = useMemo(() => {
    const summary: Record<ScreenerListType, number> = {
      READY_TO_BUY: 0,
      WATCH_PULLBACK: 0,
      WATCH_BREAKOUT: 0,
      RESEARCH_ONLY: 0,
      AVOID: 0,
    };
    for (const item of allResults) {
      summary[item.list_type] += 1;
    }
    return summary;
  }, [allResults]);

  const handleRunScreener = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setScreenerError(null);
    setResetMessage(null);
    if (isScreenerRunning) {
      setScreenerError("已有运行中的初筛任务，请先等待当前任务完成。");
      return;
    }
    try {
      const response = await runScreenerWorkflow({
        batch_size: parseOptionalInteger(batchSize),
      });
      setScreenerRun({ ...response, final_output: null });
      if (response.accepted === false && response.existing_run_id) {
        setScreenerError(response.message ?? "已有运行中的初筛任务。");
      } else {
        setScreenerError(null);
      }
    } catch (error) {
      setScreenerError(toErrorMessage(error));
    }
  };

  const handleResetCursor = async () => {
    setResetLoading(true);
    setResetMessage(null);
    setScreenerError(null);
    try {
      const response = await resetScreenerCursor();
      setResetMessage(response.message);
      setReloadToken((value) => value + 1);
    } catch (error) {
      setScreenerError(toErrorMessage(error));
    } finally {
      setResetLoading(false);
    }
  };

  const handleRunDeep = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDeepError(null);
    try {
      const response = await runDeepReviewWorkflow({
        max_symbols: parseOptionalInteger(deepMaxSymbols),
        top_n: parseOptionalInteger(deepTopN),
        deep_top_k: parseOptionalInteger(deepTopK),
      });
      setDeepRun({ ...response, final_output: null });
    } catch (error) {
      setDeepError(toErrorMessage(error));
    }
  };

  const handleSelectSymbol = (symbol: string) => {
    setSelectedSymbol((previous) => (previous === symbol ? null : symbol));
  };

  return (
    <div className="space-y-6">
      <SectionCard
        title="当前展示窗口"
        description="先看结果再做动作。17:00 前展示前一日 17:00 后完成结果；17:00 后展示当日 17:00 后完成结果。"
      >
        <div className="space-y-4">
          {batchLoading ? (
            <StatusBlock title="加载中" description="正在读取当前窗口结果..." />
          ) : null}
          {batchError ? (
            <StatusBlock title="加载失败" description={batchError} tone="error" />
          ) : null}
          {!batchLoading && !batchError && latestBatch ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Metric label="窗口开始" value={formatDateTime(latestBatch.window_start)} />
                <Metric label="窗口结束" value={formatDateTime(latestBatch.window_end)} />
                <Metric label="窗口股票数" value={String(latestBatch.total_results)} />
                <Metric label="筛选后股票数" value={String(filteredResults.length)} />
                <Metric
                  label="最新批次"
                  value={latestBatch.batch ? latestBatch.batch.batch_id : "暂无"}
                />
                <Metric
                  label="最新批次状态"
                  value={latestBatch.batch ? formatLabel(latestBatch.batch.status) : "-"}
                />
                <Metric
                  label="最新批次扫描"
                  value={
                    latestBatch.batch
                      ? `${latestBatch.batch.scanned_size}/${latestBatch.batch.universe_size}`
                      : "-"
                  }
                />
                <Metric
                  label="最新批次规则版本"
                  value={latestBatch.batch?.rule_version ?? "-"}
                />
                <Metric
                  label="最新批次完成时间"
                  value={
                    latestBatch.batch?.finished_at
                      ? formatDateTime(latestBatch.batch.finished_at)
                      : "-"
                  }
                />
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-900">分桶分布概览（当前窗口）</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  <Metric
                    label={formatListType("READY_TO_BUY")}
                    value={String(bucketSummary.READY_TO_BUY)}
                  />
                  <Metric
                    label={formatListType("WATCH_PULLBACK")}
                    value={String(bucketSummary.WATCH_PULLBACK)}
                  />
                  <Metric
                    label={formatListType("WATCH_BREAKOUT")}
                    value={String(bucketSummary.WATCH_BREAKOUT)}
                  />
                  <Metric
                    label={formatListType("RESEARCH_ONLY")}
                    value={String(bucketSummary.RESEARCH_ONLY)}
                  />
                  <Metric label={formatListType("AVOID")} value={String(bucketSummary.AVOID)} />
                </div>
              </div>
              {latestBatch.batch?.warning_messages.length ? (
                <StatusBlock
                  title="批次提示"
                  description={latestBatch.batch.warning_messages.join("；")}
                />
              ) : null}
              {latestBatch.batch?.failure_reason ? (
                <StatusBlock
                  title="批次失败说明"
                  description={latestBatch.batch.failure_reason}
                  tone="error"
                />
              ) : null}
              {batchResultsLoading ? (
                <StatusBlock
                  title="结果列表加载中"
                  description="批次摘要已就绪，正在按需读取当前窗口结果列表。"
                />
              ) : null}
              {batchResultsError ? (
                <StatusBlock
                  title="结果列表加载失败"
                  description={batchResultsError}
                  tone="error"
                />
              ) : null}

              <BatchFilterPanel
                filters={filters}
                setFilters={setFilters}
                ruleVersions={ruleVersions}
              />
              <BatchPagination
                totalResults={filteredResults.length}
                currentPage={currentPage}
                totalPages={totalPages}
                pageSize={pageSize}
                onPageChange={setCurrentPage}
                onPageSizeChange={(value) => {
                  setPageSize(value);
                  setCurrentPage(1);
                }}
              />
              <BatchResultTable
                results={pagedResults}
                selectedSymbol={selectedSymbol}
                onSelectSymbol={handleSelectSymbol}
                evaluationByVersion={evaluationByVersion}
                evaluationLoadingVersion={evaluationLoadingVersion}
                evaluationError={evaluationError}
              />
            </>
          ) : null}
          {!batchLoading && !batchError && latestBatch && latestBatch.total_results === 0 ? (
            <StatusBlock
              title="窗口暂无结果"
              description="当前时间窗口内还没有可展示的初筛结果。"
            />
          ) : null}
        </div>
      </SectionCard>

      <SectionCard
        title="运行初筛（快速入口）"
        description="输入本批次计算股票数量后即可启动。系统会自动按游标继续，避免重复扫描。"
      >
        <form className="grid gap-4 md:grid-cols-[1fr_auto]" onSubmit={handleRunScreener}>
          <Field
            label="本批次计算股票数量（batch_size）"
            value={batchSize}
            onChange={setBatchSize}
            placeholder="例如 50"
          />
          <div className="flex items-end">
            <button
              type="submit"
              disabled={isScreenerRunning}
              className="min-h-11 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:bg-emerald-300"
            >
              {isScreenerRunning ? "已有运行中的初筛任务" : "运行初筛工作流"}
            </button>
          </div>
        </form>
        <div className="mt-5 space-y-4">
          {screenerError ? (
            <StatusBlock title="初筛工作流提示" description={screenerError} tone="error" />
          ) : null}
          {screenerRun ? (
            <WorkflowRunSummary run={screenerRun} />
          ) : (
            <StatusBlock
              title="等待执行"
              description="提交后会立即返回 run_id，并持续轮询工作流运行状态。"
            />
          )}
        </div>
      </SectionCard>

      <details className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-950">
          高级操作（游标管理与深筛工作流）
        </summary>
        <div className="mt-4 space-y-6">
          <SectionCard
            title="游标管理"
            description="当你需要从股票池起点重新分批计算时，再使用该操作。"
          >
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleResetCursor}
                disabled={resetLoading || isScreenerRunning}
                className="min-h-11 rounded-2xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:text-slate-400"
              >
                {resetLoading ? "重置中..." : "重置游标"}
              </button>
              <p className="text-sm text-slate-600">
                仅影响后续初筛扫描起点，不会删除历史批次记录。
              </p>
            </div>
            {resetMessage ? (
              <div className="mt-4">
                <StatusBlock title="游标重置" description={resetMessage} />
              </div>
            ) : null}
          </SectionCard>

          <SectionCard
            title="深筛工作流（保持兼容）"
            description="深筛属于二次筛选，建议先完成初筛并确认候选后再运行。"
          >
            <form className="grid gap-4 md:grid-cols-4" onSubmit={handleRunDeep}>
              <Field label="最大股票数（max_symbols）" value={deepMaxSymbols} onChange={setDeepMaxSymbols} />
              <Field label="候选上限（top_n）" value={deepTopN} onChange={setDeepTopN} />
              <Field label="深筛数量（deep_top_k）" value={deepTopK} onChange={setDeepTopK} />
              <div className="flex items-end">
                <button
                  type="submit"
                  className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  运行深筛工作流
                </button>
              </div>
            </form>
            <div className="mt-5 space-y-4">
              {deepError ? (
                <StatusBlock title="深筛工作流启动失败" description={deepError} tone="error" />
              ) : null}
              {deepRun ? (
                <WorkflowRunSummary run={deepRun} />
              ) : (
                <StatusBlock
                  title="等待执行"
                  description="提交深筛后会返回 run_id 和步骤摘要。"
                />
              )}
              {renderDeepFinalOutput(deepRun)}
            </div>
          </SectionCard>
        </div>
      </details>
    </div>
  );
}

function useWorkflowPolling(
  runId: string | null,
  setRun: Dispatch<SetStateAction<WorkflowRunDetailResponse | null>>,
) {
  useEffect(() => {
    if (!runId) return;
    let active = true;
    const poll = async () => {
      try {
        const detail = await getWorkflowRunDetail(runId);
        if (!active) return;
        setRun(detail);
      } catch {
        // 保持当前状态，避免短时网络波动打断展示。
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [runId, setRun]);
}

function BatchFilterPanel({
  filters,
  setFilters,
  ruleVersions,
}: {
  filters: ResultFilters;
  setFilters: Dispatch<SetStateAction<ResultFilters>>;
  ruleVersions: string[];
}) {
  const updateFilter = <K extends keyof ResultFilters>(
    key: K,
    value: ResultFilters[K],
  ) => {
    setFilters((previous) => ({ ...previous, [key]: value }));
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-900">列筛选</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Field
          label="股票（代码/名称）"
          value={filters.symbolQuery}
          onChange={(value) => updateFilter("symbolQuery", value)}
        />
        <label className="space-y-2">
          <span className="text-sm font-medium text-slate-700">分桶</span>
          <select
            value={filters.listType}
            onChange={(event) =>
              updateFilter(
                "listType",
                event.target.value as ResultFilters["listType"],
              )
            }
            className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          >
            <option value="ALL">全部</option>
            <option value="READY_TO_BUY">{formatListType("READY_TO_BUY")}</option>
            <option value="WATCH_PULLBACK">{formatListType("WATCH_PULLBACK")}</option>
            <option value="WATCH_BREAKOUT">{formatListType("WATCH_BREAKOUT")}</option>
            <option value="RESEARCH_ONLY">{formatListType("RESEARCH_ONLY")}</option>
            <option value="AVOID">{formatListType("AVOID")}</option>
          </select>
        </label>
        <Field
          label="评分下限"
          value={filters.minScore}
          onChange={(value) => updateFilter("minScore", value)}
        />
        <Field
          label="评分上限"
          value={filters.maxScore}
          onChange={(value) => updateFilter("maxScore", value)}
        />
        <Field
          label="简述关键词"
          value={filters.reasonQuery}
          onChange={(value) => updateFilter("reasonQuery", value)}
        />
        <DateField
          label="计算时间（起）"
          value={filters.calculatedFrom}
          onChange={(value) => updateFilter("calculatedFrom", value)}
        />
        <DateField
          label="计算时间（止）"
          value={filters.calculatedTo}
          onChange={(value) => updateFilter("calculatedTo", value)}
        />
        <label className="space-y-2">
          <span className="text-sm font-medium text-slate-700">规则版本</span>
          <select
            value={filters.ruleVersion}
            onChange={(event) => updateFilter("ruleVersion", event.target.value)}
            className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          >
            <option value="">全部</option>
            {ruleVersions.map((version) => (
              <option key={version} value={version}>
                {version}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

function BatchPagination({
  totalResults,
  currentPage,
  totalPages,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: {
  totalResults: number;
  currentPage: number;
  totalPages: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}) {
  const start = totalResults === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, totalResults);
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-700">
          显示第 {start}-{end} 条，共 {totalResults} 条
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            每页
            <select
              value={String(pageSize)}
              onChange={(event) => onPageSizeChange(Number.parseInt(event.target.value, 10))}
              className="min-h-9 rounded-xl border border-slate-300 bg-white px-2 text-sm text-slate-900"
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            条
          </label>
          <button
            type="button"
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
            className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            上一页
          </button>
          <span className="text-sm text-slate-700">
            第 {currentPage}/{totalPages} 页
          </span>
          <button
            type="button"
            onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage >= totalPages}
            className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}

function BatchResultTable({
  results,
  selectedSymbol,
  onSelectSymbol,
  evaluationByVersion,
  evaluationLoadingVersion,
  evaluationError,
}: {
  results: ScreenerSymbolResult[];
  selectedSymbol: string | null;
  onSelectSymbol: (symbol: string) => void;
  evaluationByVersion: Record<string, ModelEvaluationResponse>;
  evaluationLoadingVersion: string | null;
  evaluationError: string | null;
}) {
  if (!results.length) {
    return <StatusBlock title="没有匹配结果" description="请调整筛选条件后重试。" />;
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-50 text-slate-700">
          <tr>
            <th className="px-4 py-3">股票</th>
            <th className="px-4 py-3">分桶</th>
            <th className="px-4 py-3">评分</th>
            <th className="px-4 py-3">预测分</th>
            <th className="px-4 py-3">简述</th>
            <th className="px-4 py-3">计算时间</th>
            <th className="px-4 py-3">规则版本</th>
          </tr>
        </thead>
        <tbody>
          {results.map((item) => {
            const isSelected = item.symbol === selectedSymbol;
            const modelVersion = item.predictive_model_version ?? null;
            const evaluation = modelVersion ? evaluationByVersion[modelVersion] ?? null : null;
            const evaluationLoading =
              modelVersion !== null && evaluationLoadingVersion === modelVersion;
            return (
              <Fragment key={`${item.symbol}-${item.calculated_at}`}>
                <tr
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectSymbol(item.symbol)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectSymbol(item.symbol);
                    }
                  }}
                  className={
                    isSelected
                      ? "cursor-pointer border-t border-slate-200 bg-emerald-50"
                      : "cursor-pointer border-t border-slate-200 hover:bg-slate-50"
                  }
                >
                  <td className="px-4 py-3 font-semibold text-emerald-700">
                    {item.symbol}
                    <span className="ml-2 text-slate-900">{item.name}</span>
                  </td>
                  <td className="px-4 py-3">{formatListType(item.list_type)}</td>
                  <td className="px-4 py-3">{formatScore(item.screener_score)}</td>
                  <td className="px-4 py-3">
                    {item.predictive_score === null || item.predictive_score === undefined
                      ? "-"
                      : formatScore(item.predictive_score)}
                  </td>
                  <td className="px-4 py-3">{item.short_reason}</td>
                  <td className="px-4 py-3">{formatDateTime(item.calculated_at)}</td>
                  <td className="px-4 py-3">{item.rule_version}</td>
                </tr>
                {isSelected ? (
                  <tr className="border-t border-slate-200 bg-white">
                    <td className="px-4 py-4" colSpan={7}>
                      <BatchResultDetail
                        result={item}
                        evaluation={evaluation}
                        evaluationLoading={evaluationLoading}
                        evaluationError={evaluationError}
                      />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function BatchResultDetail({
  result,
  evaluation,
  evaluationLoading,
  evaluationError,
}: {
  result: ScreenerSymbolResult;
  evaluation: ModelEvaluationResponse | null;
  evaluationLoading: boolean;
  evaluationError: string | null;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-base font-semibold text-slate-950">
            {result.name}（{result.symbol}）
          </h4>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            {result.headline_verdict ?? result.short_reason}
          </p>
        </div>
        <Link
          href={`/stocks/${encodeURIComponent(result.symbol)}`}
          className="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800"
        >
          打开单票页
        </Link>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <Metric label="分桶" value={formatListType(result.list_type)} />
        <Metric label="评分" value={formatScore(result.screener_score)} />
        <Metric label="趋势状态" value={formatLabel(result.trend_state)} />
        <Metric label="趋势分" value={formatScore(result.trend_score)} />
        <Metric label="最新收盘价" value={formatPrice(result.latest_close)} />
        <Metric
          label="当前动作"
          value={result.action_now ? formatDecisionBriefAction(result.action_now) : "-"}
        />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="行情质量" value={formatLabel(result.bars_quality ?? "-")} />
        <Metric label="财务质量" value={formatLabel(result.financial_quality ?? "-")} />
        <Metric label="公告质量" value={formatLabel(result.announcement_quality ?? "-")} />
        <Metric
          label="质量折损"
          value={result.quality_penalty_applied ? "已应用" : "未应用"}
        />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric
          label="预测分"
          value={
            result.predictive_score === null || result.predictive_score === undefined
              ? "-"
              : formatScore(result.predictive_score)
          }
        />
        <Metric
          label="预测分解释"
          value={formatPredictiveScoreLevel(result.predictive_score)}
        />
        <Metric
          label="预测置信度"
          value={formatRatioPercent(result.predictive_confidence)}
        />
        <Metric
          label="置信度等级"
          value={formatPredictiveConfidenceLevel(result.predictive_confidence)}
        />
        <Metric
          label="预测模型版本"
          value={result.predictive_model_version ?? "-"}
        />
      </div>
      {evaluationLoading ? (
        <StatusBlock
          title="模型版本建议"
          description="正在加载该模型版本的评估建议..."
        />
      ) : null}
      {evaluation ? (
        <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-900">模型版本建议</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric
              label="建议动作"
              value={formatModelRecommendation(evaluation.recommendation?.recommendation)}
            />
            <Metric
              label="建议版本"
              value={evaluation.recommendation?.recommended_model_version ?? "-"}
            />
            <Metric
              label="评估质量分"
              value={formatRatioPercent(evaluation.metrics.quality_score)}
            />
            <Metric
              label="回测胜率"
              value={formatRatioPercent(evaluation.metrics.screener_win_rate)}
            />
          </div>
          {evaluation.recommendation ? (
            <p className="mt-3 text-sm leading-6 text-slate-700">
              {evaluation.recommendation.reason}
            </p>
          ) : null}
        </div>
      ) : null}
      {evaluationError ? (
        <StatusBlock title="模型评估建议加载失败" description={evaluationError} tone="error" />
      ) : null}
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Metric label="支撑位" value={formatPrice(result.support_level)} />
        <Metric label="压力位" value={formatPrice(result.resistance_level)} />
        <Metric label="计算时间" value={formatDateTime(result.calculated_at)} />
      </div>
      <div className="mt-4 space-y-3">
        <Metric label="规则版本" value={result.rule_version} />
        <Metric label="规则说明" value={result.rule_summary} />
        {result.quality_note ? (
          <StatusBlock title="数据质量影响说明" description={result.quality_note} />
        ) : null}
        <StringPanel title="证据提示" items={result.evidence_hints} />
        {result.fail_reason ? (
          <StatusBlock title="失败说明" description={result.fail_reason} tone="error" />
        ) : null}
      </div>
    </div>
  );
}

function renderDeepFinalOutput(run: WorkflowRunDetailResponse | null) {
  const finalOutput = run?.final_output as {
    candidates?: DeepScreenerRunResponse["deep_candidates"];
  } | null;
  if (!run || run.status === "running") return null;
  if (!finalOutput || !Array.isArray(finalOutput.candidates)) {
    return (
      <StatusBlock
        title="无深筛输出"
        description="工作流已结束，但没有返回深筛候选。"
        tone="error"
      />
    );
  }
  return (
    <div className="space-y-4">
      {finalOutput.candidates.length === 0 ? (
        <StatusBlock title="暂无深筛候选" description="本次深筛运行未产出候选。" />
      ) : (
        finalOutput.candidates.map((candidate) => (
          <article key={candidate.symbol} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h4 className="text-base font-semibold text-slate-950">{candidate.name}</h4>
                <p className="mt-1 text-sm text-slate-600">{candidate.symbol}</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">{candidate.short_reason}</p>
              </div>
              <Link
                href={`/stocks/${encodeURIComponent(candidate.symbol)}`}
                className="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800"
              >
                打开单票页
              </Link>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="优先级" value={formatScore(candidate.priority_score)} />
              <Metric label="研究动作" value={formatAction(candidate.research_action)} />
              <Metric label="策略动作" value={formatAction(candidate.strategy_action)} />
              <Metric label="策略类型" value={candidate.strategy_type} />
              <Metric label="理想入场区间" value={formatRange(candidate.ideal_entry_range)} />
              <Metric label="止损位" value={formatPrice(candidate.stop_loss_price)} />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <Metric
                label="预测分"
                value={
                  candidate.predictive_score === null || candidate.predictive_score === undefined
                    ? "-"
                    : formatScore(candidate.predictive_score)
                }
              />
              <Metric
                label="预测置信度"
                value={formatRatioPercent(candidate.predictive_confidence)}
              />
              <Metric
                label="预测模型版本"
                value={candidate.predictive_model_version ?? "-"}
              />
            </div>
          </article>
        ))
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
      />
    </label>
  );
}

function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
      />
    </label>
  );
}

function StringPanel({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">暂无条目。</p>
      ) : (
        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          {items.map((item) => (
            <li key={item} className="rounded-2xl bg-slate-50 px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 break-all text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function toLatestBatchFromSummary(
  summary: ScreenerLatestBatchSummaryResponse,
): ScreenerLatestBatchResponse {
  return {
    ...summary,
    results: [],
  };
}

function parseOptionalInteger(value: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) return undefined;
  const parsed = Number.parseInt(normalized, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "发生未知错误，请稍后重试。";
}
