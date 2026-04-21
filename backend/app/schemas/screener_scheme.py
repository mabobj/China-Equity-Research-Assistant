"""Schemas for factor-first screener schemes and versions."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SchemeStatus = Literal["draft", "active", "archived"]


class ScreenerSchemeConfig(BaseModel):
    """Structured scheme configuration used by a scheme version."""

    model_config = ConfigDict(extra="forbid")

    universe_filter_config: dict[str, Any] = Field(default_factory=dict)
    factor_selection_config: dict[str, Any] = Field(default_factory=dict)
    factor_weight_config: dict[str, Any] = Field(default_factory=dict)
    threshold_config: dict[str, Any] = Field(default_factory=dict)
    quality_gate_config: dict[str, Any] = Field(default_factory=dict)
    bucket_rule_config: dict[str, Any] = Field(default_factory=dict)


class ScreenerScheme(BaseModel):
    """Reusable screener scheme root object."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: Optional[str] = None
    status: SchemeStatus = "draft"
    created_at: datetime
    updated_at: datetime
    current_version: Optional[str] = None
    is_builtin: bool = False
    is_default: bool = False


class ScreenerSchemeVersion(BaseModel):
    """Immutable scheme version snapshot."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str = Field(min_length=1)
    scheme_version: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    created_at: datetime
    created_by: Optional[str] = None
    change_note: Optional[str] = None
    snapshot_hash: str = Field(min_length=1)
    config: ScreenerSchemeConfig


class ScreenerSchemeVersionSummary(BaseModel):
    """Lightweight version summary for lists."""

    model_config = ConfigDict(extra="forbid")

    scheme_version: str
    version_label: str
    created_at: datetime
    change_note: Optional[str] = None
    snapshot_hash: str


class ScreenerSchemeSummary(BaseModel):
    """Lightweight scheme summary for list pages."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str
    name: str
    description: Optional[str] = None
    status: SchemeStatus
    current_version: Optional[str] = None
    is_builtin: bool = False
    is_default: bool = False
    updated_at: datetime
    current_version_summary: Optional[ScreenerSchemeVersionSummary] = None


class ScreenerSchemeListResponse(BaseModel):
    """List response for screener schemes."""

    model_config = ConfigDict(extra="forbid")

    items: list[ScreenerSchemeSummary] = Field(default_factory=list)
    total: int = Field(ge=0)


class ScreenerSchemeDetailResponse(BaseModel):
    """Detailed scheme response."""

    model_config = ConfigDict(extra="forbid")

    scheme: ScreenerScheme
    current_version_detail: Optional[ScreenerSchemeVersion] = None
    recent_versions: list[ScreenerSchemeVersionSummary] = Field(default_factory=list)


class ScreenerSchemeVersionListResponse(BaseModel):
    """List response for scheme versions."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str
    items: list[ScreenerSchemeVersionSummary] = Field(default_factory=list)
    total: int = Field(ge=0)


class CreateScreenerSchemeRequest(BaseModel):
    """Request to create a screener scheme root object."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: Optional[str] = None
    is_default: bool = False


class UpdateScreenerSchemeRequest(BaseModel):
    """Request to update scheme metadata."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    status: Optional[SchemeStatus] = None
    is_default: Optional[bool] = None


class CreateScreenerSchemeVersionRequest(BaseModel):
    """Request to create a new immutable scheme version."""

    model_config = ConfigDict(extra="forbid")

    version_label: str = Field(min_length=1)
    change_note: Optional[str] = None
    created_by: Optional[str] = None
    config: ScreenerSchemeConfig


class ScreenerRunContextSnapshot(BaseModel):
    """Frozen runtime scheme context for a workflow run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    scheme_id: str = Field(min_length=1)
    scheme_version: str = Field(min_length=1)
    scheme_name: str = Field(min_length=1)
    scheme_snapshot_hash: str = Field(min_length=1)
    trade_date: date
    started_at: datetime
    finished_at: Optional[datetime] = None
    workflow_name: str = Field(min_length=1)
    runtime_params: dict[str, Any] = Field(default_factory=dict)
    effective_scheme_config: ScreenerSchemeConfig

