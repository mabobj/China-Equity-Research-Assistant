"""全量初始化脚本：支持断点续传、失败重跑与频率控制。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Literal, Optional

from app.core.config import Settings, get_settings
from app.db.market_data_store import LocalMarketDataStore
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.providers.akshare_provider import AkshareProvider
from app.services.data_service.providers.baostock_provider import BaostockProvider
from app.services.data_service.providers.cninfo_provider import CninfoProvider

logger = logging.getLogger("full_data_init")

StepName = Literal["profile", "daily_bars", "financial_summary", "announcements"]
STEP_SEQUENCE: tuple[StepName, ...] = (
    "profile",
    "daily_bars",
    "financial_summary",
    "announcements",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="执行一次A股全量数据初始化，支持断点续传与失败重跑。",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="重置历史进度并从头开始。",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="仅用于调试的最大股票数量限制，默认不限制。",
    )
    parser.add_argument(
        "--symbol-sleep-ms",
        type=int,
        default=None,
        help="每只股票之间的暂停毫秒数，默认使用 DATA_REFRESH_SYMBOL_SLEEP_MS。",
    )
    parser.add_argument(
        "--daily-step-sleep-ms",
        type=int,
        default=200,
        help="日线步骤前的额外暂停毫秒数，默认 200。",
    )
    parser.add_argument(
        "--enable-baostock",
        action="store_true",
        help="是否启用 baostock 作为补充 provider。默认关闭以提升全量稳定性。",
    )
    parser.add_argument(
        "--slow-step-warning-seconds",
        type=float,
        default=20.0,
        help="步骤耗时超过该阈值时输出慢步骤告警日志。",
    )
    parser.add_argument(
        "--progress-log-interval",
        type=int,
        default=50,
        help="每处理多少只股票输出一次进度日志。",
    )
    parser.add_argument(
        "--state-path",
        type=str,
        default=None,
        help="断点状态文件路径，默认 data/bootstrap/full_init_state.json。",
    )
    parser.add_argument(
        "--error-log-path",
        type=str,
        default=None,
        help="异常日志JSONL路径，默认 data/bootstrap/full_init_errors.jsonl。",
    )
    return parser.parse_args()


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def _build_market_data_service(
    settings: Settings,
    enable_baostock: bool,
) -> MarketDataService:
    providers: list[object] = []
    if settings.enable_akshare:
        providers.append(
            AkshareProvider(
                daily_bars_max_retries=settings.akshare_daily_retry_max_attempts,
                daily_bars_retry_backoff_seconds=settings.akshare_daily_retry_backoff_seconds,
                daily_bars_retry_jitter_seconds=settings.akshare_daily_retry_jitter_seconds,
            )
        )
    if settings.enable_baostock and enable_baostock:
        providers.append(BaostockProvider())
    if settings.enable_cninfo:
        providers.append(CninfoProvider())

    local_store = LocalMarketDataStore(settings.duckdb_path)
    return MarketDataService(
        providers=providers,
        local_store=local_store,
    )


def _default_state(universe_symbols: list[str]) -> dict[str, Any]:
    return {
        "version": 1,
        "phase": "first_pass",
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
        "completed_at": None,
        "current_symbol": None,
        "current_step": None,
        "universe_symbols": universe_symbols,
        "next_index": 0,
        "first_pass_failures": [],
        "retry_targets": [],
        "retry_next_index": 0,
        "retry_failures": [],
        "stats": {
            "processed_symbols": 0,
            "step_success": {step: 0 for step in STEP_SEQUENCE},
            "step_failures": {step: 0 for step in STEP_SEQUENCE},
            "retry_step_success": {step: 0 for step in STEP_SEQUENCE},
            "retry_step_failures": {step: 0 for step in STEP_SEQUENCE},
        },
    }


def _load_state(state_path: Path) -> Optional[dict[str, Any]]:
    if not state_path.exists():
        return None
    with state_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _now_iso()
    _write_json_atomic(state_path, state)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def _append_error_log(error_log_path: Path, record: dict[str, Any]) -> None:
    error_log_path.parent.mkdir(parents=True, exist_ok=True)
    with error_log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False))
        file.write("\n")


def _build_error_record(
    *,
    symbol: str,
    step: StepName,
    phase: str,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "timestamp": _now_iso(),
        "phase": phase,
        "symbol": symbol,
        "step": step,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "error_chain": _format_error_chain(exc),
    }


def _format_error_chain(exc: Exception) -> str:
    chain: list[str] = []
    current: Optional[BaseException] = exc
    while current is not None:
        chain.append(
            "{error_type}: {message}".format(
                error_type=type(current).__name__,
                message=str(current),
            )
        )
        current = current.__cause__ or current.__context__
    return " <- ".join(chain)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_universe_symbols(
    market_data_service: MarketDataService,
    max_symbols: Optional[int],
) -> list[str]:
    universe = market_data_service.refresh_stock_universe()
    symbols = [item.symbol for item in universe.items]
    if max_symbols is not None and max_symbols > 0:
        return symbols[:max_symbols]
    return symbols


def _run_one_step(
    market_data_service: MarketDataService,
    settings: Settings,
    symbol: str,
    step: StepName,
) -> None:
    if step == "profile":
        market_data_service.refresh_stock_profile(symbol)
        return
    if step == "daily_bars":
        market_data_service.refresh_daily_bars(
            symbol,
            lookback_days=settings.data_refresh_daily_bar_lookback_days,
        )
        return
    if step == "financial_summary":
        market_data_service.refresh_stock_financial_summary(symbol)
        return
    if step == "announcements":
        market_data_service.refresh_stock_announcements(
            symbol,
            lookback_days=settings.data_refresh_announcement_lookback_days,
            limit=settings.data_refresh_announcement_limit,
        )
        return
    raise ValueError("Unsupported step: {step}".format(step=step))


def _run_step_with_logging(
    *,
    market_data_service: MarketDataService,
    settings: Settings,
    symbol: str,
    step: StepName,
    phase: str,
    slow_step_warning_seconds: float,
) -> None:
    logger.info("%s 步骤开始 %s [%s]", phase, symbol, step)
    started_at = time.perf_counter()
    _run_one_step(market_data_service, settings, symbol, step)
    elapsed_seconds = time.perf_counter() - started_at
    logger.info(
        "%s 步骤完成 %s [%s]，耗时 %.2f 秒",
        phase,
        symbol,
        step,
        elapsed_seconds,
    )
    if elapsed_seconds >= slow_step_warning_seconds:
        logger.warning(
            "%s 慢步骤告警 %s [%s]，耗时 %.2f 秒",
            phase,
            symbol,
            step,
            elapsed_seconds,
        )


def _contains_failure(
    failures: list[dict[str, str]],
    symbol: str,
    step: str,
) -> bool:
    return any(item["symbol"] == symbol and item["step"] == step for item in failures)


def _parse_step_name(value: str) -> StepName:
    if value not in STEP_SEQUENCE:
        raise ValueError("Unsupported step name in state: {value}".format(value=value))
    return value


def _run_first_pass(
    *,
    market_data_service: MarketDataService,
    settings: Settings,
    state: dict[str, Any],
    state_path: Path,
    error_log_path: Path,
    symbol_sleep_seconds: float,
    daily_step_sleep_seconds: float,
    progress_log_interval: int,
    slow_step_warning_seconds: float,
) -> None:
    symbols: list[str] = state["universe_symbols"]
    start_index = int(state.get("next_index", 0))
    failures: list[dict[str, str]] = list(state.get("first_pass_failures", []))
    stats: dict[str, Any] = state["stats"]

    total = len(symbols)
    logger.info("第一轮全量初始化开始：起始位置=%s，总股票数=%s", start_index, total)

    with market_data_service.session_scope():
        for index in range(start_index, total):
            symbol = symbols[index]
            logger.info("第一轮进度 %s/%s，当前股票=%s", index + 1, total, symbol)

            for step in STEP_SEQUENCE:
                state["current_symbol"] = symbol
                state["current_step"] = step
                _save_state(state_path, state)
                if step == "daily_bars" and daily_step_sleep_seconds > 0:
                    time.sleep(daily_step_sleep_seconds)
                try:
                    _run_step_with_logging(
                        market_data_service=market_data_service,
                        settings=settings,
                        symbol=symbol,
                        step=step,
                        phase="第一轮",
                        slow_step_warning_seconds=slow_step_warning_seconds,
                    )
                    stats["step_success"][step] += 1
                except Exception as exc:  # pragma: no cover - 依赖外部网络
                    stats["step_failures"][step] += 1
                    if not _contains_failure(failures, symbol, step):
                        failures.append({"symbol": symbol, "step": step})
                    error_record = _build_error_record(
                        symbol=symbol,
                        step=step,
                        phase="first_pass",
                        exc=exc,
                    )
                    _append_error_log(error_log_path, error_record)
                    logger.warning(
                        "第一轮失败 %s [%s]: %s",
                        symbol,
                        step,
                        error_record["error_chain"],
                    )

            stats["processed_symbols"] = index + 1
            state["next_index"] = index + 1
            state["first_pass_failures"] = failures
            state["current_symbol"] = None
            state["current_step"] = None
            state["stats"] = stats
            _save_state(state_path, state)

            if (index + 1) % progress_log_interval == 0 or (index + 1) == total:
                logger.info(
                    (
                        "第一轮阶段性完成：processed=%s/%s, failure_steps=%s, "
                        "profile_fail=%s, daily_fail=%s, financial_fail=%s, announcement_fail=%s"
                    ),
                    index + 1,
                    total,
                    len(failures),
                    stats["step_failures"]["profile"],
                    stats["step_failures"]["daily_bars"],
                    stats["step_failures"]["financial_summary"],
                    stats["step_failures"]["announcements"],
                )

            if symbol_sleep_seconds > 0:
                time.sleep(symbol_sleep_seconds)

    logger.info("第一轮完成：失败步骤总数=%s", len(failures))


def _run_retry_pass(
    *,
    market_data_service: MarketDataService,
    settings: Settings,
    state: dict[str, Any],
    state_path: Path,
    error_log_path: Path,
    symbol_sleep_seconds: float,
    daily_step_sleep_seconds: float,
    progress_log_interval: int,
    slow_step_warning_seconds: float,
) -> None:
    retry_targets: list[dict[str, str]] = list(state.get("retry_targets", []))
    retry_index = int(state.get("retry_next_index", 0))
    retry_failures: list[dict[str, str]] = list(state.get("retry_failures", []))
    stats: dict[str, Any] = state["stats"]
    total = len(retry_targets)

    if total == 0:
        logger.info("第一轮无失败步骤，跳过重跑。")
        return

    logger.info("第二轮失败重跑开始：起始位置=%s，总失败步骤=%s", retry_index, total)

    with market_data_service.session_scope():
        for index in range(retry_index, total):
            target = retry_targets[index]
            symbol = target["symbol"]
            step = _parse_step_name(target["step"])
            logger.info("第二轮进度 %s/%s，重跑 %s [%s]", index + 1, total, symbol, step)
            state["current_symbol"] = symbol
            state["current_step"] = step
            _save_state(state_path, state)

            if step == "daily_bars" and daily_step_sleep_seconds > 0:
                time.sleep(daily_step_sleep_seconds)

            try:
                _run_step_with_logging(
                    market_data_service=market_data_service,
                    settings=settings,
                    symbol=symbol,
                    step=step,
                    phase="第二轮",
                    slow_step_warning_seconds=slow_step_warning_seconds,
                )
                stats["retry_step_success"][step] += 1
            except Exception as exc:  # pragma: no cover - 依赖外部网络
                stats["retry_step_failures"][step] += 1
                if not _contains_failure(retry_failures, symbol, step):
                    retry_failures.append({"symbol": symbol, "step": step})
                error_record = _build_error_record(
                    symbol=symbol,
                    step=step,
                    phase="retry_pass",
                    exc=exc,
                )
                _append_error_log(error_log_path, error_record)
                logger.warning(
                    "第二轮仍失败 %s [%s]: %s",
                    symbol,
                    step,
                    error_record["error_chain"],
                )

            state["retry_next_index"] = index + 1
            state["retry_failures"] = retry_failures
            state["current_symbol"] = None
            state["current_step"] = None
            state["stats"] = stats
            _save_state(state_path, state)

            if (index + 1) % progress_log_interval == 0 or (index + 1) == total:
                logger.info(
                    "第二轮阶段性完成：processed=%s/%s, remaining=%s",
                    index + 1,
                    total,
                    len(retry_failures),
                )

            if symbol_sleep_seconds > 0:
                time.sleep(symbol_sleep_seconds)

    logger.info("第二轮完成：剩余失败步骤=%s", len(retry_failures))


def _safe_unlink(path: Path) -> None:
    if path.exists():
        path.unlink()


def main() -> int:
    args = _parse_args()
    _configure_logging()
    settings = get_settings()

    symbol_sleep_ms = (
        settings.data_refresh_symbol_sleep_ms
        if args.symbol_sleep_ms is None
        else max(0, args.symbol_sleep_ms)
    )
    symbol_sleep_seconds = max(0.0, symbol_sleep_ms / 1000.0)
    daily_step_sleep_seconds = max(0.0, max(0, args.daily_step_sleep_ms) / 1000.0)
    progress_log_interval = max(1, args.progress_log_interval)
    slow_step_warning_seconds = max(0.1, args.slow_step_warning_seconds)

    state_path = (
        Path(args.state_path)
        if args.state_path
        else settings.data_dir / "bootstrap" / "full_init_state.json"
    )
    error_log_path = (
        Path(args.error_log_path)
        if args.error_log_path
        else settings.data_dir / "bootstrap" / "full_init_errors.jsonl"
    )

    if args.reset:
        _safe_unlink(state_path)
        _safe_unlink(error_log_path)
        logger.info("已重置断点状态和错误日志。")

    market_data_service = _build_market_data_service(
        settings=settings,
        enable_baostock=args.enable_baostock,
    )
    logger.info(
        "脚本启动参数：enable_baostock=%s, symbol_sleep_ms=%s, daily_step_sleep_ms=%s, slow_step_warning_seconds=%.1f",
        args.enable_baostock,
        symbol_sleep_ms,
        max(0, args.daily_step_sleep_ms),
        slow_step_warning_seconds,
    )

    state = _load_state(state_path)
    if state is None:
        universe_symbols = _collect_universe_symbols(
            market_data_service=market_data_service,
            max_symbols=args.max_symbols,
        )
        state = _default_state(universe_symbols)
        _save_state(state_path, state)
        logger.info("已创建新任务状态，股票总数=%s", len(universe_symbols))
    elif state.get("phase") == "completed":
        logger.info("检测到历史任务已完成。如需重跑请加 --reset。")
        return 0

    try:
        if state["phase"] == "first_pass":
            _run_first_pass(
                market_data_service=market_data_service,
                settings=settings,
                state=state,
                state_path=state_path,
                error_log_path=error_log_path,
                symbol_sleep_seconds=symbol_sleep_seconds,
                daily_step_sleep_seconds=daily_step_sleep_seconds,
                progress_log_interval=progress_log_interval,
                slow_step_warning_seconds=slow_step_warning_seconds,
            )
            state["phase"] = "retry_pass"
            state["retry_targets"] = list(state.get("first_pass_failures", []))
            state["retry_next_index"] = 0
            _save_state(state_path, state)

        if state["phase"] == "retry_pass":
            _run_retry_pass(
                market_data_service=market_data_service,
                settings=settings,
                state=state,
                state_path=state_path,
                error_log_path=error_log_path,
                symbol_sleep_seconds=symbol_sleep_seconds,
                daily_step_sleep_seconds=daily_step_sleep_seconds,
                progress_log_interval=progress_log_interval,
                slow_step_warning_seconds=slow_step_warning_seconds,
            )
            state["phase"] = "completed"
            state["completed_at"] = _now_iso()
            _save_state(state_path, state)

        logger.info(
            "初始化结束：第一轮失败步骤=%s，第二轮剩余失败步骤=%s，状态文件=%s，错误日志=%s",
            len(state.get("first_pass_failures", [])),
            len(state.get("retry_failures", [])),
            str(state_path),
            str(error_log_path),
        )
        return 0
    except KeyboardInterrupt:
        logger.warning("收到中断信号，当前进度已写入状态文件，可下次继续。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
