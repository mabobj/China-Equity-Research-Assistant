"""Tests for daily data products and freshness policy."""

from __future__ import annotations

from datetime import date

from app.schemas.debate import DebateReviewReport
from app.schemas.review import StockReviewReport
from app.schemas.screener import ScreenerRunResponse
from app.schemas.strategy import StrategyPlan
from app.services.data_products.freshness import resolve_last_closed_trading_day
from app.services.data_products.datasets.debate_review_daily import DebateReviewDailyDataset
from app.services.data_products.datasets.review_report_daily import ReviewReportDailyDataset
from app.services.data_products.repository import DataProductRepository
from app.services.data_products.datasets.screener_snapshot_daily import (
    ScreenerSnapshotDailyDataset,
    ScreenerSnapshotParams,
)
from app.services.data_products.datasets.strategy_plan_daily import StrategyPlanDailyDataset
from .workflow_test_helpers import (
    build_debate_review_report,
    build_stock_review_report,
    build_strategy_plan,
)


def test_resolve_last_closed_trading_day_skips_weekend() -> None:
    assert resolve_last_closed_trading_day(today=date(2026, 3, 30)) == date(2026, 3, 27)


def test_repository_persists_entries_by_dataset_day_and_params(tmp_path) -> None:
    repository = DataProductRepository(root_dir=tmp_path)
    params_hash = repository.build_params_hash({"variant": "rule_based"})
    entry = repository.create_entry(
        dataset="decision_brief_daily",
        symbol="600519.SH",
        as_of_date=date(2024, 1, 2),
        params_hash=params_hash,
        freshness_mode="computed",
        source_mode="snapshot",
        payload={"symbol": "600519.SH"},
    )

    repository.save(entry)
    loaded = repository.load(
        dataset="decision_brief_daily",
        symbol="600519.SH",
        as_of_date=date(2024, 1, 2),
        params_hash=params_hash,
    )

    assert loaded is not None
    assert loaded.dataset == "decision_brief_daily"
    assert loaded.symbol == "600519.SH"
    assert loaded.payload["symbol"] == "600519.SH"


def test_screener_snapshot_daily_reuses_same_day_same_params(tmp_path) -> None:
    repository = DataProductRepository(root_dir=tmp_path)
    dataset = ScreenerSnapshotDailyDataset(repository=repository)
    params = ScreenerSnapshotParams(workflow_name="screener_run", max_symbols=50, top_n=10)
    payload = ScreenerRunResponse(
        as_of_date=date(2024, 1, 2),
        freshness_mode="computed",
        source_mode="pipeline",
        total_symbols=100,
        scanned_symbols=50,
        buy_candidates=[],
        watch_candidates=[],
        avoid_candidates=[],
        ready_to_buy_candidates=[],
        watch_pullback_candidates=[],
        watch_breakout_candidates=[],
        research_only_candidates=[],
    )

    dataset.save(run_date=date(2024, 1, 2), params=params, payload=payload)
    loaded = dataset.load(run_date=date(2024, 1, 2), params=params)

    assert loaded is not None
    assert loaded.payload.total_symbols == 100
    assert loaded.freshness_mode == "cache_hit"
    assert loaded.source_mode == "snapshot"


def test_review_report_daily_save_and_load(tmp_path) -> None:
    repository = DataProductRepository(root_dir=tmp_path)
    dataset = ReviewReportDailyDataset(repository=repository)
    payload: StockReviewReport = build_stock_review_report(symbol="600519.SH")

    saved = dataset.save("600519.SH", payload)
    loaded = dataset.load("600519.SH", as_of_date=saved.as_of_date)

    assert loaded is not None
    assert loaded.payload.symbol == "600519.SH"
    assert loaded.freshness_mode == "cache_hit"
    assert loaded.source_mode == "snapshot"


def test_strategy_plan_daily_save_and_load(tmp_path) -> None:
    repository = DataProductRepository(root_dir=tmp_path)
    dataset = StrategyPlanDailyDataset(repository=repository)
    payload: StrategyPlan = build_strategy_plan(symbol="600519.SH")

    saved = dataset.save("600519.SH", payload)
    loaded = dataset.load("600519.SH", as_of_date=saved.as_of_date)

    assert loaded is not None
    assert loaded.payload.symbol == "600519.SH"
    assert loaded.freshness_mode == "cache_hit"
    assert loaded.source_mode == "snapshot"


def test_debate_review_daily_separates_llm_and_rule_variants(tmp_path) -> None:
    repository = DataProductRepository(root_dir=tmp_path)
    dataset = DebateReviewDailyDataset(repository=repository)
    payload: DebateReviewReport = build_debate_review_report(symbol="600519.SH")

    dataset.save("600519.SH", payload, variant="rule_based")
    assert dataset.load(
        "600519.SH",
        as_of_date=payload.as_of_date,
        variant="llm",
    ) is None
    llm_payload = payload.model_copy(
        update={
            "runtime_mode": "llm",
            "runtime_mode_requested": "llm",
            "runtime_mode_effective": "llm",
        }
    )
    dataset.save("600519.SH", llm_payload, variant="llm")

    loaded_llm = dataset.load(
        "600519.SH",
        as_of_date=payload.as_of_date,
        variant="llm",
    )
    loaded_rule = dataset.load(
        "600519.SH",
        as_of_date=payload.as_of_date,
        variant="rule_based",
    )

    assert loaded_llm is not None
    assert loaded_rule is not None
    assert loaded_llm.payload.runtime_mode == "llm"
    assert loaded_rule.payload.runtime_mode == "rule_based"
