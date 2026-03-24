"""数据库排查 API 测试。"""

from fastapi.testclient import TestClient

from app.api.dependencies import get_db_inspector_service
from app.main import app
from app.schemas.db_admin import (
    DbQueryResponse,
    DbTableInfo,
    DbTablesResponse,
)


class StubDbInspectorService:
    """数据库排查 service 测试桩。"""

    def list_tables(self) -> DbTablesResponse:
        return DbTablesResponse(
            count=2,
            tables=[
                DbTableInfo(table_name="daily_bars", row_count=12345),
                DbTableInfo(table_name="announcement_events", row_count=567),
            ],
        )

    def query(self, sql: str, limit: int = 200) -> DbQueryResponse:
        return DbQueryResponse(
            columns=["symbol", "close"],
            rows=[["600519.SH", 1688.0]],
            row_count=1,
        )


client = TestClient(app)


def test_list_db_tables_route() -> None:
    """应返回可查询表列表。"""
    app.dependency_overrides[get_db_inspector_service] = lambda: StubDbInspectorService()

    response = client.get("/admin/db/tables")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["tables"][0]["table_name"] == "daily_bars"

    app.dependency_overrides.clear()


def test_query_db_route() -> None:
    """应返回结构化 SQL 查询结果。"""
    app.dependency_overrides[get_db_inspector_service] = lambda: StubDbInspectorService()

    response = client.post(
        "/admin/db/query",
        json={"sql": "select symbol, close from daily_bars limit 1", "limit": 50},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["columns"] == ["symbol", "close"]
    assert payload["rows"][0][0] == "600519.SH"
    assert payload["row_count"] == 1

    app.dependency_overrides.clear()
