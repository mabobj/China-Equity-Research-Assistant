"""FastAPI dependency helpers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends

from app.core.config import get_settings
from app.db.trade_review_store import TradeReviewStore
from app.db.market_data_store import LocalMarketDataStore
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.provider_registry import ProviderRegistry
from app.services.data_service.providers.akshare_provider import AkshareProvider
from app.services.data_service.providers.baostock_provider import BaostockProvider
from app.services.data_service.providers.cninfo_provider import CninfoProvider
from app.services.data_service.providers.mootdx_provider import MootdxProvider

if TYPE_CHECKING:
    from app.services.backtest_service.backtest_service import BacktestService
    from app.services.data_products.datasets.announcements_daily import (
        AnnouncementsDailyDataset,
    )
    from app.services.data_products.datasets.daily_bars_daily import DailyBarsDailyDataset
    from app.services.data_products.datasets.debate_review_daily import (
        DebateReviewDailyDataset,
    )
    from app.services.data_products.datasets.decision_brief_daily import (
        DecisionBriefDailyDataset,
    )
    from app.services.data_products.datasets.factor_snapshot_daily import (
        FactorSnapshotDailyDataset,
    )
    from app.services.data_products.datasets.financial_summary_daily import (
        FinancialSummaryDailyDataset,
    )
    from app.services.data_products.datasets.review_report_daily import (
        ReviewReportDailyDataset,
    )
    from app.services.data_products.datasets.screener_snapshot_daily import (
        ScreenerSnapshotDailyDataset,
    )
    from app.services.data_products.datasets.strategy_plan_daily import (
        StrategyPlanDailyDataset,
    )
    from app.services.data_products.repository import DataProductRepository
    from app.services.data_service.db_inspector_service import DbInspectorService
    from app.services.data_service.intraday_service import IntradayService
    from app.services.data_service.refresh_service import DataRefreshService
    from app.services.debate_service.debate_orchestrator import DebateOrchestrator
    from app.services.dataset_service.dataset_service import DatasetService
    from app.services.decision_brief_service.decision_brief_service import (
        DecisionBriefService,
    )
    from app.services.evaluation_service.evaluation_service import EvaluationService
    from app.services.experiment_service.experiment_service import ExperimentService
    from app.services.factor_service.factor_snapshot_service import (
        FactorSnapshotService,
    )
    from app.services.factor_service.trigger_snapshot_service import (
        TriggerSnapshotService,
    )
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )
    from app.services.llm_debate_service.fallback import DebateRuntimeService
    from app.services.llm_debate_service.llm_debate_orchestrator import (
        LLMDebateOrchestrator,
    )
    from app.services.llm_debate_service.llm_role_runner import LLMRoleRunner
    from app.services.llm_debate_service.progress_tracker import DebateProgressTracker
    from app.services.label_service.label_service import LabelService
    from app.services.prediction_service.prediction_service import PredictionService
    from app.services.research_service.research_manager import ResearchManager
    from app.services.research_service.strategy_planner import StrategyPlanner
    from app.services.review_record_service.review_service import ReviewRecordService
    from app.services.review_service.stock_review_service import StockReviewService
    from app.services.screener_service.deep_pipeline import DeepScreenerPipeline
    from app.services.screener_service.pipeline import ScreenerPipeline
    from app.services.screener_service.batch_service import ScreenerBatchService
    from app.services.trade_service.trade_service import TradeService
    from app.services.decision_snapshot_service.decision_snapshot_service import (
        DecisionSnapshotService,
    )
    from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
    from app.services.workflow_runtime.workflow_service import WorkflowRuntimeService
    from app.services.workspace_bundle_service.workspace_bundle_service import (
        WorkspaceBundleService,
    )


@lru_cache
def get_local_market_data_store() -> LocalMarketDataStore:
    settings = get_settings()
    return LocalMarketDataStore(database_path=settings.duckdb_path)


@lru_cache
def get_market_data_service() -> MarketDataService:
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
    from app.services.data_service.db_inspector_service import DbInspectorService

    return DbInspectorService(local_store=get_local_market_data_store())


@lru_cache
def get_technical_analysis_service() -> "TechnicalAnalysisService":
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )

    return TechnicalAnalysisService(market_data_service=get_market_data_service())


@lru_cache
def get_intraday_service() -> "IntradayService":
    from app.services.data_service.intraday_service import IntradayService

    return IntradayService(market_data_service=get_market_data_service())


@lru_cache
def get_factor_snapshot_service() -> "FactorSnapshotService":
    from app.services.factor_service.factor_snapshot_service import (
        FactorSnapshotService,
    )

    return FactorSnapshotService(
        technical_analysis_service=get_technical_analysis_service(),
        market_data_service=get_market_data_service(),
    )


@lru_cache
def get_trigger_snapshot_service() -> "TriggerSnapshotService":
    from app.services.factor_service.trigger_snapshot_service import (
        TriggerSnapshotService,
    )

    return TriggerSnapshotService(
        technical_analysis_service=get_technical_analysis_service(),
        intraday_service=get_intraday_service(),
    )


@lru_cache
def get_research_manager() -> "ResearchManager":
    from app.services.research_service.research_manager import ResearchManager

    return ResearchManager(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
    )


@lru_cache
def get_strategy_planner() -> "StrategyPlanner":
    from app.services.research_service.strategy_planner import StrategyPlanner

    return StrategyPlanner(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
        research_manager=get_research_manager(),
    )


@lru_cache
def get_stock_review_service() -> "StockReviewService":
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
    from app.services.debate_service.debate_orchestrator import DebateOrchestrator

    return DebateOrchestrator(
        stock_review_service=get_stock_review_service(),
        factor_snapshot_service=get_factor_snapshot_service(),
        strategy_planner=get_strategy_planner(),
        trigger_snapshot_service=get_trigger_snapshot_service(),
    )


@lru_cache
def get_llm_role_runner() -> "LLMRoleRunner":
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
    from app.services.llm_debate_service.progress_tracker import DebateProgressTracker

    return DebateProgressTracker()


@lru_cache
def get_llm_debate_orchestrator() -> "LLMDebateOrchestrator":
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
def get_data_product_repository() -> "DataProductRepository":
    from app.services.data_products.repository import DataProductRepository

    settings = get_settings()
    return DataProductRepository(root_dir=settings.data_dir / "daily_products")


@lru_cache
def get_experiment_service() -> "ExperimentService":
    from app.services.experiment_service.experiment_service import ExperimentService

    return ExperimentService()


@lru_cache
def get_label_service() -> "LabelService":
    from app.services.label_service.label_service import LabelService

    settings = get_settings()
    return LabelService(
        default_label_version=get_experiment_service().get_default_label_version(),
        root_dir=settings.data_dir / "prediction_assets" / "datasets",
        market_data_service=get_market_data_service(),
        dataset_service=get_dataset_service(),
    )


@lru_cache
def get_dataset_service() -> "DatasetService":
    from app.services.dataset_service.dataset_service import DatasetService

    settings = get_settings()
    return DatasetService(
        root_dir=settings.data_dir / "prediction_assets" / "datasets",
        default_feature_version=get_experiment_service().get_default_feature_version(),
        market_data_service=get_market_data_service(),
    )


@lru_cache
def get_prediction_service() -> "PredictionService":
    from app.services.prediction_service.prediction_service import PredictionService

    return PredictionService(
        dataset_service=get_dataset_service(),
        label_service=get_label_service(),
        experiment_service=get_experiment_service(),
    )


@lru_cache
def get_backtest_service() -> "BacktestService":
    from app.services.backtest_service.backtest_service import BacktestService

    return BacktestService(
        experiment_service=get_experiment_service(),
        label_service=get_label_service(),
        prediction_service=get_prediction_service(),
    )


@lru_cache
def get_evaluation_service() -> "EvaluationService":
    from app.services.evaluation_service.evaluation_service import EvaluationService

    return EvaluationService(
        experiment_service=get_experiment_service(),
        label_service=get_label_service(),
        backtest_service=get_backtest_service(),
    )


@lru_cache
def get_daily_bars_daily_dataset() -> "DailyBarsDailyDataset":
    from app.services.data_products.datasets.daily_bars_daily import DailyBarsDailyDataset

    return DailyBarsDailyDataset(market_data_service=get_market_data_service())


@lru_cache
def get_announcements_daily_dataset() -> "AnnouncementsDailyDataset":
    from app.services.data_products.datasets.announcements_daily import (
        AnnouncementsDailyDataset,
    )

    return AnnouncementsDailyDataset(market_data_service=get_market_data_service())


@lru_cache
def get_financial_summary_daily_dataset() -> "FinancialSummaryDailyDataset":
    from app.services.data_products.datasets.financial_summary_daily import (
        FinancialSummaryDailyDataset,
    )

    return FinancialSummaryDailyDataset(market_data_service=get_market_data_service())


@lru_cache
def get_factor_snapshot_daily_dataset() -> "FactorSnapshotDailyDataset":
    from app.services.data_products.datasets.factor_snapshot_daily import (
        FactorSnapshotDailyDataset,
    )

    return FactorSnapshotDailyDataset(repository=get_data_product_repository())


@lru_cache
def get_review_report_daily_dataset() -> "ReviewReportDailyDataset":
    from app.services.data_products.datasets.review_report_daily import (
        ReviewReportDailyDataset,
    )

    return ReviewReportDailyDataset(repository=get_data_product_repository())


@lru_cache
def get_strategy_plan_daily_dataset() -> "StrategyPlanDailyDataset":
    from app.services.data_products.datasets.strategy_plan_daily import (
        StrategyPlanDailyDataset,
    )

    return StrategyPlanDailyDataset(repository=get_data_product_repository())


@lru_cache
def get_debate_review_daily_dataset() -> "DebateReviewDailyDataset":
    from app.services.data_products.datasets.debate_review_daily import (
        DebateReviewDailyDataset,
    )

    return DebateReviewDailyDataset(repository=get_data_product_repository())


@lru_cache
def get_decision_brief_daily_dataset() -> "DecisionBriefDailyDataset":
    from app.services.data_products.datasets.decision_brief_daily import (
        DecisionBriefDailyDataset,
    )

    return DecisionBriefDailyDataset(repository=get_data_product_repository())


@lru_cache
def get_screener_snapshot_daily_dataset() -> "ScreenerSnapshotDailyDataset":
    from app.services.data_products.datasets.screener_snapshot_daily import (
        ScreenerSnapshotDailyDataset,
    )

    return ScreenerSnapshotDailyDataset(repository=get_data_product_repository())


@lru_cache
def get_workspace_bundle_service() -> "WorkspaceBundleService":
    from app.services.workspace_bundle_service.workspace_bundle_service import (
        WorkspaceBundleService,
    )

    return WorkspaceBundleService(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
        research_manager=get_research_manager(),
        factor_snapshot_service=get_factor_snapshot_service(),
        stock_review_service=get_stock_review_service(),
        debate_orchestrator=get_debate_orchestrator(),
        debate_runtime_service=get_debate_runtime_service(),
        strategy_planner=get_strategy_planner(),
        trigger_snapshot_service=get_trigger_snapshot_service(),
        daily_bars_daily=get_daily_bars_daily_dataset(),
        announcements_daily=get_announcements_daily_dataset(),
        financial_summary_daily=get_financial_summary_daily_dataset(),
        factor_snapshot_daily=get_factor_snapshot_daily_dataset(),
        review_report_daily=get_review_report_daily_dataset(),
        strategy_plan_daily=get_strategy_plan_daily_dataset(),
        debate_review_daily=get_debate_review_daily_dataset(),
        decision_brief_daily=get_decision_brief_daily_dataset(),
        prediction_service=get_prediction_service(),
    )


@lru_cache
def get_decision_brief_service() -> "DecisionBriefService":
    from app.services.decision_brief_service.decision_brief_service import (
        DecisionBriefService,
    )

    return DecisionBriefService(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
        factor_snapshot_service=get_factor_snapshot_service(),
        stock_review_service=get_stock_review_service(),
        debate_runtime_service=get_debate_runtime_service(),
        strategy_planner=get_strategy_planner(),
        trigger_snapshot_service=get_trigger_snapshot_service(),
    )


@lru_cache
def get_screener_pipeline() -> "ScreenerPipeline":
    from app.services.screener_service.pipeline import ScreenerPipeline

    settings = get_settings()
    return ScreenerPipeline(
        market_data_service=get_market_data_service(),
        technical_analysis_service=get_technical_analysis_service(),
        factor_snapshot_service=get_factor_snapshot_service(),
        prediction_service=get_prediction_service(),
        lookback_days=settings.screener_lookback_days,
        progress_log_interval=settings.screener_progress_log_interval,
    )


@lru_cache
def get_deep_screener_pipeline() -> "DeepScreenerPipeline":
    from app.services.screener_service.deep_pipeline import DeepScreenerPipeline

    return DeepScreenerPipeline(
        screener_pipeline=get_screener_pipeline(),
        research_manager=get_research_manager(),
        strategy_planner=get_strategy_planner(),
    )


@lru_cache
def get_screener_batch_service() -> "ScreenerBatchService":
    from app.services.screener_service.batch_service import ScreenerBatchService

    settings = get_settings()
    return ScreenerBatchService(
        root_dir=settings.data_dir / "screener_batches",
        prediction_service=get_prediction_service(),
    )


@lru_cache
def get_workflow_artifact_store() -> "FileWorkflowArtifactStore":
    from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore

    settings = get_settings()
    return FileWorkflowArtifactStore(root_dir=settings.data_dir / "workflow_runs")


@lru_cache
def get_workflow_background_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=2, thread_name_prefix="workflow-runtime")


@lru_cache
def get_trade_review_store() -> TradeReviewStore:
    settings = get_settings()
    return TradeReviewStore(database_path=settings.data_dir / "trade_review.sqlite3")


@lru_cache
def get_decision_snapshot_service() -> "DecisionSnapshotService":
    from app.services.decision_snapshot_service.decision_snapshot_service import (
        DecisionSnapshotService,
    )

    return DecisionSnapshotService(
        store=get_trade_review_store(),
        workspace_bundle_service=get_workspace_bundle_service(),
        research_manager=get_research_manager(),
    )


@lru_cache
def get_trade_service() -> "TradeService":
    from app.services.trade_service.trade_service import TradeService

    return TradeService(
        store=get_trade_review_store(),
        decision_snapshot_service=get_decision_snapshot_service(),
    )


@lru_cache
def get_review_record_service() -> "ReviewRecordService":
    from app.services.review_record_service.review_service import ReviewRecordService

    return ReviewRecordService(
        store=get_trade_review_store(),
        trade_service=get_trade_service(),
        decision_snapshot_service=get_decision_snapshot_service(),
        market_data_service=get_market_data_service(),
    )


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
    screener_snapshot_daily: "ScreenerSnapshotDailyDataset" = Depends(
        get_screener_snapshot_daily_dataset
    ),
    screener_batch_service: "ScreenerBatchService" = Depends(
        get_screener_batch_service
    ),
    evaluation_service: "EvaluationService" = Depends(get_evaluation_service),
    experiment_service: "ExperimentService" = Depends(get_experiment_service),
) -> "WorkflowRuntimeService":
    from app.services.workflow_runtime.definitions.deep_review_workflow import (
        build_deep_review_workflow_definition,
    )
    from app.services.workflow_runtime.definitions.screener_workflow import (
        build_screener_workflow_definition,
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
                review_report_daily=get_review_report_daily_dataset(),
                strategy_plan_daily=get_strategy_plan_daily_dataset(),
                debate_review_daily=get_debate_review_daily_dataset(),
            ),
            build_deep_review_workflow_definition(
                screener_pipeline=screener_pipeline,
                stock_review_service=stock_review_service,
                debate_runtime_service=debate_runtime_service,
                strategy_planner=strategy_planner,
                review_report_daily=get_review_report_daily_dataset(),
                strategy_plan_daily=get_strategy_plan_daily_dataset(),
                debate_review_daily=get_debate_review_daily_dataset(),
            ),
            build_screener_workflow_definition(
                screener_pipeline=screener_pipeline,
                screener_snapshot_daily=screener_snapshot_daily,
                market_data_service=get_market_data_service(),
            ),
        )
    )
    executor = WorkflowExecutor(artifact_store=artifact_store)
    return WorkflowRuntimeService(
        registry=registry,
        executor=executor,
        artifact_store=artifact_store,
        background_executor=get_workflow_background_executor(),
        screener_batch_service=screener_batch_service,
        evaluation_service=evaluation_service,
        experiment_service=experiment_service,
    )
