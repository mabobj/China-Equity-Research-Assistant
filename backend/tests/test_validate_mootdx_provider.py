"""Tests for mootdx validation script helpers."""

from pathlib import Path

from app.scripts.validate_mootdx_provider import (
    _build_environment_report,
    _determine_overall_status,
)


def test_determine_overall_status_supports_partial_success() -> None:
    status = _determine_overall_status(
        provider_available=True,
        daily_status="success",
        minute_status="empty",
        timeline_status="empty",
    )

    assert status == "partial_success"


def test_build_environment_report_counts_local_directories(tmp_path: Path) -> None:
    sh_lday = tmp_path / "vipdoc" / "sh" / "lday"
    sz_lday = tmp_path / "vipdoc" / "sz" / "lday"
    sh_minline = tmp_path / "vipdoc" / "sh" / "minline"
    sh_fzline = tmp_path / "vipdoc" / "sh" / "fzline"

    sh_lday.mkdir(parents=True)
    sz_lday.mkdir(parents=True)
    sh_minline.mkdir(parents=True)
    sh_fzline.mkdir(parents=True)

    (sh_lday / "sh600519.day").write_bytes(b"test")
    (sz_lday / "sz000001.day").write_bytes(b"test")

    report = _build_environment_report(tmp_path)

    assert report["tdx_dir_exists"] is True
    assert report["directory_checks"]["sh_lday_file_count"] == 1
    assert report["directory_checks"]["sz_lday_file_count"] == 1
    assert report["directory_checks"]["sh_minline_file_count"] == 0
    assert report["directory_checks"]["sh_fzline_file_count"] == 0
