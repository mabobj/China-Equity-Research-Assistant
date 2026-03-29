"""Regression tests for LLM debate import wiring."""

from __future__ import annotations

from datetime import date

from app.schemas.debate import (
    AnalystView,
    AnalystViewsBundle,
    BearCase,
    BullCase,
    ChiefJudgement,
    DebatePoint,
    DebateReviewReport,
    RiskReview,
)
from app.schemas.review import StrategySummary
from app.schemas.strategy import PriceRange
from app.services.llm_debate_service.base import LLMDebateSettings
from app.services.llm_debate_service.fallback import DebateRuntimeService


class _StubRuleOrchestrator:
    def build_inputs(self, symbol: str):
        class _Inputs:
            def __init__(self, symbol: str) -> None:
                self.symbol = symbol

        return _Inputs(symbol)

    def get_debate_review_report_from_inputs(self, inputs) -> DebateReviewReport:
        return _build_report(inputs.symbol, runtime_mode="rule_based")


class _StubLLMOrchestrator:
    def get_debate_review_report(self, symbol: str, request_id: str | None = None):
        return _build_report(symbol, runtime_mode="llm")

    def get_debate_review_report_from_inputs(self, inputs, request_id: str | None = None):
        return _build_report(inputs.symbol, runtime_mode="llm")


def test_debate_runtime_service_import_path_is_stable_for_rule_based_mode() -> None:
    """Direct submodule imports should work without package-level circular imports."""
    service = DebateRuntimeService(
        rule_based_orchestrator=_StubRuleOrchestrator(),
        llm_orchestrator=_StubLLMOrchestrator(),
        settings=LLMDebateSettings(
            enabled=True,
            api_key=None,
            model="stub-model",
            base_url=None,
            timeout_seconds=20,
            provider="auto",
        ),
    )

    report = service.get_debate_review_report("600519.SH", use_llm=False)

    assert report.symbol == "600519.SH"
    assert report.runtime_mode == "rule_based"
    assert report.final_action == "WATCH"


def _build_report(symbol: str, runtime_mode: str) -> DebateReviewReport:
    return DebateReviewReport(
        symbol=symbol,
        name="Kweichow Moutai",
        as_of_date=date(2024, 1, 2),
        analyst_views=AnalystViewsBundle(
            technical=_build_analyst("technical_analyst"),
            fundamental=_build_analyst("fundamental_analyst"),
            event=_build_analyst("event_analyst"),
            sentiment=_build_analyst("sentiment_analyst"),
        ),
        bull_case=BullCase(
            summary="Bull case",
            reasons=[DebatePoint(title="Positive", detail="Trend remains constructive.")],
        ),
        bear_case=BearCase(
            summary="Bear case",
            reasons=[DebatePoint(title="Risk", detail="Position still needs patience.")],
        ),
        key_disagreements=["Timing is the main disagreement."],
        chief_judgement=ChiefJudgement(
            final_action="WATCH",
            summary="Wait for a better entry.",
            decisive_points=["Execution timing matters more than direction."],
            key_disagreements=["Direction is fine, position is not perfect."],
        ),
        risk_review=RiskReview(
            risk_level="medium",
            summary="Risk is manageable with discipline.",
            execution_reminders=["Use the stop-loss reference."],
        ),
        final_action="WATCH",
        strategy_summary=StrategySummary(
            action="WATCH",
            strategy_type="pullback",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=99.5, high=100.5),
            stop_loss_price=98.0,
            take_profit_range=PriceRange(low=104.0, high=106.0),
            review_timeframe="daily_close_review",
            concise_summary="Wait for a pullback.",
        ),
        confidence=64,
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
    )


def _build_analyst(role: str) -> AnalystView:
    return AnalystView(
        role=role,  # type: ignore[arg-type]
        summary="Structured stub summary.",
        action_bias="neutral",
        positive_points=[DebatePoint(title="Support", detail="Supportive evidence exists.")],
        caution_points=[DebatePoint(title="Caution", detail="Need cleaner execution timing.")],
        key_levels=[],
    )
