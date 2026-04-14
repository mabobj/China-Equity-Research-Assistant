"""Tests for the stock workspace bundle service."""

from __future__ import annotations

from datetime import date, datetime
from threading import Lock, Thread
from time import sleep

from app.schemas.market_data import DailyBar, DailyBarResponse, StockProfile
from app.schemas.lineage import LineageMetadata
from app.schemas.prediction import PredictionSnapshotResponse
from app.schemas.research import ResearchReport
from app.schemas.research_inputs import AnnouncementListResponse, FinancialSummary
from app.schemas.technical import (
    BollingerSnapshot,
    EmaSnapshot,
    MacdSnapshot,
    MovingAverageSnapshot,
    TechnicalSnapshot,
    VolumeMetricsSnapshot,
)
from app.services.data_products.base import DataProductResult
from app.services.workspace_bundle_service.workspace_bundle_service import (
    WorkspaceBundleService,
)

from .test_decision_brief_service import (
    build_debate_review_report,
    build_factor_snapshot,
    build_review_report,
    build_strategy_plan,
    build_trigger_snapshot,
)


class _StubMarketDataService:
    def get_stock_profile(self, symbol: str) -> StockProfile:
        return StockProfile(
            symbol=symbol,
            code="600519",
            exchange="SH",
            name="Kweichow Moutai",
            industry="Liquor",
            list_date=date(2001, 8, 27),
            status="active",
            total_market_cap=1_800_000_000_000.0,
            circulating_market_cap=1_800_000_000_000.0,
            source="stub",
        )


class _StubTechnicalAnalysisService:
    def build_snapshot_from_bars(self, *, symbol: str, bars):
        return TechnicalSnapshot(
            symbol=symbol,
            as_of_date=date(2024, 1, 2),
            latest_close=101.2,
            latest_volume=1000.0,
            moving_averages=MovingAverageSnapshot(ma5=100.0, ma10=99.0, ma20=98.0),
            ema=EmaSnapshot(ema12=100.2, ema26=99.4),
            macd=MacdSnapshot(macd=1.2, signal=0.8, histogram=0.4),
            rsi14=58.0,
            atr14=2.5,
            bollinger=BollingerSnapshot(middle=100.0, upper=104.0, lower=96.0),
            volume_metrics=VolumeMetricsSnapshot(volume_ma5=900.0, volume_ma20=850.0),
            trend_state="up",
            trend_score=72,
            volatility_state="normal",
            support_level=100.0,
            resistance_level=105.0,
        )


class _StubResearchManager:
    def build_research_report(self, inputs) -> ResearchReport:
        return ResearchReport(
            symbol="600519.SH",
            name="Kweichow Moutai",
            as_of_date=date(2024, 1, 2),
            technical_score=72,
            fundamental_score=61,
            event_score=64,
            risk_score=35,
            overall_score=67,
            action="WATCH",
            confidence=66,
            thesis="Wait for a better pullback entry.",
            key_reasons=["Trend remains constructive."],
            risks=["Execution timing still matters."],
            triggers=["Watch the support zone."],
            invalidations=["Reassess if support breaks."],
        )


class _StubFactorSnapshotService:
    def build_from_inputs(self, inputs):
        return build_factor_snapshot()


class _StubStockReviewService:
    def build_review_report_from_components(self, **kwargs):
        return build_review_report()


class _FailingStockReviewService:
    def build_review_report_from_components(self, **kwargs):
        raise RuntimeError("review build failed")


class _StubDebateOrchestrator:
    def build_inputs_from_components(self, **kwargs):
        return type("Inputs", (), {"symbol": "600519.SH"})()


class _StubDebateRuntimeService:
    def get_debate_review_report_from_inputs(self, inputs, **kwargs):
        return build_debate_review_report()

    def get_debate_review_progress(self, symbol: str, **kwargs):
        return None


class _StubStrategyPlanner:
    def build_strategy_plan_from_components(self, **kwargs):
        return build_strategy_plan()


class _StubTriggerSnapshotService:
    def get_trigger_snapshot(self, symbol: str):
        return build_trigger_snapshot()

    def build_daily_fallback_trigger_snapshot(self, technical_snapshot):
        return build_trigger_snapshot()


class _StubDailyBarsDaily:
    def get(self, symbol: str, *, as_of_date=None, force_refresh: bool = False):
        resolved_as_of_date = as_of_date or date(2024, 1, 2)
        return DataProductResult(
            dataset="daily_bars_daily",
            symbol=symbol,
            as_of_date=resolved_as_of_date,
            payload=DailyBarResponse(
                symbol=symbol,
                start_date=date(2024, 1, 1),
                end_date=resolved_as_of_date,
                count=1,
                bars=[DailyBar(symbol=symbol, trade_date=resolved_as_of_date, close=101.2, source="stub")],
            ),
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubAnnouncementsDaily:
    def get(self, symbol: str, *, as_of_date=None, force_refresh: bool = False):
        resolved_as_of_date = as_of_date or date(2024, 1, 2)
        return DataProductResult(
            dataset="announcements_daily",
            symbol=symbol,
            as_of_date=resolved_as_of_date,
            payload=AnnouncementListResponse(symbol=symbol, count=0, items=[]),
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubFinancialSummaryDaily:
    def get(self, symbol: str, *, as_of_date=None, force_refresh: bool = False):
        resolved_as_of_date = as_of_date or date(2024, 1, 2)
        return DataProductResult(
            dataset="financial_summary_daily",
            symbol=symbol,
            as_of_date=resolved_as_of_date,
            payload=FinancialSummary(
                symbol=symbol,
                name="Kweichow Moutai",
                revenue=100.0,
                revenue_yoy=10.0,
                net_profit=20.0,
                net_profit_yoy=8.0,
                roe=18.0,
                debt_ratio=30.0,
                eps=2.5,
                source="stub",
            ),
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubFactorSnapshotDaily:
    def load(self, symbol: str, *, as_of_date):
        return None

    def save(self, symbol: str, payload):
        return DataProductResult(
            dataset="factor_snapshot_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubReviewReportDaily:
    def load(self, symbol: str, *, as_of_date):
        return None

    def save(self, symbol: str, payload):
        return DataProductResult(
            dataset="review_report_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubStrategyPlanDaily:
    def load(self, symbol: str, *, as_of_date):
        return None

    def save(self, symbol: str, payload):
        return DataProductResult(
            dataset="strategy_plan_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubDebateReviewDaily:
    def load(self, symbol: str, *, as_of_date, variant: str = "rule_based"):
        return None

    def save(self, symbol: str, payload, *, variant: str = "rule_based"):
        return DataProductResult(
            dataset="debate_review_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubDecisionBriefDaily:
    def load(self, symbol: str, *, as_of_date, variant: str = "rule_based"):
        return None

    def save(self, symbol: str, payload, *, variant: str = "rule_based"):
        return DataProductResult(
            dataset="decision_brief_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubPredictionService:
    def get_symbol_prediction(self, symbol: str, as_of_date):
        return PredictionSnapshotResponse(
            symbol=symbol,
            as_of_date=as_of_date,
            dataset_version=f"prediction_snapshot:{as_of_date.isoformat()}:{symbol}:baseline-rule-v1:v1",
            model_version="baseline-rule-v1",
            feature_version=f"features-{as_of_date.isoformat()}-v1",
            label_version="labels-v0-forward-return",
            predictive_score=68,
            upside_probability=0.68,
            expected_excess_return=0.045,
            model_confidence=0.7,
            runtime_mode="baseline",
            warning_messages=[],
            generated_at=datetime.now(),
            lineage_metadata=LineageMetadata(
                dataset="prediction_snapshot",
                dataset_version=f"prediction_snapshot:{as_of_date.isoformat()}:{symbol}:baseline-rule-v1:v1",
                generated_at=datetime.now(),
                as_of_date=as_of_date,
                symbol=symbol,
                dependencies=[],
                warning_messages=[],
            ),
        )


class _TrackingDailyBarsDaily(_StubDailyBarsDaily):
    def __init__(self) -> None:
        self.as_of_dates: list[date | None] = []

    def get(self, symbol: str, *, as_of_date=None, force_refresh: bool = False):
        self.as_of_dates.append(as_of_date)
        return super().get(symbol, as_of_date=as_of_date, force_refresh=force_refresh)


class _TrackingPredictionService(_StubPredictionService):
    def __init__(self) -> None:
        self.as_of_dates: list[date] = []

    def get_symbol_prediction(self, symbol: str, as_of_date):
        self.as_of_dates.append(as_of_date)
        return super().get_symbol_prediction(symbol, as_of_date)


class _ConcurrentTrackingDailyBarsDaily(_StubDailyBarsDaily):
    def __init__(self) -> None:
        self._lock = Lock()
        self.active_calls = 0
        self.max_active_calls = 0

    def get(self, symbol: str, *, as_of_date=None, force_refresh: bool = False):
        with self._lock:
            self.active_calls += 1
            if self.active_calls > self.max_active_calls:
                self.max_active_calls = self.active_calls
        try:
            sleep(0.15)
            return super().get(symbol, as_of_date=as_of_date, force_refresh=force_refresh)
        finally:
            with self._lock:
                self.active_calls -= 1


class _FailingPredictionService:
    def get_symbol_prediction(self, symbol: str, as_of_date):
        raise ValueError("feature dataset records 不存在：features-v0-baseline")


class _CachedReviewReportDaily(_StubReviewReportDaily):
    def load(self, symbol: str, *, as_of_date):
        payload = build_review_report().model_copy(
            update={
                "as_of_date": as_of_date,
            }
        )
        return DataProductResult(
            dataset="review_report_daily",
            symbol=symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _CachedStrategyPlanDaily(_StubStrategyPlanDaily):
    def load(self, symbol: str, *, as_of_date):
        payload = build_strategy_plan().model_copy(
            update={
                "as_of_date": as_of_date,
            }
        )
        return DataProductResult(
            dataset="strategy_plan_daily",
            symbol=symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _CachedDebateReviewDaily(_StubDebateReviewDaily):
    def __init__(self, *, llm_cached: bool = False, rule_cached: bool = False) -> None:
        self._llm_cached = llm_cached
        self._rule_cached = rule_cached

    def load(self, symbol: str, *, as_of_date, variant: str = "rule_based"):
        if variant == "llm" and not self._llm_cached:
            return None
        if variant == "rule_based" and not self._rule_cached:
            return None
        payload = build_debate_review_report().model_copy(
            update={
                "as_of_date": as_of_date,
                "runtime_mode": "llm" if variant == "llm" else "rule_based",
                "runtime_mode_effective": "llm" if variant == "llm" else "rule_based",
                "runtime_mode_requested": "llm" if variant == "llm" else "rule_based",
                "provider_used": variant,
            }
        )
        return DataProductResult(
            dataset="debate_review_daily",
            symbol=symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _FailingStrategyPlanner:
    def build_strategy_plan_from_components(self, **kwargs):
        raise RuntimeError("strategy should not be recomputed")


class _FailingReviewService:
    def build_review_report_from_components(self, **kwargs):
        raise RuntimeError("review should not be recomputed")


class _FailingDebateRuntimeService:
    def get_debate_review_report_from_inputs(self, inputs, **kwargs):
        raise RuntimeError("debate should not be recomputed")

    def get_debate_review_progress(self, symbol: str, **kwargs):
        return None


def test_workspace_bundle_service_returns_bundle_with_evidence_and_freshness() -> None:
    service = WorkspaceBundleService(
        market_data_service=_StubMarketDataService(),
        technical_analysis_service=_StubTechnicalAnalysisService(),
        research_manager=_StubResearchManager(),
        factor_snapshot_service=_StubFactorSnapshotService(),
        stock_review_service=_StubStockReviewService(),
        debate_orchestrator=_StubDebateOrchestrator(),
        debate_runtime_service=_StubDebateRuntimeService(),
        strategy_planner=_StubStrategyPlanner(),
        trigger_snapshot_service=_StubTriggerSnapshotService(),
        daily_bars_daily=_StubDailyBarsDaily(),
        announcements_daily=_StubAnnouncementsDaily(),
        financial_summary_daily=_StubFinancialSummaryDaily(),
        factor_snapshot_daily=_StubFactorSnapshotDaily(),
        review_report_daily=_StubReviewReportDaily(),
        strategy_plan_daily=_StubStrategyPlanDaily(),
        debate_review_daily=_StubDebateReviewDaily(),
        decision_brief_daily=_StubDecisionBriefDaily(),
        prediction_service=_StubPredictionService(),
    )

    bundle = service.get_workspace_bundle("600519.SH", use_llm=False)

    assert bundle.profile is not None
    assert bundle.factor_snapshot is not None
    assert bundle.decision_brief is not None
    assert bundle.predictive_snapshot is not None
    assert bundle.evidence_manifest is not None
    assert bundle.freshness_summary.items
    assert bundle.lineage_summary.items
    assert any(item.module_name == "decision_brief" for item in bundle.module_status_summary)
    assert bundle.runtime_mode_effective == "rule_based"
    assert bundle.fallback_applied is False
    assert any(item.item_name == "predictive_snapshot" for item in bundle.lineage_summary.items)


def test_workspace_bundle_service_returns_partial_bundle_when_module_fails() -> None:
    service = WorkspaceBundleService(
        market_data_service=_StubMarketDataService(),
        technical_analysis_service=_StubTechnicalAnalysisService(),
        research_manager=_StubResearchManager(),
        factor_snapshot_service=_StubFactorSnapshotService(),
        stock_review_service=_FailingStockReviewService(),
        debate_orchestrator=_StubDebateOrchestrator(),
        debate_runtime_service=_StubDebateRuntimeService(),
        strategy_planner=_StubStrategyPlanner(),
        trigger_snapshot_service=_StubTriggerSnapshotService(),
        daily_bars_daily=_StubDailyBarsDaily(),
        announcements_daily=_StubAnnouncementsDaily(),
        financial_summary_daily=_StubFinancialSummaryDaily(),
        factor_snapshot_daily=_StubFactorSnapshotDaily(),
        review_report_daily=_StubReviewReportDaily(),
        strategy_plan_daily=_StubStrategyPlanDaily(),
        debate_review_daily=_StubDebateReviewDaily(),
        decision_brief_daily=_StubDecisionBriefDaily(),
    )

    bundle = service.get_workspace_bundle("600519.SH", use_llm=False)

    assert bundle.profile is not None
    assert bundle.factor_snapshot is not None
    assert bundle.review_report is None
    assert bundle.debate_review is None
    assert bundle.module_status_summary
    review_status = next(
        item for item in bundle.module_status_summary if item.module_name == "review_report"
    )
    assert review_status.status == "error"
    assert bundle.fallback_applied is True
    assert bundle.fallback_reason == "One or more workspace modules failed and were skipped."
    assert bundle.warning_messages


def test_workspace_bundle_service_reuses_review_strategy_and_debate_snapshots() -> None:
    service = WorkspaceBundleService(
        market_data_service=_StubMarketDataService(),
        technical_analysis_service=_StubTechnicalAnalysisService(),
        research_manager=_StubResearchManager(),
        factor_snapshot_service=_StubFactorSnapshotService(),
        stock_review_service=_FailingReviewService(),
        debate_orchestrator=_StubDebateOrchestrator(),
        debate_runtime_service=_FailingDebateRuntimeService(),
        strategy_planner=_FailingStrategyPlanner(),
        trigger_snapshot_service=_StubTriggerSnapshotService(),
        daily_bars_daily=_StubDailyBarsDaily(),
        announcements_daily=_StubAnnouncementsDaily(),
        financial_summary_daily=_StubFinancialSummaryDaily(),
        factor_snapshot_daily=_StubFactorSnapshotDaily(),
        review_report_daily=_CachedReviewReportDaily(),
        strategy_plan_daily=_CachedStrategyPlanDaily(),
        debate_review_daily=_CachedDebateReviewDaily(rule_cached=True),
        decision_brief_daily=_StubDecisionBriefDaily(),
    )

    bundle = service.get_workspace_bundle("600519.SH", use_llm=False)

    assert bundle.review_report is not None
    assert bundle.strategy_plan is not None
    assert bundle.debate_review is not None
    assert bundle.review_report.freshness_mode == "cache_hit"
    assert bundle.strategy_plan.freshness_mode == "cache_hit"
    assert bundle.debate_review.freshness_mode == "cache_hit"
    assert bundle.fallback_applied is False


def test_workspace_bundle_service_use_llm_computes_live_when_llm_snapshot_missing() -> None:
    class _TrackingDebateRuntimeService:
        def __init__(self) -> None:
            self.calls: list[bool | None] = []

        def get_debate_review_report_from_inputs(self, inputs, **kwargs):
            self.calls.append(kwargs.get("use_llm"))
            return build_debate_review_report().model_copy(
                update={
                    "runtime_mode": "llm",
                    "runtime_mode_requested": "llm",
                    "runtime_mode_effective": "llm",
                    "provider_used": "llm",
                }
            )

        def get_debate_review_progress(self, symbol: str, **kwargs):
            return None

    runtime_service = _TrackingDebateRuntimeService()
    service = WorkspaceBundleService(
        market_data_service=_StubMarketDataService(),
        technical_analysis_service=_StubTechnicalAnalysisService(),
        research_manager=_StubResearchManager(),
        factor_snapshot_service=_StubFactorSnapshotService(),
        stock_review_service=_StubStockReviewService(),
        debate_orchestrator=_StubDebateOrchestrator(),
        debate_runtime_service=runtime_service,
        strategy_planner=_StubStrategyPlanner(),
        trigger_snapshot_service=_StubTriggerSnapshotService(),
        daily_bars_daily=_StubDailyBarsDaily(),
        announcements_daily=_StubAnnouncementsDaily(),
        financial_summary_daily=_StubFinancialSummaryDaily(),
        factor_snapshot_daily=_StubFactorSnapshotDaily(),
        review_report_daily=_StubReviewReportDaily(),
        strategy_plan_daily=_StubStrategyPlanDaily(),
        debate_review_daily=_CachedDebateReviewDaily(rule_cached=True, llm_cached=False),
        decision_brief_daily=_StubDecisionBriefDaily(),
    )

    bundle = service.get_workspace_bundle("600519.SH", use_llm=True)

    assert bundle.debate_review is not None
    assert runtime_service.calls == [True]
    assert bundle.debate_review.runtime_mode_requested == "llm"
    assert bundle.debate_review.runtime_mode_effective == "llm"
    assert bundle.debate_review.fallback_applied is False
    assert bundle.runtime_mode_requested == "llm"
    assert bundle.runtime_mode_effective == "llm"
    assert any(
        item.module_name == "debate_review" and item.status == "success"
        for item in bundle.module_status_summary
    )


def test_workspace_bundle_service_skips_predictive_snapshot_when_assets_missing() -> None:
    service = WorkspaceBundleService(
        market_data_service=_StubMarketDataService(),
        technical_analysis_service=_StubTechnicalAnalysisService(),
        research_manager=_StubResearchManager(),
        factor_snapshot_service=_StubFactorSnapshotService(),
        stock_review_service=_StubStockReviewService(),
        debate_orchestrator=_StubDebateOrchestrator(),
        debate_runtime_service=_StubDebateRuntimeService(),
        strategy_planner=_StubStrategyPlanner(),
        trigger_snapshot_service=_StubTriggerSnapshotService(),
        daily_bars_daily=_StubDailyBarsDaily(),
        announcements_daily=_StubAnnouncementsDaily(),
        financial_summary_daily=_StubFinancialSummaryDaily(),
        factor_snapshot_daily=_StubFactorSnapshotDaily(),
        review_report_daily=_StubReviewReportDaily(),
        strategy_plan_daily=_StubStrategyPlanDaily(),
        debate_review_daily=_StubDebateReviewDaily(),
        decision_brief_daily=_StubDecisionBriefDaily(),
        prediction_service=_FailingPredictionService(),
    )

    bundle = service.get_workspace_bundle("600519.SH", use_llm=False)

    assert bundle.predictive_snapshot is None
    predictive_status = next(
        item
        for item in bundle.module_status_summary
        if item.module_name == "predictive_snapshot"
    )
    assert predictive_status.status == "skipped"
    assert bundle.fallback_applied is False


def test_workspace_bundle_service_uses_explicit_as_of_date() -> None:
    tracking_daily_bars = _TrackingDailyBarsDaily()
    tracking_prediction_service = _TrackingPredictionService()
    service = WorkspaceBundleService(
        market_data_service=_StubMarketDataService(),
        technical_analysis_service=_StubTechnicalAnalysisService(),
        research_manager=_StubResearchManager(),
        factor_snapshot_service=_StubFactorSnapshotService(),
        stock_review_service=_StubStockReviewService(),
        debate_orchestrator=_StubDebateOrchestrator(),
        debate_runtime_service=_StubDebateRuntimeService(),
        strategy_planner=_StubStrategyPlanner(),
        trigger_snapshot_service=_StubTriggerSnapshotService(),
        daily_bars_daily=tracking_daily_bars,
        announcements_daily=_StubAnnouncementsDaily(),
        financial_summary_daily=_StubFinancialSummaryDaily(),
        factor_snapshot_daily=_StubFactorSnapshotDaily(),
        review_report_daily=_StubReviewReportDaily(),
        strategy_plan_daily=_StubStrategyPlanDaily(),
        debate_review_daily=_StubDebateReviewDaily(),
        decision_brief_daily=_StubDecisionBriefDaily(),
        prediction_service=tracking_prediction_service,
    )

    bundle = service.get_workspace_bundle(
        "600519.SH",
        use_llm=False,
        as_of_date=date(2024, 1, 5),
    )

    assert tracking_daily_bars.as_of_dates == [date(2024, 1, 5)]
    assert tracking_prediction_service.as_of_dates == [date(2024, 1, 5)]
    assert bundle.freshness_summary.default_as_of_date == date(2024, 1, 5)


def test_workspace_bundle_service_serializes_same_key_requests() -> None:
    tracking_daily_bars = _ConcurrentTrackingDailyBarsDaily()
    service = WorkspaceBundleService(
        market_data_service=_StubMarketDataService(),
        technical_analysis_service=_StubTechnicalAnalysisService(),
        research_manager=_StubResearchManager(),
        factor_snapshot_service=_StubFactorSnapshotService(),
        stock_review_service=_StubStockReviewService(),
        debate_orchestrator=_StubDebateOrchestrator(),
        debate_runtime_service=_StubDebateRuntimeService(),
        strategy_planner=_StubStrategyPlanner(),
        trigger_snapshot_service=_StubTriggerSnapshotService(),
        daily_bars_daily=tracking_daily_bars,
        announcements_daily=_StubAnnouncementsDaily(),
        financial_summary_daily=_StubFinancialSummaryDaily(),
        factor_snapshot_daily=_StubFactorSnapshotDaily(),
        review_report_daily=_StubReviewReportDaily(),
        strategy_plan_daily=_StubStrategyPlanDaily(),
        debate_review_daily=_StubDebateReviewDaily(),
        decision_brief_daily=_StubDecisionBriefDaily(),
        prediction_service=_StubPredictionService(),
    )

    bundles: list = []

    def _run_bundle() -> None:
        bundles.append(service.get_workspace_bundle("600519.SH", use_llm=False))

    threads = [Thread(target=_run_bundle), Thread(target=_run_bundle)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(bundles) == 2
    assert tracking_daily_bars.max_active_calls == 1
