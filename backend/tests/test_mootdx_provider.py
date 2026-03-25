"""Tests for mootdx provider."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from app.services.data_service.exceptions import InvalidRequestError, ProviderError
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
            ],
        )

    def minute(self, symbol: str, suffix: int = 1):
        assert symbol == "600519"
        assert suffix in {1, 5}
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
            ],
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
            ],
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
                },
            ],
        )


def _prepare_mock_tdx_dir(tmp_path: Path, code: str = "600519", exchange: str = "sh") -> Path:
    (tmp_path / "vipdoc" / exchange / "lday").mkdir(parents=True, exist_ok=True)
    (tmp_path / "vipdoc" / exchange / "minline").mkdir(parents=True, exist_ok=True)
    (tmp_path / "vipdoc" / exchange / "fzline").mkdir(parents=True, exist_ok=True)

    (tmp_path / "vipdoc" / exchange / "lday" / f"{exchange}{code}.day").write_bytes(b"test")
    (tmp_path / "vipdoc" / exchange / "minline" / f"{exchange}{code}.lc1").write_bytes(b"test")
    (tmp_path / "vipdoc" / exchange / "fzline" / f"{exchange}{code}.lc5").write_bytes(b"test")
    return tmp_path


def test_mootdx_provider_maps_daily_and_intraday_data(tmp_path: Path) -> None:
    provider = MootdxProvider(tdx_dir=_prepare_mock_tdx_dir(tmp_path))
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


def test_mootdx_provider_supports_5m_frequency(tmp_path: Path) -> None:
    provider = MootdxProvider(tdx_dir=_prepare_mock_tdx_dir(tmp_path))
    provider._get_reader = lambda: FakeReader()  # type: ignore[method-assign]

    minute_bars = provider.get_intraday_bars("600519.SH", frequency="5m", limit=10)

    assert len(minute_bars) == 1
    assert minute_bars[0].frequency == "5m"


def test_mootdx_provider_reports_missing_dir() -> None:
    provider = MootdxProvider(tdx_dir=Path("Z:/path/not/exist"))

    assert provider.is_available() is False
    assert "MOOTDX_TDX_DIR does not exist" in str(provider.get_unavailable_reason())


def test_mootdx_provider_parses_timeline_date_column(tmp_path: Path) -> None:
    provider = MootdxProvider(
        tdx_dir=_prepare_mock_tdx_dir(tmp_path, code="605255"),
    )
    provider._get_reader = lambda: FakeReaderWithDateTimeline()  # type: ignore[method-assign]

    timeline = provider.get_timeline("605255.SH", limit=10)

    assert len(timeline) == 2
    assert timeline[0].trade_time.isoformat() == "14:55:00"
    assert timeline[1].trade_time.isoformat() == "15:00:00"
    assert timeline[0].price == 100.88


def test_mootdx_provider_rejects_bj_symbol(tmp_path: Path) -> None:
    provider = MootdxProvider(tdx_dir=tmp_path)

    with pytest.raises(InvalidRequestError) as exc_info:
        provider.get_daily_bars("430047.BJ")

    assert "BJ symbols are not supported" in str(exc_info.value)


def test_mootdx_provider_reports_missing_local_file(tmp_path: Path) -> None:
    provider = MootdxProvider(tdx_dir=tmp_path)
    provider._get_reader = lambda: FakeReader()  # type: ignore[method-assign]

    with pytest.raises(ProviderError) as exc_info:
        provider.get_daily_bars("600519.SH")

    assert "mootdx local file is missing" in str(exc_info.value)


def test_mootdx_provider_rejects_unsupported_frequency(tmp_path: Path) -> None:
    provider = MootdxProvider(tdx_dir=_prepare_mock_tdx_dir(tmp_path))
    provider._get_reader = lambda: FakeReader()  # type: ignore[method-assign]

    with pytest.raises(InvalidRequestError) as exc_info:
        provider.get_intraday_bars("600519.SH", frequency="15m")

    assert "Unsupported intraday frequency" in str(exc_info.value)
