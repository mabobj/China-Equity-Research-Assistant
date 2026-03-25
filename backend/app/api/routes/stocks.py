"""股票数据相关路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_debate_orchestrator,
    get_factor_snapshot_service,
    get_market_data_service,
    get_stock_review_service,
    get_technical_analysis_service,
    get_trigger_snapshot_service,
)
from app.schemas.debate import DebateReviewReport
from app.schemas.factor import FactorSnapshot
from app.schemas.intraday import TriggerSnapshot
from app.schemas.market_data import (
    DailyBarResponse,
    IntradayBarResponse,
    StockProfile,
    TimelineResponse,
    UniverseResponse,
)
from app.schemas.research_inputs import (
    AnnouncementListResponse,
    FinancialSummary,
)
from app.schemas.review import StockReviewReport
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


@router.get("/{symbol}/intraday-bars", response_model=IntradayBarResponse)
def get_intraday_bars(
    symbol: str,
    frequency: str = Query(default="1m"),
    start_datetime: Optional[str] = Query(default=None),
    end_datetime: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=None, ge=1),
    service: MarketDataService = Depends(get_market_data_service),
) -> IntradayBarResponse:
    """返回单只股票分钟线行情，支持 1 分钟和 5 分钟频率。"""
    return service.get_intraday_bars(
        symbol=symbol,
        frequency=frequency,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        limit=limit,
    )


@router.get("/{symbol}/timeline", response_model=TimelineResponse)
def get_timeline(
    symbol: str,
    limit: Optional[int] = Query(default=None, ge=1),
    service: MarketDataService = Depends(get_market_data_service),
) -> TimelineResponse:
    """返回单只股票最新交易日的分时线预览。"""
    return service.get_timeline(
        symbol=symbol,
        limit=limit,
    )


@router.get("/{symbol}/trigger-snapshot", response_model=TriggerSnapshot)
def get_trigger_snapshot(
    symbol: str,
    frequency: str = Query(default="1m"),
    limit: int = Query(default=60, ge=1),
    service: Any = Depends(get_trigger_snapshot_service),
) -> TriggerSnapshot:
    """返回基于日线与盘中快照的轻量触发快照。"""
    return service.get_trigger_snapshot(
        symbol=symbol,
        frequency=frequency,
        limit=limit,
    )


@router.get("/{symbol}/factor-snapshot", response_model=FactorSnapshot)
def get_factor_snapshot(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    service: Any = Depends(get_factor_snapshot_service),
) -> FactorSnapshot:
    """返回单只股票的结构化因子快照。"""
    return service.get_factor_snapshot(
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


@router.get("/{symbol}/review-report", response_model=StockReviewReport)
def get_stock_review_report(
    symbol: str,
    service: Any = Depends(get_stock_review_service),
) -> StockReviewReport:
    """返回个股研判 v2 的多维结构化输出。"""
    return service.get_stock_review_report(symbol)


@router.get("/{symbol}/debate-review", response_model=DebateReviewReport)
def get_debate_review_report(
    symbol: str,
    service: Any = Depends(get_debate_orchestrator),
) -> DebateReviewReport:
    """返回角色化裁决骨架版单票报告。"""
    return service.get_debate_review_report(symbol)
