"""验证 mootdx provider 的本地行情读取能力。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.provider_registry import ProviderRegistry
from app.services.data_service.providers.mootdx_provider import MootdxProvider


@dataclass(frozen=True)
class _ValidationSummary:
    symbol: str
    tdx_dir: str
    daily_count: int
    minute_count: int
    daily_latest_date: str | None
    minute_latest_datetime: str | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证 mootdx 本地行情 provider。")
    parser.add_argument("--tdxdir", required=True, help="通达信安装目录。")
    parser.add_argument("--symbol", required=True, help="股票代码，如 600519.SH。")
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


def main() -> int:
    args = _parse_args()
    provider = MootdxProvider(tdx_dir=Path(args.tdxdir))
    service = MarketDataService(
        providers=ProviderRegistry([provider]),
        local_store=None,
    )

    try:
        capability_report = service.get_provider_capability_reports()
        health_report = service.get_provider_health_reports()

        daily_response = service.get_daily_bars(args.symbol)
        minute_response = service.get_intraday_bars(
            args.symbol,
            frequency=args.frequency,
            limit=args.minute_limit,
        )

        timeline_payload: dict[str, Any]
        try:
            timeline_response = service.get_timeline(
                args.symbol,
                limit=args.timeline_limit,
            )
            timeline_payload = timeline_response.model_dump()
        except Exception as exc:  # pragma: no cover - 依赖本地环境
            timeline_payload = {
                "status": "failed",
                "reason": str(exc),
            }

        summary = _ValidationSummary(
            symbol=args.symbol,
            tdx_dir=args.tdxdir,
            daily_count=daily_response.count,
            minute_count=minute_response.count,
            daily_latest_date=(
                daily_response.bars[-1].trade_date.isoformat()
                if daily_response.bars
                else None
            ),
            minute_latest_datetime=(
                minute_response.bars[-1].trade_datetime.isoformat()
                if minute_response.bars
                else None
            ),
        )

        payload = {
            "summary": asdict(summary),
            "provider_capability_report": _to_serializable(capability_report),
            "provider_health_report": _to_serializable(health_report),
            "daily_preview": [bar.model_dump() for bar in daily_response.bars[-5:]],
            "minute_preview": [bar.model_dump() for bar in minute_response.bars[-5:]],
            "timeline_preview": timeline_payload,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as exc:  # pragma: no cover - 依赖本地环境
        payload = {
            "status": "failed",
            "symbol": args.symbol,
            "tdx_dir": args.tdxdir,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

