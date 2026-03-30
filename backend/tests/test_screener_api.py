"""选股 API 测试。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_market_data_service,
    get_screener_batch_service,
    get_screener_pipeline,
)
from app.main import app
from app.schemas.screener import (
    ScreenerBatchRecord,
    ScreenerCandidate,
    ScreenerRunResponse,
    ScreenerSymbolResult,
)


class StubScreenerPipeline:
    """用于选股 API 测试的 pipeline 桩。"""

    def run_screener(
        self,
        max_symbols: int = None,
        top_n: int = None,
    ) -> ScreenerRunResponse:
        return ScreenerRunResponse(
            as_of_date=date(2024, 3, 25),
            total_symbols=3,
            scanned_symbols=2,
            buy_candidates=[
                ScreenerCandidate(
                    symbol="600519.SH",
                    name="贵州茅台",
                    list_type="BUY_CANDIDATE",
                    v2_list_type="READY_TO_BUY",
                    rank=1,
                    screener_score=82,
                    alpha_score=80,
                    trigger_score=72,
                    risk_score=35,
                    trend_state="up",
                    trend_score=79,
                    latest_close=1688.0,
                    support_level=1625.0,
                    resistance_level=1692.0,
                    top_positive_factors=["趋势保持向上"],
                    top_negative_factors=[],
                    risk_notes=[],
                    short_reason="上行趋势延续，价格接近突破位。",
                    calculated_at=datetime.now(timezone.utc),
                    rule_version="screener_workflow_v1",
                    rule_summary="规则筛选测试摘要",
                )
            ],
            watch_candidates=[],
            avoid_candidates=[],
            ready_to_buy_candidates=[],
            watch_pullback_candidates=[],
            watch_breakout_candidates=[],
            research_only_candidates=[],
        )


class StubScreenerBatchService:
    def __init__(self) -> None:
        self.batch = ScreenerBatchRecord(
            batch_id="batch-20260329-01",
            trade_date=date(2026, 3, 29),
            run_id="run-screener-001",
            status="completed",
            started_at=datetime(2026, 3, 29, 17, 1, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 29, 17, 5, tzinfo=timezone.utc),
            universe_size=120,
            scanned_size=118,
            rule_version="screener_workflow_v1",
            batch_size=120,
            max_symbols=120,
            top_n=30,
            warning_messages=[],
            failure_reason=None,
        )
        self.results = [
            ScreenerSymbolResult(
                batch_id=self.batch.batch_id,
                symbol="600519.SH",
                name="贵州茅台",
                list_type="READY_TO_BUY",
                screener_score=87,
                trend_state="up",
                trend_score=79,
                latest_close=1688.0,
                support_level=1625.0,
                resistance_level=1692.0,
                short_reason="趋势延续，等待执行窗口确认。",
                calculated_at=datetime(2026, 3, 29, 17, 5, tzinfo=timezone.utc),
                rule_version="screener_workflow_v1",
                rule_summary="规则筛选测试摘要",
                action_now="BUY_NOW",
                headline_verdict="当前可执行，但需要纪律。",
                evidence_hints=["趋势评分占优"],
                fail_reason=None,
            )
        ]

    def get_latest_batch(self):
        return self.batch

    def load_window_results(self):
        return (
            datetime(2026, 3, 29, 17, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 29, 18, 0, tzinfo=timezone.utc),
            self.results,
        )

    def load_batch(self, batch_id: str):
        if batch_id == self.batch.batch_id:
            return self.batch
        return None

    def load_batch_results(self, batch_id: str):
        if batch_id == self.batch.batch_id:
            return self.results
        return []

    def load_symbol_result(self, batch_id: str, symbol: str):
        if batch_id != self.batch.batch_id:
            return None
        for item in self.results:
            if item.symbol == symbol:
                return item
        return None


client = TestClient(app)


class StubMarketDataService:
    def __init__(self) -> None:
        self.storage: dict[str, str | None] = {}

    def set_refresh_cursor(self, cursor_key: str, cursor_value: str | None) -> None:
        self.storage[cursor_key] = cursor_value


def test_run_screener_route_returns_structured_payload() -> None:
    app.dependency_overrides[get_screener_pipeline] = lambda: StubScreenerPipeline()

    response = client.get("/screener/run?max_symbols=10&top_n=5")

    assert response.status_code == 200
    assert response.json()["total_symbols"] == 3
    assert response.json()["buy_candidates"][0]["symbol"] == "600519.SH"
    assert response.json()["buy_candidates"][0]["list_type"] == "BUY_CANDIDATE"
    assert response.json()["buy_candidates"][0]["v2_list_type"] == "READY_TO_BUY"

    app.dependency_overrides.clear()


def test_screener_latest_batch_route_returns_latest_batch() -> None:
    app.dependency_overrides[get_screener_batch_service] = lambda: StubScreenerBatchService()

    response = client.get("/screener/latest-batch")

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch"]["batch_id"] == "batch-20260329-01"
    assert payload["batch"]["run_id"] == "run-screener-001"
    assert payload["total_results"] == 1
    assert payload["results"][0]["symbol"] == "600519.SH"
    assert "window_start" in payload
    assert "window_end" in payload

    app.dependency_overrides.clear()


def test_screener_batch_results_route_returns_result_rows() -> None:
    app.dependency_overrides[get_screener_batch_service] = lambda: StubScreenerBatchService()

    response = client.get("/screener/batches/batch-20260329-01/results")

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch"]["batch_id"] == "batch-20260329-01"
    assert payload["results"][0]["symbol"] == "600519.SH"
    assert payload["results"][0]["rule_version"] == "screener_workflow_v1"

    app.dependency_overrides.clear()


def test_screener_batch_symbol_route_returns_single_symbol_result() -> None:
    app.dependency_overrides[get_screener_batch_service] = lambda: StubScreenerBatchService()

    response = client.get("/screener/batches/batch-20260329-01/results/600519.SH")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["symbol"] == "600519.SH"
    assert payload["result"]["list_type"] == "READY_TO_BUY"

    app.dependency_overrides.clear()


def test_reset_screener_cursor_route_returns_ok() -> None:
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()

    response = client.post("/screener/cursor/reset")

    assert response.status_code == 200
    payload = response.json()
    assert "reset_at" in payload
    assert "初筛游标已重置" in payload["message"]

    app.dependency_overrides.clear()
