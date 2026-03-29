"use client";

import Link from "next/link";
import type { Dispatch, SetStateAction } from "react";
import { useEffect, useState } from "react";

import {
  getDataRefreshStatus,
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
  formatListType,
  formatPrice,
  formatRange,
  formatScore,
} from "@/lib/format";
import type {
  DataRefreshStatus,
  DeepScreenerRunResponse,
  ScreenerCandidate,
  ScreenerRunResponse,
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

  useEffect(() => {
    void getDataRefreshStatus()
      .then(setRefreshStatus)
      .catch((error) => setRefreshError(toErrorMessage(error)));
  }, []);

  useWorkflowPolling(screenerRun?.status === "running" ? screenerRun.run_id : null, setScreenerRun);
  useWorkflowPolling(deepRun?.status === "running" ? deepRun.run_id : null, setDeepRun);

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

  const handleScreenerRun = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setScreenerError(null);
    try {
      const response = await runScreenerWorkflow({
        max_symbols: parseOptionalInteger(maxSymbols),
        top_n: parseOptionalInteger(topN),
      });
      setScreenerRun({ ...response, final_output: null });
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

  return (
    <div className="space-y-6">
      <SectionCard
        title="Data Refresh"
        description="Refresh local inputs first when needed. The screener itself now runs in workflow mode instead of waiting on a long synchronous page request."
      >
        <form className="grid gap-4 md:grid-cols-3" onSubmit={handleRefresh}>
          <Field label="max_symbols" value={maxSymbols} onChange={setMaxSymbols} />
          <div className="md:col-span-2 flex items-end gap-3">
            <button
              type="submit"
              disabled={refreshLoading}
              className="min-h-11 rounded-2xl bg-amber-600 px-5 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:bg-amber-300"
            >
              {refreshLoading ? "Starting refresh..." : "Start Refresh"}
            </button>
          </div>
        </form>
        <div className="mt-5 space-y-4">
          {refreshError ? <StatusBlock title="Refresh failed" description={refreshError} tone="error" /> : null}
          {refreshStatus ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric label="Status" value={refreshStatus.status} />
              <Metric label="Current stage" value={refreshStatus.current_stage ?? "-"} />
              <Metric label="Processed" value={`${refreshStatus.processed_symbols}/${refreshStatus.total_symbols}`} />
              <Metric label="Updated at" value={formatDateTime(refreshStatus.finished_at ?? refreshStatus.started_at)} />
            </div>
          ) : (
            <StatusBlock title="No refresh status" description="No refresh task has been loaded yet." />
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="Initial Screener Workflow"
        description="The page now starts the screener workflow immediately, returns a run_id, and polls workflow run details until the result snapshot is ready."
      >
        <form className="grid gap-4 md:grid-cols-3" onSubmit={handleScreenerRun}>
          <Field label="max_symbols" value={maxSymbols} onChange={setMaxSymbols} />
          <Field label="top_n" value={topN} onChange={setTopN} />
          <div className="flex items-end">
            <button
              type="submit"
              className="min-h-11 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800"
            >
              Start Screener Workflow
            </button>
          </div>
        </form>
        <div className="mt-5 space-y-4">
          {screenerError ? <StatusBlock title="Screener workflow failed to start" description={screenerError} tone="error" /> : null}
          {screenerRun ? <WorkflowRunSummary run={screenerRun} /> : <StatusBlock title="Waiting to run" description="Submit the screener workflow to get a run_id and step summaries." />}
          {renderScreenerFinalOutput(screenerRun)}
        </div>
      </SectionCard>

      <SectionCard
        title="Deep Review Workflow"
        description="Deep review also runs as a workflow now, so the page can show run_id, current step, and final output without keeping one long HTTP request open."
      >
        <form className="grid gap-4 md:grid-cols-4" onSubmit={handleDeepRun}>
          <Field label="max_symbols" value={maxSymbols} onChange={setMaxSymbols} />
          <Field label="top_n" value={topN} onChange={setTopN} />
          <Field label="deep_top_k" value={deepTopK} onChange={setDeepTopK} />
          <div className="flex items-end">
            <button
              type="submit"
              className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              Start Deep Review Workflow
            </button>
          </div>
        </form>
        <div className="mt-5 space-y-4">
          {deepError ? <StatusBlock title="Deep review workflow failed to start" description={deepError} tone="error" /> : null}
          {deepRun ? <WorkflowRunSummary run={deepRun} /> : <StatusBlock title="Waiting to run" description="Submit the deep review workflow to get a run_id and step summaries." />}
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
        // Keep latest state.
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
    return <StatusBlock title="No screener output" description="The workflow finished without a screener final output." tone="error" />;
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
        <Metric label="As-of date" value={formatDate(finalOutput.as_of_date)} />
        <Metric label="Freshness" value={finalOutput.freshness_mode ?? "-"} />
        <Metric label="Source mode" value={finalOutput.source_mode ?? "-"} />
        <Metric label="Scanned" value={`${finalOutput.scanned_symbols}/${finalOutput.total_symbols}`} />
      </div>
      {buckets.map(([title, items]) => (
        <div key={title} className="space-y-3">
          <h3 className="text-base font-semibold text-slate-900">
            {title} / {formatListType(title as ScreenerCandidate["v2_list_type"])}
          </h3>
          {items.length === 0 ? (
            <StatusBlock title="No candidates" description={`No ${title} candidates for this run.`} />
          ) : (
            items.map((candidate) => <CandidateCard key={candidate.symbol} candidate={candidate} />)
          )}
        </div>
      ))}
    </div>
  );
}

function renderDeepFinalOutput(run: WorkflowRunDetailResponse | null) {
  const finalOutput = run?.final_output as { candidates?: DeepScreenerRunResponse["deep_candidates"] } | null;
  if (!run || run.status === "running") return null;
  if (!finalOutput || !Array.isArray(finalOutput.candidates)) {
    return <StatusBlock title="No deep review output" description="The workflow finished without deep review candidates." tone="error" />;
  }
  return (
    <div className="space-y-4">
      {finalOutput.candidates.length === 0 ? (
        <StatusBlock title="No deep review candidates" description="This deep review run did not produce any candidates." />
      ) : (
        finalOutput.candidates.map((candidate) => (
          <article key={candidate.symbol} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h4 className="text-base font-semibold text-slate-950">{candidate.name}</h4>
                <p className="mt-1 text-sm text-slate-600">{candidate.symbol}</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">{candidate.short_reason}</p>
              </div>
              <Link href={`/stocks/${encodeURIComponent(candidate.symbol)}`} className="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800">
                Open stock page
              </Link>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="Priority" value={formatScore(candidate.priority_score)} />
              <Metric label="Research action" value={formatAction(candidate.research_action)} />
              <Metric label="Strategy action" value={formatAction(candidate.strategy_action)} />
              <Metric label="Strategy type" value={candidate.strategy_type} />
              <Metric label="Entry range" value={formatRange(candidate.ideal_entry_range)} />
              <Metric label="Stop-loss" value={formatPrice(candidate.stop_loss_price)} />
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
        <Link href={`/stocks/${encodeURIComponent(candidate.symbol)}`} className="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800">
          Open stock page
        </Link>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <Metric label="Action now" value={candidate.action_now ? formatDecisionBriefAction(candidate.action_now) : "-"} />
        <Metric label="Alpha" value={formatScore(candidate.alpha_score)} />
        <Metric label="Trigger" value={formatScore(candidate.trigger_score)} />
        <Metric label="Risk" value={formatScore(candidate.risk_score)} />
        <Metric label="Latest close" value={formatPrice(candidate.latest_close)} />
        <Metric label="Bucket" value={candidate.v2_list_type} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <StringPanel title="Positive factors" items={candidate.top_positive_factors} />
        <StringPanel title="Evidence hints" items={candidate.evidence_hints} />
      </div>
    </article>
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
        <p className="mt-3 text-sm leading-6 text-slate-600">No items.</p>
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
  return "An unexpected error occurred.";
}
