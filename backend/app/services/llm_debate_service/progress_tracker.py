"""LLM debate 杩愯杩涘害璺熻釜銆?"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.schemas.debate import DebateReviewProgress

_RETENTION_WINDOW = timedelta(hours=2)


@dataclass
class _ProgressState:
    symbol: str
    request_id: str | None
    status: str
    stage: str
    runtime_mode: str | None
    current_step: str | None
    completed_steps: int
    total_steps: int
    message: str
    started_at: datetime | None
    updated_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    recent_steps: list[str] = field(default_factory=list)


class DebateProgressTracker:
    """杞婚噺鍐呭瓨杩涘害璺熻釜鍣ㄣ€?"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._states: dict[str, _ProgressState] = {}

    def start(
        self,
        *,
        symbol: str,
        request_id: str | None,
        runtime_mode: str | None,
        message: str,
    ) -> None:
        now = self._utcnow()
        state = _ProgressState(
            symbol=symbol,
            request_id=request_id,
            status="running",
            stage="building_inputs" if runtime_mode == "llm" else "rule_based",
            runtime_mode=runtime_mode,
            current_step=None,
            completed_steps=0,
            total_steps=0,
            message=message,
            started_at=now,
            updated_at=now,
            finished_at=None,
            error_message=None,
            recent_steps=[],
        )
        with self._lock:
            self._cleanup_locked(now=now)
            self._states[self._build_key(symbol, request_id)] = state

    def update(
        self,
        *,
        symbol: str,
        request_id: str | None,
        status: str = "running",
        stage: str,
        runtime_mode: str | None = None,
        current_step: str | None = None,
        completed_steps: int | None = None,
        total_steps: int | None = None,
        message: str,
        error_message: str | None = None,
    ) -> None:
        now = self._utcnow()
        with self._lock:
            self._cleanup_locked(now=now)
            key = self._build_key(symbol, request_id)
            state = self._states.get(key)
            if state is None:
                state = _ProgressState(
                    symbol=symbol,
                    request_id=request_id,
                    status=status,
                    stage=stage,
                    runtime_mode=runtime_mode,
                    current_step=current_step,
                    completed_steps=completed_steps or 0,
                    total_steps=total_steps or 0,
                    message=message,
                    started_at=now,
                    updated_at=now,
                    finished_at=None,
                    error_message=error_message,
                    recent_steps=[],
                )
                self._states[key] = state
            else:
                state.status = status
                state.stage = stage
                state.runtime_mode = runtime_mode if runtime_mode is not None else state.runtime_mode
                state.current_step = current_step
                state.completed_steps = (
                    completed_steps if completed_steps is not None else state.completed_steps
                )
                state.total_steps = total_steps if total_steps is not None else state.total_steps
                state.message = message
                state.updated_at = now
                state.error_message = error_message

            if current_step:
                self._append_recent_step(state, current_step)

            if status in {"completed", "failed", "fallback"}:
                state.finished_at = now
                state.updated_at = now

    def get(
        self,
        *,
        symbol: str,
        request_id: str | None,
        runtime_mode: str | None = None,
    ) -> DebateReviewProgress:
        now = self._utcnow()
        with self._lock:
            self._cleanup_locked(now=now)
            state = self._states.get(self._build_key(symbol, request_id))
            if state is None:
                return DebateReviewProgress(
                    symbol=symbol,
                    request_id=request_id,
                    status="idle",
                    stage="idle",
                    runtime_mode=runtime_mode,
                    message="褰撳墠娌℃湁杩愯涓殑 Debate Review 浠诲姟銆?",
                )
            return self._to_schema(state)

    def _append_recent_step(self, state: _ProgressState, step: str) -> None:
        if state.recent_steps and state.recent_steps[-1] == step:
            return
        state.recent_steps.append(step)
        if len(state.recent_steps) > 8:
            state.recent_steps = state.recent_steps[-8:]

    def _cleanup_locked(self, *, now: datetime) -> None:
        expired_keys = [
            key
            for key, state in self._states.items()
            if state.finished_at is not None and now - state.finished_at > _RETENTION_WINDOW
        ]
        for key in expired_keys:
            self._states.pop(key, None)

    @staticmethod
    def _to_schema(state: _ProgressState) -> DebateReviewProgress:
        return DebateReviewProgress(
            symbol=state.symbol,
            request_id=state.request_id,
            status=state.status,
            stage=state.stage,
            runtime_mode=state.runtime_mode,
            current_step=state.current_step,
            completed_steps=state.completed_steps,
            total_steps=state.total_steps,
            message=state.message,
            started_at=state.started_at,
            updated_at=state.updated_at,
            finished_at=state.finished_at,
            error_message=state.error_message,
            recent_steps=list(state.recent_steps),
        )

    @staticmethod
    def _build_key(symbol: str, request_id: str | None) -> str:
        return f"{symbol}:{request_id or '_default'}"

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)
