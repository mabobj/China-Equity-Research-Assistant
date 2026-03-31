"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  createDecisionSnapshot,
  createTradeFromCurrentDecision,
  getDebateReviewProgress,
  getWorkspaceBundle,
  normalizeSymbolInput,
} from "@/lib/api";
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
  CreateTradeFromCurrentDecisionRequest,
  DebateReviewProgress,
  DecisionBriefEvidence,
  StrategyAlignment,
  TradeReasonType,
  TradeSide,
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
  const [snapshotSaving, setSnapshotSaving] = useState(false);
  const [tradeSubmitting, setTradeSubmitting] = useState(false);
  const [snapshotResult, setSnapshotResult] = useState<string | null>(null);
  const [tradeResult, setTradeResult] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [tradeForm, setTradeForm] = useState<{
    side: TradeSide;
    reasonType: TradeReasonType;
    strategyAlignment: StrategyAlignment;
    note: string;
    price: string;
    quantity: string;
  }>({
    side: "SKIP",
    reasonType: "watch_only",
    strategyAlignment: "unknown",
    note: "",
    price: "",
    quantity: "",
  });

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
            current_step: "等待工作台聚合结果",
            completed_steps: 0,
            total_steps: 9,
            message: "已提交工作台聚合请求。",
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
        setError(cause instanceof Error ? cause.message : "工作台聚合失败。");
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

  const handleSaveSnapshot = async () => {
    setActionError(null);
    setSnapshotResult(null);
    setTradeResult(null);
    setSnapshotSaving(true);
    try {
      const response = await createDecisionSnapshot({
        symbol,
        use_llm: useLlm,
      });
      setSnapshotResult(response.snapshot_id);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "保存判断失败，请稍后重试。");
    } finally {
      setSnapshotSaving(false);
    }
  };

  const handleCreateTrade = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError(null);
    setSnapshotResult(null);
    setTradeResult(null);
    setTradeSubmitting(true);
    try {
      const payload: CreateTradeFromCurrentDecisionRequest = {
        symbol,
        use_llm: useLlm,
        side: tradeForm.side,
        reason_type: tradeForm.reasonType,
        strategy_alignment: tradeForm.strategyAlignment,
        note: tradeForm.note.trim() || undefined,
      };
      if (tradeForm.side !== "SKIP") {
        const price = Number.parseFloat(tradeForm.price);
        const quantity = Number.parseInt(tradeForm.quantity, 10);
        if (!Number.isFinite(price) || price <= 0) {
          throw new Error("非 SKIP 交易需要填写有效价格。");
        }
        if (!Number.isFinite(quantity) || quantity <= 0) {
          throw new Error("非 SKIP 交易需要填写有效数量。");
        }
        payload.price = price;
        payload.quantity = quantity;
      }
      const response = await createTradeFromCurrentDecision(payload);
      setTradeResult(response.trade_id);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "记录交易失败，请稍后重试。");
    } finally {
      setTradeSubmitting(false);
    }
  };

  const failedModules = useMemo(
    () => bundle?.module_status_summary.filter((item) => item.status === "error") ?? [],
    [bundle],
  );

  return (
    <div className="space-y-6">
      <SectionCard
        title="单票工作台"
        description="单票页以工作台聚合（workspace-bundle）作为主入口，并可在启用 LLM 时轮询 debate-review 进度。"
        actions={
          <button
            type="button"
            onClick={() => setRefreshToken((value) => value + 1)}
            className="rounded-2xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800"
          >
            刷新工作台
          </button>
        }
      >
        <form className="grid gap-4 lg:grid-cols-[1fr_auto_auto]" onSubmit={handleSubmit}>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">股票代码</span>
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
              debate-review 使用 LLM
            </span>
          </label>
          <button
            type="submit"
            className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            切换股票
          </button>
        </form>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Metric label="聚合状态" value={formatLabel(status)} />
          <Metric
            label="默认基准日"
            value={formatDate(bundle?.freshness_summary.default_as_of_date ?? null)}
          />
          <Metric
            label="成功模块数"
            value={String(bundle?.module_status_summary.filter((item) => item.status === "success").length ?? 0)}
          />
          <Metric label="失败模块数" value={String(failedModules.length)} />
          <Metric
            label="运行模式"
            value={formatLabel(bundle?.runtime_mode_effective ?? "-")}
          />
        </div>

        {status === "loading" ? <LoadingBlock progress={progress} useLlm={useLlm} /> : null}
        {status === "error" ? (
          <div className="mt-5">
            <StatusBlock title="工作台聚合失败" description={error ?? "请稍后重试。"} tone="error" />
          </div>
        ) : null}
        {failedModules.length > 0 ? (
          <div className="mt-5">
            <StatusBlock
              title="模块部分失败"
              description={`失败模块：${failedModules.map((item) => item.module_name).join("、")}。`}
              tone="error"
            />
          </div>
        ) : null}
        {bundle?.fallback_applied ? (
          <div className="mt-5">
            <StatusBlock
              title="已触发降级"
              description={
                bundle.fallback_reason ??
                "运行时已触发降级，请查看下方告警信息。"
              }
              tone="error"
            />
          </div>
        ) : null}
        {bundle && bundle.warning_messages.length > 0 ? (
          <div className="mt-5">
            <StatusBlock
              title="运行告警"
              description={bundle.warning_messages.join(" | ")}
            />
          </div>
        ) : null}
        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-semibold text-slate-950">决策固化与交易记录</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            可先保存本次判断，再记录交易动作，系统会自动关联当前决策快照。
          </p>
          <div className="mt-4">
            <button
              type="button"
              onClick={handleSaveSnapshot}
              disabled={snapshotSaving || tradeSubmitting}
              className="min-h-11 rounded-2xl bg-slate-900 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:bg-slate-400"
            >
              {snapshotSaving ? "保存中..." : "保存本次判断"}
            </button>
          </div>
          <form className="mt-4 grid gap-3 md:grid-cols-3" onSubmit={handleCreateTrade}>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">动作</span>
              <select
                value={tradeForm.side}
                onChange={(event) =>
                  setTradeForm((previous) => ({
                    ...previous,
                    side: event.target.value as TradeSide,
                  }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                <option value="SKIP">SKIP</option>
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
                <option value="ADD">ADD</option>
                <option value="REDUCE">REDUCE</option>
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">原因类型</span>
              <select
                value={tradeForm.reasonType}
                onChange={(event) =>
                  setTradeForm((previous) => ({
                    ...previous,
                    reasonType: event.target.value as TradeReasonType,
                  }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                <option value="watch_only">watch_only</option>
                <option value="signal_entry">signal_entry</option>
                <option value="pullback_entry">pullback_entry</option>
                <option value="breakout_entry">breakout_entry</option>
                <option value="stop_loss">stop_loss</option>
                <option value="take_profit">take_profit</option>
                <option value="time_exit">time_exit</option>
                <option value="manual_override">manual_override</option>
                <option value="skip_due_to_quality">skip_due_to_quality</option>
                <option value="skip_due_to_risk">skip_due_to_risk</option>
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">策略对齐</span>
              <select
                value={tradeForm.strategyAlignment}
                onChange={(event) =>
                  setTradeForm((previous) => ({
                    ...previous,
                    strategyAlignment: event.target.value as StrategyAlignment,
                  }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                <option value="unknown">unknown</option>
                <option value="aligned">aligned</option>
                <option value="partially_aligned">partially_aligned</option>
                <option value="not_aligned">not_aligned</option>
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">价格（非 SKIP 必填）</span>
              <input
                value={tradeForm.price}
                onChange={(event) =>
                  setTradeForm((previous) => ({ ...previous, price: event.target.value }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">数量（非 SKIP 必填）</span>
              <input
                value={tradeForm.quantity}
                onChange={(event) =>
                  setTradeForm((previous) => ({ ...previous, quantity: event.target.value }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <label className="space-y-2 md:col-span-2">
              <span className="text-sm font-medium text-slate-700">备注</span>
              <input
                value={tradeForm.note}
                onChange={(event) =>
                  setTradeForm((previous) => ({ ...previous, note: event.target.value }))
                }
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={tradeSubmitting || snapshotSaving}
                className="min-h-11 rounded-2xl bg-emerald-700 px-4 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:bg-emerald-300"
              >
                {tradeSubmitting ? "提交中..." : "记录交易"}
              </button>
            </div>
          </form>
          {snapshotResult ? (
            <div className="mt-3">
              <StatusBlock title="保存成功" description={`snapshot_id: ${snapshotResult}`} />
            </div>
          ) : null}
          {tradeResult ? (
            <div className="mt-3">
              <StatusBlock title="记录成功" description={`trade_id: ${tradeResult}`} />
            </div>
          ) : null}
          {actionError ? (
            <div className="mt-3">
              <StatusBlock title="操作失败" description={actionError} tone="error" />
            </div>
          ) : null}
        </div>
      </SectionCard>

      {bundle ? (
        <>
          <SectionCard title="决策简报" description="先看结论，再看证据和行动建议。">
            {bundle.decision_brief ? (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <Metric label="当前动作" value={formatDecisionBriefAction(bundle.decision_brief.action_now)} />
                  <Metric label="置信度" value={formatConvictionLevel(bundle.decision_brief.conviction_level)} />
                  <Metric label="截至日期" value={formatDate(bundle.decision_brief.as_of_date)} />
                  <Metric label="下次复查窗口" value={formatLabel(bundle.decision_brief.next_review_window)} />
                </div>
                <TextPanel title={bundle.decision_brief.name} content={bundle.decision_brief.headline_verdict} />
                <div className="grid gap-4 lg:grid-cols-2">
                  <StringPanel title="入选理由" items={bundle.decision_brief.why_it_made_the_list} />
                  <StringPanel title="暂不重仓原因" items={bundle.decision_brief.why_not_all_in} />
                </div>
              </div>
            ) : (
              <StatusBlock title="暂无决策简报" description="本次工作台聚合未返回决策简报。" />
            )}
          </SectionCard>

          <SectionCard title="证据与行动" description="以下证据与行动建议均可追溯到下层模块真实输出。">
            {bundle.decision_brief ? (
              <div className="space-y-4">
                <div className="grid gap-4 lg:grid-cols-2">
                  <EvidencePanel title="看多证据" items={bundle.decision_brief.key_evidence} />
                  <EvidencePanel title="风险证据" items={bundle.decision_brief.key_risks} />
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <StringPanel title="下一步动作" items={bundle.decision_brief.what_to_do_next} />
                  <StringPanel
                    title="来源模块"
                    items={bundle.decision_brief.source_modules.map((item) => `${item.module_name}${item.note ? ` / ${item.note}` : ""}`)}
                  />
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <StringPanel
                    title="关注价位"
                    items={bundle.decision_brief.price_levels_to_watch.map((item) => `${item.label}: ${item.value_text}${item.note ? ` / ${item.note}` : ""}`)}
                  />
                  <StringPanel
                    title="证据索引"
                    items={(bundle.evidence_manifest?.bundles ?? []).flatMap((item) =>
                      item.refs.slice(0, 3).map((ref) => `${ref.dataset} / ${ref.provider} / ${ref.field_path}`),
                    )}
                  />
                </div>
              </div>
            ) : (
              <StatusBlock title="暂无证据层" description="决策简报证据暂不可用。" />
            )}
          </SectionCard>

          <SectionCard title="详细模块" description="下层模块仍可查看，但展示顺序已下沉到结论层之后。">
            <div className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="基础信息">
                  {bundle.profile ? (
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <Metric label="名称" value={bundle.profile.name} />
                      <Metric label="行业" value={bundle.profile.industry ?? "-"} />
                      <Metric label="上市日期" value={formatDate(bundle.profile.list_date)} />
                      <Metric label="状态" value={bundle.profile.status ?? "-"} />
                      <Metric label="总市值" value={bundle.profile.total_market_cap === null ? "-" : String(bundle.profile.total_market_cap)} />
                      <Metric label="数据源" value={bundle.profile.source} />
                    </div>
                  ) : (
                    <StatusBlock title="暂不可用" description="基础信息暂不可用。" />
                  )}
                </Panel>

                <Panel title="新鲜度摘要">
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
                <Panel title="因子快照">
                  {bundle.factor_snapshot ? (
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <Metric label="Alpha 分" value={formatScore(bundle.factor_snapshot.alpha_score.total_score)} />
                      <Metric label="触发分" value={formatScore(bundle.factor_snapshot.trigger_score.total_score)} />
                      <Metric label="风险分" value={formatScore(bundle.factor_snapshot.risk_score.total_score)} />
                      <Metric label="触发状态" value={formatLabel(bundle.factor_snapshot.trigger_score.trigger_state)} />
                      <Metric label="新鲜度模式" value={bundle.factor_snapshot.freshness_mode ?? "-"} />
                      <Metric label="来源模式" value={bundle.factor_snapshot.source_mode ?? "-"} />
                    </div>
                  ) : (
                    <StatusBlock title="暂不可用" description="因子快照暂不可用。" />
                  )}
                </Panel>

                <Panel title="review-report v2（主研究产物）">
                  {bundle.review_report ? (
                    <div className="space-y-3">
                      <Metric label="最终动作" value={formatAction(bundle.review_report.final_judgement.action)} />
                      <TextPanel title="技术面观点" content={bundle.review_report.technical_view.tactical_read} />
                      <TextPanel title="事件面观点" content={bundle.review_report.event_view.concise_summary} />
                    </div>
                  ) : (
                    <StatusBlock title="暂不可用" description="review-report 暂不可用。" />
                  )}
                </Panel>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="debate-review（结构化裁决）">
                  {bundle.debate_review ? (
                    <div className="space-y-3">
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        <Metric
                          label="请求模式"
                          value={formatLabel(bundle.debate_review.runtime_mode_requested ?? "-")}
                        />
                        <Metric
                          label="实际模式"
                          value={formatLabel(bundle.debate_review.runtime_mode_effective ?? bundle.debate_review.runtime_mode)}
                        />
                        <Metric label="最终动作" value={formatAction(bundle.debate_review.final_action)} />
                        <Metric
                          label="使用数据提供方"
                          value={bundle.debate_review.provider_used ?? "-"}
                        />
                        <Metric
                          label="已降级"
                          value={bundle.debate_review.fallback_applied ? "是" : "否"}
                        />
                      </div>
                      {bundle.debate_review.fallback_applied ? (
                        <StatusBlock
                          title="debate-review 已降级"
                          description={
                            bundle.debate_review.fallback_reason ??
                            "LLM 裁决失败，已切换为规则裁决。"
                          }
                        />
                      ) : null}
                      {bundle.debate_review.warning_messages.length > 0 ? (
                        <StatusBlock
                          title="debate-review 告警"
                          description={bundle.debate_review.warning_messages.join(" | ")}
                        />
                      ) : null}
                      <TextPanel title="首席裁决摘要" content={bundle.debate_review.chief_judgement.summary} />
                      <StringPanel title="看多观点" items={bundle.debate_review.bull_case.reasons.map((item) => item.detail)} />
                      <StringPanel title="看空观点" items={bundle.debate_review.bear_case.reasons.map((item) => item.detail)} />
                    </div>
                  ) : useLlm && progress ? (
                    <StatusBlock
                      title="LLM 裁决仍在运行"
                      description={`${progress.current_step ?? progress.message} (${progress.completed_steps}/${progress.total_steps || "?"})`}
                    />
                  ) : (
                    <StatusBlock title="暂不可用" description="debate-review 暂不可用。" />
                  )}
                </Panel>

                <Panel title="策略与触发">
                  <div className="space-y-3">
                    {bundle.strategy_plan ? (
                      <>
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                          <Metric label="策略动作" value={formatAction(bundle.strategy_plan.action)} />
                          <Metric label="策略类型" value={formatLabel(bundle.strategy_plan.strategy_type)} />
                          <Metric label="理想入场区间" value={formatRange(bundle.strategy_plan.ideal_entry_range)} />
                          <Metric label="止损位" value={formatPrice(bundle.strategy_plan.stop_loss_price)} />
                          <Metric label="止盈区间" value={formatRange(bundle.strategy_plan.take_profit_range)} />
                          <Metric label="复查周期" value={bundle.strategy_plan.review_timeframe} />
                        </div>
                      </>
                    ) : null}
                    {bundle.trigger_snapshot ? (
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        <Metric label="触发状态" value={formatLabel(bundle.trigger_snapshot.trigger_state)} />
                        <Metric label="最新价格" value={formatPrice(bundle.trigger_snapshot.latest_intraday_price)} />
                        <Metric label="支撑位" value={formatPrice(bundle.trigger_snapshot.daily_support_level)} />
                        <Metric label="压力位" value={formatPrice(bundle.trigger_snapshot.daily_resistance_level)} />
                        <Metric label="距支撑位" value={formatPercent(bundle.trigger_snapshot.distance_to_support_pct)} />
                        <Metric label="距压力位" value={formatPercent(bundle.trigger_snapshot.distance_to_resistance_pct)} />
                      </div>
                    ) : null}
                    {!bundle.strategy_plan && !bundle.trigger_snapshot ? (
                      <StatusBlock title="暂不可用" description="策略计划与触发快照暂不可用。" />
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
        title="正在加载工作台聚合"
        description={
          useLlm && progress
            ? `${progress.current_step ?? progress.message} (${progress.completed_steps}/${progress.total_steps || "?"})`
            : "正在等待后端返回工作台聚合结果。"
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
        <p className="mt-3 text-sm leading-6 text-slate-600">暂无条目。</p>
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
        <p className="mt-3 text-sm leading-6 text-slate-600">暂无证据条目。</p>
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
