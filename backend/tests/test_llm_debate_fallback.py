"""LLM debate 回退逻辑测试。"""

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


def _build_rule_based_report() -> DebateReviewReport:
    return DebateReviewReport(
        symbol="600519.SH",
        name="贵州茅台",
        as_of_date=date(2024, 3, 25),
        analyst_views=AnalystViewsBundle(
            technical=AnalystView(
                role="technical_analyst",
                summary="规则版技术观点",
                action_bias="supportive",
                positive_points=[DebatePoint(title="趋势", detail="趋势向上。")],
                caution_points=[],
                key_levels=["支撑位 1660"],
            ),
            fundamental=AnalystView(
                role="fundamental_analyst",
                summary="规则版基本面观点",
                action_bias="neutral",
                positive_points=[],
                caution_points=[],
                key_levels=[],
            ),
            event=AnalystView(
                role="event_analyst",
                summary="规则版事件观点",
                action_bias="neutral",
                positive_points=[],
                caution_points=[],
                key_levels=[],
            ),
            sentiment=AnalystView(
                role="sentiment_analyst",
                summary="规则版情绪观点",
                action_bias="neutral",
                positive_points=[],
                caution_points=[],
                key_levels=[],
            ),
        ),
        bull_case=BullCase(
            summary="规则版多头理由",
            reasons=[DebatePoint(title="趋势", detail="趋势占优。")],
        ),
        bear_case=BearCase(
            summary="规则版空头理由",
            reasons=[DebatePoint(title="执行", detail="等待更优位置。")],
        ),
        key_disagreements=["执行时点仍有分歧"],
        chief_judgement=ChiefJudgement(
            final_action="WATCH",
            summary="规则版最终裁决",
            decisive_points=["先观察"],
            key_disagreements=["执行时点仍有分歧"],
        ),
        risk_review=RiskReview(
            risk_level="medium",
            summary="规则版风险结论",
            execution_reminders=["严格止损。"],
        ),
        final_action="WATCH",
        strategy_summary=StrategySummary(
            action="WATCH",
            strategy_type="wait",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=1650.0, high=1665.0),
            stop_loss_price=1630.0,
            take_profit_range=PriceRange(low=1710.0, high=1740.0),
            review_timeframe="daily_close_review",
            concise_summary="等待更优位置。",
        ),
        confidence=70,
        runtime_mode="rule_based",
    )


class StubRuleBasedOrchestrator:
    def get_debate_review_report(self, symbol: str) -> DebateReviewReport:
        return _build_rule_based_report()


class StubLLMOrchestrator:
    def __init__(self, *, should_fail: bool = False) -> None:
        self._should_fail = should_fail

    def get_debate_review_report(self, symbol: str) -> DebateReviewReport:
        if self._should_fail:
            raise RuntimeError("llm failed")
        return _build_rule_based_report().model_copy(update={"runtime_mode": "llm"})


def test_debate_runtime_service_falls_back_when_disabled() -> None:
    service = DebateRuntimeService(
        rule_based_orchestrator=StubRuleBasedOrchestrator(),
        llm_orchestrator=StubLLMOrchestrator(),
        settings=LLMDebateSettings(
            enabled=False,
            api_key="test-key",
            model="gpt-test",
            base_url=None,
            timeout_seconds=10,
        ),
    )

    report = service.get_debate_review_report("600519.SH", use_llm=True)

    assert report.runtime_mode == "rule_based"
    assert report.runtime_mode_requested == "llm"
    assert report.runtime_mode_effective == "rule_based"
    assert report.fallback_applied is True
    assert report.fallback_reason == "LLM debate is disabled by configuration."
    assert report.provider_used == "rule_based"


def test_debate_runtime_service_falls_back_when_llm_fails() -> None:
    service = DebateRuntimeService(
        rule_based_orchestrator=StubRuleBasedOrchestrator(),
        llm_orchestrator=StubLLMOrchestrator(should_fail=True),
        settings=LLMDebateSettings(
            enabled=True,
            api_key="test-key",
            model="gpt-test",
            base_url=None,
            timeout_seconds=10,
        ),
    )

    report = service.get_debate_review_report("600519.SH", use_llm=True)

    assert report.runtime_mode == "rule_based"
    assert report.runtime_mode_requested == "llm"
    assert report.runtime_mode_effective == "rule_based"
    assert report.fallback_applied is True
    assert report.fallback_reason == "LLM runtime failed or timed out."
    assert report.provider_used == "rule_based"


def test_debate_runtime_service_uses_llm_when_available() -> None:
    service = DebateRuntimeService(
        rule_based_orchestrator=StubRuleBasedOrchestrator(),
        llm_orchestrator=StubLLMOrchestrator(),
        settings=LLMDebateSettings(
            enabled=True,
            api_key="test-key",
            model="gpt-test",
            base_url=None,
            timeout_seconds=10,
        ),
    )

    report = service.get_debate_review_report("600519.SH", use_llm=True)

    assert report.runtime_mode == "llm"
    assert report.runtime_mode_requested == "llm"
    assert report.runtime_mode_effective == "llm"
    assert report.fallback_applied is False
    assert report.provider_used == "llm"
