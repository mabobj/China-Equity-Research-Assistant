"""Strategy plan daily product."""

from __future__ import annotations

from datetime import date

from app.schemas.strategy import StrategyPlan
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import STRATEGY_PLAN_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_products.repository import DataProductRepository


class StrategyPlanDailyDataset:
    """Persist and reuse strategy plans by symbol/day."""

    def __init__(self, repository: DataProductRepository) -> None:
        self._repository = repository

    def load(
        self,
        symbol: str,
        *,
        as_of_date: date,
    ) -> DataProductResult[StrategyPlan] | None:
        params_hash = self._repository.build_params_hash({})
        cached = self._repository.load(
            dataset=STRATEGY_PLAN_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
        )
        if cached is None:
            return None
        payload = StrategyPlan.model_validate(cached.payload)
        return DataProductResult(
            dataset=STRATEGY_PLAN_DAILY,
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

    def save(
        self,
        symbol: str,
        payload: StrategyPlan,
    ) -> DataProductResult[StrategyPlan]:
        as_of_date = resolve_daily_analysis_as_of_date(payload.as_of_date)
        params_hash = self._repository.build_params_hash({})
        entry = self._repository.create_entry(
            dataset=STRATEGY_PLAN_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode="snapshot",
            payload=payload.model_dump(mode="json"),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=STRATEGY_PLAN_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=entry.updated_at,
            dataset_version=entry.dataset_version,
            provider_used=entry.provider_used,
            warning_messages=entry.warning_messages,
            lineage_metadata=entry.lineage_metadata,
        )
