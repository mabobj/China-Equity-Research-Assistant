"""File-backed service for factor-first screener schemes."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.schemas.screener_scheme import (
    CreateScreenerSchemeRequest,
    CreateScreenerSchemeVersionRequest,
    ScreenerRunContextSnapshot,
    ScreenerScheme,
    ScreenerSchemeConfig,
    ScreenerSchemeVersion,
    UpdateScreenerSchemeRequest,
)
from app.services.screener_service.scheme_hashing import hash_scheme_config

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_DEFAULT_SCHEME_ID = "default_builtin_scheme"
_DEFAULT_SCHEME_VERSION = "legacy_v1"


def _now() -> datetime:
    return datetime.now(_SHANGHAI_TZ)


def _default_scheme_config() -> ScreenerSchemeConfig:
    return ScreenerSchemeConfig(
        universe_filter_config={"profile": "default_a_share_universe"},
        factor_selection_config={
            "enabled_groups": ["trend", "trigger", "risk", "quality"]
        },
        factor_weight_config={"alpha": 0.45, "trigger": 0.35, "risk": 0.20},
        threshold_config={"ready_min_score": 75, "watch_min_score": 55},
        quality_gate_config={"allow_warning_quality": True, "drop_failed_quality": True},
        bucket_rule_config={
            "ready_bucket": "READY_TO_BUY",
            "watch_pullback_bucket": "WATCH_PULLBACK",
            "watch_breakout_bucket": "WATCH_BREAKOUT",
            "research_only_bucket": "RESEARCH_ONLY",
        },
    )


class ScreenerSchemeNotFoundError(KeyError):
    """Raised when a screener scheme does not exist."""


class ScreenerSchemeVersionNotFoundError(KeyError):
    """Raised when a screener scheme version does not exist."""


class ScreenerSchemeService:
    """Manage screener schemes, immutable versions, and run snapshots."""

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._scheme_dir = root_dir / "screener_schemes"
        self._version_dir = root_dir / "screener_scheme_versions"
        self._run_context_dir = root_dir / "screener_run_contexts"
        self._lock = Lock()
        self._scheme_dir.mkdir(parents=True, exist_ok=True)
        self._version_dir.mkdir(parents=True, exist_ok=True)
        self._run_context_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_builtin_default_scheme()

    def list_schemes(self) -> list[ScreenerScheme]:
        with self._lock:
            return sorted(
                self._load_all_schemes(),
                key=lambda item: (item.is_default, item.updated_at, item.scheme_id),
                reverse=True,
            )

    def create_scheme(self, request: CreateScreenerSchemeRequest) -> ScreenerScheme:
        with self._lock:
            now = _now()
            if request.is_default:
                self._clear_default_flag()
            scheme = ScreenerScheme(
                scheme_id=f"sch-{uuid4().hex[:16]}",
                name=request.name.strip(),
                description=request.description,
                status="draft",
                created_at=now,
                updated_at=now,
                current_version=None,
                is_builtin=False,
                is_default=request.is_default,
            )
            self._save_scheme(scheme)
            return scheme

    def get_scheme(self, scheme_id: str) -> ScreenerScheme:
        scheme = self._load_scheme(scheme_id)
        if scheme is None:
            raise ScreenerSchemeNotFoundError(scheme_id)
        return scheme

    def update_scheme(
        self,
        scheme_id: str,
        request: UpdateScreenerSchemeRequest,
    ) -> ScreenerScheme:
        with self._lock:
            scheme = self.get_scheme(scheme_id)
            updates = request.model_dump(exclude_unset=True)
            if "name" in updates and updates["name"] is not None:
                updates["name"] = updates["name"].strip()
            if updates.get("is_default") is True:
                self._clear_default_flag()
            updated = scheme.model_copy(
                update={
                    **updates,
                    "updated_at": _now(),
                }
            )
            self._save_scheme(updated)
            return updated

    def list_versions(self, scheme_id: str) -> list[ScreenerSchemeVersion]:
        self.get_scheme(scheme_id)
        with self._lock:
            versions = self._load_all_versions(scheme_id)
            return sorted(
                versions,
                key=lambda item: (item.created_at, item.scheme_version),
                reverse=True,
            )

    def get_version(self, scheme_id: str, scheme_version: str) -> ScreenerSchemeVersion:
        version = self._load_version(scheme_id, scheme_version)
        if version is None:
            raise ScreenerSchemeVersionNotFoundError(f"{scheme_id}:{scheme_version}")
        return version

    def get_current_version(self, scheme_id: str) -> ScreenerSchemeVersion | None:
        scheme = self.get_scheme(scheme_id)
        if scheme.current_version is None:
            return None
        return self.get_version(scheme_id, scheme.current_version)

    def resolve_scheme_selection(
        self,
        *,
        scheme_id: str | None = None,
        scheme_version: str | None = None,
    ) -> tuple[ScreenerScheme, ScreenerSchemeVersion]:
        resolved_scheme_id = scheme_id or self.get_default_scheme().scheme_id
        scheme = self.get_scheme(resolved_scheme_id)
        resolved_version = scheme_version or scheme.current_version
        if resolved_version is None:
            raise ScreenerSchemeVersionNotFoundError(
                f"{resolved_scheme_id}:current_version_missing"
            )
        version = self.get_version(resolved_scheme_id, resolved_version)
        return scheme, version

    def get_default_scheme(self) -> ScreenerScheme:
        schemes = self.list_schemes()
        for scheme in schemes:
            if scheme.is_default:
                return scheme
        return self.get_scheme(_DEFAULT_SCHEME_ID)

    def create_version(
        self,
        scheme_id: str,
        request: CreateScreenerSchemeVersionRequest,
    ) -> ScreenerSchemeVersion:
        with self._lock:
            scheme = self.get_scheme(scheme_id)
            created_at = _now()
            snapshot_hash = hash_scheme_config(request.config.model_dump(mode="json"))
            version = ScreenerSchemeVersion(
                scheme_id=scheme_id,
                scheme_version=f"sv-{uuid4().hex[:16]}",
                version_label=request.version_label.strip(),
                created_at=created_at,
                created_by=request.created_by,
                change_note=request.change_note,
                snapshot_hash=snapshot_hash,
                config=request.config,
            )
            self._save_version(version)
            updated_scheme = scheme.model_copy(
                update={
                    "current_version": version.scheme_version,
                    "updated_at": created_at,
                    "status": "active" if scheme.status == "draft" else scheme.status,
                }
            )
            self._save_scheme(updated_scheme)
            return version

    def save_run_context(self, snapshot: ScreenerRunContextSnapshot) -> ScreenerRunContextSnapshot:
        with self._lock:
            file_path = self._run_context_file(snapshot.run_id)
            file_path.write_text(
                snapshot.model_dump_json(indent=2),
                encoding="utf-8",
            )
        return snapshot

    def load_run_context(self, run_id: str) -> ScreenerRunContextSnapshot | None:
        file_path = self._run_context_file(run_id)
        if not file_path.exists():
            return None
        return ScreenerRunContextSnapshot.model_validate_json(
            file_path.read_text(encoding="utf-8")
        )

    def build_run_context_snapshot(
        self,
        *,
        run_id: str,
        workflow_name: str,
        trade_date: date,
        started_at: datetime,
        runtime_params: dict[str, object],
        scheme_id: str | None = None,
        scheme_version: str | None = None,
    ) -> ScreenerRunContextSnapshot:
        scheme, version = self.resolve_scheme_selection(
            scheme_id=scheme_id,
            scheme_version=scheme_version,
        )
        return ScreenerRunContextSnapshot(
            run_id=run_id,
            scheme_id=scheme.scheme_id,
            scheme_version=version.scheme_version,
            scheme_name=scheme.name,
            scheme_snapshot_hash=version.snapshot_hash,
            trade_date=trade_date,
            started_at=started_at,
            finished_at=None,
            workflow_name=workflow_name,
            runtime_params=runtime_params,
            effective_scheme_config=version.config,
        )

    def _ensure_builtin_default_scheme(self) -> None:
        with self._lock:
            existing = self._load_scheme(_DEFAULT_SCHEME_ID)
            if existing is not None:
                return
            created_at = _now()
            version = ScreenerSchemeVersion(
                scheme_id=_DEFAULT_SCHEME_ID,
                scheme_version=_DEFAULT_SCHEME_VERSION,
                version_label="Legacy Builtin",
                created_at=created_at,
                created_by="system",
                change_note="Bootstrap default builtin scheme.",
                snapshot_hash=hash_scheme_config(
                    _default_scheme_config().model_dump(mode="json")
                ),
                config=_default_scheme_config(),
            )
            scheme = ScreenerScheme(
                scheme_id=_DEFAULT_SCHEME_ID,
                name="默认内置方案",
                description="兼容当前初筛主链的内置默认方案。",
                status="active",
                created_at=created_at,
                updated_at=created_at,
                current_version=_DEFAULT_SCHEME_VERSION,
                is_builtin=True,
                is_default=True,
            )
            self._save_version(version)
            self._save_scheme(scheme)

    def _clear_default_flag(self) -> None:
        for scheme in self._load_all_schemes():
            if not scheme.is_default:
                continue
            self._save_scheme(
                scheme.model_copy(update={"is_default": False, "updated_at": _now()})
            )

    def _load_all_schemes(self) -> list[ScreenerScheme]:
        schemes: list[ScreenerScheme] = []
        for file_path in self._scheme_dir.glob("*.json"):
            schemes.append(
                ScreenerScheme.model_validate_json(file_path.read_text(encoding="utf-8"))
            )
        return schemes

    def _load_scheme(self, scheme_id: str) -> ScreenerScheme | None:
        file_path = self._scheme_file(scheme_id)
        if not file_path.exists():
            return None
        return ScreenerScheme.model_validate_json(file_path.read_text(encoding="utf-8"))

    def _load_all_versions(self, scheme_id: str) -> list[ScreenerSchemeVersion]:
        version_dir = self._version_dir / scheme_id
        if not version_dir.exists():
            return []
        versions: list[ScreenerSchemeVersion] = []
        for file_path in version_dir.glob("*.json"):
            versions.append(
                ScreenerSchemeVersion.model_validate_json(
                    file_path.read_text(encoding="utf-8")
                )
            )
        return versions

    def _load_version(
        self,
        scheme_id: str,
        scheme_version: str,
    ) -> ScreenerSchemeVersion | None:
        file_path = self._version_file(scheme_id, scheme_version)
        if not file_path.exists():
            return None
        return ScreenerSchemeVersion.model_validate_json(
            file_path.read_text(encoding="utf-8")
        )

    def _save_scheme(self, scheme: ScreenerScheme) -> None:
        self._scheme_file(scheme.scheme_id).write_text(
            scheme.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _save_version(self, version: ScreenerSchemeVersion) -> None:
        version_dir = self._version_dir / version.scheme_id
        version_dir.mkdir(parents=True, exist_ok=True)
        self._version_file(version.scheme_id, version.scheme_version).write_text(
            version.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _scheme_file(self, scheme_id: str) -> Path:
        return self._scheme_dir / f"{scheme_id}.json"

    def _version_file(self, scheme_id: str, scheme_version: str) -> Path:
        return self._version_dir / scheme_id / f"{scheme_version}.json"

    def _run_context_file(self, run_id: str) -> Path:
        return self._run_context_dir / f"{run_id}.json"
