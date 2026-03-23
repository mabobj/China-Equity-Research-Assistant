"""结构化交易策略 API 测试。"""

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_strategy_planner
from app.main import app
from app.schemas.strategy import PriceRange, StrategyPlan


class StubStrategyPlanner:
    """用于策略 API 测试的 planner 桩。"""

    def get_strategy_plan(self, symbol: str) -> StrategyPlan:
        return StrategyPlan(
            symbol="600519.SH",
            name="贵州茅台",
            as_of_date=date(2024, 3, 25),
            action="BUY",
            strategy_type="pullback",
            entry_window="next_3_to_5_trading_days",
            ideal_entry_range=PriceRange(low=1600.0, high=1625.0),
            entry_triggers=[
                "价格回踩支撑区后企稳。",
                "趋势状态保持非下行。",
            ],
            avoid_if=[
                "日线收盘跌破关键支撑位。",
                "研究报告 action 下修为 AVOID。",
            ],
            initial_position_hint="small",
            stop_loss_price=1578.0,
            stop_loss_rule="若买入后日线收盘跌破 1578.00，则执行止损。",
            take_profit_range=PriceRange(low=1688.0, high=1712.0),
            take_profit_rule="价格进入目标区间后分批止盈。",
            hold_rule="趋势未转弱且支撑未失守时继续持有。",
            sell_rule="若跌破止损位或趋势显著走弱，则卖出。",
            review_timeframe="daily_close_review",
            confidence=71,
        )


client = TestClient(app)


def test_get_strategy_plan_route_returns_structured_payload() -> None:
    """策略接口应返回结构化响应。"""
    app.dependency_overrides[get_strategy_planner] = lambda: StubStrategyPlanner()

    response = client.get("/strategy/600519")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["strategy_type"] == "pullback"
    assert response.json()["ideal_entry_range"]["low"] == 1600.0

    app.dependency_overrides.clear()
