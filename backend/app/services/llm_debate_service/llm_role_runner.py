"""受控 LLM 角色执行器。"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticUndefined

from app.services.llm_debate_service.base import (
    LLMDebateSettings,
    LLMRoleRunError,
    LLMSchemaValidationError,
    LLMTimeoutError,
    LLMUnavailableError,
    ModelT,
    RoleName,
    build_role_user_prompt,
    load_role_prompt,
)
from app.services.llm_debate_service.providers.base import (
    LLMProviderAdapter,
    ResponseFormatAttempt,
)
from app.services.llm_debate_service.providers.registry import (
    resolve_llm_provider_adapter,
)

logger = logging.getLogger(__name__)


class LLMRoleRunner:
    """在固定 schema 下执行单个 LLM 角色。"""

    def __init__(
        self,
        settings: LLMDebateSettings,
        client_factory: Callable[[str, str | None, int], Any] | None = None,
        provider_adapter: LLMProviderAdapter | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._provider_adapter = provider_adapter or resolve_llm_provider_adapter(
            settings
        )
        self._client: Any | None = None

    @property
    def provider_name(self) -> str:
        return self._provider_adapter.provider_name

    def run_role(
        self,
        *,
        role: RoleName,
        role_input: dict[str, Any],
        output_model: type[ModelT],
    ) -> ModelT:
        """执行单个角色，并把输出校验为目标 schema。"""
        self._ensure_available()
        client = self._get_client()
        system_prompt = load_role_prompt(role)
        base_user_prompt = build_role_user_prompt(role_input)
        attempts = self._provider_adapter.build_attempts(output_model=output_model)
        last_error: Exception | None = None

        logger.debug(
            "llm.role.start role=%s model=%s provider=%s base_url=%s input_keys=%s",
            role,
            self._settings.model,
            self._provider_adapter.provider_name,
            self._settings.base_url,
            sorted(role_input.keys()),
        )

        for attempt in attempts:
            user_prompt = self._build_user_prompt(
                base_user_prompt=base_user_prompt,
                enforce_json_in_prompt=attempt.enforce_json_in_prompt,
            )

            logger.debug(
                "llm.role.attempt role=%s format=%s model=%s provider=%s",
                role,
                attempt.name,
                self._settings.model,
                self._provider_adapter.provider_name,
            )

            try:
                response = self._create_completion(
                    client=client,
                    model=self._settings.model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_format=attempt.response_format,
                )
                content = self._extract_content(response)
                logger.debug(
                    "llm.role.raw_output role=%s format=%s content=%s",
                    role,
                    attempt.name,
                    self._truncate_text(content),
                )
                parsed = self._parse_output(
                    content=content,
                    role=role,
                    output_model=output_model,
                )
                logger.debug(
                    "llm.role.done role=%s format=%s model=%s provider=%s",
                    role,
                    attempt.name,
                    self._settings.model,
                    self._provider_adapter.provider_name,
                )
                return parsed
            except LLMSchemaValidationError:
                raise
            except Exception as exc:
                if self._looks_like_timeout(exc):
                    raise LLMTimeoutError(
                        f"LLM role '{role}' timed out after "
                        f"{self._effective_timeout_seconds()} seconds."
                    ) from exc

                last_error = exc
                error_detail = self._describe_exception(exc)

                if self._should_try_next_format(exc=exc, attempt_name=attempt.name):
                    next_attempt = self._next_attempt_name(
                        attempts=attempts,
                        current_name=attempt.name,
                    )
                    logger.warning(
                        "llm.role.compat_fallback role=%s from=%s to=%s error=%s",
                        role,
                        attempt.name,
                        next_attempt,
                        error_detail,
                    )
                    continue

                logger.warning(
                    "llm.role.failed role=%s format=%s error=%s",
                    role,
                    attempt.name,
                    error_detail,
                )
                raise LLMRoleRunError(
                    f"LLM role '{role}' failed. Details: {error_detail}"
                ) from exc

        detail = self._describe_exception(last_error) if last_error else "unknown error"
        raise LLMRoleRunError(
            f"LLM role '{role}' failed after all compatibility attempts. "
            f"Details: {detail}"
        ) from last_error

    def _ensure_available(self) -> None:
        if not self._settings.enabled:
            raise LLMUnavailableError("LLM debate is disabled by configuration.")
        if not self._settings.api_key:
            raise LLMUnavailableError("OPENAI_API_KEY is required for LLM debate.")

    def _effective_timeout_seconds(self) -> int:
        return self._provider_adapter.resolve_timeout_seconds(
            timeout_seconds=self._settings.timeout_seconds
        )

    def _get_client(self) -> Any:
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory(
                    self._settings.api_key or "",
                    self._settings.base_url,
                    self._settings.timeout_seconds,
                )
            else:
                self._client = self._provider_adapter.create_client(
                    api_key=self._settings.api_key or "",
                    base_url=self._settings.base_url,
                    timeout_seconds=self._settings.timeout_seconds,
                )
        return self._client

    @staticmethod
    def _build_user_prompt(
        *,
        base_user_prompt: str,
        enforce_json_in_prompt: bool,
    ) -> str:
        if not enforce_json_in_prompt:
            return base_user_prompt
        return (
            f"{base_user_prompt}\n\n"
            "额外要求：\n"
            "- 只输出一个 JSON 对象\n"
            "- 不要输出 Markdown 代码块\n"
            "- 不要输出额外解释文字\n"
            "- 字段必须严格贴合要求的 schema"
        )

    @staticmethod
    def _create_completion(
        *,
        client: Any,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any] | None,
    ) -> Any:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_format is not None:
            payload["response_format"] = response_format
        return client.chat.completions.create(**payload)

    @staticmethod
    def _extract_content(response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMRoleRunError("LLM response does not contain choices.")

        message = getattr(choices[0], "message", None)
        if message is None:
            raise LLMRoleRunError("LLM response does not contain a message.")

        refusal = getattr(message, "refusal", None)
        if refusal:
            raise LLMRoleRunError(f"LLM refused to answer: {refusal}")

        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                    continue
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
            joined = "".join(parts).strip()
            if joined:
                return joined

        raise LLMRoleRunError("LLM response content is empty or unsupported.")

    @staticmethod
    def _parse_output(
        *,
        content: str,
        role: RoleName,
        output_model: type[ModelT],
    ) -> ModelT:
        normalized_content = LLMRoleRunner._strip_markdown_fences(content)
        try:
            payload = json.loads(normalized_content)
        except json.JSONDecodeError as exc:
            raise LLMSchemaValidationError(
                f"LLM output is not valid JSON: {exc}"
            ) from exc

        try:
            coerced_payload = LLMRoleRunner._coerce_payload(
                payload=payload,
                role=role,
                output_model=output_model,
            )
            return output_model.model_validate(coerced_payload)
        except ValidationError as exc:
            raise LLMSchemaValidationError(
                f"LLM output failed schema validation: {exc}"
            ) from exc
        except ValueError as exc:
            raise LLMSchemaValidationError(
                f"LLM output is not valid JSON: {exc}"
            ) from exc

    @staticmethod
    def _coerce_payload(
        *,
        payload: Any,
        role: RoleName,
        output_model: type[ModelT],
    ) -> Any:
        if not isinstance(payload, dict):
            return payload

        model_name = output_model.__name__
        coerced = dict(payload)

        if "role" in output_model.model_fields:
            coerced = LLMRoleRunner._coerce_analyst_payload(
                payload=coerced,
                role=role,
                output_model=output_model,
            )
        elif model_name in {"BullCase", "BearCase"}:
            coerced = LLMRoleRunner._coerce_reason_case_payload(coerced)
        elif model_name == "ChiefJudgement":
            coerced = LLMRoleRunner._coerce_chief_judgement_payload(coerced)
        elif model_name == "RiskReview":
            coerced = LLMRoleRunner._coerce_risk_review_payload(coerced)

        return coerced

    @staticmethod
    def _coerce_analyst_payload(
        *,
        payload: dict[str, Any],
        role: RoleName,
        output_model: type[BaseModel],
    ) -> dict[str, Any]:
        coerced = dict(payload)
        role_field = output_model.model_fields.get("role")
        role_default = role_field.default if role_field is not None else None
        if role_default is not None and role_default is not PydanticUndefined:
            coerced["role"] = role_default
        else:
            coerced["role"] = str(payload.get("role") or role)

        coerced["positive_points"] = LLMRoleRunner._coerce_debate_points(
            payload.get("positive_points"),
            default_title="看多要点",
        )
        coerced["caution_points"] = LLMRoleRunner._coerce_debate_points(
            payload.get("caution_points"),
            default_title="谨慎要点",
        )
        coerced["key_levels"] = LLMRoleRunner._coerce_string_list(
            payload.get("key_levels")
        )

        if not coerced.get("action_bias"):
            coerced["action_bias"] = LLMRoleRunner._infer_action_bias(
                summary=str(payload.get("summary", "")),
                positive_points=coerced["positive_points"],
                caution_points=coerced["caution_points"],
            )
        else:
            coerced["action_bias"] = LLMRoleRunner._normalize_action_bias(
                str(coerced["action_bias"])
            )

        return coerced

    @staticmethod
    def _coerce_reason_case_payload(payload: dict[str, Any]) -> dict[str, Any]:
        coerced = dict(payload)
        coerced["reasons"] = LLMRoleRunner._coerce_debate_points(
            payload.get("reasons"),
            default_title="理由",
        )
        if not coerced.get("summary"):
            reasons = coerced["reasons"]
            if reasons:
                coerced["summary"] = reasons[0]["detail"]
        return coerced

    @staticmethod
    def _coerce_chief_judgement_payload(payload: dict[str, Any]) -> dict[str, Any]:
        coerced = dict(payload)
        action = payload.get("final_action")
        if action is not None:
            coerced["final_action"] = str(action).upper()

        decisive_points = LLMRoleRunner._coerce_string_list(
            payload.get("decisive_points")
        )
        key_disagreements = LLMRoleRunner._coerce_string_list(
            payload.get("key_disagreements")
        )
        coerced["decisive_points"] = decisive_points
        coerced["key_disagreements"] = key_disagreements

        if not coerced.get("summary"):
            coerced["summary"] = LLMRoleRunner._build_chief_summary(
                final_action=str(coerced.get("final_action", "")),
                decisive_points=decisive_points,
            )
        return coerced

    @staticmethod
    def _coerce_risk_review_payload(payload: dict[str, Any]) -> dict[str, Any]:
        coerced = dict(payload)
        if payload.get("risk_level") is not None:
            coerced["risk_level"] = LLMRoleRunner._normalize_risk_level(
                str(payload["risk_level"])
            )
        coerced["execution_reminders"] = LLMRoleRunner._coerce_string_list(
            payload.get("execution_reminders")
        )
        if not coerced.get("summary"):
            risk_level = str(coerced.get("risk_level", "medium"))
            coerced["summary"] = LLMRoleRunner._build_risk_summary(
                risk_level=risk_level,
                execution_reminders=coerced["execution_reminders"],
            )
        return coerced

    @staticmethod
    def _coerce_debate_points(
        value: Any,
        *,
        default_title: str,
    ) -> list[dict[str, str]]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = value
        else:
            return []

        normalized: list[dict[str, str]] = []
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                title = str(item.get("title") or f"{default_title}{index}").strip()
                detail = str(
                    item.get("detail") or item.get("summary") or item.get("text") or ""
                ).strip()
                if detail:
                    normalized.append({"title": title, "detail": detail})
                continue

            text = str(item).strip()
            if text:
                normalized.append(
                    {
                        "title": f"{default_title}{index}",
                        "detail": text,
                    }
                )
        return normalized

    @staticmethod
    def _coerce_string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, list):
            items: list[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    items.append(text)
            return items
        text = str(value).strip()
        return [text] if text else []

    @staticmethod
    def _build_chief_summary(
        *,
        final_action: str,
        decisive_points: list[str],
    ) -> str:
        if decisive_points:
            lead = decisive_points[0].rstrip("。；;")
        else:
            lead = ""

        action = final_action.strip().upper()
        if action == "BUY":
            tail = "综合多空信息后，当前更偏向执行买入或继续跟踪买点。"
        elif action == "WATCH":
            tail = "综合多空信息后，当前更适合继续观察，等待更清晰信号。"
        else:
            tail = "综合多空信息后，当前更适合回避或继续等待。"

        if lead:
            return f"{lead}。{tail}"
        return tail

    @staticmethod
    def _build_risk_summary(
        *,
        risk_level: str,
        execution_reminders: list[str],
    ) -> str:
        risk_level = risk_level.strip().lower()
        if risk_level == "low":
            prefix = "当前风险总体可控，但仍需遵守执行纪律。"
        elif risk_level == "high":
            prefix = "当前风险偏高，执行上应明显收紧。"
        else:
            prefix = "当前风险处于中等水平，执行上需要保持克制。"

        if execution_reminders:
            return f"{prefix}重点留意：{execution_reminders[0].rstrip('。；;')}。"
        return prefix

    @staticmethod
    def _infer_action_bias(
        *,
        summary: str,
        positive_points: list[dict[str, str]],
        caution_points: list[dict[str, str]],
    ) -> str:
        text = summary.lower()
        caution_count = len(caution_points)
        positive_count = len(positive_points)

        negative_markers = [
            "avoid",
            "negative",
            "bearish",
            "下行",
            "偏弱",
            "回避",
            "风险提升",
            "不建议",
        ]
        cautious_markers = ["谨慎", "等待", "观察", "中性", "watch"]
        supportive_markers = ["support", "breakout", "偏强", "支撑", "改善", "关注"]

        if any(marker in text for marker in negative_markers) or caution_count >= positive_count + 2:
            return "negative"
        if any(marker in text for marker in cautious_markers) or caution_count > positive_count:
            return "cautious"
        if any(marker in text for marker in supportive_markers) or positive_count > caution_count:
            return "supportive"
        return "neutral"

    @staticmethod
    def _normalize_action_bias(value: str) -> str:
        normalized = value.strip().lower()
        mapping = {
            "positive": "supportive",
            "bullish": "supportive",
            "supportive": "supportive",
            "neutral": "neutral",
            "cautious": "cautious",
            "negative": "negative",
            "bearish": "negative",
        }
        return mapping.get(normalized, "neutral")

    @staticmethod
    def _normalize_risk_level(value: str) -> str:
        normalized = value.strip().lower()
        mapping = {
            "low": "low",
            "medium": "medium",
            "mid": "medium",
            "high": "high",
            "低": "low",
            "中": "medium",
            "中等": "medium",
            "高": "high",
        }
        return mapping.get(normalized, "medium")

    @staticmethod
    def _strip_markdown_fences(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return stripped

    @staticmethod
    def _looks_like_timeout(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if status_code == 408:
            return True
        exc_name = exc.__class__.__name__.lower()
        if "timeout" in exc_name:
            return True
        cause = getattr(exc, "__cause__", None)
        return bool(cause and "timeout" in cause.__class__.__name__.lower())

    @staticmethod
    def _should_try_next_format(*, exc: Exception, attempt_name: str) -> bool:
        if attempt_name == "prompt_only_json":
            return False

        status_code = getattr(exc, "status_code", None)
        if status_code in {400, 404, 415, 422}:
            return True

        response = getattr(exc, "response", None)
        response_status = getattr(response, "status_code", None)
        if response_status in {400, 404, 415, 422}:
            return True

        text = LLMRoleRunner._describe_exception(exc).lower()
        compatibility_markers = [
            "response_format",
            "json_schema",
            "json_object",
            "bad request",
            "unsupported",
            "invalid parameter",
            "invalid_request_error",
        ]
        return any(marker in text for marker in compatibility_markers)

    @staticmethod
    def _next_attempt_name(
        *,
        attempts: list[ResponseFormatAttempt],
        current_name: str,
    ) -> str:
        names = [attempt.name for attempt in attempts]
        try:
            current_index = names.index(current_name)
        except ValueError:
            return "unknown"
        if current_index + 1 >= len(names):
            return "none"
        return names[current_index + 1]

    @staticmethod
    def _describe_exception(exc: Exception | None) -> str:
        if exc is None:
            return "unknown error"

        parts = [f"{exc.__class__.__name__}: {exc}"]

        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            parts.append(f"status={status_code}")

        body = getattr(exc, "body", None)
        if body is not None:
            parts.append(f"body={LLMRoleRunner._safe_serialize(body)}")

        response = getattr(exc, "response", None)
        if response is not None:
            response_status = getattr(response, "status_code", None)
            if response_status is not None and response_status != status_code:
                parts.append(f"response_status={response_status}")

            text = getattr(response, "text", None)
            if callable(text):
                try:
                    text = text()
                except Exception:
                    text = None
            if text:
                parts.append(f"response_text={text}")

            json_method = getattr(response, "json", None)
            if callable(json_method):
                try:
                    parts.append(
                        f"response_json={LLMRoleRunner._safe_serialize(json_method())}"
                    )
                except Exception:
                    pass

        return " | ".join(parts)

    @staticmethod
    def _safe_serialize(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return str(value)

    @staticmethod
    def _truncate_text(value: str, limit: int = 1200) -> str:
        text = value.strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...(truncated)"
