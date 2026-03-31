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
  formatDateTime,
  formatDidFollowPlan,
  formatReviewOutcome,
  formatStrategyAlignment,
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

  const handleCreateFromTrade = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!tradeId) {
      setError("请先选择一条交易记录。");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await createReviewFromTrade(tradeId, {});
      setMessage(`复盘草稿创建成功：${response.review_id}`);
      await refreshReviews(symbolFilter);
      setSelectedReviewId(response.review_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建复盘草稿失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
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
      description="把执行结果回写到复盘记录，形成“执行 -> 结果 -> 经验标签”闭环。"
    >
      <SectionCard title="从交易生成复盘草稿" description="先选择交易记录，再一键生成复盘草稿。">
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
            {selectedReview.linked_trade ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 lg:col-span-2">
                关联交易：{formatTradeSide(selectedReview.linked_trade.side)} /
                对齐状态：{formatStrategyAlignment(selectedReview.linked_trade.strategy_alignment)}
              </div>
            ) : null}
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
