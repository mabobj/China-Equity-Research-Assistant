"""选股器 pipeline。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging
from time import perf_counter
from typing import TYPE_CHECKING, Literal, Optional

from app.schemas.market_data import DailyBar, DailyBarResponse, UniverseItem
from app.schemas.research_inputs import FinancialSummary
from app.schemas.screener_factors import ScreenerFactorSnapshot
from app.schemas.screener import ScreenerCandidate, ScreenerRunResponse
from app.services.data_service.exceptions import DataServiceError
from app.services.data_service.market_data_service import MarketDataService
from app.services.factor_service.base import FactorBuildInputs
from app.services.screener_service.filters import (
    has_abnormal_price_data,
    has_acceptable_liquidity,
    has_sufficient_daily_bars,
)
from app.services.screener_service.scoring import (
    apply_score_to_screener_factor_snapshot,
    score_factor_snapshot,
    score_screener_factor_snapshot,
    score_technical_snapshot,
)
from app.services.screener_service.texts import normalize_candidate_display_fields
from app.services.screener_service.universe import load_scan_universe

if TYPE_CHECKING:
    from app.services.data_products.datasets.screener_factor_snapshot_daily import (
        ScreenerFactorSnapshotDailyDataset,
    )
    from app.services.factor_service.snapshot import FactorSnapshotService
    from app.services.feature_service.screener_factor_service import ScreenerFactorService
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )
    from app.services.lineage_service.lineage_service import LineageService
    from app.services.prediction_service.prediction_service import PredictionService
    from app.services.screener_service.cross_section_factor_service import (
        CrossSectionFactorService,
    )

logger = logging.getLogger(__name__)
_RULE_VERSION = "screener_workflow_v1"
_RULE_SUMMARY = "基于趋势评分、因子快照与风险约束的规则初筛。"
_QUALITY_STATUS = Literal["ok", "warning", "degraded", "failed"]
_QUALITY_WEIGHT = {
    "ok": 1.00,
    "warning": 0.95,
    "degraded": 0.85,
    "failed": 0.70,
}


class ScreenerPipeline:
    """执行全市场规则初筛。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        technical_analysis_service: TechnicalAnalysisService,
        factor_snapshot_service: Optional[FactorSnapshotService] = None,
        screener_factor_service: Optional["ScreenerFactorService"] = None,
        cross_section_factor_service: Optional["CrossSectionFactorService"] = None,
        screener_factor_snapshot_daily: Optional[
            "ScreenerFactorSnapshotDailyDataset"
        ] = None,
        prediction_service: Optional["PredictionService"] = None,
        lineage_service: Optional["LineageService"] = None,
        lookback_days: int = 400,
        progress_log_interval: int = 100,
        batch_daily_bar_provider_priority: tuple[str, ...] = (
            "mootdx",
            "baostock",
            "akshare",
        ),
        batch_scan_max_workers: int = 4,
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service
        self._factor_snapshot_service = factor_snapshot_service
        self._screener_factor_service = screener_factor_service
        self._cross_section_factor_service = cross_section_factor_service
        self._screener_factor_snapshot_daily = screener_factor_snapshot_daily
        self._prediction_service = prediction_service
        self._lineage_service = lineage_service
        self._lookback_days = max(lookback_days, 180)
        self._progress_log_interval = max(progress_log_interval, 1)
        self._batch_daily_bar_provider_priority = batch_daily_bar_provider_priority
        self._batch_scan_max_workers = max(batch_scan_max_workers, 1)

    def run_screener(
        self,
        max_symbols: Optional[int] = None,
        top_n: Optional[int] = None,
        force_refresh: bool = False,
        scan_items: Optional[list[UniverseItem]] = None,
        total_symbols_override: Optional[int] = None,
        run_context: Optional[dict[str, object]] = None,
    ) -> ScreenerRunResponse:
        started_at = perf_counter()
        run_context = run_context or {}
        run_context.setdefault("screener_factor_snapshot_refs", [])
        run_id = _stringify_log_value(run_context.get("run_id"))
        workflow_name = _stringify_log_value(run_context.get("workflow_name")) or "screener_run"
        batch_size = _stringify_log_value(run_context.get("batch_size"))
        cursor_start_symbol = _stringify_log_value(run_context.get("cursor_start_symbol"))
        cursor_start_index = _stringify_log_value(run_context.get("cursor_start_index"))

        with self._market_data_service.session_scope():
            if scan_items is None:
                total_symbols, scan_items = load_scan_universe(
                    market_data_service=self._market_data_service,
                    max_symbols=max_symbols,
                )
            else:
                total_symbols = (
                    total_symbols_override
                    if total_symbols_override is not None
                    else len(scan_items)
                )
            scanned_symbols = len(scan_items)
            candidates: list[ScreenerCandidate] = []
            failed_placeholders: list[ScreenerCandidate] = []
            prepared_candidates: list[_PreparedCandidate] = []
            latest_as_of_date: Optional[date] = None
            skipped_symbols = 0
            lookback_start_date = (
                date.today() - timedelta(days=self._lookback_days)
            ).isoformat()

            logger.info(
                "event=screener.pipeline.started run_id=%s workflow=%s batch_size=%s total_symbols=%s scanned_symbols=%s top_n=%s lookback_start_date=%s force_refresh=%s cursor_start_symbol=%s cursor_start_index=%s scan_max_workers=%s",
                run_id,
                workflow_name,
                batch_size,
                total_symbols,
                scanned_symbols,
                top_n,
                lookback_start_date,
                force_refresh,
                cursor_start_symbol,
                cursor_start_index,
                self._batch_scan_max_workers,
            )

            processed_symbols = 0
            max_workers = min(self._batch_scan_max_workers, max(scanned_symbols, 1))
            if max_workers == 1:
                for item in scan_items:
                    scan_result = self._scan_one_symbol(
                        item=item,
                        start_date=lookback_start_date,
                        force_refresh=force_refresh,
                        run_context=run_context,
                    )
                    processed_symbols += 1
                    if scan_result is None:
                        skipped_symbols += 1
                    else:
                        if scan_result.failed_placeholder is not None:
                            failed_placeholders.append(scan_result.failed_placeholder)
                        if scan_result.prepared_candidate is not None:
                            prepared_candidates.append(scan_result.prepared_candidate)
                        if scan_result.candidate is not None:
                            candidates.append(scan_result.candidate)
                        if latest_as_of_date is None or scan_result.as_of_date > latest_as_of_date:
                            latest_as_of_date = scan_result.as_of_date
                    self._log_progress(
                        index=processed_symbols,
                        total=scanned_symbols,
                        item=item,
                        candidates=candidates,
                        skipped_symbols=skipped_symbols,
                        started_at=started_at,
                        run_context=run_context,
                    )
            else:
                with ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix="screener-scan",
                ) as executor:
                    future_map = {
                        executor.submit(
                            self._scan_one_symbol,
                            item=item,
                            start_date=lookback_start_date,
                            force_refresh=force_refresh,
                            run_context=run_context,
                        ): item
                        for item in scan_items
                    }
                    for future in as_completed(future_map):
                        item = future_map[future]
                        processed_symbols += 1
                        try:
                            scan_result = future.result()
                        except Exception:
                            logger.exception(
                                "event=screener.symbol.unhandled_error run_id=%s workflow=%s symbol=%s",
                                run_id,
                                workflow_name,
                                item.symbol,
                            )
                            scan_result = None
                        if scan_result is None:
                            skipped_symbols += 1
                        else:
                            if scan_result.failed_placeholder is not None:
                                failed_placeholders.append(scan_result.failed_placeholder)
                            if scan_result.prepared_candidate is not None:
                                prepared_candidates.append(scan_result.prepared_candidate)
                            if scan_result.candidate is not None:
                                candidates.append(scan_result.candidate)
                            if latest_as_of_date is None or scan_result.as_of_date > latest_as_of_date:
                                latest_as_of_date = scan_result.as_of_date
                        self._log_progress(
                            index=processed_symbols,
                            total=scanned_symbols,
                            item=item,
                            candidates=candidates,
                            skipped_symbols=skipped_symbols,
                            started_at=started_at,
                            run_context=run_context,
                        )

        if prepared_candidates:
            candidates.extend(
                self._build_candidates_from_prepared(
                    prepared_candidates=prepared_candidates,
                    max_symbols=max_symbols,
                    top_n=top_n,
                    run_context=run_context,
                )
            )

        ready_to_buy_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "READY_TO_BUY"],
            top_n=top_n,
        )
        watch_pullback_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "WATCH_PULLBACK"],
            top_n=top_n,
        )
        watch_breakout_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "WATCH_BREAKOUT"],
            top_n=top_n,
        )
        research_only_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "RESEARCH_ONLY"],
            top_n=top_n,
        )
        buy_candidates = list(ready_to_buy_candidates)
        watch_candidates = _rank_candidates(
            [
                item
                for item in candidates
                if item.v2_list_type in {"WATCH_PULLBACK", "WATCH_BREAKOUT", "RESEARCH_ONLY"}
            ],
            top_n=top_n,
        )
        avoid_candidates = _rank_candidates(
            [item for item in candidates if item.v2_list_type == "AVOID"],
            top_n=top_n,
        )
        avoid_candidates = _append_failed_placeholders(
            ranked_avoid_candidates=avoid_candidates,
            failed_placeholders=failed_placeholders,
        )

        logger.info(
            "event=screener.pipeline.completed run_id=%s workflow=%s scanned_symbols=%s produced_candidates=%s skipped_symbols=%s ready_count=%s watch_count=%s avoid_count=%s elapsed_ms=%s",
            run_id,
            workflow_name,
            scanned_symbols,
            len(candidates),
            skipped_symbols,
            len(ready_to_buy_candidates),
            len(watch_candidates),
            len(avoid_candidates),
            int((perf_counter() - started_at) * 1000),
        )

        return ScreenerRunResponse(
            as_of_date=latest_as_of_date or date.today(),
            freshness_mode="force_refreshed" if force_refresh else "cache_preferred",
            source_mode="pipeline",
            total_symbols=total_symbols,
            scanned_symbols=scanned_symbols,
            buy_candidates=buy_candidates,
            watch_candidates=watch_candidates,
            avoid_candidates=avoid_candidates,
            ready_to_buy_candidates=ready_to_buy_candidates,
            watch_pullback_candidates=watch_pullback_candidates,
            watch_breakout_candidates=watch_breakout_candidates,
            research_only_candidates=research_only_candidates,
        )

    def _scan_one_symbol(
        self,
        item: UniverseItem,
        start_date: str,
        force_refresh: bool,
        run_context: Optional[dict[str, object]] = None,
    ) -> Optional["_ScanResult"]:
        run_context = run_context or {}
        run_id = _stringify_log_value(run_context.get("run_id"))
        workflow_name = _stringify_log_value(run_context.get("workflow_name")) or "screener_run"
        symbol_started_at = perf_counter()
        bars_elapsed_ms = 0
        financial_elapsed_ms = 0
        announcement_elapsed_ms = 0
        prediction_elapsed_ms = 0
        bars_quality: _QUALITY_STATUS = "warning"
        financial_quality: _QUALITY_STATUS = "warning"
        announcement_quality: _QUALITY_STATUS = "warning"
        technical_snapshot = None

        try:
            bars_started_at = perf_counter()
            daily_bars_response = self._load_daily_bars_for_scan(
                symbol=item.symbol,
                start_date=start_date,
                force_refresh=force_refresh,
            )
        except DataServiceError:
            logger.info(
                "event=screener.symbol.completed run_id=%s workflow=%s symbol=%s elapsed_ms=%s bars_elapsed_ms=%s financial_elapsed_ms=%s announcement_elapsed_ms=%s prediction_elapsed_ms=%s outcome=skipped reason=bars_load_failed",
                run_id,
                workflow_name,
                item.symbol,
                int((perf_counter() - symbol_started_at) * 1000),
                bars_elapsed_ms,
                financial_elapsed_ms,
                announcement_elapsed_ms,
                prediction_elapsed_ms,
            )
            return None
        bars_elapsed_ms = int((perf_counter() - bars_started_at) * 1000)

        bars_quality = _normalize_quality_status(daily_bars_response.quality_status)
        if bars_quality == "failed":
            failed_placeholder = _build_failed_placeholder_for_bars(
                item=item,
                response=daily_bars_response,
                quality_note="行情数据质量失败，未纳入候选排序。",
            )
            logger.info(
                "event=screener.symbol.completed run_id=%s workflow=%s symbol=%s elapsed_ms=%s bars_elapsed_ms=%s financial_elapsed_ms=%s announcement_elapsed_ms=%s prediction_elapsed_ms=%s outcome=failed_placeholder reason=bars_quality_failed bars_quality=%s financial_quality=%s announcement_quality=%s list_type=%s screener_score=%s fail_reason=%s",
                run_id,
                workflow_name,
                item.symbol,
                int((perf_counter() - symbol_started_at) * 1000),
                bars_elapsed_ms,
                financial_elapsed_ms,
                announcement_elapsed_ms,
                prediction_elapsed_ms,
                bars_quality,
                financial_quality,
                announcement_quality,
                failed_placeholder.v2_list_type,
                failed_placeholder.screener_score,
                failed_placeholder.fail_reason,
            )
            return _ScanResult(
                as_of_date=_resolve_as_of_date(daily_bars_response),
                candidate=None,
                failed_placeholder=failed_placeholder,
            )

        daily_bars = daily_bars_response.bars
        if not has_sufficient_daily_bars(daily_bars_response):
            logger.info(
                "event=screener.symbol.completed run_id=%s workflow=%s symbol=%s elapsed_ms=%s bars_elapsed_ms=%s financial_elapsed_ms=%s announcement_elapsed_ms=%s prediction_elapsed_ms=%s outcome=skipped reason=insufficient_daily_bars bars_quality=%s",
                run_id,
                workflow_name,
                item.symbol,
                int((perf_counter() - symbol_started_at) * 1000),
                bars_elapsed_ms,
                financial_elapsed_ms,
                announcement_elapsed_ms,
                prediction_elapsed_ms,
                bars_quality,
            )
            return None
        if not has_acceptable_liquidity(daily_bars_response):
            logger.info(
                "event=screener.symbol.completed run_id=%s workflow=%s symbol=%s elapsed_ms=%s bars_elapsed_ms=%s financial_elapsed_ms=%s announcement_elapsed_ms=%s prediction_elapsed_ms=%s outcome=skipped reason=insufficient_liquidity bars_quality=%s",
                run_id,
                workflow_name,
                item.symbol,
                int((perf_counter() - symbol_started_at) * 1000),
                bars_elapsed_ms,
                financial_elapsed_ms,
                announcement_elapsed_ms,
                prediction_elapsed_ms,
                bars_quality,
            )
            return None
        if has_abnormal_price_data(daily_bars_response):
            logger.info(
                "event=screener.symbol.completed run_id=%s workflow=%s symbol=%s elapsed_ms=%s bars_elapsed_ms=%s financial_elapsed_ms=%s announcement_elapsed_ms=%s prediction_elapsed_ms=%s outcome=skipped reason=abnormal_price_data bars_quality=%s",
                run_id,
                workflow_name,
                item.symbol,
                int((perf_counter() - symbol_started_at) * 1000),
                bars_elapsed_ms,
                financial_elapsed_ms,
                announcement_elapsed_ms,
                prediction_elapsed_ms,
                bars_quality,
            )
            return None

        try:
            build_snapshot = getattr(
                self._technical_analysis_service,
                "build_snapshot_from_bars",
                None,
            )
            if callable(build_snapshot):
                technical_snapshot = build_snapshot(
                    symbol=item.symbol,
                    bars=daily_bars,
                )
            else:
                technical_snapshot = self._technical_analysis_service.get_technical_snapshot(
                    item.symbol,
                )
        except DataServiceError:
            logger.info(
                "event=screener.symbol.completed run_id=%s workflow=%s symbol=%s elapsed_ms=%s bars_elapsed_ms=%s financial_elapsed_ms=%s announcement_elapsed_ms=%s prediction_elapsed_ms=%s outcome=skipped reason=technical_snapshot_failed bars_quality=%s",
                run_id,
                workflow_name,
                item.symbol,
                int((perf_counter() - symbol_started_at) * 1000),
                bars_elapsed_ms,
                financial_elapsed_ms,
                announcement_elapsed_ms,
                prediction_elapsed_ms,
                bars_quality,
            )
            return None

        financial_started_at = perf_counter()
        financial_summary, financial_quality = _safe_get_financial_summary(
            self._market_data_service,
            item.symbol,
            force_refresh=force_refresh,
        )
        financial_elapsed_ms = int((perf_counter() - financial_started_at) * 1000)
        announcement_started_at = perf_counter()
        recent_announcements, announcement_quality = _safe_get_recent_announcements(
            self._market_data_service,
            item.symbol,
            technical_snapshot.as_of_date,
            force_refresh=force_refresh,
        )
        announcement_elapsed_ms = int((perf_counter() - announcement_started_at) * 1000)
        screener_factor_snapshot = None
        if self._screener_factor_service is not None:
            screener_factor_snapshot = self._screener_factor_service.build_snapshot_from_bars(
                symbol=item.symbol,
                bars=daily_bars,
                name=item.name,
                list_status=item.status,
                provider_used=_resolve_provider_used(daily_bars_response),
                source_mode=getattr(daily_bars_response, "source_mode", None),
                freshness_mode=getattr(daily_bars_response, "freshness_mode", None),
            )

        if screener_factor_snapshot is not None:
            prediction_started_at = perf_counter()
            prediction_snapshot = self._try_get_prediction_snapshot(
                symbol=item.symbol,
                as_of_date=technical_snapshot.as_of_date,
            )
            prediction_elapsed_ms = int((perf_counter() - prediction_started_at) * 1000)
            logger.info(
                "event=screener.symbol.completed run_id=%s workflow=%s symbol=%s elapsed_ms=%s bars_elapsed_ms=%s financial_elapsed_ms=%s announcement_elapsed_ms=%s prediction_elapsed_ms=%s outcome=prepared_candidate bars_quality=%s financial_quality=%s announcement_quality=%s",
                run_id,
                workflow_name,
                item.symbol,
                int((perf_counter() - symbol_started_at) * 1000),
                bars_elapsed_ms,
                financial_elapsed_ms,
                announcement_elapsed_ms,
                prediction_elapsed_ms,
                bars_quality,
                financial_quality,
                announcement_quality,
            )
            return _ScanResult(
                as_of_date=technical_snapshot.as_of_date,
                candidate=None,
                failed_placeholder=None,
                prepared_candidate=_PreparedCandidate(
                    item=item,
                    technical_snapshot=technical_snapshot,
                    screener_factor_snapshot=screener_factor_snapshot,
                    prediction_snapshot=prediction_snapshot,
                    bars_quality=bars_quality,
                    financial_quality=financial_quality,
                    announcement_quality=announcement_quality,
                ),
            )

        if self._factor_snapshot_service is not None:
            factor_snapshot = self._factor_snapshot_service.build_from_inputs(
                FactorBuildInputs(
                    symbol=item.symbol,
                    technical_snapshot=technical_snapshot,
                    daily_bars=daily_bars,
                    financial_summary=financial_summary,
                    announcements=recent_announcements,
                )
            )
            score_result = score_factor_snapshot(
                factor_snapshot=factor_snapshot,
                technical_snapshot=technical_snapshot,
            )
        else:
            score_result = score_technical_snapshot(technical_snapshot)

        quality_gate = _apply_quality_gate(
            origin_v2_list_type=score_result.v2_list_type,
            origin_screener_score=score_result.screener_score,
            bars_quality=bars_quality,
            financial_quality=financial_quality,
            announcement_quality=announcement_quality,
        )

        prediction_started_at = perf_counter()
        prediction_snapshot = self._try_get_prediction_snapshot(
            symbol=item.symbol,
            as_of_date=technical_snapshot.as_of_date,
        )
        prediction_elapsed_ms = int((perf_counter() - prediction_started_at) * 1000)
        candidate = _build_candidate(
            item=item,
            technical_snapshot=technical_snapshot,
            score_result=score_result,
            prediction_snapshot=prediction_snapshot,
            target_v2_list_type=quality_gate.target_v2_list_type,
            target_screener_score=quality_gate.target_screener_score,
            bars_quality=bars_quality,
            financial_quality=financial_quality,
            announcement_quality=announcement_quality,
            quality_penalty_applied=quality_gate.quality_penalty_applied,
            quality_note=quality_gate.quality_note,
        )
        logger.info(
            "event=screener.symbol.completed run_id=%s workflow=%s symbol=%s elapsed_ms=%s bars_elapsed_ms=%s financial_elapsed_ms=%s announcement_elapsed_ms=%s prediction_elapsed_ms=%s outcome=candidate bars_quality=%s financial_quality=%s announcement_quality=%s list_type=%s screener_score=%s predictive_model_version=%s",
            run_id,
            workflow_name,
            item.symbol,
            int((perf_counter() - symbol_started_at) * 1000),
            bars_elapsed_ms,
            financial_elapsed_ms,
            announcement_elapsed_ms,
            prediction_elapsed_ms,
            bars_quality,
            financial_quality,
            announcement_quality,
            candidate.v2_list_type,
            candidate.screener_score,
            candidate.predictive_model_version,
        )
        return _ScanResult(
            as_of_date=technical_snapshot.as_of_date,
            candidate=candidate,
            failed_placeholder=None,
            prepared_candidate=None,
        )

    def _build_candidates_from_prepared(
        self,
        *,
        prepared_candidates: list["_PreparedCandidate"],
        max_symbols: int | None,
        top_n: int | None,
        run_context: dict[str, object],
    ) -> list[ScreenerCandidate]:
        snapshots = [item.screener_factor_snapshot for item in prepared_candidates]
        if self._cross_section_factor_service is not None:
            enriched_snapshots = self._cross_section_factor_service.enrich_snapshots(snapshots)
        else:
            enriched_snapshots = snapshots
        snapshot_by_symbol = {
            snapshot.symbol: snapshot for snapshot in enriched_snapshots
        }
        snapshot_params = _build_screener_factor_snapshot_params(
            run_context=run_context,
            max_symbols=max_symbols,
            top_n=top_n,
        )

        built_candidates: list[ScreenerCandidate] = []
        for prepared in prepared_candidates:
            screener_factor_snapshot = snapshot_by_symbol[prepared.item.symbol]
            score_result = score_screener_factor_snapshot(
                screener_factor_snapshot=screener_factor_snapshot,
                technical_snapshot=prepared.technical_snapshot,
            )
            quality_gate = _apply_quality_gate(
                origin_v2_list_type=score_result.v2_list_type,
                origin_screener_score=score_result.screener_score,
                bars_quality=prepared.bars_quality,
                financial_quality=prepared.financial_quality,
                announcement_quality=prepared.announcement_quality,
            )
            evaluated_snapshot = apply_score_to_screener_factor_snapshot(
                screener_factor_snapshot=screener_factor_snapshot,
                score_result=score_result,
                target_v2_list_type=quality_gate.target_v2_list_type,
                target_screener_score=quality_gate.target_screener_score,
                quality_penalty_applied=quality_gate.quality_penalty_applied,
                quality_note=quality_gate.quality_note,
            )
            self._persist_screener_factor_snapshot(
                symbol=prepared.item.symbol,
                snapshot=evaluated_snapshot,
                params=snapshot_params,
                run_context=run_context,
            )
            candidate = _build_candidate(
                item=prepared.item,
                technical_snapshot=prepared.technical_snapshot,
                score_result=score_result,
                prediction_snapshot=prepared.prediction_snapshot,
                target_v2_list_type=quality_gate.target_v2_list_type,
                target_screener_score=quality_gate.target_screener_score,
                bars_quality=prepared.bars_quality,
                financial_quality=prepared.financial_quality,
                announcement_quality=prepared.announcement_quality,
                quality_penalty_applied=quality_gate.quality_penalty_applied,
                quality_note=quality_gate.quality_note,
                screener_factor_snapshot=evaluated_snapshot,
            )
            built_candidates.append(candidate)
        return built_candidates

    def _persist_screener_factor_snapshot(
        self,
        *,
        symbol: str,
        snapshot: ScreenerFactorSnapshot,
        params,
        run_context: dict[str, object],
    ) -> None:
        if self._screener_factor_snapshot_daily is None:
            return
        try:
            saved = self._screener_factor_snapshot_daily.save(
                symbol,
                params=params,
                payload=snapshot,
            )
            if self._lineage_service is not None:
                self._lineage_service.register_data_product(saved)
            snapshot_refs = run_context.setdefault("screener_factor_snapshot_refs", [])
            if isinstance(snapshot_refs, list):
                snapshot_refs.append(
                    _build_lineage_ref_payload(saved)
                )
        except Exception:
            logger.exception(
                "event=screener.factor_snapshot.persist_failed symbol=%s dataset_version=%s",
                symbol,
                snapshot.dataset_version,
            )

    def _try_get_prediction_snapshot(self, *, symbol: str, as_of_date: date):
        if self._prediction_service is None:
            return None
        try:
            return self._prediction_service.get_symbol_prediction(
                symbol=symbol,
                as_of_date=as_of_date,
                build_feature_dataset=False,
            )
        except Exception:
            return None

    def _load_daily_bars_for_scan(
        self,
        *,
        symbol: str,
        start_date: str,
        force_refresh: bool,
    ) -> DailyBarResponse:
        try:
            return self._market_data_service.get_daily_bars(
                symbol,
                start_date=start_date,
                force_refresh=force_refresh,
                allow_remote_sync=False,
                provider_names=self._batch_daily_bar_provider_priority,
            )
        except TypeError:
            try:
                return self._market_data_service.get_daily_bars(
                    symbol,
                    start_date=start_date,
                    force_refresh=force_refresh,
                    provider_names=self._batch_daily_bar_provider_priority,
                )
            except TypeError:
                return self._market_data_service.get_daily_bars(
                    symbol,
                    start_date=start_date,
                )

    def _log_progress(
        self,
        index: int,
        total: int,
        item: UniverseItem,
        candidates: list[ScreenerCandidate],
        skipped_symbols: int,
        started_at: float,
        run_context: Optional[dict[str, object]] = None,
    ) -> None:
        if total <= 0:
            return
        if index != total and index % self._progress_log_interval != 0:
            return
        run_context = run_context or {}
        logger.info(
            "event=screener.run.heartbeat run_id=%s workflow=%s processed_symbols=%s total_symbols=%s last_symbol=%s produced_candidates=%s skipped_symbols=%s elapsed_ms=%s",
            _stringify_log_value(run_context.get("run_id")),
            _stringify_log_value(run_context.get("workflow_name")) or "screener_run",
            index,
            total,
            item.symbol,
            len(candidates),
            skipped_symbols,
            int((perf_counter() - started_at) * 1000),
        )


@dataclass(frozen=True)
class _ScanResult:
    """内部扫描结果。"""

    as_of_date: date
    candidate: Optional[ScreenerCandidate]
    failed_placeholder: Optional[ScreenerCandidate]
    prepared_candidate: Optional["_PreparedCandidate"] = None


@dataclass(frozen=True)
class _PreparedCandidate:
    """Prepared screener candidate awaiting batch-level enrichment and scoring."""

    item: UniverseItem
    technical_snapshot: object
    screener_factor_snapshot: ScreenerFactorSnapshot
    prediction_snapshot: object
    bars_quality: _QUALITY_STATUS
    financial_quality: _QUALITY_STATUS
    announcement_quality: _QUALITY_STATUS


@dataclass(frozen=True)
class _QualityGateResult:
    """质量门控结果。"""

    target_v2_list_type: str
    target_screener_score: int
    quality_penalty_applied: bool
    quality_note: Optional[str]


def _rank_candidates(
    candidates: list[ScreenerCandidate],
    top_n: Optional[int] = None,
) -> list[ScreenerCandidate]:
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            item.screener_score,
            item.predictive_score or -1,
            item.alpha_score,
            -item.risk_score,
            item.trend_score,
            item.symbol,
        ),
        reverse=True,
    )
    if top_n is not None:
        sorted_candidates = sorted_candidates[: max(top_n, 0)]

    ranked_candidates: list[ScreenerCandidate] = []
    for index, candidate in enumerate(sorted_candidates, start=1):
        ranked_candidates.append(candidate.model_copy(update={"rank": index}))
    return ranked_candidates


def _build_candidate(
    *,
    item: UniverseItem,
    technical_snapshot,
    score_result,
    prediction_snapshot,
    target_v2_list_type: str,
    target_screener_score: int,
    bars_quality: _QUALITY_STATUS,
    financial_quality: _QUALITY_STATUS,
    announcement_quality: _QUALITY_STATUS,
    quality_penalty_applied: bool,
    quality_note: Optional[str],
    screener_factor_snapshot: Optional[ScreenerFactorSnapshot] = None,
) -> ScreenerCandidate:
    v2_list_type = target_v2_list_type
    selection_decision = (
        screener_factor_snapshot.selection_decision
        if screener_factor_snapshot is not None
        else None
    )
    display_fields = normalize_candidate_display_fields(
        name=item.name,
        list_type=v2_list_type,
        short_reason=(
            selection_decision.short_reason
            if selection_decision is not None and selection_decision.short_reason is not None
            else score_result.short_reason
        ),
        headline_verdict=None,
        top_positive_factors=(
            selection_decision.top_positive_factors
            if selection_decision is not None
            else score_result.top_positive_factors
        ),
        top_negative_factors=(
            selection_decision.top_negative_factors
            if selection_decision is not None
            else score_result.top_negative_factors
        ),
        risk_notes=(
            selection_decision.risk_notes
            if selection_decision is not None
            else score_result.risk_notes
        ),
        evidence_hints=[
            *((selection_decision.top_positive_factors if selection_decision is not None else score_result.top_positive_factors)[:2]),
            *((selection_decision.risk_notes if selection_decision is not None else score_result.risk_notes)[:1]),
        ],
    )
    evidence_hints = [
        *((selection_decision.top_positive_factors if selection_decision is not None else score_result.top_positive_factors)[:2]),
        *((selection_decision.risk_notes if selection_decision is not None else score_result.risk_notes)[:1]),
    ]
    return ScreenerCandidate(
        symbol=item.symbol,
        name=str(display_fields["name"]),
        list_type=_to_legacy_list_type(v2_list_type),
        v2_list_type=v2_list_type,
        rank=1,
        screener_score=target_screener_score,
        alpha_score=score_result.alpha_score,
        trigger_score=score_result.trigger_score,
        risk_score=score_result.risk_score,
        trend_state=technical_snapshot.trend_state,
        trend_score=technical_snapshot.trend_score,
        latest_close=technical_snapshot.latest_close,
        support_level=technical_snapshot.support_level,
        resistance_level=technical_snapshot.resistance_level,
        top_positive_factors=list(display_fields["top_positive_factors"]),
        top_negative_factors=list(display_fields["top_negative_factors"]),
        risk_notes=list(display_fields["risk_notes"]),
        short_reason=str(display_fields["short_reason"]),
        calculated_at=datetime.now(timezone.utc),
        rule_version=_RULE_VERSION,
        rule_summary=_RULE_SUMMARY,
        headline_verdict=str(display_fields["headline_verdict"]),
        action_now=_build_action_now(v2_list_type),
        evidence_hints=list(display_fields["evidence_hints"])[:3] or evidence_hints[:3],
        bars_quality=bars_quality,
        financial_quality=financial_quality,
        announcement_quality=announcement_quality,
        quality_penalty_applied=quality_penalty_applied,
        quality_note=quality_note,
        predictive_score=(
            prediction_snapshot.predictive_score if prediction_snapshot is not None else None
        ),
        predictive_confidence=(
            prediction_snapshot.model_confidence if prediction_snapshot is not None else None
        ),
        predictive_model_version=(
            prediction_snapshot.model_version if prediction_snapshot is not None else None
        ),
        fail_reason=None,
    )


def _build_action_now(v2_list_type: str) -> str:
    mapping = {
        "READY_TO_BUY": "BUY_NOW",
        "WATCH_PULLBACK": "WAIT_PULLBACK",
        "WATCH_BREAKOUT": "WAIT_BREAKOUT",
        "RESEARCH_ONLY": "RESEARCH_ONLY",
        "AVOID": "AVOID",
    }
    return mapping.get(v2_list_type, "RESEARCH_ONLY")


def _to_legacy_list_type(v2_list_type: str) -> str:
    if v2_list_type == "READY_TO_BUY":
        return "BUY_CANDIDATE"
    if v2_list_type in {"WATCH_PULLBACK", "WATCH_BREAKOUT", "RESEARCH_ONLY"}:
        return "WATCHLIST"
    return "AVOID"


def _normalize_quality_status(raw_status: Optional[str]) -> _QUALITY_STATUS:
    if raw_status in _QUALITY_WEIGHT:
        return raw_status  # type: ignore[return-value]
    return "warning"


def _resolve_as_of_date(response: DailyBarResponse) -> date:
    if response.bars:
        return response.bars[-1].trade_date
    return date.today()


def _resolve_provider_used(response: DailyBarResponse) -> Optional[str]:
    provider_used = getattr(response, "provider_used", None)
    if provider_used is not None:
        return str(provider_used)
    if response.bars and response.bars[-1].source:
        return response.bars[-1].source
    return None


def _build_failed_placeholder_for_bars(
    *,
    item: UniverseItem,
    response: DailyBarResponse,
    quality_note: str,
) -> ScreenerCandidate:
    latest_close = response.bars[-1].close if response.bars else None
    fail_reason = "行情数据清洗质量为 failed，当前股票仅保留失败占位。"
    if response.cleaning_warnings:
        fail_reason = "{reason} 告警：{warnings}".format(
            reason=fail_reason,
            warnings="；".join(response.cleaning_warnings[:2]),
        )
    display_fields = normalize_candidate_display_fields(
        name=item.name,
        list_type="AVOID",
        short_reason="行情数据质量失败，未纳入候选排序。",
        headline_verdict="行情数据质量失败，本轮仅保留失败占位。",
        evidence_hints=response.cleaning_warnings[:2],
    )
    return ScreenerCandidate(
        symbol=item.symbol,
        name=str(display_fields["name"]),
        list_type="AVOID",
        v2_list_type="AVOID",
        rank=1,
        screener_score=0,
        alpha_score=0,
        trigger_score=0,
        risk_score=100,
        trend_state="down",
        trend_score=0,
        latest_close=latest_close if latest_close is not None else 0.0,
        support_level=None,
        resistance_level=None,
        top_positive_factors=[],
        top_negative_factors=["行情数据质量 failed"],
        risk_notes=["该股票未参与本轮候选排序"],
        short_reason=str(display_fields["short_reason"]),
        calculated_at=datetime.now(timezone.utc),
        rule_version=_RULE_VERSION,
        rule_summary=_RULE_SUMMARY,
        headline_verdict=str(display_fields["headline_verdict"]),
        action_now="AVOID",
        evidence_hints=list(display_fields["evidence_hints"]),
        bars_quality="failed",
        financial_quality=None,
        announcement_quality=None,
        quality_penalty_applied=True,
        quality_note=quality_note,
        predictive_score=None,
        predictive_confidence=None,
        predictive_model_version=None,
        fail_reason=fail_reason,
    )


def _apply_quality_gate(
    *,
    origin_v2_list_type: str,
    origin_screener_score: int,
    bars_quality: _QUALITY_STATUS,
    financial_quality: _QUALITY_STATUS,
    announcement_quality: _QUALITY_STATUS,
) -> _QualityGateResult:
    target_v2_list_type = origin_v2_list_type
    quality_notes: list[str] = []
    quality_penalty_applied = False

    if bars_quality == "degraded" and target_v2_list_type in {
        "READY_TO_BUY",
        "WATCH_PULLBACK",
        "WATCH_BREAKOUT",
    }:
        target_v2_list_type = "RESEARCH_ONLY"
        quality_notes.append("行情数据质量降级，候选已下调为研究观察。")
        quality_penalty_applied = True

    if financial_quality in {"degraded", "failed"} and target_v2_list_type in {
        "READY_TO_BUY",
        "WATCH_PULLBACK",
        "WATCH_BREAKOUT",
    }:
        target_v2_list_type = "RESEARCH_ONLY"
        quality_notes.append("财务摘要质量不足，候选已下调为研究观察。")
        quality_penalty_applied = True

    if announcement_quality == "failed" and target_v2_list_type in {
        "READY_TO_BUY",
        "WATCH_PULLBACK",
        "WATCH_BREAKOUT",
    }:
        target_v2_list_type = "RESEARCH_ONLY"
        quality_notes.append("公告输入质量不足，事件驱动不提升优先级。")
        quality_penalty_applied = True

    if target_v2_list_type == "READY_TO_BUY" and (
        bars_quality != "ok"
        or financial_quality == "failed"
        or announcement_quality == "failed"
    ):
        target_v2_list_type = "RESEARCH_ONLY"
        quality_notes.append("质量门槛未满足，已从交易候选降级为研究观察。")
        quality_penalty_applied = True

    combined_weight = (
        0.5 * _QUALITY_WEIGHT[bars_quality]
        + 0.3 * _QUALITY_WEIGHT[financial_quality]
        + 0.2 * _QUALITY_WEIGHT[announcement_quality]
    )
    adjusted_score = max(0, min(100, int(round(origin_screener_score * combined_weight))))
    if adjusted_score != origin_screener_score:
        quality_penalty_applied = True
        quality_notes.append("数据质量折损已应用于候选评分。")

    quality_note = "；".join(dict.fromkeys(quality_notes)) if quality_notes else None
    return _QualityGateResult(
        target_v2_list_type=target_v2_list_type,
        target_screener_score=adjusted_score,
        quality_penalty_applied=quality_penalty_applied,
        quality_note=quality_note,
    )


def _append_failed_placeholders(
    *,
    ranked_avoid_candidates: list[ScreenerCandidate],
    failed_placeholders: list[ScreenerCandidate],
) -> list[ScreenerCandidate]:
    if not failed_placeholders:
        return ranked_avoid_candidates
    merged = list(ranked_avoid_candidates)
    for index, item in enumerate(failed_placeholders, start=len(merged) + 1):
        merged.append(item.model_copy(update={"rank": index}))
    return merged


def _safe_get_financial_summary(
    market_data_service: MarketDataService,
    symbol: str,
    *,
    force_refresh: bool = False,
) -> tuple[Optional[FinancialSummary], _QUALITY_STATUS]:
    try:
        try:
            summary = market_data_service.get_stock_financial_summary(
                symbol,
                force_refresh=force_refresh,
                allow_remote_sync=False,
            )
        except TypeError:
            try:
                summary = market_data_service.get_stock_financial_summary(
                    symbol,
                    force_refresh=force_refresh,
                )
            except TypeError:
                summary = market_data_service.get_stock_financial_summary(symbol)
        return summary, _normalize_quality_status(summary.quality_status)
    except DataServiceError:
        return None, "warning"


def _safe_get_recent_announcements(
    market_data_service: MarketDataService,
    symbol: str,
    as_of_date: date,
    *,
    force_refresh: bool = False,
) -> tuple[list, _QUALITY_STATUS]:
    try:
        try:
            response = market_data_service.get_stock_announcements(
                symbol,
                start_date=(as_of_date - timedelta(days=30)).isoformat(),
                end_date=as_of_date.isoformat(),
                limit=50,
                force_refresh=force_refresh,
                allow_remote_sync=False,
            )
        except TypeError:
            try:
                response = market_data_service.get_stock_announcements(
                    symbol,
                    start_date=(as_of_date - timedelta(days=30)).isoformat(),
                    end_date=as_of_date.isoformat(),
                    limit=50,
                    force_refresh=force_refresh,
                )
            except TypeError:
                response = market_data_service.get_stock_announcements(
                    symbol,
                    start_date=(as_of_date - timedelta(days=30)).isoformat(),
                    end_date=as_of_date.isoformat(),
                    limit=50,
                )
    except DataServiceError:
        return [], "warning"
    return response.items, _normalize_quality_status(response.quality_status)


def _stringify_log_value(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _build_lineage_ref_payload(result) -> dict[str, object]:
    return {
        "dataset": result.dataset,
        "dataset_version": result.dataset_version,
        "symbol": result.symbol,
        "as_of_date": result.as_of_date,
        "provider_used": result.provider_used,
        "source_mode": result.source_mode,
        "freshness_mode": result.freshness_mode,
        "updated_at": result.updated_at,
    }


def _build_screener_factor_snapshot_params(
    *,
    run_context: dict[str, object],
    max_symbols: int | None,
    top_n: int | None,
):
    from app.services.data_products.datasets.screener_factor_snapshot_daily import (
        ScreenerFactorSnapshotParams,
    )

    return ScreenerFactorSnapshotParams(
        workflow_name=_stringify_log_value(run_context.get("workflow_name"))
        or "screener_run",
        max_symbols=max_symbols,
        top_n=top_n,
        batch_size=_int_or_none(run_context.get("batch_size")),
        cursor_start_symbol=_stringify_log_value(run_context.get("cursor_start_symbol")),
        cursor_start_index=_int_or_none(run_context.get("cursor_start_index")),
        reset_trade_date=_stringify_log_value(run_context.get("reset_trade_date")),
    )
