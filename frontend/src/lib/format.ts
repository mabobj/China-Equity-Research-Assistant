import type {
  PriceRange,
  ResearchAction,
  ScreenerListType,
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

const STEP_STATUS_LABELS: Record<WorkflowStepStatus, string> = {
  pending: "待执行",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  skipped: "已跳过",
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

export function formatLabel(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return value.replace(/_/g, " ");
}

export function formatAction(value: ResearchAction): string {
  return ACTION_LABELS[value];
}

export function formatListType(value: ScreenerListType): string {
  return LIST_TYPE_LABELS[value];
}

export function formatWorkflowStepStatus(value: WorkflowStepStatus): string {
  return STEP_STATUS_LABELS[value];
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
