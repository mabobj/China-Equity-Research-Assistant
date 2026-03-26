"""受控 LLM 裁决编排器。"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from app.schemas.debate import (
    AnalystView,
    AnalystViewsBundle,
    BearCase,
    BullCase,
    ChiefJudgement,
    ChiefJudgementBuild,
    DebateReviewReport,
    RiskReview,
    SingleStockResearchInputs,
)
from app.services.debate_service.debate_orchestrator import DebateOrchestrator
from app.services.llm_debate_service.base import RoleName
from app.services.llm_debate_service.llm_role_runner import LLMRoleRunner
from app.services.llm_debate_service.progress_tracker import DebateProgressTracker

_TOTAL_LLM_DEBATE_STEPS = 9


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
        progress_tracker: DebateProgressTracker | None = None,
    ) -> None:
        self._debate_orchestrator = debate_orchestrator
        self._role_runner = role_runner
        self._progress_tracker = progress_tracker

    def get_debate_review_report(
        self,
        symbol: str,
        *,
        request_id: str | None = None,
    ) -> DebateReviewReport:
        """返回 LLM 版角色化裁决报告。"""
        self._update_progress(
            symbol=symbol,
            request_id=request_id,
            stage="building_inputs",
            current_step="构建研究输入",
            completed_steps=0,
            total_steps=_TOTAL_LLM_DEBATE_STEPS,
            message="正在整理 review / factor / strategy 输入。",
        )
        inputs = self._debate_orchestrator.build_inputs(symbol)

        analyst_views = self._build_analyst_views(inputs, request_id=request_id)
        bull_case = self._build_bull_case(inputs, analyst_views, request_id=request_id)
        bear_case = self._build_bear_case(inputs, analyst_views, request_id=request_id)
        chief_judgement = self._build_chief_judgement(
            inputs=inputs,
            analyst_views=analyst_views,
            bull_case=bull_case,
            bear_case=bear_case,
            request_id=request_id,
        )
        risk_review = self._build_risk_review(inputs, request_id=request_id)

        self._update_progress(
            symbol=symbol,
            request_id=request_id,
            stage="finalizing",
            current_step="收束策略与风险复核",
            completed_steps=8,
            total_steps=_TOTAL_LLM_DEBATE_STEPS,
            message="正在生成最终裁决和策略摘要。",
        )
        finalize_node = self._debate_orchestrator.finalize_strategy(
            inputs,
            ChiefJudgementBuild(
                symbol=inputs.symbol,
                chief_judgement=chief_judgement,
                risk_review=risk_review,
            ),
        )

        report = DebateReviewReport(
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
        self._update_progress(
            symbol=symbol,
            request_id=request_id,
            status="completed",
            stage="completed",
            current_step="LLM 裁决完成",
            completed_steps=_TOTAL_LLM_DEBATE_STEPS,
            total_steps=_TOTAL_LLM_DEBATE_STEPS,
            message="LLM debate-review 已完成。",
        )
        return report

    def _build_analyst_views(
        self,
        inputs: SingleStockResearchInputs,
        *,
        request_id: str | None,
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
            request_id=request_id,
            step_index=1,
            step_label="技术分析员",
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
            request_id=request_id,
            step_index=2,
            step_label="基本面分析员",
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
            request_id=request_id,
            step_index=3,
            step_label="事件分析员",
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
            request_id=request_id,
            step_index=4,
            step_label="情绪分析员",
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
        *,
        request_id: str | None,
    ) -> BullCase:
        return self._run_role(
            role="bull_researcher",
            role_input={
                "symbol": inputs.review_report.symbol,
                "name": inputs.review_report.name,
                "analyst_views": analyst_views.model_dump(mode="json"),
            },
            output_model=BullCase,
            request_id=request_id,
            step_index=5,
            step_label="多头研究员",
        )

    def _build_bear_case(
        self,
        inputs: SingleStockResearchInputs,
        analyst_views: AnalystViewsBundle,
        *,
        request_id: str | None,
    ) -> BearCase:
        return self._run_role(
            role="bear_researcher",
            role_input={
                "symbol": inputs.review_report.symbol,
                "name": inputs.review_report.name,
                "analyst_views": analyst_views.model_dump(mode="json"),
            },
            output_model=BearCase,
            request_id=request_id,
            step_index=6,
            step_label="空头研究员",
        )

    def _build_chief_judgement(
        self,
        *,
        inputs: SingleStockResearchInputs,
        analyst_views: AnalystViewsBundle,
        bull_case: BullCase,
        bear_case: BearCase,
        request_id: str | None,
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
            request_id=request_id,
            step_index=7,
            step_label="首席分析员",
        )

    def _build_risk_review(
        self,
        inputs: SingleStockResearchInputs,
        *,
        request_id: str | None,
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
            request_id=request_id,
            step_index=8,
            step_label="风险复核员",
        )

    def _run_role(
        self,
        *,
        role: RoleName,
        role_input: dict[str, object],
        output_model,
        request_id: str | None,
        step_index: int,
        step_label: str,
    ):
        symbol = str(role_input.get("symbol", ""))
        self._update_progress(
            symbol=symbol,
            request_id=request_id,
            stage="running_roles",
            current_step=f"正在执行：{step_label}",
            completed_steps=step_index - 1,
            total_steps=_TOTAL_LLM_DEBATE_STEPS,
            message=f"后台正在运行 {step_label}。",
        )
        return self._role_runner.run_role(
            role=role,
            role_input=role_input,
            output_model=output_model,
        )

    def _update_progress(
        self,
        *,
        symbol: str,
        request_id: str | None,
        stage: str,
        current_step: str,
        completed_steps: int,
        total_steps: int,
        message: str,
        status: str = "running",
    ) -> None:
        if self._progress_tracker is None:
            return
        self._progress_tracker.update(
            symbol=symbol,
            request_id=request_id,
            status=status,
            stage=stage,
            runtime_mode="llm",
            current_step=current_step,
            completed_steps=completed_steps,
            total_steps=total_steps,
            message=message,
        )
