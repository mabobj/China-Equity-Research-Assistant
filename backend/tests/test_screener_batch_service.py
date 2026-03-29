"""Screener 批次台账服务测试。"""

from __future__ import annotations

from datetime import date, datetime
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

    latest = service.get_latest_batch()
    assert latest is not None
    assert latest.batch_id == batch.batch_id

    results = service.load_batch_results(batch.batch_id)
    assert len(results) == 1
    assert results[0].symbol == "600519.SH"
    assert results[0].rule_version == "screener_workflow_v1"
    assert results[0].rule_summary == "规则筛选测试摘要"

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
