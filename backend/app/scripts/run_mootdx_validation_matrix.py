"""批量运行 mootdx 本地行情验证矩阵。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
import json
from math import isclose
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.config import get_settings
from app.scripts.mootdx_validation_support import (
    attach_data_hints,
    build_environment_report,
    create_mootdx_service,
    to_serializable,
)
from app.services.data_service.exceptions import DataNotFoundError, ProviderError
from app.services.data_service.providers.akshare_provider import AkshareProvider
from app.services.data_service.providers.baostock_provider import BaostockProvider


@dataclass(frozen=True)
class ValidationMatrixRow:
    symbol: str
    capability: str
    status: str
    source: str
    count: int
    latest_timestamp: str | None
    error_type: str | None
    error_message: str | None
    comparison_summary: dict[str, Any] | None = None
    frequency: str | None = None


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 mootdx 本地行情批量验证矩阵。")
    parser.add_argument("--tdxdir", required=True, help="通达信安装目录。")
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="股票代码列表，支持空格分隔或逗号分隔。",
    )
    parser.add_argument(
        "--frequencies",
        nargs="+",
        default=["1m", "5m"],
        help="分钟线频率列表，默认 1m 5m。",
    )
    parser.add_argument(
        "--compare-provider",
        choices=["akshare", "baostock"],
        default=None,
        help="可选的日线对比 provider。",
    )
    parser.add_argument("--output-json", default=None, help="JSON 输出文件路径。")
    parser.add_argument("--output-csv", default=None, help="CSV 输出文件路径。")
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
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    tdx_dir = Path(args.tdxdir).expanduser()
    symbols = _parse_multi_values(args.symbols)
    frequencies = _normalize_frequencies(_parse_multi_values(args.frequencies))

    provider, service = create_mootdx_service(tdx_dir)
    environment_report = build_environment_report(tdx_dir)
    capability_report = to_serializable(service.get_provider_capability_reports())
    health_report = to_serializable(service.get_provider_health_reports())

    compare_provider = _build_compare_provider(args.compare_provider)
    results: list[dict[str, Any]] = []
    rows: list[ValidationMatrixRow] = [
        _build_capability_row(capability_report, provider.name),
        _build_health_row(health_report, provider.name),
    ]

    with _provider_session_scope(compare_provider):
        for symbol in symbols:
            symbol_result = _run_symbol_matrix(
                service=service,
                symbol=symbol,
                frequencies=frequencies,
                minute_limit=args.minute_limit,
                timeline_limit=args.timeline_limit,
                environment_report=environment_report,
                compare_provider=compare_provider,
            )
            results.append(symbol_result)
            rows.extend(symbol_result["rows"])

    payload = {
        "status": _summarize_matrix_status(rows),
        "tdx_dir": str(tdx_dir),
        "symbols": symbols,
        "frequencies": frequencies,
        "compare_provider": args.compare_provider,
        "environment_report": environment_report,
        "provider_capability_report": capability_report,
        "provider_health_report": health_report,
        "results": [
            _strip_internal_symbol_result(item)
            for item in results
        ],
        "rows": [to_serializable(row.__dict__) for row in rows],
    }

    serialized_payload = json.dumps(
        to_serializable(payload),
        ensure_ascii=False,
        indent=2,
    )
    print(serialized_payload)

    if args.output_json:
        output_json = Path(args.output_json).expanduser()
        output_json.write_text(serialized_payload, encoding="utf-8")
    if args.output_csv:
        _write_csv(Path(args.output_csv).expanduser(), rows)

    return 0 if payload["status"] != "failed" else 1


def _run_symbol_matrix(
    *,
    service,
    symbol: str,
    frequencies: list[str],
    minute_limit: int,
    timeline_limit: int,
    environment_report: dict[str, Any],
    compare_provider: object | None,
) -> dict[str, Any]:
    symbol_payload: dict[str, Any] = {
        "symbol": symbol,
        "daily": None,
        "intraday": [],
        "timeline": None,
        "rows": [],
    }

    daily_result = _execute_daily_check(service, symbol)
    comparison_summary = _compare_daily_if_requested(
        symbol=symbol,
        daily_result=daily_result,
        compare_provider=compare_provider,
    )
    symbol_payload["daily"] = _strip_full_bars(daily_result)
    symbol_payload["rows"].append(
        ValidationMatrixRow(
            symbol=symbol,
            capability="daily_bars",
            status=daily_result["status"],
            source="mootdx",
            count=int(daily_result.get("count", 0) or 0),
            latest_timestamp=daily_result.get("latest_date"),
            error_type=daily_result.get("error_type"),
            error_message=daily_result.get("error_message"),
            comparison_summary=comparison_summary,
        ),
    )

    for frequency in frequencies:
        intraday_result = _execute_intraday_check(
            service=service,
            symbol=symbol,
            frequency=frequency,
            limit=minute_limit,
        )
        intraday_result = attach_data_hints(
            intraday_result,
            environment_report,
            category="minute",
        )
        symbol_payload["intraday"].append(intraday_result)
        symbol_payload["rows"].append(
            ValidationMatrixRow(
                symbol=symbol,
                capability="intraday_bars",
                status=intraday_result["status"],
                source="mootdx",
                count=int(intraday_result.get("count", 0) or 0),
                latest_timestamp=intraday_result.get("latest_datetime"),
                error_type=intraday_result.get("error_type"),
                error_message=intraday_result.get("error_message"),
                comparison_summary=None,
                frequency=frequency,
            ),
        )

    timeline_result = _execute_timeline_check(
        service=service,
        symbol=symbol,
        limit=timeline_limit,
    )
    timeline_result = attach_data_hints(
        timeline_result,
        environment_report,
        category="timeline",
    )
    symbol_payload["timeline"] = timeline_result
    symbol_payload["rows"].append(
        ValidationMatrixRow(
            symbol=symbol,
            capability="timeline",
            status=timeline_result["status"],
            source="mootdx",
            count=int(timeline_result.get("count", 0) or 0),
            latest_timestamp=timeline_result.get("latest_time"),
            error_type=timeline_result.get("error_type"),
            error_message=timeline_result.get("error_message"),
            comparison_summary=None,
        ),
    )

    return symbol_payload


def _execute_daily_check(service, symbol: str) -> dict[str, Any]:
    try:
        response = service.get_daily_bars(symbol)
    except DataNotFoundError as exc:
        return _error_result("daily_bars", exc, empty=True)
    except Exception as exc:  # pragma: no cover - 依赖本地环境
        return _error_result("daily_bars", exc)

    return {
        "label": "daily_bars",
        "status": "success" if response.count > 0 else "empty",
        "count": response.count,
        "latest_date": response.bars[-1].trade_date.isoformat() if response.bars else None,
        "preview": [bar.model_dump() for bar in response.bars[-5:]],
        "full_bars": response.bars,
    }


def _execute_intraday_check(service, symbol: str, *, frequency: str, limit: int) -> dict[str, Any]:
    try:
        response = service.get_intraday_bars(symbol, frequency=frequency, limit=limit)
    except DataNotFoundError as exc:
        return _error_result("intraday_bars", exc, empty=True, frequency=frequency)
    except Exception as exc:  # pragma: no cover - 依赖本地环境
        return _error_result("intraday_bars", exc, frequency=frequency)

    return {
        "label": "intraday_bars",
        "status": "success" if response.count > 0 else "empty",
        "frequency": frequency,
        "count": response.count,
        "latest_datetime": (
            response.bars[-1].trade_datetime.isoformat() if response.bars else None
        ),
        "preview": [bar.model_dump() for bar in response.bars[-5:]],
    }


def _execute_timeline_check(service, symbol: str, *, limit: int) -> dict[str, Any]:
    try:
        response = service.get_timeline(symbol, limit=limit)
    except DataNotFoundError as exc:
        return _error_result("timeline", exc, empty=True)
    except Exception as exc:  # pragma: no cover - 依赖本地环境
        return _error_result("timeline", exc)

    return {
        "label": "timeline",
        "status": "success" if response.count > 0 else "empty",
        "count": response.count,
        "latest_time": response.points[-1].trade_time.isoformat() if response.points else None,
        "preview": [point.model_dump() for point in response.points[-5:]],
    }


def _error_result(
    label: str,
    exc: Exception,
    *,
    empty: bool = False,
    frequency: str | None = None,
) -> dict[str, Any]:
    payload = {
        "label": label,
        "status": "empty" if empty else "failed",
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    if frequency is not None:
        payload["frequency"] = frequency
    return payload


def _compare_daily_if_requested(
    *,
    symbol: str,
    daily_result: dict[str, Any],
    compare_provider: object | None,
) -> dict[str, Any] | None:
    if compare_provider is None:
        return None
    is_available = getattr(compare_provider, "is_available", None)
    if callable(is_available) and not is_available():
        unavailable_reason_getter = getattr(compare_provider, "get_unavailable_reason", None)
        unavailable_reason = (
            unavailable_reason_getter()
            if callable(unavailable_reason_getter)
            else "compare provider is unavailable."
        )
        return {
            "provider": getattr(compare_provider, "name", "unknown"),
            "status": "unavailable",
            "reference_count": int(daily_result.get("count", 0) or 0),
            "compared_count": 0,
            "mismatch_count": 0,
            "mismatch_note": unavailable_reason,
        }
    if daily_result["status"] != "success":
        return {
            "provider": getattr(compare_provider, "name", "unknown"),
            "status": "skipped",
            "reference_count": int(daily_result.get("count", 0) or 0),
            "compared_count": 0,
            "mismatch_count": 0,
            "mismatch_note": "mootdx daily validation did not succeed, comparison skipped.",
        }

    reference_bars = daily_result["full_bars"][-20:]
    if not reference_bars:
        return {
            "provider": getattr(compare_provider, "name", "unknown"),
            "status": "empty",
            "reference_count": 0,
            "compared_count": 0,
            "mismatch_count": 0,
            "mismatch_note": "No local daily bars were available for comparison.",
        }

    start_date = reference_bars[0].trade_date
    end_date = reference_bars[-1].trade_date
    try:
        compare_bars = compare_provider.get_daily_bars(
            symbol,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:  # pragma: no cover - runtime/network dependent
        return {
            "provider": getattr(compare_provider, "name", "unknown"),
            "status": "failed",
            "reference_count": len(reference_bars),
            "compared_count": 0,
            "mismatch_count": len(reference_bars),
            "mismatch_note": "{error_type}: {message}".format(
                error_type=type(exc).__name__,
                message=str(exc),
            ),
        }

    return _summarize_daily_comparison(
        reference_bars=reference_bars,
        compare_bars=compare_bars,
        provider_name=getattr(compare_provider, "name", "unknown"),
    )


def _summarize_daily_comparison(
    *,
    reference_bars: list,
    compare_bars: list,
    provider_name: str,
) -> dict[str, Any]:
    reference_map = {bar.trade_date: bar for bar in reference_bars}
    compare_map = {bar.trade_date: bar for bar in compare_bars}
    all_dates = sorted(set(reference_map) | set(compare_map))

    mismatch_count = 0
    mismatch_notes: list[str] = []
    compared_count = 0

    for trade_date in all_dates:
        left_bar = reference_map.get(trade_date)
        right_bar = compare_map.get(trade_date)
        if left_bar is None or right_bar is None:
            mismatch_count += 1
            mismatch_notes.append(
                "{trade_date}: missing_on_{side}".format(
                    trade_date=trade_date.isoformat(),
                    side="mootdx" if left_bar is None else provider_name,
                ),
            )
            continue

        compared_count += 1
        row_mismatches = _compare_bar_fields(left_bar, right_bar)
        if row_mismatches:
            mismatch_count += len(row_mismatches)
            mismatch_notes.append(
                "{trade_date}: {fields}".format(
                    trade_date=trade_date.isoformat(),
                    fields=",".join(row_mismatches),
                ),
            )

    status = "matched" if mismatch_count == 0 else "mismatched"
    mismatch_note = "no mismatch" if not mismatch_notes else "; ".join(mismatch_notes[:5])
    return {
        "provider": provider_name,
        "status": status,
        "reference_count": len(reference_bars),
        "compared_count": compared_count,
        "mismatch_count": mismatch_count,
        "mismatch_note": mismatch_note,
    }


def _compare_bar_fields(left_bar, right_bar) -> list[str]:
    mismatches: list[str] = []
    if not _float_close(left_bar.open, right_bar.open, abs_tol=0.02):
        mismatches.append("open")
    if not _float_close(left_bar.high, right_bar.high, abs_tol=0.02):
        mismatches.append("high")
    if not _float_close(left_bar.low, right_bar.low, abs_tol=0.02):
        mismatches.append("low")
    if not _float_close(left_bar.close, right_bar.close, abs_tol=0.02):
        mismatches.append("close")
    if not _float_close(left_bar.volume, right_bar.volume, rel_tol=0.002, abs_tol=10.0):
        mismatches.append("volume")
    if not _float_close(left_bar.amount, right_bar.amount, rel_tol=0.002, abs_tol=1000.0):
        mismatches.append("amount")
    return mismatches


def _float_close(
    left: float | None,
    right: float | None,
    *,
    rel_tol: float = 1e-4,
    abs_tol: float = 1e-4,
) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def _build_compare_provider(compare_provider_name: str | None) -> object | None:
    if compare_provider_name is None:
        return None
    settings = get_settings()
    if compare_provider_name == "akshare":
        return AkshareProvider(
            daily_bars_max_retries=settings.akshare_daily_retry_max_attempts,
            daily_bars_retry_backoff_seconds=settings.akshare_daily_retry_backoff_seconds,
            daily_bars_retry_jitter_seconds=settings.akshare_daily_retry_jitter_seconds,
        )
    if compare_provider_name == "baostock":
        return BaostockProvider()
    raise ProviderError(
        "Unsupported compare provider: {provider}".format(
            provider=compare_provider_name,
        ),
    )


def _provider_session_scope(provider: object | None):
    if provider is None:
        from contextlib import nullcontext

        return nullcontext()

    is_available = getattr(provider, "is_available", None)
    if callable(is_available) and not is_available():
        from contextlib import nullcontext

        return nullcontext()

    session_scope = getattr(provider, "session_scope", None)
    if callable(session_scope):
        return session_scope()

    from contextlib import nullcontext

    return nullcontext()


def _build_capability_row(
    capability_report: list[dict[str, Any]],
    source: str,
) -> ValidationMatrixRow:
    capabilities = capability_report[0]["capabilities"] if capability_report else []
    return ValidationMatrixRow(
        symbol="*",
        capability="provider_capability_report",
        status="success",
        source=source,
        count=len(capabilities),
        latest_timestamp=None,
        error_type=None,
        error_message=None,
        comparison_summary={"capabilities": capabilities},
    )


def _build_health_row(
    health_report: list[dict[str, Any]],
    source: str,
) -> ValidationMatrixRow:
    first_report = health_report[0] if health_report else {}
    available = bool(first_report.get("available"))
    return ValidationMatrixRow(
        symbol="*",
        capability="provider_health_report",
        status="success" if available else "failed",
        source=source,
        count=1,
        latest_timestamp=None,
        error_type=None if available else "ProviderError",
        error_message=first_report.get("unavailable_reason"),
        comparison_summary=None,
    )


def _write_csv(path: Path, rows: list[ValidationMatrixRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "symbol",
                "capability",
                "status",
                "source",
                "count",
                "latest_timestamp",
                "error_type",
                "error_message",
                "comparison_summary",
                "frequency",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row.__dict__,
                    "comparison_summary": (
                        json.dumps(
                            to_serializable(row.comparison_summary),
                            ensure_ascii=False,
                        )
                        if row.comparison_summary is not None
                        else ""
                    ),
                },
            )


def _parse_multi_values(values: Iterable[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned:
                items.append(cleaned)
    return items


def _normalize_frequencies(frequencies: list[str]) -> list[str]:
    normalized: list[str] = []
    for frequency in frequencies:
        cleaned = frequency.strip().lower()
        if cleaned not in {"1m", "5m"}:
            raise ProviderError(
                "Unsupported frequency '{frequency}'. Supported values: 1m, 5m.".format(
                    frequency=frequency,
                ),
            )
        if cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _strip_full_bars(daily_result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(daily_result)
    payload.pop("full_bars", None)
    return payload


def _strip_internal_symbol_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": result["symbol"],
        "daily": result["daily"],
        "intraday": result["intraday"],
        "timeline": result["timeline"],
    }


def _summarize_matrix_status(rows: list[ValidationMatrixRow]) -> str:
    data_rows = [row for row in rows if row.symbol != "*"]
    if not data_rows:
        return "failed"
    if all(row.status == "success" for row in data_rows):
        return "success"
    if any(row.status == "success" for row in data_rows):
        return "partial_success"
    return "failed"


if __name__ == "__main__":
    raise SystemExit(main())
