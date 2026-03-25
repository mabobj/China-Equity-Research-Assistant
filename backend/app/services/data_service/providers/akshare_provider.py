"""AKShare provider，负责基础行情与财务摘要。"""

from datetime import date, datetime
import importlib
import importlib.util
import math
import random
import time
from typing import Any, Optional

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import convert_symbol_for_provider, parse_symbol
from app.services.data_service.providers.base import (
    DAILY_BAR_CAPABILITY,
    FINANCIAL_SUMMARY_CAPABILITY,
    PROFILE_CAPABILITY,
    UNIVERSE_CAPABILITY,
)


class AkshareProvider:
    """基于 AKShare 的 provider。"""

    name = "akshare"
    capabilities = (
        PROFILE_CAPABILITY,
        DAILY_BAR_CAPABILITY,
        UNIVERSE_CAPABILITY,
        FINANCIAL_SUMMARY_CAPABILITY,
    )

    def __init__(
        self,
        daily_bars_max_retries: int = 4,
        daily_bars_retry_backoff_seconds: float = 0.8,
        daily_bars_retry_jitter_seconds: float = 0.2,
    ) -> None:
        self._daily_bars_max_retries = max(1, daily_bars_max_retries)
        self._daily_bars_retry_backoff_seconds = max(0.0, daily_bars_retry_backoff_seconds)
        self._daily_bars_retry_jitter_seconds = max(0.0, daily_bars_retry_jitter_seconds)

    def is_available(self) -> bool:
        """返回 AKShare 是否可导入。"""
        return importlib.util.find_spec("akshare") is not None

    def get_unavailable_reason(self) -> Optional[str]:
        if self.is_available():
            return None
        return "AKShare is not installed or unavailable."

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """获取单只股票基础信息。"""
        self._ensure_available()
        ak = _get_akshare_module()
        parts = parse_symbol(symbol)
        ak_symbol = convert_symbol_for_provider(symbol, "akshare")

        try:
            frame = ak.stock_individual_info_em(symbol=ak_symbol)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("AKShare failed to load stock profile.") from exc

        if frame is None or frame.empty:
            return None

        if "item" not in frame.columns or "value" not in frame.columns:
            raise ProviderError("AKShare returned an unexpected stock profile format.")

        items = {str(row["item"]): row["value"] for _, row in frame.iterrows()}
        name = _as_optional_string(items.get("股票简称")) or parts.code

        return StockProfile(
            symbol=parts.canonical,
            code=parts.code,
            exchange=parts.exchange,
            name=name,
            industry=_as_optional_string(items.get("行业")),
            list_date=_parse_compact_date(items.get("上市时间")),
            status="active",
            total_market_cap=_as_optional_float(items.get("总市值")),
            circulating_market_cap=_as_optional_float(items.get("流通市值")),
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
        ak = _get_akshare_module()
        parts = parse_symbol(symbol)
        ak_symbol = convert_symbol_for_provider(symbol, "akshare")

        frame = self._load_daily_frame_with_retry(
            ak=ak,
            ak_symbol=ak_symbol,
            start_date=start_date,
            end_date=end_date,
        )

        if frame is None or frame.empty:
            return []

        bars: list[DailyBar] = []
        for _, row in frame.iterrows():
            trade_date = _parse_flexible_date(row.get("日期"))
            if trade_date is None:
                continue

            bars.append(
                DailyBar(
                    symbol=parts.canonical,
                    trade_date=trade_date,
                    open=_as_optional_float(row.get("开盘")),
                    high=_as_optional_float(row.get("最高")),
                    low=_as_optional_float(row.get("最低")),
                    close=_as_optional_float(row.get("收盘")),
                    volume=_as_optional_float(row.get("成交量")),
                    amount=_as_optional_float(row.get("成交额")),
                    source=self.name,
                ),
            )

        return bars

    def _load_daily_frame_with_retry(
        self,
        ak: Any,
        ak_symbol: str,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> Any:
        """日线查询在网络抖动时执行重试。"""
        last_error: Optional[Exception] = None
        attempts_used = 0

        for attempt in range(1, self._daily_bars_max_retries + 1):
            attempts_used = attempt
            try:
                return ak.stock_zh_a_hist(
                    symbol=ak_symbol,
                    period="daily",
                    start_date=_format_akshare_date(start_date),
                    end_date=_format_akshare_date(end_date),
                    adjust="",
                )
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                last_error = exc
                if attempt >= self._daily_bars_max_retries:
                    break
                if not _is_transient_akshare_error(exc):
                    break

                backoff_seconds = (
                    self._daily_bars_retry_backoff_seconds * (2 ** (attempt - 1))
                    + random.uniform(0.0, self._daily_bars_retry_jitter_seconds)
                )
                time.sleep(backoff_seconds)

        if last_error is None:
            raise ProviderError("AKShare failed to load daily bars.")
        raise ProviderError(
            "AKShare failed to load daily bars after {attempts} attempts.".format(
                attempts=attempts_used,
            ),
        ) from last_error

    def get_stock_universe(self) -> list[UniverseItem]:
        """获取基础股票池。"""
        self._ensure_available()
        ak = _get_akshare_module()

        try:
            frame = ak.stock_info_a_code_name()
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("AKShare failed to load stock universe.") from exc

        if frame is None or frame.empty:
            return []

        items: list[UniverseItem] = []
        for _, row in frame.iterrows():
            code = _as_optional_string(row.get("code"))
            name = _as_optional_string(row.get("name"))
            if code is None or name is None:
                continue

            try:
                parts = parse_symbol(code)
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
        """获取单只股票基础财务摘要。"""
        self._ensure_available()
        ak = _get_akshare_module()
        parts = parse_symbol(symbol)

        try:
            frame = ak.stock_financial_analysis_indicator_em(
                symbol=parts.canonical,
                indicator="按报告期",
            )
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("AKShare failed to load financial summary.") from exc

        if frame is None or frame.empty:
            return None

        latest_row = _select_latest_financial_row(frame)
        if latest_row is None:
            return None

        return FinancialSummary(
            symbol=parts.canonical,
            name=_pick_first_string(
                latest_row,
                ["SECURITY_NAME_ABBR", "股票简称", "名称"],
            )
            or parts.code,
            report_period=_parse_flexible_date(
                _pick_first_value(
                    latest_row,
                    ["REPORT_DATE", "REPORT_PERIOD", "报告期"],
                ),
            ),
            revenue=_pick_first_float(
                latest_row,
                [
                    "TOTAL_OPERATE_INCOME",
                    "OPERATE_INCOME",
                    "营业总收入",
                    "营业收入",
                ],
            ),
            revenue_yoy=_pick_first_float(
                latest_row,
                ["YSTZ", "TOTAL_OPERATE_INCOME_YOY", "营业总收入同比增长", "营业收入同比增长"],
            ),
            net_profit=_pick_first_float(
                latest_row,
                ["PARENT_NETPROFIT", "NETPROFIT", "归母净利润", "净利润"],
            ),
            net_profit_yoy=_pick_first_float(
                latest_row,
                ["SJLTZ", "NETPROFIT_YOY", "归母净利润同比增长", "净利润同比增长"],
            ),
            roe=_pick_first_float(
                latest_row,
                ["ROE_WEIGHT", "WEIGHTAVG_ROE", "净资产收益率", "加权净资产收益率"],
            ),
            gross_margin=_pick_first_float(
                latest_row,
                ["XSMLL", "GROSS_MARGIN", "销售毛利率"],
            ),
            debt_ratio=_pick_first_float(
                latest_row,
                ["ZCFZL", "DEBT_RATIO", "资产负债率"],
            ),
            eps=_pick_first_float(
                latest_row,
                ["BASIC_EPS", "EPSJB", "基本每股收益", "每股收益"],
            ),
            bps=_pick_first_float(
                latest_row,
                ["BPS", "每股净资产"],
            ),
            source=self.name,
        )

    def _ensure_available(self) -> None:
        """在 AKShare 不可用时抛出统一错误。"""
        if not self.is_available():
            raise ProviderError("AKShare is not installed or unavailable.")


def _get_akshare_module() -> Any:
    """按需导入并返回 AKShare 模块。"""
    try:
        return importlib.import_module("akshare")
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise ProviderError("AKShare is not installed or unavailable.") from exc


def _format_akshare_date(value: Optional[date]) -> str:
    """格式化 AKShare 查询日期。"""
    if value is None:
        return ""
    return value.strftime("%Y%m%d")


def _parse_compact_date(value: Any) -> Optional[date]:
    """解析类似 20010531 的紧凑日期。"""
    text = _as_optional_string(value)
    if text is None:
        return None

    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_flexible_date(value: Any) -> Optional[date]:
    """解析 provider 日期字段。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = _as_optional_string(value)
    if text is None:
        return None

    for pattern in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue

    return None


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
    if _is_missing(value):
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


def _select_latest_financial_row(frame: Any) -> Optional[dict[str, Any]]:
    """从财务指标表中选出最新报告期记录。"""
    if frame is None or frame.empty:
        return None

    rows: list[dict[str, Any]] = frame.to_dict(orient="records")
    if not rows:
        return None

    def _sort_key(row: dict[str, Any]) -> tuple[int, str]:
        report_date = _parse_flexible_date(
            _pick_first_value(row, ["REPORT_DATE", "REPORT_PERIOD", "报告期"]),
        )
        if report_date is None:
            return (0, "")
        return (1, report_date.isoformat())

    return sorted(rows, key=_sort_key, reverse=True)[0]


def _pick_first_value(row: dict[str, Any], keys: list[str]) -> Any:
    """按候选字段顺序读取首个非空值。"""
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if not _is_missing(value) and value != "":
            return value
    return None


def _pick_first_string(row: dict[str, Any], keys: list[str]) -> Optional[str]:
    """按候选字段顺序读取首个非空字符串。"""
    return _as_optional_string(_pick_first_value(row, keys))


def _pick_first_float(row: dict[str, Any], keys: list[str]) -> Optional[float]:
    """按候选字段顺序读取首个数值。"""
    return _as_optional_float(_pick_first_value(row, keys))


def _is_transient_akshare_error(exc: Exception) -> bool:
    """判断是否属于可重试网络错误。"""
    text = str(exc).lower()
    markers = [
        "remotedisconnected",
        "connection aborted",
        "connectionerror",
        "protocolerror",
        "read timed out",
        "max retries exceeded",
        "temporarily unavailable",
        "connection reset",
    ]
    return any(marker in text for marker in markers)
