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
        <Metric label="运行 ID" value={run.run_id} />
        <Metric label="工作流" value={run.workflow_name} />
        <Metric label="状态" value={formatLabel(run.status)} />
        <Metric label="开始时间" value={formatDateTime(run.started_at)} />
        <Metric label="结束时间" value={formatDateTime(run.finished_at)} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="请求模式"
          value={formatLabel(run.runtime_mode_requested ?? "-")}
        />
        <Metric
          label="实际模式"
          value={formatLabel(run.runtime_mode_effective ?? "-")}
        />
        <Metric label="使用数据提供方" value={run.provider_used ?? "-"} />
        <Metric label="已降级" value={run.fallback_applied ? "是" : "否"} />
      </div>

      {run.error_message ? (
        <StatusBlock title="工作流执行失败" description={run.error_message} tone="error" />
      ) : null}

      {run.fallback_applied ? (
        <StatusBlock
          title="已触发降级"
          description={
            run.fallback_reason ??
            "运行时已触发降级，请检查告警和失败股票列表。"
          }
          tone="error"
        />
      ) : null}

      {run.failed_symbols.length > 0 ? (
        <StatusBlock
          title="失败股票"
          description={run.failed_symbols.join("、")}
          tone="error"
        />
      ) : null}

      {run.warning_messages.length > 0 ? (
        <StatusBlock title="运行告警" description={run.warning_messages.join(" | ")} />
      ) : null}

      <SummaryCard
        title="输入摘要"
        summary={run.input_summary}
        emptyText="暂无输入摘要。"
      />
      <SummaryCard
        title="最终输出摘要"
        summary={run.final_output_summary}
        emptyText="暂无最终输出摘要。"
      />

      <div className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-slate-950">步骤摘要</h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            每个工作流节点都会记录输入摘要、输出摘要和失败信息。
          </p>
        </div>
        {run.steps.length === 0 ? (
          <StatusBlock title="暂无步骤" description="尚未返回步骤摘要。" />
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
            状态：{formatWorkflowStepStatus(step.status)}
          </p>
          {step.message ? (
            <p className="mt-2 text-sm leading-6 text-slate-700">{step.message}</p>
          ) : null}
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[320px]">
          <Metric label="开始时间" value={formatDateTime(step.started_at)} />
          <Metric label="结束时间" value={formatDateTime(step.finished_at)} />
        </div>
      </div>

      {step.error_message ? (
        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm leading-6 text-rose-800">
          {step.error_message}
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <SummaryCard
          title="输入摘要"
          summary={step.input_summary}
          emptyText="暂无输入摘要。"
          compact
        />
        <SummaryCard
          title="输出摘要"
          summary={step.output_summary}
          emptyText="暂无输出摘要。"
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
