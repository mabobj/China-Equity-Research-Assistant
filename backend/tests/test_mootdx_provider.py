"""Tests for mootdx provider."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from app.services.data_service.providers.mootdx_provider import MootdxProvider


class FakeReader:
    def daily(self, symbol: str):
        assert symbol == "600519"
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-02",
                    "open": 100.0,
                    "high": 102.0,
                    "low": 99.0,
                    "close": 101.0,
                    "volume": 1000.0,
                    "amount": 100000.0,
                }
            ]
        )

    def minute(self, symbol: str, frequency: str = "1m"):
        assert symbol == "600519"
        assert frequency == "1m"
        return pd.DataFrame(
            [
                {
                    "datetime": "2024-01-02 09:31:00",
                    "open": 100.0,
                    "high": 100.5,
                    "low": 99.8,
                    "close": 100.2,
                    "volume": 200.0,
                    "amount": 20000.0,
                }
            ]
        )

    def fzline(self, symbol: str):
        assert symbol == "600519"
        return pd.DataFrame(
            [
                {
                    "time": "09:31",
                    "price": 100.2,
                    "volume": 200.0,
                    "amount": 20000.0,
                }
            ]
        )


class FakeReaderWithDateTimeline:
    def fzline(self, symbol: str):
        assert symbol == "605255"
        return pd.DataFrame(
            [
                {
                    "date": "2026-03-24 15:00:00",
                    "close": 99.8,
                    "volume": 40000.0,
                    "amount": 4000000.0,
                },
                {
                    "date": "2026-03-25 14:55:00",
                    "close": 100.88,
                    "volume": 44200.0,
                    "amount": 4455702.0,
                },
                {
                    "date": "2026-03-25 15:00:00",
                    "close": 100.8,
                    "volume": 47500.0,
                    "amount": 4787212.0,
                }
            ]
        )


def test_mootdx_provider_maps_daily_and_intraday_data() -> None:
    provider = MootdxProvider(tdx_dir=Path("C:/mock_tdx"))
    provider._get_reader = lambda: FakeReader()  # type: ignore[method-assign]

    daily_bars = provider.get_daily_bars("600519.SH")
    minute_bars = provider.get_intraday_bars("600519.SH", frequency="1m", limit=10)
    timeline = provider.get_timeline("600519.SH", limit=10)

    assert len(daily_bars) == 1
    assert daily_bars[0].symbol == "600519.SH"
    assert daily_bars[0].trade_date.isoformat() == "2024-01-02"

    assert len(minute_bars) == 1
    assert minute_bars[0].trade_datetime == datetime(2024, 1, 2, 9, 31, 0)
    assert minute_bars[0].frequency == "1m"

    assert len(timeline) == 1
    assert timeline[0].trade_time.isoformat() == "09:31:00"


def test_mootdx_provider_reports_missing_dir() -> None:
    provider = MootdxProvider(tdx_dir=Path("Z:/path/not/exist"))

    assert provider.is_available() is False
    assert "MOOTDX_TDX_DIR does not exist" in str(provider.get_unavailable_reason())


def test_mootdx_provider_parses_timeline_date_column() -> None:
    provider = MootdxProvider(tdx_dir=Path("C:/mock_tdx"))
    provider._get_reader = lambda: FakeReaderWithDateTimeline()  # type: ignore[method-assign]

    timeline = provider.get_timeline("605255.SH", limit=10)

    assert len(timeline) == 2
    assert timeline[0].trade_time.isoformat() == "14:55:00"
    assert timeline[1].trade_time.isoformat() == "15:00:00"
    assert timeline[0].price == 100.88
