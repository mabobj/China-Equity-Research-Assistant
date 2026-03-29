"""API tests for strategy routes."""

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_strategy_plan_daily_dataset,
    get_strategy_planner,
)
from app.main import app
from app.schemas.strategy import PriceRange, StrategyPlan
from app.services.data_products.base import DataProductResult


class StubStrategyPlanner:
    def get_strategy_plan(self, symbol: str) -> StrategyPlan:
        return StrategyPlan(
            symbol="600519.SH",
            name="Kweichow Moutai",
            as_of_date=date(2024, 3, 25),
            action="BUY",
            strategy_type="pullback",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=1600.0, high=1625.0),
            entry_triggers=["Pullback holds support", "Trend remains non-down"],
            avoid_if=["Daily close breaks support", "Research action drops to AVOID"],
            initial_position_hint="small",
            stop_loss_price=1578.0,
            stop_loss_rule="Stop after support break.",
            take_profit_range=PriceRange(low=1688.0, high=1712.0),
            take_profit_rule="Scale out in target range.",
            hold_rule="Hold while trend is intact.",
            sell_rule="Exit when stop-loss or invalidation is hit.",
            review_timeframe="daily_close_review",
            confidence=71,
        )


class StubStrategyPlanDaily:
    def load(self, symbol: str, *, as_of_date):
        return None

    def save(self, symbol: str, payload: StrategyPlan):
        return DataProductResult(
            dataset="strategy_plan_daily",
            symbol=symbol,
            as_of_date=payload.as_of_date,
            payload=payload,
            freshness_mode="computed",
            source_mode="snapshot",
            updated_at=datetime.now(timezone.utc),
        )


client = TestClient(app)


def test_get_strategy_plan_route_returns_structured_payload() -> None:
    app.dependency_overrides[get_strategy_planner] = lambda: StubStrategyPlanner()
    app.dependency_overrides[get_strategy_plan_daily_dataset] = (
        lambda: StubStrategyPlanDaily()
    )

    response = client.get("/strategy/600519")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["strategy_type"] == "pullback"
    assert response.json()["ideal_entry_range"]["low"] == 1600.0
    assert response.json()["freshness_mode"] == "computed"
    assert response.json()["source_mode"] == "snapshot"

    app.dependency_overrides.clear()
