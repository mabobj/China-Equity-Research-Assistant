"""手动数据补全服务。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from threading import Lock, Thread
import time
from typing import Callable, Optional

from app.schemas.data_refresh import DataRefreshStatus
from app.services.data_service.market_data_service import MarketDataService

logger = logging.getLogger(__name__)

_MAX_RECENT_MESSAGES = 200
_REFRESH_CURSOR_KEY = "manual_data_refresh_universe_cursor"


@dataclass
class _RefreshState:
    """后台数据补全任务的内部状态。"""

    status: str = "idle"
    is_running: bool = False
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    universe_count: int = 0
    total_symbols: int = 0
    processed_symbols: int = 0
    succeeded_symbols: int = 0
    failed_symbols: int = 0
    profiles_updated: int = 0
    daily_bars_updated: int = 0
    financial_summaries_updated: int = 0
    announcements_updated: int = 0
    daily_bars_synced_rows: int = 0
    announcements_synced_items: int = 0
    profile_step_failures: int = 0
    daily_bar_step_failures: int = 0
    financial_step_failures: int = 0
    announcement_step_failures: int = 0
    universe_updated: bool = False
    max_symbols: Optional[int] = None
    current_symbol: Optional[str] = None
    current_stage: Optional[str] = None
    message: str = "尚未执行数据补全。"
    recent_warnings: list[str] = field(default_factory=list)
    recent_errors: list[str] = field(default_factory=list)


class DataRefreshService:
    """负责触发和跟踪手动数据补全任务。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        daily_bar_lookback_days: int,
        announcement_lookback_days: int,
        announcement_limit: int,
        progress_log_interval: int,
        symbol_sleep_ms: int = 0,
        task_runner: Optional[Callable[[Callable[[], None]], None]] = None,
    ) -> None:
        self._market_data_service = market_data_service
        self._daily_bar_lookback_days = daily_bar_lookback_days
        self._announcement_lookback_days = announcement_lookback_days
        self._announcement_limit = announcement_limit
        self._progress_log_interval = max(1, progress_log_interval)
        self._symbol_sleep_seconds = max(0.0, symbol_sleep_ms / 1000.0)
        self._task_runner = task_runner or self._run_in_background
        self._lock = Lock()
        self._state = _RefreshState()

    def start_manual_refresh(self, max_symbols: Optional[int] = None) -> DataRefreshStatus:
        """启动一次手动数据补全任务。"""
        with self._lock:
            if self._state.is_running:
                return self._build_status()

            self._state = _RefreshState(
                status="running",
                is_running=True,
                started_at=datetime.utcnow(),
                max_symbols=max_symbols,
                message="数据补全任务已启动，正在刷新股票池。",
                current_stage="refresh_universe",
            )

        self._task_runner(lambda: self._run_refresh(max_symbols))
        return self.get_status()

    def get_status(self) -> DataRefreshStatus:
        """读取当前数据补全任务状态。"""
        with self._lock:
            return self._build_status()

    def _run_in_background(self, callback: Callable[[], None]) -> None:
        """将补全任务放到后台线程执行。"""
        thread = Thread(target=callback, daemon=True, name="data-refresh-worker")
        thread.start()

    def _run_refresh(self, max_symbols: Optional[int]) -> None:
        """执行完整的数据补全流程。"""
        logger.info("开始执行手动数据补全，max_symbols=%s", max_symbols)
        last_processed_symbol: Optional[str] = None

        try:
            universe_response = self._market_data_service.refresh_stock_universe()
            universe_items = universe_response.items
            selected_items = self._select_symbols_for_run(universe_items, max_symbols)
            total_symbols = len(selected_items)

            self._update_state(
                universe_count=universe_response.count,
                total_symbols=total_symbols,
                universe_updated=True,
                message="股票池已刷新，开始补全个股数据。",
                current_stage="refresh_symbols",
            )

            if total_symbols == 0:
                self._complete_refresh(
                    status="completed",
                    message="股票池为空，本次无需补全个股数据。",
                )
                return

            with self._market_data_service.session_scope():
                for index, item in enumerate(selected_items, start=1):
                    last_processed_symbol = item.symbol
                    self._update_state(
                        current_symbol=item.symbol,
                        current_stage="refresh_symbol",
                        message=(
                            "正在补全 {current}/{total}: {symbol}".format(
                                current=index,
                                total=total_symbols,
                                symbol=item.symbol,
                            )
                        ),
                    )
                    logger.info(
                        "数据补全进度 %s/%s，当前股票 %s",
                        index,
                        total_symbols,
                        item.symbol,
                    )

                    symbol_success = self._refresh_one_symbol(item.symbol)
                    if symbol_success:
                        self._increment_success()
                    else:
                        failure_message = "{symbol}: 所有核心数据域均补全失败。".format(
                            symbol=item.symbol,
                        )
                        logger.warning("股票数据补全失败 %s", failure_message)
                        self._increment_failure(failure_message)

                    self._increment_processed()
                    if self._symbol_sleep_seconds > 0:
                        time.sleep(self._symbol_sleep_seconds)
                    if index % self._progress_log_interval == 0 or index == total_symbols:
                        status = self.get_status()
                        logger.info(
                            (
                                "数据补全阶段完成：processed=%s/%s, success=%s, failed=%s, "
                                "daily_rows=%s, announcement_items=%s"
                            ),
                            status.processed_symbols,
                            status.total_symbols,
                            status.succeeded_symbols,
                            status.failed_symbols,
                            status.daily_bars_synced_rows,
                            status.announcements_synced_items,
                        )

            self._save_refresh_cursor(last_processed_symbol)
            status = self.get_status()
            completion_message = (
                "数据补全完成，共处理 {processed} 只股票，成功 {success}，失败 {failed}。".format(
                    processed=status.total_symbols,
                    success=status.succeeded_symbols,
                    failed=status.failed_symbols,
                )
            )
            self._complete_refresh(status="completed", message=completion_message)
            logger.info(completion_message)
        except Exception as exc:  # pragma: no cover - 兜底保护真实运行环境
            logger.exception("数据补全任务执行失败")
            self._save_refresh_cursor(last_processed_symbol)
            self._complete_refresh(
                status="failed",
                message="数据补全任务执行失败：{message}".format(message=str(exc)),
                error_message="{error_type}: {message}".format(
                    error_type=type(exc).__name__,
                    message=str(exc),
                ),
            )

    def _select_symbols_for_run(
        self,
        universe_items: list[object],
        max_symbols: Optional[int],
    ) -> list[object]:
        """根据游标选择本轮要补全的股票，避免每次都从第一只开始。"""
        if not universe_items:
            return []

        if max_symbols is None or max_symbols <= 0 or max_symbols >= len(universe_items):
            return universe_items

        symbols = [str(getattr(item, "symbol", "")) for item in universe_items]
        cursor_symbol = self._market_data_service.get_refresh_cursor(_REFRESH_CURSOR_KEY)
        start_index = 0
        if cursor_symbol and cursor_symbol in symbols:
            start_index = (symbols.index(cursor_symbol) + 1) % len(universe_items)

        batch_size = min(max_symbols, len(universe_items))
        selected_items: list[object] = []
        for offset in range(batch_size):
            selected_items.append(universe_items[(start_index + offset) % len(universe_items)])

        logger.info(
            "本轮补全游标选择：cursor=%s, start_symbol=%s, batch_size=%s",
            cursor_symbol,
            getattr(selected_items[0], "symbol", None) if selected_items else None,
            batch_size,
        )
        return selected_items

    def _save_refresh_cursor(self, last_symbol: Optional[str]) -> None:
        """保存本轮补全游标，供下次补全续扫。"""
        if not last_symbol:
            return
        try:
            self._market_data_service.set_refresh_cursor(
                _REFRESH_CURSOR_KEY,
                last_symbol,
            )
        except Exception:  # pragma: no cover - 游标失败不应中断主流程
            logger.exception("写入数据补全游标失败，last_symbol=%s", last_symbol)

    def _refresh_one_symbol(self, symbol: str) -> bool:
        """补全单只股票的核心数据域。"""
        completed_steps = 0

        if self._run_refresh_step(
            symbol=symbol,
            stage_name="基础信息",
            success_counter_name="profiles_updated",
            failure_counter_name="profile_step_failures",
            callback=lambda: self._market_data_service.refresh_stock_profile(symbol),
        ):
            completed_steps += 1

        daily_bars_rows = self._run_refresh_step(
            symbol=symbol,
            stage_name="日线数据",
            success_counter_name="daily_bars_updated",
            failure_counter_name="daily_bar_step_failures",
            callback=lambda: self._market_data_service.refresh_daily_bars(
                symbol,
                lookback_days=self._daily_bar_lookback_days,
            ),
        )
        if daily_bars_rows is not None:
            completed_steps += 1
            self._add_counter("daily_bars_synced_rows", int(daily_bars_rows))

        if self._run_refresh_step(
            symbol=symbol,
            stage_name="财务摘要",
            success_counter_name="financial_summaries_updated",
            failure_counter_name="financial_step_failures",
            callback=lambda: self._market_data_service.refresh_stock_financial_summary(
                symbol,
            ),
        ):
            completed_steps += 1

        announcement_items = self._run_refresh_step(
            symbol=symbol,
            stage_name="近期公告",
            success_counter_name="announcements_updated",
            failure_counter_name="announcement_step_failures",
            callback=lambda: self._market_data_service.refresh_stock_announcements(
                symbol,
                lookback_days=self._announcement_lookback_days,
                limit=self._announcement_limit,
            ),
        )
        if announcement_items is not None:
            completed_steps += 1
            self._add_counter("announcements_synced_items", int(announcement_items))

        return completed_steps > 0

    def _run_refresh_step(
        self,
        symbol: str,
        stage_name: str,
        success_counter_name: str,
        failure_counter_name: str,
        callback: Callable[[], object],
    ) -> Optional[object]:
        """执行单个数据域补全，失败时记录 warning 并继续。"""
        try:
            result = callback()
        except Exception as exc:  # pragma: no cover - 真实运行时保护
            detail = self._build_error_detail(exc)
            warning_message = "{symbol} [{stage}] {detail}".format(
                symbol=symbol,
                stage=stage_name,
                detail=detail,
            )
            logger.warning("数据补全步骤失败：%s", warning_message)
            self._add_warning(warning_message)
            self._add_counter(failure_counter_name, 1)
            return None

        self._add_counter(success_counter_name, 1)
        return result

    def _build_error_detail(self, exc: Exception) -> str:
        """拼接异常链路，输出可排查的详细原因。"""
        chain: list[str] = []
        current: Optional[BaseException] = exc
        while current is not None:
            chain.append(
                "{error_type}: {message}".format(
                    error_type=type(current).__name__,
                    message=str(current),
                ),
            )
            current = current.__cause__ or current.__context__
        return " <- ".join(chain)

    def _increment_processed(self) -> None:
        self._add_counter("processed_symbols", 1)

    def _increment_success(self) -> None:
        self._add_counter("succeeded_symbols", 1)

    def _increment_failure(self, error_message: str) -> None:
        self._add_counter("failed_symbols", 1)
        with self._lock:
            self._state.recent_errors.append(error_message)
            self._state.recent_errors = self._state.recent_errors[-_MAX_RECENT_MESSAGES:]

    def _add_warning(self, warning_message: str) -> None:
        with self._lock:
            self._state.recent_warnings.append(warning_message)
            self._state.recent_warnings = self._state.recent_warnings[-_MAX_RECENT_MESSAGES:]

    def _add_counter(self, counter_name: str, value: int) -> None:
        with self._lock:
            current_value = getattr(self._state, counter_name)
            setattr(self._state, counter_name, current_value + value)

    def _update_state(self, **kwargs: object) -> None:
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._state, key, value)

    def _complete_refresh(
        self,
        status: str,
        message: str,
        error_message: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._state.status = status
            self._state.is_running = False
            self._state.finished_at = datetime.utcnow()
            self._state.current_stage = None
            self._state.current_symbol = None
            self._state.message = message
            if error_message:
                self._state.recent_errors.append(error_message)
                self._state.recent_errors = self._state.recent_errors[-_MAX_RECENT_MESSAGES:]

    def _build_status(self) -> DataRefreshStatus:
        return DataRefreshStatus(
            status=self._state.status,
            is_running=self._state.is_running,
            started_at=self._state.started_at,
            finished_at=self._state.finished_at,
            universe_count=self._state.universe_count,
            total_symbols=self._state.total_symbols,
            processed_symbols=self._state.processed_symbols,
            succeeded_symbols=self._state.succeeded_symbols,
            failed_symbols=self._state.failed_symbols,
            profiles_updated=self._state.profiles_updated,
            daily_bars_updated=self._state.daily_bars_updated,
            financial_summaries_updated=self._state.financial_summaries_updated,
            announcements_updated=self._state.announcements_updated,
            daily_bars_synced_rows=self._state.daily_bars_synced_rows,
            announcements_synced_items=self._state.announcements_synced_items,
            profile_step_failures=self._state.profile_step_failures,
            daily_bar_step_failures=self._state.daily_bar_step_failures,
            financial_step_failures=self._state.financial_step_failures,
            announcement_step_failures=self._state.announcement_step_failures,
            universe_updated=self._state.universe_updated,
            max_symbols=self._state.max_symbols,
            current_symbol=self._state.current_symbol,
            current_stage=self._state.current_stage,
            message=self._state.message,
            recent_warnings=list(self._state.recent_warnings),
            recent_errors=list(self._state.recent_errors),
        )
