"""Screener snapshot daily product."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.schemas.screener import ScreenerRunResponse
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import SCREENER_SNAPSHOT_DAILY
from app.services.data_products.repository import DataProductRepository


@dataclass(frozen=True)
class ScreenerSnapshotParams:
    workflow_name: str
    max_symbols: int | None
    top_n: int | None
    deep_top_k: int | None = None


class ScreenerSnapshotDailyDataset:
    """Persist and reuse screener run result by day and params."""

    def __init__(self, repository: DataProductRepository) -> None:
        self._repository = repository

    def load(
        self,
        *,
        run_date: date,
        params: ScreenerSnapshotParams,
    ) -> DataProductResult[ScreenerRunResponse] | None:
        params_hash = self._params_hash(params)
        cached = self._repository.load(
            dataset=SCREENER_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
            params_hash=params_hash,
        )
        if cached is None:
            return None
        payload = ScreenerRunResponse.model_validate(cached.payload)
        return DataProductResult(
            dataset=SCREENER_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
            payload=payload,
            freshness_mode="cache_hit",
            source_mode="snapshot",
            updated_at=cached.updated_at,
        )

    def save(
        self,
        *,
        run_date: date,
        params: ScreenerSnapshotParams,
        payload: ScreenerRunResponse,
    ) -> DataProductResult[ScreenerRunResponse]:
        params_hash = self._params_hash(params)
        entry = self._repository.create_entry(
            dataset=SCREENER_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode="snapshot",
            payload=payload.model_dump(mode="json"),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=SCREENER_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=entry.updated_at,
        )

    def _params_hash(self, params: ScreenerSnapshotParams) -> str:
        return self._repository.build_params_hash(
            {
                "workflow_name": params.workflow_name,
                "max_symbols": params.max_symbols,
                "top_n": params.top_n,
                "deep_top_k": params.deep_top_k,
            }
        )
