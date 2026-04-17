"""Screener selection snapshot daily product."""

from __future__ import annotations

from datetime import date

from app.schemas.lineage import LineageMetadata
from app.schemas.screener import ScreenerRunResponse
from app.services.data_products.base import DataProductResult
from app.services.data_products.catalog import SCREENER_SELECTION_SNAPSHOT_DAILY
from app.services.data_products.datasets.screener_snapshot_daily import (
    ScreenerSnapshotParams,
)
from app.services.data_products.repository import DataProductRepository
from app.services.screener_service.texts import normalize_candidate_display_fields


class ScreenerSelectionSnapshotDailyDataset:
    """Persist selection-level screener outputs with explicit lineage metadata."""

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
            dataset=SCREENER_SELECTION_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
            params_hash=params_hash,
        )
        if cached is None:
            return None
        payload = _normalize_screener_payload(
            ScreenerRunResponse.model_validate(cached.payload)
        )
        return DataProductResult(
            dataset=SCREENER_SELECTION_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
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
        *,
        run_date: date,
        params: ScreenerSnapshotParams,
        payload: ScreenerRunResponse,
        lineage_metadata: LineageMetadata | None = None,
    ) -> DataProductResult[ScreenerRunResponse]:
        params_hash = self._params_hash(params)
        normalized_payload = _normalize_screener_payload(payload)
        entry = self._repository.create_entry(
            dataset=SCREENER_SELECTION_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
            params_hash=params_hash,
            freshness_mode="computed",
            source_mode="snapshot",
            payload=normalized_payload.model_dump(mode="json"),
            lineage_metadata=(
                lineage_metadata.model_dump(mode="json")
                if lineage_metadata is not None
                else None
            ),
        )
        self._repository.save(entry)
        return DataProductResult(
            dataset=SCREENER_SELECTION_SNAPSHOT_DAILY,
            symbol=params.workflow_name,
            as_of_date=run_date,
            payload=normalized_payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=entry.updated_at,
            dataset_version=entry.dataset_version,
            provider_used=entry.provider_used,
            warning_messages=entry.warning_messages,
            lineage_metadata=entry.lineage_metadata,
        )

    def _params_hash(self, params: ScreenerSnapshotParams) -> str:
        return self._repository.build_params_hash(
            {
                "workflow_name": params.workflow_name,
                "max_symbols": params.max_symbols,
                "top_n": params.top_n,
                "batch_size": params.batch_size,
                "cursor_start_symbol": params.cursor_start_symbol,
                "cursor_start_index": params.cursor_start_index,
                "reset_trade_date": params.reset_trade_date,
                "deep_top_k": params.deep_top_k,
                "snapshot_version": params.snapshot_version,
            }
        )


def _normalize_screener_payload(payload: ScreenerRunResponse) -> ScreenerRunResponse:
    return payload.model_copy(
        update={
            "buy_candidates": _normalize_candidates(payload.buy_candidates),
            "watch_candidates": _normalize_candidates(payload.watch_candidates),
            "avoid_candidates": _normalize_candidates(payload.avoid_candidates),
            "ready_to_buy_candidates": _normalize_candidates(
                payload.ready_to_buy_candidates
            ),
            "watch_pullback_candidates": _normalize_candidates(
                payload.watch_pullback_candidates
            ),
            "watch_breakout_candidates": _normalize_candidates(
                payload.watch_breakout_candidates
            ),
            "research_only_candidates": _normalize_candidates(
                payload.research_only_candidates
            ),
        }
    )


def _normalize_candidates(candidates):
    normalized = []
    for candidate in candidates:
        display_fields = normalize_candidate_display_fields(
            name=candidate.name,
            list_type=candidate.v2_list_type,
            short_reason=candidate.short_reason,
            headline_verdict=candidate.headline_verdict,
            top_positive_factors=candidate.top_positive_factors,
            top_negative_factors=candidate.top_negative_factors,
            risk_notes=candidate.risk_notes,
            evidence_hints=candidate.evidence_hints,
        )
        short_reason = str(display_fields["short_reason"])
        headline_verdict = str(display_fields["headline_verdict"])
        normalized_name = str(display_fields["name"])
        normalized_positive = list(display_fields["top_positive_factors"])
        normalized_negative = list(display_fields["top_negative_factors"])
        normalized_risks = list(display_fields["risk_notes"])
        normalized_hints = list(display_fields["evidence_hints"])
        if (
            headline_verdict == candidate.headline_verdict
            and short_reason == candidate.short_reason
            and normalized_name == candidate.name
            and normalized_positive == candidate.top_positive_factors
            and normalized_negative == candidate.top_negative_factors
            and normalized_risks == candidate.risk_notes
            and normalized_hints == candidate.evidence_hints
        ):
            normalized.append(candidate)
            continue
        normalized.append(
            candidate.model_copy(
                update={
                    "name": normalized_name,
                    "short_reason": short_reason,
                    "headline_verdict": headline_verdict,
                    "top_positive_factors": normalized_positive,
                    "top_negative_factors": normalized_negative,
                    "risk_notes": normalized_risks,
                    "evidence_hints": normalized_hints,
                }
            )
        )
    return normalized
