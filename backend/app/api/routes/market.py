"""关键市场数据域只读路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_market_context_service
from app.schemas.market_context import (
    BenchmarkCatalogResponse,
    MarketBreadthSnapshot,
    RiskProxySnapshot,
)
from app.services.data_service.exceptions import InvalidDateError, InvalidRequestError

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/benchmarks", response_model=BenchmarkCatalogResponse)
def get_benchmark_catalog(
    as_of_date: Optional[str] = Query(default=None),
    service: Any = Depends(get_market_context_service),
) -> BenchmarkCatalogResponse:
    """读取标准基准目录。"""
    try:
        return service.get_benchmark_catalog(as_of_date=as_of_date)
    except (InvalidDateError, InvalidRequestError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/breadth", response_model=MarketBreadthSnapshot)
def get_market_breadth(
    as_of_date: Optional[str] = Query(default=None),
    max_symbols: Optional[int] = Query(default=500, ge=1, le=5000),
    force_refresh: bool = Query(default=False),
    service: Any = Depends(get_market_context_service),
) -> MarketBreadthSnapshot:
    """读取市场广度快照。"""
    try:
        return service.get_market_breadth(
            as_of_date=as_of_date,
            max_symbols=max_symbols,
            force_refresh=force_refresh,
        )
    except (InvalidDateError, InvalidRequestError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/risk-proxies", response_model=RiskProxySnapshot)
def get_risk_proxy(
    as_of_date: Optional[str] = Query(default=None),
    max_symbols: Optional[int] = Query(default=500, ge=1, le=5000),
    force_refresh: bool = Query(default=False),
    service: Any = Depends(get_market_context_service),
) -> RiskProxySnapshot:
    """读取基础风险代理快照。"""
    try:
        return service.get_risk_proxy(
            as_of_date=as_of_date,
            max_symbols=max_symbols,
            force_refresh=force_refresh,
        )
    except (InvalidDateError, InvalidRequestError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
