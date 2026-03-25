"""Tests for mootdx validation matrix script helpers."""

from datetime import date

from app.schemas.market_data import DailyBar
from app.scripts.run_mootdx_validation_matrix import (
    _normalize_frequencies,
    _parse_multi_values,
    _summarize_daily_comparison,
    build_argument_parser,
)


def test_matrix_argument_parser_supports_multiple_symbols_and_outputs() -> None:
    parser = build_argument_parser()

    args = parser.parse_args(
        [
            "--tdxdir",
            "D:/new_tdx64",
            "--symbols",
            "600519.SH",
            "000001.SZ",
            "--frequencies",
            "1m",
            "5m",
            "--compare-provider",
            "akshare",
            "--output-json",
            "result.json",
            "--output-csv",
            "result.csv",
        ],
    )

    assert args.symbols == ["600519.SH", "000001.SZ"]
    assert args.frequencies == ["1m", "5m"]
    assert args.compare_provider == "akshare"
    assert args.output_json == "result.json"
    assert args.output_csv == "result.csv"


def test_parse_multi_values_supports_comma_separated_items() -> None:
    values = _parse_multi_values(["600519.SH,000001.SZ", "300750.SZ"])

    assert values == ["600519.SH", "000001.SZ", "300750.SZ"]


def test_normalize_frequencies_deduplicates() -> None:
    frequencies = _normalize_frequencies(["1m", "5m", "1m"])

    assert frequencies == ["1m", "5m"]


def test_daily_comparison_reports_mismatches() -> None:
    reference_bars = [
        DailyBar(
            symbol="600519.SH",
            trade_date=date(2024, 1, 2),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0,
            amount=100000.0,
            source="mootdx",
        )
    ]
    compare_bars = [
        DailyBar(
            symbol="600519.SH",
            trade_date=date(2024, 1, 2),
            open=100.0,
            high=101.0,
            low=99.0,
            close=101.5,
            volume=1000.0,
            amount=100000.0,
            source="akshare",
        )
    ]

    summary = _summarize_daily_comparison(
        reference_bars=reference_bars,
        compare_bars=compare_bars,
        provider_name="akshare",
    )

    assert summary["status"] == "mismatched"
    assert summary["mismatch_count"] == 1
    assert "close" in summary["mismatch_note"]
