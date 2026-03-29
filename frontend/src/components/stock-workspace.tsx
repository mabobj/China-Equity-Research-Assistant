"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { getDebateReviewProgress, getWorkspaceBundle, normalizeSymbolInput } from "@/lib/api";
import {
  formatAction,
  formatConvictionLevel,
  formatDate,
  formatDecisionBriefAction,
  formatLabel,
  formatPercent,
  formatPrice,
  formatRange,
  formatScore,
} from "@/lib/format";
import type {
  DebateReviewProgress,
  DecisionBriefEvidence,
  WorkspaceBundleResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { SingleStockWorkflowPanel } from "./single-stock-workflow-panel";
import { StatusBlock } from "./status-block";

type StockWorkspaceProps = { symbol: string };

export function StockWorkspace({ symbol }: StockWorkspaceProps) {
  const router = useRouter();
  const [inputValue, setInputValue] = useState(symbol);
  const [useLlm, setUseLlm] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [bundle, setBundle] = useState<WorkspaceBundleResponse | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<DebateReviewProgress | null>(null);

  useEffect(() => {
    setInputValue(symbol);
  }, [symbol]);

  useEffect(() => {
    let active = true;
    let timer: number | null = null;
    const requestId = useLlm ? buildRequestId(symbol) : undefined;

    setStatus("loading");
    setError(null);
    setBundle(null);
    setProgress(
      useLlm
        ? {
            symbol,
            request_id: requestId ?? null,
            status: "running",
            stage: "building_inputs",
            runtime_mode: "llm",
            current_step: "Waiting for workspace bundle",
            completed_steps: 0,
            total_steps: 9,
            message: "Workspace bundle submitted.",
            started_at: null,
            updated_at: null,
            finished_at: null,
            error_message: null,
            recent_steps: [],
          }
        : null,
    );

    if (useLlm && requestId) {
      const poll = async () => {
        try {
          const value = await getDebateReviewProgress(symbol, { useLlm: true, requestId });
          if (active) setProgress(value);
        } catch {
          // Keep last progress.
        }
      };
      void poll();
      timer = window.setInterval(() => void poll(), 1500);
    }

    void getWorkspaceBundle(symbol, {
      useLlm,
      requestId,
      forceRefresh: refreshToken > 0,
    })
      .then((value) => {
        if (!active) return;
        setBundle(value);
        setProgress((previous) => value.debate_progress ?? previous);
        setStatus("success");
      })
      .catch((cause) => {
        if (!active) return;
        setStatus("error");
        setError(cause instanceof Error ? cause.message : "Workspace bundle failed.");
      })
      .finally(() => {
        if (timer !== null) window.clearInterval(timer);
      });

    return () => {
      active = false;
      if (timer !== null) window.clearInterval(timer);
    };
  }, [refreshToken, symbol, useLlm]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = normalizeSymbolInput(inputValue);
    if (!normalized) return;
    router.push(`/stocks/${encodeURIComponent(normalized)}`);
  };

  const failedModules = useMemo(
    () => bundle?.module_status_summary.filter((item) => item.status === "error") ?? [],
    [bundle],
  );

  return (
    <div className="space-y-6">
      <SectionCard
        title="Single-Stock Workspace"
        description="The stock page now uses one workspace bundle as the main backend entry, plus optional LLM debate progress polling."
        actions={
          <button
            type="button"
            onClick={() => setRefreshToken((value) => value + 1)}
            className="rounded-2xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800"
          >
            Refresh Workspace
          </button>
        }
      >
        <form className="grid gap-4 lg:grid-cols-[1fr_auto_auto]" onSubmit={handleSubmit}>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">symbol</span>
            <input
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="600519.SH"
              className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
          </label>
          <label className="flex items-end">
            <span className="flex min-h-11 items-center gap-3 rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(event) => setUseLlm(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              Debate Review uses LLM
            </span>
          </label>
          <button
            type="submit"
            className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Switch Symbol
          </button>
        </form>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Metric label="Bundle status" value={formatLabel(status)} />
          <Metric
            label="Default as-of"
            value={formatDate(bundle?.freshness_summary.default_as_of_date ?? null)}
          />
          <Metric
            label="Success modules"
            value={String(bundle?.module_status_summary.filter((item) => item.status === "success").length ?? 0)}
          />
          <Metric label="Failed modules" value={String(failedModules.length)} />
          <Metric
            label="Runtime mode"
            value={formatLabel(bundle?.runtime_mode_effective ?? "-")}
          />
        </div>

        {status === "loading" ? <LoadingBlock progress={progress} useLlm={useLlm} /> : null}
        {status === "error" ? (
          <div className="mt-5">
            <StatusBlock title="Workspace bundle failed" description={error ?? "Please retry later."} tone="error" />
          </div>
        ) : null}
        {failedModules.length > 0 ? (
          <div className="mt-5">
            <StatusBlock
              title="Partial module failures"
              description={`Failed modules: ${failedModules.map((item) => item.module_name).join(", ")}.`}
              tone="error"
            />
          </div>
        ) : null}
        {bundle?.fallback_applied ? (
          <div className="mt-5">
            <StatusBlock
              title="Fallback applied"
              description={
                bundle.fallback_reason ??
                "Runtime fallback was applied. See warning messages for details."
              }
              tone="error"
            />
          </div>
        ) : null}
        {bundle && bundle.warning_messages.length > 0 ? (
          <div className="mt-5">
            <StatusBlock
              title="Runtime warnings"
              description={bundle.warning_messages.join(" | ")}
            />
          </div>
        ) : null}
      </SectionCard>

      {bundle ? (
        <>
          <SectionCard title="Decision Brief" description="Read the verdict first, then check the evidence and the action layer.">
            {bundle.decision_brief ? (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <Metric label="Action now" value={formatDecisionBriefAction(bundle.decision_brief.action_now)} />
                  <Metric label="Conviction" value={formatConvictionLevel(bundle.decision_brief.conviction_level)} />
                  <Metric label="As-of date" value={formatDate(bundle.decision_brief.as_of_date)} />
                  <Metric label="Next review" value={formatLabel(bundle.decision_brief.next_review_window)} />
                </div>
                <TextPanel title={bundle.decision_brief.name} content={bundle.decision_brief.headline_verdict} />
                <div className="grid gap-4 lg:grid-cols-2">
                  <StringPanel title="Why it made the list" items={bundle.decision_brief.why_it_made_the_list} />
                  <StringPanel title="Why not all-in" items={bundle.decision_brief.why_not_all_in} />
                </div>
              </div>
            ) : (
              <StatusBlock title="No decision brief" description="This workspace bundle did not return a decision brief." />
            )}
          </SectionCard>

          <SectionCard title="Evidence and Actions" description="These evidence items and action hints are traceable to real lower-module outputs.">
            {bundle.decision_brief ? (
              <div className="space-y-4">
                <div className="grid gap-4 lg:grid-cols-2">
                  <EvidencePanel title="Positive evidence" items={bundle.decision_brief.key_evidence} />
                  <EvidencePanel title="Risk evidence" items={bundle.decision_brief.key_risks} />
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <StringPanel title="What to do next" items={bundle.decision_brief.what_to_do_next} />
                  <StringPanel
                    title="Source modules"
                    items={bundle.decision_brief.source_modules.map((item) => `${item.module_name}${item.note ? ` / ${item.note}` : ""}`)}
                  />
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <StringPanel
                    title="Price levels"
                    items={bundle.decision_brief.price_levels_to_watch.map((item) => `${item.label}: ${item.value_text}${item.note ? ` / ${item.note}` : ""}`)}
                  />
                  <StringPanel
                    title="Evidence manifest"
                    items={(bundle.evidence_manifest?.bundles ?? []).flatMap((item) =>
                      item.refs.slice(0, 3).map((ref) => `${ref.dataset} / ${ref.provider} / ${ref.field_path}`),
                    )}
                  />
                </div>
              </div>
            ) : (
              <StatusBlock title="No evidence layer" description="Decision brief evidence is unavailable." />
            )}
          </SectionCard>

          <SectionCard title="Detailed Modules" description="The lower modules are still available, but now sit below the conclusion layer.">
            <div className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Profile">
                  {bundle.profile ? (
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <Metric label="Name" value={bundle.profile.name} />
                      <Metric label="Industry" value={bundle.profile.industry ?? "-"} />
                      <Metric label="List date" value={formatDate(bundle.profile.list_date)} />
                      <Metric label="Status" value={bundle.profile.status ?? "-"} />
                      <Metric label="Market cap" value={bundle.profile.total_market_cap === null ? "-" : String(bundle.profile.total_market_cap)} />
                      <Metric label="Source" value={bundle.profile.source} />
                    </div>
                  ) : (
                    <StatusBlock title="Unavailable" description="Profile data is unavailable." />
                  )}
                </Panel>

                <Panel title="Freshness summary">
                  <div className="grid gap-3 sm:grid-cols-2">
                    {(bundle.freshness_summary.items ?? []).map((item) => (
                      <Metric
                        key={item.item_name}
                        label={item.item_name}
                        value={`${formatDate(item.as_of_date)} / ${item.freshness_mode ?? "-"} / ${item.source_mode ?? "-"}`}
                      />
                    ))}
                  </div>
                </Panel>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Factor Snapshot">
                  {bundle.factor_snapshot ? (
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <Metric label="Alpha" value={formatScore(bundle.factor_snapshot.alpha_score.total_score)} />
                      <Metric label="Trigger" value={formatScore(bundle.factor_snapshot.trigger_score.total_score)} />
                      <Metric label="Risk" value={formatScore(bundle.factor_snapshot.risk_score.total_score)} />
                      <Metric label="Trigger state" value={formatLabel(bundle.factor_snapshot.trigger_score.trigger_state)} />
                      <Metric label="Freshness" value={bundle.factor_snapshot.freshness_mode ?? "-"} />
                      <Metric label="Source mode" value={bundle.factor_snapshot.source_mode ?? "-"} />
                    </div>
                  ) : (
                    <StatusBlock title="Unavailable" description="Factor snapshot is unavailable." />
                  )}
                </Panel>

                <Panel title="Review Report v2 (Primary Research Artifact)">
                  {bundle.review_report ? (
                    <div className="space-y-3">
                      <Metric label="Final action" value={formatAction(bundle.review_report.final_judgement.action)} />
                      <TextPanel title="Technical view" content={bundle.review_report.technical_view.tactical_read} />
                      <TextPanel title="Event view" content={bundle.review_report.event_view.concise_summary} />
                    </div>
                  ) : (
                    <StatusBlock title="Unavailable" description="Review report is unavailable." />
                  )}
                </Panel>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Debate Review (Structured Adjudication)">
                  {bundle.debate_review ? (
                    <div className="space-y-3">
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        <Metric
                          label="Requested mode"
                          value={formatLabel(bundle.debate_review.runtime_mode_requested ?? "-")}
                        />
                        <Metric
                          label="Effective mode"
                          value={formatLabel(bundle.debate_review.runtime_mode_effective ?? bundle.debate_review.runtime_mode)}
                        />
                        <Metric label="Final action" value={formatAction(bundle.debate_review.final_action)} />
                        <Metric
                          label="Provider used"
                          value={bundle.debate_review.provider_used ?? "-"}
                        />
                        <Metric
                          label="Fallback"
                          value={bundle.debate_review.fallback_applied ? "yes" : "no"}
                        />
                      </div>
                      {bundle.debate_review.fallback_applied ? (
                        <StatusBlock
                          title="Debate fallback applied"
                          description={
                            bundle.debate_review.fallback_reason ??
                            "LLM debate switched to rule-based mode."
                          }
                        />
                      ) : null}
                      {bundle.debate_review.warning_messages.length > 0 ? (
                        <StatusBlock
                          title="Debate warnings"
                          description={bundle.debate_review.warning_messages.join(" | ")}
                        />
                      ) : null}
                      <TextPanel title="Chief judgement" content={bundle.debate_review.chief_judgement.summary} />
                      <StringPanel title="Bull case" items={bundle.debate_review.bull_case.reasons.map((item) => item.detail)} />
                      <StringPanel title="Bear case" items={bundle.debate_review.bear_case.reasons.map((item) => item.detail)} />
                    </div>
                  ) : useLlm && progress ? (
                    <StatusBlock
                      title="LLM debate still running"
                      description={`${progress.current_step ?? progress.message} (${progress.completed_steps}/${progress.total_steps || "?"})`}
                    />
                  ) : (
                    <StatusBlock title="Unavailable" description="Debate review is unavailable." />
                  )}
                </Panel>

                <Panel title="Strategy and Trigger">
                  <div className="space-y-3">
                    {bundle.strategy_plan ? (
                      <>
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                          <Metric label="Strategy action" value={formatAction(bundle.strategy_plan.action)} />
                          <Metric label="Strategy type" value={formatLabel(bundle.strategy_plan.strategy_type)} />
                          <Metric label="Entry range" value={formatRange(bundle.strategy_plan.ideal_entry_range)} />
                          <Metric label="Stop-loss" value={formatPrice(bundle.strategy_plan.stop_loss_price)} />
                          <Metric label="Take-profit" value={formatRange(bundle.strategy_plan.take_profit_range)} />
                          <Metric label="Review timeframe" value={bundle.strategy_plan.review_timeframe} />
                        </div>
                      </>
                    ) : null}
                    {bundle.trigger_snapshot ? (
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        <Metric label="Trigger state" value={formatLabel(bundle.trigger_snapshot.trigger_state)} />
                        <Metric label="Latest price" value={formatPrice(bundle.trigger_snapshot.latest_intraday_price)} />
                        <Metric label="Support" value={formatPrice(bundle.trigger_snapshot.daily_support_level)} />
                        <Metric label="Resistance" value={formatPrice(bundle.trigger_snapshot.daily_resistance_level)} />
                        <Metric label="Distance to support" value={formatPercent(bundle.trigger_snapshot.distance_to_support_pct)} />
                        <Metric label="Distance to resistance" value={formatPercent(bundle.trigger_snapshot.distance_to_resistance_pct)} />
                      </div>
                    ) : null}
                    {!bundle.strategy_plan && !bundle.trigger_snapshot ? (
                      <StatusBlock title="Unavailable" description="Strategy plan and trigger snapshot are unavailable." />
                    ) : null}
                  </div>
                </Panel>
              </div>
            </div>
          </SectionCard>

          <SingleStockWorkflowPanel symbol={symbol} />
        </>
      ) : null}
    </div>
  );
}

function LoadingBlock({
  progress,
  useLlm,
}: {
  progress: DebateReviewProgress | null;
  useLlm: boolean;
}) {
  return (
    <div className="mt-5">
      <StatusBlock
        title="Loading workspace bundle"
        description={
          useLlm && progress
            ? `${progress.current_step ?? progress.message} (${progress.completed_steps}/${progress.total_steps || "?"})`
            : "Waiting for the backend workspace bundle response."
        }
      />
    </div>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <div className="mt-3">{children}</div>
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

function TextPanel({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-3 text-sm leading-6 text-slate-700">{content}</p>
    </div>
  );
}

function StringPanel({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">No items.</p>
      ) : (
        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          {items.map((item) => (
            <li key={item} className="rounded-2xl bg-white px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EvidencePanel({
  title,
  items,
}: {
  title: string;
  items: DecisionBriefEvidence[];
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">No evidence items.</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {items.map((item) => (
            <li key={`${item.source_module}-${item.title}-${item.detail}`} className="rounded-2xl bg-white p-3">
              <p className="text-sm font-semibold text-slate-900">{item.title}</p>
              <p className="mt-1 text-sm leading-6 text-slate-700">{item.detail}</p>
              {item.evidence_refs.length > 0 ? (
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {item.evidence_refs.slice(0, 2).map((ref) => `${ref.dataset} / ${ref.field_path}`).join(" | ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function buildRequestId(symbol: string): string {
  const randomPart =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Math.random().toString(16).slice(2)}-${Date.now().toString(16)}`;
  return `${normalizeSymbolInput(symbol)}-${randomPart}`;
}
