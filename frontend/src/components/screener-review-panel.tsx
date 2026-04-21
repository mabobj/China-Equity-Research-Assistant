"use client";

import { formatDateTime, formatLabel } from "@/lib/format";
import type {
  ScreenerSchemeReviewStatsResponse,
  ScreenerSchemeRunsResponse,
  ScreenerSchemeStatsResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { ScreenerMetric, ScreenerStringPanel } from "./screener-shared";
import { StatusBlock } from "./status-block";

export function ScreenerReviewPanel({
  runs,
  stats,
  feedback,
  loading,
  error,
  selectedBatchId,
  onSelectBatchId,
}: {
  runs: ScreenerSchemeRunsResponse | null;
  stats: ScreenerSchemeStatsResponse | null;
  feedback: ScreenerSchemeReviewStatsResponse | null;
  loading: boolean;
  error: string | null;
  selectedBatchId: string | null;
  onSelectBatchId: (batchId: string) => void;
}) {
  const hasAnyReviewData = Boolean(stats || feedback || runs);

  return (
    <SectionCard
      title="反馈"
      description="这里按方案查看历史运行、进入研究/交易/复盘的数量，以及最基础的反馈分布。"
    >
      <div className="space-y-4">
        {loading ? (
          <StatusBlock
            title="加载中"
            description="正在读取当前方案的历史运行与反馈统计..."
          />
        ) : null}
        {error ? <StatusBlock title="反馈加载失败" description={error} tone="error" /> : null}
        {!loading && !error && !hasAnyReviewData ? (
          <StatusBlock
            title="反馈数据暂未形成"
            description="当前方案还没有足够的历史运行、研究、交易或复盘沉淀。先完成一次初筛运行，后续这里会逐步形成统计。"
          />
        ) : null}

        <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-900">
          反馈区回答三个问题：这套方案跑过多少次、筛出了什么、后续有没有进入研究与交易。点击历史批次后，结果区会同步切换到对应批次。
        </div>

        {stats ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <ScreenerMetric label="运行次数" value={String(stats.stats.total_runs)} />
            <ScreenerMetric label="总候选数" value={String(stats.stats.total_candidates)} />
            <ScreenerMetric
              label="进入研究链"
              value={String(stats.stats.entered_research_count)}
            />
            <ScreenerMetric label="交易记录数" value={String(stats.stats.trade_count)} />
            <ScreenerMetric label="复盘记录数" value={String(stats.stats.review_count)} />
          </div>
        ) : null}

        {stats ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ScreenerMetric
              label="可直接关注买点"
              value={String(stats.stats.ready_count)}
            />
            <ScreenerMetric label="观察类候选" value={String(stats.stats.watch_count)} />
            <ScreenerMetric
              label="仅研究跟踪"
              value={String(stats.stats.research_count)}
            />
            <ScreenerMetric label="回避" value={String(stats.stats.avoid_count)} />
          </div>
        ) : null}

        {feedback ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <ScreenerMetric
              label="命中股票数"
              value={String(feedback.feedback.linked_symbols)}
            />
            <ScreenerMetric
              label="产生交易的股票"
              value={String(feedback.feedback.traded_symbols)}
            />
            <ScreenerMetric
              label="产生复盘的股票"
              value={String(feedback.feedback.reviewed_symbols)}
            />
            <ScreenerMetric
              label="一致交易"
              value={String(feedback.feedback.aligned_trades)}
            />
            <ScreenerMetric
              label="不一致交易"
              value={String(feedback.feedback.not_aligned_trades)}
            />
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-2">
          <ScreenerStringPanel
            title="复盘结果分布"
            items={toDistributionItems(
              stats?.stats.outcome_distribution ?? feedback?.feedback.outcome_distribution ?? {},
            )}
          />
          <ScreenerStringPanel
            title="计划执行情况"
            items={toDistributionItems(feedback?.feedback.did_follow_plan_distribution ?? {})}
          />
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <ScreenerStringPanel
            title="经验标签"
            items={toDistributionItems(feedback?.feedback.lesson_tag_distribution ?? {})}
          />
          <ScreenerStringPanel
            title="方案版本覆盖"
            items={(stats?.stats.scheme_versions ?? []).map((item) => item)}
          />
        </div>

        {runs ? (
          <div className="rounded-2xl border border-slate-200 bg-white">
            <div className="border-b border-slate-200 px-4 py-3">
              <p className="text-sm font-semibold text-slate-950">历史运行</p>
              <p className="mt-1 text-sm text-slate-600">
                点击某次运行后，结果区会切换到对应批次的候选列表。
              </p>
              {selectedBatchId ? (
                <p className="mt-2 text-sm font-medium text-emerald-700">
                  当前正在查看批次：{selectedBatchId}
                </p>
              ) : (
                <p className="mt-2 text-sm text-slate-600">
                  请选择一个批次，结果区才会切换到对应候选。
                </p>
              )}
            </div>
            {runs.items.length === 0 ? (
              <div className="p-4">
                <StatusBlock
                  title="暂无历史运行"
                  description="当前方案还没有可查看的运行记录。"
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-700">
                    <tr>
                      <th className="px-4 py-3">批次</th>
                      <th className="px-4 py-3">运行状态</th>
                      <th className="px-4 py-3">方案版本</th>
                      <th className="px-4 py-3">候选数</th>
                      <th className="px-4 py-3">研究/交易/复盘</th>
                      <th className="px-4 py-3">完成时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.items.map((item) => {
                      const isSelected = item.batch_id === selectedBatchId;
                      return (
                        <tr
                          key={item.batch_id}
                          role="button"
                          tabIndex={0}
                          onClick={() => onSelectBatchId(item.batch_id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onSelectBatchId(item.batch_id);
                            }
                          }}
                          className={
                            isSelected
                              ? "cursor-pointer border-t border-slate-200 bg-emerald-50"
                              : "cursor-pointer border-t border-slate-200 hover:bg-slate-50"
                          }
                        >
                          <td className="px-4 py-3 font-semibold text-emerald-700">
                            {item.batch_id}
                          </td>
                          <td className="px-4 py-3">{formatLabel(item.status)}</td>
                          <td className="px-4 py-3">{item.scheme_version ?? "-"}</td>
                          <td className="px-4 py-3">{item.result_count}</td>
                          <td className="px-4 py-3">
                            {item.decision_snapshot_count}/{item.trade_count}/{item.review_count}
                          </td>
                          <td className="px-4 py-3">
                            {formatDateTime(item.finished_at ?? item.started_at)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </SectionCard>
  );
}

function toDistributionItems(distribution: Record<string, number>): string[] {
  const entries = Object.entries(distribution);
  if (entries.length === 0) {
    return [];
  }
  return entries
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([key, value]) => `${formatLabel(key)}：${value}`);
}
