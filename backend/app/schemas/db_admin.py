"""数据库排查接口 Schema。"""

from pydantic import BaseModel, ConfigDict, Field


class DbTableInfo(BaseModel):
    """可查询表信息。"""

    model_config = ConfigDict(extra="forbid")

    table_name: str
    row_count: int = Field(ge=0)


class DbTablesResponse(BaseModel):
    """数据库表列表响应。"""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    tables: list[DbTableInfo]


class DbQueryRequest(BaseModel):
    """数据库查询请求。"""

    model_config = ConfigDict(extra="forbid")

    sql: str = Field(min_length=1)
    limit: int = Field(default=200, ge=1, le=2000)


class DbQueryResponse(BaseModel):
    """数据库查询响应。"""

    model_config = ConfigDict(extra="forbid")

    columns: list[str]
    rows: list[list[object]]
    row_count: int = Field(ge=0)
