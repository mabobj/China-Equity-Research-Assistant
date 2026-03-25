"""验证单个 symbol 的 mootdx 本地行情读取能力。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.scripts.mootdx_validation_support import run_mootdx_symbol_validation, to_serializable


def build_argument_parser() -> argparse.ArgumentParser:
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
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    payload = run_mootdx_symbol_validation(
        tdx_dir=Path(args.tdxdir).expanduser(),
        symbol=args.symbol,
        frequency=args.frequency,
        minute_limit=args.minute_limit,
        timeline_limit=args.timeline_limit,
    )

    daily_result = dict(payload["daily_result"])
    daily_result.pop("full_bars", None)
    payload["daily_result"] = daily_result

    print(json.dumps(to_serializable(payload), ensure_ascii=False, indent=2))
    return 0 if payload["status"] in {"success", "partial_success"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
