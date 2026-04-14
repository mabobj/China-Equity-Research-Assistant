from app.services.data_service.financial_quality import (
    compare_financial_summary_consistency,
    evaluate_financial_summary_quality,
)


def test_quality_marks_core_missing_as_degraded() -> None:
    quality_status, missing_fields, warnings = evaluate_financial_summary_quality(
        {
            "report_period": None,
            "report_type": "unknown",
            "revenue": None,
            "net_profit": 1.0,
            "roe": None,
            "debt_ratio": None,
            "gross_margin": None,
        }
    )

    assert quality_status == "degraded"
    assert "report_period" in missing_fields
    assert "revenue" in missing_fields
    assert "unknown_report_type" in warnings


def test_quality_marks_unreasonable_ranges_as_warning() -> None:
    quality_status, _, warnings = evaluate_financial_summary_quality(
        {
            "report_period": "2025-12-31",
            "report_type": "annual",
            "revenue": 10.0,
            "net_profit": 2.0,
            "roe": 300.0,
            "debt_ratio": 120.0,
            "gross_margin": -150.0,
        }
    )

    assert quality_status == "warning"
    assert "roe_out_of_range" in warnings
    assert "debt_ratio_out_of_range" in warnings
    assert "gross_margin_out_of_range" in warnings


def test_compare_financial_summary_consistency_detects_large_gap() -> None:
    warnings = compare_financial_summary_consistency(
        {"revenue": 100.0, "net_profit": 50.0, "roe": 10.0},
        {"revenue": 200.0, "net_profit": 55.0, "roe": 15.0},
    )

    assert "revenue_provider_mismatch" in warnings
