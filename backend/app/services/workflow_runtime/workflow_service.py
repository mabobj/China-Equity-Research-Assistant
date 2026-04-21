"""Workflow runtime service facade."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import logging
from threading import Lock
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.schemas.workflow import (
    DeepReviewWorkflowRunRequest,
    ScreenerWorkflowRunRequest,
    SingleStockWorkflowRunRequest,
    WorkflowRunDetailResponse,
    WorkflowRunResponse,
    WorkflowStepSummary,
)
from app.services.workflow_runtime.artifacts import FileWorkflowArtifactStore
from app.services.workflow_runtime.base import (
    WorkflowArtifact,
    WorkflowDefinition,
    WorkflowRunResult,
    WorkflowStepResult,
)
from app.services.workflow_runtime.executor import WorkflowExecutor
from app.services.workflow_runtime.registry import WorkflowRegistry

logger = logging.getLogger(__name__)
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class WorkflowRuntimeService:
    """Run workflows synchronously or start them in lightweight background threads."""

    def __init__(
        self,
        registry: WorkflowRegistry,
        executor: WorkflowExecutor,
        artifact_store: FileWorkflowArtifactStore,
        background_executor: ThreadPoolExecutor | None = None,
        screener_batch_service: Any | None = None,
        screener_scheme_service: Any | None = None,
        evaluation_service: Any | None = None,
        experiment_service: Any | None = None,
        stale_running_timeout_seconds: int = 600,
        recommendation_cache_ttl_seconds: int = 600,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._artifact_store = artifact_store
        self._background_executor = background_executor or ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="workflow-runtime",
        )
        self._screener_batch_service = screener_batch_service
        self._screener_scheme_service = screener_scheme_service
        self._evaluation_service = evaluation_service
        self._experiment_service = experiment_service
        self._stale_running_timeout = timedelta(
            seconds=max(stale_running_timeout_seconds, 30)
        )
        self._recommendation_cache_ttl = timedelta(
            seconds=max(recommendation_cache_ttl_seconds, 60)
        )
        self._active_futures: dict[str, Future] = {}
        self._future_lock = Lock()
        self._recommendation_cache: dict[str, tuple[datetime, dict[str, Any] | None]] = {}

    def run_single_stock_workflow(
        self,
        request: SingleStockWorkflowRunRequest,
    ) -> WorkflowRunResponse:
        definition = self._registry.get_definition("single_stock_full_review")
        result = self._executor.execute(definition, request)
        return self._to_run_response(result)

    def run_deep_review_workflow(
        self,
        request: DeepReviewWorkflowRunRequest,
    ) -> WorkflowRunResponse:
        definition = self._registry.get_definition("deep_candidate_review")
        return self._start_background_workflow(definition, request)

    def run_screener_workflow(
        self,
        request: ScreenerWorkflowRunRequest,
    ) -> WorkflowRunResponse:
        definition = self._registry.get_definition("screener_run")
        scheme_snapshot = None
        if self._screener_scheme_service is not None:
            started_at = datetime.now(_SHANGHAI_TZ)
            scheme_snapshot = self._screener_scheme_service.build_run_context_snapshot(
                run_id="pending",
                workflow_name=definition.name,
                trade_date=started_at.date(),
                started_at=started_at,
                runtime_params={
                    "batch_size": request.batch_size,
                    "max_symbols": request.max_symbols,
                    "top_n": request.top_n,
                    "force_refresh": request.force_refresh,
                },
                scheme_id=request.scheme_id,
                scheme_version=request.scheme_version,
            )
        running_artifact = self._find_valid_running_artifact(
            workflow_name=definition.name
        )
        if running_artifact is not None:
            logger.info(
                "event=screener.run.reuse_existing workflow=%s run_id=%s started_at=%s",
                definition.name,
                running_artifact.run_id,
                running_artifact.started_at.isoformat(),
            )
            return self._build_existing_running_response(running_artifact)

        def _on_started(artifact: WorkflowArtifact) -> None:
            if self._screener_scheme_service is not None and scheme_snapshot is not None:
                self._screener_scheme_service.save_run_context(
                    scheme_snapshot.model_copy(
                        update={"run_id": artifact.run_id, "started_at": artifact.started_at}
                    )
                )
            if self._screener_batch_service is None:
                return
            batch_size = self._resolve_screener_batch_size(request)
            batch_record = self._screener_batch_service.create_running_batch(
                run_id=artifact.run_id,
                batch_size=batch_size,
                max_symbols=request.max_symbols,
                top_n=request.top_n,
                started_at=artifact.started_at,
                scheme_id=(
                    scheme_snapshot.scheme_id if scheme_snapshot is not None else None
                ),
                scheme_version=(
                    scheme_snapshot.scheme_version
                    if scheme_snapshot is not None
                    else None
                ),
                scheme_name=(
                    scheme_snapshot.scheme_name if scheme_snapshot is not None else None
                ),
                scheme_snapshot_hash=(
                    scheme_snapshot.scheme_snapshot_hash
                    if scheme_snapshot is not None
                    else None
                ),
            )
            logger.info(
                "event=screener.run.started workflow=%s run_id=%s batch_id=%s batch_size=%s max_symbols=%s top_n=%s force_refresh=%s",
                definition.name,
                artifact.run_id,
                batch_record.batch_id,
                batch_size,
                request.max_symbols,
                request.top_n,
                request.force_refresh,
            )

        def _on_completed(result: WorkflowRunResult) -> None:
            if self._screener_batch_service is None:
                return
            final_output_dump = (
                result.final_output.model_dump(mode="json")
                if result.final_output is not None
                else None
            )
            self._screener_batch_service.finalize_batch(
                run_id=result.run_id,
                status=result.status,
                finished_at=result.finished_at,
                final_output=final_output_dump,
                final_output_summary=result.final_output_summary,
                error_message=result.error_message,
            )
            logger.info(
                "event=screener.run.completed workflow=%s run_id=%s status=%s scanned_symbols=%s finished_at=%s",
                definition.name,
                result.run_id,
                result.status,
                final_output_dump.get("scanned_symbols") if isinstance(final_output_dump, dict) else None,
                result.finished_at.isoformat() if result.finished_at is not None else None,
            )

        return self._start_background_workflow(
            definition,
            request,
            on_started=_on_started,
            on_completed=_on_completed,
            input_summary_overrides=(
                {
                    "scheme_id": scheme_snapshot.scheme_id,
                    "scheme_version": scheme_snapshot.scheme_version,
                    "scheme_name": scheme_snapshot.scheme_name,
                    "scheme_snapshot_hash": scheme_snapshot.scheme_snapshot_hash,
                }
                if scheme_snapshot is not None
                else None
            ),
        )

    def get_run_detail(self, run_id: str) -> WorkflowRunDetailResponse:
        artifact = self._artifact_store.load_run(run_id)
        artifact = self._resolve_running_artifact_for_read(artifact)
        visibility = self._build_runtime_visibility(
            status=artifact.status,
            workflow_name=artifact.workflow_name,
            input_summary=artifact.input_summary,
            final_output_summary=artifact.final_output_summary,
            final_output=artifact.final_output,
        )
        return WorkflowRunDetailResponse.model_validate(
            {
                "run_id": artifact.run_id,
                "workflow_name": artifact.workflow_name,
                "status": artifact.status,
                "started_at": artifact.started_at,
                "finished_at": artifact.finished_at,
                "input_summary": artifact.input_summary,
                "steps": self._to_step_summaries(artifact.steps),
                "final_output_summary": artifact.final_output_summary,
                "final_output": artifact.final_output,
                "error_message": artifact.error_message,
                "accepted": True,
                "existing_run_id": None,
                "message": None,
                **visibility,
            }
        )

    def get_latest_running_detail(
        self,
        *,
        workflow_name: str,
    ) -> WorkflowRunDetailResponse | None:
        artifact = self._find_valid_running_artifact(workflow_name=workflow_name)
        if artifact is None:
            return None
        return self.get_run_detail(artifact.run_id)

    def _start_background_workflow(
        self,
        definition: WorkflowDefinition,
        request,
        *,
        on_started: Callable[[WorkflowArtifact], None] | None = None,
        on_completed: Callable[[WorkflowRunResult], None] | None = None,
        input_summary_overrides: dict[str, Any] | None = None,
    ) -> WorkflowRunResponse:
        validated_request = definition.request_contract.model_validate(request)
        run_id = uuid4().hex
        started_at = datetime.now(timezone.utc)
        input_summary = definition.input_summary_builder(validated_request)
        if input_summary_overrides:
            input_summary.update(input_summary_overrides)
        initial_artifact = WorkflowArtifact(
            run_id=run_id,
            workflow_name=definition.name,
            status="running",
            started_at=started_at,
            finished_at=None,
            input_summary=input_summary,
            steps=tuple(),
            final_output_summary={},
            final_output=None,
            error_message=None,
        )
        self._artifact_store.save_artifact(initial_artifact)
        if on_started is not None:
            try:
                on_started(initial_artifact)
            except Exception:
                logger.exception(
                    "workflow.runtime.on_started_failed workflow=%s run_id=%s",
                    definition.name,
                    run_id,
                )
        future = self._background_executor.submit(
            self._run_background_workflow,
            definition,
            validated_request,
            run_id,
            started_at,
            on_completed,
        )
        with self._future_lock:
            self._active_futures[run_id] = future
        visibility = self._build_runtime_visibility(
            status="running",
            workflow_name=definition.name,
            input_summary=initial_artifact.input_summary,
            final_output_summary={},
            final_output=None,
        )
        return WorkflowRunResponse.model_validate(
            {
                "run_id": run_id,
                "workflow_name": definition.name,
                "status": "running",
                "started_at": started_at,
                "finished_at": None,
                "input_summary": initial_artifact.input_summary,
                "steps": [],
                "final_output_summary": {},
                "error_message": None,
                "accepted": True,
                "existing_run_id": None,
                "message": None,
                **visibility,
            }
        )

    def _run_background_workflow(
        self,
        definition: WorkflowDefinition,
        validated_request,
        run_id: str,
        started_at: datetime,
        on_completed: Callable[[WorkflowRunResult], None] | None,
    ) -> None:
        try:
            result = self._executor.execute(
                definition,
                validated_request,
                run_id=run_id,
                started_at=started_at,
                persist_initial_state=False,
            )
        except Exception as exc:
            logger.exception(
                "workflow.runtime.background_failed workflow=%s run_id=%s",
                definition.name,
                run_id,
            )
            self._mark_background_run_failed(
                run_id=run_id,
                workflow_name=definition.name,
                started_at=started_at,
                error_message=f"后台执行异常：{exc}",
            )
            return
        finally:
            with self._future_lock:
                self._active_futures.pop(run_id, None)
        if on_completed is None:
            return
        try:
            on_completed(result)
        except Exception:
            logger.exception(
                "workflow.runtime.on_completed_failed workflow=%s run_id=%s",
                definition.name,
                run_id,
            )

    def _to_run_response(self, result) -> WorkflowRunResponse:
        final_output_dump = (
            result.final_output.model_dump(mode="json")
            if result.final_output is not None
            else None
        )
        visibility = self._build_runtime_visibility(
            status=result.status,
            workflow_name=result.workflow_name,
            input_summary=result.input_summary,
            final_output_summary=result.final_output_summary,
            final_output=final_output_dump,
        )
        return WorkflowRunResponse.model_validate(
            {
                "run_id": result.run_id,
                "workflow_name": result.workflow_name,
                "status": result.status,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "input_summary": result.input_summary,
                "steps": self._to_step_summaries(result.steps),
                "final_output_summary": result.final_output_summary,
                "error_message": result.error_message,
                "accepted": True,
                "existing_run_id": None,
                "message": None,
                **visibility,
            }
        )

    def _to_step_summaries(
        self,
        steps: tuple[WorkflowStepResult, ...],
    ) -> list[WorkflowStepSummary]:
        return [
            WorkflowStepSummary(
                node_name=step.node_name,
                status=step.status,
                started_at=step.started_at,
                finished_at=step.finished_at,
                message=step.message,
                input_summary=step.input_summary,
                output_summary=step.output_summary,
                error_message=step.error_message,
            )
            for step in steps
        ]

    def _build_runtime_visibility(
        self,
        *,
        status: str,
        workflow_name: str,
        input_summary: dict[str, Any],
        final_output_summary: dict[str, Any],
        final_output: dict[str, Any] | None,
    ) -> dict[str, Any]:
        requested_mode = self._requested_runtime_mode(input_summary=input_summary)
        scheme_id = input_summary.get("scheme_id")
        scheme_version = input_summary.get("scheme_version")
        scheme_name = input_summary.get("scheme_name")
        scheme_snapshot_hash = input_summary.get("scheme_snapshot_hash")
        debate_payload = self._extract_debate_payload(final_output=final_output)
        effective_mode = (
            debate_payload.get("runtime_mode_effective")
            or debate_payload.get("runtime_mode")
            or requested_mode
        )
        failed_symbols = self._extract_failed_symbols(
            final_output_summary=final_output_summary
        )
        fallback_applied = bool(debate_payload.get("fallback_applied")) or bool(
            failed_symbols
        )
        fallback_reason = debate_payload.get("fallback_reason")
        warning_messages = list(debate_payload.get("warning_messages") or [])
        summary_warnings = final_output_summary.get("warning_messages")
        if isinstance(summary_warnings, list):
            warning_messages.extend(
                str(item) for item in summary_warnings if isinstance(item, str)
            )

        if failed_symbols:
            if fallback_reason is None:
                fallback_reason = "Some symbols failed and were skipped."
            warning_messages.append(
                f"Partial run with {len(failed_symbols)} failed symbol(s)."
            )

        provider_used = debate_payload.get("provider_used") or "workflow_runtime"
        provider_candidates = debate_payload.get("provider_candidates") or [provider_used]
        model_versions = self._extract_model_versions(
            final_output=final_output,
            final_output_summary=final_output_summary,
        )
        model_recommendation, recommendation_warning = self._resolve_model_recommendation(
            status=status,
            model_versions=model_versions,
        )
        if recommendation_warning is not None:
            warning_messages.append(recommendation_warning)
        version_recommendation_alert = self._build_version_recommendation_alert(
            model_versions=model_versions,
            model_recommendation=model_recommendation,
        )
        if version_recommendation_alert is not None:
            warning_messages.append(version_recommendation_alert)
        warning_messages = self._dedupe_messages(warning_messages)

        return {
            "provider_used": provider_used,
            "provider_candidates": provider_candidates,
            "fallback_applied": fallback_applied,
            "fallback_reason": fallback_reason,
            "runtime_mode_requested": requested_mode,
            "runtime_mode_effective": effective_mode,
            "warning_messages": warning_messages,
            "failed_symbols": failed_symbols,
            "model_recommendation": model_recommendation,
            "version_recommendation_alert": version_recommendation_alert,
            "scheme_id": scheme_id,
            "scheme_version": scheme_version,
            "scheme_name": scheme_name,
            "scheme_snapshot_hash": scheme_snapshot_hash,
        }

    def _build_existing_running_response(
        self,
        artifact: WorkflowArtifact,
    ) -> WorkflowRunResponse:
        visibility = self._build_runtime_visibility(
            status=artifact.status,
            workflow_name=artifact.workflow_name,
            input_summary=artifact.input_summary,
            final_output_summary=artifact.final_output_summary,
            final_output=artifact.final_output,
        )
        warning_messages = list(visibility.get("warning_messages", []))
        warning_messages.append("已有运行中的初筛任务，本次请求复用现有运行记录。")
        visibility["warning_messages"] = warning_messages
        return WorkflowRunResponse.model_validate(
            {
                "run_id": artifact.run_id,
                "workflow_name": artifact.workflow_name,
                "status": artifact.status,
                "started_at": artifact.started_at,
                "finished_at": artifact.finished_at,
                "input_summary": artifact.input_summary,
                "steps": self._to_step_summaries(artifact.steps),
                "final_output_summary": artifact.final_output_summary,
                "error_message": artifact.error_message,
                "accepted": False,
                "existing_run_id": artifact.run_id,
                "message": "已有运行中的初筛任务，请等待当前任务完成。",
                **visibility,
            }
        )

    def _requested_runtime_mode(self, *, input_summary: dict[str, Any]) -> str | None:
        use_llm = input_summary.get("use_llm")
        if use_llm is None:
            return None
        return "llm" if bool(use_llm) else "rule_based"

    def _extract_debate_payload(self, *, final_output: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(final_output, dict):
            return {}
        debate_review = final_output.get("debate_review")
        if not isinstance(debate_review, dict):
            return {}
        return debate_review

    def _extract_failed_symbols(self, *, final_output_summary: dict[str, Any]) -> list[str]:
        raw = final_output_summary.get("failed_symbols")
        if not isinstance(raw, list):
            return []
        symbols: list[str] = []
        for item in raw:
            if isinstance(item, str) and item:
                symbols.append(item)
        return symbols

    def _extract_model_versions(
        self,
        *,
        final_output: dict[str, Any] | None,
        final_output_summary: dict[str, Any],
    ) -> list[str]:
        versions: list[str] = []
        seen: set[str] = set()

        def add_version(value: Any) -> None:
            if not isinstance(value, str):
                return
            normalized = value.strip()
            if normalized == "" or normalized in seen:
                return
            seen.add(normalized)
            versions.append(normalized)

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                add_version(value.get("predictive_model_version"))
                predictive_snapshot = value.get("predictive_snapshot")
                if isinstance(predictive_snapshot, dict):
                    add_version(predictive_snapshot.get("model_version"))
                for nested in value.values():
                    walk(nested)
                return
            if isinstance(value, list):
                for item in value:
                    walk(item)

        raw_versions = final_output_summary.get("predictive_model_versions")
        if isinstance(raw_versions, list):
            for item in raw_versions:
                add_version(item)
        if isinstance(final_output, dict):
            walk(final_output)
        return versions

    def _resolve_model_recommendation(
        self,
        *,
        status: str,
        model_versions: list[str],
    ) -> tuple[dict[str, Any] | None, str | None]:
        if (
            self._evaluation_service is None
            or not model_versions
            or status == "running"
        ):
            return None, None

        default_model_version = self._get_default_model_version()
        primary_model_version = (
            default_model_version
            if default_model_version in model_versions
            else model_versions[0]
        )
        warning_message = None
        if len(model_versions) > 1:
            warning_message = (
                "本次工作流检测到多个预测模型版本，建议关注版本一致性。"
            )
        recommendation = self._load_model_recommendation(primary_model_version)
        return recommendation, warning_message

    def _load_model_recommendation(self, model_version: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        cached = self._recommendation_cache.get(model_version)
        if cached is not None and now - cached[0] < self._recommendation_cache_ttl:
            return cached[1]
        logger.debug(
            "workflow.runtime.recommendation_cache_miss model_version=%s",
            model_version,
        )
        return None

    def _build_version_recommendation_alert(
        self,
        *,
        model_versions: list[str],
        model_recommendation: dict[str, Any] | None,
    ) -> str | None:
        if model_recommendation is None:
            return None
        recommended_model_version = model_recommendation.get("recommended_model_version")
        if not isinstance(recommended_model_version, str) or recommended_model_version == "":
            return None
        default_model_version = self._get_default_model_version()
        if (
            default_model_version is not None
            and default_model_version != recommended_model_version
        ):
            return (
                "模型版本建议发生变化：默认版本为 "
                f"{default_model_version}，建议关注 {recommended_model_version}。"
            )
        if model_versions and model_versions[0] != recommended_model_version:
            return (
                "当前运行主要使用模型 "
                f"{model_versions[0]}，评估建议为 {recommended_model_version}。"
            )
        return None

    def _get_default_model_version(self) -> str | None:
        if self._experiment_service is None:
            return None
        try:
            default_version = self._experiment_service.get_default_model_version()
        except Exception:
            logger.exception("workflow.runtime.default_model_version_failed")
            return None
        if not isinstance(default_version, str):
            return None
        normalized = default_version.strip()
        return normalized if normalized else None

    def _dedupe_messages(self, messages: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for message in messages:
            text = str(message).strip()
            if text == "" or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _find_valid_running_artifact(self, *, workflow_name: str) -> WorkflowArtifact | None:
        running = self._artifact_store.find_latest_run(
            workflow_name=workflow_name,
            status="running",
        )
        if running is None:
            return None

        now = datetime.now(timezone.utc)

        with self._future_lock:
            future = self._active_futures.get(running.run_id)
            if future is not None and not future.done():
                return running
            if future is not None and future.done():
                self._active_futures.pop(running.run_id, None)

        if now - running.started_at < self._stale_running_timeout:
            return running

        self._mark_stale_running_artifact_failed(running, finished_at=now)
        return None

    def _mark_stale_running_artifact_failed(
        self,
        artifact: WorkflowArtifact,
        *,
        finished_at: datetime,
    ) -> None:
        reason = "检测到陈旧的运行中记录，系统已自动标记为失败并允许重新发起任务。"
        failed_artifact = WorkflowArtifact(
            run_id=artifact.run_id,
            workflow_name=artifact.workflow_name,
            status="failed",
            started_at=artifact.started_at,
            finished_at=finished_at,
            input_summary=artifact.input_summary,
            steps=artifact.steps,
            final_output_summary=artifact.final_output_summary,
            final_output=artifact.final_output,
            error_message=artifact.error_message or reason,
        )
        self._artifact_store.save_artifact(failed_artifact)
        if self._screener_batch_service is None:
            return
        self._screener_batch_service.finalize_batch(
            run_id=artifact.run_id,
            status="failed",
            finished_at=finished_at,
            final_output=artifact.final_output,
            final_output_summary=artifact.final_output_summary,
            error_message=reason,
        )

    def _resolve_running_artifact_for_read(
        self,
        artifact: WorkflowArtifact,
    ) -> WorkflowArtifact:
        if artifact.status != "running":
            return artifact

        now = datetime.now(timezone.utc)
        with self._future_lock:
            future = self._active_futures.get(artifact.run_id)
            if future is not None and not future.done():
                return artifact
            if future is not None and future.done():
                self._active_futures.pop(artifact.run_id, None)

        if now - artifact.started_at < self._stale_running_timeout:
            return artifact

        self._mark_stale_running_artifact_failed(artifact, finished_at=now)
        return self._artifact_store.load_run(artifact.run_id)

    def _mark_background_run_failed(
        self,
        *,
        run_id: str,
        workflow_name: str,
        started_at: datetime,
        error_message: str,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        try:
            existing = self._artifact_store.load_run(run_id)
            steps = existing.steps
            input_summary = existing.input_summary
            final_output_summary = existing.final_output_summary
            final_output = existing.final_output
        except FileNotFoundError:
            steps = tuple()
            input_summary = {}
            final_output_summary = {}
            final_output = None

        failed_artifact = WorkflowArtifact(
            run_id=run_id,
            workflow_name=workflow_name,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            input_summary=input_summary,
            steps=steps,
            final_output_summary=final_output_summary,
            final_output=final_output,
            error_message=error_message,
        )
        self._artifact_store.save_artifact(failed_artifact)
        if self._screener_batch_service is not None:
            self._screener_batch_service.finalize_batch(
                run_id=run_id,
                status="failed",
                finished_at=finished_at,
                final_output=final_output,
                final_output_summary=final_output_summary,
                error_message=error_message,
            )

    def _resolve_screener_batch_size(self, request: ScreenerWorkflowRunRequest) -> int:
        if request.batch_size is not None:
            return request.batch_size
        if request.max_symbols is not None:
            return request.max_symbols
        return 50
