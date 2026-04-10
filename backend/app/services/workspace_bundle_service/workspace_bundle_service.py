"""Single-stock workspace bundle service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging
from threading import Lock
from typing import TYPE_CHECKING, Any

from app.schemas.decision_brief import DecisionBrief
from app.schemas.evidence import EvidenceManifest
from app.schemas.market_data import StockProfile
from app.schemas.prediction import PredictionSnapshotResponse
from app.schemas.workspace import (
    FreshnessSummary,
    WorkspaceBundleResponse,
    WorkspaceFreshnessItem,
    WorkspaceModuleStatus,
)
from app.services.data_products.datasets.announcements_daily import AnnouncementsDailyDataset
from app.services.data_products.datasets.daily_bars_daily import DailyBarsDailyDataset
from app.services.data_products.datasets.debate_review_daily import DebateReviewDailyDataset
from app.services.data_products.datasets.decision_brief_daily import DecisionBriefDailyDataset
from app.services.data_products.datasets.factor_snapshot_daily import FactorSnapshotDailyDataset
from app.services.data_products.datasets.financial_summary_daily import FinancialSummaryDailyDataset
from app.services.data_products.datasets.review_report_daily import ReviewReportDailyDataset
from app.services.data_products.datasets.strategy_plan_daily import StrategyPlanDailyDataset
from app.services.data_products.freshness import resolve_daily_analysis_as_of_date
from app.services.decision_brief_service.brief_builder import build_decision_brief
from app.services.decision_brief_service.evidence_builder import build_evidence_manifest
from app.services.factor_service.base import FactorBuildInputs
from app.services.research_service.research_manager import ResearchInputs

if TYPE_CHECKING:
    from app.services.debate_service.debate_orchestrator import DebateOrchestrator
    from app.services.factor_service.factor_snapshot_service import FactorSnapshotService
    from app.services.factor_service.trigger_snapshot_service import TriggerSnapshotService
    from app.services.feature_service.technical_analysis_service import (
        TechnicalAnalysisService,
    )
    from app.services.llm_debate_service.fallback import DebateRuntimeService
    from app.services.research_service.research_manager import ResearchManager
    from app.services.research_service.strategy_planner import StrategyPlanner
    from app.services.review_service.stock_review_service import StockReviewService

logger = logging.getLogger(__name__)


@dataclass
class _WorkspaceState:
    profile: StockProfile | None = None
    factor_snapshot: Any | None = None
    review_report: Any | None = None
    debate_review: Any | None = None
    strategy_plan: Any | None = None
    trigger_snapshot: Any | None = None
    decision_brief: DecisionBrief | None = None
    predictive_snapshot: PredictionSnapshotResponse | None = None
    evidence_manifest: EvidenceManifest | None = None


class WorkspaceBundleService:
    """Build the stock workspace bundle in one backend pass."""

    def __init__(
        self,
        *,
        market_data_service,
        technical_analysis_service: "TechnicalAnalysisService",
        research_manager: "ResearchManager",
        factor_snapshot_service: "FactorSnapshotService",
        stock_review_service: "StockReviewService",
        debate_orchestrator: "DebateOrchestrator",
        debate_runtime_service: "DebateRuntimeService",
        strategy_planner: "StrategyPlanner",
        trigger_snapshot_service: "TriggerSnapshotService",
        daily_bars_daily: DailyBarsDailyDataset,
        announcements_daily: AnnouncementsDailyDataset,
        financial_summary_daily: FinancialSummaryDailyDataset,
        factor_snapshot_daily: FactorSnapshotDailyDataset,
        review_report_daily: ReviewReportDailyDataset,
        strategy_plan_daily: StrategyPlanDailyDataset,
        debate_review_daily: DebateReviewDailyDataset,
        decision_brief_daily: DecisionBriefDailyDataset,
        prediction_service=None,
    ) -> None:
        self._market_data_service = market_data_service
        self._technical_analysis_service = technical_analysis_service
        self._research_manager = research_manager
        self._factor_snapshot_service = factor_snapshot_service
        self._stock_review_service = stock_review_service
        self._debate_orchestrator = debate_orchestrator
        self._debate_runtime_service = debate_runtime_service
        self._strategy_planner = strategy_planner
        self._trigger_snapshot_service = trigger_snapshot_service
        self._daily_bars_daily = daily_bars_daily
        self._announcements_daily = announcements_daily
        self._financial_summary_daily = financial_summary_daily
        self._factor_snapshot_daily = factor_snapshot_daily
        self._review_report_daily = review_report_daily
        self._strategy_plan_daily = strategy_plan_daily
        self._debate_review_daily = debate_review_daily
        self._decision_brief_daily = decision_brief_daily
        self._prediction_service = prediction_service
        self._bundle_lock_guard = Lock()
        self._bundle_locks: dict[tuple[str, date, bool, bool], Lock] = {}

    def get_workspace_bundle(
        self,
        symbol: str,
        *,
        use_llm: bool | None = None,
        force_refresh: bool = False,
        request_id: str | None = None,
        as_of_date: date | None = None,
    ) -> WorkspaceBundleResponse:
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        bundle_lock = self._get_bundle_lock(
            symbol=symbol,
            as_of_date=resolved_as_of_date,
            use_llm=bool(use_llm),
            force_refresh=force_refresh,
        )
        logger.debug(
            "workspace.bundle.lock_wait symbol=%s as_of_date=%s use_llm=%s force_refresh=%s",
            symbol,
            resolved_as_of_date,
            bool(use_llm),
            force_refresh,
        )
        with bundle_lock:
            logger.debug(
                "workspace.bundle.lock_acquired symbol=%s as_of_date=%s use_llm=%s force_refresh=%s",
                symbol,
                resolved_as_of_date,
                bool(use_llm),
                force_refresh,
            )
            return self._build_workspace_bundle(
                symbol,
                use_llm=use_llm,
                force_refresh=force_refresh,
                request_id=request_id,
                as_of_date=resolved_as_of_date,
            )

    def _build_workspace_bundle(
        self,
        symbol: str,
        *,
        use_llm: bool | None = None,
        force_refresh: bool = False,
        request_id: str | None = None,
        as_of_date: date | None = None,
    ) -> WorkspaceBundleResponse:
        statuses: list[WorkspaceModuleStatus] = []
        freshness_items: list[WorkspaceFreshnessItem] = []
        warning_messages: list[str] = []
        state = _WorkspaceState()
        resolved_as_of_date = resolve_daily_analysis_as_of_date(as_of_date)
        brief_variant = "llm" if bool(use_llm) else "rule_based"
        runtime_mode_requested = "llm" if bool(use_llm) else "rule_based"

        state.profile = self._run_module(
            module_name="profile",
            statuses=statuses,
            fn=lambda: self._market_data_service.get_stock_profile(symbol),
        )

        daily_bars_product = self._run_module(
            module_name="daily_bars_daily",
            statuses=statuses,
            fn=lambda: self._daily_bars_daily.get(
                symbol,
                as_of_date=resolved_as_of_date,
                force_refresh=force_refresh,
            ),
        )
        if daily_bars_product is not None:
            if daily_bars_product.payload.count == 0:
                warning_messages.append(
                    "No daily bars are available for the selected trading date."
                )
            freshness_items.append(
                WorkspaceFreshnessItem(
                    item_name="daily_bars_daily",
                    as_of_date=daily_bars_product.as_of_date,
                    freshness_mode=daily_bars_product.freshness_mode,
                    source_mode=daily_bars_product.source_mode,
                )
            )

        announcements_product = self._run_module(
            module_name="announcements_daily",
            statuses=statuses,
            fn=lambda: self._announcements_daily.get(
                symbol,
                as_of_date=resolved_as_of_date,
                force_refresh=force_refresh,
            ),
        )
        if announcements_product is not None:
            freshness_items.append(
                WorkspaceFreshnessItem(
                    item_name="announcements_daily",
                    as_of_date=announcements_product.as_of_date,
                    freshness_mode=announcements_product.freshness_mode,
                    source_mode=announcements_product.source_mode,
                )
            )

        financial_summary_product = self._run_module(
            module_name="financial_summary_daily",
            statuses=statuses,
            fn=lambda: self._financial_summary_daily.get(
                symbol,
                as_of_date=resolved_as_of_date,
                force_refresh=force_refresh,
            ),
        )
        if financial_summary_product is not None:
            freshness_items.append(
                WorkspaceFreshnessItem(
                    item_name="financial_summary_daily",
                    as_of_date=financial_summary_product.as_of_date,
                    freshness_mode=financial_summary_product.freshness_mode,
                    source_mode=financial_summary_product.source_mode,
                )
            )

        technical_snapshot = None
        if daily_bars_product is not None:
            technical_snapshot = self._run_module(
                module_name="technical_snapshot",
                statuses=statuses,
                fn=lambda: self._technical_analysis_service.build_snapshot_from_bars(
                    symbol=symbol,
                    bars=daily_bars_product.payload.bars,
                ),
            )

        if technical_snapshot is not None:
            state.trigger_snapshot = self._run_module(
                module_name="trigger_snapshot",
                statuses=statuses,
                fn=lambda: self._get_trigger_snapshot_with_fallback(
                    symbol=symbol,
                    technical_snapshot=technical_snapshot,
                ),
            )

        factor_cached = None if force_refresh else self._factor_snapshot_daily.load(
            symbol,
            as_of_date=resolved_as_of_date,
        )
        if factor_cached is not None:
            state.factor_snapshot = factor_cached.payload.model_copy(
                update={
                    "freshness_mode": factor_cached.freshness_mode,
                    "source_mode": factor_cached.source_mode,
                }
            )
            statuses.append(
                WorkspaceModuleStatus(
                    module_name="factor_snapshot",
                    status="success",
                    message="Loaded from same-day snapshot.",
                )
            )
            freshness_items.append(
                WorkspaceFreshnessItem(
                    item_name="factor_snapshot_daily",
                    as_of_date=factor_cached.as_of_date,
                    freshness_mode=factor_cached.freshness_mode,
                    source_mode=factor_cached.source_mode,
                )
            )
        elif technical_snapshot is not None and daily_bars_product is not None:
            computed_factor = self._run_module(
                module_name="factor_snapshot",
                statuses=statuses,
                fn=lambda: self._factor_snapshot_service.build_from_inputs(
                    FactorBuildInputs(
                        symbol=symbol,
                        technical_snapshot=technical_snapshot,
                        daily_bars=daily_bars_product.payload.bars,
                        financial_summary=(
                            financial_summary_product.payload
                            if financial_summary_product is not None
                            else None
                        ),
                        announcements=(
                            announcements_product.payload.items
                            if announcements_product is not None
                            else []
                        ),
                    )
                ),
            )
            if computed_factor is not None:
                saved_factor = self._factor_snapshot_daily.save(symbol, computed_factor)
                state.factor_snapshot = saved_factor.payload.model_copy(
                    update={
                        "freshness_mode": saved_factor.freshness_mode,
                        "source_mode": saved_factor.source_mode,
                    }
                )
                freshness_items.append(
                    WorkspaceFreshnessItem(
                        item_name="factor_snapshot_daily",
                        as_of_date=saved_factor.as_of_date,
                        freshness_mode=saved_factor.freshness_mode,
                        source_mode=saved_factor.source_mode,
                    )
                )

        strategy_cached = None if force_refresh else self._strategy_plan_daily.load(
            symbol,
            as_of_date=resolved_as_of_date,
        )
        if strategy_cached is not None:
            state.strategy_plan = strategy_cached.payload.model_copy(
                update={
                    "freshness_mode": strategy_cached.freshness_mode,
                    "source_mode": strategy_cached.source_mode,
                }
            )
            statuses.append(
                WorkspaceModuleStatus(
                    module_name="strategy_plan",
                    status="success",
                    message="Loaded from same-day snapshot.",
                )
            )
            freshness_items.append(
                WorkspaceFreshnessItem(
                    item_name="strategy_plan_daily",
                    as_of_date=strategy_cached.as_of_date,
                    freshness_mode=strategy_cached.freshness_mode,
                    source_mode=strategy_cached.source_mode,
                )
            )
        else:
            research_report = None
            if (
                state.profile is not None
                and technical_snapshot is not None
                and financial_summary_product is not None
                and announcements_product is not None
            ):
                research_report = self._run_module(
                    module_name="research_report",
                    statuses=statuses,
                    fn=lambda: self._research_manager.build_research_report(
                        ResearchInputs(
                            profile=state.profile,
                            technical_snapshot=technical_snapshot,
                            daily_bars_response=daily_bars_product.payload,
                            financial_summary=financial_summary_product.payload,
                            announcements=announcements_product.payload.items,
                            announcements_quality_status=(
                                announcements_product.payload.quality_status
                            ),
                            announcements_cleaning_warnings=list(
                                announcements_product.payload.cleaning_warnings
                            ),
                        )
                    ),
                )

            if (
                state.profile is not None
                and technical_snapshot is not None
                and research_report is not None
            ):
                computed_strategy = self._run_module(
                    module_name="strategy_plan",
                    statuses=statuses,
                    fn=lambda: self._strategy_planner.build_strategy_plan_from_components(
                        profile_name=state.profile.name,
                        technical_snapshot=technical_snapshot,
                        research_report=research_report,
                    ),
                )
                if computed_strategy is not None:
                    saved_strategy = self._strategy_plan_daily.save(
                        symbol,
                        computed_strategy,
                    )
                    state.strategy_plan = saved_strategy.payload.model_copy(
                        update={
                            "freshness_mode": saved_strategy.freshness_mode,
                            "source_mode": saved_strategy.source_mode,
                        }
                    )
                    freshness_items.append(
                        WorkspaceFreshnessItem(
                            item_name="strategy_plan_daily",
                            as_of_date=saved_strategy.as_of_date,
                            freshness_mode=saved_strategy.freshness_mode,
                            source_mode=saved_strategy.source_mode,
                        )
                    )

        review_cached = None if force_refresh else self._review_report_daily.load(
            symbol,
            as_of_date=resolved_as_of_date,
        )
        if review_cached is not None:
            state.review_report = review_cached.payload.model_copy(
                update={
                    "freshness_mode": review_cached.freshness_mode,
                    "source_mode": review_cached.source_mode,
                }
            )
            statuses.append(
                WorkspaceModuleStatus(
                    module_name="review_report",
                    status="success",
                    message="Loaded from same-day snapshot.",
                )
            )
            freshness_items.append(
                WorkspaceFreshnessItem(
                    item_name="review_report_daily",
                    as_of_date=review_cached.as_of_date,
                    freshness_mode=review_cached.freshness_mode,
                    source_mode=review_cached.source_mode,
                )
            )
        elif (
            state.profile is not None
            and technical_snapshot is not None
            and state.factor_snapshot is not None
            and state.trigger_snapshot is not None
            and state.strategy_plan is not None
        ):
            computed_review = self._run_module(
                module_name="review_report",
                statuses=statuses,
                fn=lambda: self._stock_review_service.build_review_report_from_components(
                    symbol=symbol,
                    profile=state.profile,
                    technical_snapshot=technical_snapshot,
                    factor_snapshot=state.factor_snapshot,
                    trigger_snapshot=state.trigger_snapshot,
                    strategy_plan=state.strategy_plan,
                    financial_summary=(
                        financial_summary_product.payload
                        if financial_summary_product is not None
                        else None
                    ),
                    announcements=(
                        announcements_product.payload.items
                        if announcements_product is not None
                        else []
                    ),
                ),
            )
            if computed_review is not None:
                saved_review = self._review_report_daily.save(symbol, computed_review)
                state.review_report = saved_review.payload.model_copy(
                    update={
                        "freshness_mode": saved_review.freshness_mode,
                        "source_mode": saved_review.source_mode,
                    }
                )
                freshness_items.append(
                    WorkspaceFreshnessItem(
                        item_name="review_report_daily",
                        as_of_date=saved_review.as_of_date,
                        freshness_mode=saved_review.freshness_mode,
                        source_mode=saved_review.source_mode,
                    )
                )

        debate_inputs = None
        debate_variant = "llm" if bool(use_llm) else "rule_based"
        debate_cached = None if force_refresh else self._debate_review_daily.load(
            symbol,
            as_of_date=resolved_as_of_date,
            variant=debate_variant,
        )
        if debate_cached is not None and bool(use_llm):
            cached_fallback_reason = debate_cached.payload.fallback_reason or ""
            if cached_fallback_reason.startswith(
                "Workspace bundle deferred live LLM debate"
            ):
                debate_cached = None
        if debate_cached is not None:
            state.debate_review = debate_cached.payload.model_copy(
                update={
                    "freshness_mode": debate_cached.freshness_mode,
                    "source_mode": debate_cached.source_mode,
                }
            )
            statuses.append(
                WorkspaceModuleStatus(
                    module_name="debate_review",
                    status="success",
                    message="Loaded from same-day snapshot.",
                )
            )
            freshness_items.append(
                WorkspaceFreshnessItem(
                    item_name="debate_review_daily",
                    as_of_date=debate_cached.as_of_date,
                    freshness_mode=debate_cached.freshness_mode,
                    source_mode=debate_cached.source_mode,
                )
            )
        elif (
            state.review_report is not None
            and state.factor_snapshot is not None
            and state.strategy_plan is not None
        ):
            debate_inputs = self._debate_orchestrator.build_inputs_from_components(
                review_report=state.review_report,
                factor_snapshot=state.factor_snapshot,
                strategy_plan=state.strategy_plan,
            )
            if state.debate_review is None:
                runtime_use_llm = bool(use_llm)
                computed_debate = self._run_module(
                    module_name="debate_review",
                    statuses=statuses,
                    fn=lambda: self._debate_runtime_service.get_debate_review_report_from_inputs(
                        debate_inputs,
                        use_llm=runtime_use_llm,
                        request_id=request_id,
                    ),
                )
                if computed_debate is not None:
                    debate_variant_to_save = (
                        "llm"
                        if (
                            computed_debate.runtime_mode_effective == "llm"
                            or computed_debate.runtime_mode == "llm"
                        )
                        else "rule_based"
                    )
                    saved_debate = self._debate_review_daily.save(
                        symbol,
                        computed_debate,
                        variant=debate_variant_to_save,
                    )
                    state.debate_review = saved_debate.payload.model_copy(
                        update={
                            "freshness_mode": saved_debate.freshness_mode,
                            "source_mode": saved_debate.source_mode,
                        }
                    )
                    freshness_items.append(
                        WorkspaceFreshnessItem(
                            item_name="debate_review_daily",
                            as_of_date=saved_debate.as_of_date,
                            freshness_mode=saved_debate.freshness_mode,
                            source_mode=saved_debate.source_mode,
                        )
                    )

        brief_cached = None if force_refresh else self._decision_brief_daily.load(
            symbol,
            as_of_date=resolved_as_of_date,
            variant=brief_variant,
        )
        if brief_cached is not None:
            state.decision_brief = brief_cached.payload.model_copy(
                update={
                    "freshness_mode": brief_cached.freshness_mode,
                    "source_mode": brief_cached.source_mode,
                }
            )
            statuses.append(
                WorkspaceModuleStatus(
                    module_name="decision_brief",
                    status="success",
                    message="Loaded from same-day snapshot.",
                )
            )
            freshness_items.append(
                WorkspaceFreshnessItem(
                    item_name="decision_brief_daily",
                    as_of_date=brief_cached.as_of_date,
                    freshness_mode=brief_cached.freshness_mode,
                    source_mode=brief_cached.source_mode,
                )
            )
        elif (
            state.profile is not None
            and state.factor_snapshot is not None
            and state.review_report is not None
            and state.debate_review is not None
            and state.strategy_plan is not None
            and state.trigger_snapshot is not None
        ):
            computed_brief = self._run_module(
                module_name="decision_brief",
                statuses=statuses,
                fn=lambda: build_decision_brief(
                    profile=state.profile,
                    factor_snapshot=state.factor_snapshot,
                    review_report=state.review_report,
                    debate_review=state.debate_review,
                    strategy_plan=state.strategy_plan,
                    trigger_snapshot=state.trigger_snapshot,
                    freshness_mode="computed",
                    source_mode="workspace_bundle",
                ),
            )
            if computed_brief is not None:
                saved_brief = self._decision_brief_daily.save(
                    symbol,
                    computed_brief,
                    variant=brief_variant,
                )
                state.decision_brief = saved_brief.payload.model_copy(
                    update={
                        "freshness_mode": saved_brief.freshness_mode,
                        "source_mode": saved_brief.source_mode,
                    }
                )
                freshness_items.append(
                    WorkspaceFreshnessItem(
                        item_name="decision_brief_daily",
                        as_of_date=saved_brief.as_of_date,
                        freshness_mode=saved_brief.freshness_mode,
                        source_mode=saved_brief.source_mode,
                    )
                )

        if state.decision_brief is not None:
            state.evidence_manifest = build_evidence_manifest(state.decision_brief)

        if self._prediction_service is not None:
            state.predictive_snapshot = self._run_optional_module(
                module_name="predictive_snapshot",
                statuses=statuses,
                fn=lambda: self._get_prediction_snapshot(
                    symbol=symbol,
                    as_of_date=resolved_as_of_date,
                ),
                skip_message="Predictive snapshot is not ready yet. Continue with research modules.",
                fallback_reason="Predictive assets are not ready; module was skipped.",
            )

        debate_progress = None
        if request_id is not None:
            debate_progress = self._debate_runtime_service.get_debate_review_progress(
                symbol,
                request_id=request_id,
                use_llm=use_llm,
            )

        provider_used = None
        provider_candidates: list[str] = []
        runtime_mode_effective = runtime_mode_requested
        fallback_applied = False
        fallback_reason = None

        if state.debate_review is not None:
            provider_used = state.debate_review.provider_used
            provider_candidates = list(state.debate_review.provider_candidates)
            runtime_mode_effective = (
                state.debate_review.runtime_mode_effective
                or state.debate_review.runtime_mode
                or runtime_mode_requested
            )
            if state.debate_review.fallback_applied:
                fallback_applied = True
                fallback_reason = (
                    state.debate_review.fallback_reason
                    or "Debate runtime switched to rule-based mode."
                )
            warning_messages.extend(state.debate_review.warning_messages)

        failed_modules = [item.module_name for item in statuses if item.status == "error"]
        if failed_modules:
            fallback_applied = True
            if fallback_reason is None:
                fallback_reason = "One or more workspace modules failed and were skipped."
            warning_messages.append(
                "Partial workspace result. Failed modules: %s."
                % ", ".join(failed_modules)
            )

        return WorkspaceBundleResponse(
            symbol=symbol,
            use_llm=bool(use_llm),
            profile=state.profile,
            factor_snapshot=state.factor_snapshot,
            review_report=state.review_report,
            debate_review=state.debate_review,
            strategy_plan=state.strategy_plan,
            trigger_snapshot=state.trigger_snapshot,
            decision_brief=state.decision_brief,
            predictive_snapshot=state.predictive_snapshot,
            module_status_summary=statuses,
            evidence_manifest=state.evidence_manifest,
            freshness_summary=FreshnessSummary(
                default_as_of_date=resolved_as_of_date,
                items=freshness_items,
            ),
            debate_progress=debate_progress,
            provider_used=provider_used,
            provider_candidates=provider_candidates,
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
            runtime_mode_requested=runtime_mode_requested,
            runtime_mode_effective=runtime_mode_effective,
            warning_messages=warning_messages,
        )

    def _get_bundle_lock(
        self,
        *,
        symbol: str,
        as_of_date: date,
        use_llm: bool,
        force_refresh: bool,
    ) -> Lock:
        lock_key = (symbol, as_of_date, use_llm, force_refresh)
        with self._bundle_lock_guard:
            existing_lock = self._bundle_locks.get(lock_key)
            if existing_lock is not None:
                return existing_lock
            created_lock = Lock()
            self._bundle_locks[lock_key] = created_lock
            return created_lock

    def _get_trigger_snapshot_with_fallback(
        self,
        *,
        symbol: str,
        technical_snapshot,
    ):
        try:
            return self._trigger_snapshot_service.get_trigger_snapshot(symbol)
        except Exception:
            return self._trigger_snapshot_service.build_daily_fallback_trigger_snapshot(
                technical_snapshot
            )

    def _run_module(self, *, module_name: str, statuses: list[WorkspaceModuleStatus], fn):
        try:
            value = fn()
        except Exception as exc:
            logger.debug("workspace.bundle.module_fail module=%s error=%s", module_name, exc)
            statuses.append(
                WorkspaceModuleStatus(
                    module_name=module_name,
                    status="error",
                    message=f"{module_name} is temporarily unavailable.",
                    fallback_applied=True,
                    fallback_reason=f"{module_name} failed and was skipped.",
                )
            )
            return None

        statuses.append(
            WorkspaceModuleStatus(
                module_name=module_name,
                status="success",
                message=None,
            )
        )
        return value

    def _run_optional_module(
        self,
        *,
        module_name: str,
        statuses: list[WorkspaceModuleStatus],
        fn,
        skip_message: str,
        fallback_reason: str,
    ):
        try:
            value = fn()
        except Exception as exc:
            logger.debug("workspace.bundle.module_skip module=%s error=%s", module_name, exc)
            statuses.append(
                WorkspaceModuleStatus(
                    module_name=module_name,
                    status="skipped",
                    message=skip_message,
                    fallback_applied=True,
                    fallback_reason=fallback_reason,
                    warning_messages=[str(exc)],
                )
            )
            return None

        statuses.append(
            WorkspaceModuleStatus(
                module_name=module_name,
                status="success",
                message=None,
            )
        )
        return value

    def _get_prediction_snapshot(self, *, symbol: str, as_of_date):
        try:
            return self._prediction_service.get_symbol_prediction(
                symbol=symbol,
                as_of_date=as_of_date,
                build_feature_dataset=False,
            )
        except TypeError:
            return self._prediction_service.get_symbol_prediction(
                symbol=symbol,
                as_of_date=as_of_date,
            )
