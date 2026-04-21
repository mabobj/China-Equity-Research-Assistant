from __future__ import annotations

from datetime import date, datetime, timezone

from app.db.trade_review_store import TradeReviewStore
from app.schemas.screener import ScreenerBatchRecord, ScreenerSymbolResult
from app.services.screener_service.scheme_review_service import (
    ScreenerSchemeReviewService,
)
from app.services.screener_service.scheme_service import ScreenerSchemeService


class StubBatchService:
    def __init__(
        self,
        *,
        batches: list[ScreenerBatchRecord],
        batch_results: dict[str, list[ScreenerSymbolResult]],
    ) -> None:
        self._batches = batches
        self._batch_results = batch_results

    def list_batches(self) -> list[ScreenerBatchRecord]:
        return list(self._batches)

    def load_batch_results(
        self,
        batch_id: str,
        *,
        hydrate_predictive: bool = True,
    ) -> list[ScreenerSymbolResult]:
        return list(self._batch_results.get(batch_id, []))


def test_scheme_review_service_lists_runs_with_journal_counts(tmp_path) -> None:
    scheme_service = ScreenerSchemeService(root_dir=tmp_path / "schemes")
    store = TradeReviewStore(database_path=tmp_path / "trade_review.sqlite3")
    batch = ScreenerBatchRecord(
        batch_id="batch-1",
        trade_date=date(2026, 4, 21),
        run_id="run-1",
        status="completed",
        started_at=datetime(2026, 4, 21, 9, 30, tzinfo=timezone.utc),
        finished_at=datetime(2026, 4, 21, 9, 35, tzinfo=timezone.utc),
        universe_size=50,
        scanned_size=50,
        rule_version="screener_workflow_v1",
        batch_size=50,
        max_symbols=50,
        top_n=20,
        scheme_id="default_builtin_scheme",
        scheme_version="legacy_v1",
        scheme_name="默认内置方案",
        scheme_snapshot_hash="hash-1",
    )
    batch_service = StubBatchService(
        batches=[batch],
        batch_results={
            "batch-1": [
                _build_result(
                    batch_id="batch-1",
                    symbol="600519.SH",
                    list_type="READY_TO_BUY",
                ),
                _build_result(
                    batch_id="batch-1",
                    symbol="000001.SZ",
                    list_type="RESEARCH_ONLY",
                ),
            ]
        },
    )
    _seed_snapshot(store, symbol="600519.SH", snapshot_id="ds-1")
    _seed_trade(store, symbol="600519.SH", trade_id="tr-1", snapshot_id="ds-1")
    _seed_review(store, symbol="600519.SH", review_id="rv-1", trade_id="tr-1")

    service = ScreenerSchemeReviewService(
        scheme_service=scheme_service,
        batch_service=batch_service,  # type: ignore[arg-type]
        store=store,
    )

    response = service.list_scheme_runs(scheme_id="default_builtin_scheme")

    assert response.count == 1
    run = response.items[0]
    assert run.result_count == 2
    assert run.ready_count == 1
    assert run.research_count == 1
    assert run.decision_snapshot_count == 1
    assert run.trade_count == 1
    assert run.review_count == 1


def test_scheme_review_service_builds_stats_and_feedback(tmp_path) -> None:
    scheme_service = ScreenerSchemeService(root_dir=tmp_path / "schemes")
    store = TradeReviewStore(database_path=tmp_path / "trade_review.sqlite3")
    batches = [
        ScreenerBatchRecord(
            batch_id="batch-1",
            trade_date=date(2026, 4, 21),
            run_id="run-1",
            status="completed",
            started_at=datetime(2026, 4, 21, 9, 30, tzinfo=timezone.utc),
            finished_at=datetime(2026, 4, 21, 9, 35, tzinfo=timezone.utc),
            universe_size=50,
            scanned_size=50,
            rule_version="screener_workflow_v1",
            batch_size=50,
            max_symbols=50,
            top_n=20,
            scheme_id="default_builtin_scheme",
            scheme_version="legacy_v1",
            scheme_name="默认内置方案",
            scheme_snapshot_hash="hash-1",
        ),
        ScreenerBatchRecord(
            batch_id="batch-2",
            trade_date=date(2026, 4, 22),
            run_id="run-2",
            status="failed",
            started_at=datetime(2026, 4, 22, 9, 30, tzinfo=timezone.utc),
            finished_at=datetime(2026, 4, 22, 9, 31, tzinfo=timezone.utc),
            universe_size=50,
            scanned_size=10,
            rule_version="screener_workflow_v1",
            batch_size=50,
            max_symbols=50,
            top_n=20,
            scheme_id="default_builtin_scheme",
            scheme_version="legacy_v1",
            scheme_name="默认内置方案",
            scheme_snapshot_hash="hash-1",
            failure_reason="test-failure",
        ),
    ]
    batch_service = StubBatchService(
        batches=batches,
        batch_results={
            "batch-1": [
                _build_result(
                    batch_id="batch-1",
                    symbol="600519.SH",
                    list_type="READY_TO_BUY",
                ),
                _build_result(
                    batch_id="batch-1",
                    symbol="000001.SZ",
                    list_type="WATCH_PULLBACK",
                ),
            ],
            "batch-2": [
                _build_result(
                    batch_id="batch-2",
                    symbol="600519.SH",
                    list_type="RESEARCH_ONLY",
                )
            ],
        },
    )
    _seed_snapshot(store, symbol="600519.SH", snapshot_id="ds-1")
    _seed_trade(
        store,
        symbol="600519.SH",
        trade_id="tr-1",
        snapshot_id="ds-1",
        strategy_alignment="aligned",
    )
    _seed_review(
        store,
        symbol="600519.SH",
        review_id="rv-1",
        trade_id="tr-1",
        outcome_label="success",
        did_follow_plan="yes",
        lesson_tags=["good_timing", "follow_plan"],
    )

    service = ScreenerSchemeReviewService(
        scheme_service=scheme_service,
        batch_service=batch_service,  # type: ignore[arg-type]
        store=store,
    )

    stats_response = service.get_scheme_stats(scheme_id="default_builtin_scheme")
    feedback_response = service.get_scheme_feedback(scheme_id="default_builtin_scheme")

    assert stats_response.stats.total_runs == 2
    assert stats_response.stats.completed_runs == 1
    assert stats_response.stats.failed_runs == 1
    assert stats_response.stats.total_candidates == 3
    assert stats_response.stats.ready_count == 1
    assert stats_response.stats.watch_count == 1
    assert stats_response.stats.research_count == 1
    assert stats_response.stats.entered_research_count == 1
    assert stats_response.stats.outcome_distribution["success"] == 1

    assert feedback_response.feedback.linked_symbols == 2
    assert feedback_response.feedback.traded_symbols == 1
    assert feedback_response.feedback.reviewed_symbols == 1
    assert feedback_response.feedback.aligned_trades == 1
    assert feedback_response.feedback.did_follow_plan_distribution["yes"] == 1
    assert feedback_response.feedback.lesson_tag_distribution["good_timing"] == 1


def _build_result(
    *,
    batch_id: str,
    symbol: str,
    list_type: str,
) -> ScreenerSymbolResult:
    return ScreenerSymbolResult(
        batch_id=batch_id,
        symbol=symbol,
        name=symbol,
        list_type=list_type,
        screener_score=80,
        trend_state="up",
        trend_score=75,
        latest_close=10.0,
        short_reason="test",
        calculated_at=datetime(2026, 4, 21, 9, 35, tzinfo=timezone.utc),
        rule_version="screener_workflow_v1",
        rule_summary="test-summary",
    )


def _seed_snapshot(
    store: TradeReviewStore,
    *,
    symbol: str,
    snapshot_id: str,
) -> None:
    store.create_decision_snapshot(
        {
            "snapshot_id": snapshot_id,
            "symbol": symbol,
            "as_of_date": "2026-04-21",
            "action": "BUY",
            "confidence": 70,
            "technical_score": 70,
            "fundamental_score": 65,
            "event_score": 60,
            "overall_score": 68,
            "thesis": "test",
            "risks": [],
            "triggers": [],
            "invalidations": [],
            "data_quality_summary": None,
            "confidence_reasons": [],
            "runtime_mode_requested": None,
            "runtime_mode_effective": None,
            "predictive_score": None,
            "predictive_confidence": None,
            "predictive_model_version": None,
            "predictive_feature_version": None,
            "predictive_label_version": None,
            "source_refs": [],
            "created_at": datetime(2026, 4, 21, 9, 40, tzinfo=timezone.utc).isoformat(),
        }
    )


def _seed_trade(
    store: TradeReviewStore,
    *,
    symbol: str,
    trade_id: str,
    snapshot_id: str,
    strategy_alignment: str = "aligned",
) -> None:
    created_at = datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc).isoformat()
    store.create_trade_record(
        {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": "BUY",
            "trade_date": created_at,
            "price": 10.0,
            "quantity": 100,
            "amount": 1000.0,
            "reason_type": "signal_entry",
            "note": "test",
            "decision_snapshot_id": snapshot_id,
            "strategy_alignment": strategy_alignment,
            "alignment_override_reason": None,
            "created_at": created_at,
            "updated_at": created_at,
        }
    )


def _seed_review(
    store: TradeReviewStore,
    *,
    symbol: str,
    review_id: str,
    trade_id: str,
    outcome_label: str = "success",
    did_follow_plan: str = "yes",
    lesson_tags: list[str] | None = None,
) -> None:
    created_at = datetime(2026, 4, 23, 10, 0, tzinfo=timezone.utc).isoformat()
    store.create_review_record(
        {
            "review_id": review_id,
            "symbol": symbol,
            "review_date": "2026-04-23",
            "linked_trade_id": trade_id,
            "linked_decision_snapshot_id": "ds-1",
            "outcome_label": outcome_label,
            "holding_days": 2,
            "max_favorable_excursion": 5.0,
            "max_adverse_excursion": -1.0,
            "exit_reason": None,
            "did_follow_plan": did_follow_plan,
            "review_summary": "test",
            "lesson_tags": lesson_tags or [],
            "warning_messages": [],
            "created_at": created_at,
            "updated_at": created_at,
        }
    )
