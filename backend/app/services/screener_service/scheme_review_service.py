"""Scheme-level run, stats, and feedback aggregation for factor-first screener."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from app.db.trade_review_store import TradeReviewStore
from app.schemas.screener import ScreenerBatchRecord, ScreenerSymbolResult
from app.schemas.screener_scheme_review import (
    ScreenerSchemeFeedbackSummary,
    ScreenerSchemeReviewStatsResponse,
    ScreenerSchemeRunSummary,
    ScreenerSchemeRunsResponse,
    ScreenerSchemeStats,
    ScreenerSchemeStatsResponse,
)
from app.services.screener_service.batch_service import ScreenerBatchService
from app.services.screener_service.scheme_service import ScreenerSchemeService


@dataclass
class _RelatedJournalStats:
    decision_snapshot_ids: set[str] = field(default_factory=set)
    decision_symbols: set[str] = field(default_factory=set)
    trade_ids: set[str] = field(default_factory=set)
    trade_symbols: set[str] = field(default_factory=set)
    review_ids: set[str] = field(default_factory=set)
    review_symbols: set[str] = field(default_factory=set)
    outcome_distribution: Counter[str] = field(default_factory=Counter)
    alignment_distribution: Counter[str] = field(default_factory=Counter)
    did_follow_plan_distribution: Counter[str] = field(default_factory=Counter)
    lesson_tag_distribution: Counter[str] = field(default_factory=Counter)


class ScreenerSchemeReviewService:
    """Provide read-only scheme review aggregations on top of existing stores."""

    def __init__(
        self,
        *,
        scheme_service: ScreenerSchemeService,
        batch_service: ScreenerBatchService,
        store: TradeReviewStore,
    ) -> None:
        self._scheme_service = scheme_service
        self._batch_service = batch_service
        self._store = store

    def list_scheme_runs(
        self,
        *,
        scheme_id: str,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int = 20,
    ) -> ScreenerSchemeRunsResponse:
        batches = self._load_scheme_batches(
            scheme_id=scheme_id,
            started_from=started_from,
            started_to=started_to,
            limit=limit,
        )
        items = [self._build_run_summary(batch) for batch in batches]
        return ScreenerSchemeRunsResponse(
            scheme_id=scheme_id,
            count=len(items),
            items=items,
        )

    def get_scheme_stats(
        self,
        *,
        scheme_id: str,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int = 100,
    ) -> ScreenerSchemeStatsResponse:
        batches = self._load_scheme_batches(
            scheme_id=scheme_id,
            started_from=started_from,
            started_to=started_to,
            limit=limit,
        )
        runs = [self._build_run_summary(batch) for batch in batches]
        symbol_set: set[str] = set()
        for batch in batches:
            symbol_set.update(self._symbols_for_batch(batch.batch_id))
        related = self._collect_related_journal_stats(symbol_set)
        scheme_versions = sorted(
            {item.scheme_version for item in runs if item.scheme_version},
            reverse=True,
        )

        stats = ScreenerSchemeStats(
            total_runs=len(runs),
            completed_runs=sum(1 for item in runs if item.status == "completed"),
            failed_runs=sum(1 for item in runs if item.status == "failed"),
            running_runs=sum(1 for item in runs if item.status == "running"),
            total_candidates=sum(item.result_count for item in runs),
            ready_count=sum(item.ready_count for item in runs),
            watch_count=sum(item.watch_count for item in runs),
            avoid_count=sum(item.avoid_count for item in runs),
            research_count=sum(item.research_count for item in runs),
            entered_research_count=len(
                related.decision_symbols | related.trade_symbols | related.review_symbols
            ),
            decision_snapshot_count=len(related.decision_snapshot_ids),
            trade_count=len(related.trade_ids),
            review_count=len(related.review_ids),
            outcome_distribution=dict(sorted(related.outcome_distribution.items())),
            scheme_versions=scheme_versions,
            warning_messages=[
                "方案级反馈当前基于方案批次股票与本地 journal 记录做符号级归因，后续可升级为显式外键归因。"
            ],
        )
        return ScreenerSchemeStatsResponse(
            scheme_id=scheme_id,
            started_from=started_from,
            started_to=started_to,
            stats=stats,
        )

    def get_scheme_feedback(
        self,
        *,
        scheme_id: str,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int = 100,
    ) -> ScreenerSchemeReviewStatsResponse:
        batches = self._load_scheme_batches(
            scheme_id=scheme_id,
            started_from=started_from,
            started_to=started_to,
            limit=limit,
        )
        symbol_set: set[str] = set()
        for batch in batches:
            symbol_set.update(self._symbols_for_batch(batch.batch_id))

        related = self._collect_related_journal_stats(symbol_set)
        feedback = ScreenerSchemeFeedbackSummary(
            linked_symbols=len(symbol_set),
            traded_symbols=len(related.trade_symbols),
            reviewed_symbols=len(related.review_symbols),
            aligned_trades=related.alignment_distribution.get("aligned", 0),
            partially_aligned_trades=related.alignment_distribution.get(
                "partially_aligned", 0
            ),
            not_aligned_trades=related.alignment_distribution.get("not_aligned", 0),
            did_follow_plan_distribution=dict(
                sorted(related.did_follow_plan_distribution.items())
            ),
            outcome_distribution=dict(sorted(related.outcome_distribution.items())),
            lesson_tag_distribution=dict(sorted(related.lesson_tag_distribution.items())),
            warning_messages=[
                "反馈统计当前基于方案命中股票与本地 trade/review 记录聚合，不代表严格的一对一策略归因。"
            ],
        )
        return ScreenerSchemeReviewStatsResponse(
            scheme_id=scheme_id,
            started_from=started_from,
            started_to=started_to,
            feedback=feedback,
        )

    def _load_scheme_batches(
        self,
        *,
        scheme_id: str,
        started_from: datetime | None,
        started_to: datetime | None,
        limit: int,
    ) -> list[ScreenerBatchRecord]:
        self._scheme_service.get_scheme(scheme_id)
        batches = [
            item
            for item in self._batch_service.list_batches()
            if item.scheme_id == scheme_id
        ]
        if started_from is not None:
            batches = [item for item in batches if item.started_at >= started_from]
        if started_to is not None:
            batches = [item for item in batches if item.started_at <= started_to]
        return batches[:limit]

    def _build_run_summary(self, batch: ScreenerBatchRecord) -> ScreenerSchemeRunSummary:
        results = self._batch_service.load_batch_results(
            batch.batch_id,
            hydrate_predictive=False,
        )
        related = self._collect_related_journal_stats({item.symbol for item in results})
        counts = self._count_result_buckets(results)
        return ScreenerSchemeRunSummary(
            batch_id=batch.batch_id,
            run_id=batch.run_id,
            trade_date=batch.trade_date,
            started_at=batch.started_at,
            finished_at=batch.finished_at,
            status=batch.status,
            scheme_version=batch.scheme_version,
            scheme_name=batch.scheme_name,
            universe_size=batch.universe_size,
            scanned_size=batch.scanned_size,
            result_count=len(results),
            ready_count=counts["ready"],
            watch_count=counts["watch"],
            avoid_count=counts["avoid"],
            research_count=counts["research"],
            decision_snapshot_count=len(related.decision_snapshot_ids),
            trade_count=len(related.trade_ids),
            review_count=len(related.review_ids),
            warning_messages=list(batch.warning_messages),
            failure_reason=batch.failure_reason,
        )

    def _symbols_for_batch(self, batch_id: str) -> set[str]:
        return {
            item.symbol
            for item in self._batch_service.load_batch_results(
                batch_id,
                hydrate_predictive=False,
            )
        }

    def _count_result_buckets(
        self,
        results: list[ScreenerSymbolResult],
    ) -> dict[str, int]:
        counts = {"ready": 0, "watch": 0, "avoid": 0, "research": 0}
        for item in results:
            list_type = item.list_type.upper()
            if list_type == "READY_TO_BUY":
                counts["ready"] += 1
            elif list_type in {"WATCH_PULLBACK", "WATCH_BREAKOUT"}:
                counts["watch"] += 1
            elif list_type == "RESEARCH_ONLY":
                counts["research"] += 1
            elif list_type == "AVOID":
                counts["avoid"] += 1
        return counts

    def _collect_related_journal_stats(
        self,
        symbols: set[str],
    ) -> _RelatedJournalStats:
        stats = _RelatedJournalStats()
        for symbol in symbols:
            for snapshot in self._store.list_decision_snapshots(symbol=symbol, limit=500):
                snapshot_id = str(snapshot["snapshot_id"])
                stats.decision_snapshot_ids.add(snapshot_id)
                stats.decision_symbols.add(symbol)
            for trade in self._store.list_trade_records(symbol=symbol, limit=500):
                trade_id = str(trade["trade_id"])
                stats.trade_ids.add(trade_id)
                stats.trade_symbols.add(symbol)
                alignment = str(trade.get("strategy_alignment") or "unknown")
                stats.alignment_distribution[alignment] += 1
            for review in self._store.list_review_records(symbol=symbol, limit=500):
                review_id = str(review["review_id"])
                stats.review_ids.add(review_id)
                stats.review_symbols.add(symbol)
                outcome = str(review.get("outcome_label") or "unknown")
                follow_plan = str(review.get("did_follow_plan") or "partial")
                stats.outcome_distribution[outcome] += 1
                stats.did_follow_plan_distribution[follow_plan] += 1
                for tag in review.get("lesson_tags", []):
                    stats.lesson_tag_distribution[str(tag)] += 1
        return stats
