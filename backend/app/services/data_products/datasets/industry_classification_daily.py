"""行业/板块分类日级数据产品。"""

from __future__ import annotations

from app.schemas.market_context import StockClassificationSnapshot
from app.services.common.text_normalization import normalize_display_text
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import INDUSTRY_CLASSIFICATION_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_products.repository import DataProductRepository
from app.services.data_service.market_data_service import MarketDataService
from app.services.data_service.normalize import infer_board_from_symbol

_PRIMARY_BENCHMARK_BY_BOARD = {
    "main_board": ("000300.SH", "沪深300"),
    "chinext": ("399006.SZ", "创业板指"),
    "star_market": ("000688.SH", "科创50"),
}


class IndustryClassificationDailyDataset:
    """按日保存单票的行业/板块分类结果。"""

    def __init__(
        self,
        *,
        repository: DataProductRepository,
        market_data_service: MarketDataService,
    ) -> None:
        self._repository = repository
        self._market_data_service = market_data_service

    def get(
        self,
        symbol: str,
        *,
        as_of_date=None,
        force_refresh: bool = False,
    ) -> DataProductResult[StockClassificationSnapshot]:
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        params_hash = self._repository.build_params_hash({})
        if not force_refresh:
            cached = self._repository.load(
                dataset=INDUSTRY_CLASSIFICATION_DAILY,
                symbol=symbol,
                as_of_date=resolved_as_of_date,
                params_hash=params_hash,
            )
            if cached is not None:
                payload = StockClassificationSnapshot.model_validate(cached.payload)
                return DataProductResult(
                    dataset=INDUSTRY_CLASSIFICATION_DAILY,
                    symbol=symbol,
                    as_of_date=cached.as_of_date,
                    payload=payload,
                    freshness_mode="cache_hit",
                    source_mode="snapshot",
                    updated_at=cached.updated_at,
                    dataset_version=cached.dataset_version,
                    provider_used=cached.provider_used,
                    warning_messages=cached.warning_messages,
                    lineage_metadata=cached.lineage_metadata,
                )

        profile = self._market_data_service.get_stock_profile(symbol)
        board = infer_board_from_symbol(symbol)
        industry = normalize_display_text(profile.industry) or profile.industry
        warning_messages: list[str] = []
        quality_status = "ok"
        if industry is None:
            quality_status = "warning"
            warning_messages.append("industry_missing_use_board_only")

        benchmark_symbol, benchmark_name = _PRIMARY_BENCHMARK_BY_BOARD.get(
            board,
            ("000300.SH", "沪深300"),
        )
        payload = StockClassificationSnapshot(
            symbol=profile.symbol,
            name=normalize_display_text(profile.name) or profile.name,
            exchange=profile.exchange,
            board=board,
            industry=industry,
            as_of_date=resolved_as_of_date,
            quality_status=quality_status,
            warning_messages=warning_messages,
            source_mode="derived_from_profile",
            freshness_mode="snapshot",
            primary_benchmark_symbol=benchmark_symbol,
            primary_benchmark_name=benchmark_name,
        )
        entry = self._repository.create_entry(
            dataset=INDUSTRY_CLASSIFICATION_DAILY,
            symbol=symbol,
            as_of_date=resolved_as_of_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode="snapshot",
            payload=payload.model_dump(mode="json"),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=INDUSTRY_CLASSIFICATION_DAILY,
            symbol=symbol,
            as_of_date=resolved_as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=entry.updated_at,
            dataset_version=entry.dataset_version,
            provider_used=entry.provider_used,
            warning_messages=entry.warning_messages,
            lineage_metadata=entry.lineage_metadata,
        )
