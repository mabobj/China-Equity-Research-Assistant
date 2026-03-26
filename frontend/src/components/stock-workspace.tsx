"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  getDecisionBrief,
  getDebateReview,
  getDebateReviewProgress,
  getFactorSnapshot,
  getStockProfile,
  getStockReviewReport,
  getStrategyPlan,
  getTriggerSnapshot,
  normalizeSymbolInput,
} from "@/lib/api";
import {
  formatAction,
  formatConvictionLevel,
  formatDate,
  formatDateTime,
  formatDecisionBriefAction,
  formatLabel,
  formatPercent,
  formatPrice,
  formatRange,
  formatScore,
} from "@/lib/format";
import type {
  DecisionBrief,
  DecisionBriefEvidence,
  DecisionPriceLevel,
  DecisionSourceModule,
  DebatePoint,
  DebateReviewProgress,
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

type StockWorkspaceProps = { symbol: string };

type ModuleKey =
  | "decisionBrief"
  | "profile"
  | "factorSnapshot"
  | "reviewReport"
  | "debateReview"
  | "strategyPlan"
  | "triggerSnapshot";

type ModuleState<T> = {
  status: "idle" | "loading" | "success" | "error";
  data: T | null;
  error: string | null;
  startedAt: number | null;
  progress: DebateReviewProgress | null;
};

type WorkspaceState = {
  decisionBrief: ModuleState<DecisionBrief>;
  profile: ModuleState<StockProfile>;
  factorSnapshot: ModuleState<FactorSnapshot>;
  reviewReport: ModuleState<StockReviewReport>;
  debateReview: ModuleState<DebateReviewReport>;
  strategyPlan: ModuleState<StrategyPlan>;
  triggerSnapshot: ModuleState<TriggerSnapshot>;
};

const MODULE_LABELS: Record<ModuleKey, string> = {
  decisionBrief: "Decision Brief",
  profile: "股票基础信息",
  factorSnapshot: "Factor Snapshot",
  reviewReport: "Review Report v2",
  debateReview: "Debate Review",
  strategyPlan: "Strategy Plan",
  triggerSnapshot: "盘中 / Trigger Snapshot",
};

const MODULE_ORDER: ModuleKey[] = [
  "decisionBrief",
  "profile",
  "factorSnapshot",
  "reviewReport",
  "debateReview",
  "strategyPlan",
  "triggerSnapshot",
];

function createEmptyModuleState<T>(): ModuleState<T> {
  return { status: "idle", data: null, error: null, startedAt: null, progress: null };
}

function createLoadingModuleState<T>(): ModuleState<T> {
  return {
    status: "loading",
    data: null,
    error: null,
    startedAt: Date.now(),
    progress: null,
  };
}

function createInitialWorkspaceState(): WorkspaceState {
  return {
    decisionBrief: createEmptyModuleState<DecisionBrief>(),
    profile: createEmptyModuleState<StockProfile>(),
    factorSnapshot: createEmptyModuleState<FactorSnapshot>(),
    reviewReport: createEmptyModuleState<StockReviewReport>(),
    debateReview: createEmptyModuleState<DebateReviewReport>(),
    strategyPlan: createEmptyModuleState<StrategyPlan>(),
    triggerSnapshot: createEmptyModuleState<TriggerSnapshot>(),
  };
}

function createLoadingWorkspaceState(): WorkspaceState {
  return {
    decisionBrief: createLoadingModuleState<DecisionBrief>(),
    profile: createLoadingModuleState<StockProfile>(),
    factorSnapshot: createLoadingModuleState<FactorSnapshot>(),
    reviewReport: createLoadingModuleState<StockReviewReport>(),
    debateReview: createLoadingModuleState<DebateReviewReport>(),
    strategyPlan: createLoadingModuleState<StrategyPlan>(),
    triggerSnapshot: createLoadingModuleState<TriggerSnapshot>(),
  };
}

function buildInitialLlmProgress(symbol: string): DebateReviewProgress {
  return {
    symbol,
    request_id: null,
    status: "running",
    stage: "building_inputs",
    runtime_mode: "llm",
    current_step: "等待后台启动 LLM 裁决",
    completed_steps: 0,
    total_steps: 9,
    message: "已提交 LLM debate-review，请等待后台按角色顺序完成。",
    started_at: null,
    updated_at: null,
    finished_at: null,
    error_message: null,
    recent_steps: [],
  };
}

export function StockWorkspace({ symbol }: StockWorkspaceProps) {
  const router = useRouter();
  const [inputValue, setInputValue] = useState(symbol);
  const [useLlm, setUseLlm] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [workspaceState, setWorkspaceState] = useState<WorkspaceState>(createInitialWorkspaceState());
  const [clock, setClock] = useState(Date.now());

  useEffect(() => {
    setInputValue(symbol);
  }, [symbol]);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true;
    let progressTimer: number | null = null;

    const nextState = createLoadingWorkspaceState();
    if (useLlm) {
      const initialProgress = buildInitialLlmProgress(symbol);
      nextState.decisionBrief.progress = initialProgress;
      nextState.debateReview.progress = initialProgress;
    }
    setWorkspaceState(nextState);

    const debateRequestId = useLlm ? buildDebateRequestId(symbol) : undefined;

    const updateModule = <K extends ModuleKey>(
      key: K,
      updater: (previous: WorkspaceState[K]) => WorkspaceState[K],
    ) => {
      if (!active) return;
      setWorkspaceState((previous) => ({ ...previous, [key]: updater(previous[key]) }));
    };

    const markModuleSuccess = <K extends ModuleKey>(key: K, value: WorkspaceState[K]["data"]) => {
      updateModule(key, (previous) => ({
        ...previous,
        status: "success",
        data: value,
        error: null,
        progress: null,
      }));
    };

    const markModuleError = (key: ModuleKey, error: unknown) => {
      updateModule(key, (previous) => ({
        ...previous,
        status: "error",
        data: null,
        error: toErrorMessage(error),
      }));
    };

    const stopDebateProgressPolling = () => {
      if (progressTimer !== null) {
        window.clearInterval(progressTimer);
        progressTimer = null;
      }
    };

    const startDebateProgressPolling = () => {
      if (!useLlm || !debateRequestId) return;
      const poll = async () => {
        try {
          const progress = await getDebateReviewProgress(symbol, {
            useLlm: true,
            requestId: debateRequestId,
          });
          if (!active) return;
          updateModule("debateReview", (previous) => ({ ...previous, progress }));
          updateModule("decisionBrief", (previous) => ({ ...previous, progress }));
        } catch {
          // 进度失败时不打断主请求。
        }
      };
      void poll();
      progressTimer = window.setInterval(() => void poll(), 1500);
    };

    const loadModule = async <T, K extends ModuleKey>(key: K, loader: () => Promise<T>) => {
      try {
        const value = await loader();
        if (!active) return;
        markModuleSuccess(key, value as WorkspaceState[K]["data"]);
      } catch (error) {
        if (!active) return;
        markModuleError(key, error);
      }
    };

    startDebateProgressPolling();

    void loadModule("decisionBrief", () => getDecisionBrief(symbol, { useLlm }));
    void loadModule("profile", () => getStockProfile(symbol));
    void loadModule("factorSnapshot", () => getFactorSnapshot(symbol));
    void loadModule("reviewReport", () => getStockReviewReport(symbol));
    void loadModule("debateReview", async () => {
      try {
        return await getDebateReview(symbol, { useLlm, requestId: debateRequestId });
      } finally {
        stopDebateProgressPolling();
      }
    });
    void loadModule("strategyPlan", () => getStrategyPlan(symbol));
    void loadModule("triggerSnapshot", () => getTriggerSnapshot(symbol));

    return () => {
      active = false;
      stopDebateProgressPolling();
    };
  }, [refreshToken, symbol, useLlm]);

  const moduleSummaries = useMemo(
    () =>
      MODULE_ORDER.map((key) => ({
        key,
        label: MODULE_LABELS[key],
        status: workspaceState[key].status,
      })),
    [workspaceState],
  );
  const loadingModules = moduleSummaries.filter((item) => item.status === "loading");
  const failedModules = moduleSummaries.filter((item) => item.status === "error");
  const completedModules = moduleSummaries.filter((item) => item.status === "success");

  const decisionBrief = workspaceState.decisionBrief.data;
  const profile = workspaceState.profile.data;
  const analysisAsOfDate =
    decisionBrief?.as_of_date ??
    workspaceState.reviewReport.data?.as_of_date ??
    workspaceState.debateReview.data?.as_of_date ??
    workspaceState.strategyPlan.data?.as_of_date ??
    workspaceState.factorSnapshot.data?.as_of_date ??
    null;
  const triggerAsOfDateTime = workspaceState.triggerSnapshot.data?.as_of_datetime ?? null;
  const hasProfileGaps = Boolean(
    profile &&
      (!profile.industry ||
        !profile.list_date ||
        profile.total_market_cap === null ||
        profile.circulating_market_cap === null),
  );

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedSymbol = normalizeSymbolInput(inputValue);
    if (!normalizedSymbol) return;
    router.push(`/stocks/${encodeURIComponent(normalizedSymbol)}`);
  };

  return (
    <div className="space-y-6">
      <SectionCard
        title="单票工作台控制台"
        description="切换股票代码、刷新当前链路，并决定 Debate Review 是否启用 LLM。"
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
                Debate Review 使用 LLM
              </span>
            </label>
            <button
              type="submit"
              className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              切换股票
            </button>
          </form>

          <div className="grid gap-3 lg:grid-cols-3">
            <Metric label="已完成模块" value={`${completedModules.length} / ${MODULE_ORDER.length}`} />
            <Metric label="加载中模块" value={loadingModules.length === 0 ? "0" : loadingModules.map((item) => item.label).join("、")} />
            <Metric label="失败模块" value={failedModules.length === 0 ? "无" : failedModules.map((item) => item.label).join("、")} />
          </div>

          {loadingModules.length > 0 ? (
            <StatusBlock
              title="模块正在独立加载"
              description={`当前仍在加载：${loadingModules.map((item) => item.label).join("、")}。页面不会等待所有模块同时完成，你可以先查看已经返回的内容。`}
            />
          ) : null}

          {failedModules.length > 0 ? (
            <StatusBlock
              title="部分模块加载失败"
              description={`失败模块：${failedModules.map((item) => item.label).join("、")}。其他模块仍可继续查看。`}
              tone="error"
            />
          ) : null}
        </div>
      </SectionCard>

      <SectionCard
        title="Decision Brief"
        description="先看结论：当前该不该动、为什么值得看、为什么还不能重仓。"
      >
        {renderModuleState({
          state: workspaceState.decisionBrief,
          loadingTitle: useLlm ? "正在生成 LLM 版 Decision Brief" : "正在生成 Decision Brief",
          loadingDescription: buildDebateLoadingDescription({
            progress: workspaceState.decisionBrief.progress,
            startedAt: workspaceState.decisionBrief.startedAt,
            clock,
            useLlm,
          }),
          emptyText: "当前没有拿到统一决策简报。",
          content: decisionBrief ? (
            <div className="space-y-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                      {decisionBrief.symbol}
                    </span>
                    {profile?.industry ? (
                      <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                        {profile.industry}
                      </span>
                    ) : null}
                    {profile?.source ? (
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600">
                        基础资料：{profile.source}
                      </span>
                    ) : null}
                  </div>
                  <h3 className="text-2xl font-semibold text-slate-950">{decisionBrief.name}</h3>
                  <p className="max-w-3xl text-base leading-7 text-slate-700">{decisionBrief.headline_verdict}</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:w-[340px]">
                  <Metric label="当前动作" value={formatDecisionBriefAction(decisionBrief.action_now)} />
                  <Metric label="置信度" value={formatConvictionLevel(decisionBrief.conviction_level)} />
                  <Metric label="分析基准日" value={formatDate(decisionBrief.as_of_date)} />
                  <Metric label="复核窗口" value={formatLabel(decisionBrief.next_review_window)} />
                </div>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <StringListPanel title="为什么值得继续看" items={decisionBrief.why_it_made_the_list} emptyText="当前没有额外的正向摘要。" />
                <StringListPanel title="为什么不能直接重仓" items={decisionBrief.why_not_all_in} emptyText="当前没有额外的风险摘要。" />
              </div>
            </div>
          ) : null,
        })}
      </SectionCard>

      <SectionCard
        title="看多证据 / 风险证据"
        description="这里只保留最关键、且能追溯到下层模块的证据。"
      >
        {renderModuleState({
          state: workspaceState.decisionBrief,
          loadingTitle: "正在整理证据层",
          loadingDescription: buildLoadingDescription(workspaceState.decisionBrief.startedAt, clock),
          emptyText: "当前没有拿到证据层摘要。",
          content: decisionBrief ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <BriefEvidencePanel title="看多证据" items={decisionBrief.key_evidence} emptyText="当前没有明确的正向证据。" />
              <BriefEvidencePanel title="风险证据" items={decisionBrief.key_risks} emptyText="当前没有明确的风险证据。" />
            </div>
          ) : null,
        })}
      </SectionCard>

      <SectionCard
        title="行动建议"
        description="把复杂输出翻译成下一步动作、关注价位和复核节奏。"
      >
        {renderModuleState({
          state: workspaceState.decisionBrief,
          loadingTitle: "正在整理行动层",
          loadingDescription: buildLoadingDescription(workspaceState.decisionBrief.startedAt, clock),
          emptyText: "当前没有拿到行动建议。",
          content: decisionBrief ? (
            <div className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <StringListPanel title="接下来怎么做" items={decisionBrief.what_to_do_next} emptyText="当前没有额外动作建议。" />
                <SourceModulePanel title="本简报引用的来源模块" items={decisionBrief.source_modules} />
              </div>
              <PriceLevelPanel items={decisionBrief.price_levels_to_watch} />
            </div>
          ) : null,
        })}
      </SectionCard>

      <SectionCard
        title="Factor Snapshot 摘要"
        description="展示 alpha / trigger / risk 三个核心分数，以及当前最强和最弱的因子组。"
      >
        {renderModuleState({
          state: workspaceState.factorSnapshot,
          loadingTitle: "正在计算 Factor Snapshot",
          loadingDescription: buildCalculationDescription(workspaceState.factorSnapshot.startedAt, clock, "当前会基于本地日线、公告和财务摘要即时计算。"),
          emptyText: "当前没有拿到因子快照。",
          content: workspaceState.factorSnapshot.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="交易日" value={formatDate(workspaceState.factorSnapshot.data.as_of_date)} />
                <Metric label="alpha 分" value={formatScore(workspaceState.factorSnapshot.data.alpha_score.total_score)} />
                <Metric label="trigger 分" value={formatScore(workspaceState.factorSnapshot.data.trigger_score.total_score)} />
                <Metric label="trigger 状态" value={formatLabel(workspaceState.factorSnapshot.data.trigger_score.trigger_state)} />
                <Metric label="risk 分" value={formatScore(workspaceState.factorSnapshot.data.risk_score.total_score)} />
                <Metric label="重新计算" value="每次刷新页面都会重算" />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <SignalGroupList
                  title="偏强因子组"
                  groups={workspaceState.factorSnapshot.data.factor_group_scores.filter((group) => (group.score ?? 0) >= 55)}
                  emptyText="当前没有明显偏强的因子组。"
                  signalKey="top_positive_signals"
                />
                <SignalGroupList
                  title="偏弱因子组"
                  groups={workspaceState.factorSnapshot.data.factor_group_scores.filter((group) => (group.score ?? 0) <= 45)}
                  emptyText="当前没有明显偏弱的因子组。"
                  signalKey="top_negative_signals"
                />
              </div>
            </div>
          ) : null,
        })}
      </SectionCard>

      <SectionCard
        title="Review Report v2"
        description="这是个股研判 v2 的结构化输出，Decision Brief 的很多结论都从这里往上提炼。"
      >
        {renderModuleState({
          state: workspaceState.reviewReport,
          loadingTitle: "正在生成 Review Report v2",
          loadingDescription: buildCalculationDescription(workspaceState.reviewReport.startedAt, clock, "当前会根据本地数据和已有规则即时生成研究结论。"),
          emptyText: "当前没有拿到 review-report。",
          content: workspaceState.reviewReport.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="最终动作" value={formatAction(workspaceState.reviewReport.data.final_judgement.action)} />
                <Metric label="置信度" value={formatScore(workspaceState.reviewReport.data.confidence)} />
                <Metric label="alpha 分" value={formatScore(workspaceState.reviewReport.data.factor_profile.alpha_score)} />
                <Metric label="trigger 分" value={formatScore(workspaceState.reviewReport.data.factor_profile.trigger_score)} />
                <Metric label="risk 分" value={formatScore(workspaceState.reviewReport.data.factor_profile.risk_score)} />
                <Metric label="复核窗口" value={formatLabel(workspaceState.reviewReport.data.strategy_summary.review_timeframe)} />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <TextPanel title="最终判断" content={workspaceState.reviewReport.data.final_judgement.summary} />
                <TextPanel title="技术视角" content={workspaceState.reviewReport.data.technical_view.tactical_read} />
                <TextPanel title="基本面视角" content={workspaceState.reviewReport.data.fundamental_view.data_completeness_note} />
                <TextPanel title="事件视角" content={workspaceState.reviewReport.data.event_view.concise_summary} />
                <StringListPanel title="多头理由" items={workspaceState.reviewReport.data.bull_case.reasons} emptyText="当前没有额外多头理由。" />
                <StringListPanel title="空头理由" items={workspaceState.reviewReport.data.bear_case.reasons} emptyText="当前没有额外空头理由。" />
              </div>
            </div>
          ) : null,
        })}
      </SectionCard>

      <SectionCard
        title="Debate Review"
        description="这里展示角色化裁决结果，可切换 rule-based 与 LLM 模式。"
      >
        {renderModuleState({
          state: workspaceState.debateReview,
          loadingTitle: useLlm ? "LLM debate-review 正在后台执行" : "正在生成规则版 Debate Review",
          loadingDescription: buildDebateLoadingDescription({
            progress: workspaceState.debateReview.progress,
            startedAt: workspaceState.debateReview.startedAt,
            clock,
            useLlm,
          }),
          emptyText: "当前没有拿到 debate-review。",
          content: workspaceState.debateReview.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="运行模式" value={workspaceState.debateReview.data.runtime_mode === "llm" ? "LLM" : "规则版"} />
                <Metric label="最终动作" value={formatAction(workspaceState.debateReview.data.final_action)} />
                <Metric label="置信度" value={formatScore(workspaceState.debateReview.data.confidence)} />
                <Metric label="风险等级" value={formatLabel(workspaceState.debateReview.data.risk_review.risk_level)} />
                <Metric label="策略类型" value={formatLabel(workspaceState.debateReview.data.strategy_summary.strategy_type)} />
                <Metric label="重新计算" value="每次刷新页面都会重算" />
              </div>
              <TextPanel title="首席裁决" content={workspaceState.debateReview.data.chief_judgement.summary} />
              <div className="grid gap-4 lg:grid-cols-2">
                <AnalystPanel title="技术分析员" summary={workspaceState.debateReview.data.analyst_views.technical.summary} positivePoints={workspaceState.debateReview.data.analyst_views.technical.positive_points} cautionPoints={workspaceState.debateReview.data.analyst_views.technical.caution_points} />
                <AnalystPanel title="基本面分析员" summary={workspaceState.debateReview.data.analyst_views.fundamental.summary} positivePoints={workspaceState.debateReview.data.analyst_views.fundamental.positive_points} cautionPoints={workspaceState.debateReview.data.analyst_views.fundamental.caution_points} />
                <AnalystPanel title="事件分析员" summary={workspaceState.debateReview.data.analyst_views.event.summary} positivePoints={workspaceState.debateReview.data.analyst_views.event.positive_points} cautionPoints={workspaceState.debateReview.data.analyst_views.event.caution_points} />
                <AnalystPanel title="情绪分析员" summary={workspaceState.debateReview.data.analyst_views.sentiment.summary} positivePoints={workspaceState.debateReview.data.analyst_views.sentiment.positive_points} cautionPoints={workspaceState.debateReview.data.analyst_views.sentiment.caution_points} />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <DebatePointPanel title="多头研究员" summary={workspaceState.debateReview.data.bull_case.summary} points={workspaceState.debateReview.data.bull_case.reasons} />
                <DebatePointPanel title="空头研究员" summary={workspaceState.debateReview.data.bear_case.summary} points={workspaceState.debateReview.data.bear_case.reasons} />
                <StringListPanel title="裁决关键点" items={workspaceState.debateReview.data.chief_judgement.decisive_points} emptyText="当前没有额外裁决关键点。" />
                <StringListPanel title="执行提醒" items={workspaceState.debateReview.data.risk_review.execution_reminders} emptyText="当前没有额外执行提醒。" />
              </div>
            </div>
          ) : null,
        })}
      </SectionCard>

      <SectionCard title="Strategy Plan" description="展示结构化交易策略，只保留执行需要的关键字段。">
        {renderModuleState({
          state: workspaceState.strategyPlan,
          loadingTitle: "正在生成 Strategy Plan",
          loadingDescription: buildCalculationDescription(workspaceState.strategyPlan.startedAt, clock, "当前会根据最新本地数据和研究结论即时生成策略。"),
          emptyText: "当前没有拿到 strategy plan。",
          content: workspaceState.strategyPlan.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="动作" value={formatAction(workspaceState.strategyPlan.data.action)} />
                <Metric label="策略类型" value={formatLabel(workspaceState.strategyPlan.data.strategy_type)} />
                <Metric label="入场窗口" value={formatLabel(workspaceState.strategyPlan.data.entry_window)} />
                <Metric label="理想入场区间" value={formatRange(workspaceState.strategyPlan.data.ideal_entry_range)} />
                <Metric label="止损价" value={formatPrice(workspaceState.strategyPlan.data.stop_loss_price)} />
                <Metric label="止盈区间" value={formatRange(workspaceState.strategyPlan.data.take_profit_range)} />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <StringListPanel title="入场触发" items={workspaceState.strategyPlan.data.entry_triggers} emptyText="当前没有入场触发条件。" />
                <StringListPanel title="避免条件" items={workspaceState.strategyPlan.data.avoid_if} emptyText="当前没有额外避免条件。" />
                <TextPanel title="止损规则" content={workspaceState.strategyPlan.data.stop_loss_rule} />
                <TextPanel title="止盈规则" content={workspaceState.strategyPlan.data.take_profit_rule} />
                <TextPanel title="持有规则" content={workspaceState.strategyPlan.data.hold_rule} />
                <TextPanel title="卖出规则" content={workspaceState.strategyPlan.data.sell_rule} />
              </div>
            </div>
          ) : null,
        })}
      </SectionCard>

      <SectionCard
        title="盘中 / Trigger Snapshot"
        description="如果当前 provider 可用，这里会给出轻量盘中触发摘要；若不可用，也会明确显示当前状态。"
      >
        {renderModuleState({
          state: workspaceState.triggerSnapshot,
          loadingTitle: "正在获取 Trigger Snapshot",
          loadingDescription: buildCalculationDescription(workspaceState.triggerSnapshot.startedAt, clock, "当前会优先尝试盘中 provider，必要时自动退回日线 fallback。"),
          emptyText: "当前没有拿到 trigger snapshot。",
          content: workspaceState.triggerSnapshot.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="快照时间" value={formatDateTime(workspaceState.triggerSnapshot.data.as_of_datetime)} />
                <Metric label="触发状态" value={formatLabel(workspaceState.triggerSnapshot.data.trigger_state)} />
                <Metric label="日线趋势" value={formatLabel(workspaceState.triggerSnapshot.data.daily_trend_state)} />
                <Metric label="最新价格" value={formatPrice(workspaceState.triggerSnapshot.data.latest_intraday_price)} />
                <Metric label="距支撑位" value={formatPercent(workspaceState.triggerSnapshot.data.distance_to_support_pct)} />
                <Metric label="距压力位" value={formatPercent(workspaceState.triggerSnapshot.data.distance_to_resistance_pct)} />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <TextPanel title="触发说明" content={workspaceState.triggerSnapshot.data.trigger_note} />
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-950">关键价位</p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <Metric label="支撑位" value={formatPrice(workspaceState.triggerSnapshot.data.daily_support_level)} />
                    <Metric label="压力位" value={formatPrice(workspaceState.triggerSnapshot.data.daily_resistance_level)} />
                  </div>
                </div>
              </div>
            </div>
          ) : null,
        })}
      </SectionCard>

      <SectionCard
        title="股票基础信息与数据状态"
        description="基础资料、时效性和本地优先读取策略放在这里，避免干扰最上层的结论判断。"
      >
        <div className="space-y-4">
          {renderModuleState({
            state: workspaceState.profile,
            loadingTitle: "正在加载股票基础信息",
            loadingDescription: buildLoadingDescription(workspaceState.profile.startedAt, clock),
            emptyText: "当前没有拿到股票基础信息。",
            content: profile ? (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <Metric label="行业" value={profile.industry ?? "-"} />
                  <Metric label="上市日期" value={formatDate(profile.list_date)} />
                  <Metric label="状态" value={profile.status ?? "-"} />
                  <Metric label="总市值" value={formatLargeNumber(profile.total_market_cap)} />
                  <Metric label="流通市值" value={formatLargeNumber(profile.circulating_market_cap)} />
                  <Metric label="数据源" value={profile.source} />
                </div>
                {hasProfileGaps ? (
                  <StatusBlock
                    title="基础资料仍有缺口"
                    description="当前基础记录还不完整，系统会继续遵循“本地优先、缺失再补远端并落本地”的策略。其他分析模块仍可继续查看。"
                    tone="error"
                  />
                ) : null}
              </div>
            ) : null,
          })}

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="分析基准日" value={formatDate(analysisAsOfDate)} />
            <Metric label="Trigger 快照时间" value={formatDateTime(triggerAsOfDateTime)} />
            <Metric label="重新计算时机" value="每次打开页面或点击刷新时" />
            <Metric label="结果有效期" value={analysisAsOfDate ? "直到本地底层数据更新或你再次刷新页面前" : "等待模块返回后显示"} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <TextPanel title="本地优先的数据" content="股票基础资料、日线、公告、财务摘要都遵循“本地优先”。本地已有就直接读取；本地缺失或资料不完整时，再请求外部 provider，并把结果落到本地。" />
            <TextPanel title="即时计算的数据" content="Factor Snapshot、Review Report、Debate Review、Strategy Plan 都是在接口调用时基于当前本地数据即时计算，不单独做长期缓存。页面每次刷新都会重新计算。" />
            <TextPanel title="盘中数据说明" content="Trigger Snapshot 优先尝试盘中 provider；若盘中数据不可用，会自动退回日线 fallback。当前更偏向实时读取，不作为长期盘中缓存。" />
            <TextPanel title="推荐查看顺序" content="先看 Decision Brief 判断结论，再看证据层确认依据，最后下沉到 review / debate / strategy / factor / trigger 这些详细模块。" />
          </div>
        </div>
      </SectionCard>

      <SingleStockWorkflowPanel symbol={symbol} />
    </div>
  );
}

function renderModuleState({
  state,
  loadingTitle,
  loadingDescription,
  emptyText,
  content,
}: {
  state: ModuleState<unknown>;
  loadingTitle: string;
  loadingDescription: string;
  emptyText: string;
  content: ReactNode;
}) {
  if (state.status === "loading") {
    return <LoadingPanel state={state} title={loadingTitle} description={loadingDescription} />;
  }
  if (state.status === "error") {
    return <StatusBlock title="加载失败" description={state.error ?? "发生未知错误，请稍后重试。"} tone="error" />;
  }
  if (state.status !== "success" || !state.data) {
    return <StatusBlock title="暂无结果" description={emptyText} />;
  }
  return <>{content}</>;
}

function LoadingPanel({
  state,
  title,
  description,
}: {
  state: ModuleState<unknown>;
  title: string;
  description: string;
}) {
  const progress = state.progress;
  const progressRatio =
    progress && progress.total_steps > 0
      ? Math.max(8, Math.min(100, Math.round((progress.completed_steps / progress.total_steps) * 100)))
      : 18;

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="space-y-1">
        <p className="text-sm font-semibold text-slate-950">{title}</p>
        <p className="text-sm leading-6 text-slate-700">{description}</p>
      </div>
      {progress ? (
        <div className="space-y-3">
          <div className="h-2 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full rounded-full bg-emerald-600 transition-[width] duration-500" style={{ width: `${progressRatio}%` }} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Metric label="后台阶段" value={progress.current_step ?? formatLabel(progress.stage)} />
            <Metric label="步骤进度" value={progress.total_steps > 0 ? `${progress.completed_steps} / ${progress.total_steps}` : "等待后台返回"} />
          </div>
          <p className="text-sm leading-6 text-slate-700">{progress.message}</p>
          {progress.error_message ? <StatusBlock title="后台提示" description={progress.error_message} tone="error" /> : null}
          {progress.recent_steps.length > 0 ? <StringListPanel title="最近步骤" items={progress.recent_steps} emptyText="当前没有最近步骤。" /> : null}
        </div>
      ) : null}
    </div>
  );
}

function BriefEvidencePanel({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: DecisionBriefEvidence[];
  emptyText: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">{emptyText}</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {items.map((item) => (
            <li key={`${item.source_module}-${item.title}-${item.detail}`} className="rounded-2xl bg-white p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600">
                  {formatLabel(item.source_module)}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-700">{item.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PriceLevelPanel({ items }: { items: DecisionPriceLevel[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">重点价位</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">当前没有额外价位提示。</p>
      ) : (
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <div key={`${item.label}-${item.value_text}`} className="rounded-2xl bg-white p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{item.label}</p>
              <p className="mt-2 text-sm font-semibold text-slate-950">{item.value_text}</p>
              {item.note ? <p className="mt-2 text-sm leading-6 text-slate-600">{item.note}</p> : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SourceModulePanel({ title, items }: { title: string; items: DecisionSourceModule[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">当前没有来源模块说明。</p>
      ) : (
        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          {items.map((item) => (
            <li key={`${item.module_name}-${item.as_of ?? "na"}`} className="rounded-2xl bg-white px-3 py-2">
              <span className="font-medium text-slate-900">{formatLabel(item.module_name)}</span>
              {item.as_of ? ` · ${item.as_of}` : ""}
              {item.note ? ` · ${item.note}` : ""}
            </li>
          ))}
        </ul>
      )}
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
              <p className="text-sm font-semibold text-slate-900">{group.group_name}</p>
              <p className="mt-1 text-xs text-slate-500">组分数：{formatScore(group.score)}</p>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                {group[signalKey].length === 0 ? <li>当前没有额外信号。</li> : group[signalKey].slice(0, 3).map((signal) => <li key={signal}>{signal}</li>)}
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
        <DebatePointList title="支持点" points={positivePoints} emptyText="当前没有额外支持点。" />
        <DebatePointList title="谨慎点" points={cautionPoints} emptyText="当前没有额外谨慎点。" />
      </div>
    </div>
  );
}

function DebatePointPanel({ title, summary, points }: { title: string; summary: string; points: DebatePoint[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-3 text-sm leading-6 text-slate-700">{summary}</p>
      <DebatePointList title="核心要点" points={points} emptyText="当前没有额外核心要点。" className="mt-4" />
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

function StringListPanel({ title, items, emptyText }: { title: string; items: string[]; emptyText: string }) {
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function buildLoadingDescription(startedAt: number | null, clock: number): string {
  return `请求已发出${formatWaitTime(startedAt, clock)}。模块会独立返回，你可以先查看其他已完成内容。`;
}

function buildCalculationDescription(startedAt: number | null, clock: number, tail: string): string {
  return `请求已发出${formatWaitTime(startedAt, clock)}。${tail}`;
}

function buildDebateLoadingDescription({
  progress,
  startedAt,
  clock,
  useLlm,
}: {
  progress: DebateReviewProgress | null;
  startedAt: number | null;
  clock: number;
  useLlm: boolean;
}) {
  const waitText = `请求已发出${formatWaitTime(startedAt, clock)}。`;
  if (!useLlm) return `${waitText}当前使用规则版裁决，通常会在本地较快完成。`;
  if (!progress) return `${waitText}正在等待后台返回 LLM 裁决进度。`;
  return `${waitText}${progress.message}`;
}

function formatWaitTime(startedAt: number | null, clock: number): string {
  if (!startedAt) return "，正在等待后台响应";
  const seconds = Math.max(1, Math.floor((clock - startedAt) / 1000));
  return `，已等待 ${seconds} 秒`;
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "发生未知错误，请稍后重试。";
}

function buildDebateRequestId(symbol: string): string {
  const randomPart =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Math.random().toString(16).slice(2)}-${Date.now().toString(16)}`;
  return `${normalizeSymbolInput(symbol)}-${randomPart}`;
}

function formatLargeNumber(value: number | null): string {
  if (value === null) return "-";
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)} 亿`;
  return formatPrice(value);
}
