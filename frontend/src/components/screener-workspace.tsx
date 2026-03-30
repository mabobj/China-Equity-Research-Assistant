"use client";

import Link from "next/link";
import type { Dispatch, SetStateAction } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  getLatestScreenerBatch,
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
  formatPrice,
  formatRange,
  formatScore,
} from "@/lib/format";
import type {
  DeepScreenerRunResponse,
  ScreenerListType,
  ScreenerLatestBatchResponse,
  ScreenerSymbolResult,
  WorkflowRunDetailResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";
import { WorkflowRunSummary } from "./workflow-run-summary";

const POLL_MS = 1500;

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
  const [latestBatch, setLatestBatch] = useState<ScreenerLatestBatchResponse | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [filters, setFilters] = useState<ResultFilters>(INITIAL_FILTERS);
  const [reloadToken, setReloadToken] = useState(0);

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
      setBatchLoading(true);
      setBatchError(null);
      try {
        const response = await getLatestScreenerBatch();
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
        setBatchError(toErrorMessage(error));
      } finally {
        if (active) {
          setBatchLoading(false);
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

  const ruleVersions = useMemo(() => {
    return [...new Set(allResults.map((item) => item.rule_version).filter(Boolean))];
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

  return (
    <div className="space-y-6">
      <SectionCard
        title="初筛工作流"
        description="按游标分批运行初筛。输入本批次计算股票数量，系统会自动从当前游标继续。"
      >
        <form className="grid gap-4 md:grid-cols-3" onSubmit={handleRunScreener}>
          <Field
            label="本批次计算股票数量（batch_size）"
            value={batchSize}
            onChange={setBatchSize}
            placeholder="例如 50"
          />
          <div className="flex items-end gap-3">
            <button
              type="submit"
              disabled={isScreenerRunning}
              className="min-h-11 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:bg-emerald-300"
            >
              {isScreenerRunning ? "已有运行中的初筛任务" : "运行初筛工作流"}
            </button>
            <button
              type="button"
              onClick={handleResetCursor}
              disabled={resetLoading || isScreenerRunning}
              className="min-h-11 rounded-2xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:text-slate-400"
            >
              {resetLoading ? "重置中..." : "重置游标"}
            </button>
          </div>
        </form>
        <div className="mt-5 space-y-4">
          {resetMessage ? <StatusBlock title="游标重置" description={resetMessage} /> : null}
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

      <SectionCard
        title="当前展示窗口"
        description="17:00 前展示前一日 17:00 后完成结果；17:00 后展示当日 17:00 后完成结果。"
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

              <BatchFilterPanel
                filters={filters}
                setFilters={setFilters}
                ruleVersions={ruleVersions}
              />
              <BatchResultTable
                results={filteredResults}
                selectedSymbol={selectedSymbol}
                onSelectSymbol={setSelectedSymbol}
              />
              {selectedResult ? <BatchResultDetail result={selectedResult} /> : null}
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
        title="深筛工作流（保持兼容）"
        description="深筛流程本轮不改逻辑，仍保持现有工作流入口。"
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
            <option value="READY_TO_BUY">READY_TO_BUY</option>
            <option value="WATCH_PULLBACK">WATCH_PULLBACK</option>
            <option value="WATCH_BREAKOUT">WATCH_BREAKOUT</option>
            <option value="RESEARCH_ONLY">RESEARCH_ONLY</option>
            <option value="AVOID">AVOID</option>
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

function BatchResultTable({
  results,
  selectedSymbol,
  onSelectSymbol,
}: {
  results: ScreenerSymbolResult[];
  selectedSymbol: string | null;
  onSelectSymbol: (symbol: string) => void;
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
            <th className="px-4 py-3">简述</th>
            <th className="px-4 py-3">计算时间</th>
            <th className="px-4 py-3">规则版本</th>
          </tr>
        </thead>
        <tbody>
          {results.map((item) => (
            <tr
              key={`${item.symbol}-${item.calculated_at}`}
              className={
                item.symbol === selectedSymbol
                  ? "border-t border-slate-200 bg-emerald-50"
                  : "border-t border-slate-200"
              }
            >
              <td className="px-4 py-3">
                <button
                  type="button"
                  onClick={() => onSelectSymbol(item.symbol)}
                  className="text-left font-semibold text-emerald-700 transition hover:text-emerald-800"
                >
                  {item.symbol}
                  <span className="ml-2 text-slate-900">{item.name}</span>
                </button>
              </td>
              <td className="px-4 py-3">{formatListType(item.list_type)}</td>
              <td className="px-4 py-3">{formatScore(item.screener_score)}</td>
              <td className="px-4 py-3">{item.short_reason}</td>
              <td className="px-4 py-3">{formatDateTime(item.calculated_at)}</td>
              <td className="px-4 py-3">{item.rule_version}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BatchResultDetail({ result }: { result: ScreenerSymbolResult }) {
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
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Metric label="支撑位" value={formatPrice(result.support_level)} />
        <Metric label="压力位" value={formatPrice(result.resistance_level)} />
        <Metric label="计算时间" value={formatDateTime(result.calculated_at)} />
      </div>
      <div className="mt-4 space-y-3">
        <Metric label="规则版本" value={result.rule_version} />
        <Metric label="规则说明" value={result.rule_summary} />
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
