"""手动数据补全相关的 Pydantic Schema。"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class DataRefreshRequest(BaseModel):
    """前端触发手动数据补全时的请求体。"""

    model_config = ConfigDict(extra="forbid")

    max_symbols: Optional[int] = Field(default=None, ge=1)


class DataRefreshStatus(BaseModel):
    """手动数据补全任务的结构化状态。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["idle", "running", "completed", "failed"]
    is_running: bool
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    universe_count: int = Field(ge=0)
    total_symbols: int = Field(ge=0)
    processed_symbols: int = Field(ge=0)
    succeeded_symbols: int = Field(ge=0)
    failed_symbols: int = Field(ge=0)
    profiles_updated: int = Field(ge=0)
    daily_bars_updated: int = Field(ge=0)
    financial_summaries_updated: int = Field(ge=0)
    announcements_updated: int = Field(ge=0)
    daily_bars_synced_rows: int = Field(ge=0)
    announcements_synced_items: int = Field(ge=0)
    profile_step_failures: int = Field(ge=0)
    daily_bar_step_failures: int = Field(ge=0)
    financial_step_failures: int = Field(ge=0)
    announcement_step_failures: int = Field(ge=0)
    universe_updated: bool = False
    max_symbols: Optional[int] = Field(default=None, ge=1)
    current_symbol: Optional[str] = None
    current_stage: Optional[str] = None
    message: str
    recent_warnings: list[str] = Field(default_factory=list)
    recent_errors: list[str] = Field(default_factory=list)
