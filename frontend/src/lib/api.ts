import type {
  DataRefreshStatus,
  CreateDecisionSnapshotRequest,
  CreateReviewFromTradeRequest,
  CreateReviewRequest,
  CreateTradeFromCurrentDecisionRequest,
  CreateTradeRequest,
  DbQueryResponse,
  DbTablesResponse,
  DecisionBrief,
  DecisionSnapshot,
  DecisionSnapshotListResponse,
  DebateReviewProgress,
  DebateReviewReport,
  DeepReviewWorkflowRunRequest,
  DeepScreenerRunResponse,
  FactorSnapshot,
  ResearchReport,
  ReviewListResponse,
  ReviewRecord,
  ScreenerRunResponse,
  ScreenerBatchDetailResponse,
  ScreenerBatchResultsResponse,
  ScreenerCursorResetResponse,
  ScreenerLatestBatchResponse,
  ScreenerSymbolResultResponse,
  ScreenerWorkflowRunRequest,
  SingleStockWorkflowRunRequest,
  StockProfile,
  StockReviewReport,
  StrategyPlan,
  TradeListResponse,
  TradeRecord,
  TriggerSnapshot,
  UpdateReviewRequest,
  UpdateTradeRequest,
  ModelEvaluationResponse,
  WorkspaceBundleResponse,
  WorkflowRunDetailResponse,
  WorkflowRunResponse,
} from "@/types/api";

const API_PREFIX = "/api/backend";
const STOCK_PAGE_TIMEOUT_MS = 90_000;
const DEBATE_REVIEW_TIMEOUT_MS = 240_000;
const MODEL_EVALUATION_TIMEOUT_MS = 300_000;
const DATA_REFRESH_TIMEOUT_MS = 30_000;
const MIN_SCREENER_TIMEOUT_MS = 120_000;
const MAX_SCREENER_TIMEOUT_MS = 1_800_000;
const MIN_DEEP_SCREENER_TIMEOUT_MS = 180_000;
const MAX_DEEP_SCREENER_TIMEOUT_MS = 2_700_000;
const MIN_WORKFLOW_TIMEOUT_MS = 90_000;
const SCREENER_TIMEOUT_PER_SYMBOL_MS = 250;
const DEEP_SCREENER_TIMEOUT_PER_SYMBOL_MS = 350;

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

type WorkspaceBundleParams = DebateReviewParams & {
  forceRefresh?: boolean;
};

type FetchOptions = {
  timeoutMs: number;
  method?: "GET" | "POST" | "PATCH";
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

export async function getLatestScreenerBatch(): Promise<ScreenerLatestBatchResponse> {
  return fetchBackend<ScreenerLatestBatchResponse>("/screener/latest-batch", {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
  });
}

export async function getActiveScreenerRun(): Promise<WorkflowRunDetailResponse | null> {
  return fetchBackend<WorkflowRunDetailResponse | null>("/screener/active-run", {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
  });
}

export async function resetScreenerCursor(): Promise<ScreenerCursorResetResponse> {
  return fetchBackend<ScreenerCursorResetResponse>("/screener/cursor/reset", {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "POST",
    body: {},
  });
}

export async function getScreenerBatchDetail(
  batchId: string,
): Promise<ScreenerBatchDetailResponse> {
  return fetchBackend<ScreenerBatchDetailResponse>(
    `/screener/batches/${encodeURIComponent(batchId)}`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getScreenerBatchResults(
  batchId: string,
): Promise<ScreenerBatchResultsResponse> {
  return fetchBackend<ScreenerBatchResultsResponse>(
    `/screener/batches/${encodeURIComponent(batchId)}/results`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getScreenerBatchSymbolResult(
  batchId: string,
  symbol: string,
): Promise<ScreenerSymbolResultResponse> {
  return fetchBackend<ScreenerSymbolResultResponse>(
    `/screener/batches/${encodeURIComponent(batchId)}/results/${encodeURIComponent(
      normalizeSymbolInput(symbol),
    )}`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getStockProfile(symbol: string): Promise<StockProfile> {
  return fetchBackend<StockProfile>(
    `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/profile`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getWorkspaceBundle(
  symbol: string,
  params: WorkspaceBundleParams = {},
): Promise<WorkspaceBundleResponse> {
  return fetchBackend<WorkspaceBundleResponse>(
    buildPath(
      `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/workspace-bundle`,
      {
        use_llm: params.useLlm,
        request_id: params.requestId,
        force_refresh: params.forceRefresh,
      },
    ),
    { timeoutMs: DEBATE_REVIEW_TIMEOUT_MS },
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

export async function getDecisionBrief(
  symbol: string,
  params: DebateReviewParams = {},
): Promise<DecisionBrief> {
  return fetchBackend<DecisionBrief>(
    buildPath(
      `/stocks/${encodeURIComponent(normalizeSymbolInput(symbol))}/decision-brief`,
      {
        use_llm: params.useLlm,
      },
    ),
    { timeoutMs: DEBATE_REVIEW_TIMEOUT_MS },
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

export async function getModelEvaluation(
  modelVersion: string,
): Promise<ModelEvaluationResponse> {
  return fetchBackend<ModelEvaluationResponse>(
    `/evaluations/models/${encodeURIComponent(modelVersion)}`,
    { timeoutMs: MODEL_EVALUATION_TIMEOUT_MS },
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
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "POST",
    body: payload,
  });
}

export async function runScreenerWorkflow(
  payload: ScreenerWorkflowRunRequest,
): Promise<WorkflowRunResponse> {
  return fetchBackend<WorkflowRunResponse>("/workflows/screener/run", {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
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

export async function createDecisionSnapshot(
  payload: CreateDecisionSnapshotRequest,
): Promise<DecisionSnapshot> {
  return fetchBackend<DecisionSnapshot>("/decision-snapshots", {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "POST",
    body: payload,
  });
}

export async function getDecisionSnapshot(
  snapshotId: string,
): Promise<DecisionSnapshot> {
  return fetchBackend<DecisionSnapshot>(
    `/decision-snapshots/${encodeURIComponent(snapshotId)}`,
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function listDecisionSnapshots(
  params: {
    symbol?: string;
    limit?: number;
  } = {},
): Promise<DecisionSnapshotListResponse> {
  return fetchBackend<DecisionSnapshotListResponse>(
    buildPath("/decision-snapshots", {
      symbol: params.symbol ? normalizeSymbolInput(params.symbol) : undefined,
      limit: params.limit,
    }),
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function createTrade(payload: CreateTradeRequest): Promise<TradeRecord> {
  return fetchBackend<TradeRecord>("/trades", {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "POST",
    body: payload,
  });
}

export async function createTradeFromCurrentDecision(
  payload: CreateTradeFromCurrentDecisionRequest,
): Promise<TradeRecord> {
  return fetchBackend<TradeRecord>("/trades/from-current-decision", {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "POST",
    body: payload,
  });
}

export async function listTrades(
  params: {
    symbol?: string;
    side?: string;
    from?: string;
    to?: string;
    limit?: number;
  } = {},
): Promise<TradeListResponse> {
  return fetchBackend<TradeListResponse>(
    buildPath("/trades", {
      symbol: params.symbol ? normalizeSymbolInput(params.symbol) : undefined,
      side: params.side,
      from: params.from,
      to: params.to,
      limit: params.limit,
    }),
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getTrade(tradeId: string): Promise<TradeRecord> {
  return fetchBackend<TradeRecord>(`/trades/${encodeURIComponent(tradeId)}`, {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
  });
}

export async function updateTrade(
  tradeId: string,
  payload: UpdateTradeRequest,
): Promise<TradeRecord> {
  return fetchBackend<TradeRecord>(`/trades/${encodeURIComponent(tradeId)}`, {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "PATCH",
    body: payload,
  });
}

export async function createReview(payload: CreateReviewRequest): Promise<ReviewRecord> {
  return fetchBackend<ReviewRecord>("/reviews", {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "POST",
    body: payload,
  });
}

export async function createReviewFromTrade(
  tradeId: string,
  payload: CreateReviewFromTradeRequest,
): Promise<ReviewRecord> {
  return fetchBackend<ReviewRecord>(`/reviews/from-trade/${encodeURIComponent(tradeId)}`, {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "POST",
    body: payload,
  });
}

export async function listReviews(
  params: {
    symbol?: string;
    outcomeLabel?: string;
    limit?: number;
  } = {},
): Promise<ReviewListResponse> {
  return fetchBackend<ReviewListResponse>(
    buildPath("/reviews", {
      symbol: params.symbol ? normalizeSymbolInput(params.symbol) : undefined,
      outcome_label: params.outcomeLabel,
      limit: params.limit,
    }),
    { timeoutMs: STOCK_PAGE_TIMEOUT_MS },
  );
}

export async function getReview(reviewId: string): Promise<ReviewRecord> {
  return fetchBackend<ReviewRecord>(`/reviews/${encodeURIComponent(reviewId)}`, {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
  });
}

export async function updateReview(
  reviewId: string,
  payload: UpdateReviewRequest,
): Promise<ReviewRecord> {
  return fetchBackend<ReviewRecord>(`/reviews/${encodeURIComponent(reviewId)}`, {
    timeoutMs: STOCK_PAGE_TIMEOUT_MS,
    method: "PATCH",
    body: payload,
  });
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
      body: method === "GET" ? undefined : JSON.stringify(options.body ?? {}),
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

function buildHeaders(method: "GET" | "POST" | "PATCH"): HeadersInit {
  if (method === "POST" || method === "PATCH") {
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

function clampTimeout(timeoutMs: number, maxTimeoutMs: number): number {
  return Math.min(Math.max(timeoutMs, STOCK_PAGE_TIMEOUT_MS), maxTimeoutMs);
}
