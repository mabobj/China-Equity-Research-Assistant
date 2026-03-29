"""选股器路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import (
    get_deep_screener_pipeline,
    get_screener_batch_service,
    get_screener_pipeline,
)
from app.schemas.screener import (
    DeepScreenerRunResponse,
    ScreenerBatchDetailResponse,
    ScreenerBatchResultsResponse,
    ScreenerLatestBatchResponse,
    ScreenerRunResponse,
    ScreenerSymbolResultResponse,
)

router = APIRouter(prefix="/screener", tags=["screener"])


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
    return ScreenerLatestBatchResponse(batch=batch_service.get_latest_batch())


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
    batch_service: Any = Depends(get_screener_batch_service),
) -> ScreenerBatchResultsResponse:
    """返回指定批次的股票结果列表。"""
    batch = batch_service.load_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Screener batch not found.")
    return ScreenerBatchResultsResponse(
        batch=batch,
        results=batch_service.load_batch_results(batch_id),
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
