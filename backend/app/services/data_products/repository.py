"""File-backed repository for daily product snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.data_products.base import DataProductCacheEntry


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
        )

    def save(self, entry: DataProductCacheEntry) -> None:
        file_path = self._build_file_path(
            dataset=entry.dataset,
            symbol=entry.symbol,
            as_of_date=entry.as_of_date,
            params_hash=entry.params_hash,
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
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
    ) -> DataProductCacheEntry:
        return DataProductCacheEntry(
            dataset=dataset,
            symbol=symbol,
            as_of_date=as_of_date,
            params_hash=params_hash,
            freshness_mode=freshness_mode,
            source_mode=source_mode,
            updated_at=datetime.now(timezone.utc),
            payload=payload,
        )

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
