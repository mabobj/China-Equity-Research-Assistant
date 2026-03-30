"""日线清洗层测试。"""

from datetime import date

from app.schemas.market_data import DailyBar
from app.services.data_service.cleaning.bars import clean_daily_bars


def test_clean_daily_bars_maps_fields_and_normalizes_units() -> None:
    """AKShare 风格字段应映射并统一到内部口径。"""
    result = clean_daily_bars(
        symbol="600519.SH",
        rows=[
            {
                "symbol": "600519",
                "日期": "2024-01-02",
                "开盘": "100.0",
                "最高": "102.0",
                "最低": "99.0",
                "收盘": "101.0",
                "成交量": "10",
                "成交额": "100000.0",
                "source": "akshare",
            }
        ],
        as_of_date=date(2024, 1, 3),
    )

    assert result.summary.quality_status == "ok"
    assert result.summary.output_rows == 1
    bar = result.bars[0]
    assert bar.symbol == "600519.SH"
    assert bar.trade_date == date(2024, 1, 2)
    assert bar.volume == 1000.0
    assert bar.amount == 100000.0


def test_clean_daily_bars_drops_invalid_rows_and_deduplicates() -> None:
    """异常行应剔除；重复键只保留一条。"""
    rows = [
        {
            "symbol": "600519.SH",
            "trade_date": "2024-01-02",
            "open": 10.0,
            "high": 10.8,
            "low": 9.9,
            "close": 10.5,
            "volume": 1000.0,
            "amount": 10000.0,
            "source": "mootdx",
        },
        {
            "symbol": "600519.SH",
            "trade_date": "2024-01-02",
            "open": 10.0,
            "high": 10.8,
            "low": 9.9,
            "close": 10.5,
            "volume": 1000.0,
            "amount": 10000.0,
            "source": "mootdx",
        },
        {
            "symbol": "600519.SH",
            "trade_date": "2024-01-02",
            "open": 10.1,
            "high": 10.9,
            "low": 9.8,
            "close": 10.6,
            "volume": 1002.0,
            "amount": 10020.0,
            "source": "mootdx",
        },
        {
            "symbol": "600519.SH",
            "trade_date": "2024-01-03",
            "open": 10.0,
            "high": 10.1,
            "low": 9.9,
            "close": -1.0,
            "volume": 500.0,
            "amount": 5000.0,
            "source": "mootdx",
        },
    ]
    result = clean_daily_bars(symbol="600519.SH", rows=rows)

    assert result.summary.output_rows == 1
    assert result.summary.dropped_rows == 3
    assert result.summary.dropped_duplicate_rows == 2
    assert result.bars[0].close == 10.6
    assert result.summary.quality_status == "failed"
    assert any("invalid_close_price" in item for item in result.summary.warning_messages)


def test_clean_daily_bars_accepts_daily_bar_schema() -> None:
    """已有 DailyBar schema 输入也应可直接清洗。"""
    source_bars = [
        DailyBar(
            symbol="sh600519",
            trade_date=date(2024, 1, 2),
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            volume=1000.0,
            amount=100000.0,
            source="baostock",
        )
    ]
    result = clean_daily_bars(symbol="600519.SH", rows=source_bars)

    assert result.summary.output_rows == 1
    assert result.bars[0].symbol == "600519.SH"
    assert result.bars[0].source == "baostock"


def test_clean_daily_bars_converts_mootdx_volume_to_share() -> None:
    """mootdx 日线成交量应统一转换为“股”口径。"""
    result = clean_daily_bars(
        symbol="000001.SZ",
        rows=[
            {
                "symbol": "000001.SZ",
                "trade_date": "2024-01-03",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 30087.0,
                "amount": 123456789.0,
                "source": "mootdx",
            }
        ],
        as_of_date=date(2024, 1, 3),
    )

    assert result.summary.quality_status == "ok"
    assert len(result.bars) == 1
    assert result.bars[0].volume == 3008700.0
