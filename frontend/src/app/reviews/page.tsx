"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { PageShell } from "@/components/page-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBlock } from "@/components/status-block";
import {
  createReviewFromTrade,
  listReviews,
  listTrades,
  normalizeSymbolInput,
  updateReview,
} from "@/lib/api";
import {
  formatAction,
  formatDateTime,
  formatDidFollowPlan,
  formatLabel,
  formatPrice,
  formatRatioPercent,
  formatReviewOutcome,
  formatStrategyAlignment,
  formatTradeReasonType,
  formatTradeSide,
} from "@/lib/format";
import type {
  DidFollowPlan,
  ReviewOutcomeLabel,
  ReviewRecord,
  TradeRecord,
} from "@/types/api";

type OptionItem = {
  value: string;
  label: string;
};

const OUTCOME_OPTIONS: OptionItem[] = [
  { value: "success", label: formatReviewOutcome("success") },
  { value: "partial_success", label: formatReviewOutcome("partial_success") },
  { value: "failure", label: formatReviewOutcome("failure") },
  { value: "invalidated", label: formatReviewOutcome("invalidated") },
  { value: "no_trade", label: formatReviewOutcome("no_trade") },
];

const FOLLOW_PLAN_OPTIONS: OptionItem[] = [
  { value: "yes", label: formatDidFollowPlan("yes") },
  { value: "partial", label: formatDidFollowPlan("partial") },
  { value: "no", label: formatDidFollowPlan("no") },
];

export default function ReviewsPage() {
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [tradeId, setTradeId] = useState("");
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [symbolFilter, setSymbolFilter] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const selectedReview = useMemo(
    () => reviews.find((item) => item.review_id === selectedReviewId) ?? null,
    [reviews, selectedReviewId],
  );
  const reviewDeviationSummary = useMemo(
    () => buildReviewDeviationSummary(selectedReview),
    [selectedReview],
  );
  const reviewedTradeIds = useMemo(() => {
    return new Set(
      reviews
        .map((item) => item.linked_trade_id)
        .filter((value): value is string => Boolean(value)),
    );
  }, [reviews]);
  const pendingTrades = useMemo(() => {
    return trades.filter((item) => !reviewedTradeIds.has(item.trade_id));
  }, [trades, reviewedTradeIds]);
  const [editForm, setEditForm] = useState<{
    outcomeLabel: ReviewOutcomeLabel;
    didFollowPlan: DidFollowPlan;
    reviewSummary: string;
    exitReason: string;
    lessonTags: string;
  }>({
    outcomeLabel: "partial_success",
    didFollowPlan: "partial",
    reviewSummary: "",
    exitReason: "",
    lessonTags: "",
  });

  const refreshTrades = useCallback(async () => {
    const response = await listTrades({ limit: 200 });
    setTrades(response.items);
    if (!tradeId && response.items.length > 0) {
      setTradeId(response.items[0].trade_id);
    }
  }, [tradeId]);

  const refreshReviews = useCallback(async (symbol?: string) => {
    setStatus("loading");
    setError(null);
    try {
      const response = await listReviews({
        symbol: symbol ? normalizeSymbolInput(symbol) : undefined,
        limit: 200,
      });
      setReviews(response.items);
      setSelectedReviewId((previous) => {
        if (!response.items.length) return null;
        if (previous && response.items.some((item) => item.review_id === previous)) {
          return previous;
        }
        return response.items[0].review_id;
      });
      setStatus("success");
    } catch (cause) {
      setStatus("error");
      setError(cause instanceof Error ? cause.message : "加载复盘记录失败，请稍后重试。");
    }
  }, []);

  useEffect(() => {
    void refreshTrades();
    void refreshReviews();
  }, [refreshReviews, refreshTrades]);

  useEffect(() => {
    if (!selectedReview) {
      return;
    }
    setEditForm({
      outcomeLabel: selectedReview.outcome_label,
      didFollowPlan: selectedReview.did_follow_plan,
      reviewSummary: selectedReview.review_summary,
      exitReason: selectedReview.exit_reason ?? "",
      lessonTags: selectedReview.lesson_tags.join(", "),
    });
  }, [selectedReview]);

  const createDraftByTradeId = async (selectedTradeId: string) => {
    if (!selectedTradeId) {
      setError("请先选择一条交易记录。");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await createReviewFromTrade(selectedTradeId, {});
      setMessage(`复盘草稿创建成功：${response.review_id}`);
      await refreshReviews(symbolFilter);
      setSelectedReviewId(response.review_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建复盘草稿失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  };

  const handleCreateFromTrade = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await createDraftByTradeId(tradeId);
  };

  const handleUpdateReview = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedReview) {
      setError("请先选择需要编辑的复盘记录。");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await updateReview(selectedReview.review_id, {
        outcome_label: editForm.outcomeLabel,
        did_follow_plan: editForm.didFollowPlan,
        review_summary: editForm.reviewSummary.trim(),
        exit_reason: editForm.exitReason.trim() || undefined,
        lesson_tags: editForm.lessonTags
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setMessage(`复盘记录已更新：${response.review_id}`);
      await refreshReviews(symbolFilter);
      setSelectedReviewId(response.review_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "更新复盘记录失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  };

  const handleFilterSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void refreshReviews(symbolFilter);
  };

  return (
    <PageShell
      title="复盘记录"
      description="优先处理待复盘交易，再完善复盘结论，形成“执行 -> 结果 -> 经验标签”闭环。"
    >
      <SectionCard title="待复盘交易" description="先从未复盘的交易开始，一键生成复盘草稿。">
        <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="待复盘交易数" value={String(pendingTrades.length)} />
          <Metric label="复盘总数" value={String(reviews.length)} />
          <Metric label="交易总数" value={String(trades.length)} />
          <Metric
            label="复盘覆盖率"
            value={trades.length > 0 ? `${Math.round((reviews.length / trades.length) * 100)}%` : "-"}
          />
        </div>
        {pendingTrades.length > 0 ? (
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-700">
                <tr>
                  <th className="px-4 py-3">交易时间</th>
                  <th className="px-4 py-3">股票</th>
                  <th className="px-4 py-3">动作</th>
                  <th className="px-4 py-3">对齐状态</th>
                  <th className="px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {pendingTrades.slice(0, 20).map((item) => (
                  <tr key={item.trade_id} className="border-t border-slate-200">
                    <td className="px-4 py-3">{formatDateTime(item.trade_date)}</td>
                    <td className="px-4 py-3">{item.symbol}</td>
                    <td className="px-4 py-3">{formatTradeSide(item.side)}</td>
                    <td className="px-4 py-3">{formatStrategyAlignment(item.strategy_alignment)}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => void createDraftByTradeId(item.trade_id)}
                        disabled={saving}
                        className="rounded-2xl bg-emerald-700 px-3 py-1 text-xs font-semibold text-white transition hover:bg-emerald-800 disabled:bg-emerald-300"
                      >
                        生成复盘草稿
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <StatusBlock title="暂无待复盘交易" description="当前交易都已完成复盘，或还没有交易记录。" />
        )}
      </SectionCard>

      <SectionCard title="从指定交易生成复盘草稿（高级）" description="当你需要指定某条交易时再使用。">
        <form className="grid gap-4 md:grid-cols-[1fr_auto]" onSubmit={handleCreateFromTrade}>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">交易记录</span>
            <select
              value={tradeId}
              onChange={(event) => setTradeId(event.target.value)}
              className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            >
              {trades.length === 0 ? <option value="">暂无交易记录</option> : null}
              {trades.map((item) => (
                <option key={item.trade_id} value={item.trade_id}>
                  {item.symbol} / {formatTradeSide(item.side)} / {formatDateTime(item.trade_date)}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={saving}
              className="min-h-11 rounded-2xl bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:bg-emerald-300"
            >
              {saving ? "处理中..." : "生成复盘草稿"}
            </button>
          </div>
        </form>
        {message ? (
          <div className="mt-4">
            <StatusBlock title="操作成功" description={message} />
          </div>
        ) : null}
        {error ? (
          <div className="mt-4">
            <StatusBlock title="操作失败" description={error} tone="error" />
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="复盘列表与详情" description="支持按股票筛选，并可编辑结果标签与总结。">
        <form className="grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={handleFilterSubmit}>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">筛选股票代码</span>
            <input
              value={symbolFilter}
              onChange={(event) => setSymbolFilter(event.target.value)}
              className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              className="min-h-11 rounded-2xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              刷新列表
            </button>
          </div>
        </form>

        {status === "loading" ? (
          <div className="mt-4">
            <StatusBlock title="加载中" description="正在读取复盘记录..." />
          </div>
        ) : null}
        {status === "error" && error ? (
          <div className="mt-4">
            <StatusBlock title="加载失败" description={error} tone="error" />
          </div>
        ) : null}
        {status === "success" && reviews.length === 0 ? (
          <div className="mt-4">
            <StatusBlock title="暂无复盘记录" description="可先从交易记录生成一条复盘草稿。" />
          </div>
        ) : null}

        {reviews.length > 0 ? (
          <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-700">
                <tr>
                  <th className="px-4 py-3">日期</th>
                  <th className="px-4 py-3">股票</th>
                  <th className="px-4 py-3">结果标签</th>
                  <th className="px-4 py-3">是否按计划</th>
                  <th className="px-4 py-3">持有天数</th>
                  <th className="px-4 py-3">摘要</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((item) => (
                  <tr
                    key={item.review_id}
                    className={
                      selectedReviewId === item.review_id
                        ? "cursor-pointer border-t border-slate-200 bg-emerald-50"
                        : "cursor-pointer border-t border-slate-200"
                    }
                    onClick={() => setSelectedReviewId(item.review_id)}
                  >
                    <td className="px-4 py-3">{item.review_date}</td>
                    <td className="px-4 py-3">{item.symbol}</td>
                    <td className="px-4 py-3">{formatReviewOutcome(item.outcome_label)}</td>
                    <td className="px-4 py-3">{formatDidFollowPlan(item.did_follow_plan)}</td>
                    <td className="px-4 py-3">{item.holding_days ?? "-"}</td>
                    <td className="px-4 py-3">{item.review_summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {selectedReview ? (
          <form className="mt-4 grid gap-4 lg:grid-cols-2" onSubmit={handleUpdateReview}>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 lg:col-span-2">
              当前复盘：{selectedReview.symbol} / {selectedReview.review_date}
              {" "}（关联交易：{selectedReview.linked_trade_id ?? "-"}）
            </div>
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900 lg:col-span-2">
              <p className="font-semibold">复盘对照视图</p>
              <p className="mt-1">
                先核对“原判断快照”，再看“执行路径”，最后再更新复盘结论与经验标签。
              </p>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 lg:col-span-2">
              <p className="text-sm font-semibold text-amber-950">偏差诊断摘要</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Metric label="偏差等级" value={formatDeviationSeverity(reviewDeviationSummary.severity)} />
                <Metric
                  label="复盘结果"
                  value={formatReviewOutcome(selectedReview.outcome_label)}
                />
                <Metric
                  label="执行一致性"
                  value={formatDidFollowPlan(selectedReview.did_follow_plan)}
                />
                <Metric
                  label="关联告警数"
                  value={String(selectedReview.warning_messages.length)}
                />
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <StringList title="诊断要点" items={reviewDeviationSummary.notes} />
                <StringList title="建议下一步" items={reviewDeviationSummary.followups} />
              </div>
            </div>
            {selectedReview.linked_decision_snapshot ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 lg:col-span-2">
                <p className="text-sm font-semibold text-slate-950">原判断快照</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <Metric
                    label="决策动作"
                    value={formatSnapshotAction(selectedReview.linked_decision_snapshot.action)}
                  />
                  <Metric
                    label="置信度"
                    value={`${selectedReview.linked_decision_snapshot.confidence} / 100`}
                  />
                  <Metric
                    label="综合评分"
                    value={`${selectedReview.linked_decision_snapshot.overall_score} / 100`}
                  />
                  <Metric
                    label="快照时间"
                    value={formatDateTime(selectedReview.linked_decision_snapshot.created_at)}
                  />
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <Metric
                    label="预测分"
                    value={
                      selectedReview.linked_decision_snapshot.predictive_score === null ||
                      selectedReview.linked_decision_snapshot.predictive_score === undefined
                        ? "-"
                        : `${selectedReview.linked_decision_snapshot.predictive_score} / 100`
                    }
                  />
                  <Metric
                    label="预测置信度"
                    value={formatRatioPercent(
                      selectedReview.linked_decision_snapshot.predictive_confidence,
                    )}
                  />
                  <Metric
                    label="预测模型版本"
                    value={
                      selectedReview.linked_decision_snapshot.predictive_model_version ?? "-"
                    }
                  />
                </div>
                {selectedReview.linked_decision_snapshot.data_quality_summary ? (
                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                    <QualityTag
                      label="行情质量"
                      value={
                        selectedReview.linked_decision_snapshot.data_quality_summary.bars_quality
                      }
                    />
                    <QualityTag
                      label="财务质量"
                      value={
                        selectedReview.linked_decision_snapshot.data_quality_summary
                          .financial_quality
                      }
                    />
                    <QualityTag
                      label="公告质量"
                      value={
                        selectedReview.linked_decision_snapshot.data_quality_summary
                          .announcement_quality
                      }
                    />
                  </div>
                ) : null}
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <StringList
                    title="关键触发条件"
                    items={selectedReview.linked_decision_snapshot.triggers}
                  />
                  <StringList
                    title="失效条件"
                    items={selectedReview.linked_decision_snapshot.invalidations}
                  />
                </div>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <StringList
                    title="核心风险"
                    items={selectedReview.linked_decision_snapshot.risks}
                  />
                  <StringList
                    title="置信度说明"
                    items={selectedReview.linked_decision_snapshot.confidence_reasons}
                  />
                </div>
                <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                  <p className="text-sm font-semibold text-slate-900">原判断摘要</p>
                  <p className="mt-2">{selectedReview.linked_decision_snapshot.thesis}</p>
                </div>
              </div>
            ) : (
              <StatusBlock
                title="未关联原判断快照"
                description="该复盘记录未绑定 decision snapshot，建议后续优先使用“从当前判断创建交易”路径。"
                tone="error"
              />
            )}
            {selectedReview.linked_trade ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 lg:col-span-2">
                <p className="text-sm font-semibold text-slate-950">执行路径</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <Metric
                    label="交易动作"
                    value={formatTradeSide(selectedReview.linked_trade.side)}
                  />
                  <Metric
                    label="原因类型"
                    value={formatTradeReasonType(selectedReview.linked_trade.reason_type)}
                  />
                  <Metric
                    label="对齐状态"
                    value={formatStrategyAlignment(selectedReview.linked_trade.strategy_alignment)}
                  />
                  <Metric
                    label="交易时间"
                    value={formatDateTime(selectedReview.linked_trade.trade_date)}
                  />
                  <Metric
                    label="价格"
                    value={formatPrice(selectedReview.linked_trade.price)}
                  />
                  <Metric
                    label="数量"
                    value={selectedReview.linked_trade.quantity?.toString() ?? "-"}
                  />
                  <Metric
                    label="金额"
                    value={formatPrice(selectedReview.linked_trade.amount)}
                  />
                  <Metric
                    label="人工覆盖原因"
                    value={selectedReview.linked_trade.alignment_override_reason ?? "-"}
                  />
                </div>
                {selectedReview.linked_trade.note ? (
                  <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                    <p className="text-sm font-semibold text-slate-900">交易备注</p>
                    <p className="mt-2">{selectedReview.linked_trade.note}</p>
                  </div>
                ) : null}
              </div>
            ) : (
              <StatusBlock
                title="未关联交易路径"
                description="该复盘记录未绑定 trade 记录，无法展示执行细节。"
                tone="error"
              />
            )}
            {selectedReview.warning_messages.length > 0 ? (
              <div className="lg:col-span-2">
                <StatusBlock
                  title="复盘运行告警"
                  description={selectedReview.warning_messages.join(" | ")}
                />
              </div>
            ) : null}
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">结果标签</span>
              <select
                value={editForm.outcomeLabel}
                onChange={(event) =>
                  setEditForm((previous) => ({
                    ...previous,
                    outcomeLabel: event.target.value as ReviewOutcomeLabel,
                  }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                {OUTCOME_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">执行一致性</span>
              <select
                value={editForm.didFollowPlan}
                onChange={(event) =>
                  setEditForm((previous) => ({
                    ...previous,
                    didFollowPlan: event.target.value as DidFollowPlan,
                  }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                {FOLLOW_PLAN_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2 lg:col-span-2">
              <span className="text-sm font-medium text-slate-700">复盘总结</span>
              <textarea
                value={editForm.reviewSummary}
                onChange={(event) =>
                  setEditForm((previous) => ({ ...previous, reviewSummary: event.target.value }))
                }
                rows={4}
                className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">退出原因</span>
              <input
                value={editForm.exitReason}
                onChange={(event) =>
                  setEditForm((previous) => ({ ...previous, exitReason: event.target.value }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">经验标签（逗号分隔）</span>
              <input
                value={editForm.lessonTags}
                onChange={(event) =>
                  setEditForm((previous) => ({ ...previous, lessonTags: event.target.value }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <div className="flex items-end lg:col-span-2">
              <button
                type="submit"
                disabled={saving}
                className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:bg-slate-400"
              >
                {saving ? "保存中..." : "保存复盘修改"}
              </button>
            </div>
          </form>
        ) : null}
      </SectionCard>
    </PageShell>
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

function QualityTag({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
      <span className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <p className="mt-1 font-semibold text-slate-900">{formatLabel(value)}</p>
    </div>
  );
}

function StringList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm leading-6 text-slate-600">暂无条目。</p>
      ) : (
        <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
          {items.map((item) => (
            <li key={`${title}-${item}`} className="rounded-xl bg-white px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function formatSnapshotAction(value: string): string {
  const normalized = value.toUpperCase();
  if (normalized === "BUY" || normalized === "WATCH" || normalized === "AVOID") {
    return formatAction(normalized);
  }
  return formatLabel(value);
}

type ReviewDeviationSeverity = "low" | "medium" | "high";

type ReviewDeviationSummary = {
  severity: ReviewDeviationSeverity;
  notes: string[];
  followups: string[];
};

function buildReviewDeviationSummary(review: ReviewRecord | null): ReviewDeviationSummary {
  if (!review) {
    return {
      severity: "low",
      notes: ["暂无可诊断复盘记录。"],
      followups: ["先选择一条复盘记录查看详情。"],
    };
  }

  const notes: string[] = [];
  const followups: string[] = [];
  let score = 0;

  if (!review.linked_trade) {
    score += 2;
    notes.push("未关联交易路径，执行信息不完整。");
    followups.push("优先通过“从交易生成复盘”补齐执行路径。");
  } else {
    if (review.linked_trade.strategy_alignment === "not_aligned") {
      score += 2;
      notes.push("交易动作与原判断方向不一致（not_aligned）。");
      followups.push("复盘时重点核查入场/退出触发是否偏离原计划。");
    } else if (review.linked_trade.strategy_alignment === "partially_aligned") {
      score += 1;
      notes.push("交易动作与原判断仅部分一致。");
      followups.push("补充“人工覆盖原因”和执行偏差说明。");
    }

    if (review.linked_trade.reason_type === "manual_override") {
      score += 1;
      notes.push("本次交易使用了人工覆盖动作。");
      followups.push("记录人工覆盖条件，便于后续检验是否有效。");
    }
  }

  if (review.did_follow_plan === "no") {
    score += 2;
    notes.push("复盘标记为未按计划执行。");
    followups.push("对照原判断触发条件，明确偏离发生在入场还是退出。");
  } else if (review.did_follow_plan === "partial") {
    score += 1;
    notes.push("复盘标记为部分按计划执行。");
    followups.push("把“按计划部分”和“偏离部分”拆开写入总结。");
  }

  if (review.outcome_label === "failure" || review.outcome_label === "invalidated") {
    score += 1;
    notes.push("当前结果为失败或失效，需重点关注可复现原因。");
    followups.push("将关键教训沉淀为 lesson_tags，避免重复错误。");
  }

  if (review.warning_messages.length > 0) {
    score += 1;
    notes.push(`存在 ${review.warning_messages.length} 条运行告警，结果需谨慎解读。`);
    followups.push("先处理告警再比较该案例与其他样本。");
  }

  if (notes.length === 0) {
    notes.push("判断、执行、复盘三段链路整体一致。");
    followups.push("可将本案例标记为可复用模板，复用到同类机会。");
  }

  const severity: ReviewDeviationSeverity = score >= 5 ? "high" : score >= 2 ? "medium" : "low";
  return { severity, notes, followups };
}

function formatDeviationSeverity(value: ReviewDeviationSeverity): string {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}
