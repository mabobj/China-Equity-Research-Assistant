"""Batch-level cross-sectional enrichment for screener factor snapshots."""

from __future__ import annotations

import pandas as pd

from app.schemas.screener_factors import ScreenerFactorSnapshot


class CrossSectionFactorService:
    """Enrich screener factor snapshots with same-batch rank features."""

    def enrich_snapshots(
        self,
        snapshots: list[ScreenerFactorSnapshot],
    ) -> list[ScreenerFactorSnapshot]:
        if not snapshots:
            return []

        frame = pd.DataFrame(
            [
                {
                    "symbol": snapshot.symbol,
                    "industry_bucket": (
                        snapshot.cross_section_factors.industry_bucket
                        or (snapshot.raw_inputs.industry if snapshot.raw_inputs else None)
                    ),
                    "amount_20d": snapshot.process_metrics.avg_amount_20d,
                    "return_20d": snapshot.process_metrics.return_20d,
                    "trend_score_raw": snapshot.cross_section_factors.trend_score_raw,
                    "atr_20_pct": snapshot.process_metrics.atr_20_pct,
                }
                for snapshot in snapshots
            ]
        )

        amount_rank = _rank_percentile(frame, "amount_20d")
        return_rank = _rank_percentile(frame, "return_20d")
        trend_rank = _rank_percentile(frame, "trend_score_raw")
        atr_rank = _rank_percentile(frame, "atr_20_pct")
        industry_rank = _build_industry_relative_strength_rank(frame)
        universe_size = len(snapshots)

        enriched: list[ScreenerFactorSnapshot] = []
        for snapshot in snapshots:
            current = snapshot.cross_section_factors
            update = current.model_copy(
                update={
                    "universe_size": universe_size,
                    "industry_bucket": current.industry_bucket
                    or (snapshot.raw_inputs.industry if snapshot.raw_inputs else None),
                    "amount_rank_pct": amount_rank.get(snapshot.symbol),
                    "return_20d_rank_pct": return_rank.get(snapshot.symbol),
                    "trend_score_rank_pct": trend_rank.get(snapshot.symbol),
                    "atr_pct_rank_pct": atr_rank.get(snapshot.symbol),
                    "industry_relative_strength_rank_pct": industry_rank.get(snapshot.symbol),
                }
            )
            enriched.append(
                snapshot.model_copy(
                    update={"cross_section_factors": update},
                )
            )
        return enriched


def _rank_percentile(frame: pd.DataFrame, column: str) -> dict[str, float | None]:
    ranked = frame[column].rank(method="average", pct=True)
    results: dict[str, float | None] = {}
    for row, value in zip(frame.itertuples(), ranked, strict=False):
        if pd.isna(value):
            results[row.symbol] = None
        else:
            results[row.symbol] = float(value)
    return results


def _build_industry_relative_strength_rank(frame: pd.DataFrame) -> dict[str, float | None]:
    valid = frame.dropna(subset=["industry_bucket", "return_20d"])
    if valid.empty:
        return {row.symbol: None for row in frame.itertuples()}

    industry_strength = (
        valid.groupby("industry_bucket", as_index=True)["return_20d"]
        .mean()
        .rank(method="average", pct=True)
    )
    results: dict[str, float | None] = {}
    for row in frame.itertuples():
        if row.industry_bucket is None or row.industry_bucket not in industry_strength.index:
            results[row.symbol] = None
        else:
            results[row.symbol] = float(industry_strength[row.industry_bucket])
    return results
