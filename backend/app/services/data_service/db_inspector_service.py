"""数据库排查服务。"""

from app.db.market_data_store import LocalMarketDataStore
from app.schemas.db_admin import (
    DbQueryResponse,
    DbTableInfo,
    DbTablesResponse,
)
from app.services.data_service.exceptions import InvalidRequestError


class DbInspectorService:
    """提供数据库表浏览和只读 SQL 查询能力。"""

    def __init__(self, local_store: LocalMarketDataStore) -> None:
        self._local_store = local_store

    def list_tables(self) -> DbTablesResponse:
        """列出所有可查询表及行数。"""
        tables = [
            DbTableInfo(
                table_name=str(item["table_name"]),
                row_count=int(item["row_count"]),
            )
            for item in self._local_store.list_queryable_tables()
        ]
        return DbTablesResponse(count=len(tables), tables=tables)

    def query(self, sql: str, limit: int = 200) -> DbQueryResponse:
        """执行只读 SQL 查询。"""
        if not sql.strip():
            raise InvalidRequestError("SQL cannot be empty.")

        try:
            columns, rows = self._local_store.execute_readonly_sql(sql=sql, limit=limit)
        except ValueError as exc:
            raise InvalidRequestError(str(exc)) from exc
        except Exception as exc:
            raise InvalidRequestError(
                "Failed to execute SQL query: {message}".format(message=str(exc)),
            ) from exc

        return DbQueryResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )
