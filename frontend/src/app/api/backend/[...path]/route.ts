import { NextRequest, NextResponse } from "next/server";

const DEFAULT_BACKEND_API_BASE_URL = "http://127.0.0.1:8000";
const STOCK_PAGE_TIMEOUT_MS = 90_000;
const DEBATE_REVIEW_TIMEOUT_MS = 240_000;
const MODEL_EVALUATION_TIMEOUT_MS = 300_000;
const DATA_REFRESH_TIMEOUT_MS = 30_000;
const MIN_SCREENER_TIMEOUT_MS = 120_000;
const MAX_SCREENER_TIMEOUT_MS = 1_800_000;
const MIN_DEEP_SCREENER_TIMEOUT_MS = 180_000;
const MAX_DEEP_SCREENER_TIMEOUT_MS = 2_700_000;
const SINGLE_STOCK_WORKFLOW_TIMEOUT_MS = 90_000;
const MIN_DEEP_WORKFLOW_TIMEOUT_MS = 240_000;
const MAX_DEEP_WORKFLOW_TIMEOUT_MS = 3_600_000;
const SCREENER_TIMEOUT_PER_SYMBOL_MS = 250;
const DEEP_SCREENER_TIMEOUT_PER_SYMBOL_MS = 350;
const WORKFLOW_TIMEOUT_PER_SYMBOL_MS = 500;

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, context, "GET");
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, context, "POST");
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, context, "PATCH");
}

async function proxyRequest(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
  method: "GET" | "POST" | "PATCH",
) {
  const { path } = await context.params;
  const targetUrl = buildTargetUrl(request, path);
  const requestBodyText = method === "GET" ? undefined : await request.text();
  const timeoutMs = getProxyTimeout(request, path, requestBodyText);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const upstreamResponse = await fetch(targetUrl, {
      method,
      headers: buildUpstreamHeaders(request, method),
      body: method === "GET" ? undefined : requestBodyText,
      cache: "no-store",
      signal: controller.signal,
    });

    const upstreamBody = await upstreamResponse.text();
    const contentType =
      upstreamResponse.headers.get("content-type") ?? "application/json";

    return new NextResponse(upstreamBody, {
      status: upstreamResponse.status,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (error) {
    const message =
      error instanceof Error && error.name === "AbortError"
        ? "前端代理请求后端超时，请确认后端服务是否可用。"
        : "前端代理请求后端失败，请确认后端地址与服务状态。";

    return NextResponse.json({ detail: message }, { status: 502 });
  } finally {
    clearTimeout(timeout);
  }
}

function buildTargetUrl(request: NextRequest, path: string[]): string {
  const baseUrl = (
    process.env.BACKEND_API_BASE_URL ?? DEFAULT_BACKEND_API_BASE_URL
  ).replace(/\/$/, "");
  const joinedPath = path.join("/");
  const search = request.nextUrl.search;
  return `${baseUrl}/${joinedPath}${search}`;
}

function buildUpstreamHeaders(
  request: NextRequest,
  method: "GET" | "POST" | "PATCH",
): HeadersInit {
  const headers: HeadersInit = {
    Accept: request.headers.get("accept") ?? "application/json",
  };

  if (method === "POST" || method === "PATCH") {
    headers["Content-Type"] =
      request.headers.get("content-type") ?? "application/json";
  }

  return headers;
}

function getProxyTimeout(
  request: NextRequest,
  path: string[],
  requestBodyText?: string,
): number {
  if (path[0] === "data" && path[1] === "refresh") {
    return DATA_REFRESH_TIMEOUT_MS;
  }

  const maxSymbols = resolveMaxSymbols(
    request.nextUrl.searchParams.get("max_symbols"),
    requestBodyText,
  );

  if (path[0] === "workflows" && path[1] === "single-stock" && path[2] === "run") {
    return SINGLE_STOCK_WORKFLOW_TIMEOUT_MS;
  }

  if (path[0] === "stocks" && path[2] === "debate-review") {
    return DEBATE_REVIEW_TIMEOUT_MS;
  }

  if (path[0] === "evaluations" && path[1] === "models") {
    return MODEL_EVALUATION_TIMEOUT_MS;
  }

  if (path[0] === "workflows" && path[1] === "deep-review" && path[2] === "run") {
    if (maxSymbols === undefined) {
      return MIN_DEEP_WORKFLOW_TIMEOUT_MS;
    }

    return clampTimeout(
      MIN_DEEP_WORKFLOW_TIMEOUT_MS + maxSymbols * WORKFLOW_TIMEOUT_PER_SYMBOL_MS,
      MAX_DEEP_WORKFLOW_TIMEOUT_MS,
    );
  }

  if (path[0] === "screener" && path[1] === "deep-run") {
    if (maxSymbols === undefined) {
      return MIN_DEEP_SCREENER_TIMEOUT_MS;
    }

    return clampTimeout(
      MIN_DEEP_SCREENER_TIMEOUT_MS +
        maxSymbols * DEEP_SCREENER_TIMEOUT_PER_SYMBOL_MS,
      MAX_DEEP_SCREENER_TIMEOUT_MS,
    );
  }

  if (path[0] === "screener") {
    if (maxSymbols === undefined) {
      return MIN_SCREENER_TIMEOUT_MS;
    }

    return clampTimeout(
      MIN_SCREENER_TIMEOUT_MS + maxSymbols * SCREENER_TIMEOUT_PER_SYMBOL_MS,
      MAX_SCREENER_TIMEOUT_MS,
    );
  }

  return STOCK_PAGE_TIMEOUT_MS;
}

function resolveMaxSymbols(
  queryValue: string | null,
  requestBodyText?: string,
): number | undefined {
  const fromQuery = parseOptionalPositiveInteger(queryValue);
  if (fromQuery !== undefined) {
    return fromQuery;
  }

  if (!requestBodyText) {
    return undefined;
  }

  try {
    const payload = JSON.parse(requestBodyText) as {
      max_symbols?: number | null;
    };
    return parseOptionalPositiveInteger(
      payload.max_symbols === undefined || payload.max_symbols === null
        ? null
        : String(payload.max_symbols),
    );
  } catch {
    return undefined;
  }
}

function parseOptionalPositiveInteger(value: string | null): number | undefined {
  if (value === null || value.trim() === "") {
    return undefined;
  }

  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }

  return parsed;
}

function clampTimeout(timeoutMs: number, maxTimeoutMs: number): number {
  return Math.min(Math.max(timeoutMs, STOCK_PAGE_TIMEOUT_MS), maxTimeoutMs);
}
