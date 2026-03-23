"""CNINFO provider，用于公告列表拉取。"""

from datetime import date, datetime
from functools import lru_cache
import math
from typing import Any, Optional

import httpx

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary
from app.services.data_service.exceptions import ProviderError
from app.services.data_service.normalize import convert_symbol_for_provider, parse_symbol

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
    """基于 CNINFO 的公告 provider。"""

    name = "cninfo"

    def is_available(self) -> bool:
        """CNINFO provider 不依赖额外三方包，默认可用。"""
        return True

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """当前 provider 不负责股票基础信息。"""
        return None

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        """当前 provider 不负责日线行情。"""
        return []

    def get_stock_universe(self) -> list[UniverseItem]:
        """当前 provider 不负责基础股票池。"""
        return []

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        """获取单只股票公告列表。"""
        parts = parse_symbol(symbol)
        stock_code = convert_symbol_for_provider(symbol, "cninfo")
        org_id = self._get_org_id(stock_code)
        total_pages = max(1, math.ceil(limit / 30))
        items: list[AnnouncementItem] = []

        try:
            with httpx.Client(
                headers=_CNINFO_HEADERS,
                follow_redirects=True,
                timeout=15.0,
            ) as client:
                for page_num in range(1, total_pages + 1):
                    payload = {
                        "pageNum": str(page_num),
                        "pageSize": str(min(max(limit, 1), 30)),
                        "column": "szse",
                        "tabName": "fulltext",
                        "plate": "",
                        "stock": "{code},{org_id}".format(
                            code=stock_code,
                            org_id=org_id,
                        ),
                        "searchkey": "",
                        "secid": "",
                        "category": "",
                        "trade": "",
                        "seDate": "{start}~{end}".format(
                            start=start_date.isoformat(),
                            end=end_date.isoformat(),
                        ),
                        "sortName": "",
                        "sortType": "",
                        "isHLtitle": "true",
                    }
                    response = client.post(
                        "{base}/new/hisAnnouncement/query".format(
                            base=_CNINFO_BASE_URL,
                        ),
                        data=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    for raw_item in data.get("announcements", []):
                        mapped_item = self._map_announcement_item(
                            parts.canonical,
                            stock_code,
                            raw_item,
                        )
                        if mapped_item is not None:
                            items.append(mapped_item)
                        if len(items) >= limit:
                            return items[:limit]
        except httpx.HTTPError as exc:  # pragma: no cover - 依赖外部网络
            raise ProviderError("CNINFO failed to load announcements.") from exc
        except ValueError as exc:  # pragma: no cover - 依赖外部响应
            raise ProviderError("CNINFO returned an invalid announcements payload.") from exc

        return items[:limit]

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        """当前 provider 不负责财务摘要。"""
        return None

    def _get_org_id(self, stock_code: str) -> str:
        """获取股票对应的 CNINFO 机构编号。"""
        org_map = _get_cninfo_org_id_map()
        org_id = org_map.get(stock_code)
        if org_id is None:
            raise ProviderError(
                "CNINFO could not resolve orgId for symbol {symbol}.".format(
                    symbol=stock_code,
                ),
            )
        return org_id

    def _map_announcement_item(
        self,
        symbol: str,
        stock_code: str,
        raw_item: dict[str, Any],
    ) -> Optional[AnnouncementItem]:
        """将 CNINFO 原始公告记录映射为统一结构。"""
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
            or "未分类"
        )
        url = (
            "{base}/new/disclosure/detail?stockCode={stock_code}"
            "&announcementId={announcement_id}&orgId={org_id}"
            "&announcementTime={announcement_time}"
        ).format(
            base=_CNINFO_BASE_URL,
            stock_code=stock_code,
            announcement_id=announcement_id,
            org_id=org_id,
            announcement_time=publish_date.isoformat(),
        )
        return AnnouncementItem(
            symbol=symbol,
            title=title,
            publish_date=publish_date,
            announcement_type=announcement_type,
            source=self.name,
            url=url,
        )


@lru_cache
def _get_cninfo_org_id_map() -> dict[str, str]:
    """缓存股票代码到 CNINFO orgId 的映射。"""
    try:
        with httpx.Client(
            headers=_CNINFO_HEADERS,
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            response = client.get("{base}/new/data/szse_stock.json".format(base=_CNINFO_BASE_URL))
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:  # pragma: no cover - 依赖外部网络
        raise ProviderError("CNINFO failed to load stock metadata.") from exc
    except ValueError as exc:  # pragma: no cover - 依赖外部响应
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
    """解析 CNINFO 公告时间字段。"""
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
    """将 provider 字段转换为清洗后的字符串。"""
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    return text
