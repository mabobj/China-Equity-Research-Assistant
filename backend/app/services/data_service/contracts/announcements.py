"""公告清洗后的内部契约。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.research_inputs import AnnouncementItem, AnnouncementListResponse

AnnouncementQualityStatus = Literal["ok", "warning", "degraded", "failed"]


class AnnouncementCleaningSummary(BaseModel):
    """公告清洗摘要。"""

    model_config = ConfigDict(extra="forbid")

    quality_status: AnnouncementQualityStatus
    total_rows: int = Field(ge=0)
    output_rows: int = Field(ge=0)
    dropped_rows: int = Field(ge=0)
    dropped_duplicate_rows: int = Field(ge=0)
    warning_messages: list[str] = Field(default_factory=list)


class CleanAnnouncementItem(BaseModel):
    """清洗后的公告索引项。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    title: str
    publish_date: date
    source: str
    url: Optional[str] = None
    announcement_type: str = "other"
    announcement_subtype: Optional[str] = None
    as_of_date: date
    quality_status: AnnouncementQualityStatus = "ok"
    cleaning_warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    coerced_fields: list[str] = Field(default_factory=list)
    provider_used: Optional[str] = None
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None
    dedupe_key: Optional[str] = None

    def to_announcement_item(self) -> AnnouncementItem:
        """转换为对外兼容 AnnouncementItem。"""
        return AnnouncementItem(
            symbol=self.symbol,
            title=self.title,
            publish_date=self.publish_date,
            announcement_type=self.announcement_type,
            announcement_subtype=self.announcement_subtype,
            source=self.source,
            url=self.url,
            quality_status=self.quality_status,
            cleaning_warnings=list(self.cleaning_warnings),
            missing_fields=list(self.missing_fields),
            coerced_fields=list(self.coerced_fields),
            provider_used=self.provider_used,
            fallback_applied=self.fallback_applied,
            fallback_reason=self.fallback_reason,
            source_mode=self.source_mode,
            freshness_mode=self.freshness_mode,
            dedupe_key=self.dedupe_key,
            as_of_date=self.as_of_date,
        )


class CleanAnnouncementListResult(BaseModel):
    """清洗后的公告列表结果。"""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    items: list[CleanAnnouncementItem]
    quality_status: AnnouncementQualityStatus
    cleaning_warnings: list[str] = Field(default_factory=list)
    dropped_rows: int = Field(default=0, ge=0)
    dropped_duplicate_rows: int = Field(default=0, ge=0)
    as_of_date: date
    provider_used: Optional[str] = None
    fallback_applied: bool = False
    fallback_reason: Optional[str] = None
    source_mode: Optional[str] = None
    freshness_mode: Optional[str] = None
    summary: AnnouncementCleaningSummary

    def to_announcement_items(self) -> list[AnnouncementItem]:
        """转换为列表 schema。"""
        return [item.to_announcement_item() for item in self.items]

    def to_announcement_list_response(self) -> AnnouncementListResponse:
        """转换为对外兼容 AnnouncementListResponse。"""
        return AnnouncementListResponse(
            symbol=self.symbol,
            count=len(self.items),
            items=self.to_announcement_items(),
            quality_status=self.quality_status,
            cleaning_warnings=list(self.cleaning_warnings),
            dropped_rows=self.dropped_rows,
            dropped_duplicate_rows=self.dropped_duplicate_rows,
            provider_used=self.provider_used,
            fallback_applied=self.fallback_applied,
            fallback_reason=self.fallback_reason,
            source_mode=self.source_mode,
            freshness_mode=self.freshness_mode,
            as_of_date=self.as_of_date,
        )

