"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  getDebateReview,
  getFactorSnapshot,
  getStockProfile,
  getStockReviewReport,
  getStrategyPlan,
  getTriggerSnapshot,
  normalizeSymbolInput,
} from "@/lib/api";
import {
  formatAction,
  formatDate,
  formatDateTime,
  formatLabel,
  formatPercent,
  formatPrice,
  formatRange,
  formatScore,
} from "@/lib/format";
import type {
  DebatePoint,
  DebateReviewReport,
  FactorSnapshot,
  StockProfile,
  StockReviewReport,
  StrategyPlan,
  TriggerSnapshot,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { SingleStockWorkflowPanel } from "./single-stock-workflow-panel";
import { StatusBlock } from "./status-block";

type StockWorkspaceProps = {
  symbol: string;
};

type ModuleKey =
  | "profile"
  | "factorSnapshot"
  | "reviewReport"
  | "debateReview"
  | "strategyPlan"
  | "triggerSnapshot";

type WorkspaceData = {
  profile: StockProfile | null;
  factorSnapshot: FactorSnapshot | null;
  reviewReport: StockReviewReport | null;
  debateReview: DebateReviewReport | null;
  strategyPlan: StrategyPlan | null;
  triggerSnapshot: TriggerSnapshot | null;
};

const EMPTY_WORKSPACE_DATA: WorkspaceData = {
  profile: null,
  factorSnapshot: null,
  reviewReport: null,
  debateReview: null,
  strategyPlan: null,
  triggerSnapshot: null,
};

export function StockWorkspace({ symbol }: StockWorkspaceProps) {
  const router = useRouter();
  const [inputValue, setInputValue] = useState(symbol);
  const [useLlm, setUseLlm] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [data, setData] = useState<WorkspaceData>(EMPTY_WORKSPACE_DATA);
  const [errors, setErrors] = useState<Partial<Record<ModuleKey, string>>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setInputValue(symbol);
  }, [symbol]);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);

      const results = await Promise.allSettled([
        getStockProfile(symbol),
        getFactorSnapshot(symbol),
        getStockReviewReport(symbol),
        getDebateReview(symbol, { useLlm }),
        getStrategyPlan(symbol),
        getTriggerSnapshot(symbol),
      ]);

      if (!active) {
        return;
      }

      const nextData: WorkspaceData = {
        profile: getSettledValue(results[0]),
        factorSnapshot: getSettledValue(results[1]),
        reviewReport: getSettledValue(results[2]),
        debateReview: getSettledValue(results[3]),
        strategyPlan: getSettledValue(results[4]),
        triggerSnapshot: getSettledValue(results[5]),
      };

      const nextErrors: Partial<Record<ModuleKey, string>> = {
        profile: getSettledError(results[0]),
        factorSnapshot: getSettledError(results[1]),
        reviewReport: getSettledError(results[2]),
        debateReview: getSettledError(results[3]),
        strategyPlan: getSettledError(results[4]),
        triggerSnapshot: getSettledError(results[5]),
      };

      setData(nextData);
      setErrors(removeEmptyErrors(nextErrors));
      setLoading(false);
    }

    void load();

    return () => {
      active = false;
    };
  }, [refreshToken, symbol, useLlm]);

  const failedModules = useMemo(
    () =>
      Object.entries(errors)
        .filter(([, value]) => Boolean(value))
        .map(([key]) => key),
    [errors],
  );

  const hasAnyData = Object.values(data).some((value) => value !== null);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedSymbol = normalizeSymbolInput(inputValue);
    if (!normalizedSymbol) {
      return;
    }

    router.push(`/stocks/${encodeURIComponent(normalizedSymbol)}`);
  };

  return (
    <div className="space-y-6">
      <SectionCard
        title="单票工作台控制台"
        description="切换股票代码、刷新当前链路，并决定 debate-review 是否启用 LLM。"
        actions={
          <button
            type="button"
            onClick={() => setRefreshToken((current) => current + 1)}
            className="rounded-2xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800"
          >
            刷新当前股票分析
          </button>
        }
      >
        <div className="space-y-4">
          <form className="grid gap-4 lg:grid-cols-[1fr_auto_auto]" onSubmit={handleSubmit}>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">symbol</span>
              <input
                value={inputValue}
                onChange={(event) => setInputValue(event.target.value)}
                placeholder="输入股票代码，例如 600519.SH"
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

          {loading ? (
            <StatusBlock
              title="正在加载"
              description="正在并行读取基础信息、因子快照、review-report、debate-review、strategy plan 和触发快照。"
            />
          ) : null}

          {!loading && failedModules.length > 0 ? (
            <StatusBlock
              title="部分模块加载失败"
              description={`当前仍可查看已成功返回的模块。失败模块：${failedModules.join("、")}。`}
              tone="error"
            />
          ) : null}

          {!loading && !hasAnyData ? (
            <StatusBlock
              title="暂无可展示结果"
              description="当前没有拿到可展示的单票分析结果，请确认后端服务和数据源状态。"
              tone="error"
            />
          ) : null}
        </div>
      </SectionCard>

      <SectionCard
        title="股票基础信息"
        description="这里展示当前股票的基础资料和静态元信息。"
      >
        {data.profile ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-2xl font-semibold text-slate-950">
                {data.profile.name}
              </h2>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
                {data.profile.symbol}
              </span>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
                {data.profile.exchange}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="行业" value={data.profile.industry ?? "-"} />
              <Metric label="上市日期" value={formatDate(data.profile.list_date)} />
              <Metric label="状态" value={data.profile.status ?? "-"} />
              <Metric
                label="总市值"
                value={formatLargeNumber(data.profile.total_market_cap)}
              />
              <Metric
                label="流通市值"
                value={formatLargeNumber(data.profile.circulating_market_cap)}
              />
              <Metric label="数据源" value={data.profile.source} />
            </div>
          </div>
        ) : (
          <ModuleFallback
            error={errors.profile}
            emptyText="当前没有拿到股票基础信息。"
          />
        )}
      </SectionCard>

      <SectionCard
        title="Factor Snapshot 摘要"
        description="显示 alpha / trigger / risk 三个核心分数，以及当前最强和最弱的因子组。"
      >
        {data.factorSnapshot ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="交易日" value={formatDate(data.factorSnapshot.as_of_date)} />
              <Metric
                label="alpha 分"
                value={formatScore(data.factorSnapshot.alpha_score.total_score)}
              />
              <Metric
                label="trigger 分"
                value={formatScore(data.factorSnapshot.trigger_score.total_score)}
              />
              <Metric
                label="trigger 状态"
                value={formatLabel(data.factorSnapshot.trigger_score.trigger_state)}
              />
              <Metric
                label="risk 分"
                value={formatScore(data.factorSnapshot.risk_score.total_score)}
              />
              <Metric
                label="因子组数"
                value={String(data.factorSnapshot.factor_group_scores.length)}
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <SignalGroupList
                title="偏强因子组"
                groups={data.factorSnapshot.factor_group_scores
                  .filter((group) => (group.score ?? 0) >= 50)
                  .slice(0, 4)}
                emptyText="当前没有明确偏强的因子组。"
                signalKey="top_positive_signals"
              />
              <SignalGroupList
                title="偏弱因子组"
                groups={data.factorSnapshot.factor_group_scores
                  .filter((group) => (group.score ?? 0) < 50)
                  .slice(0, 4)}
                emptyText="当前没有明确偏弱的因子组。"
                signalKey="top_negative_signals"
              />
            </div>
          </div>
        ) : (
          <ModuleFallback
            error={errors.factorSnapshot}
            emptyText="当前没有拿到因子快照。"
          />
        )}
      </SectionCard>

      <SectionCard
        title="Review Report v2"
        description="这里汇总 review_service 的多维结构化判断，不展示原始 JSON。"
      >
        {data.reviewReport ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <Metric
                label="最终动作"
                value={formatAction(data.reviewReport.final_judgement.action)}
              />
              <Metric
                label="置信度"
                value={formatScore(data.reviewReport.confidence)}
              />
              <Metric
                label="alpha / trigger / risk"
                value={`${data.reviewReport.factor_profile.alpha_score} / ${data.reviewReport.factor_profile.trigger_score} / ${data.reviewReport.factor_profile.risk_score}`}
              />
              <Metric
                label="技术趋势"
                value={formatLabel(data.reviewReport.technical_view.trend_state)}
              />
              <Metric
                label="事件温度"
                value={formatLabel(data.reviewReport.event_view.event_temperature)}
              />
            </div>
            <TextPanel
              title="最终结论"
              content={data.reviewReport.final_judgement.summary}
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <TextPanel
                title="因子画像"
                content={data.reviewReport.factor_profile.concise_summary}
              />
              <TextPanel
                title="技术画像"
                content={data.reviewReport.technical_view.tactical_read}
              />
              <TextPanel
                title="基本面画像"
                content={
                  data.reviewReport.fundamental_view.quality_read ??
                  data.reviewReport.fundamental_view.data_completeness_note
                }
              />
              <TextPanel
                title="事件与情绪"
                content={`${data.reviewReport.event_view.concise_summary} ${data.reviewReport.sentiment_view.concise_summary}`}
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <StringListPanel
                title="多头理由"
                items={data.reviewReport.bull_case.reasons}
                emptyText="当前没有多头理由。"
              />
              <StringListPanel
                title="空头理由"
                items={data.reviewReport.bear_case.reasons}
                emptyText="当前没有空头理由。"
              />
              <StringListPanel
                title="关键分歧"
                items={data.reviewReport.key_disagreements}
                emptyText="当前没有关键分歧。"
              />
              <StringListPanel
                title="最终关键点"
                items={data.reviewReport.final_judgement.key_points}
                emptyText="当前没有最终关键点。"
              />
            </div>
          </div>
        ) : (
          <ModuleFallback
            error={errors.reviewReport}
            emptyText="当前没有拿到 review-report。"
          />
        )}
      </SectionCard>

      <SectionCard
        title="Debate Review"
        description="这里展示角色化裁决结果，可切换 rule-based 与 LLM 运行模式。"
      >
        {data.debateReview ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric
                label="运行模式"
                value={data.debateReview.runtime_mode === "llm" ? "LLM" : "规则版"}
              />
              <Metric
                label="最终动作"
                value={formatAction(data.debateReview.final_action)}
              />
              <Metric
                label="置信度"
                value={formatScore(data.debateReview.confidence)}
              />
              <Metric
                label="风险等级"
                value={formatLabel(data.debateReview.risk_review.risk_level)}
              />
              <Metric
                label="策略类型"
                value={formatLabel(data.debateReview.strategy_summary.strategy_type)}
              />
              <Metric
                label="复核周期"
                value={formatLabel(data.debateReview.strategy_summary.review_timeframe)}
              />
            </div>
            <TextPanel
              title="首席裁决"
              content={data.debateReview.chief_judgement.summary}
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <AnalystPanel
                title="技术分析员"
                summary={data.debateReview.analyst_views.technical.summary}
                positivePoints={data.debateReview.analyst_views.technical.positive_points}
                cautionPoints={data.debateReview.analyst_views.technical.caution_points}
              />
              <AnalystPanel
                title="基本面分析员"
                summary={data.debateReview.analyst_views.fundamental.summary}
                positivePoints={data.debateReview.analyst_views.fundamental.positive_points}
                cautionPoints={data.debateReview.analyst_views.fundamental.caution_points}
              />
              <AnalystPanel
                title="事件分析员"
                summary={data.debateReview.analyst_views.event.summary}
                positivePoints={data.debateReview.analyst_views.event.positive_points}
                cautionPoints={data.debateReview.analyst_views.event.caution_points}
              />
              <AnalystPanel
                title="情绪分析员"
                summary={data.debateReview.analyst_views.sentiment.summary}
                positivePoints={data.debateReview.analyst_views.sentiment.positive_points}
                cautionPoints={data.debateReview.analyst_views.sentiment.caution_points}
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <DebatePointPanel
                title="多头研究员"
                summary={data.debateReview.bull_case.summary}
                points={data.debateReview.bull_case.reasons}
              />
              <DebatePointPanel
                title="空头研究员"
                summary={data.debateReview.bear_case.summary}
                points={data.debateReview.bear_case.reasons}
              />
              <StringListPanel
                title="裁决关键点"
                items={data.debateReview.chief_judgement.decisive_points}
                emptyText="当前没有裁决关键点。"
              />
              <StringListPanel
                title="执行提醒"
                items={data.debateReview.risk_review.execution_reminders}
                emptyText="当前没有额外执行提醒。"
              />
            </div>
          </div>
        ) : (
          <ModuleFallback
            error={errors.debateReview}
            emptyText="当前没有拿到 debate-review。"
          />
        )}
      </SectionCard>

      <SectionCard
        title="Strategy Plan"
        description="展示结构化交易策略，只保留执行需要的关键字段。"
      >
        {data.strategyPlan ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="动作" value={formatAction(data.strategyPlan.action)} />
              <Metric
                label="策略类型"
                value={formatLabel(data.strategyPlan.strategy_type)}
              />
              <Metric
                label="入场窗口"
                value={formatLabel(data.strategyPlan.entry_window)}
              />
              <Metric
                label="理想入场区间"
                value={formatRange(data.strategyPlan.ideal_entry_range)}
              />
              <Metric
                label="止损价"
                value={formatPrice(data.strategyPlan.stop_loss_price)}
              />
              <Metric
                label="止盈区间"
                value={formatRange(data.strategyPlan.take_profit_range)}
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <StringListPanel
                title="入场触发"
                items={data.strategyPlan.entry_triggers}
                emptyText="当前没有入场触发条件。"
              />
              <StringListPanel
                title="避免条件"
                items={data.strategyPlan.avoid_if}
                emptyText="当前没有避免条件。"
              />
              <TextPanel
                title="止损规则"
                content={data.strategyPlan.stop_loss_rule}
              />
              <TextPanel
                title="止盈规则"
                content={data.strategyPlan.take_profit_rule}
              />
              <TextPanel title="持有规则" content={data.strategyPlan.hold_rule} />
              <TextPanel title="卖出规则" content={data.strategyPlan.sell_rule} />
            </div>
          </div>
        ) : (
          <ModuleFallback
            error={errors.strategyPlan}
            emptyText="当前没有拿到 strategy plan。"
          />
        )}
      </SectionCard>

      <SectionCard
        title="盘中 / Trigger Snapshot"
        description="如果当前 provider 可用，这里会给出轻量盘中触发摘要；若不可用，也会明确展示当前状态。"
      >
        {data.triggerSnapshot ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric
                label="快照时间"
                value={formatDateTime(data.triggerSnapshot.as_of_datetime)}
              />
              <Metric
                label="触发状态"
                value={formatLabel(data.triggerSnapshot.trigger_state)}
              />
              <Metric
                label="日线趋势"
                value={formatLabel(data.triggerSnapshot.daily_trend_state)}
              />
              <Metric
                label="最新价格"
                value={formatPrice(data.triggerSnapshot.latest_intraday_price)}
              />
              <Metric
                label="距支撑位"
                value={formatPercent(data.triggerSnapshot.distance_to_support_pct)}
              />
              <Metric
                label="距压力位"
                value={formatPercent(data.triggerSnapshot.distance_to_resistance_pct)}
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <TextPanel title="触发说明" content={data.triggerSnapshot.trigger_note} />
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-950">关键价位</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Metric
                    label="支撑位"
                    value={formatPrice(data.triggerSnapshot.daily_support_level)}
                  />
                  <Metric
                    label="压力位"
                    value={formatPrice(data.triggerSnapshot.daily_resistance_level)}
                  />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <ModuleFallback
            error={errors.triggerSnapshot}
            emptyText="当前没有拿到 trigger snapshot。"
          />
        )}
      </SectionCard>

      <SingleStockWorkflowPanel symbol={symbol} />
    </div>
  );
}

function SignalGroupList({
  title,
  groups,
  emptyText,
  signalKey,
}: {
  title: string;
  groups: FactorSnapshot["factor_group_scores"];
  emptyText: string;
  signalKey: "top_positive_signals" | "top_negative_signals";
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {groups.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">{emptyText}</p>
      ) : (
        <div className="mt-3 grid gap-3">
          {groups.map((group) => (
            <div key={group.group_name} className="rounded-2xl bg-white p-3">
              <p className="text-sm font-semibold text-slate-900">
                {group.group_name}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                组分数：{formatScore(group.score)}
              </p>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                {group[signalKey].length === 0 ? (
                  <li>当前没有额外信号。</li>
                ) : (
                  group[signalKey].slice(0, 3).map((signal) => <li key={signal}>{signal}</li>)
                )}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AnalystPanel({
  title,
  summary,
  positivePoints,
  cautionPoints,
}: {
  title: string;
  summary: string;
  positivePoints: DebatePoint[];
  cautionPoints: DebatePoint[];
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-3 text-sm leading-6 text-slate-700">{summary}</p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <DebatePointList
          title="支持点"
          points={positivePoints}
          emptyText="当前没有支持点。"
        />
        <DebatePointList
          title="谨慎点"
          points={cautionPoints}
          emptyText="当前没有谨慎点。"
        />
      </div>
    </div>
  );
}

function DebatePointPanel({
  title,
  summary,
  points,
}: {
  title: string;
  summary: string;
  points: DebatePoint[];
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-3 text-sm leading-6 text-slate-700">{summary}</p>
      <DebatePointList
        title="核心要点"
        points={points}
        emptyText="当前没有核心要点。"
        className="mt-4"
      />
    </div>
  );
}

function DebatePointList({
  title,
  points,
  emptyText,
  className,
}: {
  title: string;
  points: DebatePoint[];
  emptyText: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      {points.length === 0 ? (
        <p className="mt-2 text-sm leading-6 text-slate-600">{emptyText}</p>
      ) : (
        <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
          {points.map((point) => (
            <li key={`${point.title}-${point.detail}`} className="rounded-2xl bg-white p-3">
              <p className="font-medium text-slate-900">{point.title}</p>
              <p className="mt-1">{point.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StringListPanel({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: string[];
  emptyText: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">{emptyText}</p>
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

function TextPanel({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-3 text-sm leading-6 text-slate-700">{content}</p>
    </div>
  );
}

function ModuleFallback({
  error,
  emptyText,
}: {
  error?: string;
  emptyText: string;
}) {
  if (error) {
    return <StatusBlock title="加载失败" description={error} tone="error" />;
  }

  return <StatusBlock title="暂无结果" description={emptyText} />;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function getSettledValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}

function getSettledError<T>(result: PromiseSettledResult<T>): string | undefined {
  if (result.status === "fulfilled") {
    return undefined;
  }

  if (result.reason instanceof Error) {
    return result.reason.message;
  }

  return "发生未知错误，请稍后重试。";
}

function removeEmptyErrors(
  errors: Partial<Record<ModuleKey, string>>,
): Partial<Record<ModuleKey, string>> {
  return Object.fromEntries(
    Object.entries(errors).filter(([, value]) => Boolean(value)),
  ) as Partial<Record<ModuleKey, string>>;
}

function formatLargeNumber(value: number | null): string {
  if (value === null) {
    return "-";
  }

  if (value >= 100000000) {
    return `${(value / 100000000).toFixed(2)} 亿`;
  }

  return formatPrice(value);
}
