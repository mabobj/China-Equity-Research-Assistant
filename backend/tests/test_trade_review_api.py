"""交易与复盘闭环 API 测试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_decision_snapshot_service,
    get_review_record_service,
    get_trade_service,
)
from app.db.trade_review_store import TradeReviewStore
from app.main import app
from app.schemas.market_data import DailyBar, DailyBarResponse
from app.schemas.research import ResearchDataQualitySummary, ResearchReport
from app.services.decision_snapshot_service.decision_snapshot_service import (
    DecisionSnapshotService,
)
from app.services.review_record_service.review_service import ReviewRecordService
from app.services.trade_service.trade_service import TradeService


@dataclass
class _FreshnessItem:
    item_name: str
    as_of_date: date
    freshness_mode: str
    source_mode: str


@dataclass
class _FreshnessSummary:
    items: list[_FreshnessItem]


@dataclass
class _WorkspaceBundle:
    freshness_summary: _FreshnessSummary
    runtime_mode_requested: str
    runtime_mode_effective: str


class _StubWorkspaceBundleService:
    def get_workspace_bundle(self, symbol: str, **kwargs) -> _WorkspaceBundle:
        return _WorkspaceBundle(
            freshness_summary=_FreshnessSummary(
                items=[
                    _FreshnessItem(
                        item_name="review_report_daily",
                        as_of_date=date(2026, 3, 31),
                        freshness_mode="cache_hit",
                        source_mode="local",
                    )
                ]
            ),
            runtime_mode_requested="rule_based",
            runtime_mode_effective="rule_based",
        )


class _StubResearchManager:
    def get_research_report(self, symbol: str) -> ResearchReport:
        return ResearchReport(
            symbol=symbol,
            name="测试股票",
            as_of_date=date(2026, 3, 31),
            technical_score=66,
            fundamental_score=58,
            event_score=61,
            risk_score=40,
            overall_score=62,
            action="WATCH",
            confidence=57,
            thesis="信号偏中性，建议观察。",
            key_reasons=["趋势未破坏"],
            risks=["财务字段缺失较多"],
            triggers=["回踩支撑位企稳"],
            invalidations=["跌破关键支撑位"],
            data_quality_summary=ResearchDataQualitySummary(
                bars_quality="ok",
                financial_quality="degraded",
                announcement_quality="ok",
                technical_modifier=1.0,
                fundamental_modifier=0.6,
                event_modifier=1.0,
                overall_quality_modifier=0.86,
            ),
            confidence_reasons=["财务质量降级，置信度下调。"],
        )


class _StubMarketDataService:
    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        return DailyBarResponse(
            symbol=symbol,
            start_date=date.fromisoformat(start_date or "2026-03-30"),
            end_date=date.fromisoformat(end_date or "2026-03-31"),
            count=2,
            bars=[
                DailyBar(
                    symbol=symbol,
                    trade_date=date(2026, 3, 31),
                    high=1620.0,
                    low=1580.0,
                    close=1605.0,
                    source="stub",
                ),
                DailyBar(
                    symbol=symbol,
                    trade_date=date(2026, 4, 1),
                    high=1630.0,
                    low=1570.0,
                    close=1612.0,
                    source="stub",
                ),
            ],
        )


client = TestClient(app)


def _build_services(tmp_path):
    store = TradeReviewStore(database_path=tmp_path / "trade_review.sqlite3")
    snapshot_service = DecisionSnapshotService(
        store=store,
        workspace_bundle_service=_StubWorkspaceBundleService(),
        research_manager=_StubResearchManager(),
    )
    trade_service = TradeService(
        store=store,
        decision_snapshot_service=snapshot_service,
    )
    review_service = ReviewRecordService(
        store=store,
        trade_service=trade_service,
        decision_snapshot_service=snapshot_service,
        market_data_service=_StubMarketDataService(),
    )
    return snapshot_service, trade_service, review_service


def test_decision_snapshot_trade_review_flow(tmp_path) -> None:
    snapshot_service, trade_service, review_service = _build_services(tmp_path)
    app.dependency_overrides[get_decision_snapshot_service] = lambda: snapshot_service
    app.dependency_overrides[get_trade_service] = lambda: trade_service
    app.dependency_overrides[get_review_record_service] = lambda: review_service

    snapshot_response = client.post(
        "/decision-snapshots",
        json={"symbol": "600519.SH", "use_llm": False},
    )
    assert snapshot_response.status_code == 200
    snapshot_payload = snapshot_response.json()
    assert snapshot_payload["symbol"] == "600519.SH"
    assert snapshot_payload["data_quality_summary"]["financial_quality"] == "degraded"

    trade_response = client.post(
        "/trades",
        json={
            "symbol": "600519.SH",
            "side": "BUY",
            "trade_date": "2026-03-31T09:30:00+00:00",
            "price": 1600.0,
            "quantity": 100,
            "reason_type": "signal_entry",
            "note": "测试交易",
            "auto_create_snapshot": True,
            "use_llm": False,
        },
    )
    assert trade_response.status_code == 200
    trade_payload = trade_response.json()
    assert trade_payload["decision_snapshot_id"] is not None
    assert trade_payload["decision_snapshot"]["runtime_mode_effective"] == "rule_based"

    skip_response = client.post(
        "/trades",
        json={
            "symbol": "600519.SH",
            "side": "SKIP",
            "trade_date": "2026-03-31T10:30:00+00:00",
            "reason_type": "skip_due_to_quality",
            "note": "质量不够，暂不执行",
            "auto_create_snapshot": False,
        },
    )
    assert skip_response.status_code == 200
    skip_payload = skip_response.json()
    assert skip_payload["price"] is None
    assert skip_payload["quantity"] is None

    review_response = client.post(
        "/reviews/from-trade/{trade_id}".format(trade_id=trade_payload["trade_id"]),
        json={"review_date": "2026-04-01"},
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["linked_trade_id"] == trade_payload["trade_id"]
    assert review_payload["holding_days"] == 1
    assert review_payload["max_favorable_excursion"] is not None
    assert review_payload["max_adverse_excursion"] is not None

    list_trade_response = client.get("/trades?symbol=600519.SH&limit=20")
    assert list_trade_response.status_code == 200
    assert list_trade_response.json()["count"] >= 2

    list_review_response = client.get("/reviews?symbol=600519.SH&limit=20")
    assert list_review_response.status_code == 200
    assert list_review_response.json()["count"] >= 1

    app.dependency_overrides.clear()


def test_review_metrics_handles_missing_bars_with_controlled_warning(tmp_path) -> None:
    class _NoBarsMarketDataService:
        def get_daily_bars(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
        ):
            return DailyBarResponse(
                symbol=symbol,
                start_date=date.fromisoformat(start_date or "2026-03-30"),
                end_date=date.fromisoformat(end_date or "2026-03-31"),
                count=0,
                bars=[],
            )

    store = TradeReviewStore(database_path=tmp_path / "trade_review.sqlite3")
    snapshot_service = DecisionSnapshotService(
        store=store,
        workspace_bundle_service=_StubWorkspaceBundleService(),
        research_manager=_StubResearchManager(),
    )
    trade_service = TradeService(store=store, decision_snapshot_service=snapshot_service)
    review_service = ReviewRecordService(
        store=store,
        trade_service=trade_service,
        decision_snapshot_service=snapshot_service,
        market_data_service=_NoBarsMarketDataService(),
    )
    app.dependency_overrides[get_trade_service] = lambda: trade_service
    app.dependency_overrides[get_review_record_service] = lambda: review_service

    create_trade = client.post(
        "/trades",
        json={
            "symbol": "600519.SH",
            "side": "BUY",
            "trade_date": "2026-03-31T09:30:00+00:00",
            "price": 1600.0,
            "quantity": 100,
            "reason_type": "signal_entry",
            "note": "测试缺行情",
        },
    )
    assert create_trade.status_code == 200
    trade_id = create_trade.json()["trade_id"]

    review_response = client.post(
        "/reviews/from-trade/{trade_id}".format(trade_id=trade_id),
        json={"review_date": "2026-04-01"},
    )
    assert review_response.status_code == 200
    payload = review_response.json()
    assert payload["holding_days"] is None
    assert payload["max_favorable_excursion"] is None
    assert payload["max_adverse_excursion"] is None
    assert "daily_bars_unavailable_for_review_window" in payload["warning_messages"]

    app.dependency_overrides.clear()


def test_trade_alignment_and_review_follow_plan_constraints(tmp_path) -> None:
    snapshot_service, trade_service, review_service = _build_services(tmp_path)
    app.dependency_overrides[get_decision_snapshot_service] = lambda: snapshot_service
    app.dependency_overrides[get_trade_service] = lambda: trade_service
    app.dependency_overrides[get_review_record_service] = lambda: review_service

    manual_snapshot = client.post(
        "/decision-snapshots",
        json={
            "payload": {
                "symbol": "600519.SH",
                "as_of_date": "2026-03-31",
                "action": "AVOID",
                "confidence": 20,
                "technical_score": 30,
                "fundamental_score": 25,
                "event_score": 35,
                "overall_score": 28,
                "thesis": "避免参与",
            }
        },
    )
    assert manual_snapshot.status_code == 200
    snapshot_id = manual_snapshot.json()["snapshot_id"]

    invalid_trade = client.post(
        "/trades",
        json={
            "symbol": "600519.SH",
            "side": "BUY",
            "trade_date": "2026-03-31T09:30:00+00:00",
            "price": 1600.0,
            "quantity": 100,
            "reason_type": "signal_entry",
            "decision_snapshot_id": snapshot_id,
            "strategy_alignment": "aligned",
        },
    )
    assert invalid_trade.status_code == 400
    assert "alignment_override_reason" in invalid_trade.json()["detail"]

    valid_trade = client.post(
        "/trades",
        json={
            "symbol": "600519.SH",
            "side": "BUY",
            "trade_date": "2026-03-31T09:35:00+00:00",
            "price": 1601.0,
            "quantity": 100,
            "reason_type": "signal_entry",
            "decision_snapshot_id": snapshot_id,
            "strategy_alignment": "unknown",
        },
    )
    assert valid_trade.status_code == 200
    trade_payload = valid_trade.json()
    assert trade_payload["strategy_alignment"] == "not_aligned"

    review_response = client.post(
        "/reviews",
        json={
            "symbol": "600519.SH",
            "review_date": "2026-04-01",
            "linked_trade_id": trade_payload["trade_id"],
            "linked_decision_snapshot_id": snapshot_id,
            "outcome_label": "failure",
            "did_follow_plan": "yes",
            "review_summary": "测试复盘",
        },
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["did_follow_plan"] == "no"
    assert (
        "did_follow_plan_auto_adjusted_from_yes_to_no_due_to_trade_alignment"
        in review_payload["warning_messages"]
    )

    app.dependency_overrides.clear()
