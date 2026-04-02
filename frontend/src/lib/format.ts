import type {
  DecisionBriefActionNow,
  DecisionConvictionLevel,
  DidFollowPlan,
  PriceRange,
  ResearchAction,
  ReviewOutcomeLabel,
  ScreenerListType,
  StrategyAlignment,
  TradeReasonType,
  TradeSide,
  ModelVersionRecommendation,
  WorkflowStepStatus,
} from "@/types/api";

const priceFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const percentFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const LIST_TYPE_LABELS: Record<ScreenerListType, string> = {
  READY_TO_BUY: "可直接关注买点",
  WATCH_PULLBACK: "等待回踩",
  WATCH_BREAKOUT: "等待突破",
  RESEARCH_ONLY: "仅研究跟踪",
  AVOID: "回避",
};

const ACTION_LABELS: Record<ResearchAction, string> = {
  BUY: "买入",
  WATCH: "观察",
  AVOID: "回避",
};

const DECISION_BRIEF_ACTION_LABELS: Record<DecisionBriefActionNow, string> = {
  BUY_NOW: "现在可执行",
  WAIT_PULLBACK: "等待回踩",
  WAIT_BREAKOUT: "等待突破",
  RESEARCH_ONLY: "继续研究",
  AVOID: "先回避",
};

const CONVICTION_LEVEL_LABELS: Record<DecisionConvictionLevel, string> = {
  low: "低",
  medium: "中",
  high: "高",
};

const STEP_STATUS_LABELS: Record<WorkflowStepStatus, string> = {
  pending: "待执行",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  skipped: "已跳过",
};

const TRADE_SIDE_LABELS: Record<TradeSide, string> = {
  BUY: "买入",
  SELL: "卖出",
  ADD: "加仓",
  REDUCE: "减仓",
  SKIP: "跳过",
};

const TRADE_REASON_TYPE_LABELS: Record<TradeReasonType, string> = {
  signal_entry: "信号入场",
  pullback_entry: "回踩入场",
  breakout_entry: "突破入场",
  stop_loss: "止损退出",
  take_profit: "止盈退出",
  time_exit: "时间退出",
  manual_override: "人工覆盖",
  watch_only: "仅观察",
  skip_due_to_quality: "因数据质量跳过",
  skip_due_to_risk: "因风险跳过",
};

const STRATEGY_ALIGNMENT_LABELS: Record<StrategyAlignment, string> = {
  aligned: "一致",
  partially_aligned: "部分一致",
  not_aligned: "不一致",
  unknown: "未知",
};

const REVIEW_OUTCOME_LABELS: Record<ReviewOutcomeLabel, string> = {
  success: "成功",
  partial_success: "部分成功",
  failure: "失败",
  invalidated: "失效",
  no_trade: "未交易",
};

const DID_FOLLOW_PLAN_LABELS: Record<DidFollowPlan, string> = {
  yes: "是",
  partial: "部分",
  no: "否",
};

const GENERIC_LABELS: Record<string, string> = {
  idle: "空闲",
  loading: "加载中",
  success: "成功",
  error: "错误",
  pending: "待执行",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  llm: "LLM",
  rule_based: "规则版",
  fallback_rule_based: "规则回退",
  cache_hit: "命中本地缓存",
  ok: "正常",
  warning: "告警",
  degraded: "降级",
};

const MODEL_RECOMMENDATION_LABELS: Record<
  ModelVersionRecommendation["recommendation"],
  string
> = {
  promote_candidate: "可升级为默认版本",
  keep_baseline: "继续使用基线版本",
  observe: "继续观察",
};

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("zh-CN", {
    hour12: false,
  });
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return priceFormatter.format(value);
}

export function formatRange(range: PriceRange | null | undefined): string {
  if (!range) {
    return "-";
  }
  return `${formatPrice(range.low)} - ${formatPrice(range.high)}`;
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value} / 100`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${percentFormatter.format(value)}%`;
}

export function formatRatioPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${percentFormatter.format(value * 100)}%`;
}

export function formatLabel(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  if (GENERIC_LABELS[value]) {
    return GENERIC_LABELS[value];
  }
  return value.replace(/_/g, " ");
}

export function formatAction(value: ResearchAction): string {
  return ACTION_LABELS[value];
}

export function formatDecisionBriefAction(value: DecisionBriefActionNow): string {
  return DECISION_BRIEF_ACTION_LABELS[value];
}

export function formatConvictionLevel(value: DecisionConvictionLevel): string {
  return CONVICTION_LEVEL_LABELS[value];
}

export function formatListType(value: ScreenerListType): string {
  return LIST_TYPE_LABELS[value];
}

export function formatWorkflowStepStatus(value: WorkflowStepStatus): string {
  return STEP_STATUS_LABELS[value];
}

export function formatTradeSide(value: TradeSide): string {
  return TRADE_SIDE_LABELS[value];
}

export function formatTradeReasonType(value: TradeReasonType): string {
  return TRADE_REASON_TYPE_LABELS[value];
}

export function formatStrategyAlignment(value: StrategyAlignment): string {
  return STRATEGY_ALIGNMENT_LABELS[value];
}

export function formatReviewOutcome(value: ReviewOutcomeLabel): string {
  return REVIEW_OUTCOME_LABELS[value];
}

export function formatDidFollowPlan(value: DidFollowPlan): string {
  return DID_FOLLOW_PLAN_LABELS[value];
}

export function formatPredictiveScoreLevel(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (value >= 80) return "高强度信号";
  if (value >= 65) return "中等偏强";
  if (value >= 50) return "中性观察";
  return "偏弱信号";
}

export function formatPredictiveConfidenceLevel(
  value: number | null | undefined,
): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (value >= 0.8) return "高";
  if (value >= 0.65) return "中";
  return "低";
}

export function formatModelRecommendation(
  value: ModelVersionRecommendation["recommendation"] | null | undefined,
): string {
  if (!value) {
    return "-";
  }
  return MODEL_RECOMMENDATION_LABELS[value] ?? value;
}

export function formatUnknownValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? "-" : value.map((item) => formatUnknownValue(item)).join(" / ");
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
