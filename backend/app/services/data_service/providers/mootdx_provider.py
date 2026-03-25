"""mootdx 本地行情 provider。"""

from __future__ import annotations

from datetime import date, datetime, time
import importlib
import importlib.util
from pathlib import Path
from typing import Any, Optional

from app.schemas.market_data import DailyBar, IntradayBar, TimelinePoint
from app.services.data_service.exceptions import InvalidRequestError, ProviderError
from app.services.data_service.normalize import SymbolParts, parse_symbol
from app.services.data_service.providers.base import (
    DAILY_BAR_CAPABILITY,
    INTRADAY_BAR_CAPABILITY,
    TIMELINE_CAPABILITY,
)

_INTRADAY_FREQUENCY_CONFIG: dict[str, tuple[str, str, int]] = {
    "1m": ("minline", "lc1", 1),
    "5m": ("fzline", "lc5", 5),
}


class MootdxProvider:
    """基于 mootdx 读取本地通达信标准市场行情。"""

    name = "mootdx"
    capabilities = (
        DAILY_BAR_CAPABILITY,
        INTRADAY_BAR_CAPABILITY,
        TIMELINE_CAPABILITY,
    )

    def __init__(self, tdx_dir: Path) -> None:
        self._tdx_dir = tdx_dir.expanduser()

    def is_available(self) -> bool:
        return importlib.util.find_spec("mootdx") is not None and self._tdx_dir.exists()

    def get_unavailable_reason(self) -> Optional[str]:
        reasons: list[str] = []
        if importlib.util.find_spec("mootdx") is None:
            reasons.append("mootdx is not installed in the current Python environment.")
        if not self._tdx_dir.exists():
            reasons.append(
                "MOOTDX_TDX_DIR does not exist: {path}".format(path=self._tdx_dir),
            )
        if not reasons:
            return None
        return " ".join(reasons)

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        parts = self._parse_supported_symbol(symbol)
        self._ensure_local_file(parts, dataset="daily_bars")
        reader = self._get_reader()

        try:
            frame = reader.daily(symbol=parts.code)
        except Exception as exc:  # pragma: no cover - 依赖本地环境
            raise ProviderError("mootdx failed to load daily bars.") from exc

        if frame is None or getattr(frame, "empty", False):
            return []

        bars: list[DailyBar] = []
        rows = _frame_to_records(frame)
        for row in rows:
            trade_date = _parse_row_date(row)
            if trade_date is None:
                continue
            if start_date is not None and trade_date < start_date:
                continue
            if end_date is not None and trade_date > end_date:
                continue
            bars.append(
                DailyBar(
                    symbol=parts.canonical,
                    trade_date=trade_date,
                    open=_pick_float(row, ("open", "OPEN")),
                    high=_pick_float(row, ("high", "HIGH")),
                    low=_pick_float(row, ("low", "LOW")),
                    close=_pick_float(row, ("close", "CLOSE")),
                    volume=_pick_float(row, ("volume", "vol", "VOLUME")),
                    amount=_pick_float(row, ("amount", "amt", "AMOUNT")),
                    source=self.name,
                ),
            )

        return sorted(bars, key=lambda item: item.trade_date)

    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[IntradayBar]:
        parts = self._parse_supported_symbol(symbol)
        normalized_frequency = _normalize_intraday_frequency(frequency)
        _, _, suffix = _INTRADAY_FREQUENCY_CONFIG[normalized_frequency]
        self._ensure_local_file(parts, dataset="intraday_bars", frequency=normalized_frequency)
        reader = self._get_reader()

        minute_method = getattr(reader, "minute", None)
        if minute_method is None:
            raise ProviderError("mootdx reader does not support minute data.")

        try:
            frame = minute_method(symbol=parts.code, suffix=suffix)
        except Exception as exc:  # pragma: no cover - 依赖本地环境
            raise ProviderError("mootdx failed to load intraday bars.") from exc

        if frame is None or getattr(frame, "empty", False):
            return []

        bars: list[IntradayBar] = []
        rows = _frame_to_records(frame)
        for row in rows:
            trade_datetime = _parse_row_datetime(row)
            if trade_datetime is None:
                continue
            if start_datetime is not None and trade_datetime < start_datetime:
                continue
            if end_datetime is not None and trade_datetime > end_datetime:
                continue
            bars.append(
                IntradayBar(
                    symbol=parts.canonical,
                    trade_datetime=trade_datetime,
                    frequency=normalized_frequency,
                    open=_pick_float(row, ("open", "OPEN")),
                    high=_pick_float(row, ("high", "HIGH")),
                    low=_pick_float(row, ("low", "LOW")),
                    close=_pick_float(row, ("close", "CLOSE", "price", "PRICE")),
                    volume=_pick_float(row, ("volume", "vol", "VOLUME")),
                    amount=_pick_float(row, ("amount", "amt", "AMOUNT")),
                    source=self.name,
                ),
            )

        bars = sorted(bars, key=lambda item: item.trade_datetime)
        if limit is not None and limit >= 0:
            return bars[-limit:]
        return bars

    def get_timeline(
        self,
        symbol: str,
        limit: Optional[int] = None,
    ) -> list[TimelinePoint]:
        parts = self._parse_supported_symbol(symbol)
        self._ensure_local_file(parts, dataset="timeline")
        reader = self._get_reader()

        timeline_method = getattr(reader, "fzline", None)
        if timeline_method is None:
            raise ProviderError("mootdx reader does not support timeline data.")

        try:
            frame = timeline_method(symbol=parts.code)
        except Exception as exc:  # pragma: no cover - 依赖本地环境
            raise ProviderError("mootdx failed to load timeline data.") from exc

        if frame is None or getattr(frame, "empty", False):
            return []

        points: list[TimelinePoint] = []
        rows = _frame_to_records(frame)
        latest_trade_date = _detect_latest_trade_date(rows)
        for row in rows:
            row_trade_date = _parse_row_date(row)
            if latest_trade_date is not None and row_trade_date != latest_trade_date:
                continue
            trade_time = _parse_row_time(row)
            if trade_time is None:
                continue
            points.append(
                TimelinePoint(
                    symbol=parts.canonical,
                    trade_time=trade_time,
                    price=_pick_float(row, ("price", "close", "PRICE")),
                    volume=_pick_float(row, ("volume", "vol", "VOLUME")),
                    amount=_pick_float(row, ("amount", "amt", "AMOUNT")),
                    source=self.name,
                ),
            )

        points = sorted(points, key=lambda item: item.trade_time)
        if limit is not None and limit >= 0:
            return points[-limit:]
        return points

    def _parse_supported_symbol(self, symbol: str) -> SymbolParts:
        cleaned = symbol.strip()
        if cleaned == "":
            raise InvalidRequestError("Symbol cannot be empty.")

        upper_symbol = cleaned.upper()
        if upper_symbol.endswith(".BJ") or upper_symbol.startswith("BJ"):
            raise InvalidRequestError(
                "mootdx currently supports only SH/SZ local market symbols. BJ symbols are not supported.",
            )

        parts = parse_symbol(cleaned)
        if parts.exchange not in {"SH", "SZ"}:
            raise InvalidRequestError(
                "mootdx currently supports only SH/SZ local market symbols.",
            )
        return parts

    def _ensure_local_file(
        self,
        parts: SymbolParts,
        *,
        dataset: str,
        frequency: Optional[str] = None,
    ) -> Path:
        relative_path = _build_relative_data_path(parts, dataset=dataset, frequency=frequency)
        local_path = self._tdx_dir / relative_path
        if not local_path.exists():
            raise ProviderError(
                "mootdx local file is missing for {symbol}: {path}".format(
                    symbol=parts.canonical,
                    path=local_path,
                ),
            )
        return local_path

    def _get_reader(self) -> Any:
        unavailable_reason = self.get_unavailable_reason()
        if unavailable_reason is not None:
            raise ProviderError(unavailable_reason)
        try:
            reader_module = importlib.import_module("mootdx.reader")
            reader_factory = getattr(reader_module, "Reader")
            return reader_factory.factory(market="std", tdxdir=str(self._tdx_dir))
        except Exception as exc:  # pragma: no cover - 依赖本地环境
            raise ProviderError("Failed to initialize mootdx reader.") from exc


def _build_relative_data_path(
    parts: SymbolParts,
    *,
    dataset: str,
    frequency: Optional[str] = None,
) -> Path:
    exchange_dir = parts.exchange.lower()
    filename_prefix = "{exchange}{code}".format(
        exchange=exchange_dir,
        code=parts.code,
    )
    if dataset == "daily_bars":
        return Path("vipdoc") / exchange_dir / "lday" / "{name}.day".format(
            name=filename_prefix,
        )
    if dataset == "intraday_bars":
        normalized_frequency = _normalize_intraday_frequency(frequency or "1m")
        subdir, extension, _ = _INTRADAY_FREQUENCY_CONFIG[normalized_frequency]
        return Path("vipdoc") / exchange_dir / subdir / "{name}.{ext}".format(
            name=filename_prefix,
            ext=extension,
        )
    if dataset == "timeline":
        return Path("vipdoc") / exchange_dir / "fzline" / "{name}.lc5".format(
            name=filename_prefix,
        )
    raise InvalidRequestError(
        "Unsupported mootdx local dataset mapping: {dataset}".format(dataset=dataset),
    )


def _normalize_intraday_frequency(frequency: str) -> str:
    cleaned = frequency.strip().lower()
    if cleaned in _INTRADAY_FREQUENCY_CONFIG:
        return cleaned
    raise InvalidRequestError(
        "Unsupported intraday frequency '{frequency}'. Supported values: 1m, 5m.".format(
            frequency=frequency,
        ),
    )


def _frame_to_records(frame: Any) -> list[dict[str, Any]]:
    if hasattr(frame, "reset_index"):
        frame = frame.reset_index()
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    raise ProviderError("mootdx returned an unsupported data structure.")


def _pick_float(row: dict[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _parse_row_date(row: dict[str, Any]) -> Optional[date]:
    for key in ("date", "datetime", "trade_date", "trade_datetime", "index"):
        value = row.get(key)
        parsed = _parse_date_value(value)
        if parsed is not None:
            return parsed
    return None


def _parse_row_datetime(row: dict[str, Any]) -> Optional[datetime]:
    for key in ("datetime", "trade_datetime", "date", "index"):
        value = row.get(key)
        parsed = _parse_datetime_value(value)
        if parsed is not None:
            return parsed

    row_date = _parse_date_value(row.get("date"))
    row_time = _parse_time_value(row.get("time"))
    if row_date is not None and row_time is not None:
        return datetime.combine(row_date, row_time)
    return None


def _parse_row_time(row: dict[str, Any]) -> Optional[time]:
    for key in ("time", "trade_time", "datetime", "date", "index"):
        value = row.get(key)
        parsed = _parse_time_value(value)
        if parsed is not None:
            return parsed
    return None


def _detect_latest_trade_date(rows: list[dict[str, Any]]) -> Optional[date]:
    dates = [parsed for row in rows if (parsed := _parse_row_date(row)) is not None]
    if not dates:
        return None
    return max(dates)


def _parse_date_value(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _parse_datetime_value(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    for pattern in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
    ):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    parsed_date = _parse_date_value(text)
    if parsed_date is not None:
        return datetime.combine(parsed_date, time(0, 0))
    return None


def _parse_time_value(value: Any) -> Optional[time]:
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    if len(text) == 4 and text.isdigit():
        return time(hour=int(text[:2]), minute=int(text[2:]))
    if len(text) == 6 and text.isdigit():
        return time(hour=int(text[:2]), minute=int(text[2:4]), second=int(text[4:]))
    parsed_datetime = _parse_datetime_value(text)
    if parsed_datetime is not None:
        return parsed_datetime.time()
    return None
