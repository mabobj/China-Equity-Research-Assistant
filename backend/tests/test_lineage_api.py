from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_lineage_service
from app.main import app
from app.schemas.lineage import LineageListResponse
from app.services.lineage_service.utils import build_lineage_metadata

client = TestClient(app)


class _StubLineageService:
    def __init__(self) -> None:
        self._metadata = build_lineage_metadata(
            dataset="feature_dataset",
            dataset_version="features-2026-04-14-v1",
            as_of_date=date(2026, 4, 14),
            symbol=None,
            dependencies=[],
        )

    def get_dataset_lineage(self, *, dataset: str, dataset_version: str):
        if dataset != "feature_dataset" or dataset_version != "features-2026-04-14-v1":
            raise ValueError("missing")
        return self._metadata

    def list_dataset_lineage(self, *, dataset=None, symbol=None, as_of_date=None, limit=50):
        items = [self._metadata] if dataset in {None, "feature_dataset"} else []
        return LineageListResponse(count=len(items), items=items)


def test_lineage_routes_return_structured_payload() -> None:
    app.dependency_overrides[get_lineage_service] = lambda: _StubLineageService()

    list_response = client.get("/lineage/datasets?dataset=feature_dataset")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    detail_response = client.get(
        "/lineage/datasets/feature_dataset/features-2026-04-14-v1"
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["dataset_version"] == "features-2026-04-14-v1"

    missing_response = client.get("/lineage/datasets/missing/missing")
    assert missing_response.status_code == 404

    app.dependency_overrides.clear()
