"""LLM 裁决运行时的基础定义。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

RoleName = Literal[
    "technical_analyst",
    "fundamental_analyst",
    "event_analyst",
    "sentiment_analyst",
    "bull_researcher",
    "bear_researcher",
    "chief_analyst",
    "risk_reviewer",
]
RuntimeMode = Literal["rule_based", "llm"]
ModelT = TypeVar("ModelT", bound=BaseModel)

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_FILE_BY_ROLE: dict[RoleName, str] = {
    "technical_analyst": "TECHNICAL_ANALYST_AGENT.md",
    "fundamental_analyst": "FUNDAMENTAL_ANALYST_AGENT.md",
    "event_analyst": "EVENT_ANALYST_AGENT.md",
    "sentiment_analyst": "SENTIMENT_ANALYST_AGENT.md",
    "bull_researcher": "BULL_RESEARCHER_AGENT.md",
    "bear_researcher": "BEAR_RESEARCHER_AGENT.md",
    "chief_analyst": "CHIEF_ANALYST_AGENT.md",
    "risk_reviewer": "RISK_REVIEWER_AGENT.md",
}


class LLMDebateError(Exception):
    """LLM 裁决运行时的基础异常。"""


class LLMUnavailableError(LLMDebateError):
    """LLM 运行条件不满足。"""


class LLMRoleRunError(LLMDebateError):
    """LLM 角色执行失败。"""


class LLMSchemaValidationError(LLMDebateError):
    """LLM 响应未通过 schema 校验。"""


class LLMTimeoutError(LLMDebateError):
    """LLM 响应超时。"""


@dataclass(frozen=True)
class LLMDebateSettings:
    """LLM 裁决运行时配置。"""

    enabled: bool
    api_key: str | None
    model: str
    base_url: str | None
    timeout_seconds: int
    provider: str = "auto"


def load_role_prompt(role: RoleName) -> str:
    """加载某个角色的提示词模板。"""
    prompt_path = PROMPT_DIR / PROMPT_FILE_BY_ROLE[role]
    return prompt_path.read_text(encoding="utf-8").strip()


def build_role_user_prompt(role_input: dict[str, Any]) -> str:
    """把结构化输入编码为用户提示。"""
    return (
        "以下是本次角色分析允许使用的全部输入数据。"
        "你只能基于这些字段输出结果，不能补充输入中不存在的事实。\n\n"
        "```json\n"
        f"{json.dumps(role_input, ensure_ascii=False, indent=2)}\n"
        "```"
    )
