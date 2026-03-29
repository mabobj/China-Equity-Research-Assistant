"""Stock data and stock workspace routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import (
    get_debate_review_daily_dataset,
    get_debate_runtime_service,
    get_decision_brief_service,
    get_factor_snapshot_service,
    get_market_data_service,
    get_review_report_daily_dataset,
    get_stock_review_service,
    get_technical_analysis_service,
    get_trigger_snapshot_service,
    get_workspace_bundle_service,
)
from app.schemas.debate import DebateReviewProgress, DebateReviewReport
from app.schemas.decision_brief import DecisionBrief
from app.schemas.factor import FactorSnapshot
from app.schemas.intraday import TriggerSnapshot
from app.schemas.market_data import (
    DailyBarResponse,
    IntradayBarResponse,
    StockProfile,
    TimelineResponse,
    UniverseResponse,
)
from app.schemas.research_inputs import AnnouncementListResponse, FinancialSummary
from app.schemas.review import StockReviewReport
from app.schemas.technical import TechnicalSnapshot
from app.schemas.workspace import WorkspaceBundleResponse
from app.services.data_products.freshness import resolve_last_closed_trading_day
from app.services.data_service.market_data_service import MarketDataService

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/universe", response_model=UniverseResponse)
def get_stock_universe(
    service: MarketDataService = Depends(get_market_data_service),
) -> UniverseResponse:
    return service.get_stock_universe()


@router.get("/{symbol}/profile", response_model=StockProfile)
def get_stock_profile(
    symbol: str,
    service: MarketDataService = Depends(get_market_data_service),
) -> StockProfile:
    return service.get_stock_profile(symbol)


@router.get("/{symbol}/daily-bars", response_model=DailyBarResponse)
def get_daily_bars(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    service: MarketDataService = Depends(get_market_data_service),
) -> DailyBarResponse:
    return service.get_daily_bars(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{symbol}/intraday-bars", response_model=IntradayBarResponse)
def get_intraday_bars(
    symbol: str,
    frequency: str = Query(default="1m"),
    start_datetime: Optional[str] = Query(default=None),
    end_datetime: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=None, ge=1),
    service: MarketDataService = Depends(get_market_data_service),
) -> IntradayBarResponse:
    return service.get_intraday_bars(
        symbol=symbol,
        frequency=frequency,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        limit=limit,
    )


@router.get("/{symbol}/timeline", response_model=TimelineResponse)
def get_timeline(
    symbol: str,
    limit: Optional[int] = Query(default=None, ge=1),
    service: MarketDataService = Depends(get_market_data_service),
) -> TimelineResponse:
    return service.get_timeline(symbol=symbol, limit=limit)


@router.get("/{symbol}/trigger-snapshot", response_model=TriggerSnapshot)
def get_trigger_snapshot(
    symbol: str,
    frequency: str = Query(default="1m"),
    limit: int = Query(default=60, ge=1),
    service: Any = Depends(get_trigger_snapshot_service),
) -> TriggerSnapshot:
    return service.get_trigger_snapshot(symbol=symbol, frequency=frequency, limit=limit)


@router.get("/{symbol}/factor-snapshot", response_model=FactorSnapshot)
def get_factor_snapshot(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    service: Any = Depends(get_factor_snapshot_service),
) -> FactorSnapshot:
    return service.get_factor_snapshot(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{symbol}/announcements", response_model=AnnouncementListResponse)
def get_stock_announcements(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    service: MarketDataService = Depends(get_market_data_service),
) -> AnnouncementListResponse:
    return service.get_stock_announcements(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@router.get("/{symbol}/financial-summary", response_model=FinancialSummary)
def get_stock_financial_summary(
    symbol: str,
    service: MarketDataService = Depends(get_market_data_service),
) -> FinancialSummary:
    return service.get_stock_financial_summary(symbol)


@router.get("/{symbol}/technical", response_model=TechnicalSnapshot)
def get_technical_snapshot(
    symbol: str,
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    service: Any = Depends(get_technical_analysis_service),
) -> TechnicalSnapshot:
    return service.get_technical_snapshot(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{symbol}/review-report", response_model=StockReviewReport)
def get_stock_review_report(
    symbol: str,
    force_refresh: bool = Query(default=False),
    service: Any = Depends(get_stock_review_service),
    review_report_daily: Any = Depends(get_review_report_daily_dataset),
) -> StockReviewReport:
    as_of_date = resolve_last_closed_trading_day()
    if not force_refresh:
        cached = review_report_daily.load(symbol, as_of_date=as_of_date)
        if cached is not None:
            return cached.payload.model_copy(
                update={
                    "freshness_mode": cached.freshness_mode,
                    "source_mode": cached.source_mode,
                }
            )
    computed = service.get_stock_review_report(symbol)
    saved = review_report_daily.save(symbol, computed)
    return saved.payload.model_copy(
        update={
            "freshness_mode": saved.freshness_mode,
            "source_mode": saved.source_mode,
        }
    )


@router.get("/{symbol}/decision-brief", response_model=DecisionBrief)
def get_stock_decision_brief(
    symbol: str,
    use_llm: Optional[bool] = Query(default=None),
    service: Any = Depends(get_decision_brief_service),
) -> DecisionBrief:
    return service.get_decision_brief(symbol, use_llm=use_llm)


@router.get("/{symbol}/debate-review", response_model=DebateReviewReport)
def get_debate_review_report(
    symbol: str,
    use_llm: Optional[bool] = Query(default=None),
    force_refresh: bool = Query(default=False),
    request_id: Optional[str] = Query(default=None),
    service: Any = Depends(get_debate_runtime_service),
    debate_review_daily: Any = Depends(get_debate_review_daily_dataset),
) -> DebateReviewReport:
    as_of_date = resolve_last_closed_trading_day()
    requested_variant = "llm" if bool(use_llm) else "rule_based"
    if not force_refresh:
        cached = debate_review_daily.load(
            symbol,
            as_of_date=as_of_date,
            variant=requested_variant,
        )
        if cached is not None:
            return cached.payload.model_copy(
                update={
                    "freshness_mode": cached.freshness_mode,
                    "source_mode": cached.source_mode,
                }
            )
    try:
        report = service.get_debate_review_report(
            symbol,
            use_llm=use_llm,
            request_id=request_id,
        )
        variant_to_save = (
            "llm"
            if (
                report.runtime_mode_effective == "llm"
                or report.runtime_mode == "llm"
            )
            else "rule_based"
        )
        saved = debate_review_daily.save(
            symbol,
            report,
            variant=variant_to_save,
        )
        return saved.payload.model_copy(
            update={
                "freshness_mode": saved.freshness_mode,
                "source_mode": saved.source_mode,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Debate review is temporarily unavailable.",
        ) from exc


@router.get("/{symbol}/debate-review-progress", response_model=DebateReviewProgress)
def get_debate_review_progress(
    symbol: str,
    use_llm: Optional[bool] = Query(default=None),
    request_id: Optional[str] = Query(default=None),
    service: Any = Depends(get_debate_runtime_service),
) -> DebateReviewProgress:
    return service.get_debate_review_progress(
        symbol,
        use_llm=use_llm,
        request_id=request_id,
    )


@router.get("/{symbol}/workspace-bundle", response_model=WorkspaceBundleResponse)
def get_workspace_bundle(
    symbol: str,
    use_llm: Optional[bool] = Query(default=None),
    force_refresh: bool = Query(default=False),
    request_id: Optional[str] = Query(default=None),
    service: Any = Depends(get_workspace_bundle_service),
) -> WorkspaceBundleResponse:
    try:
        return service.get_workspace_bundle(
            symbol,
            use_llm=use_llm,
            force_refresh=force_refresh,
            request_id=request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Workspace bundle is temporarily unavailable.",
        ) from exc
