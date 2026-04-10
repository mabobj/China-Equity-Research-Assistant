"""初筛批次台账持久化服务。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any, Iterable
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.schemas.screener import (
    ScreenerBatchRecord,
    ScreenerRunResponse,
    ScreenerSymbolResult,
)
from app.services.data_products.freshness import resolve_last_closed_trading_day
from app.services.screener_service.texts import normalize_candidate_display_fields

logger = logging.getLogger(__name__)
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_DEFAULT_RULE_VERSION = "screener_workflow_v1"
_DEFAULT_RULE_SUMMARY = "基于趋势评分、因子快照与风险约束的规则初筛。"


class ScreenerBatchService:
    """管理初筛批次记录和批次结果。"""

    def __init__(
        self,
        root_dir: Path,
        prediction_service: Any | None = None,
    ) -> None:
        self._root_dir = root_dir
        self._batch_dir = root_dir / "batches"
        self._result_dir = root_dir / "results"
        self._run_index_dir = root_dir / "run_index"
        self._prediction_service = prediction_service
        self._prediction_cache: dict[tuple[str, str], tuple[int, float, str]] = {}
        self._lock = Lock()
        self._batch_dir.mkdir(parents=True, exist_ok=True)
        self._result_dir.mkdir(parents=True, exist_ok=True)
        self._run_index_dir.mkdir(parents=True, exist_ok=True)

    def create_running_batch(
        self,
        *,
        run_id: str,
        batch_size: int | None,
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
            batch_size=batch_size,
            max_symbols=max_symbols,
            top_n=top_n,
        )
        with self._lock:
            self._save_batch_record(record)
            self._save_run_index(run_id=run_id, batch_id=batch_id)
        logger.info(
            "event=screener.batch.created run_id=%s batch_id=%s trade_date=%s batch_size=%s max_symbols=%s top_n=%s started_at=%s",
            run_id,
            batch_id,
            resolved_trade_date.isoformat(),
            batch_size,
            max_symbols,
            top_n,
            started_at.isoformat(),
        )
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
            if current.status == "completed" and status == "failed":
                return current

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
            logger.info(
                "event=screener.batch.finalized run_id=%s batch_id=%s status=%s scanned_size=%s universe_size=%s result_count=%s warning_count=%s failure_reason=%s",
                run_id,
                batch_id,
                record.status,
                scanned_size,
                universe_size,
                len(results),
                len(warnings),
                failure_reason,
            )
            return record

    def get_display_window(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        current = _to_shanghai_datetime(now)
        reset_point = datetime.combine(current.date(), time(17, 0), tzinfo=_SHANGHAI_TZ)
        if current >= reset_point:
            return reset_point, current
        return reset_point - timedelta(days=1), reset_point

    def get_latest_batch(self, *, now: datetime | None = None) -> ScreenerBatchRecord | None:
        window_start, window_end = self.get_display_window(now=now)
        records = self.list_batches_in_window(window_start=window_start, window_end=window_end)
        if not records:
            return None

        completed = [item for item in records if item.status == "completed"]
        running = [item for item in records if item.status == "running"]

        latest_completed = (
            sorted(
                completed,
                key=lambda item: (
                    self._batch_reference_time(item),
                    item.started_at,
                    item.batch_id,
                ),
                reverse=True,
            )[0]
            if completed
            else None
        )
        latest_running = (
            sorted(running, key=lambda item: (item.started_at, item.batch_id), reverse=True)[0]
            if running
            else None
        )

        if latest_running is not None and (
            latest_completed is None
            or latest_running.started_at >= latest_completed.started_at
        ):
            return latest_running
        if latest_completed is not None:
            return latest_completed
        return records[0]

    def list_batches(self) -> list[ScreenerBatchRecord]:
        records = self._load_all_batches()
        return sorted(
            records,
            key=lambda item: (self._batch_reference_time(item), item.started_at, item.batch_id),
            reverse=True,
        )

    def list_batches_in_window(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[ScreenerBatchRecord]:
        records = self._load_all_batches()
        filtered = [
            item
            for item in records
            if window_start <= self._batch_reference_time(item) < window_end
        ]
        return sorted(
            filtered,
            key=lambda item: (self._batch_reference_time(item), item.started_at, item.batch_id),
            reverse=True,
        )

    def load_window_results(
        self,
        *,
        now: datetime | None = None,
        hydrate_predictive: bool = True,
    ) -> tuple[datetime, datetime, list[ScreenerSymbolResult]]:
        window_start, window_end = self.get_display_window(now=now)
        records = self.list_batches_in_window(window_start=window_start, window_end=window_end)
        logger.info(
            "event=screener.window_results.load_started window_start=%s window_end=%s batch_count=%s hydrate_predictive=%s",
            window_start.isoformat(),
            window_end.isoformat(),
            len(records),
            hydrate_predictive,
        )

        latest_by_symbol: dict[str, ScreenerSymbolResult] = {}
        for batch in records:
            if batch.status not in {"completed", "failed"}:
                continue
            for result in self.load_batch_results(
                batch.batch_id,
                hydrate_predictive=hydrate_predictive,
            ):
                key = result.symbol.upper()
                current = latest_by_symbol.get(key)
                if current is None:
                    latest_by_symbol[key] = result
                    continue
                if _to_shanghai_datetime(result.calculated_at) > _to_shanghai_datetime(
                    current.calculated_at
                ):
                    latest_by_symbol[key] = result

        merged = sorted(
            latest_by_symbol.values(),
            key=lambda item: (_to_shanghai_datetime(item.calculated_at), item.symbol),
            reverse=True,
        )
        logger.info(
            "event=screener.window_results.load_completed window_start=%s window_end=%s merged_symbol_count=%s hydrate_predictive=%s",
            window_start.isoformat(),
            window_end.isoformat(),
            len(merged),
            hydrate_predictive,
        )
        return window_start, window_end, merged

    def load_window_summary(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[datetime, datetime, int]:
        window_start, window_end, merged = self.load_window_results(
            now=now,
            hydrate_predictive=False,
        )
        logger.info(
            "event=screener.window_summary.load_completed window_start=%s window_end=%s total_results=%s",
            window_start.isoformat(),
            window_end.isoformat(),
            len(merged),
        )
        return window_start, window_end, len(merged)

    def load_batch(self, batch_id: str) -> ScreenerBatchRecord | None:
        file_path = self._batch_file(batch_id)
        if not file_path.exists():
            return None
        return ScreenerBatchRecord.model_validate_json(file_path.read_text(encoding="utf-8"))

    def load_batch_results(
        self,
        batch_id: str,
        *,
        hydrate_predictive: bool = True,
    ) -> list[ScreenerSymbolResult]:
        file_path = self._result_file(batch_id)
        if not file_path.exists():
            return []
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        results = [
            _normalize_symbol_result(ScreenerSymbolResult.model_validate(item))
            for item in payload
        ]
        logger.info(
            "event=screener.batch_results.load_started batch_id=%s raw_result_count=%s hydrate_predictive=%s",
            batch_id,
            len(results),
            hydrate_predictive,
        )
        updated = False
        if hydrate_predictive:
            results, updated = self._hydrate_missing_predictive_fields(results)
        if updated:
            with self._lock:
                self._save_batch_results(batch_id=batch_id, results=results)
        logger.info(
            "event=screener.batch_results.load_completed batch_id=%s result_count=%s predictive_hydrated=%s hydrate_predictive=%s",
            batch_id,
            len(results),
            updated,
            hydrate_predictive,
        )
        return results

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
        return sorted(running, key=lambda item: (item.started_at, item.batch_id), reverse=True)[0]

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
            display_fields = normalize_candidate_display_fields(
                name=candidate.name,
                list_type=candidate.v2_list_type,
                short_reason=candidate.short_reason,
                headline_verdict=candidate.headline_verdict,
                evidence_hints=candidate.evidence_hints,
            )
            results.append(
                ScreenerSymbolResult(
                    batch_id=batch_id,
                    symbol=candidate.symbol,
                    name=str(display_fields["name"]),
                    list_type=candidate.v2_list_type,
                    screener_score=candidate.screener_score,
                    trend_state=candidate.trend_state,
                    trend_score=candidate.trend_score,
                    latest_close=candidate.latest_close,
                    support_level=candidate.support_level,
                    resistance_level=candidate.resistance_level,
                    short_reason=str(display_fields["short_reason"]),
                    calculated_at=candidate.calculated_at or calculated_at,
                    rule_version=candidate.rule_version or rule_version,
                    rule_summary=candidate.rule_summary or _DEFAULT_RULE_SUMMARY,
                    action_now=candidate.action_now,
                    headline_verdict=str(display_fields["headline_verdict"]),
                    evidence_hints=list(display_fields["evidence_hints"]),
                    fail_reason=candidate.fail_reason,
                    bars_quality=candidate.bars_quality,
                    financial_quality=candidate.financial_quality,
                    announcement_quality=candidate.announcement_quality,
                    quality_penalty_applied=candidate.quality_penalty_applied,
                    quality_note=candidate.quality_note,
                    predictive_score=candidate.predictive_score,
                    predictive_confidence=candidate.predictive_confidence,
                    predictive_model_version=candidate.predictive_model_version,
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

    def _batch_reference_time(self, record: ScreenerBatchRecord) -> datetime:
        return _to_shanghai_datetime(record.finished_at or record.started_at)

    def _hydrate_missing_predictive_fields(
        self,
        results: list[ScreenerSymbolResult],
    ) -> tuple[list[ScreenerSymbolResult], bool]:
        if self._prediction_service is None or not results:
            return results, False

        updated = False
        hydrated: list[ScreenerSymbolResult] = []
        for result in results:
            if (
                result.predictive_score is not None
                and result.predictive_confidence is not None
                and result.predictive_model_version
            ):
                hydrated.append(result)
                continue

            as_of_date = _to_shanghai_datetime(result.calculated_at).date()
            cache_key = (result.symbol.upper(), as_of_date.isoformat())
            prediction_tuple = self._prediction_cache.get(cache_key)
            if prediction_tuple is None:
                try:
                    snapshot = self._prediction_service.get_symbol_prediction(
                        symbol=result.symbol,
                        as_of_date=as_of_date,
                        build_feature_dataset=False,
                    )
                except Exception:
                    hydrated.append(result)
                    continue
                prediction_tuple = (
                    int(snapshot.predictive_score),
                    float(snapshot.model_confidence),
                    str(snapshot.model_version),
                )
                self._prediction_cache[cache_key] = prediction_tuple

            hydrated.append(
                result.model_copy(
                    update={
                        "predictive_score": prediction_tuple[0],
                        "predictive_confidence": prediction_tuple[1],
                        "predictive_model_version": prediction_tuple[2],
                    }
                )
            )
            updated = True
        return hydrated, updated


def resolve_screener_trade_date(now: datetime | None = None) -> date:
    """解析本次手动初筛应归属的交易日。"""

    current = _to_shanghai_datetime(now)
    if current.weekday() < 5 and current.hour >= 17:
        return current.date()
    return resolve_last_closed_trading_day(today=current.date())


def _to_shanghai_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(_SHANGHAI_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=_SHANGHAI_TZ)
    return value.astimezone(_SHANGHAI_TZ)


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


def _normalize_symbol_result(result: ScreenerSymbolResult) -> ScreenerSymbolResult:
    display_fields = normalize_candidate_display_fields(
        name=result.name,
        list_type=result.list_type,
        short_reason=result.short_reason,
        headline_verdict=result.headline_verdict,
        evidence_hints=result.evidence_hints,
    )
    short_reason = str(display_fields["short_reason"])
    headline = str(display_fields["headline_verdict"])
    normalized_name = str(display_fields["name"])
    normalized_hints = list(display_fields["evidence_hints"])
    if (
        short_reason == result.short_reason
        and headline == result.headline_verdict
        and normalized_name == result.name
        and normalized_hints == result.evidence_hints
    ):
        return result
    return result.model_copy(
        update={
            "name": normalized_name,
            "short_reason": short_reason,
            "headline_verdict": headline,
            "evidence_hints": normalized_hints,
        }
    )
