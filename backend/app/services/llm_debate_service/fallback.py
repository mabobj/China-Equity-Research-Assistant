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
        requested_mode = "llm" if requested_llm else "rule_based"
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
                requested_mode=requested_mode,
                fallback_applied=bool(requested_llm and not self._settings.enabled),
                fallback_reason=(
                    "LLM debate is disabled by configuration."
                    if requested_llm and not self._settings.enabled
                    else None
                ),
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
                requested_mode=requested_mode,
                fallback_applied=True,
                fallback_reason="LLM API key is missing.",
            )

        try:
            report = self._call_llm_report(symbol=symbol, request_id=request_id)
            return self._decorate_report(
                report=report,
                requested_mode=requested_mode,
                effective_mode="llm",
                provider_used=self._llm_provider_name(),
                provider_candidates=self._provider_candidates(requested_mode=requested_mode),
                fallback_applied=False,
                fallback_reason=None,
                warning_messages=[],
            )
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
                error_message="LLM runtime failed and switched to rule-based debate.",
            )
            return self._get_rule_based_report(
                symbol=symbol,
                request_id=request_id,
                reason_message="LLM failed, switched to rule-based debate.",
                requested_mode=requested_mode,
                fallback_applied=True,
                fallback_reason="LLM runtime failed or timed out.",
            )

    def get_debate_review_report_from_inputs(
        self,
        inputs: SingleStockResearchInputs,
        *,
        use_llm: bool | None = None,
        request_id: str | None = None,
    ) -> DebateReviewReport:
        requested_llm = self._settings.enabled if use_llm is None else use_llm
        requested_mode = "llm" if requested_llm else "rule_based"
        should_use_llm = self._settings.enabled and requested_llm
        if not should_use_llm:
            return self._get_rule_based_report_from_inputs(
                inputs=inputs,
                request_id=request_id,
                reason_message="Using the rule-based debate runtime.",
                requested_mode=requested_mode,
                fallback_applied=bool(requested_llm and not self._settings.enabled),
                fallback_reason=(
                    "LLM debate is disabled by configuration."
                    if requested_llm and not self._settings.enabled
                    else None
                ),
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
                requested_mode=requested_mode,
                fallback_applied=True,
                fallback_reason="LLM API key is missing.",
            )

        try:
            report = self._call_llm_report_from_inputs(
                inputs=inputs,
                request_id=request_id,
            )
            return self._decorate_report(
                report=report,
                requested_mode=requested_mode,
                effective_mode="llm",
                provider_used=self._llm_provider_name(),
                provider_candidates=self._provider_candidates(requested_mode=requested_mode),
                fallback_applied=False,
                fallback_reason=None,
                warning_messages=[],
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
                error_message="LLM runtime failed and switched to rule-based debate.",
            )
            return self._get_rule_based_report_from_inputs(
                inputs=inputs,
                request_id=request_id,
                reason_message="LLM failed, switched to rule-based debate.",
                requested_mode=requested_mode,
                fallback_applied=True,
                fallback_reason="LLM runtime failed or timed out.",
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
        requested_mode: str,
        fallback_applied: bool,
        fallback_reason: str | None,
    ) -> DebateReviewReport:
        build_inputs = getattr(self._rule_based_orchestrator, "build_inputs", None)
        if not callable(build_inputs):
            report = self._rule_based_orchestrator.get_debate_review_report(symbol)
            return self._decorate_report(
                report=report,
                requested_mode=requested_mode,
                effective_mode="rule_based",
                provider_used="rule_based",
                provider_candidates=self._provider_candidates(requested_mode=requested_mode),
                fallback_applied=fallback_applied,
                fallback_reason=fallback_reason,
                warning_messages=[fallback_reason] if fallback_reason else [],
            )

        inputs = build_inputs(symbol)
        return self._get_rule_based_report_from_inputs(
            inputs=inputs,
            request_id=request_id,
            reason_message=reason_message,
            requested_mode=requested_mode,
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
        )

    def _get_rule_based_report_from_inputs(
        self,
        *,
        inputs: SingleStockResearchInputs,
        request_id: str | None,
        reason_message: str,
        requested_mode: str,
        fallback_applied: bool,
        fallback_reason: str | None,
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
        return self._decorate_report(
            report=report,
            requested_mode=requested_mode,
            effective_mode="rule_based",
            provider_used="rule_based",
            provider_candidates=self._provider_candidates(requested_mode=requested_mode),
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
            warning_messages=[fallback_reason] if fallback_reason else [],
        )

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

    def _llm_provider_name(self) -> str:
        provider_name = getattr(self._llm_orchestrator, "provider_name", None)
        if isinstance(provider_name, str) and provider_name:
            return provider_name
        return "llm"

    def _provider_candidates(self, *, requested_mode: str) -> list[str]:
        if requested_mode == "llm":
            return [self._llm_provider_name(), "rule_based"]
        return ["rule_based"]

    def _decorate_report(
        self,
        *,
        report: DebateReviewReport,
        requested_mode: str,
        effective_mode: str,
        provider_used: str,
        provider_candidates: list[str],
        fallback_applied: bool,
        fallback_reason: str | None,
        warning_messages: list[str],
    ) -> DebateReviewReport:
        return report.model_copy(
            update={
                "runtime_mode": effective_mode,
                "provider_used": provider_used,
                "provider_candidates": provider_candidates,
                "fallback_applied": fallback_applied,
                "fallback_reason": fallback_reason,
                "runtime_mode_requested": requested_mode,
                "runtime_mode_effective": effective_mode,
                "warning_messages": warning_messages,
            }
        )
