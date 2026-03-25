"""API 依赖注入辅助函数。"""

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.db.market_data_store import LocalMarketDataStore
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.provider_registry import ProviderRegistry
from app.services.data_service.providers.akshare_provider import AkshareProvider
from app.services.data_service.providers.baostock_provider import BaostockProvider
from app.services.data_service.providers.cninfo_provider import CninfoProvider
from app.services.data_service.providers.mootdx_provider import MootdxProvider

if TYPE_CHECKING:
    from app.services.data_service.db_inspector_service import DbInspectorService
    from app.services.data_service.intraday_service import IntradayService
    from app.services.data_service.refresh_service import DataRefreshService
    from app.services.factor_service.factor_snapshot_service import (
        FactorSnapshotService,
    )
    from app.services.factor_service.trigger_snapshot_service import (
        TriggerSnapshotService,
    )
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )
    from app.services.research_service.research_manager import ResearchManager
    from app.services.research_service.strategy_planner import StrategyPlanner
    from app.services.screener_service.deep_pipeline import DeepScreenerPipeline
    from app.services.screener_service.pipeline import ScreenerPipeline


@lru_cache
def get_local_market_data_store() -> LocalMarketDataStore:
    """构建本地市场数据仓储。"""
    settings = get_settings()
    return LocalMarketDataStore(database_path=settings.duckdb_path)


@lru_cache
def get_market_data_service() -> MarketDataService:
    """构建启用中的市场数据 service。"""
    settings = get_settings()
    providers = []

    if settings.enable_mootdx and settings.mootdx_tdx_dir is not None:
        providers.append(MootdxProvider(tdx_dir=settings.mootdx_tdx_dir))
    if settings.enable_akshare:
        providers.append(
            AkshareProvider(
                daily_bars_max_retries=settings.akshare_daily_retry_max_attempts,
                daily_bars_retry_backoff_seconds=settings.akshare_daily_retry_backoff_seconds,
                daily_bars_retry_jitter_seconds=settings.akshare_daily_retry_jitter_seconds,
            )
        )
    if settings.enable_baostock:
        providers.append(BaostockProvider())
    if settings.enable_cninfo:
        providers.append(CninfoProvider())

    return MarketDataService(
        providers=ProviderRegistry(providers),
        local_store=get_local_market_data_store(),
    )


@lru_cache
def get_data_refresh_service() -> "DataRefreshService":
    """构建手动数据补全 service。"""
    from app.services.data_service.refresh_service import DataRefreshService

    settings = get_settings()
    return DataRefreshService(
        market_data_service=get_market_data_service(),
        daily_bar_lookback_days=settings.data_refresh_daily_bar_lookback_days,
        announcement_lookback_days=settings.data_refresh_announcement_lookback_days,
        announcement_limit=settings.data_refresh_announcement_limit,
        progress_log_interval=settings.data_refresh_progress_log_interval,
        symbol_sleep_ms=settings.data_refresh_symbol_sleep_ms,
    )


@lru_cache
def get_db_inspector_service() -> "DbInspectorService":
    """构建数据库排查 service。"""
    from app.services.data_service.db_inspector_service import DbInspectorService

    return DbInspectorService(local_store=get_local_market_data_store())


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
def get_intraday_service() -> "IntradayService":
    """构建盘中快照 service。"""
    from app.services.data_service.intraday_service import IntradayService

    return IntradayService(
        market_data_service=get_market_data_service(),
    )


@lru_cache
def get_factor_snapshot_service() -> "FactorSnapshotService":
    """构建 factor snapshot service。"""
    from app.services.factor_service.factor_snapshot_service import (
        FactorSnapshotService,
    )

    return FactorSnapshotService(
        technical_analysis_service=get_technical_analysis_service(),
        market_data_service=get_market_data_service(),
    )


@lru_cache
def get_trigger_snapshot_service() -> "TriggerSnapshotService":
    """构建轻量触发快照 service。"""
    from app.services.factor_service.trigger_snapshot_service import (
        TriggerSnapshotService,
    )

    return TriggerSnapshotService(
        technical_analysis_service=get_technical_analysis_service(),
        intraday_service=get_intraday_service(),
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

    settings = get_settings()
    return ScreenerPipeline(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
        factor_snapshot_service=get_factor_snapshot_service(),
        lookback_days=settings.screener_lookback_days,
        progress_log_interval=settings.screener_progress_log_interval,
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
