"""验证 mootdx provider 的本地行情读取能力。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Callable

from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.exceptions import DataNotFoundError
from app.services.data_service.provider_registry import ProviderRegistry
from app.services.data_service.providers.mootdx_provider import MootdxProvider


@dataclass(frozen=True)
class _ValidationSummary:
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证 mootdx 本地行情 provider。")
    parser.add_argument("--tdxdir", required=True, help="通达信安装目录。")
    parser.add_argument("--symbol", required=True, help="股票代码，例如 600519.SH。")
    parser.add_argument(
        "--frequency",
        default="1m",
        help="分钟线频率标签，默认 1m。",
    )
    parser.add_argument(
        "--minute-limit",
        type=int,
        default=20,
        help="分钟线样本数量，默认 20。",
    )
    parser.add_argument(
        "--timeline-limit",
        type=int,
        default=10,
        help="分时线样本数量，默认 10。",
    )
    return parser.parse_args()


def _to_serializable(value: Any) -> Any:
    if isinstance(value, (datetime, Path)):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_to_serializable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_serializable(item) for key, item in value.items()}
    return value


def _count_files(path: Path) -> int | None:
    if not path.exists() or not path.is_dir():
        return None
    return sum(1 for item in path.iterdir() if item.is_file())


def _build_environment_report(tdx_dir: Path) -> dict[str, Any]:
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
            "sh_lday_file_count": _count_files(sh_lday),
            "sz_lday_file_count": _count_files(sz_lday),
            "sh_minline_file_count": _count_files(sh_minline),
            "sz_minline_file_count": _count_files(sz_minline),
            "sh_fzline_file_count": _count_files(sh_fzline),
            "sz_fzline_file_count": _count_files(sz_fzline),
        },
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
        },
    )


def _build_minute_result(
    service: MarketDataService,
    symbol: str,
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


def _determine_overall_status(
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


def _attach_data_hints(
    result: dict[str, Any],
    environment_report: dict[str, Any],
    *,
    category: str,
) -> dict[str, Any]:
    if result["status"] not in {"empty", "failed"}:
        return result

    directory_checks = environment_report["directory_checks"]
    if category == "minute":
        sh_count = directory_checks["sh_minline_file_count"]
        sz_count = directory_checks["sz_minline_file_count"]
        if sh_count == 0 and sz_count == 0:
            result["hint"] = "本地 minline 目录存在，但当前未发现分钟线文件。"
    if category == "timeline":
        sh_count = directory_checks["sh_fzline_file_count"]
        sz_count = directory_checks["sz_fzline_file_count"]
        if sh_count == 0 and sz_count == 0:
            result["hint"] = "本地 fzline 目录存在，但当前未发现分时线文件。"
    return result


def main() -> int:
    args = _parse_args()
    tdx_dir = Path(args.tdxdir).expanduser()
    provider = MootdxProvider(tdx_dir=tdx_dir)
    registry = ProviderRegistry([provider])
    service = MarketDataService(
        providers=registry,
        local_store=None,
    )

    environment_report = _build_environment_report(tdx_dir)
    capability_report = service.get_provider_capability_reports()
    health_report = service.get_provider_health_reports()
    provider_available = provider.is_available()
    unavailable_reason = provider.get_unavailable_reason()

    daily_result: dict[str, Any]
    minute_result: dict[str, Any]
    timeline_result: dict[str, Any]

    if provider_available:
        daily_result = _build_daily_result(service, args.symbol)
        minute_result = _build_minute_result(
            service,
            args.symbol,
            frequency=args.frequency,
            limit=args.minute_limit,
        )
        timeline_result = _build_timeline_result(
            service,
            args.symbol,
            limit=args.timeline_limit,
        )
        minute_result = _attach_data_hints(
            minute_result,
            environment_report,
            category="minute",
        )
        timeline_result = _attach_data_hints(
            timeline_result,
            environment_report,
            category="timeline",
        )
    else:
        daily_result = {
            "label": "daily",
            "status": "failed",
            "error_type": "ProviderError",
            "error_message": unavailable_reason,
        }
        minute_result = {
            "label": "minute",
            "status": "failed",
            "error_type": "ProviderError",
            "error_message": unavailable_reason,
        }
        timeline_result = {
            "label": "timeline",
            "status": "failed",
            "error_type": "ProviderError",
            "error_message": unavailable_reason,
        }

    overall_status = _determine_overall_status(
        provider_available=provider_available,
        daily_status=daily_result["status"],
        minute_status=minute_result["status"],
        timeline_status=timeline_result["status"],
    )

    summary = _ValidationSummary(
        symbol=args.symbol,
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
        "provider_capability_report": _to_serializable(capability_report),
        "provider_health_report": _to_serializable(health_report),
        "daily_result": daily_result,
        "minute_result": minute_result,
        "timeline_result": timeline_result,
    }

    if unavailable_reason is not None:
        payload["provider_unavailable_reason"] = unavailable_reason

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if overall_status in {"success", "partial_success"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
