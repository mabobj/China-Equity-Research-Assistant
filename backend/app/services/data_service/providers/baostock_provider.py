"""BaoStock provider，负责基础行情补充。"""

from datetime import date, datetime
import importlib
import importlib.util
import math
from typing import Any, Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import (
    canonical_symbol_from_provider_symbol,
    convert_symbol_for_provider,
    parse_symbol,
)


class BaostockProvider:
    """基于 BaoStock 的 provider。"""

    name = "baostock"

    def is_available(self) -> bool:
        """返回 BaoStock 是否可导入。"""
        return importlib.util.find_spec("baostock") is not None

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """获取单只股票基础信息。"""
        self._ensure_available()
        bs = _get_baostock_module()
        parts = parse_symbol(symbol)
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with _BaoStockSession(bs):
                result = bs.query_stock_basic(code=baostock_symbol)
                rows = _result_to_rows(result)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("BaoStock failed to load stock profile.") from exc

        if not rows:
            return None

        row = rows[0]
        return StockProfile(
            symbol=parts.canonical,
            code=parts.code,
            exchange=parts.exchange,
            name=_as_optional_string(row.get("code_name")) or parts.code,
            industry=None,
            list_date=_parse_iso_date(row.get("ipoDate")),
            status=_map_trade_status(row.get("status")),
            total_market_cap=None,
            circulating_market_cap=None,
            source=self.name,
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        """获取单只股票日线行情。"""
        self._ensure_available()
        bs = _get_baostock_module()
        parts = parse_symbol(symbol)
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with _BaoStockSession(bs):
                result = bs.query_history_k_data_plus(
                    code=baostock_symbol,
                    fields="date,open,high,low,close,volume,amount",
                    start_date=_format_baostock_date(start_date),
                    end_date=_format_baostock_date(end_date),
                    frequency="d",
                    adjustflag="3",
                )
                rows = _result_to_rows(result)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("BaoStock failed to load daily bars.") from exc

        if not rows:
            return []

        bars: list[DailyBar] = []
        for row in rows:
            trade_date = _parse_iso_date(row.get("date"))
            if trade_date is None:
                continue

            bars.append(
                DailyBar(
                    symbol=parts.canonical,
                    trade_date=trade_date,
                    open=_as_optional_float(row.get("open")),
                    high=_as_optional_float(row.get("high")),
                    low=_as_optional_float(row.get("low")),
                    close=_as_optional_float(row.get("close")),
                    volume=_as_optional_float(row.get("volume")),
                    amount=_as_optional_float(row.get("amount")),
                    source=self.name,
                ),
            )

        return bars

    def get_stock_universe(self) -> list[UniverseItem]:
        """获取基础股票池。"""
        self._ensure_available()
        bs = _get_baostock_module()

        try:
            with _BaoStockSession(bs):
                result = bs.query_all_stock(day="")
                rows = _result_to_rows(result)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("BaoStock failed to load stock universe.") from exc

        if not rows:
            return []

        items: list[UniverseItem] = []
        for row in rows:
            raw_code = _as_optional_string(row.get("code"))
            name = _as_optional_string(row.get("code_name"))
            if raw_code is None or name is None:
                continue

            try:
                canonical_symbol = canonical_symbol_from_provider_symbol(raw_code)
                parts = parse_symbol(canonical_symbol)
            except Exception:
                continue

            items.append(
                UniverseItem(
                    symbol=parts.canonical,
                    code=parts.code,
                    exchange=parts.exchange,
                    name=name,
                    status="active",
                    source=self.name,
                ),
            )

        return items

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        """当前 provider 不负责公告列表。"""
        return []

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        """当前 provider 不负责财务摘要。"""
        return None

    def _ensure_available(self) -> None:
        """在 BaoStock 不可用时抛出统一错误。"""
        if not self.is_available():
            raise ProviderError("BaoStock is not installed or unavailable.")


class _BaoStockSession:
    """BaoStock 登录上下文管理器。"""

    def __init__(self, baostock_module: Any) -> None:
        self._baostock_module = baostock_module

    def __enter__(self) -> "_BaoStockSession":
        login_result = self._baostock_module.login()
        if getattr(login_result, "error_code", "") != "0":
            raise ProviderError("BaoStock login failed.")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._baostock_module.logout()


def _get_baostock_module() -> Any:
    """按需导入并返回 BaoStock 模块。"""
    try:
        return importlib.import_module("baostock")
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise ProviderError("BaoStock is not installed or unavailable.") from exc


def _result_to_rows(result: Any) -> list[dict[str, Any]]:
    """将 BaoStock 结果集转换为字典列表。"""
    if getattr(result, "error_code", "") != "0":
        raise ProviderError("BaoStock query failed.")

    rows = []
    fields = list(getattr(result, "fields", []))
    while result.next():
        values = result.get_row_data()
        rows.append(dict(zip(fields, values)))

    return rows


def _format_baostock_date(value: Optional[date]) -> str:
    """格式化 BaoStock 查询日期。"""
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")


def _parse_iso_date(value: Any) -> Optional[date]:
    """解析 ISO 日期字符串。"""
    text = _as_optional_string(value)
    if text is None:
        return None

    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _map_trade_status(value: Any) -> Optional[str]:
    """将 BaoStock 状态码映射为可读标签。"""
    text = _as_optional_string(value)
    if text is None:
        return None
    return "active" if text == "1" else "inactive"


def _as_optional_string(value: Any) -> Optional[str]:
    """将 provider 字段转换为清洗后的字符串。"""
    if _is_missing(value):
        return None

    text = str(value).strip()
    if text == "":
        return None
    return text


def _as_optional_float(value: Any) -> Optional[float]:
    """将 provider 字段转换为浮点数。"""
    if _is_missing(value) or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_missing(value: Any) -> bool:
    """判断 provider 字段是否应视为缺失值。"""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False
