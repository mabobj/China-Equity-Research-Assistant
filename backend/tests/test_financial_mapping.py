from datetime import date

from app.services.data_service.financial_mapping import (
    map_akshare_financial_payload,
    map_baostock_financial_payload,
    map_tushare_financial_payload,
)
from app.services.data_service.normalize import (
    normalize_financial_report_period,
    normalize_financial_report_type,
)


def test_map_tushare_financial_payload() -> None:
    mapped = map_tushare_financial_payload(
        "600519.SH",
        {
            "income": {
                "end_date": "2025-12-31",
                "total_revenue": "1000000000",
                "n_income_attr_p": "500000000",
                "report_type": "1",
            },
            "fina_indicator": {
                "roe": "18.6",
                "debt_to_assets": "36.5",
                "grossprofit_margin": "91.2",
                "netprofit_yoy": "12.0",
                "tr_yoy": "14.8",
                "eps": "42.6",
                "bps": "210.3",
            },
        },
        name="Kweichow Moutai",
    )

    assert mapped["symbol"] == "600519.SH"
    assert mapped["report_period"] == date(2025, 12, 31)
    assert mapped["report_type"] == "annual"
    assert mapped["revenue"] == 1000000000.0
    assert mapped["net_profit"] == 500000000.0
    assert mapped["roe"] == 18.6


def test_map_baostock_financial_payload() -> None:
    mapped = map_baostock_financial_payload(
        "000001.SZ",
        {
            "report_period": "2025-09-30",
            "profit": {"netProfit": "200000000", "epsTTM": "1.25"},
            "growth": {"YOYNetProfit": "8.4", "YOYMBRevenue": "6.1"},
            "balance": {"liabilityToAsset": "74.2", "bps": "18.2"},
            "dupont": {"dupontROE": "11.5"},
            "operation": {"mainBusinessRevenue": "1200000000", "gpMargin": "28.0"},
        },
    )

    assert mapped["report_type"] == "q3"
    assert mapped["revenue"] == 1200000000.0
    assert mapped["net_profit"] == 200000000.0
    assert mapped["debt_ratio"] == 74.2


def test_map_akshare_financial_payload() -> None:
    mapped = map_akshare_financial_payload(
        "000001.SZ",
        {
            "name": "Ping An Bank",
            "row": {
                "REPORT_DATE": "2025-03-31",
                "OPERATE_INCOME": "500000000",
                "PARENT_NETPROFIT": "120000000",
                "ROE": "10.2",
                "DEBT_RATIO": "91.0",
                "YSTZ": "4.2",
                "SJLTZ": "3.8",
                "GROSS_MARGIN": "31.5",
                "EPS": "0.55",
                "BPS": "19.8",
            },
        },
    )

    assert mapped["report_type"] == "q1"
    assert mapped["revenue"] == 500000000.0
    assert mapped["net_profit"] == 120000000.0
    assert mapped["eps"] == 0.55


def test_financial_report_type_normalization() -> None:
    q1_period = normalize_financial_report_period("2025-03-31")
    half_period = normalize_financial_report_period("2025-06-30")
    q3_period = normalize_financial_report_period("2025-09-30")
    annual_period = normalize_financial_report_period("2025-12-31")

    assert normalize_financial_report_type(None, report_period=q1_period) == "q1"
    assert normalize_financial_report_type(None, report_period=half_period) == "half"
    assert normalize_financial_report_type(None, report_period=q3_period) == "q3"
    assert normalize_financial_report_type(None, report_period=annual_period) == "annual"
    assert normalize_financial_report_type("ttm") == "ttm"
    assert normalize_financial_report_type("mystery") == "unknown"
