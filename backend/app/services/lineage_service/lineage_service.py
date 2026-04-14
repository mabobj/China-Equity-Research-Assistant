"""Application service for lineage registration and queries."""

from __future__ import annotations

from app.schemas.lineage import LineageListResponse, LineageMetadata
from app.services.data_products.base import DataProductResult
from app.services.lineage_service.repository import LineageRepository


class LineageService:
    """Register and query lineage metadata."""

    def __init__(self, repository: LineageRepository) -> None:
        self._repository = repository

    def register_metadata(self, metadata: LineageMetadata) -> LineageMetadata:
        self._repository.save(metadata)
        return metadata

    def register_data_product(self, result: DataProductResult[object]) -> LineageMetadata:
        metadata = result.lineage_metadata
        if metadata is None:
            raise ValueError("data product lineage metadata is unavailable")
        self._repository.save(metadata)
        return metadata

    def get_dataset_lineage(
        self,
        *,
        dataset: str,
        dataset_version: str,
    ) -> LineageMetadata:
        metadata = self._repository.get(
            dataset=dataset,
            dataset_version=dataset_version,
        )
        if metadata is None:
            raise ValueError(f"lineage record not found: {dataset}/{dataset_version}")
        return metadata

    def list_dataset_lineage(
        self,
        *,
        dataset: str | None = None,
        symbol: str | None = None,
        as_of_date=None,
        limit: int = 50,
    ) -> LineageListResponse:
        items = self._repository.list(
            dataset=dataset,
            symbol=symbol,
            as_of_date=as_of_date,
            limit=limit,
        )
        return LineageListResponse(count=len(items), items=items)
