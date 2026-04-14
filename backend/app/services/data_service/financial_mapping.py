"""Centralized financial provider field mapping."""

from __future__ import annotations

from typing import Any, Mapping

from app.services.data_service.normalize import (
    normalize_financial_amount_to_yuan,
    normalize_financial_percent,
    normalize_financial_report_period,
    normalize_financial_report_type,
)


def map_tushare_financial_payload(
    symbol: str,
    payload: Mapping[str, Any],
    name: str | None = None,
) -> dict[str, Any]:
    income_row = _to_mapping(payload.get("income"))
    indicator_row = _to_mapping(payload.get("fina_indicator"))
    merged = {**income_row, **indicator_row}

    report_period = normalize_financial_report_period(
        merged.get("end_date") or merged.get("report_period") or merged.get("ann_date")
    )
    raw_report_type = merged.get("report_type")
    if raw_report_type in {"1", 1}:
        raw_report_type = "annual"
    elif raw_report_type in {"2", 2}:
        raw_report_type = "q1"
    elif raw_report_type in {"3", 3}:
        raw_report_type = "half"
    elif raw_report_type in {"4", 4}:
        raw_report_type = "q3"
    report_type = normalize_financial_report_type(
        raw_report_type,
        report_period=report_period,
    )

    return {
        "symbol": symbol,
        "name": name or _pick_text(merged, "name", "ts_name", "stock_name"),
        "report_period": report_period,
        "report_type": report_type,
        "revenue": normalize_financial_amount_to_yuan(
            _pick_number(merged, "revenue", "total_revenue", "total_operate_income")
        ),
        "net_profit": normalize_financial_amount_to_yuan(
            _pick_number(merged, "net_profit", "n_income_attr_p", "n_income")
        ),
        "roe": normalize_financial_percent(
            _pick_number(merged, "roe", "roe_dt", "roe_avg")
        ),
        "debt_ratio": normalize_financial_percent(
            _pick_number(merged, "debt_ratio", "debt_to_assets")
        ),
        "revenue_yoy": normalize_financial_percent(
            _pick_number(merged, "revenue_yoy", "tr_yoy", "or_yoy")
        ),
        "net_profit_yoy": normalize_financial_percent(
            _pick_number(merged, "net_profit_yoy", "netprofit_yoy", "profit_dedt_yoy")
        ),
        "gross_margin": normalize_financial_percent(
            _pick_number(merged, "gross_margin", "grossprofit_margin")
        ),
        "eps": _pick_number(merged, "eps", "basic_eps", "dt_eps"),
        "bps": _pick_number(merged, "bps", "book_value_per_share", "bps"),
        "source": "tushare",
    }


def map_baostock_financial_payload(
    symbol: str,
    payload: Mapping[str, Any],
    name: str | None = None,
) -> dict[str, Any]:
    profit_row = _to_mapping(payload.get("profit"))
    operation_row = _to_mapping(payload.get("operation"))
    growth_row = _to_mapping(payload.get("growth"))
    balance_row = _to_mapping(payload.get("balance"))
    dupont_row = _to_mapping(payload.get("dupont"))
    merged = {**profit_row, **operation_row, **growth_row, **balance_row, **dupont_row}

    report_period = normalize_financial_report_period(
        payload.get("report_period") or merged.get("statDate") or merged.get("pubDate")
    )
    report_type = normalize_financial_report_type(
        payload.get("report_type"),
        report_period=report_period,
    )

    return {
        "symbol": symbol,
        "name": name,
        "report_period": report_period,
        "report_type": report_type,
        "revenue": normalize_financial_amount_to_yuan(
            _pick_number(
                merged,
                "MBRevenue",
                "mainBusinessRevenue",
                "totalOperateIncome",
                "totalRevenue",
            )
        ),
        "net_profit": normalize_financial_amount_to_yuan(
            _pick_number(
                merged,
                "netProfit",
                "NPToShareholders",
                "niap",
                "netIncome",
            )
        ),
        "roe": normalize_financial_percent(
            _pick_number(merged, "dupontROE", "roeAvg", "roe")
        ),
        "debt_ratio": normalize_financial_percent(
            _pick_number(merged, "liabilityToAsset", "debtToAsset", "assetDebtRatio")
        ),
        "revenue_yoy": normalize_financial_percent(
            _pick_number(merged, "YOYMBRevenue", "YOYTotalRevenue", "revenue_yoy")
        ),
        "net_profit_yoy": normalize_financial_percent(
            _pick_number(merged, "YOYNetProfit", "YOYNI", "net_profit_yoy")
        ),
        "gross_margin": normalize_financial_percent(
            _pick_number(merged, "gpMargin", "grossMargin", "gross_margin")
        ),
        "eps": _pick_number(merged, "epsTTM", "eps", "basicEPS"),
        "bps": _pick_number(merged, "bps", "netAssetPS"),
        "source": "baostock",
    }


def map_akshare_financial_payload(
    symbol: str,
    payload: Mapping[str, Any],
    name: str | None = None,
) -> dict[str, Any]:
    row = _to_mapping(payload.get("row") or payload)
    report_period = normalize_financial_report_period(
        row.get("REPORT_DATE")
        or row.get("REPORT_PERIOD")
        or row.get("NOTICE_DATE")
        or row.get("report_period")
    )
    report_type = normalize_financial_report_type(
        row.get("report_type"),
        report_period=report_period,
    )
    return {
        "symbol": symbol,
        "name": name or payload.get("name") or _pick_text(row, "SECURITY_NAME_ABBR", "NAME", "SECURITY_NAME"),
        "report_period": report_period,
        "report_type": report_type,
        "revenue": normalize_financial_amount_to_yuan(
            _pick_number(row, "TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "TOTAL_REVENUE")
        ),
        "net_profit": normalize_financial_amount_to_yuan(
            _pick_number(row, "PARENT_NETPROFIT", "NETPROFIT", "NET_INCOME")
        ),
        "roe": normalize_financial_percent(
            _pick_number(row, "ROE_WEIGHT", "WEIGHTAVG_ROE", "ROE")
        ),
        "debt_ratio": normalize_financial_percent(
            _pick_number(row, "ZCFZL", "DEBT_RATIO")
        ),
        "revenue_yoy": normalize_financial_percent(
            _pick_number(row, "YSTZ", "TOTAL_OPERATE_INCOME_YOY", "OPERATE_INCOME_YOY")
        ),
        "net_profit_yoy": normalize_financial_percent(
            _pick_number(row, "SJLTZ", "NETPROFIT_YOY", "PARENT_NETPROFIT_YOY")
        ),
        "gross_margin": normalize_financial_percent(
            _pick_number(row, "XSMLL", "GROSS_MARGIN")
        ),
        "eps": _pick_number(row, "BASIC_EPS", "EPSJB", "EPS"),
        "bps": _pick_number(row, "BPS"),
        "source": "akshare",
    }


def _to_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _pick_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _pick_number(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            continue
    return None
