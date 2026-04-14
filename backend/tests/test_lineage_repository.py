from __future__ import annotations

from datetime import date

from app.services.lineage_service.repository import LineageRepository
from app.services.lineage_service.utils import build_lineage_metadata


def test_lineage_repository_can_save_and_query_records(tmp_path) -> None:
    repository = LineageRepository(tmp_path / "lineage.sqlite3")
    metadata = build_lineage_metadata(
        dataset="feature_dataset",
        dataset_version="features-2026-04-14-v1",
        as_of_date=date(2026, 4, 14),
        dependencies=[],
    )

    repository.save(metadata)

    loaded = repository.get(
        dataset="feature_dataset",
        dataset_version="features-2026-04-14-v1",
    )
    assert loaded is not None
    assert loaded.dataset_version == "features-2026-04-14-v1"

    items = repository.list(dataset="feature_dataset", limit=10)
    assert len(items) == 1
    assert items[0].dataset == "feature_dataset"
