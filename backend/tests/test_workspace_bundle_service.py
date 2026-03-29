"""Tests for the stock workspace bundle service."""

from __future__ import annotations

from datetime import date, datetime

from app.schemas.market_data import DailyBar, DailyBarResponse, StockProfile
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
    def get(self, symbol: str, force_refresh: bool = False):
        return DataProductResult(
            dataset="daily_bars_daily",
            symbol=symbol,
            as_of_date=date(2024, 1, 2),
            payload=DailyBarResponse(
                symbol=symbol,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 2),
                count=1,
                bars=[DailyBar(symbol=symbol, trade_date=date(2024, 1, 2), close=101.2, source="stub")],
            ),
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubAnnouncementsDaily:
    def get(self, symbol: str, force_refresh: bool = False):
        return DataProductResult(
            dataset="announcements_daily",
            symbol=symbol,
            as_of_date=date(2024, 1, 2),
            payload=AnnouncementListResponse(symbol=symbol, count=0, items=[]),
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=datetime.now(),
        )


class _StubFinancialSummaryDaily:
    def get(self, symbol: str, force_refresh: bool = False):
        return DataProductResult(
            dataset="financial_summary_daily",
            symbol=symbol,
            as_of_date=date(2024, 1, 2),
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
        decision_brief_daily=_StubDecisionBriefDaily(),
    )

    bundle = service.get_workspace_bundle("600519.SH", use_llm=False)

    assert bundle.profile is not None
    assert bundle.factor_snapshot is not None
    assert bundle.decision_brief is not None
    assert bundle.evidence_manifest is not None
    assert bundle.freshness_summary.items
    assert any(item.module_name == "decision_brief" for item in bundle.module_status_summary)


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
