"""Screener factor snapshot daily product."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.schemas.screener_factors import ScreenerFactorSnapshot
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import SCREENER_FACTOR_SNAPSHOT_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_products.repository import DataProductRepository

_SCREENER_FACTOR_SNAPSHOT_VERSION = "20260416_cn_v1"


@dataclass(frozen=True)
class ScreenerFactorSnapshotParams:
    workflow_name: str
    max_symbols: int | None
    top_n: int | None
    batch_size: int | None = None
    cursor_start_symbol: str | None = None
    cursor_start_index: int | None = None
    reset_trade_date: str | None = None
    scheme_id: str | None = None
    scheme_version: str | None = None
    scheme_name: str | None = None
    scheme_snapshot_hash: str | None = None
    snapshot_version: str = _SCREENER_FACTOR_SNAPSHOT_VERSION


class ScreenerFactorSnapshotDailyDataset:
    """Persist and reuse per-symbol screener factor snapshots by day and run context."""

    def __init__(self, repository: DataProductRepository) -> None:
        self._repository = repository

    def load(
        self,
        symbol: str,
        *,
        as_of_date: date,
        params: ScreenerFactorSnapshotParams,
    ) -> DataProductResult[ScreenerFactorSnapshot] | None:
        params_hash = self._params_hash(params)
        cached = self._repository.load(
            dataset=SCREENER_FACTOR_SNAPSHOT_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
        )
        if cached is None:
            return None
        payload = ScreenerFactorSnapshot.model_validate(cached.payload)
        return DataProductResult(
            dataset=SCREENER_FACTOR_SNAPSHOT_DAILY,
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
        *,
        params: ScreenerFactorSnapshotParams,
        payload: ScreenerFactorSnapshot,
    ) -> DataProductResult[ScreenerFactorSnapshot]:
        as_of_date = resolve_daily_analysis_as_of_date(payload.as_of_date)
        params_hash = self._params_hash(params)
        entry = self._repository.create_entry(
            dataset=SCREENER_FACTOR_SNAPSHOT_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode="snapshot",
            payload=payload.model_dump(mode="json"),
            dataset_version=payload.dataset_version,
            provider_used=payload.provider_used,
            warning_messages=payload.warning_messages,
            lineage_metadata=(
                payload.lineage_metadata.model_dump(mode="json")
                if payload.lineage_metadata is not None
                else None
            ),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=SCREENER_FACTOR_SNAPSHOT_DAILY,
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

    def _params_hash(self, params: ScreenerFactorSnapshotParams) -> str:
        return self._repository.build_params_hash(
            {
                "workflow_name": params.workflow_name,
                "max_symbols": params.max_symbols,
                "top_n": params.top_n,
                "batch_size": params.batch_size,
                "cursor_start_symbol": params.cursor_start_symbol,
                "cursor_start_index": params.cursor_start_index,
                "reset_trade_date": params.reset_trade_date,
                "scheme_id": params.scheme_id,
                "scheme_version": params.scheme_version,
                "scheme_name": params.scheme_name,
                "scheme_snapshot_hash": params.scheme_snapshot_hash,
                "snapshot_version": params.snapshot_version,
            }
        )
