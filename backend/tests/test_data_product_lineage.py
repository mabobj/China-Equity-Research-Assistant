from __future__ import annotations

from datetime import date

from app.schemas.factor import AlphaScore, FactorSnapshot, RiskScore, TriggerScore
from app.services.data_products.datasets.factor_snapshot_daily import (
    FactorSnapshotDailyDataset,
)
from app.services.data_products.repository import DataProductRepository


def test_repository_backed_data_product_preserves_lineage_metadata(tmp_path) -> None:
    repository = DataProductRepository(tmp_path / "daily_products")
    dataset = FactorSnapshotDailyDataset(repository=repository)
    payload = FactorSnapshot(
        symbol="600519.SH",
        as_of_date=date(2026, 4, 14),
        freshness_mode="computed",
        source_mode="snapshot",
        alpha_score=AlphaScore(total_score=62),
        trigger_score=TriggerScore(total_score=54, trigger_state="neutral"),
        risk_score=RiskScore(total_score=28),
    )

    saved = dataset.save("600519.SH", payload)
    loaded = dataset.load("600519.SH", as_of_date=date(2026, 4, 14))

    assert saved.dataset_version == "factor_snapshot_daily:2026-04-14:600519.SH:v1"
    assert saved.lineage_metadata is not None
    assert loaded is not None
    assert loaded.dataset_version == saved.dataset_version
    assert loaded.lineage_metadata is not None
    assert loaded.lineage_metadata.dataset_version == saved.dataset_version
