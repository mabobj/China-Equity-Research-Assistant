"use client";

import Link from "next/link";
import type { Dispatch, SetStateAction } from "react";
import { useEffect, useState } from "react";

import {
  getDataRefreshStatus,
  getLatestScreenerBatch,
  getScreenerBatchResults,
  getWorkflowRunDetail,
  runDeepReviewWorkflow,
  runScreenerWorkflow,
  startDataRefresh,
} from "@/lib/api";
import {
  formatAction,
  formatDate,
  formatDateTime,
  formatDecisionBriefAction,
  formatLabel,
  formatListType,
  formatPrice,
  formatRange,
  formatScore,
} from "@/lib/format";
import type {
  DataRefreshStatus,
  DeepScreenerRunResponse,
  ScreenerBatchRecord,
  ScreenerBatchResultsResponse,
  ScreenerCandidate,
  ScreenerRunResponse,
  ScreenerSymbolResult,
  WorkflowRunDetailResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";
import { WorkflowRunSummary } from "./workflow-run-summary";

const POLL_MS = 1500;

export function ScreenerWorkspace() {
  const [refreshStatus, setRefreshStatus] = useState<DataRefreshStatus | null>(null);
  const [refreshLoading, setRefreshLoading] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [maxSymbols, setMaxSymbols] = useState("50");
  const [topN, setTopN] = useState("20");
  const [deepTopK, setDeepTopK] = useState("8");
  const [screenerRun, setScreenerRun] = useState<WorkflowRunDetailResponse | null>(null);
  const [deepRun, setDeepRun] = useState<WorkflowRunDetailResponse | null>(null);
  const [screenerError, setScreenerError] = useState<string | null>(null);
  const [deepError, setDeepError] = useState<string | null>(null);
  const [latestBatch, setLatestBatch] = useState<ScreenerBatchRecord | null>(null);
  const [latestBatchResults, setLatestBatchResults] = useState<ScreenerSymbolResult[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [selectedBatchSymbol, setSelectedBatchSymbol] = useState<string | null>(null);
  const [batchReloadToken, setBatchReloadToken] = useState(0);

  useEffect(() => {
    void getDataRefreshStatus()
      .then(setRefreshStatus)
      .catch((error) => setRefreshError(toErrorMessage(error)));
  }, []);

  useEffect(() => {
    let active = true;
    const loadLatestBatch = async () => {
      setBatchLoading(true);
      setBatchError(null);
      try {
        const latest = await getLatestScreenerBatch();
        if (!active) return;
        setLatestBatch(latest.batch);
        if (!latest.batch) {
          setLatestBatchResults([]);
          setSelectedBatchSymbol(null);
          return;
        }
        const resultsResponse: ScreenerBatchResultsResponse =
          await getScreenerBatchResults(latest.batch.batch_id);
        if (!active) return;
        setLatestBatchResults(resultsResponse.results);
        setSelectedBatchSymbol((previous) => {
          if (
            previous &&
            resultsResponse.results.some((item) => item.symbol === previous)
          ) {
            return previous;
          }
          return resultsResponse.results[0]?.symbol ?? null;
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
    void loadLatestBatch();
    return () => {
      active = false;
    };
  }, [batchReloadToken]);

  useEffect(() => {
    if (!screenerRun) return;
    if (screenerRun.status !== "running") {
      setBatchReloadToken((value) => value + 1);
    }
  }, [screenerRun]);

  useWorkflowPolling(
    screenerRun?.status === "running" ? screenerRun.run_id : null,
    setScreenerRun,
  );
  useWorkflowPolling(
    deepRun?.status === "running" ? deepRun.run_id : null,
    setDeepRun,
  );

  const handleRefresh = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setRefreshLoading(true);
    setRefreshError(null);
    try {
      setRefreshStatus(
        await startDataRefresh({
          maxSymbols: parseOptionalInteger(maxSymbols),
        }),
      );
    } catch (error) {
      setRefreshError(toErrorMessage(error));
    } finally {
      setRefreshLoading(false);
    }
  };

  const isScreenerRunning =
    screenerRun?.status === "running" || latestBatch?.status === "running";

  const handleScreenerRun = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setScreenerError(null);
    if (isScreenerRunning) {
      setScreenerError("已有运行中的初筛任务，请先等待当前任务完成。");
      return;
    }
    try {
      const response = await runScreenerWorkflow({
        max_symbols: parseOptionalInteger(maxSymbols),
        top_n: parseOptionalInteger(topN),
      });
      setScreenerRun({ ...response, final_output: null });
      if (response.status !== "running") {
        setBatchReloadToken((value) => value + 1);
      }
    } catch (error) {
      setScreenerError(toErrorMessage(error));
    }
  };

  const handleDeepRun = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDeepError(null);
    try {
      const response = await runDeepReviewWorkflow({
        max_symbols: parseOptionalInteger(maxSymbols),
        top_n: parseOptionalInteger(topN),
        deep_top_k: parseOptionalInteger(deepTopK),
      });
      setDeepRun({ ...response, final_output: null });
    } catch (error) {
      setDeepError(toErrorMessage(error));
    }
  };

  const selectedBatchResult = selectedBatchSymbol
    ? latestBatchResults.find((item) => item.symbol === selectedBatchSymbol) ?? null
    : null;

  return (
    <div className="space-y-6">
      <SectionCard
        title="数据刷新"
        description="需要时可先补齐本地数据。选股页面当前以工作流方式运行，不再依赖超长同步请求。"
      >
        <form className="grid gap-4 md:grid-cols-3" onSubmit={handleRefresh}>
          <Field label="最大股票数（max_symbols）" value={maxSymbols} onChange={setMaxSymbols} />
          <div className="md:col-span-2 flex items-end gap-3">
            <button
              type="submit"
              disabled={refreshLoading}
              className="min-h-11 rounded-2xl bg-amber-600 px-5 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:bg-amber-300"
            >
              {refreshLoading ? "正在启动刷新..." : "开始刷新"}
            </button>
          </div>
        </form>
        <div className="mt-5 space-y-4">
          {refreshError ? (
            <StatusBlock title="刷新失败" description={refreshError} tone="error" />
          ) : null}
          {refreshStatus ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric label="状态" value={formatLabel(refreshStatus.status)} />
              <Metric label="当前阶段" value={formatLabel(refreshStatus.current_stage ?? "-")} />
              <Metric
                label="处理进度"
                value={`${refreshStatus.processed_symbols}/${refreshStatus.total_symbols}`}
              />
              <Metric
                label="更新时间"
                value={formatDateTime(refreshStatus.finished_at ?? refreshStatus.started_at)}
              />
            </div>
          ) : (
            <StatusBlock
              title="暂无刷新状态"
              description="还没有加载任何刷新任务状态。"
            />
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="初筛工作流"
        description="提交后会立即返回 run_id，并轮询工作流运行记录直到结果落盘。"
      >
        <form className="grid gap-4 md:grid-cols-3" onSubmit={handleScreenerRun}>
          <Field label="最大股票数（max_symbols）" value={maxSymbols} onChange={setMaxSymbols} />
          <Field label="候选上限（top_n）" value={topN} onChange={setTopN} />
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
          {isScreenerRunning ? (
            <StatusBlock
              title="运行中任务"
              description={`当前初筛任务正在运行，run_id=${screenerRun?.run_id ?? latestBatch?.run_id ?? "-"}`}
            />
          ) : null}
          {screenerError ? (
            <StatusBlock title="初筛工作流启动失败" description={screenerError} tone="error" />
          ) : null}
          {screenerRun ? (
            <WorkflowRunSummary run={screenerRun} />
          ) : (
            <StatusBlock
              title="等待执行"
              description="提交初筛工作流后会返回 run_id 和步骤摘要。"
            />
          )}
          {screenerRun?.warning_messages?.length ? (
            <StatusBlock
              title="运行提示"
              description={screenerRun.warning_messages.join("；")}
            />
          ) : null}
          {renderScreenerFinalOutput(screenerRun)}
        </div>
      </SectionCard>

      <SectionCard
        title="最新初筛批次"
        description="批次台账会沉淀每次初筛结果，可查看每只股票的评分、规则版本与计算时间。"
      >
        <div className="space-y-4">
          {batchLoading ? (
            <StatusBlock title="批次加载中" description="正在读取最新批次结果..." />
          ) : null}
          {batchError ? (
            <StatusBlock title="批次加载失败" description={batchError} tone="error" />
          ) : null}
          {!batchLoading && !batchError && !latestBatch ? (
            <StatusBlock
              title="暂无批次"
              description="尚未生成可查看的初筛批次，请先运行一次初筛工作流。"
            />
          ) : null}
          {latestBatch ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Metric label="批次 ID" value={latestBatch.batch_id} />
                <Metric label="交易日" value={formatDate(latestBatch.trade_date)} />
                <Metric label="批次状态" value={formatLabel(latestBatch.status)} />
                <Metric label="关联运行" value={latestBatch.run_id} />
                <Metric
                  label="扫描规模"
                  value={`${latestBatch.scanned_size}/${latestBatch.universe_size}`}
                />
                <Metric label="规则版本" value={latestBatch.rule_version} />
                <Metric label="开始时间" value={formatDateTime(latestBatch.started_at)} />
                <Metric
                  label="完成时间"
                  value={
                    latestBatch.finished_at
                      ? formatDateTime(latestBatch.finished_at)
                      : "-"
                  }
                />
              </div>
              {latestBatch.failure_reason ? (
                <StatusBlock
                  title="批次失败说明"
                  description={latestBatch.failure_reason}
                  tone="error"
                />
              ) : null}
              {latestBatch.warning_messages.length ? (
                <StatusBlock
                  title="批次告警"
                  description={latestBatch.warning_messages.join("；")}
                />
              ) : null}
              <BatchResultTable
                results={latestBatchResults}
                selectedSymbol={selectedBatchSymbol}
                onSelectSymbol={(symbol) => setSelectedBatchSymbol(symbol)}
              />
              {selectedBatchResult ? (
                <BatchResultDetail result={selectedBatchResult} />
              ) : null}
            </>
          ) : null}
        </div>
      </SectionCard>

      <SectionCard
        title="深筛工作流"
        description="深筛同样使用工作流模式，页面可查看 run_id、当前步骤、局部失败与最终结果。"
      >
        <form className="grid gap-4 md:grid-cols-4" onSubmit={handleDeepRun}>
          <Field label="最大股票数（max_symbols）" value={maxSymbols} onChange={setMaxSymbols} />
          <Field label="候选上限（top_n）" value={topN} onChange={setTopN} />
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
              description="提交深筛工作流后会返回 run_id 和步骤摘要。"
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

function renderScreenerFinalOutput(run: WorkflowRunDetailResponse | null) {
  const finalOutput = run?.final_output as ScreenerRunResponse | null;
  if (!run || run.status === "running") return null;
  if (!finalOutput) {
    return (
      <StatusBlock
        title="无初筛输出"
        description="工作流已结束，但没有返回初筛结果。"
        tone="error"
      />
    );
  }

  const buckets: Array<[string, ScreenerCandidate[]]> = [
    ["READY_TO_BUY", finalOutput.ready_to_buy_candidates],
    ["WATCH_PULLBACK", finalOutput.watch_pullback_candidates],
    ["WATCH_BREAKOUT", finalOutput.watch_breakout_candidates],
    ["RESEARCH_ONLY", finalOutput.research_only_candidates],
    ["AVOID", finalOutput.avoid_candidates],
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="截至日期" value={formatDate(finalOutput.as_of_date)} />
        <Metric label="新鲜度模式" value={finalOutput.freshness_mode ?? "-"} />
        <Metric label="来源模式" value={finalOutput.source_mode ?? "-"} />
        <Metric
          label="扫描进度"
          value={`${finalOutput.scanned_symbols}/${finalOutput.total_symbols}`}
        />
      </div>
      {buckets.map(([title, items]) => (
        <div key={title} className="space-y-3">
          <h3 className="text-base font-semibold text-slate-900">
            {formatListType(title as ScreenerCandidate["v2_list_type"])}（{title}）
          </h3>
          {items.length === 0 ? (
            <StatusBlock title="暂无候选" description={`本次运行没有 ${title} 分桶候选。`} />
          ) : (
            items.map((candidate) => <CandidateCard key={candidate.symbol} candidate={candidate} />)
          )}
        </div>
      ))}
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

function CandidateCard({ candidate }: { candidate: ScreenerCandidate }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-base font-semibold text-slate-950">{candidate.name}</h4>
          <p className="mt-1 text-sm text-slate-600">{candidate.symbol}</p>
          <p className="mt-2 text-sm font-semibold leading-6 text-slate-900">
            {candidate.headline_verdict ?? candidate.short_reason}
          </p>
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
        <Metric
          label="当前动作"
          value={candidate.action_now ? formatDecisionBriefAction(candidate.action_now) : "-"}
        />
        <Metric label="Alpha 分" value={formatScore(candidate.alpha_score)} />
        <Metric label="触发分" value={formatScore(candidate.trigger_score)} />
        <Metric label="风险分" value={formatScore(candidate.risk_score)} />
        <Metric label="最新收盘价" value={formatPrice(candidate.latest_close)} />
        <Metric
          label="分桶"
          value={`${formatListType(candidate.v2_list_type)}（${candidate.v2_list_type}）`}
        />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Metric
          label="计算时间"
          value={candidate.calculated_at ? formatDateTime(candidate.calculated_at) : "-"}
        />
        <Metric label="规则版本" value={candidate.rule_version ?? "-"} />
        <Metric label="规则说明" value={candidate.rule_summary ?? "-"} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <StringPanel title="正向因子" items={candidate.top_positive_factors} />
        <StringPanel title="证据提示" items={candidate.evidence_hints} />
      </div>
    </article>
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
    return <StatusBlock title="批次结果为空" description="该批次还没有可展示的股票结果。" />;
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
              key={item.symbol}
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
      </div>
    </div>
  );
}

function Field({
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
