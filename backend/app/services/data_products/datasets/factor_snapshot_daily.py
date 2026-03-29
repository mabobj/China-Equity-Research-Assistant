"""Factor snapshot daily product."""

from __future__ import annotations

from app.schemas.factor import FactorSnapshot
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import FACTOR_SNAPSHOT_DAILY
from app.services.data_products.freshness import resolve_last_closed_trading_day
from app.services.data_products.repository import DataProductRepository


class FactorSnapshotDailyDataset:
    """Persist and reuse factor snapshot by day."""

    def __init__(self, repository: DataProductRepository) -> None:
        self._repository = repository

    def load(
        self,
        symbol: str,
        *,
        as_of_date,
    ) -> DataProductResult[FactorSnapshot] | None:
        params_hash = self._repository.build_params_hash({})
        cached = self._repository.load(
            dataset=FACTOR_SNAPSHOT_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
        )
        if cached is None:
            return None
        payload = FactorSnapshot.model_validate(cached.payload)
        return DataProductResult(
            dataset=FACTOR_SNAPSHOT_DAILY,
            symbol=symbol,
            as_of_date=cached.as_of_date,
            payload=payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=cached.updated_at,
        )

    def save(self, symbol: str, payload: FactorSnapshot) -> DataProductResult[FactorSnapshot]:
        as_of_date = payload.as_of_date or resolve_last_closed_trading_day()
        params_hash = self._repository.build_params_hash({})
        entry = self._repository.create_entry(
            dataset=FACTOR_SNAPSHOT_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode="snapshot",
            payload=payload.model_dump(mode="json"),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=FACTOR_SNAPSHOT_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=entry.updated_at,
        )
