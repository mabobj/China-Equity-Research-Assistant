"""API 依赖注入辅助函数。"""

from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends

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
    from app.services.debate_service.debate_orchestrator import DebateOrchestrator
    from app.services.llm_debate_service.fallback import DebateRuntimeService
    from app.services.llm_debate_service.llm_debate_orchestrator import (
        LLMDebateOrchestrator,
    )
    from app.services.llm_debate_service.llm_role_runner import LLMRoleRunner
    from app.services.llm_debate_service.progress_tracker import DebateProgressTracker
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
    from app.services.review_service.stock_review_service import StockReviewService
    from app.services.screener_service.deep_pipeline import DeepScreenerPipeline
    from app.services.screener_service.pipeline import ScreenerPipeline
    from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
    from app.services.workflow_runtime.workflow_service import WorkflowRuntimeService


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
def get_stock_review_service() -> "StockReviewService":
    """构建个股研判 v2 service。"""
    from app.services.review_service.stock_review_service import StockReviewService

    return StockReviewService(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
        factor_snapshot_service=get_factor_snapshot_service(),
        trigger_snapshot_service=get_trigger_snapshot_service(),
        strategy_planner=get_strategy_planner(),
    )


@lru_cache
def get_debate_orchestrator() -> "DebateOrchestrator":
    """构建角色化裁决骨架编排器。"""
    from app.services.debate_service.debate_orchestrator import DebateOrchestrator

    return DebateOrchestrator(
        stock_review_service=get_stock_review_service(),
        factor_snapshot_service=get_factor_snapshot_service(),
        strategy_planner=get_strategy_planner(),
        trigger_snapshot_service=get_trigger_snapshot_service(),
    )


@lru_cache
def get_llm_role_runner() -> "LLMRoleRunner":
    """构建受控 LLM 角色执行器。"""
    from app.services.llm_debate_service.base import LLMDebateSettings
    from app.services.llm_debate_service.llm_role_runner import LLMRoleRunner

    settings = get_settings()
    return LLMRoleRunner(
        settings=LLMDebateSettings(
            enabled=settings.enable_llm_debate,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.llm_debate_timeout_seconds,
            provider=settings.llm_provider,
        )
    )


@lru_cache
def get_debate_progress_tracker() -> "DebateProgressTracker":
    """构建 debate 运行进度跟踪器。"""
    from app.services.llm_debate_service.progress_tracker import DebateProgressTracker

    return DebateProgressTracker()


@lru_cache
def get_llm_debate_orchestrator() -> "LLMDebateOrchestrator":
    """构建受控 LLM 裁决编排器。"""
    from app.services.llm_debate_service.llm_debate_orchestrator import (
        LLMDebateOrchestrator,
    )

    return LLMDebateOrchestrator(
        debate_orchestrator=get_debate_orchestrator(),
        role_runner=get_llm_role_runner(),
        progress_tracker=get_debate_progress_tracker(),
    )


@lru_cache
def get_debate_runtime_service() -> "DebateRuntimeService":
    """构建统一的 debate 运行时服务。"""
    from app.services.llm_debate_service.base import LLMDebateSettings
    from app.services.llm_debate_service.fallback import DebateRuntimeService

    settings = get_settings()
    return DebateRuntimeService(
        rule_based_orchestrator=get_debate_orchestrator(),
        llm_orchestrator=get_llm_debate_orchestrator(),
        progress_tracker=get_debate_progress_tracker(),
        settings=LLMDebateSettings(
            enabled=settings.enable_llm_debate,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.llm_debate_timeout_seconds,
            provider=settings.llm_provider,
        ),
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


@lru_cache
def get_workflow_artifact_store() -> "FileWorkflowArtifactStore":
    """构建 workflow 运行记录存储。"""
    from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore

    settings = get_settings()
    return FileWorkflowArtifactStore(root_dir=settings.data_dir / "workflow_runs")


def get_workflow_runtime_service(
    debate_orchestrator: "DebateOrchestrator" = Depends(get_debate_orchestrator),
    factor_snapshot_service: "FactorSnapshotService" = Depends(
        get_factor_snapshot_service
    ),
    stock_review_service: "StockReviewService" = Depends(get_stock_review_service),
    debate_runtime_service: "DebateRuntimeService" = Depends(
        get_debate_runtime_service
    ),
    strategy_planner: "StrategyPlanner" = Depends(get_strategy_planner),
    screener_pipeline: "ScreenerPipeline" = Depends(get_screener_pipeline),
) -> "WorkflowRuntimeService":
    """构建 workflow runtime service。"""
    from app.services.workflow_runtime.definitions.deep_review_workflow import (
        build_deep_review_workflow_definition,
    )
    from app.services.workflow_runtime.definitions.single_stock_workflow import (
        build_single_stock_workflow_definition,
    )
    from app.services.workflow_runtime.executor import WorkflowExecutor
    from app.services.workflow_runtime.registry import WorkflowRegistry
    from app.services.workflow_runtime.workflow_service import WorkflowRuntimeService

    artifact_store = get_workflow_artifact_store()
    registry = WorkflowRegistry(
        definitions=(
            build_single_stock_workflow_definition(
                debate_orchestrator=debate_orchestrator,
                factor_snapshot_service=factor_snapshot_service,
                stock_review_service=stock_review_service,
                debate_runtime_service=debate_runtime_service,
                strategy_planner=strategy_planner,
            ),
            build_deep_review_workflow_definition(
                screener_pipeline=screener_pipeline,
                stock_review_service=stock_review_service,
                debate_runtime_service=debate_runtime_service,
                strategy_planner=strategy_planner,
            ),
        )
    )
    executor = WorkflowExecutor(artifact_store=artifact_store)
    return WorkflowRuntimeService(
        registry=registry,
        executor=executor,
        artifact_store=artifact_store,
    )
