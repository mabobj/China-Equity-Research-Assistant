"""CNINFO provider for announcements and periodic report indexes."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any, Optional

import httpx

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import (
    AnnouncementItem,
    FinancialReportIndexItem,
    FinancialSummary,
)
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import (
    convert_symbol_for_provider,
    normalize_financial_report_period,
    normalize_financial_report_type,
    parse_symbol,
)
from app.services.data_service.providers.base import (
    ANNOUNCEMENT_CAPABILITY,
    FINANCIAL_REPORT_INDEX_CAPABILITY,
)

_CNINFO_BASE_URL = "https://www.cninfo.com.cn"
_CNINFO_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": _CNINFO_BASE_URL,
    "Referer": (
        "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch"
        "?url=disclosure/list/search"
    ),
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}


class CninfoProvider:
    """Provider backed by the official CNINFO disclosure index."""

    name = "cninfo"
    capabilities = (ANNOUNCEMENT_CAPABILITY, FINANCIAL_REPORT_INDEX_CAPABILITY)

    def is_available(self) -> bool:
        return True

    def get_unavailable_reason(self) -> Optional[str]:
        return None

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        return None

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        return []

    def get_stock_universe(self) -> list[UniverseItem]:
        return []

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        parts = parse_symbol(symbol)
        stock_code = convert_symbol_for_provider(symbol, "cninfo")
        org_id = self._get_org_id(stock_code)
        rows = self._query_announcements(
            stock_code=stock_code,
            org_id=org_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            category="",
            searchkey="",
        )

        items: list[AnnouncementItem] = []
        for raw_item in rows:
            mapped = self._map_announcement_item(parts.canonical, stock_code, raw_item)
            if mapped is not None:
                items.append(mapped)
        return items[: max(limit, 1)]

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        return None

    def get_financial_report_indexes(
        self,
        symbol: str,
        limit: int = 20,
    ) -> list[FinancialReportIndexItem]:
        parts = parse_symbol(symbol)
        stock_code = convert_symbol_for_provider(symbol, "cninfo")
        org_id = self._get_org_id(stock_code)
        end_date = date.today()
        start_date = date(end_date.year - 3, 1, 1)
        rows = self._query_announcements(
            stock_code=stock_code,
            org_id=org_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            category="category_ndbg_szsh;",
            searchkey="年度报告 半年度报告 第一季度报告 第三季度报告",
        )

        items: list[FinancialReportIndexItem] = []
        for raw_item in rows:
            mapped = self._map_financial_report_index_item(
                parts.canonical,
                stock_code,
                raw_item,
            )
            if mapped is not None:
                items.append(mapped)
        return items[: max(limit, 1)]

    def _query_announcements(
        self,
        *,
        stock_code: str,
        org_id: str,
        start_date: date,
        end_date: date,
        limit: int,
        category: str,
        searchkey: str,
    ) -> list[dict[str, Any]]:
        page_size = min(max(limit, 1), 30)
        max_items = max(limit, 1)
        items: list[dict[str, Any]] = []
        try:
            with httpx.Client(
                headers=_CNINFO_HEADERS,
                follow_redirects=True,
                timeout=15.0,
            ) as client:
                page_num = 1
                while len(items) < max_items:
                    payload = {
                        "pageNum": str(page_num),
                        "pageSize": str(page_size),
                        "column": "szse",
                        "tabName": "fulltext",
                        "plate": "",
                        "stock": f"{stock_code},{org_id}",
                        "searchkey": searchkey,
                        "secid": "",
                        "category": category,
                        "trade": "",
                        "seDate": f"{start_date.isoformat()}~{end_date.isoformat()}",
                        "sortName": "",
                        "sortType": "",
                        "isHLtitle": "true",
                    }
                    response = client.post(
                        f"{_CNINFO_BASE_URL}/new/hisAnnouncement/query",
                        data=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    page_items = data.get("announcements", [])
                    if not isinstance(page_items, list) or not page_items:
                        break
                    items.extend(page_items)
                    if len(page_items) < page_size:
                        break
                    page_num += 1
        except httpx.HTTPError as exc:  # pragma: no cover - network
            raise ProviderError("CNINFO failed to load disclosure indexes.") from exc
        except ValueError as exc:  # pragma: no cover - payload
            raise ProviderError("CNINFO returned an invalid disclosure payload.") from exc
        except Exception as exc:  # pragma: no cover - guard
            raise ProviderError("CNINFO failed to parse disclosure payload.") from exc
        return items[:max_items]

    def _get_org_id(self, stock_code: str) -> str:
        org_map = _get_cninfo_org_id_map()
        org_id = org_map.get(stock_code)
        if org_id is None:
            raise ProviderError(
                f"CNINFO could not resolve orgId for symbol {stock_code}."
            )
        return org_id

    def _map_announcement_item(
        self,
        symbol: str,
        stock_code: str,
        raw_item: dict[str, Any],
    ) -> AnnouncementItem | None:
        title = _as_optional_string(raw_item.get("announcementTitle"))
        publish_date = _parse_cninfo_publish_date(raw_item.get("announcementTime"))
        announcement_id = _as_optional_string(raw_item.get("announcementId"))
        org_id = _as_optional_string(raw_item.get("orgId"))
        if title is None or publish_date is None or announcement_id is None or org_id is None:
            return None
        announcement_type = (
            _as_optional_string(raw_item.get("announcementTypeName"))
            or _as_optional_string(raw_item.get("announcementType"))
            or _as_optional_string(raw_item.get("adjunctType"))
            or "other"
        )
        url = (
            f"{_CNINFO_BASE_URL}/new/disclosure/detail?stockCode={stock_code}"
            f"&announcementId={announcement_id}&orgId={org_id}"
            f"&announcementTime={publish_date.isoformat()}"
        )
        return AnnouncementItem(
            symbol=symbol,
            title=title,
            publish_date=publish_date,
            announcement_type=announcement_type,
            source=self.name,
            url=url,
        )

    def _map_financial_report_index_item(
        self,
        symbol: str,
        stock_code: str,
        raw_item: dict[str, Any],
    ) -> FinancialReportIndexItem | None:
        title = _as_optional_string(raw_item.get("announcementTitle"))
        publish_date = _parse_cninfo_publish_date(raw_item.get("announcementTime"))
        announcement_id = _as_optional_string(raw_item.get("announcementId"))
        org_id = _as_optional_string(raw_item.get("orgId"))
        if title is None or publish_date is None or announcement_id is None or org_id is None:
            return None
        report_period = normalize_financial_report_period(title)
        report_type = normalize_financial_report_type(title, report_period=report_period)
        if report_type == "unknown":
            return None
        url = (
            f"{_CNINFO_BASE_URL}/new/disclosure/detail?stockCode={stock_code}"
            f"&announcementId={announcement_id}&orgId={org_id}"
            f"&announcementTime={publish_date.isoformat()}"
        )
        return FinancialReportIndexItem(
            symbol=symbol,
            report_period=report_period,
            report_type=report_type,
            title=title,
            publish_date=publish_date,
            source=self.name,
            url=url,
        )


@lru_cache
def _get_cninfo_org_id_map() -> dict[str, str]:
    try:
        with httpx.Client(
            headers=_CNINFO_HEADERS,
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            response = client.get(f"{_CNINFO_BASE_URL}/new/data/szse_stock.json")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:  # pragma: no cover - network
        raise ProviderError("CNINFO failed to load stock metadata.") from exc
    except ValueError as exc:  # pragma: no cover - payload
        raise ProviderError("CNINFO returned an invalid stock metadata payload.") from exc

    stock_list = data.get("stockList", [])
    org_map: dict[str, str] = {}
    for item in stock_list:
        code = _as_optional_string(item.get("code"))
        org_id = _as_optional_string(item.get("orgId"))
        if code is None or org_id is None:
            continue
        org_map[code] = org_id
    return org_map


def _parse_cninfo_publish_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        text = _as_optional_string(value)
        if text is None:
            return None
        for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue
        return None
    return datetime.fromtimestamp(timestamp / 1000).date()


def _as_optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return text
