"""预测数据集与标签数据集 schema。"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lineage import LineageMetadata, LineageSourceRef


class FeatureDatasetSummary(BaseModel):
    """特征数据集摘要。"""

    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    as_of_date: date
    symbol_count: int = Field(ge=0)
    feature_count: int = Field(ge=0)
    label_version: Optional[str] = None
    source_mode: str = "local"
    description: Optional[str] = None
    lineage_metadata: Optional[LineageMetadata] = None
    upstream_sources: list[LineageSourceRef] = Field(default_factory=list)


class FeatureDatasetResponse(BaseModel):
    """特征数据集详情。"""

    model_config = ConfigDict(extra="forbid")

    summary: FeatureDatasetSummary
    feature_names: list[str] = Field(default_factory=list)
    warning_messages: list[str] = Field(default_factory=list)


class FeatureDatasetBuildRequest(BaseModel):
    """构建特征数据集请求。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: Optional[date] = None
    max_symbols: int = Field(default=300, ge=1, le=2000)
    force_refresh: bool = False


class LabelDatasetSummary(BaseModel):
    """标签数据集摘要。"""

    model_config = ConfigDict(extra="forbid")

    label_version: str
    as_of_date: date
    symbol_count: int = Field(ge=0)
    window_5d: int = Field(default=5, ge=1)
    window_10d: int = Field(default=10, ge=1)
    source_mode: str = "local"
    description: Optional[str] = None
    feature_version: Optional[str] = None
    lineage_metadata: Optional[LineageMetadata] = None


class LabelDatasetResponse(BaseModel):
    """标签数据集详情。"""

    model_config = ConfigDict(extra="forbid")

    summary: LabelDatasetSummary
    warning_messages: list[str] = Field(default_factory=list)


class LabelDatasetBuildRequest(BaseModel):
    """构建标签数据集请求。"""

    model_config = ConfigDict(extra="forbid")

    as_of_date: Optional[date] = None
    max_symbols: int = Field(default=300, ge=1, le=2000)
    force_refresh: bool = False
