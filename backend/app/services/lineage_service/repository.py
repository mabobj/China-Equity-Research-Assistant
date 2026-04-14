"""Local repository for lineage metadata records."""

from __future__ import annotations

from datetime import date, datetime
import json
import sqlite3
from pathlib import Path

from app.schemas.lineage import LineageMetadata


class LineageRepository:
    """Persist and query lineage metadata in a lightweight SQLite store."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save(self, metadata: LineageMetadata) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO dataset_lineage_records (
                    dataset,
                    dataset_version,
                    symbol,
                    as_of_date,
                    schema_version,
                    generated_at,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dataset, dataset_version) DO UPDATE SET
                    symbol = excluded.symbol,
                    as_of_date = excluded.as_of_date,
                    schema_version = excluded.schema_version,
                    generated_at = excluded.generated_at,
                    payload_json = excluded.payload_json
                """,
                [
                    metadata.dataset,
                    metadata.dataset_version,
                    metadata.symbol,
                    metadata.as_of_date.isoformat(),
                    metadata.schema_version,
                    metadata.generated_at.isoformat(),
                    json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False),
                ],
            )

    def get(self, *, dataset: str, dataset_version: str) -> LineageMetadata | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM dataset_lineage_records
                WHERE dataset = ? AND dataset_version = ?
                """,
                [dataset, dataset_version],
            ).fetchone()
        if row is None:
            return None
        return LineageMetadata.model_validate(json.loads(str(row[0])))

    def list(
        self,
        *,
        dataset: str | None = None,
        symbol: str | None = None,
        as_of_date: date | None = None,
        limit: int = 50,
    ) -> list[LineageMetadata]:
        query = """
            SELECT payload_json
            FROM dataset_lineage_records
            WHERE 1 = 1
        """
        params: list[object] = []
        if dataset:
            query += " AND dataset = ?"
            params.append(dataset)
        if symbol:
            query += " AND (symbol = ? OR symbol IS NULL)"
            params.append(symbol)
        if as_of_date:
            query += " AND as_of_date = ?"
            params.append(as_of_date.isoformat())
        query += " ORDER BY generated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [LineageMetadata.model_validate(json.loads(str(row[0]))) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_lineage_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    symbol TEXT,
                    as_of_date TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    generated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(dataset, dataset_version)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_lineage_dataset_generated_at
                ON dataset_lineage_records(dataset, generated_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_lineage_symbol_as_of_date
                ON dataset_lineage_records(symbol, as_of_date DESC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection
