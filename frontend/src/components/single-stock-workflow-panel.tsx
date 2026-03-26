"use client";

import { useEffect, useState } from "react";

import {
  getWorkflowRunDetail,
  runSingleStockWorkflow,
} from "@/lib/api";
import type {
  WorkflowRunDetailResponse,
  WorkflowRunResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";
import { WorkflowRunSummary } from "./workflow-run-summary";

const SINGLE_STOCK_WORKFLOW_NODES = [
  "SingleStockResearchInputs",
  "FactorSnapshotBuild",
  "ReviewReportBuild",
  "DebateReviewBuild",
  "StrategyPlanBuild",
] as const;

type SingleStockWorkflowPanelProps = {
  symbol: string;
};

export function SingleStockWorkflowPanel({
  symbol,
}: SingleStockWorkflowPanelProps) {
  const [startFrom, setStartFrom] = useState("");
  const [stopAfter, setStopAfter] = useState("");
  const [useLlm, setUseLlm] = useState(false);
  const [lookupRunId, setLookupRunId] = useState("");
  const [run, setRun] = useState<WorkflowRunResponse | WorkflowRunDetailResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);

  useEffect(() => {
    setLookupRunId("");
  }, [symbol]);

  async function handleRun(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await runSingleStockWorkflow({
        symbol,
        start_from: startFrom || undefined,
        stop_after: stopAfter || undefined,
        use_llm: useLlm,
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
      title="单票 Workflow"
      description="直接在工作台里运行 single_stock_full_review。支持从中间节点启动，也可以按 run_id 回看本次执行记录。"
    >
      <div id="workflow" className="space-y-5">
        <form className="grid gap-4 lg:grid-cols-4" onSubmit={handleRun}>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">symbol</span>
            <input
              value={symbol}
              readOnly
              className="min-h-11 w-full rounded-2xl border border-slate-300 bg-slate-100 px-4 text-sm text-slate-900"
            />
          </label>
          <NodeSelect
            label="start_from"
            value={startFrom}
            onChange={setStartFrom}
            options={SINGLE_STOCK_WORKFLOW_NODES}
          />
          <NodeSelect
            label="stop_after"
            value={stopAfter}
            onChange={setStopAfter}
            options={SINGLE_STOCK_WORKFLOW_NODES}
          />
          <label className="flex items-end">
            <span className="flex min-h-11 w-full items-center gap-3 rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(event) => setUseLlm(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              辩论裁决使用 LLM
            </span>
          </label>
          <div className="lg:col-span-4 flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={loading}
              className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {loading ? "正在执行 workflow..." : "运行 single_stock_full_review"}
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
            description="点击上方按钮后会返回 run_id、节点摘要和最终输出摘要。"
          />
        ) : null}
        {run ? <WorkflowRunSummary run={run} /> : null}
      </div>
    </SectionCard>
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

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return "发生未知错误，请稍后重试。";
}
