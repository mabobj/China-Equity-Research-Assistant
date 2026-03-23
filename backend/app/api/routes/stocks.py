"""股票数据相关路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_market_data_service,
    get_technical_analysis_service,
)
from app.schemas.market_data import DailyBarResponse, StockProfile, UniverseResponse
from app.schemas.research_inputs import (
    AnnouncementListResponse,
    FinancialSummary,
)
from app.schemas.technical import TechnicalSnapshot
from app.services.data_service.market_data_service import MarketDataService

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/universe", response_model=UniverseResponse)
def get_stock_universe(
    service: MarketDataService = Depends(get_market_data_service),
) -> UniverseResponse:
    """返回当前基础股票池。"""
    return service.get_stock_universe()


@router.get("/{symbol}/profile", response_model=StockProfile)
def get_stock_profile(
    symbol: str,
    service: MarketDataService = Depends(get_market_data_service),
) -> StockProfile:
    """返回单只股票基础信息。"""
    return service.get_stock_profile(symbol)


@router.get("/{symbol}/daily-bars", response_model=DailyBarResponse)
def get_daily_bars(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    service: MarketDataService = Depends(get_market_data_service),
) -> DailyBarResponse:
    """返回单只股票日线行情。"""
    return service.get_daily_bars(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{symbol}/announcements", response_model=AnnouncementListResponse)
def get_stock_announcements(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    service: MarketDataService = Depends(get_market_data_service),
) -> AnnouncementListResponse:
    """返回单只股票公告列表。"""
    return service.get_stock_announcements(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@router.get("/{symbol}/financial-summary", response_model=FinancialSummary)
def get_stock_financial_summary(
    symbol: str,
    service: MarketDataService = Depends(get_market_data_service),
) -> FinancialSummary:
    """返回单只股票基础财务摘要。"""
    return service.get_stock_financial_summary(symbol)


@router.get("/{symbol}/technical", response_model=TechnicalSnapshot)
def get_technical_snapshot(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    service: Any = Depends(get_technical_analysis_service),
) -> TechnicalSnapshot:
    """返回最新交易日的技术分析快照。"""
    return service.get_technical_snapshot(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )
