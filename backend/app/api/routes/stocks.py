"""Routes for market data access."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_market_data_service
from app.schemas.market_data import DailyBarResponse, StockProfile, UniverseResponse
from app.services.data_service.market_data_service import MarketDataService

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/universe", response_model=UniverseResponse)
def get_stock_universe(
    service: MarketDataService = Depends(get_market_data_service),
) -> UniverseResponse:
    """Return the current basic A-share stock universe."""
    return service.get_stock_universe()


@router.get("/{symbol}/profile", response_model=StockProfile)
def get_stock_profile(
    symbol: str,
    service: MarketDataService = Depends(get_market_data_service),
) -> StockProfile:
    """Return basic profile information for one stock."""
    return service.get_stock_profile(symbol)


@router.get("/{symbol}/daily-bars", response_model=DailyBarResponse)
def get_daily_bars(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    service: MarketDataService = Depends(get_market_data_service),
) -> DailyBarResponse:
    """Return daily bars for one stock."""
    return service.get_daily_bars(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )
