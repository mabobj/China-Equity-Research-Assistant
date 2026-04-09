"""日线口径元数据 API 契约测试。"""

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_data_service
from app.main import app
from app.schemas.market_data import DailyBar, DailyBarResponse


class StubDailyBarMetadataService:
    def get_daily_bars(
        self,
        symbol: str,
        start_date=None,
        end_date=None,
        adjustment_mode: str = "raw",
        **kwargs,
    ) -> DailyBarResponse:
        return DailyBarResponse(
            symbol="600519.SH",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            count=1,
            bars=[
                DailyBar(
                    symbol="600519.SH",
                    trade_date=date(2024, 1, 2),
                    close=101.0,
                    adjustment_mode="raw",
                    corporate_action_flags=[],
                    source="stub",
                )
            ],
            adjustment_mode="raw",
            corporate_action_mode="unmodeled",
            corporate_action_warnings=["corporate_actions_not_modeled_yet"],
        )


client = TestClient(app)


def setup_module(module) -> None:  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_market_data_service] = (
        lambda: StubDailyBarMetadataService()
    )


def teardown_module(module) -> None:  # type: ignore[no-untyped-def]
    app.dependency_overrides.clear()


def test_daily_bars_api_exposes_adjustment_metadata() -> None:
    response = client.get("/stocks/600519/daily-bars")

    assert response.status_code == 200
    payload = response.json()
    assert payload["adjustment_mode"] == "raw"
    assert payload["corporate_action_mode"] == "unmodeled"
    assert "corporate_actions_not_modeled_yet" in payload["corporate_action_warnings"]
