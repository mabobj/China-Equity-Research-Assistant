import type {
  DeepScreenerRunResponse,
  ResearchReport,
  ScreenerRunResponse,
  StrategyPlan,
} from "@/types/api";

const API_PREFIX = "/api/backend";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type QueryValue = string | number | undefined;

type ScreenerParams = {
  maxSymbols?: number;
  topN?: number;
};

type DeepScreenerParams = ScreenerParams & {
  deepTopK?: number;
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
  );
}

export async function getResearchReport(symbol: string): Promise<ResearchReport> {
  return fetchBackend<ResearchReport>(
    `/research/${encodeURIComponent(normalizeSymbolInput(symbol))}`,
  );
}

export async function getStrategyPlan(symbol: string): Promise<StrategyPlan> {
  return fetchBackend<StrategyPlan>(
    `/strategy/${encodeURIComponent(normalizeSymbolInput(symbol))}`,
  );
}

async function fetchBackend<T>(path: string): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
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
  if (!queryString) {
    return path;
  }
  return `${path}?${queryString}`;
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
