"use client";

import { useState } from "react";

import {
  getWorkflowRunDetail,
  runDeepReviewWorkflow,
} from "@/lib/api";
import type {
  WorkflowRunDetailResponse,
  WorkflowRunResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";
import { WorkflowRunSummary } from "./workflow-run-summary";

const DEEP_REVIEW_WORKFLOW_NODES = [
  "ScreenerRun",
  "DeepCandidateSelect",
  "CandidateReviewBuild",
  "CandidateDebateBuild",
  "CandidateStrategyBuild",
] as const;

type FormState = {
  maxSymbols: string;
  topN: string;
  deepTopK: string;
  startFrom: string;
  stopAfter: string;
  useLlm: boolean;
};

const INITIAL_FORM_STATE: FormState = {
  maxSymbols: "30",
  topN: "10",
  deepTopK: "5",
  startFrom: "",
  stopAfter: "",
  useLlm: false,
};

export function DeepReviewWorkflowPanel() {
  const [form, setForm] = useState<FormState>(INITIAL_FORM_STATE);
  const [lookupRunId, setLookupRunId] = useState("");
  const [run, setRun] = useState<WorkflowRunResponse | WorkflowRunDetailResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);

  async function handleRun(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await runDeepReviewWorkflow({
        max_symbols: parseOptionalInteger(form.maxSymbols),
        top_n: parseOptionalInteger(form.topN),
        deep_top_k: parseOptionalInteger(form.deepTopK),
        start_from: form.startFrom || undefined,
        stop_after: form.stopAfter || undefined,
        use_llm: form.useLlm,
      });
      setRun(response);
      setLookupRunId(response.run_id);
    } catch (runError) {
      setError(getErrorMessage(runError));
    } finally {
      setLoading(false);
    }
  }

  async function handleLookup() {
    if (!lookupRunId.trim()) {
      return;
    }

    setLookupLoading(true);
    setLookupError(null);

    try {
      const response = await getWorkflowRunDetail(lookupRunId.trim());
      setRun(response);
    } catch (lookupRunError) {
      setLookupError(getErrorMessage(lookupRunError));
    } finally {
      setLookupLoading(false);
    }
  }

  return (
    <SectionCard
      title="Deep Review Workflow"
      description="在当前选股工作台里直接运行 deep_candidate_review，并查看运行记录、步骤摘要和最终输出摘要。"
    >
      <div id="workflow" className="space-y-5">
        <form className="grid gap-4 lg:grid-cols-3" onSubmit={handleRun}>
          <Field
            label="max_symbols"
            value={form.maxSymbols}
            onChange={(value) => setForm((current) => ({ ...current, maxSymbols: value }))}
          />
          <Field
            label="top_n"
            value={form.topN}
            onChange={(value) => setForm((current) => ({ ...current, topN: value }))}
          />
          <Field
            label="deep_top_k"
            value={form.deepTopK}
            onChange={(value) => setForm((current) => ({ ...current, deepTopK: value }))}
          />
          <NodeSelect
            label="start_from"
            value={form.startFrom}
            onChange={(value) => setForm((current) => ({ ...current, startFrom: value }))}
            options={DEEP_REVIEW_WORKFLOW_NODES}
          />
          <NodeSelect
            label="stop_after"
            value={form.stopAfter}
            onChange={(value) => setForm((current) => ({ ...current, stopAfter: value }))}
            options={DEEP_REVIEW_WORKFLOW_NODES}
          />
          <label className="flex items-end">
            <span className="flex min-h-11 w-full items-center gap-3 rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.useLlm}
                onChange={(event) =>
                  setForm((current) => ({ ...current, useLlm: event.target.checked }))
                }
                className="h-4 w-4 rounded border-slate-300"
              />
              辩论节点使用 LLM
            </span>
          </label>
          <div className="lg:col-span-3 flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={loading}
              className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {loading ? "正在执行 workflow..." : "运行 deep_candidate_review"}
            </button>
          </div>
        </form>

        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">按 run_id 查看记录</span>
            <input
              value={lookupRunId}
              onChange={(event) => setLookupRunId(event.target.value)}
              placeholder="输入 workflow run_id"
              className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
          </label>
          <button
            type="button"
            onClick={() => void handleLookup()}
            disabled={lookupLoading}
            className="min-h-11 self-end rounded-2xl border border-slate-300 px-5 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {lookupLoading ? "读取中..." : "查看运行记录"}
          </button>
        </div>

        {error ? (
          <StatusBlock title="执行失败" description={error} tone="error" />
        ) : null}
        {lookupError ? (
          <StatusBlock title="读取失败" description={lookupError} tone="error" />
        ) : null}
        {!run && !loading && !error ? (
          <StatusBlock
            title="尚未执行"
            description="执行完成后会返回 run_id、步骤摘要，以及最终输出摘要。"
          />
        ) : null}
        {run ? <WorkflowRunSummary run={run} /> : null}
      </div>
    </SectionCard>
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
        inputMode="numeric"
        className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
      />
    </label>
  );
}

function NodeSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly string[];
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
      >
        <option value="">从头开始 / 运行到末尾</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function parseOptionalInteger(value: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number.parseInt(normalized, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }

  return parsed;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return "发生未知错误，请稍后重试。";
}
