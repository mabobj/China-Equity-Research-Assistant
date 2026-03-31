"""交易与复盘闭环的 SQLite 存储。"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Optional


class TradeReviewStore:
    """单用户场景下的轻量 SQLite 存储。"""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path))
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    technical_score INTEGER NOT NULL,
                    fundamental_score INTEGER NOT NULL,
                    event_score INTEGER NOT NULL,
                    overall_score INTEGER NOT NULL,
                    thesis TEXT NOT NULL,
                    risks_json TEXT NOT NULL,
                    triggers_json TEXT NOT NULL,
                    invalidations_json TEXT NOT NULL,
                    data_quality_summary_json TEXT,
                    confidence_reasons_json TEXT NOT NULL,
                    runtime_mode_requested TEXT,
                    runtime_mode_effective TEXT,
                    source_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_records (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    price REAL,
                    quantity INTEGER,
                    amount REAL,
                    reason_type TEXT NOT NULL,
                    note TEXT,
                    decision_snapshot_id TEXT,
                    strategy_alignment TEXT NOT NULL,
                    alignment_override_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_records (
                    review_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    review_date TEXT NOT NULL,
                    linked_trade_id TEXT,
                    linked_decision_snapshot_id TEXT,
                    outcome_label TEXT NOT NULL,
                    holding_days INTEGER,
                    max_favorable_excursion REAL,
                    max_adverse_excursion REAL,
                    exit_reason TEXT,
                    did_follow_plan TEXT NOT NULL,
                    review_summary TEXT NOT NULL,
                    lesson_tags_json TEXT NOT NULL,
                    warning_messages_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_decision_snapshots_symbol_created ON decision_snapshots(symbol, created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_records_symbol_trade_date ON trade_records(symbol, trade_date DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_records_symbol_review_date ON review_records(symbol, review_date DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_records_snapshot_id ON trade_records(decision_snapshot_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_records_trade_id ON review_records(linked_trade_id)"
            )
            self._ensure_column(
                connection,
                table_name="trade_records",
                column_name="alignment_override_reason",
                definition="TEXT",
            )
            connection.commit()

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        *,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        existing_columns = {
            str(item["name"])
            for item in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}",
        )

    def create_decision_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO decision_snapshots (
                    snapshot_id, symbol, as_of_date, action, confidence,
                    technical_score, fundamental_score, event_score, overall_score,
                    thesis, risks_json, triggers_json, invalidations_json,
                    data_quality_summary_json, confidence_reasons_json,
                    runtime_mode_requested, runtime_mode_effective, source_refs_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["snapshot_id"],
                    payload["symbol"],
                    payload["as_of_date"],
                    payload["action"],
                    payload["confidence"],
                    payload["technical_score"],
                    payload["fundamental_score"],
                    payload["event_score"],
                    payload["overall_score"],
                    payload["thesis"],
                    _dumps(payload["risks"]),
                    _dumps(payload["triggers"]),
                    _dumps(payload["invalidations"]),
                    _dumps(payload.get("data_quality_summary")),
                    _dumps(payload["confidence_reasons"]),
                    payload.get("runtime_mode_requested"),
                    payload.get("runtime_mode_effective"),
                    _dumps(payload["source_refs"]),
                    payload["created_at"],
                ),
            )
            connection.commit()
        return payload

    def get_decision_snapshot(self, snapshot_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM decision_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        return self._map_decision_snapshot_row(row)

    def list_decision_snapshots(
        self,
        *,
        symbol: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM decision_snapshots"
        args: list[Any] = []
        if symbol:
            sql += " WHERE symbol = ?"
            args.append(symbol)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)

        with self._lock, self._connect() as connection:
            rows = connection.execute(sql, tuple(args)).fetchall()
        return [self._map_decision_snapshot_row(row) for row in rows]

    def create_trade_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trade_records (
                    trade_id, symbol, side, trade_date, price, quantity, amount,
                    reason_type, note, decision_snapshot_id, strategy_alignment, alignment_override_reason,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["trade_id"],
                    payload["symbol"],
                    payload["side"],
                    payload["trade_date"],
                    payload.get("price"),
                    payload.get("quantity"),
                    payload.get("amount"),
                    payload["reason_type"],
                    payload.get("note"),
                    payload.get("decision_snapshot_id"),
                    payload["strategy_alignment"],
                    payload.get("alignment_override_reason"),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return payload

    def get_trade_record(self, trade_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM trade_records WHERE trade_id = ?",
                (trade_id,),
            ).fetchone()
        if row is None:
            return None
        return self._map_trade_row(row)

    def list_trade_records(
        self,
        *,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM trade_records WHERE 1=1"
        args: list[Any] = []
        if symbol:
            sql += " AND symbol = ?"
            args.append(symbol)
        if side:
            sql += " AND side = ?"
            args.append(side)
        if from_date is not None:
            sql += " AND trade_date >= ?"
            args.append(_to_iso_datetime(from_date))
        if to_date is not None:
            sql += " AND trade_date <= ?"
            args.append(_to_iso_datetime(to_date))
        sql += " ORDER BY trade_date DESC, created_at DESC LIMIT ?"
        args.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(sql, tuple(args)).fetchall()
        return [self._map_trade_row(row) for row in rows]

    def update_trade_record(self, trade_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not updates:
            return self.get_trade_record(trade_id)

        set_segments: list[str] = []
        args: list[Any] = []
        for key, value in updates.items():
            set_segments.append(f"{key} = ?")
            args.append(value)
        args.append(trade_id)

        sql = "UPDATE trade_records SET {segments} WHERE trade_id = ?".format(
            segments=", ".join(set_segments),
        )
        with self._lock, self._connect() as connection:
            connection.execute(sql, tuple(args))
            connection.commit()
        return self.get_trade_record(trade_id)

    def create_review_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO review_records (
                    review_id, symbol, review_date, linked_trade_id, linked_decision_snapshot_id,
                    outcome_label, holding_days, max_favorable_excursion, max_adverse_excursion,
                    exit_reason, did_follow_plan, review_summary, lesson_tags_json,
                    warning_messages_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["review_id"],
                    payload["symbol"],
                    payload["review_date"],
                    payload.get("linked_trade_id"),
                    payload.get("linked_decision_snapshot_id"),
                    payload["outcome_label"],
                    payload.get("holding_days"),
                    payload.get("max_favorable_excursion"),
                    payload.get("max_adverse_excursion"),
                    payload.get("exit_reason"),
                    payload["did_follow_plan"],
                    payload["review_summary"],
                    _dumps(payload["lesson_tags"]),
                    _dumps(payload["warning_messages"]),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return payload

    def get_review_record(self, review_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM review_records WHERE review_id = ?",
                (review_id,),
            ).fetchone()
        if row is None:
            return None
        return self._map_review_row(row)

    def list_review_records(
        self,
        *,
        symbol: Optional[str] = None,
        outcome_label: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM review_records WHERE 1=1"
        args: list[Any] = []
        if symbol:
            sql += " AND symbol = ?"
            args.append(symbol)
        if outcome_label:
            sql += " AND outcome_label = ?"
            args.append(outcome_label)
        sql += " ORDER BY review_date DESC, created_at DESC LIMIT ?"
        args.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(sql, tuple(args)).fetchall()
        return [self._map_review_row(row) for row in rows]

    def update_review_record(self, review_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not updates:
            return self.get_review_record(review_id)

        set_segments: list[str] = []
        args: list[Any] = []
        for key, value in updates.items():
            set_segments.append(f"{key} = ?")
            if key in {"lesson_tags_json", "warning_messages_json"}:
                args.append(_dumps(value))
            else:
                args.append(value)
        args.append(review_id)
        sql = "UPDATE review_records SET {segments} WHERE review_id = ?".format(
            segments=", ".join(set_segments),
        )
        with self._lock, self._connect() as connection:
            connection.execute(sql, tuple(args))
            connection.commit()
        return self.get_review_record(review_id)

    def _map_decision_snapshot_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "snapshot_id": row["snapshot_id"],
            "symbol": row["symbol"],
            "as_of_date": row["as_of_date"],
            "action": row["action"],
            "confidence": row["confidence"],
            "technical_score": row["technical_score"],
            "fundamental_score": row["fundamental_score"],
            "event_score": row["event_score"],
            "overall_score": row["overall_score"],
            "thesis": row["thesis"],
            "risks": _loads_list(row["risks_json"]),
            "triggers": _loads_list(row["triggers_json"]),
            "invalidations": _loads_list(row["invalidations_json"]),
            "data_quality_summary": _loads_object(row["data_quality_summary_json"]),
            "confidence_reasons": _loads_list(row["confidence_reasons_json"]),
            "runtime_mode_requested": row["runtime_mode_requested"],
            "runtime_mode_effective": row["runtime_mode_effective"],
            "source_refs": _loads_list(row["source_refs_json"]),
            "created_at": row["created_at"],
        }

    def _map_trade_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "trade_id": row["trade_id"],
            "symbol": row["symbol"],
            "side": row["side"],
            "trade_date": row["trade_date"],
            "price": row["price"],
            "quantity": row["quantity"],
            "amount": row["amount"],
            "reason_type": row["reason_type"],
            "note": row["note"],
            "decision_snapshot_id": row["decision_snapshot_id"],
            "strategy_alignment": row["strategy_alignment"],
            "alignment_override_reason": row["alignment_override_reason"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _map_review_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "review_id": row["review_id"],
            "symbol": row["symbol"],
            "review_date": row["review_date"],
            "linked_trade_id": row["linked_trade_id"],
            "linked_decision_snapshot_id": row["linked_decision_snapshot_id"],
            "outcome_label": row["outcome_label"],
            "holding_days": row["holding_days"],
            "max_favorable_excursion": row["max_favorable_excursion"],
            "max_adverse_excursion": row["max_adverse_excursion"],
            "exit_reason": row["exit_reason"],
            "did_follow_plan": row["did_follow_plan"],
            "review_summary": row["review_summary"],
            "lesson_tags": _loads_list(row["lesson_tags_json"]),
            "warning_messages": _loads_list(row["warning_messages_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_iso_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    if isinstance(parsed, list):
        return parsed
    return []


def _loads_object(value: Any) -> Optional[dict[str, Any]]:
    if value in (None, ""):
        return None
    try:
        parsed = json.loads(value)
    except Exception:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)
