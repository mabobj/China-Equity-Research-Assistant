"use client";

import { formatDateTime, formatLabel } from "@/lib/format";
import type {
  ScreenerSchemeDetailResponse,
  WorkflowRunDetailResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { ScreenerField, ScreenerMetric } from "./screener-shared";
import { StatusBlock } from "./status-block";
import { WorkflowRunSummary } from "./workflow-run-summary";

export function ScreenerRunPanel({
  schemeDetail,
  screenerRun,
  screenerError,
  batchSize,
  setBatchSize,
  maxSymbols,
  setMaxSymbols,
  forceRefresh,
  setForceRefresh,
  isRunning,
  onRun,
  onResetCursor,
  resetLoading,
  resetMessage,
}: {
  schemeDetail: ScreenerSchemeDetailResponse | null;
  screenerRun: WorkflowRunDetailResponse | null;
  screenerError: string | null;
  batchSize: string;
  setBatchSize: (value: string) => void;
  maxSymbols: string;
  setMaxSymbols: (value: string) => void;
  forceRefresh: boolean;
  setForceRefresh: (value: boolean) => void;
  isRunning: boolean;
  onRun: (event: React.FormEvent<HTMLFormElement>) => void;
  onResetCursor: () => void;
  resetLoading: boolean;
  resetMessage: string | null;
}) {
  return (
    <SectionCard
      title="运行"
      description="运行参数只控制本次执行，不会改写方案版本本身。"
    >
      <div className="space-y-4">
        {schemeDetail ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ScreenerMetric label="方案名称" value={schemeDetail.scheme.name} />
            <ScreenerMetric
              label="方案版本"
              value={
                schemeDetail.current_version_detail?.version_label ??
                schemeDetail.scheme.current_version ??
                "-"
              }
            />
            <ScreenerMetric
              label="方案版本号"
              value={schemeDetail.current_version_detail?.scheme_version ?? "-"}
            />
            <ScreenerMetric
              label="方案最近更新"
              value={formatDateTime(schemeDetail.scheme.updated_at)}
            />
          </div>
        ) : null}

        <form className="grid gap-4 lg:grid-cols-4" onSubmit={onRun}>
          <ScreenerField
            label="本批次计算股票数量（batch_size）"
            value={batchSize}
            onChange={setBatchSize}
            placeholder="例如 50"
          />
          <ScreenerField
            label="本次扫描上限（max_symbols）"
            value={maxSymbols}
            onChange={setMaxSymbols}
            placeholder="留空表示使用 batch_size"
          />
          <label className="flex min-h-11 items-center gap-3 rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 lg:mt-7">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(event) => setForceRefresh(event.target.checked)}
              className="size-4 rounded border-slate-300"
            />
            强制刷新本次运行所需数据
          </label>
          <div className="flex items-end gap-3">
            <button
              type="submit"
              disabled={isRunning || !schemeDetail}
              className="min-h-11 flex-1 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:bg-emerald-300"
            >
              {isRunning ? "当前已有运行中的初筛任务" : "按当前方案运行初筛"}
            </button>
          </div>
        </form>

        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <button
            type="button"
            onClick={onResetCursor}
            disabled={resetLoading || isRunning}
            className="min-h-11 rounded-2xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:text-slate-400"
          >
            {resetLoading ? "重置中..." : "重置游标"}
          </button>
          <p className="text-sm text-slate-600">
            当日快照作废后，下次初筛会从股票池起点重新开始计算。
          </p>
        </div>

        {resetMessage ? <StatusBlock title="游标重置" description={resetMessage} /> : null}
        {screenerError ? (
          <StatusBlock title="初筛工作流提示" description={screenerError} tone="error" />
        ) : null}
        {screenerRun ? (
          <WorkflowRunSummary run={screenerRun} />
        ) : (
          <StatusBlock
            title="等待执行"
            description="提交后会返回 run_id，并在页面内持续展示本次工作流运行状态。"
          />
        )}

        {screenerRun?.scheme_name ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ScreenerMetric label="运行中的方案" value={screenerRun.scheme_name} />
            <ScreenerMetric
              label="方案版本"
              value={screenerRun.scheme_version ?? "-"}
            />
            <ScreenerMetric
              label="运行状态"
              value={formatLabel(screenerRun.status)}
            />
            <ScreenerMetric
              label="开始时间"
              value={formatDateTime(screenerRun.started_at)}
            />
          </div>
        ) : null}
      </div>
    </SectionCard>
  );
}
