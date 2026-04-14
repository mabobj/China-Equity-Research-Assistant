"""Schemas for lineage and dataset version tracking."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LineageSourceRef(BaseModel):
    """Reference to one direct upstream source."""

    model_config = ConfigDict(extra="forbid")

    dataset: str
    dataset_version: str
    symbol: Optional[str] = None
    as_of_date: date
    provider_used: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None
    updated_at: Optional[datetime] = None


class LineageDependency(BaseModel):
    """One direct dependency relationship."""

    model_config = ConfigDict(extra="forbid")

    role: str
    source_ref: LineageSourceRef


class LineageMetadata(BaseModel):
    """Unified lineage metadata for one materialized output."""

    model_config = ConfigDict(extra="forbid")

    dataset: str
    dataset_version: str
    schema_version: int = Field(default=1, ge=1)
    generated_at: datetime
    as_of_date: date
    symbol: Optional[str] = None
    dependencies: list[LineageDependency] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)


class LineageListResponse(BaseModel):
    """List response for lineage records."""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    items: list[LineageMetadata] = Field(default_factory=list)


class WorkspaceLineageItem(BaseModel):
    """Lineage summary item for one workspace module."""

    model_config = ConfigDict(extra="forbid")

    item_name: str
    dataset: str
    dataset_version: str
    as_of_date: date
    provider_used: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None


class LineageSummary(BaseModel):
    """Compact lineage summary for a composite output."""

    model_config = ConfigDict(extra="forbid")

    items: list[WorkspaceLineageItem] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)
