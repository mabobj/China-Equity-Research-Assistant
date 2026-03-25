"""API tests for stock data routes."""

from datetime import date, datetime, time
from typing import Optional

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_factor_snapshot_service,
    get_market_data_service,
    get_trigger_snapshot_service,
)
from app.main import app
from app.schemas.factor import (
    AlphaScore,
    FactorGroupScore,
    FactorSnapshot,
    RiskScore,
    TriggerScore,
)
from app.schemas.intraday import TriggerSnapshot
from app.schemas.market_data import (
    DailyBar,
    DailyBarResponse,
    IntradayBar,
    IntradayBarResponse,
    StockProfile,
    TimelinePoint,
    TimelineResponse,
    UniverseItem,
    UniverseResponse,
)
from app.schemas.research_inputs import AnnouncementListResponse, FinancialSummary


class StubMarketDataService:
    """Stub service for API route tests."""

    def get_stock_profile(self, symbol: str) -> StockProfile:
        return StockProfile(
            symbol="600519.SH",
            code="600519",
            exchange="SH",
            name="Kweichow Moutai",
            source="stub",
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DailyBarResponse:
        return DailyBarResponse(
            symbol="600519.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            count=1,
            bars=[
                DailyBar(
                    symbol="600519.SH",
                    trade_date=date(2024, 1, 2),
                    close=101.0,
                    source="stub",
                )
            ],
        )

    def get_intraday_bars(
        self,
        symbol: str,
        frequency: str = "1m",
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> IntradayBarResponse:
        return IntradayBarResponse(
            symbol="600519.SH",
            frequency=frequency,
            start_datetime=datetime(2024, 1, 2, 9, 30, 0),
            end_datetime=datetime(2024, 1, 2, 10, 0, 0),
            count=1,
            bars=[
                IntradayBar(
                    symbol="600519.SH",
                    trade_datetime=datetime(2024, 1, 2, 9, 31, 0),
                    frequency=frequency,
                    close=100.2,
                    source="stub",
                )
            ],
        )

    def get_timeline(
        self,
        symbol: str,
        limit: Optional[int] = None,
    ) -> TimelineResponse:
        return TimelineResponse(
            symbol="600519.SH",
            count=1,
            points=[
                TimelinePoint(
                    symbol="600519.SH",
                    trade_time=time(14, 55, 0),
                    price=100.8,
                    source="stub",
                )
            ],
        )

    def get_stock_universe(self) -> UniverseResponse:
        return UniverseResponse(
            count=1,
            items=[
                UniverseItem(
                    symbol="600519.SH",
                    code="600519",
                    exchange="SH",
                    name="Kweichow Moutai",
                    source="stub",
                )
            ],
        )

    def get_stock_financial_summary(self, symbol: str) -> FinancialSummary:
        return FinancialSummary(
            symbol="600519.SH",
            name="Kweichow Moutai",
            revenue=100.0,
            revenue_yoy=12.0,
            net_profit=20.0,
            net_profit_yoy=15.0,
            roe=18.0,
            debt_ratio=30.0,
            eps=2.5,
            source="stub",
        )

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> AnnouncementListResponse:
        return AnnouncementListResponse(symbol="600519.SH", count=0, items=[])


client = TestClient(app)


class StubTriggerSnapshotService:
    def get_trigger_snapshot(
        self,
        symbol: str,
        frequency: str = "1m",
        limit: int = 60,
    ) -> TriggerSnapshot:
        return TriggerSnapshot(
            symbol="600519.SH",
            as_of_datetime=datetime(2024, 1, 2, 10, 0, 0),
            daily_trend_state="up",
            daily_support_level=100.0,
            daily_resistance_level=102.0,
            latest_intraday_price=101.3,
            distance_to_support_pct=1.3,
            distance_to_resistance_pct=0.69,
            trigger_state="near_breakout",
            trigger_note="盘中价格接近日线压力位，上行趋势下处于突破观察区。",
        )


class StubFactorSnapshotService:
    def get_factor_snapshot(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> FactorSnapshot:
        return FactorSnapshot(
            symbol="600519.SH",
            as_of_date=date(2024, 1, 2),
            raw_factors={"return_20d": 0.08},
            normalized_factors={"return_20d": 72.0},
            factor_group_scores=[
                FactorGroupScore(
                    group_name="trend",
                    score=72.0,
                    top_positive_signals=["20日收益率保持正向，短期相对强弱仍在改善"],
                    top_negative_signals=[],
                )
            ],
            alpha_score=AlphaScore(total_score=73, breakdown=[]),
            trigger_score=TriggerScore(
                total_score=68,
                trigger_state="pullback",
                breakdown=[],
            ),
            risk_score=RiskScore(total_score=35, breakdown=[]),
        )


def test_get_stock_profile_route_returns_structured_payload() -> None:
    """The stock profile endpoint should return the schema payload."""
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()
    response = client.get("/stocks/600519/profile")

    assert response.status_code == 200
    assert response.json()["symbol"] == "600519.SH"
    assert response.json()["name"] == "Kweichow Moutai"

    app.dependency_overrides.clear()


def test_invalid_symbol_returns_400() -> None:
    """Invalid symbols should return a clear 400 response."""
    app.dependency_overrides.clear()
    response = client.get("/stocks/not-a-symbol/profile")

    assert response.status_code == 400
    assert "Invalid symbol" in response.json()["detail"]


def test_intraday_bars_route_supports_frequency_and_datetime_filters() -> None:
    """The intraday route should expose structured minute-bar payloads."""
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()

    response = client.get(
        "/stocks/600519/intraday-bars?frequency=5m&start_datetime=2024-01-02T09:30:00&end_datetime=2024-01-02T10:00:00",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["frequency"] == "5m"
    assert payload["start_datetime"] == "2024-01-02T09:30:00"
    assert payload["end_datetime"] == "2024-01-02T10:00:00"
    assert payload["count"] == 1

    app.dependency_overrides.clear()


def test_timeline_route_returns_structured_payload() -> None:
    """The timeline route should return the latest-trading-day preview points."""
    app.dependency_overrides[get_market_data_service] = lambda: StubMarketDataService()

    response = client.get("/stocks/600519/timeline?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["count"] == 1
    assert payload["points"][0]["trade_time"] == "14:55:00"

    app.dependency_overrides.clear()


def test_trigger_snapshot_route_returns_structured_payload() -> None:
    """The trigger snapshot route should return structured trigger fields."""
    app.dependency_overrides[get_trigger_snapshot_service] = (
        lambda: StubTriggerSnapshotService()
    )

    response = client.get("/stocks/600519/trigger-snapshot?frequency=5m&limit=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["trigger_state"] == "near_breakout"
    assert payload["daily_trend_state"] == "up"

    app.dependency_overrides.clear()


def test_factor_snapshot_route_returns_structured_payload() -> None:
    """The factor snapshot route should return structured factor fields."""
    app.dependency_overrides[get_factor_snapshot_service] = (
        lambda: StubFactorSnapshotService()
    )

    response = client.get("/stocks/600519/factor-snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["alpha_score"]["total_score"] == 73
    assert payload["trigger_score"]["trigger_state"] == "pullback"
    assert payload["risk_score"]["total_score"] == 35

    app.dependency_overrides.clear()
