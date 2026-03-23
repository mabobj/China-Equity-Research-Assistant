"""Dependency helpers for API routes."""

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.providers.akshare_provider import AkshareProvider
from app.services.data_service.providers.baostock_provider import BaostockProvider

if TYPE_CHECKING:
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )


@lru_cache
def get_market_data_service() -> MarketDataService:
    """Build the market data service with enabled providers."""
    settings = get_settings()
    providers = []

    if settings.enable_akshare:
        providers.append(AkshareProvider())
    if settings.enable_baostock:
        providers.append(BaostockProvider())

    return MarketDataService(providers=providers)


@lru_cache
def get_technical_analysis_service() -> "TechnicalAnalysisService":
    """构建技术分析服务。"""
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )

    return TechnicalAnalysisService(
        market_data_service=get_market_data_service(),
    )
