"""Helpers for lineage metadata construction."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.schemas.lineage import LineageDependency, LineageMetadata, LineageSourceRef


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_source_ref(
    *,
    dataset: str,
    dataset_version: str,
    as_of_date: date,
    symbol: str | None = None,
    provider_used: str | None = None,
    source_mode: str | None = None,
    freshness_mode: str | None = None,
    updated_at: datetime | None = None,
) -> LineageSourceRef:
    return LineageSourceRef(
        dataset=dataset,
        dataset_version=dataset_version,
        symbol=symbol,
        as_of_date=as_of_date,
        provider_used=provider_used,
        source_mode=source_mode,
        freshness_mode=freshness_mode,
        updated_at=updated_at,
    )


def build_dependency(
    role: str,
    source_ref: LineageSourceRef,
) -> LineageDependency:
    return LineageDependency(role=role, source_ref=source_ref)


def build_lineage_metadata(
    *,
    dataset: str,
    dataset_version: str,
    as_of_date: date,
    symbol: str | None = None,
    dependencies: list[LineageDependency] | None = None,
    warning_messages: list[str] | None = None,
    generated_at: datetime | None = None,
) -> LineageMetadata:
    return LineageMetadata(
        dataset=dataset,
        dataset_version=dataset_version,
        generated_at=generated_at or utcnow(),
        as_of_date=as_of_date,
        symbol=symbol,
        dependencies=list(dependencies or []),
        warning_messages=list(warning_messages or []),
    )
