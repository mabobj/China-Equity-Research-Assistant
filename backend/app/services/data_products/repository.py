"""File-backed repository for daily product snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.data_products.base import (
    DataProductCacheEntry,
    build_dataset_version,
    build_default_lineage_metadata,
    infer_provider_used,
    infer_warning_messages,
)


class DataProductRepository:
    """Persist JSON snapshots for daily derived products."""

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def build_params_hash(self, params: dict[str, Any] | None = None) -> str:
        payload = params or {}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def load(
        self,
        *,
        dataset: str,
        symbol: str,
        as_of_date: date,
        params_hash: str,
    ) -> DataProductCacheEntry | None:
        file_path = self._build_file_path(
            dataset=dataset,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
        )
        if not file_path.exists():
            return None
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return DataProductCacheEntry(
            dataset=payload["dataset"],
            symbol=payload["symbol"],
            as_of_date=date.fromisoformat(payload["as_of_date"]),
            params_hash=payload["params_hash"],
            freshness_mode=payload["freshness_mode"],
            source_mode=payload["source_mode"],
            updated_at=datetime.fromisoformat(payload["updated_at"]),
            payload=payload["payload"],
            dataset_version=payload.get("dataset_version"),
            provider_used=payload.get("provider_used"),
            warning_messages=list(payload.get("warning_messages", [])),
            lineage_metadata=payload.get("lineage_metadata"),
        )

    def save(self, entry: DataProductCacheEntry) -> None:
        file_path = self._build_file_path(
            dataset=entry.dataset,
            symbol=entry.symbol,
            as_of_date=entry.as_of_date,
            params_hash=entry.params_hash,
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        lineage_metadata = entry.lineage_metadata
        if hasattr(lineage_metadata, "model_dump"):
            lineage_metadata = lineage_metadata.model_dump(mode="json")
        file_path.write_text(
            json.dumps(
                {
                    "dataset": entry.dataset,
                    "symbol": entry.symbol,
                    "as_of_date": entry.as_of_date.isoformat(),
                    "params_hash": entry.params_hash,
                    "freshness_mode": entry.freshness_mode,
                    "source_mode": entry.source_mode,
                    "updated_at": entry.updated_at.isoformat(),
                    "payload": entry.payload,
                    "dataset_version": entry.dataset_version,
                    "provider_used": entry.provider_used,
                    "warning_messages": entry.warning_messages,
                    "lineage_metadata": lineage_metadata,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )

    def create_entry(
        self,
        *,
        dataset: str,
        symbol: str,
        as_of_date: date,
        params_hash: str,
        freshness_mode: str,
        source_mode: str,
        payload: dict[str, object],
        dataset_version: str | None = None,
        provider_used: str | None = None,
        warning_messages: list[str] | None = None,
        lineage_metadata: dict[str, object] | None = None,
    ) -> DataProductCacheEntry:
        updated_at = datetime.now(timezone.utc)
        resolved_dataset_version = dataset_version or build_dataset_version(
            dataset,
            as_of_date,
            symbol,
        )
        resolved_provider_used = provider_used or infer_provider_used(payload)
        resolved_warning_messages = list(warning_messages or infer_warning_messages(payload))
        resolved_lineage_metadata = lineage_metadata or build_default_lineage_metadata(
            dataset=dataset,
            dataset_version=resolved_dataset_version,
            symbol=symbol,
            as_of_date=as_of_date,
            provider_used=resolved_provider_used,
            source_mode=source_mode,
            freshness_mode=freshness_mode,
            updated_at=updated_at,
            warning_messages=resolved_warning_messages,
        )
        return DataProductCacheEntry(
            dataset=dataset,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
            freshness_mode=freshness_mode,
            source_mode=source_mode,
            updated_at=updated_at,
            payload=payload,
            dataset_version=resolved_dataset_version,
            provider_used=resolved_provider_used,
            warning_messages=resolved_warning_messages,
            lineage_metadata=resolved_lineage_metadata,
        )

    def find_by_dataset_version(
        self,
        *,
        dataset: str,
        dataset_version: str,
    ) -> DataProductCacheEntry | None:
        dataset_dir = self._root_dir / dataset
        if not dataset_dir.exists():
            return None
        for file_path in dataset_dir.rglob("*.json"):
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            if payload.get("dataset_version") != dataset_version:
                continue
            return DataProductCacheEntry(
                dataset=payload["dataset"],
                symbol=payload["symbol"],
                as_of_date=date.fromisoformat(payload["as_of_date"]),
                params_hash=payload["params_hash"],
                freshness_mode=payload["freshness_mode"],
                source_mode=payload["source_mode"],
                updated_at=datetime.fromisoformat(payload["updated_at"]),
                payload=payload["payload"],
                dataset_version=payload.get("dataset_version"),
                provider_used=payload.get("provider_used"),
                warning_messages=list(payload.get("warning_messages", [])),
                lineage_metadata=payload.get("lineage_metadata"),
            )
        return None

    def _build_file_path(
        self,
        *,
        dataset: str,
        symbol: str,
        as_of_date: date,
        params_hash: str,
    ) -> Path:
        return (
            self._root_dir
            / dataset
            / as_of_date.isoformat()
            / f"{symbol}-{params_hash}.json"
        )
