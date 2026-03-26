"""LLM provider 适配器选择器。"""

from __future__ import annotations

from app.services.llm_debate_service.base import LLMDebateSettings
from app.services.llm_debate_service.providers.base import LLMProviderAdapter
from app.services.llm_debate_service.providers.openai_compatible_provider import (
    OpenAICompatibleProviderAdapter,
)
from app.services.llm_debate_service.providers.volcengine_ark_provider import (
    VolcengineArkProviderAdapter,
)


def resolve_llm_provider_adapter(settings: LLMDebateSettings) -> LLMProviderAdapter:
    """根据配置或 base_url 自动选择 provider 适配器。"""
    provider_name = (settings.provider or "auto").strip().lower()
    if provider_name == "auto":
        provider_name = _detect_provider_name(settings.base_url)

    if provider_name == "volcengine_ark":
        return VolcengineArkProviderAdapter()
    return OpenAICompatibleProviderAdapter()


def _detect_provider_name(base_url: str | None) -> str:
    if base_url is None:
        return "openai_compatible"

    normalized = base_url.strip().lower()
    if "volces.com" in normalized or "/ark/" in normalized or "ark.cn-" in normalized:
        return "volcengine_ark"
    return "openai_compatible"
