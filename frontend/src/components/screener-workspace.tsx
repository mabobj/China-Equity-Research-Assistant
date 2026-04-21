"use client";

import type { Dispatch, SetStateAction } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  getActiveScreenerRun,
  getModelEvaluation,
  getScreenerBatchResults,
  getScreenerSchemeDetail,
  getScreenerSchemeFeedback,
  getScreenerSchemeRuns,
  getScreenerSchemeStats,
  getScreenerSchemes,
  getWorkflowRunDetail,
  resetScreenerCursor,
  runDeepReviewWorkflow,
  runScreenerWorkflow,
} from "@/lib/api";
import type {
  DeepScreenerRunResponse,
  ModelEvaluationResponse,
  ScreenerBatchResultsResponse,
  ScreenerSchemeDetailResponse,
  ScreenerSchemeListResponse,
  ScreenerSchemeReviewStatsResponse,
  ScreenerSchemeRunsResponse,
  ScreenerSchemeStatsResponse,
  WorkflowRunDetailResponse,
} from "@/types/api";

import { ScreenerResultPanel, type ResultFilters } from "./screener-result-panel";
import { ScreenerReviewPanel } from "./screener-review-panel";
import { ScreenerRunPanel } from "./screener-run-panel";
import { ScreenerSchemePanel } from "./screener-scheme-panel";
import { SectionCard } from "./section-card";
import { ScreenerField, ScreenerMetric } from "./screener-shared";
import { StatusBlock } from "./status-block";
import { WorkflowRunSummary } from "./workflow-run-summary";

const POLL_MS = 1500;

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
  const [maxSymbols, setMaxSymbols] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [deepMaxSymbols, setDeepMaxSymbols] = useState("50");
  const [deepTopN, setDeepTopN] = useState("20");
  const [deepTopK, setDeepTopK] = useState("8");
  const [schemes, setSchemes] = useState<ScreenerSchemeListResponse | null>(null);
  const [selectedSchemeId, setSelectedSchemeId] = useState<string | null>(null);
  const [schemeDetail, setSchemeDetail] = useState<ScreenerSchemeDetailResponse | null>(null);
  const [schemeRuns, setSchemeRuns] = useState<ScreenerSchemeRunsResponse | null>(null);
  const [schemeStats, setSchemeStats] = useState<ScreenerSchemeStatsResponse | null>(null);
  const [schemeFeedback, setSchemeFeedback] = useState<ScreenerSchemeReviewStatsResponse | null>(
    null,
  );
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [selectedBatchResults, setSelectedBatchResults] =
    useState<ScreenerBatchResultsResponse | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [filters, setFilters] = useState<ResultFilters>(INITIAL_FILTERS);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [screenerRun, setScreenerRun] = useState<WorkflowRunDetailResponse | null>(null);
  const [deepRun, setDeepRun] = useState<WorkflowRunDetailResponse | null>(null);
  const [schemeLoading, setSchemeLoading] = useState(false);
  const [schemeError, setSchemeError] = useState<string | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [screenerError, setScreenerError] = useState<string | null>(null);
  const [deepError, setDeepError] = useState<string | null>(null);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const [evaluationByVersion, setEvaluationByVersion] = useState<
    Record<string, ModelEvaluationResponse>
  >({});
  const [evaluationLoadingVersion, setEvaluationLoadingVersion] = useState<string | null>(null);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const runningRunId = screenerRun?.status === "running" ? screenerRun.run_id : null;
  useWorkflowPolling(runningRunId, setScreenerRun);
  useWorkflowPolling(
    deepRun?.status === "running" ? deepRun.run_id : null,
    setDeepRun,
  );

  useEffect(() => {
    let active = true;
    const loadInitial = async () => {
      setSchemeLoading(true);
      setSchemeError(null);
      try {
        const [schemeList, activeRun] = await Promise.all([
          getScreenerSchemes(),
          getActiveScreenerRun(),
        ]);
        if (!active) return;
        setSchemes(schemeList);
        if (activeRun?.status === "running") {
          setScreenerRun(activeRun);
        }
        setSelectedSchemeId((previous) => {
          if (previous) return previous;
          if (activeRun?.scheme_id) return activeRun.scheme_id;
          const defaultScheme =
            schemeList.items.find((item) => item.is_default) ?? schemeList.items[0];
          return defaultScheme?.scheme_id ?? null;
        });
      } catch (error) {
        if (!active) return;
        setSchemeError(toErrorMessage(error));
      } finally {
        if (active) {
          setSchemeLoading(false);
        }
      }
    };
    void loadInitial();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedSchemeId) return;
    let active = true;
    const loadSchemeContext = async () => {
      setFeedbackLoading(true);
      setFeedbackError(null);
      try {
        const [detail, runs, stats, feedback] = await Promise.all([
          getScreenerSchemeDetail(selectedSchemeId),
          getScreenerSchemeRuns(selectedSchemeId),
          getScreenerSchemeStats(selectedSchemeId),
          getScreenerSchemeFeedback(selectedSchemeId),
        ]);
        if (!active) return;
        setSchemeDetail(detail);
        setSchemeRuns(runs);
        setSchemeStats(stats);
        setSchemeFeedback(feedback);
        setSelectedBatchId((previous) => {
          if (previous && runs.items.some((item) => item.batch_id === previous)) {
            return previous;
          }
          const preferredRun =
            runs.items.find(
              (item) => item.status === "completed" && item.result_count > 0,
            ) ?? runs.items[0];
          return preferredRun?.batch_id ?? null;
        });
      } catch (error) {
        if (!active) return;
        setFeedbackError(toErrorMessage(error));
      } finally {
        if (active) {
          setFeedbackLoading(false);
        }
      }
    };
    void loadSchemeContext();
    return () => {
      active = false;
    };
  }, [selectedSchemeId, reloadToken]);

  useEffect(() => {
    if (!selectedBatchId) {
      setSelectedBatchResults(null);
      setSelectedSymbol(null);
      return;
    }
    let active = true;
    const loadBatchResults = async () => {
      setResultsLoading(true);
      setResultsError(null);
      try {
        const response = await getScreenerBatchResults(selectedBatchId);
        if (!active) return;
        setSelectedBatchResults(response);
        setSelectedSymbol((previous) => {
          if (previous && response.results.some((item) => item.symbol === previous)) {
            return previous;
          }
          return response.results[0]?.symbol ?? null;
        });
      } catch (error) {
        if (!active) return;
        setResultsError(toErrorMessage(error));
      } finally {
        if (active) {
          setResultsLoading(false);
        }
      }
    };
    void loadBatchResults();
    return () => {
      active = false;
    };
  }, [selectedBatchId]);

  useEffect(() => {
    if (screenerRun?.status === "running") {
      return;
    }
    setReloadToken((value) => value + 1);
  }, [screenerRun?.status]);

  const allResults = useMemo(
    () => selectedBatchResults?.results ?? [],
    [selectedBatchResults?.results],
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

  useEffect(() => {
    setCurrentPage(1);
  }, [filters, pageSize, selectedBatchId]);

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

  const selectedResult =
    selectedSymbol == null
      ? null
      : filteredResults.find((item) => item.symbol === selectedSymbol) ??
        allResults.find((item) => item.symbol === selectedSymbol) ??
        null;

  const selectedRunSummary =
    selectedBatchId == null
      ? null
      : schemeRuns?.items.find((item) => item.batch_id === selectedBatchId) ?? null;

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
      .catch((error) => {
        if (!active) return;
        setEvaluationError(toErrorMessage(error));
      })
      .finally(() => {
        if (!active) return;
        setEvaluationLoadingVersion(null);
      });

    return () => {
      active = false;
    };
  }, [evaluationByVersion, selectedResult?.predictive_model_version]);

  const isScreenerRunning = screenerRun?.status === "running";

  const handleRunScreener = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setScreenerError(null);
    setResetMessage(null);
    if (isScreenerRunning) {
      setScreenerError("当前已有运行中的初筛任务，请等待完成后再发起新的方案运行。");
      return;
    }
    if (!selectedSchemeId) {
      setScreenerError("请先选择一套方案。");
      return;
    }
    try {
      const response = await runScreenerWorkflow({
        batch_size: parseOptionalInteger(batchSize),
        max_symbols: parseOptionalInteger(maxSymbols),
        force_refresh: forceRefresh,
        scheme_id: selectedSchemeId,
      });
      setScreenerRun({ ...response, final_output: null });
      if (response.accepted === false && response.existing_run_id) {
        setScreenerError(response.message ?? "当前已有运行中的初筛任务。");
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

  const updateFilter = <K extends keyof ResultFilters>(
    key: K,
    value: ResultFilters[K],
  ) => {
    setFilters((previous) => ({ ...previous, [key]: value }));
  };

  return (
    <div className="space-y-6">
      <ContextOverview
        schemeName={schemeDetail?.scheme.name ?? null}
        schemeVersion={
          schemeDetail?.current_version_detail?.version_label ??
          schemeDetail?.scheme.current_version ??
          null
        }
        batchId={selectedBatchResults?.batch.batch_id ?? selectedBatchId}
        batchStatus={selectedBatchResults?.batch.status ?? selectedRunSummary?.status ?? null}
        selectedResultCount={filteredResults.length}
        selectedSymbol={selectedResult?.symbol ?? null}
      />

      <ScreenerSchemePanel
        schemes={schemes}
        selectedSchemeId={selectedSchemeId}
        schemeDetail={schemeDetail}
        loading={schemeLoading}
        error={schemeError}
        onSelectScheme={setSelectedSchemeId}
      />

      <ScreenerRunPanel
        schemeDetail={schemeDetail}
        screenerRun={screenerRun}
        screenerError={screenerError}
        batchSize={batchSize}
        setBatchSize={setBatchSize}
        maxSymbols={maxSymbols}
        setMaxSymbols={setMaxSymbols}
        forceRefresh={forceRefresh}
        setForceRefresh={setForceRefresh}
        isRunning={isScreenerRunning}
        onRun={handleRunScreener}
        onResetCursor={handleResetCursor}
        resetLoading={resetLoading}
        resetMessage={resetMessage}
      />

      <ScreenerResultPanel
        batch={selectedBatchResults?.batch ?? null}
        loading={resultsLoading}
        error={resultsError}
        results={pagedResults}
        filteredResults={filteredResults}
        selectedSymbol={selectedSymbol}
        onSelectSymbol={(symbol) =>
          setSelectedSymbol((previous) => (previous === symbol ? null : symbol))
        }
        filters={filters}
        onUpdateFilter={updateFilter}
        currentPage={currentPage}
        totalPages={totalPages}
        totalResults={filteredResults.length}
        pageSize={pageSize}
        onPageChange={setCurrentPage}
        onPageSizeChange={(value) => {
          setPageSize(value);
          setCurrentPage(1);
        }}
        evaluationByVersion={evaluationByVersion}
        evaluationLoadingVersion={evaluationLoadingVersion}
        evaluationError={evaluationError}
      />

      <ScreenerReviewPanel
        runs={schemeRuns}
        stats={schemeStats}
        feedback={schemeFeedback}
        loading={feedbackLoading}
        error={feedbackError}
        selectedBatchId={selectedBatchId}
        onSelectBatchId={setSelectedBatchId}
      />

      <details className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-950">
          高级操作（深筛工作流）
        </summary>
        <div className="mt-4 space-y-6">
          <SectionCard
            title="深筛工作流（保持兼容）"
            description="深筛仍保留为二次筛选入口，建议先完成当前方案的初筛运行后再继续。"
          >
            <form className="grid gap-4 md:grid-cols-4" onSubmit={handleRunDeep}>
              <ScreenerField
                label="最大股票数（max_symbols）"
                value={deepMaxSymbols}
                onChange={setDeepMaxSymbols}
              />
              <ScreenerField
                label="候选上限（top_n）"
                value={deepTopN}
                onChange={setDeepTopN}
              />
              <ScreenerField
                label="深筛数量（deep_top_k）"
                value={deepTopK}
                onChange={setDeepTopK}
              />
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

function ContextOverview({
  schemeName,
  schemeVersion,
  batchId,
  batchStatus,
  selectedResultCount,
  selectedSymbol,
}: {
  schemeName: string | null;
  schemeVersion: string | null;
  batchId: string | null;
  batchStatus: string | null;
  selectedResultCount: number;
  selectedSymbol: string | null;
}) {
  return (
    <SectionCard
      title="当前查看上下文"
      description="先确认你当前看的是哪套方案、哪次批次、哪只股票，后面的结果和反馈都会围绕这个上下文变化。"
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <ScreenerMetric label="当前方案" value={schemeName ?? "尚未选择"} />
        <ScreenerMetric label="方案版本" value={schemeVersion ?? "-"} />
        <ScreenerMetric label="当前批次" value={batchId ?? "尚未选中"} />
        <ScreenerMetric label="批次状态" value={batchStatus ?? "-"} />
        <ScreenerMetric label="当前明细股票" value={selectedSymbol ?? "-"} />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <ScreenerMetric label="当前候选数" value={String(selectedResultCount)} />
        <ScreenerMetric
          label="如何切换批次"
          value="在反馈区点击历史运行行"
        />
        <ScreenerMetric
          label="如何切换股票"
          value="在结果区点击候选行"
        />
      </div>
    </SectionCard>
  );
}

function useWorkflowPolling(
  runId: string | null,
  setRun: Dispatch<SetStateAction<WorkflowRunDetailResponse | null>>,
) {
  const inFlightRef = useRef(false);

  useEffect(() => {
    if (!runId) return;
    let active = true;
    const poll = async () => {
      if (!active || inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        const detail = await getWorkflowRunDetail(runId);
        if (!active) {
          inFlightRef.current = false;
          return;
        }
        setRun(detail);
      } catch {
        // 保持当前状态，避免短暂网络波动打断展示。
      } finally {
        inFlightRef.current = false;
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), POLL_MS);
    return () => {
      active = false;
      inFlightRef.current = false;
      window.clearInterval(timer);
    };
  }, [runId, setRun]);
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
          <article
            key={candidate.symbol}
            className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
          >
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <ScreenerMetric label="股票" value={`${candidate.name} / ${candidate.symbol}`} />
              <ScreenerMetric label="优先级" value={String(candidate.priority_score)} />
              <ScreenerMetric label="研究动作" value={candidate.research_action} />
              <ScreenerMetric label="策略动作" value={candidate.strategy_action} />
              <ScreenerMetric
                label="预测分"
                value={
                  candidate.predictive_score === null || candidate.predictive_score === undefined
                    ? "-"
                    : String(candidate.predictive_score)
                }
              />
              <ScreenerMetric
                label="模型版本"
                value={candidate.predictive_model_version ?? "-"}
              />
            </div>
          </article>
        ))
      )}
    </div>
  );
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
