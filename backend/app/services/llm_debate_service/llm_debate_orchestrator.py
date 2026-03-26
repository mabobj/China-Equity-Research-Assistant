"""受控 LLM 裁决编排器。"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from app.schemas.debate import (
    AnalystView,
    AnalystViewsBundle,
    BullCase,
    ChiefJudgement,
    ChiefJudgementBuild,
    DebateReviewReport,
    RiskReview,
    SingleStockResearchInputs,
    BearCase,
)
from app.services.debate_service.debate_orchestrator import DebateOrchestrator
from app.services.llm_debate_service.base import RoleName
from app.services.llm_debate_service.llm_role_runner import LLMRoleRunner


class TechnicalAnalystOutput(AnalystView):
    """技术角色的固定输出。"""

    model_config = ConfigDict(extra="forbid")
    role: Literal["technical_analyst"] = "technical_analyst"


class FundamentalAnalystOutput(AnalystView):
    """基本面角色的固定输出。"""

    model_config = ConfigDict(extra="forbid")
    role: Literal["fundamental_analyst"] = "fundamental_analyst"


class EventAnalystOutput(AnalystView):
    """事件角色的固定输出。"""

    model_config = ConfigDict(extra="forbid")
    role: Literal["event_analyst"] = "event_analyst"


class SentimentAnalystOutput(AnalystView):
    """情绪角色的固定输出。"""

    model_config = ConfigDict(extra="forbid")
    role: Literal["sentiment_analyst"] = "sentiment_analyst"


class LLMDebateOrchestrator:
    """在固定角色、固定轮次下执行一次受控 LLM 裁决。"""

    def __init__(
        self,
        debate_orchestrator: DebateOrchestrator,
        role_runner: LLMRoleRunner,
    ) -> None:
        self._debate_orchestrator = debate_orchestrator
        self._role_runner = role_runner

    def get_debate_review_report(self, symbol: str) -> DebateReviewReport:
        """返回 LLM 版角色化裁决报告。"""
        inputs = self._debate_orchestrator.build_inputs(symbol)
        analyst_views = self._build_analyst_views(inputs)
        bull_case = self._build_bull_case(inputs, analyst_views)
        bear_case = self._build_bear_case(inputs, analyst_views)
        chief_judgement = self._build_chief_judgement(
            inputs=inputs,
            analyst_views=analyst_views,
            bull_case=bull_case,
            bear_case=bear_case,
        )
        risk_review = self._build_risk_review(inputs)
        finalize_node = self._debate_orchestrator.finalize_strategy(
            inputs,
            ChiefJudgementBuild(
                symbol=inputs.symbol,
                chief_judgement=chief_judgement,
                risk_review=risk_review,
            ),
        )

        return DebateReviewReport(
            symbol=inputs.review_report.symbol,
            name=inputs.review_report.name,
            as_of_date=inputs.review_report.as_of_date,
            analyst_views=analyst_views,
            bull_case=bull_case,
            bear_case=bear_case,
            key_disagreements=chief_judgement.key_disagreements,
            chief_judgement=chief_judgement,
            risk_review=risk_review,
            final_action=finalize_node.final_action,
            strategy_summary=finalize_node.strategy_summary,
            confidence=finalize_node.confidence,
            runtime_mode="llm",
        )

    def _build_analyst_views(
        self,
        inputs: SingleStockResearchInputs,
    ) -> AnalystViewsBundle:
        review_report = inputs.review_report

        technical = self._run_role(
            role="technical_analyst",
            role_input={
                "symbol": review_report.symbol,
                "name": review_report.name,
                "as_of_date": review_report.as_of_date.isoformat(),
                "technical_view": review_report.technical_view.model_dump(mode="json"),
                "strategy_summary": review_report.strategy_summary.model_dump(mode="json"),
            },
            output_model=TechnicalAnalystOutput,
        )
        fundamental = self._run_role(
            role="fundamental_analyst",
            role_input={
                "symbol": review_report.symbol,
                "name": review_report.name,
                "as_of_date": review_report.as_of_date.isoformat(),
                "fundamental_view": review_report.fundamental_view.model_dump(mode="json"),
                "factor_profile": review_report.factor_profile.model_dump(mode="json"),
            },
            output_model=FundamentalAnalystOutput,
        )
        event = self._run_role(
            role="event_analyst",
            role_input={
                "symbol": review_report.symbol,
                "name": review_report.name,
                "as_of_date": review_report.as_of_date.isoformat(),
                "event_view": review_report.event_view.model_dump(mode="json"),
                "factor_profile": review_report.factor_profile.model_dump(mode="json"),
            },
            output_model=EventAnalystOutput,
        )
        sentiment = self._run_role(
            role="sentiment_analyst",
            role_input={
                "symbol": review_report.symbol,
                "name": review_report.name,
                "as_of_date": review_report.as_of_date.isoformat(),
                "sentiment_view": review_report.sentiment_view.model_dump(mode="json"),
                "technical_view": review_report.technical_view.model_dump(mode="json"),
                "factor_profile": review_report.factor_profile.model_dump(mode="json"),
            },
            output_model=SentimentAnalystOutput,
        )

        return AnalystViewsBundle(
            technical=technical,
            fundamental=fundamental,
            event=event,
            sentiment=sentiment,
        )

    def _build_bull_case(
        self,
        inputs: SingleStockResearchInputs,
        analyst_views: AnalystViewsBundle,
    ) -> BullCase:
        return self._run_role(
            role="bull_researcher",
            role_input={
                "symbol": inputs.review_report.symbol,
                "name": inputs.review_report.name,
                "analyst_views": analyst_views.model_dump(mode="json"),
            },
            output_model=BullCase,
        )

    def _build_bear_case(
        self,
        inputs: SingleStockResearchInputs,
        analyst_views: AnalystViewsBundle,
    ) -> BearCase:
        return self._run_role(
            role="bear_researcher",
            role_input={
                "symbol": inputs.review_report.symbol,
                "name": inputs.review_report.name,
                "analyst_views": analyst_views.model_dump(mode="json"),
            },
            output_model=BearCase,
        )

    def _build_chief_judgement(
        self,
        *,
        inputs: SingleStockResearchInputs,
        analyst_views: AnalystViewsBundle,
        bull_case: BullCase,
        bear_case: BearCase,
    ) -> ChiefJudgement:
        return self._run_role(
            role="chief_analyst",
            role_input={
                "symbol": inputs.review_report.symbol,
                "name": inputs.review_report.name,
                "factor_profile": inputs.review_report.factor_profile.model_dump(mode="json"),
                "strategy_summary": inputs.review_report.strategy_summary.model_dump(mode="json"),
                "analyst_views": analyst_views.model_dump(mode="json"),
                "bull_case": bull_case.model_dump(mode="json"),
                "bear_case": bear_case.model_dump(mode="json"),
            },
            output_model=ChiefJudgement,
        )

    def _build_risk_review(
        self,
        inputs: SingleStockResearchInputs,
    ) -> RiskReview:
        return self._run_role(
            role="risk_reviewer",
            role_input={
                "symbol": inputs.review_report.symbol,
                "name": inputs.review_report.name,
                "factor_profile": inputs.review_report.factor_profile.model_dump(mode="json"),
                "technical_view": inputs.review_report.technical_view.model_dump(mode="json"),
                "strategy_summary": inputs.review_report.strategy_summary.model_dump(mode="json"),
            },
            output_model=RiskReview,
        )

    def _run_role(
        self,
        *,
        role: RoleName,
        role_input: dict[str, object],
        output_model,
    ):
        return self._role_runner.run_role(
            role=role,
            role_input=role_input,
            output_model=output_model,
        )
