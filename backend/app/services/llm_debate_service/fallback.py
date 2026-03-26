"""LLM 与规则版 debate 运行时回退服务。"""

from __future__ import annotations

import logging

from app.schemas.debate import DebateReviewReport
from app.services.debate_service.debate_orchestrator import DebateOrchestrator
from app.services.llm_debate_service.base import LLMDebateSettings
from app.services.llm_debate_service.llm_debate_orchestrator import LLMDebateOrchestrator

logger = logging.getLogger(__name__)


class DebateRuntimeService:
    """统一封装 rule-based 与 llm 两种 debate 运行时。"""

    def __init__(
        self,
        rule_based_orchestrator: DebateOrchestrator,
        llm_orchestrator: LLMDebateOrchestrator,
        settings: LLMDebateSettings,
    ) -> None:
        self._rule_based_orchestrator = rule_based_orchestrator
        self._llm_orchestrator = llm_orchestrator
        self._settings = settings

    def get_debate_review_report(
        self,
        symbol: str,
        use_llm: bool | None = None,
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
            return self._get_rule_based_report(symbol)

        if not self._settings.api_key:
            logger.info("LLM debate 未配置 API key，自动回退规则版。symbol=%s", symbol)
            return self._get_rule_based_report(symbol)

        try:
            report = self._llm_orchestrator.get_debate_review_report(symbol)
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
            return self._get_rule_based_report(symbol)

    def _get_rule_based_report(self, symbol: str) -> DebateReviewReport:
        report = self._rule_based_orchestrator.get_debate_review_report(symbol)
        logger.debug(
            "debate.runtime.rule_based symbol=%s final_action=%s confidence=%s",
            symbol,
            report.final_action,
            report.confidence,
        )
        return report.model_copy(update={"runtime_mode": "rule_based"})
