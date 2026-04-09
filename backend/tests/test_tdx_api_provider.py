"""tdx-api provider 测试。"""

from datetime import date

from app.services.data_service.providers.tdx_api_provider import TdxApiProvider


def test_tdx_api_provider_parses_universe_payload() -> None:
    """股票池应能从 code/message/data 响应壳中正确解析。"""
    provider = TdxApiProvider(base_url="http://127.0.0.1:8080")
    provider._request_json = lambda *args, **kwargs: {  # type: ignore[method-assign]
        "code": 0,
        "message": "ok",
        "data": [
            {"code": "sh600519", "name": "贵州茅台"},
            {"code": "sz000001", "name": "平安银行"},
        ],
    }

    items = provider.get_stock_universe()

    assert len(items) == 2
    assert items[0].symbol == "600519.SH"
    assert items[0].name == "贵州茅台"
    assert items[1].symbol == "000001.SZ"


def test_tdx_api_provider_maps_daily_bars_without_schema_breakage() -> None:
    """日线 provider 应返回统一 DailyBar 列表，后续单位转换交给 normalize。"""
    provider = TdxApiProvider(base_url="http://127.0.0.1:8080")
    provider._request_json = lambda *args, **kwargs: {  # type: ignore[method-assign]
        "code": 0,
        "message": "ok",
        "data": [
            {
                "date": "2026-04-08",
                "open": 12345,
                "high": 12500,
                "low": 12200,
                "close": 12480,
                "volume": 321,
                "amount": 987654,
            }
        ],
    }

    bars = provider.get_daily_bars(
        "600519.SH",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 8),
    )

    assert len(bars) == 1
    assert bars[0].symbol == "600519.SH"
    assert bars[0].trade_date.isoformat() == "2026-04-08"
    assert bars[0].open == 12345.0
    assert bars[0].volume == 321.0
