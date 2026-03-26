import type {
  DataRefreshStatus,
  DbQueryResponse,
  DbTablesResponse,
  DebateReviewProgress,
  DebateReviewReport,
  DeepReviewWorkflowRunRequest,
  DeepScreenerRunResponse,
  FactorSnapshot,
  ResearchReport,
  ScreenerRunResponse,
  SingleStockWorkflowRunRequest,
  StockProfile,
  StockReviewReport,
  StrategyPlan,
  TriggerSnapshot,
  WorkflowRunDetailResponse,
  WorkflowRunResponse,
} from "@/types/api";

const API_PREFIX = "/api/backend";
const STOCK_PAGE_TIMEOUT_MS = 90_000;
const DEBATE_REVIEW_TIMEOUT_MS = 240_000;
const DATA_REFRESH_TIMEOUT_MS = 30_000;
const MIN_SCREENER_TIMEOUT_MS = 120_000;
const MAX_SCREENER_TIMEOUT_MS = 1_800_000;
const MIN_DEEP_SCREENER_TIMEOUT_MS = 180_000;
const MAX_DEEP_SCREENER_TIMEOUT_MS = 2_700_000;
const MIN_WORKFLOW_TIMEOUT_MS = 90_000;
const MAX_WORKFLOW_TIMEOUT_MS = 3_600_000;
const SCREENER_TIMEOUT_PER_SYMBOL_MS = 250;
const DEEP_SCREENER_TIMEOUT_PER_SYMBOL_MS = 350;
const WORKFLOW_TIMEOUT_PER_SYMBOL_MS = 500;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type QueryValue = string | number | boolean | undefined;

type ScreenerParams = {
  maxSymbols?: number;
  topN?: number;
};

type DeepScreenerParams = ScreenerParams & {
  deepTopK?: number;
};

type DataRefreshParams = {
  maxSymbols?: number;
};

type DebateReviewParams = {
  useLlm?: boolean;
  requestId?: string;
};

type FetchOptions = {
  timeoutMs: number;
  method?: "GET" | "POST";
  body?: unknown;
};

export function normalizeSymbolInput(value: string): string {
  return value.trim().toUpperCase();
}

export async function getScreenerRun(
  params: ScreenerParams,
): Promise<ScreenerRunResponse> {
  return fetchBackend<ScreenerRunResponse>(
    buildPath("/screener/run", {
      max_symbols: params.maxSymbols,
      top_n: params.topN,
    }),
    {
      timeoutMs: resolveScreenerTimeoutMs(params.maxSymbols),
    },
  );
}

export async function getDeepScreenerRun(
  params: DeepScreenerParams,
): Promise<DeepScreenerRunResponse> {
  return fetchBackend<DeepScreenerRunResponse>(
    buildPath("/screener/deep-run", {
      max_symbols: params.maxSymbols,
      top_n: params.topN,
      deep_top_k: params.deepTopK,
    }),
    {
      timeoutMs: resolveDeepScreenerTimeoutMs(params.maxSymbols),
    },
  );
}

export async function getStockProfile(symbol: string): Promise<StockProfile> {
  return fetchBackend<StockProfile>(
    `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/profile`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getFactorSnapshot(symbol: string): Promise<FactorSnapshot> {
  return fetchBackend<FactorSnapshot>(
    `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/factor-snapshot`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getStockReviewReport(
  symbol: string,
): Promise<StockReviewReport> {
  return fetchBackend<StockReviewReport>(
    `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/review-report`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getDebateReview(
  symbol: string,
  params: DebateReviewParams = {},
): Promise<DebateReviewReport> {
  return fetchBackend<DebateReviewReport>(
    buildPath(
      `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/debate-review`,
      {
        use_llm: params.useLlm,
        request_id: params.requestId,
      },
    ),
    { timeoutMs: DEBATE_REVIEW_TIMEOUT_MS },
  );
}

export async function getDebateReviewProgress(
  symbol: string,
  params: DebateReviewParams = {},
): Promise<DebateReviewProgress> {
  return fetchBackend<DebateReviewProgress>(
    buildPath(
      `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/debate-review-progress`,
      {
        use_llm: params.useLlm,
        request_id: params.requestId,
      },
    ),
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getTriggerSnapshot(
  symbol: string,
): Promise<TriggerSnapshot> {
  return fetchBackend<TriggerSnapshot>(
    `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/trigger-snapshot`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getResearchReport(symbol: string): Promise<ResearchReport> {
  return fetchBackend<ResearchReport>(
    `/research/${encodeURIComponent(normalizeSymbolInput(symbol))}`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getStrategyPlan(symbol: string): Promise<StrategyPlan> {
  return fetchBackend<StrategyPlan>(
    `/strategy/${encodeURIComponent(normalizeSymbolInput(symbol))}`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function runSingleStockWorkflow(
  payload: SingleStockWorkflowRunRequest,
): Promise<WorkflowRunResponse> {
  return fetchBackend<WorkflowRunResponse>("/workflows/single-stock/run", {
    timeoutMs: resolveSingleStockWorkflowTimeoutMs(),
    method: "POST",
    body: payload,
  });
}

export async function runDeepReviewWorkflow(
  payload: DeepReviewWorkflowRunRequest,
): Promise<WorkflowRunResponse> {
  return fetchBackend<WorkflowRunResponse>("/workflows/deep-review/run", {
    timeoutMs: resolveDeepWorkflowTimeoutMs(payload.max_symbols),
    method: "POST",
    body: payload,
  });
}

export async function getWorkflowRunDetail(
  runId: string,
): Promise<WorkflowRunDetailResponse> {
  return fetchBackend<WorkflowRunDetailResponse>(
    `/workflows/runs/${encodeURIComponent(runId)}`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getDataRefreshStatus(): Promise<DataRefreshStatus> {
  return fetchBackend<DataRefreshStatus>("/data/refresh", {
    timeoutMs: DATA_REFRESH_TIMEOUT_MS,
  });
}

export async function startDataRefresh(
  params: DataRefreshParams,
): Promise<DataRefreshStatus> {
  return fetchBackend<DataRefreshStatus>("/data/refresh", {
    timeoutMs: DATA_REFRESH_TIMEOUT_MS,
    method: "POST",
    body: {
      max_symbols: params.maxSymbols,
    },
  });
}

export async function getDbTables(): Promise<DbTablesResponse> {
  return fetchBackend<DbTablesResponse>("/admin/db/tables", {
    timeoutMs: DATA_REFRESH_TIMEOUT_MS,
  });
}

export async function runDbQuery(
  sql: string,
  limit = 200,
): Promise<DbQueryResponse> {
  return fetchBackend<DbQueryResponse>("/admin/db/query", {
    timeoutMs: DATA_REFRESH_TIMEOUT_MS,
    method: "POST",
    body: {
      sql,
      limit,
    },
  });
}

async function fetchBackend<T>(
  path: string,
  options: FetchOptions,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeoutMs);
  const method = options.method ?? "GET";

  try {
    const response = await fetch(`${API_PREFIX}${path}`, {
      method,
      cache: "no-store",
      headers: buildHeaders(method),
      body: method === "POST" ? JSON.stringify(options.body ?? {}) : undefined,
      signal: controller.signal,
    });

    if (!response.ok) {
      const message = await parseErrorMessage(response);
      throw new ApiError(message, response.status);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求超时，请稍后重试。", 408);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function buildHeaders(method: "GET" | "POST"): HeadersInit {
  if (method === "POST") {
    return {
      Accept: "application/json",
      "Content-Type": "application/json",
    };
  }

  return {
    Accept: "application/json",
  };
}

function buildPath(path: string, query: Record<string, QueryValue>): string {
  const searchParams = new URLSearchParams();

  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === "") {
      return;
    }
    searchParams.set(key, String(value));
  });

  const queryString = searchParams.toString();
  return queryString ? `${path}?${queryString}` : path;
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string;
      message?: string;
    };

    if (typeof payload.detail === "string" && payload.detail.length > 0) {
      return payload.detail;
    }
    if (typeof payload.message === "string" && payload.message.length > 0) {
      return payload.message;
    }
  } catch {
    return `请求失败（${response.status}）`;
  }

  return `请求失败（${response.status}）`;
}

function resolveScreenerTimeoutMs(maxSymbols?: number): number {
  if (maxSymbols === undefined) {
    return MIN_SCREENER_TIMEOUT_MS;
  }

  return clampTimeout(
    MIN_SCREENER_TIMEOUT_MS + maxSymbols * SCREENER_TIMEOUT_PER_SYMBOL_MS,
    MAX_SCREENER_TIMEOUT_MS,
  );
}

function resolveDeepScreenerTimeoutMs(maxSymbols?: number): number {
  if (maxSymbols === undefined) {
    return MIN_DEEP_SCREENER_TIMEOUT_MS;
  }

  return clampTimeout(
    MIN_DEEP_SCREENER_TIMEOUT_MS + maxSymbols * DEEP_SCREENER_TIMEOUT_PER_SYMBOL_MS,
    MAX_DEEP_SCREENER_TIMEOUT_MS,
  );
}

function resolveSingleStockWorkflowTimeoutMs(): number {
  return MIN_WORKFLOW_TIMEOUT_MS;
}

function resolveDeepWorkflowTimeoutMs(maxSymbols?: number): number {
  if (maxSymbols === undefined) {
    return 240_000;
  }

  return clampTimeout(
    240_000 + maxSymbols * WORKFLOW_TIMEOUT_PER_SYMBOL_MS,
    MAX_WORKFLOW_TIMEOUT_MS,
  );
}

function clampTimeout(timeoutMs: number, maxTimeoutMs: number): number {
  return Math.min(Math.max(timeoutMs, STOCK_PAGE_TIMEOUT_MS), maxTimeoutMs);
}
