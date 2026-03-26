"""LLM provider 适配层基础定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel


@dataclass(frozen=True)
class ResponseFormatAttempt:
    """单次 response_format 尝试配置。"""

    name: str
    response_format: dict[str, Any] | None
    enforce_json_in_prompt: bool = False


class LLMProviderAdapter(Protocol):
    """不同 LLM 网关的统一适配接口。"""

    provider_name: str

    def create_client(
        self,
        *,
        api_key: str,
        base_url: str | None,
        timeout_seconds: int,
    ) -> Any:
        """创建底层客户端。"""

    def resolve_timeout_seconds(self, *, timeout_seconds: int) -> int:
        """返回当前 provider 实际采用的超时秒数。"""

    def build_attempts(
        self,
        *,
        output_model: type[BaseModel],
    ) -> list[ResponseFormatAttempt]:
        """返回当前 provider 支持的输出格式尝试顺序。"""
