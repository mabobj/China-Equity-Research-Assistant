"""Screener 批次台账服务测试。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from app.schemas.screener import ScreenerCandidate, ScreenerRunResponse
from app.services.screener_service.batch_service import (
    ScreenerBatchService,
    resolve_screener_trade_date,
)


def test_batch_service_persists_batch_and_symbol_results(tmp_path) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    started_at = datetime(2026, 3, 29, 17, 5, tzinfo=ZoneInfo("Asia/Shanghai"))
    batch = service.create_running_batch(
        run_id="run-001",
        batch_size=60,
        max_symbols=120,
        top_n=30,
        started_at=started_at,
    )

    output = ScreenerRunResponse(
        as_of_date=date(2026, 3, 28),
        freshness_mode="computed",
        source_mode="pipeline",
        total_symbols=120,
        scanned_symbols=118,
        buy_candidates=[],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[
            ScreenerCandidate(
                symbol="600519.SH",
                name="贵州茅台",
                list_type="BUY_CANDIDATE",
                v2_list_type="READY_TO_BUY",
                rank=1,
                screener_score=87,
                alpha_score=82,
                trigger_score=73,
                risk_score=36,
                trend_state="up",
                trend_score=78,
                latest_close=1688.5,
                support_level=1625.0,
                resistance_level=1692.0,
                top_positive_factors=["趋势延续"],
                top_negative_factors=[],
                risk_notes=[],
                short_reason="趋势结构保持向上。",
                rule_version="screener_workflow_v1",
                rule_summary="规则筛选测试摘要",
                bars_quality="ok",
                financial_quality="warning",
                announcement_quality="ok",
                quality_penalty_applied=True,
                quality_note="财务摘要质量一般，候选保留观察。",
            )
        ],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[],
        research_only_candidates=[],
    )

    finished_at = datetime(2026, 3, 29, 17, 8, tzinfo=ZoneInfo("Asia/Shanghai"))
    finalized = service.finalize_batch(
        run_id="run-001",
        status="completed",
        finished_at=finished_at,
        final_output=output.model_dump(mode="json"),
        final_output_summary={},
        error_message=None,
    )

    assert finalized is not None
    assert finalized.status == "completed"
    assert finalized.finished_at == finished_at
    assert finalized.universe_size == 120
    assert finalized.scanned_size == 118

    latest = service.get_latest_batch(now=finished_at + timedelta(minutes=1))
    assert latest is not None
    assert latest.batch_id == batch.batch_id

    results = service.load_batch_results(batch.batch_id)
    assert len(results) == 1
    assert results[0].symbol == "600519.SH"
    assert results[0].rule_version == "screener_workflow_v1"
    assert results[0].rule_summary == "规则筛选测试摘要"
    assert results[0].financial_quality == "warning"
    assert results[0].quality_penalty_applied is True
    assert results[0].quality_note is not None

    detail = service.load_symbol_result(batch.batch_id, "600519.SH")
    assert detail is not None
    assert detail.screener_score == 87


def test_resolve_screener_trade_date_after_1700_uses_today() -> None:
    resolved = resolve_screener_trade_date(
        now=datetime(2026, 3, 30, 17, 5, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert resolved == date(2026, 3, 30)


def test_resolve_screener_trade_date_before_1700_uses_last_closed_day() -> None:
    resolved = resolve_screener_trade_date(
        now=datetime(2026, 3, 30, 16, 55, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert resolved == date(2026, 3, 27)


def test_batch_service_returns_latest_completed_batch_by_time(tmp_path) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    started_a = datetime(2026, 3, 29, 17, 1, tzinfo=ZoneInfo("Asia/Shanghai"))
    started_b = datetime(2026, 3, 29, 17, 3, tzinfo=ZoneInfo("Asia/Shanghai"))

    batch_a = service.create_running_batch(
        run_id="run-a",
        batch_size=50,
        max_symbols=50,
        top_n=20,
        started_at=started_a,
    )
    batch_b = service.create_running_batch(
        run_id="run-b",
        batch_size=50,
        max_symbols=50,
        top_n=20,
        started_at=started_b,
    )

    service.finalize_batch(
        run_id="run-a",
        status="completed",
        finished_at=started_a,
        final_output=None,
        final_output_summary={},
        error_message=None,
    )
    service.finalize_batch(
        run_id="run-b",
        status="completed",
        finished_at=started_b,
        final_output=None,
        final_output_summary={},
        error_message=None,
    )

    latest = service.get_latest_batch(now=started_b + timedelta(minutes=1))
    assert latest is not None
    assert latest.batch_id == batch_b.batch_id
    assert latest.batch_id != batch_a.batch_id


def test_batch_service_localizes_legacy_english_headline(tmp_path) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    started_at = datetime(2026, 3, 29, 17, 5, tzinfo=ZoneInfo("Asia/Shanghai"))
    service.create_running_batch(
        run_id="run-legacy",
        batch_size=50,
        max_symbols=50,
        top_n=20,
        started_at=started_at,
    )

    output = ScreenerRunResponse(
        as_of_date=date(2026, 3, 28),
        freshness_mode="computed",
        source_mode="pipeline",
        total_symbols=50,
        scanned_symbols=50,
        buy_candidates=[],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[
            ScreenerCandidate(
                symbol="000045.SZ",
                name="深纺织Ａ",
                list_type="WATCHLIST",
                v2_list_type="WATCH_BREAKOUT",
                rank=1,
                screener_score=70,
                alpha_score=65,
                trigger_score=66,
                risk_score=45,
                trend_state="up",
                trend_score=82,
                latest_close=12.3,
                support_level=11.5,
                resistance_level=12.8,
                top_positive_factors=["短期趋势改善"],
                top_negative_factors=["财务字段缺失较多"],
                risk_notes=["财务字段缺失较多"],
                short_reason="优势: 短期趋势改善 | 风险: 财务字段缺失较多",
                headline_verdict=(
                    "深纺织Ａ is worth tracking, but breakout confirmation is still needed. "
                    "优势: 短期趋势改善 | 风险: 财务字段缺失较多"
                ),
            )
        ],
        research_only_candidates=[],
    )

    service.finalize_batch(
        run_id="run-legacy",
        status="completed",
        finished_at=started_at,
        final_output=output.model_dump(mode="json"),
        final_output_summary={},
        error_message=None,
    )

    latest = service.get_latest_batch(now=started_at + timedelta(minutes=1))
    assert latest is not None
    rows = service.load_batch_results(latest.batch_id)
    assert rows
    assert "is worth tracking" not in (rows[0].headline_verdict or "")
    assert "值得跟踪，仍需突破确认后再执行。" in (rows[0].headline_verdict or "")


def test_finalize_failed_will_not_override_completed_batch(tmp_path) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    started_at = datetime(2026, 3, 29, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    created = service.create_running_batch(
        run_id="run-keep-completed",
        batch_size=30,
        max_symbols=30,
        top_n=10,
        started_at=started_at,
    )

    service.finalize_batch(
        run_id="run-keep-completed",
        status="completed",
        finished_at=started_at,
        final_output=None,
        final_output_summary={},
        error_message=None,
    )
    preserved = service.finalize_batch(
        run_id="run-keep-completed",
        status="failed",
        finished_at=started_at,
        final_output=None,
        final_output_summary={},
        error_message="stale",
    )

    assert preserved is not None
    assert preserved.status == "completed"
    stored = service.load_batch(created.batch_id)
    assert stored is not None
    assert stored.status == "completed"


def test_get_display_window_before_1700_uses_previous_1700_to_today_1700(tmp_path) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    window_start, window_end = service.get_display_window(
        now=datetime(2026, 3, 30, 16, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert window_start == datetime(2026, 3, 29, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert window_end == datetime(2026, 3, 30, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_get_display_window_after_1700_uses_today_1700_to_now(tmp_path) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    now = datetime(2026, 3, 30, 17, 1, tzinfo=ZoneInfo("Asia/Shanghai"))
    window_start, window_end = service.get_display_window(now=now)
    assert window_start == datetime(2026, 3, 30, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert window_end == now


def test_load_window_results_keeps_latest_record_per_symbol(tmp_path) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    started_a = datetime(2026, 3, 30, 17, 1, tzinfo=ZoneInfo("Asia/Shanghai"))
    started_b = datetime(2026, 3, 30, 17, 3, tzinfo=ZoneInfo("Asia/Shanghai"))
    batch_a = service.create_running_batch(
        run_id="run-window-a",
        batch_size=20,
        max_symbols=20,
        top_n=None,
        started_at=started_a,
    )
    batch_b = service.create_running_batch(
        run_id="run-window-b",
        batch_size=20,
        max_symbols=20,
        top_n=None,
        started_at=started_b,
    )

    candidate_a = ScreenerCandidate(
        symbol="600519.SH",
        name="贵州茅台",
        list_type="WATCHLIST",
        v2_list_type="WATCH_BREAKOUT",
        rank=1,
        screener_score=70,
        alpha_score=66,
        trigger_score=65,
        risk_score=43,
        trend_state="up",
        trend_score=72,
        latest_close=1670.0,
        support_level=1620.0,
        resistance_level=1680.0,
        top_positive_factors=[],
        top_negative_factors=[],
        risk_notes=[],
        short_reason="趋势尚可，等待突破确认。",
        calculated_at=started_a,
    )
    candidate_b = candidate_a.model_copy(
        update={
            "screener_score": 76,
            "short_reason": "趋势继续改善，等待突破确认。",
            "calculated_at": started_b,
        }
    )
    output_a = ScreenerRunResponse(
        as_of_date=date(2026, 3, 30),
        freshness_mode="computed",
        source_mode="pipeline",
        total_symbols=20,
        scanned_symbols=20,
        buy_candidates=[],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[candidate_a],
        research_only_candidates=[],
    )
    output_b = output_a.model_copy(
        update={
            "watch_breakout_candidates": [candidate_b],
        }
    )
    service.finalize_batch(
        run_id="run-window-a",
        status="completed",
        finished_at=started_a,
        final_output=output_a.model_dump(mode="json"),
        final_output_summary={},
        error_message=None,
    )
    service.finalize_batch(
        run_id="run-window-b",
        status="completed",
        finished_at=started_b,
        final_output=output_b.model_dump(mode="json"),
        final_output_summary={},
        error_message=None,
    )

    window_start, window_end, rows = service.load_window_results(
        now=datetime(2026, 3, 30, 17, 10, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert window_start == datetime(2026, 3, 30, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert window_end == datetime(2026, 3, 30, 17, 10, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert len(rows) == 1
    assert rows[0].batch_id == batch_b.batch_id
    assert rows[0].screener_score == 76
    assert rows[0].batch_id != batch_a.batch_id


def test_load_window_results_same_timestamp_keeps_newer_batch(tmp_path) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    started_a = datetime(2026, 3, 30, 17, 1, tzinfo=ZoneInfo("Asia/Shanghai"))
    started_b = datetime(2026, 3, 30, 17, 3, tzinfo=ZoneInfo("Asia/Shanghai"))
    batch_a = service.create_running_batch(
        run_id="run-tie-a",
        batch_size=20,
        max_symbols=20,
        top_n=None,
        started_at=started_a,
    )
    batch_b = service.create_running_batch(
        run_id="run-tie-b",
        batch_size=20,
        max_symbols=20,
        top_n=None,
        started_at=started_b,
    )

    same_calculated_at = datetime(2026, 3, 30, 17, 5, tzinfo=ZoneInfo("Asia/Shanghai"))
    candidate_a = ScreenerCandidate(
        symbol="600519.SH",
        name="贵州茅台",
        list_type="WATCHLIST",
        v2_list_type="WATCH_BREAKOUT",
        rank=1,
        screener_score=70,
        alpha_score=66,
        trigger_score=65,
        risk_score=43,
        trend_state="up",
        trend_score=72,
        latest_close=1670.0,
        support_level=1620.0,
        resistance_level=1680.0,
        top_positive_factors=[],
        top_negative_factors=[],
        risk_notes=[],
        short_reason="趋势尚可，等待突破确认。",
        calculated_at=same_calculated_at,
        predictive_score=None,
        predictive_confidence=None,
        predictive_model_version=None,
    )
    candidate_b = candidate_a.model_copy(
        update={
            "screener_score": 76,
            "short_reason": "趋势继续改善，等待突破确认。",
            "predictive_score": 78,
            "predictive_confidence": 0.78,
            "predictive_model_version": "baseline-rule-v1",
        }
    )
    output_a = ScreenerRunResponse(
        as_of_date=date(2026, 3, 30),
        freshness_mode="computed",
        source_mode="pipeline",
        total_symbols=20,
        scanned_symbols=20,
        buy_candidates=[],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[candidate_a],
        research_only_candidates=[],
    )
    output_b = output_a.model_copy(
        update={
            "watch_breakout_candidates": [candidate_b],
        }
    )
    service.finalize_batch(
        run_id="run-tie-a",
        status="completed",
        finished_at=started_a,
        final_output=output_a.model_dump(mode="json"),
        final_output_summary={},
        error_message=None,
    )
    service.finalize_batch(
        run_id="run-tie-b",
        status="completed",
        finished_at=started_b,
        final_output=output_b.model_dump(mode="json"),
        final_output_summary={},
        error_message=None,
    )

    _, _, rows = service.load_window_results(
        now=datetime(2026, 3, 30, 17, 10, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert len(rows) == 1
    assert rows[0].batch_id == batch_b.batch_id
    assert rows[0].batch_id != batch_a.batch_id
    assert rows[0].predictive_score == 78


class _StubPredictionService:
    def get_symbol_prediction(
        self,
        *,
        symbol: str,
        as_of_date: date,
        build_feature_dataset: bool = False,
    ):
        class _Snapshot:
            predictive_score = 66
            model_confidence = 0.7
            model_version = "baseline-rule-v1"

        assert symbol == "600519.SH"
        assert as_of_date == date(2026, 3, 30)
        assert build_feature_dataset is False
        return _Snapshot()


def test_load_batch_results_hydrates_missing_predictive_fields(tmp_path) -> None:
    service = ScreenerBatchService(
        root_dir=tmp_path,
        prediction_service=_StubPredictionService(),
    )
    started_at = datetime(2026, 3, 30, 17, 1, tzinfo=ZoneInfo("Asia/Shanghai"))
    batch = service.create_running_batch(
        run_id="run-hydrate",
        batch_size=20,
        max_symbols=20,
        top_n=None,
        started_at=started_at,
    )
    candidate = ScreenerCandidate(
        symbol="600519.SH",
        name="贵州茅台",
        list_type="WATCHLIST",
        v2_list_type="WATCH_BREAKOUT",
        rank=1,
        screener_score=70,
        alpha_score=66,
        trigger_score=65,
        risk_score=43,
        trend_state="up",
        trend_score=72,
        latest_close=1670.0,
        support_level=1620.0,
        resistance_level=1680.0,
        top_positive_factors=[],
        top_negative_factors=[],
        risk_notes=[],
        short_reason="趋势尚可，等待突破确认。",
        calculated_at=datetime(2026, 3, 30, 8, 0, tzinfo=ZoneInfo("UTC")),
        predictive_score=None,
        predictive_confidence=None,
        predictive_model_version=None,
    )
    output = ScreenerRunResponse(
        as_of_date=date(2026, 3, 30),
        freshness_mode="computed",
        source_mode="pipeline",
        total_symbols=20,
        scanned_symbols=20,
        buy_candidates=[],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[candidate],
        research_only_candidates=[],
    )
    service.finalize_batch(
        run_id="run-hydrate",
        status="completed",
        finished_at=started_at,
        final_output=output.model_dump(mode="json"),
        final_output_summary={},
        error_message=None,
    )
    rows = service.load_batch_results(batch.batch_id)
    assert rows
    assert rows[0].predictive_score == 66
    assert rows[0].predictive_confidence == 0.7
    assert rows[0].predictive_model_version == "baseline-rule-v1"


def test_batch_service_emits_structured_batch_logs(tmp_path, caplog) -> None:
    service = ScreenerBatchService(root_dir=tmp_path)
    started_at = datetime(2026, 3, 30, 17, 5, tzinfo=ZoneInfo("Asia/Shanghai"))

    with caplog.at_level(logging.INFO):
        batch = service.create_running_batch(
            run_id="run-log-batch",
            batch_size=20,
            max_symbols=20,
            top_n=10,
            started_at=started_at,
        )
        service.finalize_batch(
            run_id="run-log-batch",
            status="completed",
            finished_at=started_at + timedelta(minutes=1),
            final_output=None,
            final_output_summary={"warning_messages": ["测试告警"]},
            error_message=None,
        )
        service.load_window_summary(now=started_at + timedelta(minutes=2))

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "event=screener.batch.created" in message and batch.batch_id in message
        for message in messages
    )
    assert any(
        "event=screener.batch.finalized" in message and batch.batch_id in message
        for message in messages
    )
    assert any("event=screener.window_summary.load_completed" in message for message in messages)
