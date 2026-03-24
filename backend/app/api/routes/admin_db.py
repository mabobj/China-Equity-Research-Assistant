"""数据库排查路由。"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_db_inspector_service
from app.schemas.db_admin import DbQueryRequest, DbQueryResponse, DbTablesResponse

router = APIRouter(prefix="/admin/db", tags=["admin-db"])


@router.get("/tables", response_model=DbTablesResponse)
def list_db_tables(
    service: Any = Depends(get_db_inspector_service),
) -> DbTablesResponse:
    """列出本地数据库的所有可查询表。"""
    return service.list_tables()


@router.post("/query", response_model=DbQueryResponse)
def query_db(
    payload: DbQueryRequest,
    service: Any = Depends(get_db_inspector_service),
) -> DbQueryResponse:
    """执行只读 SQL 查询。"""
    return service.query(sql=payload.sql, limit=payload.limit)
