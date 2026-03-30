"""财务摘要清洗层测试。"""

from datetime import date

from app.services.data_service.cleaning.financials import clean_financial_summary


def test_clean_financial_summary_maps_aliases_and_normalizes_units() -> None:
    """中英文字段、金额与百分比口径应统一。"""
    result = clean_financial_summary(
        symbol="sh600519",
        rows=[
            {
                "symbol": "600519",
                "股票简称": "贵州茅台",
                "报告期": "2024年报",
                "营业总收入": "12.5亿",
                "营收同比": "12.5%",
                "归母净利润": "6.8亿",
                "净利润同比": "0.18",
                "净资产收益率": "0.148",
                "资产负债率": "36.2%",
                "source": "akshare",
            }
        ],
        as_of_date=date(2025, 1, 15),
        provider_used="akshare",
        source_mode="provider_only",
    )

    assert result.summary is not None
    summary = result.summary
    assert summary.symbol == "600519.SH"
    assert summary.name == "贵州茅台"
    assert summary.report_period == date(2024, 12, 31)
    assert summary.report_type == "annual"
    assert summary.revenue == 1250000000.0
    assert summary.net_profit == 680000000.0
    assert summary.net_profit_yoy == 18.0
    assert summary.roe is not None
    assert abs(summary.roe - 14.8) < 1e-9
    assert summary.debt_ratio == 36.2
    assert summary.as_of_date == date(2025, 1, 15)
    assert summary.provider_used == "akshare"
    assert summary.source_mode == "provider_only"
    assert result.cleaning_summary.quality_status in {"ok", "warning"}


def test_clean_financial_summary_parses_q3_and_ttm_report_type() -> None:
    """应能识别季度和 TTM 报告类型。"""
    q3_result = clean_financial_summary(
        symbol="000001.SZ",
        rows=[
            {
                "symbol": "000001.SZ",
                "report_period": "2024Q3",
                "revenue": 100.0,
                "net_profit": 80.0,
                "roe": 10.0,
                "debt_ratio": 40.0,
                "source": "akshare",
            }
        ],
    )
    assert q3_result.summary is not None
    assert q3_result.summary.report_type == "q3"
    assert q3_result.summary.report_period == date(2024, 9, 30)

    ttm_result = clean_financial_summary(
        symbol="000001.SZ",
        rows=[
            {
                "symbol": "000001.SZ",
                "report_period": "TTM",
                "report_type": "ttm",
                "revenue": 100.0,
                "net_profit": 80.0,
                "roe": 10.0,
                "debt_ratio": 40.0,
                "source": "akshare",
            }
        ],
    )
    assert ttm_result.summary is not None
    assert ttm_result.summary.report_type == "ttm"
    assert ttm_result.summary.report_period is None


def test_clean_financial_summary_marks_failed_when_core_fields_unusable() -> None:
    """核心字段不可用时，质量应降为 failed。"""
    result = clean_financial_summary(
        symbol="600519.SH",
        rows=[
            {
                "symbol": "600519.SH",
                "report_period": "invalid_period",
                "source": "akshare",
            }
        ],
    )

    assert result.summary is not None
    assert result.summary.quality_status == "failed"
    assert result.cleaning_summary.quality_status == "failed"
    assert any(
        "core_financial_fields_all_missing" in item
        for item in result.cleaning_summary.warning_messages
    )


def test_clean_financial_summary_deduplicates_conflicting_rows() -> None:
    """同股票同报告期冲突记录应保留更完整的一条。"""
    result = clean_financial_summary(
        symbol="600519.SH",
        rows=[
            {
                "symbol": "600519.SH",
                "report_period": "2024-12-31",
                "revenue": 10.0,
                "net_profit": 5.0,
                "roe": 8.0,
                "debt_ratio": 30.0,
                "source": "akshare",
            },
            {
                "symbol": "600519.SH",
                "report_period": "2024-12-31",
                "revenue": 12.0,
                "net_profit": 6.0,
                "roe": 9.0,
                "debt_ratio": 31.0,
                "gross_margin": 40.0,
                "eps": 3.0,
                "bps": 10.0,
                "source": "akshare",
            },
        ],
    )

    assert result.summary is not None
    assert result.summary.revenue == 12.0
    assert result.summary.gross_margin == 40.0
    assert result.cleaning_summary.dropped_duplicate_rows == 1
    assert any(
        "conflicting_financial_row" in item
        for item in result.cleaning_summary.warning_messages
    )
