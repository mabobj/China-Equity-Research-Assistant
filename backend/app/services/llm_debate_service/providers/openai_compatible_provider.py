"""默认 OpenAI 兼容 provider 适配器。"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from app.services.llm_debate_service.providers.base import (
    LLMProviderAdapter,
    ResponseFormatAttempt,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleProviderAdapter(LLMProviderAdapter):
    """适配标准 OpenAI 兼容网关。"""

    provider_name = "openai_compatible"

    def resolve_timeout_seconds(self, *, timeout_seconds: int) -> int:
        return timeout_seconds

    def create_client(
        self,
        *,
        api_key: str,
        base_url: str | None,
        timeout_seconds: int,
    ) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The 'openai' package is not installed.") from exc

        logger.debug(
            "初始化 OpenAI 兼容客户端，provider=%s base_url=%s timeout=%s",
            self.provider_name,
            base_url,
            timeout_seconds,
        )
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
        )

    def build_attempts(
        self,
        *,
        output_model: type[BaseModel],
    ) -> list[ResponseFormatAttempt]:
        return [
            ResponseFormatAttempt(
                name="json_schema",
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_model.__name__,
                        "schema": output_model.model_json_schema(),
                        "strict": True,
                    },
                },
            ),
            ResponseFormatAttempt(
                name="json_object",
                response_format={"type": "json_object"},
            ),
            ResponseFormatAttempt(
                name="prompt_only_json",
                response_format=None,
                enforce_json_in_prompt=True,
            ),
        ]
