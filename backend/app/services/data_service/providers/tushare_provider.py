"""Tushare provider for structured financial summary data."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any, Optional

from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import convert_symbol_for_provider, parse_symbol
from app.services.data_service.providers.base import FINANCIAL_SUMMARY_CAPABILITY


class TushareProvider:
    """Optional structured financial summary provider backed by Tushare."""

    name = "tushare"
    capabilities = (FINANCIAL_SUMMARY_CAPABILITY,)

    def __init__(self, *, token: str) -> None:
        self._token = token.strip()

    def is_available(self) -> bool:
        return bool(self._token) and importlib.util.find_spec("tushare") is not None

    def get_unavailable_reason(self) -> Optional[str]:
        if not self._token:
            return "Tushare token is not configured."
        if importlib.util.find_spec("tushare") is None:
            return "Tushare is not installed or unavailable."
        return None

    def get_stock_financial_summary_raw(self, symbol: str) -> Optional[dict[str, Any]]:
        self._ensure_available()
        parts = parse_symbol(symbol)
        ts = _get_tushare_module()
        try:
            ts.set_token(self._token)
            pro = ts.pro_api()
            income_frame = pro.income(ts_code=convert_symbol_for_provider(symbol, "tushare"))
            indicator_frame = pro.fina_indicator(ts_code=convert_symbol_for_provider(symbol, "tushare"))
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            raise ProviderError("Tushare failed to load financial summary.") from exc

        income_row = _select_latest_tushare_row(income_frame)
        indicator_row = _select_latest_tushare_row(indicator_frame)
        if income_row is None and indicator_row is None:
            return None

        return {
            "symbol": parts.canonical,
            "name": None,
            "income": income_row or {},
            "fina_indicator": indicator_row or {},
            "source": self.name,
        }

    def get_stock_financial_summary(self, symbol: str) -> None:
        """Compatibility shim; service should consume raw payloads."""
        return None

    def _ensure_available(self) -> None:
        if not self.is_available():
            raise ProviderError(self.get_unavailable_reason() or "Tushare is unavailable.")


def _get_tushare_module() -> Any:
    try:
        return importlib.import_module("tushare")
    except Exception as exc:  # pragma: no cover - depends on local env
        raise ProviderError("Tushare is not installed or unavailable.") from exc


def _select_latest_tushare_row(frame: Any) -> Optional[dict[str, Any]]:
    if frame is None:
        return None
    if getattr(frame, "empty", False):
        return None
    rows = frame.to_dict(orient="records")
    if not rows:
        return None

    def _sort_key(row: dict[str, Any]) -> tuple[int, str]:
        end_date = str(row.get("end_date") or row.get("report_period") or "")
        ann_date = str(row.get("ann_date") or "")
        return (1 if end_date else 0, f"{end_date}|{ann_date}")

    return sorted(rows, key=_sort_key, reverse=True)[0]
