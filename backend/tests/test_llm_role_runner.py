"""受控 LLM 角色执行器测试。"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from app.services.llm_debate_service.base import (
    LLMDebateSettings,
    LLMRoleRunError,
    LLMSchemaValidationError,
)
from app.services.llm_debate_service.llm_role_runner import LLMRoleRunner
from app.services.llm_debate_service.providers.registry import (
    resolve_llm_provider_adapter,
)


class SampleOutput(BaseModel):
    """测试用输出 schema。"""

    model_config = ConfigDict(extra="forbid")

    summary: str
    score: int


class StubResponse:
    """模拟 OpenAI chat.completions 响应。"""

    def __init__(self, content: Any) -> None:
        self.choices = [
            type(
                "Choice",
                (),
                {
                    "message": type(
                        "Message",
                        (),
                        {"content": content, "refusal": None},
                    )()
                },
            )()
        ]


class FakeBadRequestError(Exception):
    """模拟第三方兼容网关返回的 400 错误。"""

    def __init__(self, message: str, *, body: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status_code = 400
        self.body = body or {
            "error": {
                "message": "response_format json_schema is not supported",
            }
        }
        self.response = type(
            "Response",
            (),
            {
                "status_code": 400,
                "text": '{"error":{"message":"response_format json_schema is not supported"}}',
                "json": lambda self: {
                    "error": {
                        "message": "response_format json_schema is not supported",
                    }
                },
            },
        )()


class StubCompletionsApi:
    """可按顺序返回结果或异常的假接口。"""

    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> StubResponse:
        self.calls.append(kwargs)
        if not self._outcomes:
            raise AssertionError("No more outcomes configured for StubCompletionsApi.")

        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return StubResponse(outcome)


class StubClient:
    """模拟 OpenAI 客户端。"""

    def __init__(self, completions_api: StubCompletionsApi) -> None:
        self.chat = type("ChatApi", (), {"completions": completions_api})()


def _build_runner(
    completions_api: StubCompletionsApi,
    *,
    base_url: str = "https://example.com/v1",
    provider: str = "auto",
) -> LLMRoleRunner:
    return LLMRoleRunner(
        settings=LLMDebateSettings(
            enabled=True,
            api_key="test-key",
            model="gpt-test",
            base_url=base_url,
            timeout_seconds=10,
            provider=provider,
        ),
        client_factory=lambda api_key, url, timeout_seconds: StubClient(completions_api),
    )


def test_llm_role_runner_returns_validated_model() -> None:
    completions_api = StubCompletionsApi(['{"summary":"结构化输出","score":80}'])
    runner = _build_runner(completions_api)

    result = runner.run_role(
        role="technical_analyst",
        role_input={"symbol": "600519.SH"},
        output_model=SampleOutput,
    )

    assert result.summary == "结构化输出"
    assert result.score == 80
    assert completions_api.calls[0]["model"] == "gpt-test"
    assert completions_api.calls[0]["response_format"]["type"] == "json_schema"


def test_llm_role_runner_falls_back_when_json_schema_is_unsupported() -> None:
    completions_api = StubCompletionsApi(
        [
            FakeBadRequestError("400 Bad Request"),
            '{"summary":"兼容模式成功","score":88}',
        ]
    )
    runner = _build_runner(completions_api)

    result = runner.run_role(
        role="technical_analyst",
        role_input={"symbol": "600519.SH"},
        output_model=SampleOutput,
    )

    assert result.summary == "兼容模式成功"
    assert result.score == 88
    assert len(completions_api.calls) == 2
    assert completions_api.calls[0]["response_format"]["type"] == "json_schema"
    assert completions_api.calls[1]["response_format"]["type"] == "json_object"


def test_llm_role_runner_uses_ark_prompt_only_mode() -> None:
    completions_api = StubCompletionsApi(['{"summary":"结构化输出","score":66}'])
    runner = _build_runner(
        completions_api,
        base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
    )

    result = runner.run_role(
        role="technical_analyst",
        role_input={"symbol": "600519.SH"},
        output_model=SampleOutput,
    )

    assert result.score == 66
    assert len(completions_api.calls) == 1
    assert "response_format" not in completions_api.calls[0]


def test_llm_role_runner_raises_schema_error_on_invalid_payload() -> None:
    completions_api = StubCompletionsApi(['{"summary":"缺少 score"}'])
    runner = _build_runner(completions_api)

    with pytest.raises(LLMSchemaValidationError):
        runner.run_role(
            role="technical_analyst",
            role_input={"symbol": "600519.SH"},
            output_model=SampleOutput,
        )


def test_llm_role_runner_coerces_common_analyst_shape_drift() -> None:
    completions_api = StubCompletionsApi(
        [
            FakeBadRequestError("json_schema unsupported"),
            FakeBadRequestError("json_object unsupported"),
            """{
              "role": "technical_analyst",
              "summary": "日线偏弱，当前位置更适合观察。",
              "positive_points": ["靠近支撑位，短期仍有缓冲"],
              "caution_points": ["趋势仍偏弱", "跌破支撑后风险会抬升"],
              "key_levels": ["支撑位 1383.20", "压力位 1498.07"]
            }""",
        ]
    )
    runner = _build_runner(completions_api)

    from app.schemas.debate import AnalystView

    result = runner.run_role(
        role="technical_analyst",
        role_input={"symbol": "600519.SH"},
        output_model=AnalystView,
    )

    assert result.role == "technical_analyst"
    assert result.action_bias in {"cautious", "negative", "neutral"}
    assert result.positive_points
    assert result.positive_points[0].detail == "靠近支撑位，短期仍有缓冲"
    assert result.caution_points[0].title == "谨慎要点1"


def test_llm_role_runner_coerces_missing_chief_summary() -> None:
    completions_api = StubCompletionsApi(
        [
            FakeBadRequestError("json_schema unsupported"),
            FakeBadRequestError("json_object unsupported"),
            """{
              "final_action": "AVOID",
              "decisive_points": ["技术趋势偏弱，当前不适合主动开仓"],
              "key_disagreements": ["支撑位仍未有效跌破"]
            }""",
        ]
    )
    runner = _build_runner(completions_api)

    from app.schemas.debate import ChiefJudgement

    result = runner.run_role(
        role="chief_analyst",
        role_input={"symbol": "600519.SH"},
        output_model=ChiefJudgement,
    )

    assert result.final_action == "AVOID"
    assert result.summary
    assert "回避" in result.summary or "等待" in result.summary


def test_llm_role_runner_raises_role_error_when_all_formats_fail() -> None:
    completions_api = StubCompletionsApi(
        [
            FakeBadRequestError("first bad request"),
            FakeBadRequestError("second bad request"),
            RuntimeError("gateway exploded"),
        ]
    )
    runner = _build_runner(completions_api)

    with pytest.raises(LLMRoleRunError):
        runner.run_role(
            role="technical_analyst",
            role_input={"symbol": "600519.SH"},
            output_model=SampleOutput,
        )


def test_resolve_llm_provider_adapter_detects_ark() -> None:
    settings = LLMDebateSettings(
        enabled=True,
        api_key="test-key",
        model="ark-code-latest",
        base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
        timeout_seconds=20,
    )

    adapter = resolve_llm_provider_adapter(settings)

    assert adapter.provider_name == "volcengine_ark"
    assert adapter.resolve_timeout_seconds(timeout_seconds=20) == 60
