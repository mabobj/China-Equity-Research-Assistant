"""provider 原始字段映射到统一字段。"""

from __future__ import annotations

from typing import Any, Mapping

_DAILY_BAR_FIELD_ALIASES = {
    "symbol": "symbol",
    "code": "symbol",
    "ts_code": "symbol",
    "date": "trade_date",
    "trade_date": "trade_date",
    "datetime": "trade_date",
    "日期": "trade_date",
    "open": "open",
    "开盘": "open",
    "high": "high",
    "最高": "high",
    "low": "low",
    "最低": "low",
    "close": "close",
    "收盘": "close",
    "volume": "volume",
    "vol": "volume",
    "成交量": "volume",
    "amount": "amount",
    "amt": "amount",
    "成交额": "amount",
    "turnover_rate": "turnover_rate",
    "turnover": "turnover_rate",
    "换手率": "turnover_rate",
    "pct_change": "pct_change",
    "涨跌幅": "pct_change",
    "source": "source",
}

_FINANCIAL_FIELD_ALIASES = {
    "symbol": "symbol",
    "code": "symbol",
    "ts_code": "symbol",
    "name": "name",
    "股票简称": "name",
    "名称": "name",
    "security_name_abbr": "name",
    "report_period": "report_period",
    "report_date": "report_period",
    "报告期": "report_period",
    "report_type": "report_type",
    "报告类型": "report_type",
    "revenue": "revenue",
    "total_operate_income": "revenue",
    "operate_income": "revenue",
    "营业总收入": "revenue",
    "营业收入": "revenue",
    "revenue_yoy": "revenue_yoy",
    "total_operate_income_yoy": "revenue_yoy",
    "营业总收入同比": "revenue_yoy",
    "营业总收入同比增长": "revenue_yoy",
    "营收同比": "revenue_yoy",
    "ystz": "revenue_yoy",
    "net_profit": "net_profit",
    "parent_netprofit": "net_profit",
    "netprofit": "net_profit",
    "归母净利润": "net_profit",
    "净利润": "net_profit",
    "net_profit_yoy": "net_profit_yoy",
    "netprofit_yoy": "net_profit_yoy",
    "归母净利润同比": "net_profit_yoy",
    "归母净利润同比增长": "net_profit_yoy",
    "净利润同比": "net_profit_yoy",
    "sjltz": "net_profit_yoy",
    "roe": "roe",
    "roe_weight": "roe",
    "weightavg_roe": "roe",
    "净资产收益率": "roe",
    "加权净资产收益率": "roe",
    "gross_margin": "gross_margin",
    "xsmll": "gross_margin",
    "销售毛利率": "gross_margin",
    "毛利率": "gross_margin",
    "debt_ratio": "debt_ratio",
    "zcfzl": "debt_ratio",
    "资产负债率": "debt_ratio",
    "eps": "eps",
    "basic_eps": "eps",
    "每股收益": "eps",
    "bps": "bps",
    "每股净资产": "bps",
    "source": "source",
}

_ANNOUNCEMENT_FIELD_ALIASES = {
    "symbol": "symbol",
    "code": "symbol",
    "ts_code": "symbol",
    "title": "title",
    "公告标题": "title",
    "公告名称": "title",
    "headline": "title",
    "date": "publish_date",
    "publish_date": "publish_date",
    "publish_time": "publish_date",
    "datetime": "publish_date",
    "公告日期": "publish_date",
    "发布时间": "publish_date",
    "url": "url",
    "公告链接": "url",
    "链接": "url",
    "source": "source",
    "来源": "source",
    "announcement_type": "announcement_type",
    "公告类型": "announcement_type",
    "announcement_subtype": "announcement_subtype",
    "公告子类型": "announcement_subtype",
}


def map_daily_bar_row(
    row: Mapping[str, Any],
    *,
    default_source: str | None = None,
) -> dict[str, Any]:
    """把原始 row 映射为统一 bars 键名。"""
    mapped = _map_row_with_aliases(row, _DAILY_BAR_FIELD_ALIASES)
    if default_source is not None and "source" not in mapped:
        mapped["source"] = default_source
    return mapped


def map_financial_summary_row(
    row: Mapping[str, Any],
    *,
    default_source: str | None = None,
) -> dict[str, Any]:
    """把原始 row 映射为统一财务摘要键名。"""
    mapped = _map_row_with_aliases(row, _FINANCIAL_FIELD_ALIASES)
    if default_source is not None and "source" not in mapped:
        mapped["source"] = default_source
    return mapped


def map_announcement_row(
    row: Mapping[str, Any],
    *,
    default_source: str | None = None,
) -> dict[str, Any]:
    """把原始 row 映射为统一公告键名。"""
    mapped = _map_row_with_aliases(row, _ANNOUNCEMENT_FIELD_ALIASES)
    if default_source is not None and "source" not in mapped:
        mapped["source"] = default_source
    return mapped


def _map_row_with_aliases(
    row: Mapping[str, Any],
    aliases: Mapping[str, str],
) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for raw_key, raw_value in row.items():
        raw_key_text = str(raw_key).strip()
        canonical_key = aliases.get(raw_key_text.lower())
        if canonical_key is None:
            canonical_key = aliases.get(raw_key_text)
        if canonical_key is None:
            continue
        mapped[canonical_key] = raw_value
    return mapped
