"""选股器股票池加载。"""

from typing import Optional

from app.schemas.market_data import UniverseItem
from app.services.data_service.market_data_service import MarketDataService
from app.services.screener_service.filters import is_common_a_share_symbol, is_special_treatment_name


def load_scan_universe(
    market_data_service: MarketDataService,
    max_symbols: Optional[int] = None,
) -> tuple[int, list[UniverseItem]]:
    """加载并预过滤基础股票池。"""
    universe_response = market_data_service.get_stock_universe()
    total_symbols = universe_response.count

    filtered_items: list[UniverseItem] = []
    for item in universe_response.items:
        if not is_common_a_share_symbol(item.symbol):
            continue
        if is_special_treatment_name(item.name):
            continue
        filtered_items.append(item)

    # 固定排序，避免同参数多次运行时扫描集合漂移。
    filtered_items.sort(key=lambda item: item.symbol)

    if max_symbols is not None:
        filtered_items = filtered_items[: max(max_symbols, 0)]

    return total_symbols, filtered_items
