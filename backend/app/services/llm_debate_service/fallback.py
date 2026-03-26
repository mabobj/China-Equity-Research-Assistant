"""LLM 与规则版 debate 运行时回退服务。"""

from __future__ import annotations

import logging

from app.schemas.debate import DebateReviewProgress, DebateReviewReport
from app.services.debate_service.debate_orchestrator import DebateOrchestrator
from app.services.llm_debate_service.base import LLMDebateSettings
from app.services.llm_debate_service.llm_debate_orchestrator import LLMDebateOrchestrator
from app.services.llm_debate_service.progress_tracker import DebateProgressTracker

logger = logging.getLogger(__name__)


class DebateRuntimeService:
    """统一封装 rule-based 与 llm 两种 debate 运行时。"""

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
        """根据配置或显式参数选择运行时，并在失败时自动回退。"""
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
                reason_message="当前使用规则版裁决。",
            )

        self._progress_tracker.start(
            symbol=symbol,
            request_id=request_id,
            runtime_mode="llm",
            message="已提交 LLM debate-review，请等待后台顺序执行各角色。",
        )

        if not self._settings.api_key:
            logger.info("LLM debate 未配置 API key，自动回退规则版。symbol=%s", symbol)
            self._progress_tracker.update(
                symbol=symbol,
                request_id=request_id,
                status="fallback",
                stage="fallback_rule_based",
                runtime_mode="llm",
                current_step="LLM 不可用，切换规则版",
                completed_steps=0,
                total_steps=0,
                message="未配置 LLM API key，已自动切换到规则版。",
            )
            return self._get_rule_based_report(
                symbol=symbol,
                request_id=request_id,
                reason_message="LLM 未配置，已自动切换规则版。",
            )

        try:
            if request_id is None:
                report = self._llm_orchestrator.get_debate_review_report(symbol)
            else:
                report = self._llm_orchestrator.get_debate_review_report(
                    symbol,
                    request_id=request_id,
                )
            logger.debug(
                "debate.runtime.llm_success symbol=%s final_action=%s confidence=%s",
                symbol,
                report.final_action,
                report.confidence,
            )
            return report
        except Exception as exc:
            logger.warning(
                "LLM debate 执行失败，自动回退规则版。symbol=%s error=%s",
                symbol,
                exc,
            )
            self._progress_tracker.update(
                symbol=symbol,
                request_id=request_id,
                status="fallback",
                stage="fallback_rule_based",
                runtime_mode="llm",
                current_step="LLM 执行失败，切换规则版",
                completed_steps=0,
                total_steps=0,
                message="LLM 执行失败，正在回退到规则版。",
                error_message=str(exc),
            )
            return self._get_rule_based_report(
                symbol=symbol,
                request_id=request_id,
                reason_message="LLM 执行失败，已自动切换规则版。",
            )

    def get_debate_review_progress(
        self,
        symbol: str,
        *,
        request_id: str | None = None,
        use_llm: bool | None = None,
    ) -> DebateReviewProgress:
        """返回当前 symbol/request_id 对应的运行进度。"""
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
        self._progress_tracker.update(
            symbol=symbol,
            request_id=request_id,
            status="running",
            stage="rule_based",
            runtime_mode="rule_based",
            current_step="规则版裁决",
            completed_steps=0,
            total_steps=1,
            message=reason_message,
        )
        report = self._rule_based_orchestrator.get_debate_review_report(symbol)
        logger.debug(
            "debate.runtime.rule_based symbol=%s final_action=%s confidence=%s",
            symbol,
            report.final_action,
            report.confidence,
        )
        self._progress_tracker.update(
            symbol=symbol,
            request_id=request_id,
            status="completed",
            stage="completed",
            runtime_mode="rule_based",
            current_step="规则版裁决完成",
            completed_steps=1,
            total_steps=1,
            message="规则版 debate-review 已完成。",
        )
        return report.model_copy(update={"runtime_mode": "rule_based"})
