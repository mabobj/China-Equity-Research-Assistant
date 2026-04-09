"""tdx-api 本地 HTTP 行情 provider。"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import httpx

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import (
    canonical_symbol_from_provider_symbol,
    convert_symbol_for_provider,
    normalize_symbol,
    parse_provider_date,
    parse_symbol,
)
from app.services.data_service.providers.base import (
    DAILY_BAR_CAPABILITY,
    PROFILE_CAPABILITY,
    UNIVERSE_CAPABILITY,
)


class TdxApiProvider:
    """基于本地 tdx-api 的 provider。"""

    name = "tdx_api"
    capabilities = (
        PROFILE_CAPABILITY,
        DAILY_BAR_CAPABILITY,
        UNIVERSE_CAPABILITY,
    )

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self._base_url)

    def get_unavailable_reason(self) -> Optional[str]:
        if self.is_available():
            return None
        return "TDX_API_BASE_URL is not configured."

    def get_stock_universe(self) -> list[UniverseItem]:
        payload = self._request_json("GET", "/api/stock-codes")
        items: list[UniverseItem] = []
        for row in self._extract_list_payload(payload):
            canonical_symbol = self._extract_canonical_symbol(row)
            if canonical_symbol is None:
                continue
            parts = parse_symbol(canonical_symbol)
            name = self._pick_string(row, "name", "stock_name", "label", "code_name")
            items.append(
                UniverseItem(
                    symbol=parts.canonical,
                    code=parts.code,
                    exchange=parts.exchange,
                    name=name or parts.code,
                    status="active",
                    source=self.name,
                )
            )
        return items

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        canonical_symbol = normalize_symbol(symbol)
        parts = parse_symbol(canonical_symbol)

        try:
            payload = self._request_json(
                "GET",
                "/api/search",
                params={"keyword": convert_symbol_for_provider(canonical_symbol, "tdx_api")},
            )
        except ProviderError:
            return None

        for row in self._extract_list_payload(payload):
            row_symbol = self._extract_canonical_symbol(row)
            if row_symbol != canonical_symbol:
                continue
            return StockProfile(
                symbol=parts.canonical,
                code=parts.code,
                exchange=parts.exchange,
                name=self._pick_string(row, "name", "stock_name", "label", "code_name")
                or parts.code,
                industry=self._pick_string(row, "industry"),
                list_date=parse_provider_date(
                    self._pick_value(row, "list_date", "ipo_date", "listDate"),
                ),
                status="active",
                total_market_cap=self._pick_float(row, "total_market_cap", "totalMarketCap"),
                circulating_market_cap=self._pick_float(
                    row,
                    "circulating_market_cap",
                    "circulatingMarketCap",
                ),
                source=self.name,
            )
        return None

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        canonical_symbol = normalize_symbol(symbol)
        payload = self._request_json(
            "GET",
            "/api/kline",
            params={
                "code": convert_symbol_for_provider(canonical_symbol, "tdx_api"),
                "type": "day",
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        )

        bars: list[DailyBar] = []
        for row in self._extract_list_payload(payload):
            trade_date = parse_provider_date(
                self._pick_value(row, "date", "trade_date", "day"),
            )
            if trade_date is None:
                continue
            bars.append(
                DailyBar(
                    symbol=canonical_symbol,
                    trade_date=trade_date,
                    open=self._pick_float(row, "open", "o"),
                    high=self._pick_float(row, "high", "h"),
                    low=self._pick_float(row, "low", "l"),
                    close=self._pick_float(row, "close", "c"),
                    volume=self._pick_float(row, "volume", "vol"),
                    amount=self._pick_float(row, "amount", "amt"),
                    source=self.name,
                )
            )
        return sorted(bars, key=lambda item: item.trade_date)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        if not self._base_url:
            raise ProviderError("tdx-api base URL is not configured.")
        request_params = {key: value for key, value in (params or {}).items() if value is not None}
        url = "{base}{path}".format(base=self._base_url, path=path)
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.request(method, url, params=request_params)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # pragma: no cover - runtime/network dependent
            raise ProviderError("tdx-api request failed.") from exc

        if isinstance(payload, dict) and "code" in payload:
            code = payload.get("code")
            if code not in {0, "0", None}:
                raise ProviderError(
                    "tdx-api returned an error response: {message}".format(
                        message=payload.get("message") or "unknown error",
                    )
                )
        return payload

    def _extract_list_payload(self, payload: Any) -> list[dict[str, Any]]:
        data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            for key in ("items", "rows", "list"):
                candidate = data.get(key)
                if isinstance(candidate, list):
                    return [row for row in candidate if isinstance(row, dict)]
            return [data]
        return []

    def _extract_canonical_symbol(self, row: dict[str, Any]) -> str | None:
        raw_symbol = self._pick_string(row, "symbol", "code", "stock_code", "secu_code")
        if raw_symbol is None:
            return None
        try:
            return canonical_symbol_from_provider_symbol(raw_symbol)
        except Exception:
            return None

    @staticmethod
    def _pick_value(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row:
                return row[key]
        return None

    @classmethod
    def _pick_string(cls, row: dict[str, Any], *keys: str) -> str | None:
        value = cls._pick_value(row, *keys)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _pick_float(cls, row: dict[str, Any], *keys: str) -> float | None:
        value = cls._pick_value(row, *keys)
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            return None
