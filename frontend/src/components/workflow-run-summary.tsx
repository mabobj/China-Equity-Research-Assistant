"use client";

import {
  formatDateTime,
  formatLabel,
  formatUnknownValue,
  formatWorkflowStepStatus,
} from "@/lib/format";
import type {
  WorkflowRunDetailResponse,
  WorkflowRunResponse,
  WorkflowStepSummary,
} from "@/types/api";

import { StatusBlock } from "./status-block";

type WorkflowRunSummaryProps = {
  run: WorkflowRunResponse | WorkflowRunDetailResponse;
};

export function WorkflowRunSummary({ run }: WorkflowRunSummaryProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Run ID" value={run.run_id} />
        <Metric label="Workflow" value={run.workflow_name} />
        <Metric label="Status" value={formatLabel(run.status)} />
        <Metric label="Started at" value={formatDateTime(run.started_at)} />
        <Metric label="Finished at" value={formatDateTime(run.finished_at)} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Requested mode"
          value={formatLabel(run.runtime_mode_requested ?? "-")}
        />
        <Metric
          label="Effective mode"
          value={formatLabel(run.runtime_mode_effective ?? "-")}
        />
        <Metric label="Provider used" value={run.provider_used ?? "-"} />
        <Metric label="Fallback" value={run.fallback_applied ? "yes" : "no"} />
      </div>

      {run.error_message ? (
        <StatusBlock title="Workflow failed" description={run.error_message} tone="error" />
      ) : null}

      {run.fallback_applied ? (
        <StatusBlock
          title="Fallback applied"
          description={
            run.fallback_reason ??
            "Runtime fallback was applied. Please check warnings and failed symbols."
          }
          tone="error"
        />
      ) : null}

      {run.failed_symbols.length > 0 ? (
        <StatusBlock
          title="Failed symbols"
          description={run.failed_symbols.join(", ")}
          tone="error"
        />
      ) : null}

      {run.warning_messages.length > 0 ? (
        <StatusBlock title="Warnings" description={run.warning_messages.join(" | ")} />
      ) : null}

      <SummaryCard
        title="Input summary"
        summary={run.input_summary}
        emptyText="No input summary."
      />
      <SummaryCard
        title="Final output summary"
        summary={run.final_output_summary}
        emptyText="No final output summary."
      />

      <div className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-slate-950">Step summary</h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Each workflow node records input/output summary and failure details.
          </p>
        </div>
        {run.steps.length === 0 ? (
          <StatusBlock title="No steps yet" description="No step summary returned yet." />
        ) : (
          <div className="grid gap-4">
            {run.steps.map((step) => (
              <StepCard key={`${run.run_id}-${step.node_name}`} step={step} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StepCard({ step }: { step: WorkflowStepSummary }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h4 className="text-base font-semibold text-slate-950">{step.node_name}</h4>
          <p className="mt-1 text-sm text-slate-600">
            Status: {formatWorkflowStepStatus(step.status)}
          </p>
          {step.message ? (
            <p className="mt-2 text-sm leading-6 text-slate-700">{step.message}</p>
          ) : null}
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[320px]">
          <Metric label="Started at" value={formatDateTime(step.started_at)} />
          <Metric label="Finished at" value={formatDateTime(step.finished_at)} />
        </div>
      </div>

      {step.error_message ? (
        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm leading-6 text-rose-800">
          {step.error_message}
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <SummaryCard
          title="Input summary"
          summary={step.input_summary}
          emptyText="No input summary."
          compact
        />
        <SummaryCard
          title="Output summary"
          summary={step.output_summary}
          emptyText="No output summary."
          compact
        />
      </div>
    </article>
  );
}

function SummaryCard({
  title,
  summary,
  emptyText,
  compact = false,
}: {
  title: string;
  summary: Record<string, unknown>;
  emptyText: string;
  compact?: boolean;
}) {
  const entries = Object.entries(summary);

  return (
    <div
      className={`rounded-2xl border border-slate-200 bg-white ${
        compact ? "p-3" : "p-4"
      }`}
    >
      <h4 className="text-sm font-semibold text-slate-950">{title}</h4>
      {entries.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">{emptyText}</p>
      ) : (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {entries.map(([key, value]) => (
            <Metric key={key} label={formatLabel(key)} value={formatUnknownValue(value)} />
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 break-all text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}
