"""API 依赖注入辅助函数。"""

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.providers.akshare_provider import AkshareProvider
from app.services.data_service.providers.baostock_provider import BaostockProvider
from app.services.data_service.providers.cninfo_provider import CninfoProvider

if TYPE_CHECKING:
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )
    from app.services.research_service.research_manager import ResearchManager
    from app.services.research_service.strategy_planner import StrategyPlanner
    from app.services.screener_service.deep_pipeline import DeepScreenerPipeline
    from app.services.screener_service.pipeline import ScreenerPipeline


@lru_cache
def get_market_data_service() -> MarketDataService:
    """构建启用中的市场数据 service。"""
    settings = get_settings()
    providers = []

    if settings.enable_akshare:
        providers.append(AkshareProvider())
    if settings.enable_baostock:
        providers.append(BaostockProvider())
    if settings.enable_cninfo:
        providers.append(CninfoProvider())

    return MarketDataService(providers=providers)


@lru_cache
def get_technical_analysis_service() -> "TechnicalAnalysisService":
    """构建技术分析 service。"""
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )

    return TechnicalAnalysisService(
        market_data_service=get_market_data_service(),
    )


@lru_cache
def get_research_manager() -> "ResearchManager":
    """构建单票研究 manager。"""
    from app.services.research_service.research_manager import ResearchManager

    return ResearchManager(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
    )


@lru_cache
def get_strategy_planner() -> "StrategyPlanner":
    """构建结构化交易策略 planner。"""
    from app.services.research_service.strategy_planner import StrategyPlanner

    return StrategyPlanner(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
        research_manager=get_research_manager(),
    )


@lru_cache
def get_screener_pipeline() -> "ScreenerPipeline":
    """构建规则初筛选股 pipeline。"""
    from app.services.screener_service.pipeline import ScreenerPipeline

    return ScreenerPipeline(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
    )


@lru_cache
def get_deep_screener_pipeline() -> "DeepScreenerPipeline":
    """构建深筛聚合 pipeline。"""
    from app.services.screener_service.deep_pipeline import DeepScreenerPipeline

    return DeepScreenerPipeline(
        screener_pipeline=get_screener_pipeline(),
        research_manager=get_research_manager(),
        strategy_planner=get_strategy_planner(),
    )
