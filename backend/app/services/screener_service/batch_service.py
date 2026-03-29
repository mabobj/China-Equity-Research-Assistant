"""初筛批次台账持久化服务。"""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from threading import Lock
from typing import Iterable
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.schemas.screener import (
    ScreenerBatchRecord,
    ScreenerRunResponse,
    ScreenerSymbolResult,
)
from app.services.data_products.freshness import resolve_last_closed_trading_day

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_DEFAULT_RULE_VERSION = "screener_workflow_v1"
_DEFAULT_RULE_SUMMARY = "基于趋势评分、因子快照与风险约束的规则初筛。"


class ScreenerBatchService:
    """管理初筛批次记录和批次结果。"""

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._batch_dir = root_dir / "batches"
        self._result_dir = root_dir / "results"
        self._run_index_dir = root_dir / "run_index"
        self._lock = Lock()
        self._batch_dir.mkdir(parents=True, exist_ok=True)
        self._result_dir.mkdir(parents=True, exist_ok=True)
        self._run_index_dir.mkdir(parents=True, exist_ok=True)

    def create_running_batch(
        self,
        *,
        run_id: str,
        max_symbols: int | None,
        top_n: int | None,
        started_at: datetime,
        trade_date: date | None = None,
        rule_version: str = _DEFAULT_RULE_VERSION,
    ) -> ScreenerBatchRecord:
        resolved_trade_date = trade_date or resolve_screener_trade_date()
        batch_id = self._build_batch_id(resolved_trade_date)
        record = ScreenerBatchRecord(
            batch_id=batch_id,
            trade_date=resolved_trade_date,
            run_id=run_id,
            status="running",
            started_at=started_at,
            finished_at=None,
            universe_size=0,
            scanned_size=0,
            rule_version=rule_version,
            max_symbols=max_symbols,
            top_n=top_n,
        )
        with self._lock:
            self._save_batch_record(record)
            self._save_run_index(run_id=run_id, batch_id=batch_id)
        return record

    def finalize_batch(
        self,
        *,
        run_id: str,
        status: str,
        finished_at: datetime | None,
        final_output: dict | None,
        final_output_summary: dict | None,
        error_message: str | None,
    ) -> ScreenerBatchRecord | None:
        with self._lock:
            batch_id = self._load_batch_id_by_run_id(run_id)
            if batch_id is None:
                return None

            current = self.load_batch(batch_id)
            if current is None:
                return None

            screener_output = self._parse_screener_output(final_output)
            warnings = self._extract_warnings(final_output_summary)
            failure_reason = error_message
            universe_size = current.universe_size
            scanned_size = current.scanned_size
            results: list[ScreenerSymbolResult] = []

            if screener_output is not None:
                universe_size = screener_output.total_symbols
                scanned_size = screener_output.scanned_symbols
                results = self._build_symbol_results(
                    batch_id=batch_id,
                    output=screener_output,
                    calculated_at=finished_at or datetime.now(_SHANGHAI_TZ),
                    rule_version=current.rule_version,
                )

            if status == "failed" and failure_reason is None:
                failure_reason = "初筛工作流执行失败。"

            record = current.model_copy(
                update={
                    "status": "completed" if status == "completed" else "failed",
                    "finished_at": finished_at,
                    "universe_size": universe_size,
                    "scanned_size": scanned_size,
                    "warning_messages": warnings,
                    "failure_reason": failure_reason,
                }
            )
            self._save_batch_record(record)
            self._save_batch_results(batch_id=batch_id, results=results)
            return record

    def get_latest_batch(self) -> ScreenerBatchRecord | None:
        records = self._load_all_batches()
        if not records:
            return None

        completed = [item for item in records if item.status == "completed"]
        if completed:
            return sorted(
                completed,
                key=lambda item: (
                    item.trade_date,
                    item.finished_at or item.started_at,
                    item.started_at,
                ),
                reverse=True,
            )[0]

        return sorted(
            records,
            key=lambda item: (item.started_at, item.trade_date),
            reverse=True,
        )[0]

    def load_batch(self, batch_id: str) -> ScreenerBatchRecord | None:
        file_path = self._batch_file(batch_id)
        if not file_path.exists():
            return None
        return ScreenerBatchRecord.model_validate_json(file_path.read_text(encoding="utf-8"))

    def load_batch_results(self, batch_id: str) -> list[ScreenerSymbolResult]:
        file_path = self._result_file(batch_id)
        if not file_path.exists():
            return []
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return [ScreenerSymbolResult.model_validate(item) for item in payload]

    def load_symbol_result(self, batch_id: str, symbol: str) -> ScreenerSymbolResult | None:
        normalized = symbol.strip().upper()
        for result in self.load_batch_results(batch_id):
            if result.symbol.upper() == normalized:
                return result
        return None

    def find_running_batch(self) -> ScreenerBatchRecord | None:
        records = self._load_all_batches()
        running = [item for item in records if item.status == "running"]
        if not running:
            return None
        return sorted(running, key=lambda item: item.started_at, reverse=True)[0]

    def _load_all_batches(self) -> list[ScreenerBatchRecord]:
        records: list[ScreenerBatchRecord] = []
        for file_path in self._batch_dir.glob("*.json"):
            try:
                records.append(
                    ScreenerBatchRecord.model_validate_json(
                        file_path.read_text(encoding="utf-8")
                    )
                )
            except Exception:
                continue
        return records

    def _parse_screener_output(self, final_output: dict | None) -> ScreenerRunResponse | None:
        if not isinstance(final_output, dict):
            return None
        try:
            return ScreenerRunResponse.model_validate(final_output)
        except Exception:
            return None

    def _extract_warnings(self, final_output_summary: dict | None) -> list[str]:
        if not isinstance(final_output_summary, dict):
            return []
        raw = final_output_summary.get("warning_messages")
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw if isinstance(item, str) and item.strip()]

    def _build_symbol_results(
        self,
        *,
        batch_id: str,
        output: ScreenerRunResponse,
        calculated_at: datetime,
        rule_version: str,
    ) -> list[ScreenerSymbolResult]:
        candidates = _iter_unique_candidates(output)
        results: list[ScreenerSymbolResult] = []
        for candidate in candidates:
            results.append(
                ScreenerSymbolResult(
                    batch_id=batch_id,
                    symbol=candidate.symbol,
                    name=candidate.name,
                    list_type=candidate.v2_list_type,
                    screener_score=candidate.screener_score,
                    trend_state=candidate.trend_state,
                    trend_score=candidate.trend_score,
                    latest_close=candidate.latest_close,
                    support_level=candidate.support_level,
                    resistance_level=candidate.resistance_level,
                    short_reason=candidate.short_reason,
                    calculated_at=candidate.calculated_at or calculated_at,
                    rule_version=candidate.rule_version or rule_version,
                    rule_summary=candidate.rule_summary or _DEFAULT_RULE_SUMMARY,
                    action_now=candidate.action_now,
                    headline_verdict=candidate.headline_verdict,
                    evidence_hints=candidate.evidence_hints,
                )
            )
        return results

    def _save_batch_record(self, record: ScreenerBatchRecord) -> None:
        self._batch_file(record.batch_id).write_text(
            record.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _save_batch_results(self, *, batch_id: str, results: list[ScreenerSymbolResult]) -> None:
        payload = [item.model_dump(mode="json") for item in results]
        self._result_file(batch_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_run_index(self, *, run_id: str, batch_id: str) -> None:
        self._run_index_file(run_id).write_text(
            json.dumps({"run_id": run_id, "batch_id": batch_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_batch_id_by_run_id(self, run_id: str) -> str | None:
        file_path = self._run_index_file(run_id)
        if not file_path.exists():
            return None
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        batch_id = payload.get("batch_id")
        if isinstance(batch_id, str) and batch_id:
            return batch_id
        return None

    def _build_batch_id(self, trade_date: date) -> str:
        return f"screener-{trade_date.strftime('%Y%m%d')}-{uuid4().hex[:8]}"

    def _batch_file(self, batch_id: str) -> Path:
        return self._batch_dir / f"{batch_id}.json"

    def _result_file(self, batch_id: str) -> Path:
        return self._result_dir / f"{batch_id}.json"

    def _run_index_file(self, run_id: str) -> Path:
        return self._run_index_dir / f"{run_id}.json"


def resolve_screener_trade_date(now: datetime | None = None) -> date:
    """解析本次手动初筛应归属的交易日。"""

    current = now.astimezone(_SHANGHAI_TZ) if now else datetime.now(_SHANGHAI_TZ)
    if current.weekday() < 5 and current.hour >= 17:
        return current.date()
    return resolve_last_closed_trading_day(today=current.date())


def _iter_unique_candidates(output: ScreenerRunResponse) -> Iterable:
    ordered_groups = [
        output.ready_to_buy_candidates,
        output.watch_pullback_candidates,
        output.watch_breakout_candidates,
        output.research_only_candidates,
        output.avoid_candidates,
    ]
    merged: list = []
    for group in ordered_groups:
        merged.extend(group)
    if not merged:
        merged.extend(output.buy_candidates)
        merged.extend(output.watch_candidates)
        merged.extend(output.avoid_candidates)

    seen: set[str] = set()
    for item in merged:
        key = item.symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        yield item
