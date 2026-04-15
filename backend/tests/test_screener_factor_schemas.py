from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.schemas.lineage import LineageMetadata
from app.schemas.screener_factors import (
    ScreenerAtomicFactors,
    ScreenerCompositeScore,
    ScreenerCrossSectionFactors,
    ScreenerFactorSnapshot,
    ScreenerProcessMetrics,
    ScreenerRawInputs,
    ScreenerSelectionDecision,
    build_screener_dataset_version,
)


def test_build_screener_dataset_version_is_deterministic() -> None:
    version = build_screener_dataset_version(
        dataset="screener_factor_snapshot_daily",
        as_of_date=date(2026, 4, 16),
        symbol="000001.SZ",
    )

    assert version == "screener_factor_snapshot_daily:2026-04-16:000001.SZ:v1"


def test_screener_factor_snapshot_accepts_nested_models() -> None:
    snapshot = ScreenerFactorSnapshot(
        symbol="000001.SZ",
        as_of_date=date(2026, 4, 16),
        dataset_version=build_screener_dataset_version(
            dataset="screener_factor_snapshot_daily",
            as_of_date=date(2026, 4, 16),
            symbol="000001.SZ",
        ),
        generated_at=datetime(2026, 4, 16, 9, 30, 0),
        provider_used="tdx_api",
        source_mode="local_plus_provider",
        freshness_mode="cache_preferred",
        raw_inputs=ScreenerRawInputs(
            symbol="000001.SZ",
            name="PingAnBank",
            market="A",
            board="MainBoard",
            industry="Bank",
            latest_trade_date=date(2026, 4, 16),
            is_st=False,
            is_suspended=False,
            bars_count=240,
            latest_close=12.34,
            latest_amount=1_250_000_000.0,
        ),
        process_metrics=ScreenerProcessMetrics(
            ma_20=12.10,
            ma_60=11.58,
            ma_20_slope=0.038,
            close_percentile_60d=0.82,
            return_20d=0.11,
            atr_20_pct=0.029,
            amount_ratio_5d_20d=1.24,
            support_level_20d=11.95,
            resistance_level_20d=12.58,
        ),
        atomic_factors=ScreenerAtomicFactors(
            basic_universe_eligibility=True,
            close_above_ma20=True,
            close_above_ma60=True,
            ma20_above_ma60=True,
            trend_state_basic="up",
            breakout_ready=True,
            liquidity_pass=True,
        ),
        cross_section_factors=ScreenerCrossSectionFactors(
            universe_size=5100,
            amount_rank_pct=0.91,
            return_20d_rank_pct=0.84,
            trend_score_raw=78.5,
            trend_score_rank_pct=0.86,
            industry_relative_strength_rank_pct=0.72,
            trend_persistence_5d=0.80,
        ),
        composite_score=ScreenerCompositeScore(
            screener_score=81,
            alpha_score=79,
            trigger_score=76,
            risk_score=34,
            list_type="BUY_CANDIDATE",
            v2_list_type="READY_TO_BUY",
            action_now="BUY_NOW",
            quality_penalty_applied=False,
        ),
        selection_decision=ScreenerSelectionDecision(
            list_type="BUY_CANDIDATE",
            v2_list_type="READY_TO_BUY",
            action_now="BUY_NOW",
            selection_reasons=["trend_confirmed", "liquidity_ok"],
            top_positive_factors=["positive_return_20d", "close_near_range_high"],
            risk_notes=["requires_deep_review_for_financial_quality"],
            short_reason="trend_and_position_are_constructive",
        ),
        lineage_metadata=LineageMetadata(
            dataset="screener_factor_snapshot_daily",
            dataset_version="screener_factor_snapshot_daily:2026-04-16:000001.SZ:v1",
            schema_version=1,
            generated_at=datetime(2026, 4, 16, 9, 30, 0),
            as_of_date=date(2026, 4, 16),
            symbol="000001.SZ",
            dependencies=[],
            warning_messages=[],
        ),
    )

    assert snapshot.schema_version == 1
    assert snapshot.raw_inputs is not None
    assert snapshot.raw_inputs.symbol == "000001.SZ"
    assert snapshot.composite_score is not None
    assert snapshot.composite_score.v2_list_type == "READY_TO_BUY"
    assert snapshot.selection_decision is not None
    assert snapshot.selection_decision.selection_reasons == ["trend_confirmed", "liquidity_ok"]


def test_screener_process_metrics_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ScreenerProcessMetrics(
            ma_20=12.0,
            unexpected_metric=1.0,
        )
