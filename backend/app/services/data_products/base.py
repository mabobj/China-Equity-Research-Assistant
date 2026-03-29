"""Core objects for daily data products."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Generic, TypeVar

from app.schemas.evidence import EvidenceBundle

T = TypeVar("T")


@dataclass(frozen=True)
class DataProductResult(Generic[T]):
    """One resolved daily data product."""

    dataset: str
    symbol: str
    as_of_date: date
    payload: T
    freshness_mode: str
    source_mode: str
    updated_at: datetime
    evidence_bundle: EvidenceBundle | None = None


@dataclass(frozen=True)
class DataProductCacheEntry:
    """Serialized entry persisted in the file repository."""

    dataset: str
    symbol: str
    as_of_date: date
    params_hash: str
    freshness_mode: str
    source_mode: str
    updated_at: datetime
    payload: dict[str, object]
