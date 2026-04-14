"""Debate review daily product."""

from __future__ import annotations

from datetime import date

from app.schemas.debate import DebateReviewReport
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import DEBATE_REVIEW_DAILY
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.data_products.repository import DataProductRepository


class DebateReviewDailyDataset:
    """Persist and reuse debate reviews by symbol/day and runtime variant."""

    def __init__(self, repository: DataProductRepository) -> None:
        self._repository = repository

    def load(
        self,
        symbol: str,
        *,
        as_of_date: date,
        variant: str = "rule_based",
    ) -> DataProductResult[DebateReviewReport] | None:
        params_hash = self._repository.build_params_hash({"variant": variant})
        cached = self._repository.load(
            dataset=DEBATE_REVIEW_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
        )
        if cached is None:
            return None
        payload = DebateReviewReport.model_validate(cached.payload)
        return DataProductResult(
            dataset=DEBATE_REVIEW_DAILY,
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
        payload: DebateReviewReport,
        *,
        variant: str = "rule_based",
    ) -> DataProductResult[DebateReviewReport]:
        as_of_date = resolve_daily_analysis_as_of_date(payload.as_of_date)
        params_hash = self._repository.build_params_hash({"variant": variant})
        entry = self._repository.create_entry(
            dataset=DEBATE_REVIEW_DAILY,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode="snapshot",
            payload=payload.model_dump(mode="json"),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=DEBATE_REVIEW_DAILY,
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
