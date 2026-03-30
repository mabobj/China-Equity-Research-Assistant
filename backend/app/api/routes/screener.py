"""选股器路由。"""

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import (
    get_market_data_service,
    get_deep_screener_pipeline,
    get_screener_batch_service,
    get_screener_pipeline,
)
from app.schemas.screener import (
    ScreenerCursorResetResponse,
    DeepScreenerRunResponse,
    ScreenerBatchDetailResponse,
    ScreenerBatchResultsResponse,
    ScreenerLatestBatchResponse,
    ScreenerRunResponse,
    ScreenerSymbolResultResponse,
)

router = APIRouter(prefix="/screener", tags=["screener"])
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


@router.get("/run", response_model=ScreenerRunResponse)
def run_screener(
    max_symbols: Optional[int] = Query(default=None, ge=1),
    top_n: Optional[int] = Query(default=None, ge=1),
    pipeline: Any = Depends(get_screener_pipeline),
) -> ScreenerRunResponse:
    """运行规则初筛选股器。"""
    return pipeline.run_screener(
        max_symbols=max_symbols,
        top_n=top_n,
    )


@router.get("/deep-run", response_model=DeepScreenerRunResponse)
def run_deep_screener(
    max_symbols: Optional[int] = Query(default=None, ge=1),
    top_n: Optional[int] = Query(default=None, ge=1),
    deep_top_k: Optional[int] = Query(default=None, ge=1),
    pipeline: Any = Depends(get_deep_screener_pipeline),
) -> DeepScreenerRunResponse:
    """运行深筛聚合选股器。"""
    return pipeline.run_deep_screener(
        max_symbols=max_symbols,
        top_n=top_n,
        deep_top_k=deep_top_k,
    )


@router.get("/latest-batch", response_model=ScreenerLatestBatchResponse)
def get_latest_batch(
    batch_service: Any = Depends(get_screener_batch_service),
) -> ScreenerLatestBatchResponse:
    """返回当前可查看的最新批次。"""
    window_start, window_end, window_results = batch_service.load_window_results()
    return ScreenerLatestBatchResponse(
        window_start=window_start,
        window_end=window_end,
        batch=batch_service.get_latest_batch(),
        results=window_results,
        total_results=len(window_results),
    )


@router.get("/batches/{batch_id}", response_model=ScreenerBatchDetailResponse)
def get_batch_detail(
    batch_id: str,
    batch_service: Any = Depends(get_screener_batch_service),
) -> ScreenerBatchDetailResponse:
    """返回指定批次摘要。"""
    batch = batch_service.load_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Screener batch not found.")
    return ScreenerBatchDetailResponse(batch=batch)


@router.get("/batches/{batch_id}/results", response_model=ScreenerBatchResultsResponse)
def get_batch_results(
    batch_id: str,
    symbol_query: Optional[str] = Query(default=None),
    list_type: Optional[str] = Query(default=None),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    max_score: Optional[int] = Query(default=None, ge=0, le=100),
    reason_query: Optional[str] = Query(default=None),
    calculated_from: Optional[datetime] = Query(default=None),
    calculated_to: Optional[datetime] = Query(default=None),
    rule_version: Optional[str] = Query(default=None),
    batch_service: Any = Depends(get_screener_batch_service),
) -> ScreenerBatchResultsResponse:
    """返回指定批次的股票结果列表。"""
    batch = batch_service.load_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Screener batch not found.")
    results = batch_service.load_batch_results(batch_id)
    results = _filter_symbol_results(
        results=results,
        symbol_query=symbol_query,
        list_type=list_type,
        min_score=min_score,
        max_score=max_score,
        reason_query=reason_query,
        calculated_from=calculated_from,
        calculated_to=calculated_to,
        rule_version=rule_version,
    )
    return ScreenerBatchResultsResponse(
        batch=batch,
        results=results,
    )


@router.get(
    "/batches/{batch_id}/results/{symbol}",
    response_model=ScreenerSymbolResultResponse,
)
def get_batch_symbol_result(
    batch_id: str,
    symbol: str,
    batch_service: Any = Depends(get_screener_batch_service),
) -> ScreenerSymbolResultResponse:
    """返回指定批次内单只股票筛选结果。"""
    batch = batch_service.load_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Screener batch not found.")
    result = batch_service.load_symbol_result(batch_id, symbol)
    if result is None:
        raise HTTPException(status_code=404, detail="Screener symbol result not found.")
    return ScreenerSymbolResultResponse(batch=batch, result=result)


@router.post("/cursor/reset", response_model=ScreenerCursorResetResponse)
def reset_screener_cursor(
    market_data_service: Any = Depends(get_market_data_service),
) -> ScreenerCursorResetResponse:
    """手动重置初筛游标，下一次运行从股票池首支开始。"""
    now = datetime.now(_SHANGHAI_TZ)
    market_data_service.set_refresh_cursor("screener_run_cursor_symbol", None)
    market_data_service.set_refresh_cursor(
        "screener_run_cursor_last_reset_date",
        now.date().isoformat(),
    )
    return ScreenerCursorResetResponse(
        reset_at=now,
        message="初筛游标已重置，下一次运行将从首支股票开始。",
    )


def _filter_symbol_results(
    *,
    results: list[Any],
    symbol_query: Optional[str],
    list_type: Optional[str],
    min_score: Optional[int],
    max_score: Optional[int],
    reason_query: Optional[str],
    calculated_from: Optional[datetime],
    calculated_to: Optional[datetime],
    rule_version: Optional[str],
) -> list[Any]:
    filtered = list(results)
    if symbol_query:
        normalized = symbol_query.strip().upper()
        filtered = [
            item
            for item in filtered
            if normalized in item.symbol.upper() or normalized in item.name.upper()
        ]
    if list_type:
        normalized = list_type.strip().upper()
        filtered = [item for item in filtered if item.list_type.upper() == normalized]
    if min_score is not None:
        filtered = [item for item in filtered if item.screener_score >= min_score]
    if max_score is not None:
        filtered = [item for item in filtered if item.screener_score <= max_score]
    if reason_query:
        normalized = reason_query.strip().lower()
        filtered = [item for item in filtered if normalized in item.short_reason.lower()]
    if calculated_from is not None:
        filtered = [item for item in filtered if item.calculated_at >= calculated_from]
    if calculated_to is not None:
        filtered = [item for item in filtered if item.calculated_at <= calculated_to]
    if rule_version:
        normalized = rule_version.strip()
        filtered = [item for item in filtered if item.rule_version == normalized]
    return filtered
