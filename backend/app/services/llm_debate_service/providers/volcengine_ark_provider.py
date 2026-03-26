"""火山方舟 OpenAI 兼容网关适配器。"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from app.services.llm_debate_service.providers.base import (
    LLMProviderAdapter,
    ResponseFormatAttempt,
)

logger = logging.getLogger(__name__)


class VolcengineArkProviderAdapter(LLMProviderAdapter):
    """适配火山方舟 coding/plan 套餐模型。"""

    provider_name = "volcengine_ark"

    def resolve_timeout_seconds(self, *, timeout_seconds: int) -> int:
        return max(timeout_seconds, 60)

    def create_client(
        self,
        *,
        api_key: str,
        base_url: str | None,
        timeout_seconds: int,
    ) -> Any:
        try:
            import httpx
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The 'openai' package is not installed.") from exc

        # 火山方舟 coding/plan 套餐的响应时间通常会明显长于普通模型。
        # 这里对读取超时设置一个更稳妥的下限，同时关闭 SDK 级自动重试，
        # 避免一次角色调用被重复超时拖成长尾请求。
        effective_timeout_seconds = self.resolve_timeout_seconds(
            timeout_seconds=timeout_seconds
        )
        timeout = httpx.Timeout(
            timeout=effective_timeout_seconds,
            connect=min(10.0, float(effective_timeout_seconds)),
        )

        logger.debug(
            "初始化火山方舟兼容客户端，provider=%s base_url=%s requested_timeout=%s effective_timeout=%s max_retries=%s",
            self.provider_name,
            base_url,
            timeout_seconds,
            effective_timeout_seconds,
            0,
        )
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
        )

    def build_attempts(
        self,
        *,
        output_model: type[BaseModel],
    ) -> list[ResponseFormatAttempt]:
        # 当前火山方舟 coding plan 套餐不支持 response_format，
        # 直接进入 prompt_only_json 模式，避免无意义的 400 错误。
        return [
            ResponseFormatAttempt(
                name="prompt_only_json",
                response_format=None,
                enforce_json_in_prompt=True,
            )
        ]
