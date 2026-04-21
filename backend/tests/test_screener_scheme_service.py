"""Tests for screener scheme file-backed service."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.schemas.screener_scheme import (
    CreateScreenerSchemeRequest,
    CreateScreenerSchemeVersionRequest,
    ScreenerRunContextSnapshot,
    ScreenerSchemeConfig,
    UpdateScreenerSchemeRequest,
)
from app.services.screener_service.scheme_hashing import hash_scheme_config
from app.services.screener_service.scheme_service import ScreenerSchemeService


def _sample_config() -> ScreenerSchemeConfig:
    return ScreenerSchemeConfig(
        universe_filter_config={"board": "main"},
        factor_selection_config={"enabled_groups": ["trend", "quality"]},
        factor_weight_config={"alpha": 0.5, "trigger": 0.3, "risk": 0.2},
        threshold_config={"ready_min_score": 78},
        quality_gate_config={"drop_failed_quality": True},
        bucket_rule_config={"ready_bucket": "READY_TO_BUY"},
    )


def test_scheme_service_bootstraps_builtin_default_scheme(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)

    schemes = service.list_schemes()

    assert schemes
    assert schemes[0].scheme_id == "default_builtin_scheme"
    assert schemes[0].is_builtin is True
    assert schemes[0].is_default is True
    current_version = service.get_current_version("default_builtin_scheme")
    assert current_version is not None
    assert current_version.scheme_version == "legacy_v1"


def test_scheme_service_create_version_updates_current_version(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)
    scheme = service.create_scheme(
        CreateScreenerSchemeRequest(
            name="趋势优先方案",
            description="用于测试的方案。",
            is_default=False,
        )
    )

    created_version = service.create_version(
        scheme.scheme_id,
        CreateScreenerSchemeVersionRequest(
            version_label="v1",
            change_note="首次版本",
            created_by="tester",
            config=_sample_config(),
        ),
    )

    stored_scheme = service.get_scheme(scheme.scheme_id)
    versions = service.list_versions(scheme.scheme_id)

    assert stored_scheme.current_version == created_version.scheme_version
    assert stored_scheme.status == "active"
    assert len(versions) == 1
    assert versions[0].snapshot_hash == hash_scheme_config(
        _sample_config().model_dump(mode="json")
    )


def test_scheme_service_only_keeps_one_default_scheme(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)
    created = service.create_scheme(
        CreateScreenerSchemeRequest(
            name="新的默认方案",
            description=None,
            is_default=True,
        )
    )

    builtin = service.get_scheme("default_builtin_scheme")
    updated = service.get_scheme(created.scheme_id)

    assert builtin.is_default is False
    assert updated.is_default is True


def test_scheme_service_persists_run_context_snapshot(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)
    snapshot = ScreenerRunContextSnapshot(
        run_id="run-001",
        scheme_id="default_builtin_scheme",
        scheme_version="legacy_v1",
        scheme_name="默认内置方案",
        scheme_snapshot_hash="hash-001",
        trade_date=date(2026, 4, 21),
        started_at=datetime(2026, 4, 21, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=None,
        workflow_name="screener_run",
        runtime_params={"batch_size": 50},
        effective_scheme_config=_sample_config(),
    )

    service.save_run_context(snapshot)
    loaded = service.load_run_context("run-001")

    assert loaded is not None
    assert loaded.run_id == "run-001"
    assert loaded.effective_scheme_config.factor_weight_config["alpha"] == 0.5


def test_scheme_service_update_scheme_metadata(tmp_path) -> None:
    service = ScreenerSchemeService(root_dir=tmp_path)
    scheme = service.create_scheme(
        CreateScreenerSchemeRequest(
            name="方案A",
            description="旧描述",
            is_default=False,
        )
    )

    updated = service.update_scheme(
        scheme.scheme_id,
        UpdateScreenerSchemeRequest(
            name="方案A-更新",
            description="新描述",
            status="archived",
        ),
    )

    assert updated.name == "方案A-更新"
    assert updated.description == "新描述"
    assert updated.status == "archived"

