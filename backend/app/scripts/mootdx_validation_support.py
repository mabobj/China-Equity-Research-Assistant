"""mootdx 验证脚本共用支持函数。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time
import importlib.util
from pathlib import Path
import sys
from typing import Any, Callable

from app.services.data_service.exceptions import DataNotFoundError
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.provider_registry import ProviderRegistry
from app.services.data_service.providers.mootdx_provider import MootdxProvider


@dataclass(frozen=True)
class ValidationSummary:
    symbol: str
    tdx_dir: str
    overall_status: str
    daily_status: str
    minute_status: str
    timeline_status: str
    daily_count: int
    minute_count: int
    timeline_count: int
    daily_latest_date: str | None
    minute_latest_datetime: str | None
    timeline_latest_time: str | None


def to_serializable(value: Any) -> Any:
    if isinstance(value, (date, datetime, time, Path)):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [to_serializable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_serializable(item) for key, item in value.items()}
    return value


def count_files(path: Path) -> int | None:
    if not path.exists() or not path.is_dir():
        return None
    return sum(1 for item in path.iterdir() if item.is_file())


def build_environment_report(tdx_dir: Path) -> dict[str, Any]:
    sh_lday = tdx_dir / "vipdoc" / "sh" / "lday"
    sz_lday = tdx_dir / "vipdoc" / "sz" / "lday"
    sh_minline = tdx_dir / "vipdoc" / "sh" / "minline"
    sz_minline = tdx_dir / "vipdoc" / "sz" / "minline"
    sh_fzline = tdx_dir / "vipdoc" / "sh" / "fzline"
    sz_fzline = tdx_dir / "vipdoc" / "sz" / "fzline"

    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "mootdx_installed": importlib.util.find_spec("mootdx") is not None,
        "tdx_dir_input": str(tdx_dir),
        "tdx_dir_resolved": str(tdx_dir.resolve()),
        "tdx_dir_exists": tdx_dir.exists(),
        "directory_checks": {
            "sh_lday_exists": sh_lday.exists(),
            "sz_lday_exists": sz_lday.exists(),
            "sh_minline_exists": sh_minline.exists(),
            "sz_minline_exists": sz_minline.exists(),
            "sh_fzline_exists": sh_fzline.exists(),
            "sz_fzline_exists": sz_fzline.exists(),
            "sh_lday_file_count": count_files(sh_lday),
            "sz_lday_file_count": count_files(sz_lday),
            "sh_minline_file_count": count_files(sh_minline),
            "sz_minline_file_count": count_files(sz_minline),
            "sh_fzline_file_count": count_files(sh_fzline),
            "sz_fzline_file_count": count_files(sz_fzline),
        },
    }


def create_mootdx_service(
    tdx_dir: Path,
) -> tuple[MootdxProvider, MarketDataService]:
    provider = MootdxProvider(tdx_dir=tdx_dir)
    service = MarketDataService(
        providers=ProviderRegistry([provider]),
        local_store=None,
    )
    return provider, service


def run_mootdx_symbol_validation(
    *,
    tdx_dir: Path,
    symbol: str,
    frequency: str = "1m",
    minute_limit: int = 20,
    timeline_limit: int = 10,
) -> dict[str, Any]:
    provider, service = create_mootdx_service(tdx_dir)
    environment_report = build_environment_report(tdx_dir)
    capability_report = service.get_provider_capability_reports()
    health_report = service.get_provider_health_reports()
    provider_available = provider.is_available()
    unavailable_reason = provider.get_unavailable_reason()

    if provider_available:
        daily_result = _build_daily_result(service, symbol)
        minute_result = _build_minute_result(
            service,
            symbol,
            frequency=frequency,
            limit=minute_limit,
        )
        timeline_result = _build_timeline_result(
            service,
            symbol,
            limit=timeline_limit,
        )
        minute_result = attach_data_hints(
            minute_result,
            environment_report,
            category="minute",
        )
        timeline_result = attach_data_hints(
            timeline_result,
            environment_report,
            category="timeline",
        )
    else:
        daily_result = _build_unavailable_result("daily", unavailable_reason)
        minute_result = _build_unavailable_result("minute", unavailable_reason)
        timeline_result = _build_unavailable_result("timeline", unavailable_reason)

    overall_status = determine_overall_status(
        provider_available=provider_available,
        daily_status=daily_result["status"],
        minute_status=minute_result["status"],
        timeline_status=timeline_result["status"],
    )

    summary = ValidationSummary(
        symbol=symbol,
        tdx_dir=str(tdx_dir),
        overall_status=overall_status,
        daily_status=daily_result["status"],
        minute_status=minute_result["status"],
        timeline_status=timeline_result["status"],
        daily_count=int(daily_result.get("count", 0) or 0),
        minute_count=int(minute_result.get("count", 0) or 0),
        timeline_count=int(timeline_result.get("count", 0) or 0),
        daily_latest_date=daily_result.get("latest_date"),
        minute_latest_datetime=minute_result.get("latest_datetime"),
        timeline_latest_time=timeline_result.get("latest_time"),
    )

    payload = {
        "status": overall_status,
        "summary": asdict(summary),
        "environment_report": environment_report,
        "provider_capability_report": to_serializable(capability_report),
        "provider_health_report": to_serializable(health_report),
        "daily_result": daily_result,
        "minute_result": minute_result,
        "timeline_result": timeline_result,
    }
    if unavailable_reason is not None:
        payload["provider_unavailable_reason"] = unavailable_reason
    return payload


def determine_overall_status(
    *,
    provider_available: bool,
    daily_status: str,
    minute_status: str,
    timeline_status: str,
) -> str:
    if not provider_available or daily_status == "failed":
        return "failed"
    if minute_status == "success" or timeline_status == "success":
        return "success"
    if daily_status == "success":
        return "partial_success"
    return "failed"


def attach_data_hints(
    result: dict[str, Any],
    environment_report: dict[str, Any],
    *,
    category: str,
) -> dict[str, Any]:
    if result["status"] not in {"empty", "failed"}:
        return result

    directory_checks = environment_report["directory_checks"]
    if category == "minute":
        if (
            directory_checks["sh_minline_file_count"] == 0
            and directory_checks["sz_minline_file_count"] == 0
        ):
            result["hint"] = "本地 minline 目录存在，但当前未发现分钟线文件。"
    if category == "timeline":
        if (
            directory_checks["sh_fzline_file_count"] == 0
            and directory_checks["sz_fzline_file_count"] == 0
        ):
            result["hint"] = "本地 fzline 目录存在，但当前未发现分时线文件。"
    return result


def _build_unavailable_result(label: str, unavailable_reason: str | None) -> dict[str, Any]:
    return {
        "label": label,
        "status": "failed",
        "error_type": "ProviderError",
        "error_message": unavailable_reason,
    }


def _run_check(
    label: str,
    loader: Callable[[], Any],
    preview_builder: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    try:
        payload = loader()
    except DataNotFoundError as exc:
        return {
            "label": label,
            "status": "empty",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
    except Exception as exc:  # pragma: no cover - 依赖本地环境
        return {
            "label": label,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }

    return {
        "label": label,
        "status": "success" if payload.count > 0 else "empty",
        **preview_builder(payload),
    }


def _build_daily_result(service: MarketDataService, symbol: str) -> dict[str, Any]:
    return _run_check(
        label="daily",
        loader=lambda: service.get_daily_bars(symbol),
        preview_builder=lambda payload: {
            "count": payload.count,
            "latest_date": (
                payload.bars[-1].trade_date.isoformat() if payload.bars else None
            ),
            "preview": [bar.model_dump() for bar in payload.bars[-5:]],
            "full_bars": payload.bars,
        },
    )


def _build_minute_result(
    service: MarketDataService,
    symbol: str,
    *,
    frequency: str,
    limit: int,
) -> dict[str, Any]:
    return _run_check(
        label="minute",
        loader=lambda: service.get_intraday_bars(
            symbol,
            frequency=frequency,
            limit=limit,
        ),
        preview_builder=lambda payload: {
            "frequency": frequency,
            "count": payload.count,
            "latest_datetime": (
                payload.bars[-1].trade_datetime.isoformat() if payload.bars else None
            ),
            "preview": [bar.model_dump() for bar in payload.bars[-5:]],
        },
    )


def _build_timeline_result(
    service: MarketDataService,
    symbol: str,
    *,
    limit: int,
) -> dict[str, Any]:
    return _run_check(
        label="timeline",
        loader=lambda: service.get_timeline(symbol, limit=limit),
        preview_builder=lambda payload: {
            "count": payload.count,
            "latest_time": (
                payload.points[-1].trade_time.isoformat() if payload.points else None
            ),
            "preview": [point.model_dump() for point in payload.points[-5:]],
        },
    )
