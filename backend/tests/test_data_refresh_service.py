"""手动数据补全服务测试。"""

from __future__ import annotations

from contextlib import contextmanager

from app.services.data_service.refresh_service import DataRefreshService


class StubUniverseItem:
    """测试用股票池项。"""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol


class StubUniverseResponse:
    """测试用股票池响应。"""

    def __init__(self, symbols: list[str]) -> None:
        self.count = len(symbols)
        self.items = [StubUniverseItem(symbol) for symbol in symbols]


class StubMarketDataService:
    """测试用市场数据服务。"""

    def __init__(self) -> None:
        self.profile_symbols: list[str] = []
        self.daily_bar_symbols: list[tuple[str, int]] = []
        self.financial_symbols: list[str] = []
        self.announcement_symbols: list[tuple[str, int, int]] = []
        self.refresh_cursor: str | None = None

    def refresh_stock_universe(self) -> StubUniverseResponse:
        return StubUniverseResponse(["600519.SH", "000001.SZ"])

    @contextmanager
    def session_scope(self):
        yield

    def refresh_stock_profile(self, symbol: str):
        self.profile_symbols.append(symbol)
        return None

    def refresh_daily_bars(self, symbol: str, lookback_days: int = 400) -> int:
        self.daily_bar_symbols.append((symbol, lookback_days))
        return 2

    def refresh_stock_financial_summary(self, symbol: str):
        self.financial_symbols.append(symbol)
        return None

    def refresh_stock_announcements(
        self,
        symbol: str,
        lookback_days: int = 90,
        limit: int = 50,
    ):
        self.announcement_symbols.append((symbol, lookback_days, limit))
        return None

    def get_refresh_cursor(self, cursor_key: str) -> str | None:
        return self.refresh_cursor

    def set_refresh_cursor(self, cursor_key: str, cursor_value: str | None) -> None:
        self.refresh_cursor = cursor_value


class FailingMarketDataService(StubMarketDataService):
    """测试个别股票失败时任务是否继续。"""

    def refresh_stock_profile(self, symbol: str):
        super().refresh_stock_profile(symbol)
        if symbol == "000001.SZ":
            raise RuntimeError("profile failed")
        return None


class FullyFailingMarketDataService(StubMarketDataService):
    """测试当一只股票所有数据域都失败时的状态。"""

    def refresh_stock_profile(self, symbol: str):
        raise RuntimeError("profile failed")

    def refresh_daily_bars(self, symbol: str, lookback_days: int = 400) -> int:
        raise RuntimeError("daily bars failed")

    def refresh_stock_financial_summary(self, symbol: str):
        raise RuntimeError("financial failed")

    def refresh_stock_announcements(
        self,
        symbol: str,
        lookback_days: int = 90,
        limit: int = 50,
    ):
        raise RuntimeError("announcements failed")


def test_data_refresh_service_completes_and_updates_status() -> None:
    """手动数据补全应能完成并返回结构化状态。"""
    market_data_service = StubMarketDataService()
    refresh_service = DataRefreshService(
        market_data_service=market_data_service,
        daily_bar_lookback_days=400,
        announcement_lookback_days=90,
        announcement_limit=50,
        progress_log_interval=1,
        task_runner=lambda callback: callback(),
    )

    status = refresh_service.start_manual_refresh(max_symbols=1)

    assert status.status == "completed"
    assert status.universe_updated is True
    assert status.universe_count == 2
    assert status.total_symbols == 1
    assert status.processed_symbols == 1
    assert status.succeeded_symbols == 1
    assert status.failed_symbols == 0
    assert status.profiles_updated == 1
    assert status.daily_bars_updated == 1
    assert status.financial_summaries_updated == 1
    assert status.announcements_updated == 1
    assert status.daily_bars_synced_rows == 2
    assert status.announcements_synced_items == 0
    assert market_data_service.profile_symbols == ["600519.SH"]
    assert market_data_service.daily_bar_symbols == [("600519.SH", 400)]
    assert market_data_service.financial_symbols == ["600519.SH"]
    assert market_data_service.announcement_symbols == [("600519.SH", 90, 50)]
    assert market_data_service.refresh_cursor == "600519.SH"


def test_data_refresh_service_keeps_running_after_single_symbol_failure() -> None:
    """单个数据域失败不应让整只股票计为失败。"""
    refresh_service = DataRefreshService(
        market_data_service=FailingMarketDataService(),
        daily_bar_lookback_days=300,
        announcement_lookback_days=30,
        announcement_limit=20,
        progress_log_interval=1,
        task_runner=lambda callback: callback(),
    )

    status = refresh_service.start_manual_refresh()

    assert status.status == "completed"
    assert status.total_symbols == 2
    assert status.processed_symbols == 2
    assert status.succeeded_symbols == 2
    assert status.failed_symbols == 0
    assert status.recent_errors == []
    assert status.profile_step_failures == 1
    assert len(status.recent_warnings) == 1
    assert "000001.SZ [基础信息]" in status.recent_warnings[0]


def test_data_refresh_service_marks_symbol_failed_when_all_steps_fail() -> None:
    """只有所有数据域都失败时，整只股票才应记为失败。"""
    refresh_service = DataRefreshService(
        market_data_service=FullyFailingMarketDataService(),
        daily_bar_lookback_days=300,
        announcement_lookback_days=30,
        announcement_limit=20,
        progress_log_interval=1,
        task_runner=lambda callback: callback(),
    )

    status = refresh_service.start_manual_refresh(max_symbols=1)

    assert status.status == "completed"
    assert status.total_symbols == 1
    assert status.processed_symbols == 1
    assert status.succeeded_symbols == 0
    assert status.failed_symbols == 1
    assert any("600519.SH" in message for message in status.recent_errors)
    assert status.profile_step_failures == 1
    assert status.daily_bar_step_failures == 1
    assert status.financial_step_failures == 1
    assert status.announcement_step_failures == 1


def test_data_refresh_service_rotates_symbols_with_cursor() -> None:
    """按 max_symbols 批次补全时，应基于游标轮转而不是总从第一只开始。"""
    market_data_service = StubMarketDataService()
    refresh_service = DataRefreshService(
        market_data_service=market_data_service,
        daily_bar_lookback_days=400,
        announcement_lookback_days=90,
        announcement_limit=50,
        progress_log_interval=1,
        task_runner=lambda callback: callback(),
    )

    refresh_service.start_manual_refresh(max_symbols=1)
    refresh_service.start_manual_refresh(max_symbols=1)

    assert market_data_service.profile_symbols == ["600519.SH", "000001.SZ"]
    assert market_data_service.refresh_cursor == "000001.SZ"
