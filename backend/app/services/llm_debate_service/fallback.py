"""Runtime facade for rule-based and LLM debate execution."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.schemas.debate import DebateReviewProgress, DebateReviewReport, SingleStockResearchInputs
from app.services.llm_debate_service.base import LLMDebateSettings
from app.services.llm_debate_service.progress_tracker import DebateProgressTracker

if TYPE_CHECKING:
    from app.services.debate_service.debate_orchestrator import DebateOrchestrator
    from app.services.llm_debate_service.llm_debate_orchestrator import LLMDebateOrchestrator

logger = logging.getLogger(__name__)


class DebateRuntimeService:
    """Choose LLM or rule-based debate execution with controlled fallback."""

    def __init__(
        self,
        rule_based_orchestrator: DebateOrchestrator,
        llm_orchestrator: LLMDebateOrchestrator,
        settings: LLMDebateSettings,
        progress_tracker: DebateProgressTracker | None = None,
    ) -> None:
        self._rule_based_orchestrator = rule_based_orchestrator
        self._llm_orchestrator = llm_orchestrator
        self._settings = settings
        self._progress_tracker = progress_tracker or DebateProgressTracker()

    def get_debate_review_report(
        self,
        symbol: str,
        use_llm: bool | None = None,
        request_id: str | None = None,
    ) -> DebateReviewReport:
        requested_llm = self._settings.enabled if use_llm is None else use_llm
        should_use_llm = self._settings.enabled and requested_llm
        logger.debug(
            "debate.runtime.select symbol=%s requested_use_llm=%s env_enabled=%s resolved_use_llm=%s",
            symbol,
            use_llm,
            self._settings.enabled,
            should_use_llm,
        )
        if not should_use_llm:
            return self._get_rule_based_report(
                symbol=symbol,
                request_id=request_id,
                reason_message="Using the rule-based debate runtime.",
            )

        self._progress_tracker.start(
            symbol=symbol,
            request_id=request_id,
            runtime_mode="llm",
            message="LLM debate-review submitted and waiting for role execution.",
        )

        if not self._settings.api_key:
            logger.info(
                "debate.runtime.llm_unavailable symbol=%s reason=missing_api_key",
                symbol,
            )
            self._progress_tracker.update(
                symbol=symbol,
                request_id=request_id,
                status="fallback",
                stage="fallback_rule_based",
                runtime_mode="llm",
                current_step="Switching to rule-based debate",
                completed_steps=0,
                total_steps=0,
                message="LLM API key is missing; switched to rule-based debate.",
            )
            return self._get_rule_based_report(
                symbol=symbol,
                request_id=request_id,
                reason_message="LLM is unavailable, switched to rule-based debate.",
            )

        try:
            return self._call_llm_report(symbol=symbol, request_id=request_id)
        except Exception as exc:
            logger.warning(
                "debate.runtime.llm_failed symbol=%s error=%s",
                symbol,
                exc,
            )
            self._progress_tracker.update(
                symbol=symbol,
                request_id=request_id,
                status="fallback",
                stage="fallback_rule_based",
                runtime_mode="llm",
                current_step="Switching to rule-based debate",
                completed_steps=0,
                total_steps=0,
                message="LLM debate failed; switched to rule-based debate.",
                error_message=str(exc),
            )
            return self._get_rule_based_report(
                symbol=symbol,
                request_id=request_id,
                reason_message="LLM failed, switched to rule-based debate.",
            )

    def get_debate_review_report_from_inputs(
        self,
        inputs: SingleStockResearchInputs,
        *,
        use_llm: bool | None = None,
        request_id: str | None = None,
    ) -> DebateReviewReport:
        requested_llm = self._settings.enabled if use_llm is None else use_llm
        should_use_llm = self._settings.enabled and requested_llm
        if not should_use_llm:
            return self._get_rule_based_report_from_inputs(
                inputs=inputs,
                request_id=request_id,
                reason_message="Using the rule-based debate runtime.",
            )

        self._progress_tracker.start(
            symbol=inputs.symbol,
            request_id=request_id,
            runtime_mode="llm",
            message="LLM debate-review submitted and waiting for role execution.",
        )

        if not self._settings.api_key:
            return self._get_rule_based_report_from_inputs(
                inputs=inputs,
                request_id=request_id,
                reason_message="LLM is unavailable, switched to rule-based debate.",
            )

        try:
            return self._call_llm_report_from_inputs(
                inputs=inputs,
                request_id=request_id,
            )
        except Exception as exc:
            logger.warning(
                "debate.runtime.llm_failed symbol=%s error=%s",
                inputs.symbol,
                exc,
            )
            self._progress_tracker.update(
                symbol=inputs.symbol,
                request_id=request_id,
                status="fallback",
                stage="fallback_rule_based",
                runtime_mode="llm",
                current_step="Switching to rule-based debate",
                completed_steps=0,
                total_steps=0,
                message="LLM debate failed; switched to rule-based debate.",
                error_message=str(exc),
            )
            return self._get_rule_based_report_from_inputs(
                inputs=inputs,
                request_id=request_id,
                reason_message="LLM failed, switched to rule-based debate.",
            )

    def get_debate_review_progress(
        self,
        symbol: str,
        *,
        request_id: str | None = None,
        use_llm: bool | None = None,
    ) -> DebateReviewProgress:
        runtime_mode = (
            "llm"
            if (self._settings.enabled and (use_llm if use_llm is not None else True))
            else "rule_based"
        )
        return self._progress_tracker.get(
            symbol=symbol,
            request_id=request_id,
            runtime_mode=runtime_mode,
        )

    def _get_rule_based_report(
        self,
        *,
        symbol: str,
        request_id: str | None,
        reason_message: str,
    ) -> DebateReviewReport:
        build_inputs = getattr(self._rule_based_orchestrator, "build_inputs", None)
        if not callable(build_inputs):
            report = self._rule_based_orchestrator.get_debate_review_report(symbol)
            return report.model_copy(update={"runtime_mode": "rule_based"})

        inputs = build_inputs(symbol)
        return self._get_rule_based_report_from_inputs(
            inputs=inputs,
            request_id=request_id,
            reason_message=reason_message,
        )

    def _get_rule_based_report_from_inputs(
        self,
        *,
        inputs: SingleStockResearchInputs,
        request_id: str | None,
        reason_message: str,
    ) -> DebateReviewReport:
        self._progress_tracker.update(
            symbol=inputs.symbol,
            request_id=request_id,
            status="running",
            stage="rule_based",
            runtime_mode="rule_based",
            current_step="Running rule-based debate",
            completed_steps=0,
            total_steps=1,
            message=reason_message,
        )
        get_from_inputs = getattr(
            self._rule_based_orchestrator,
            "get_debate_review_report_from_inputs",
            None,
        )
        if callable(get_from_inputs):
            report = get_from_inputs(inputs)
        else:
            report = self._rule_based_orchestrator.get_debate_review_report(inputs.symbol)
        logger.debug(
            "debate.runtime.rule_based symbol=%s final_action=%s confidence=%s",
            inputs.symbol,
            report.final_action,
            report.confidence,
        )
        self._progress_tracker.update(
            symbol=inputs.symbol,
            request_id=request_id,
            status="completed",
            stage="completed",
            runtime_mode="rule_based",
            current_step="Rule-based debate completed",
            completed_steps=1,
            total_steps=1,
            message="Rule-based debate-review completed.",
        )
        return report.model_copy(update={"runtime_mode": "rule_based"})

    def _call_llm_report(
        self,
        *,
        symbol: str,
        request_id: str | None,
    ) -> DebateReviewReport:
        try:
            return self._llm_orchestrator.get_debate_review_report(
                symbol,
                request_id=request_id,
            )
        except TypeError:
            return self._llm_orchestrator.get_debate_review_report(symbol)

    def _call_llm_report_from_inputs(
        self,
        *,
        inputs: SingleStockResearchInputs,
        request_id: str | None,
    ) -> DebateReviewReport:
        get_from_inputs = getattr(
            self._llm_orchestrator,
            "get_debate_review_report_from_inputs",
            None,
        )
        if callable(get_from_inputs):
            try:
                return get_from_inputs(inputs, request_id=request_id)
            except TypeError:
                return get_from_inputs(inputs)
        return self._call_llm_report(symbol=inputs.symbol, request_id=request_id)
