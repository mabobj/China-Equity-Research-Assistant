"""交易与复盘 SQLite 存储测试。"""

from __future__ import annotations

from app.db.trade_review_store import TradeReviewStore, utc_now_iso


def test_trade_review_store_crud_and_filters(tmp_path) -> None:
    store = TradeReviewStore(database_path=tmp_path / "trade_review.sqlite3")

    snapshot_payload = {
        "snapshot_id": "ds-001",
        "symbol": "600519.SH",
        "as_of_date": "2026-03-31",
        "action": "WATCH",
        "confidence": 65,
        "technical_score": 70,
        "fundamental_score": 62,
        "event_score": 58,
        "overall_score": 64,
        "thesis": "保持观察，等待更清晰触发位。",
        "risks": ["短期波动放大"],
        "triggers": ["回踩支撑位企稳"],
        "invalidations": ["跌破关键支撑位"],
        "data_quality_summary": {
            "bars_quality": "ok",
            "financial_quality": "warning",
            "announcement_quality": "ok",
            "technical_modifier": 1.0,
            "fundamental_modifier": 0.85,
            "event_modifier": 1.0,
            "overall_quality_modifier": 0.9475,
        },
        "confidence_reasons": ["财务字段存在缺失，置信度下调。"],
        "runtime_mode_requested": "rule_based",
        "runtime_mode_effective": "rule_based",
        "source_refs": [],
        "created_at": utc_now_iso(),
    }
    store.create_decision_snapshot(snapshot_payload)

    trade_payload = {
        "trade_id": "tr-001",
        "symbol": "600519.SH",
        "side": "BUY",
        "trade_date": "2026-03-31T09:45:00+00:00",
        "price": 1600.0,
        "quantity": 100,
        "amount": 160000.0,
        "reason_type": "signal_entry",
        "note": "测试买入",
        "decision_snapshot_id": "ds-001",
        "strategy_alignment": "aligned",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    store.create_trade_record(trade_payload)

    review_payload = {
        "review_id": "rv-001",
        "symbol": "600519.SH",
        "review_date": "2026-04-02",
        "linked_trade_id": "tr-001",
        "linked_decision_snapshot_id": "ds-001",
        "outcome_label": "partial_success",
        "holding_days": 2,
        "max_favorable_excursion": 1.8,
        "max_adverse_excursion": -0.9,
        "exit_reason": "time_exit",
        "did_follow_plan": "yes",
        "review_summary": "按计划执行，结果中性偏正。",
        "lesson_tags": ["good_exit"],
        "warning_messages": [],
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    store.create_review_record(review_payload)

    snapshot = store.get_decision_snapshot("ds-001")
    assert snapshot is not None
    assert snapshot["symbol"] == "600519.SH"
    assert snapshot["confidence_reasons"] == ["财务字段存在缺失，置信度下调。"]

    trades = store.list_trade_records(symbol="600519.SH", limit=20)
    assert len(trades) == 1
    assert trades[0]["trade_id"] == "tr-001"

    updated_trade = store.update_trade_record("tr-001", {"note": "测试买入-更新"})
    assert updated_trade is not None
    assert updated_trade["note"] == "测试买入-更新"

    reviews = store.list_review_records(symbol="600519.SH", limit=20)
    assert len(reviews) == 1
    assert reviews[0]["review_id"] == "rv-001"

    updated_review = store.update_review_record("rv-001", {"lesson_tags_json": ["good_exit", "trend_continued"]})
    assert updated_review is not None
    assert updated_review["lesson_tags"] == ["good_exit", "trend_continued"]
