"""BaoStock provider，负责基础行情补充。"""

from contextlib import contextmanager
from datetime import date, datetime
import importlib
import importlib.util
import math
from threading import RLock
from typing import Any, Iterator, Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import (
    canonical_symbol_from_provider_symbol,
    convert_symbol_for_provider,
    parse_symbol,
)

_BAOSTOCK_LOCK = RLock()


class BaostockProvider:
    """基于 BaoStock 的 provider。"""

    name = "baostock"

    def __init__(self) -> None:
        self._session_depth = 0
        self._logged_in_module: Optional[Any] = None

    def is_available(self) -> bool:
        """返回 BaoStock 是否可导入。"""
        return importlib.util.find_spec("baostock") is not None

    @contextmanager
    def session_scope(self) -> Iterator[None]:
        """在一段批量查询中复用同一个 BaoStock 会话。"""
        self._ensure_available()
        bs = _get_baostock_module()

        with _BAOSTOCK_LOCK:
            should_login = self._session_depth == 0
            if should_login:
                _login_baostock(bs)
                self._logged_in_module = bs
            self._session_depth += 1

            try:
                yield
            finally:
                self._session_depth -= 1
                if self._session_depth == 0:
                    try:
                        if self._logged_in_module is not None:
                            self._logged_in_module.logout()
                    finally:
                        self._logged_in_module = None

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """获取单只股票基础信息。"""
        self._ensure_available()
        parts = parse_symbol(symbol)
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with self.session_scope():
                bs = self._get_active_module()
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
        parts = parse_symbol(symbol)
        baostock_symbol = convert_symbol_for_provider(symbol, "baostock")

        try:
            with self.session_scope():
                bs = self._get_active_module()
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

        try:
            with self.session_scope():
                bs = self._get_active_module()
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

    def _get_active_module(self) -> Any:
        """返回当前已登录的 BaoStock 模块。"""
        if self._logged_in_module is None:
            raise ProviderError("BaoStock session is not active.")
        return self._logged_in_module


def _get_baostock_module() -> Any:
    """按需导入并返回 BaoStock 模块。"""
    try:
        return importlib.import_module("baostock")
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise ProviderError("BaoStock is not installed or unavailable.") from exc


def _login_baostock(baostock_module: Any) -> None:
    """登录 BaoStock。"""
    login_result = baostock_module.login()
    if getattr(login_result, "error_code", "") != "0":
        raise ProviderError("BaoStock login failed.")


def _result_to_rows(result: Any) -> list[dict[str, Any]]:
    """把 BaoStock 结果集转换为字典列表。"""
    if result is None:
        raise ProviderError("BaoStock returned an empty query result object.")

    if getattr(result, "error_code", "") != "0":
        raise ProviderError("BaoStock query failed.")

    rows = []
    raw_fields = getattr(result, "fields", [])
    if raw_fields is None:
        return rows

    fields = list(raw_fields)
    next_method = getattr(result, "next", None)
    if not callable(next_method):
        raise ProviderError("BaoStock returned an unexpected query result format.")

    while next_method():
        values = result.get_row_data()
        if values is None:
            continue
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
    """把 BaoStock 状态码映射为可读标签。"""
    text = _as_optional_string(value)
    if text is None:
        return None
    return "active" if text == "1" else "inactive"


def _as_optional_string(value: Any) -> Optional[str]:
    """把 provider 字段转换为清洗后的字符串。"""
    if _is_missing(value):
        return None

    text = str(value).strip()
    if text == "":
        return None
    return text


def _as_optional_float(value: Any) -> Optional[float]:
    """把 provider 字段转换为浮点数。"""
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
