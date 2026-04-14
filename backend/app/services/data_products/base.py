"""Core objects for daily data products."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Generic, TypeVar

from app.schemas.evidence import EvidenceBundle
from app.schemas.lineage import LineageDependency, LineageMetadata, LineageSourceRef

T = TypeVar("T")


def build_dataset_version(dataset: str, as_of_date: date, symbol: str | None) -> str:
    """Build a stable dataset version for daily products."""

    normalized_symbol = (symbol or "").strip()
    if normalized_symbol in {"", "__market__", "__global__"}:
        normalized_symbol = "global"
    return f"{dataset}:{as_of_date.isoformat()}:{normalized_symbol}:v1"


def infer_provider_used(payload: object) -> str | None:
    """Infer provider/source from a payload when possible."""

    if isinstance(payload, dict):
        provider_used = payload.get("provider_used")
        if isinstance(provider_used, str) and provider_used.strip() != "":
            return provider_used.strip()
        source = payload.get("source")
        if isinstance(source, str) and source.strip() != "":
            return source.strip()
        items = payload.get("items")
        if isinstance(items, list) and items:
            first_item = items[0]
            if isinstance(first_item, dict):
                item_provider = first_item.get("provider_used")
                if isinstance(item_provider, str) and item_provider.strip() != "":
                    return item_provider.strip()
                item_source = first_item.get("source")
                if isinstance(item_source, str) and item_source.strip() != "":
                    return item_source.strip()

    provider_used = getattr(payload, "provider_used", None)
    if isinstance(provider_used, str) and provider_used.strip() != "":
        return provider_used.strip()

    source = getattr(payload, "source", None)
    if isinstance(source, str) and source.strip() != "":
        return source.strip()

    bars = getattr(payload, "bars", None)
    if isinstance(bars, list) and bars:
        first_bar_source = getattr(bars[0], "source", None)
        if isinstance(first_bar_source, str) and first_bar_source.strip() != "":
            return first_bar_source.strip()

    items = getattr(payload, "items", None)
    if isinstance(items, list) and items:
        first_item = items[0]
        item_provider = getattr(first_item, "provider_used", None)
        if isinstance(item_provider, str) and item_provider.strip() != "":
            return item_provider.strip()
        item_source = getattr(first_item, "source", None)
        if isinstance(item_source, str) and item_source.strip() != "":
            return item_source.strip()

    return None


def infer_warning_messages(payload: object) -> list[str]:
    """Infer warning messages from a payload when present."""

    if isinstance(payload, dict):
        warning_messages = payload.get("warning_messages")
        if isinstance(warning_messages, list):
            return [
                str(message)
                for message in warning_messages
                if str(message).strip() != ""
            ]
        cleaning_warnings = payload.get("cleaning_warnings")
        if isinstance(cleaning_warnings, list):
            return [
                str(message)
                for message in cleaning_warnings
                if str(message).strip() != ""
            ]

    warning_messages = getattr(payload, "warning_messages", None)
    if isinstance(warning_messages, list):
        return [str(message) for message in warning_messages if str(message).strip() != ""]

    cleaning_warnings = getattr(payload, "cleaning_warnings", None)
    if isinstance(cleaning_warnings, list):
        return [
            str(message)
            for message in cleaning_warnings
            if str(message).strip() != ""
        ]

    return []


def build_default_lineage_metadata(
    *,
    dataset: str,
    dataset_version: str,
    symbol: str,
    as_of_date: date,
    provider_used: str | None,
    source_mode: str,
    freshness_mode: str,
    updated_at: datetime,
    warning_messages: list[str],
) -> LineageMetadata:
    """Build a minimal lineage record for one data product."""

    dependencies: list[LineageDependency] = []
    if provider_used:
        dependencies.append(
            LineageDependency(
                role="provider",
                source_ref=LineageSourceRef(
                    dataset="provider_source",
                    dataset_version=f"provider:{provider_used}:v1",
                    symbol=None,
                    as_of_date=as_of_date,
                    provider_used=provider_used,
                    source_mode=source_mode,
                    freshness_mode=freshness_mode,
                    updated_at=updated_at,
                ),
            )
        )
    normalized_symbol = None if symbol in {"", "__market__", "__global__"} else symbol
    return LineageMetadata(
        dataset=dataset,
        dataset_version=dataset_version,
        generated_at=updated_at,
        as_of_date=as_of_date,
        symbol=normalized_symbol,
        dependencies=dependencies,
        warning_messages=warning_messages,
    )


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
    dataset_version: str | None = None
    provider_used: str | None = None
    warning_messages: list[str] = field(default_factory=list)
    lineage_metadata: LineageMetadata | dict[str, object] | None = None

    def __post_init__(self) -> None:
        dataset_version = self.dataset_version or build_dataset_version(
            self.dataset,
            self.as_of_date,
            self.symbol,
        )
        provider_used = self.provider_used or infer_provider_used(self.payload)
        warning_messages = (
            list(self.warning_messages)
            if self.warning_messages
            else infer_warning_messages(self.payload)
        )
        lineage_metadata = self.lineage_metadata
        if isinstance(lineage_metadata, dict):
            lineage_metadata = LineageMetadata.model_validate(lineage_metadata)
        lineage_metadata = lineage_metadata or build_default_lineage_metadata(
            dataset=self.dataset,
            dataset_version=dataset_version,
            symbol=self.symbol,
            as_of_date=self.as_of_date,
            provider_used=provider_used,
            source_mode=self.source_mode,
            freshness_mode=self.freshness_mode,
            updated_at=self.updated_at,
            warning_messages=warning_messages,
        )
        object.__setattr__(self, "dataset_version", dataset_version)
        object.__setattr__(self, "provider_used", provider_used)
        object.__setattr__(self, "warning_messages", warning_messages)
        object.__setattr__(self, "lineage_metadata", lineage_metadata)


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
    dataset_version: str | None = None
    provider_used: str | None = None
    warning_messages: list[str] = field(default_factory=list)
    lineage_metadata: LineageMetadata | dict[str, object] | None = None
