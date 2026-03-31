"""复盘记录服务。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from app.db.trade_review_store import TradeReviewStore, parse_iso_date, parse_iso_datetime, utc_now_iso
from app.schemas.journal import (
    CreateReviewFromTradeRequest,
    CreateReviewRequest,
    DidFollowPlan,
    ReviewListResponse,
    ReviewOutcomeLabel,
    ReviewRecord,
    TradeRecord,
    UpdateReviewRequest,
)
from app.services.data_service.market_data_service import MarketDataService
from app.services.decision_snapshot_service.decision_snapshot_service import (
    DecisionSnapshotService,
)
from app.services.trade_service.trade_service import TradeService


class ReviewRecordService:
    """管理复盘记录与草稿生成。"""

    def __init__(
        self,
        *,
        store: TradeReviewStore,
        trade_service: TradeService,
        decision_snapshot_service: DecisionSnapshotService,
        market_data_service: MarketDataService,
    ) -> None:
        self._store = store
        self._trade_service = trade_service
        self._decision_snapshot_service = decision_snapshot_service
        self._market_data_service = market_data_service

    def create_review(self, request: CreateReviewRequest) -> ReviewRecord:
        linked_trade = self._trade_service.get_trade(request.linked_trade_id) if request.linked_trade_id else None
        did_follow_plan, consistency_warnings = _normalize_did_follow_plan(
            did_follow_plan=request.did_follow_plan,
            trade=linked_trade,
        )
        warning_messages = _merge_warning_messages(
            base_messages=list(request.warning_messages),
            extra_messages=consistency_warnings,
        )
        now_iso = utc_now_iso()
        payload = {
            "review_id": "rv-" + uuid4().hex[:16],
            "symbol": request.symbol,
            "review_date": request.review_date.isoformat(),
            "linked_trade_id": request.linked_trade_id,
            "linked_decision_snapshot_id": request.linked_decision_snapshot_id,
            "outcome_label": request.outcome_label,
            "holding_days": request.holding_days,
            "max_favorable_excursion": request.max_favorable_excursion,
            "max_adverse_excursion": request.max_adverse_excursion,
            "exit_reason": request.exit_reason,
            "did_follow_plan": did_follow_plan,
            "review_summary": request.review_summary,
            "lesson_tags": list(request.lesson_tags),
            "warning_messages": warning_messages,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        self._store.create_review_record(payload)
        return self._to_review_record(payload)

    def create_from_trade(
        self,
        trade_id: str,
        request: CreateReviewFromTradeRequest,
    ) -> ReviewRecord:
        trade = self._trade_service.get_trade(trade_id)
        if trade is None:
            raise ValueError("指定的交易记录不存在。")

        review_date = request.review_date or date.today()
        metrics = self._compute_review_metrics(trade=trade, review_date=review_date)
        outcome_label = request.outcome_label or _default_outcome_label(trade)
        did_follow_plan = request.did_follow_plan or _default_did_follow_plan(trade)
        review_summary = _build_review_summary(
            trade=trade,
            outcome_label=outcome_label,
            did_follow_plan=did_follow_plan,
            warnings=metrics["warning_messages"],
        )
        lesson_tags = _build_lesson_tags(
            trade=trade,
            outcome_label=outcome_label,
            warnings=metrics["warning_messages"],
        )

        create_request = CreateReviewRequest(
            symbol=trade.symbol,
            review_date=review_date,
            linked_trade_id=trade.trade_id,
            linked_decision_snapshot_id=trade.decision_snapshot_id,
            outcome_label=outcome_label,
            holding_days=metrics["holding_days"],
            max_favorable_excursion=metrics["max_favorable_excursion"],
            max_adverse_excursion=metrics["max_adverse_excursion"],
            exit_reason=request.exit_reason,
            did_follow_plan=did_follow_plan,
            review_summary=review_summary,
            lesson_tags=lesson_tags,
            warning_messages=metrics["warning_messages"],
        )
        return self.create_review(create_request)

    def get_review(self, review_id: str) -> Optional[ReviewRecord]:
        row = self._store.get_review_record(review_id)
        if row is None:
            return None
        return self._to_review_record(row)

    def list_reviews(
        self,
        *,
        symbol: Optional[str] = None,
        outcome_label: Optional[str] = None,
        limit: int = 50,
    ) -> ReviewListResponse:
        rows = self._store.list_review_records(
            symbol=symbol,
            outcome_label=outcome_label,
            limit=limit,
        )
        items = [self._to_review_record(row) for row in rows]
        return ReviewListResponse(count=len(items), items=items)

    def update_review(self, review_id: str, request: UpdateReviewRequest) -> Optional[ReviewRecord]:
        current = self._store.get_review_record(review_id)
        if current is None:
            return None

        updates = request.model_dump(exclude_none=True)
        linked_trade_id = str(current.get("linked_trade_id")) if current.get("linked_trade_id") else None
        linked_trade = self._trade_service.get_trade(linked_trade_id) if linked_trade_id else None

        raw_warning_messages = request.warning_messages
        existing_warning_messages = list(current.get("warning_messages", []))

        merged_did_follow_plan = request.did_follow_plan or str(current.get("did_follow_plan", "partial"))
        normalized_follow_plan, consistency_warnings = _normalize_did_follow_plan(
            did_follow_plan=merged_did_follow_plan,  # type: ignore[arg-type]
            trade=linked_trade,
        )

        normalized_updates: dict = {}
        for key, value in updates.items():
            if key == "lesson_tags":
                normalized_updates["lesson_tags_json"] = json_safe_list(value)
            elif key == "warning_messages":
                normalized_updates["warning_messages_json"] = json_safe_list(value)
            elif key == "review_date" and value is not None:
                normalized_updates["review_date"] = value.isoformat()
            else:
                normalized_updates[key] = value
        if request.did_follow_plan is not None:
            normalized_updates["did_follow_plan"] = normalized_follow_plan
        if consistency_warnings:
            merged_warnings = _merge_warning_messages(
                base_messages=json_safe_list(raw_warning_messages) if raw_warning_messages is not None else existing_warning_messages,
                extra_messages=consistency_warnings,
            )
            normalized_updates["warning_messages_json"] = merged_warnings
        normalized_updates["updated_at"] = utc_now_iso()
        row = self._store.update_review_record(review_id, normalized_updates)
        if row is None:
            return None
        return self._to_review_record(row)

    def _to_review_record(self, payload: dict) -> ReviewRecord:
        linked_trade = None
        if payload.get("linked_trade_id"):
            linked_trade = self._trade_service.get_trade(str(payload["linked_trade_id"]))
        linked_snapshot = None
        snapshot_id = payload.get("linked_decision_snapshot_id")
        if snapshot_id:
            linked_snapshot = self._decision_snapshot_service.get_snapshot(str(snapshot_id))
        return ReviewRecord(
            review_id=str(payload["review_id"]),
            symbol=str(payload["symbol"]),
            review_date=parse_iso_date(str(payload["review_date"])),
            linked_trade_id=payload.get("linked_trade_id"),
            linked_decision_snapshot_id=payload.get("linked_decision_snapshot_id"),
            outcome_label=str(payload["outcome_label"]),
            holding_days=payload.get("holding_days"),
            max_favorable_excursion=payload.get("max_favorable_excursion"),
            max_adverse_excursion=payload.get("max_adverse_excursion"),
            exit_reason=payload.get("exit_reason"),
            did_follow_plan=str(payload["did_follow_plan"]),
            review_summary=str(payload["review_summary"]),
            lesson_tags=[str(item) for item in payload.get("lesson_tags", [])],
            warning_messages=[str(item) for item in payload.get("warning_messages", [])],
            created_at=parse_iso_datetime(str(payload["created_at"])).astimezone(timezone.utc),
            updated_at=parse_iso_datetime(str(payload["updated_at"])).astimezone(timezone.utc),
            linked_trade=linked_trade,
            linked_decision_snapshot=linked_snapshot,
        )

    def _compute_review_metrics(self, *, trade: TradeRecord, review_date: date) -> dict:
        warnings: list[str] = []
        if trade.side == "SKIP":
            return {
                "holding_days": 0,
                "max_favorable_excursion": None,
                "max_adverse_excursion": None,
                "warning_messages": warnings,
            }

        if trade.price is None:
            warnings.append("missing_entry_price")
            return {
                "holding_days": None,
                "max_favorable_excursion": None,
                "max_adverse_excursion": None,
                "warning_messages": warnings,
            }

        start_date = trade.trade_date.date()
        if review_date < start_date:
            warnings.append("review_date_before_trade_date")
            return {
                "holding_days": None,
                "max_favorable_excursion": None,
                "max_adverse_excursion": None,
                "warning_messages": warnings,
            }

        response = self._market_data_service.get_daily_bars(
            symbol=trade.symbol,
            start_date=start_date.isoformat(),
            end_date=review_date.isoformat(),
        )
        if not response.bars:
            warnings.append("daily_bars_unavailable_for_review_window")
            return {
                "holding_days": None,
                "max_favorable_excursion": None,
                "max_adverse_excursion": None,
                "warning_messages": warnings,
            }

        entry_price = float(trade.price)
        highs = [bar.high for bar in response.bars if bar.high is not None]
        lows = [bar.low for bar in response.bars if bar.low is not None]

        mfe = None
        mae = None
        if highs:
            mfe = round(((max(highs) - entry_price) / entry_price) * 100, 4)
        else:
            warnings.append("missing_high_values")
        if lows:
            mae = round(((min(lows) - entry_price) / entry_price) * 100, 4)
        else:
            warnings.append("missing_low_values")

        holding_days = (review_date - start_date).days
        return {
            "holding_days": holding_days,
            "max_favorable_excursion": mfe,
            "max_adverse_excursion": mae,
            "warning_messages": warnings,
        }


def _default_outcome_label(trade: TradeRecord) -> ReviewOutcomeLabel:
    if trade.side == "SKIP":
        return "no_trade"
    return "partial_success"


def _default_did_follow_plan(trade: TradeRecord) -> DidFollowPlan:
    if trade.strategy_alignment == "aligned":
        return "yes"
    if trade.strategy_alignment == "partially_aligned":
        return "partial"
    return "no"


def _build_review_summary(
    *,
    trade: TradeRecord,
    outcome_label: ReviewOutcomeLabel,
    did_follow_plan: DidFollowPlan,
    warnings: list[str],
) -> str:
    if trade.side == "SKIP":
        return "该候选未执行交易，当前复盘结论为 no_trade。"
    follow_text = {
        "yes": "与原计划一致",
        "partial": "与原计划部分一致",
        "no": "与原计划不一致",
    }[did_follow_plan]
    warning_text = "；存在数据缺口需谨慎解释" if warnings else ""
    return "该次交易{follow}，复盘结果为 {outcome}{warning}。".format(
        follow=follow_text,
        outcome=outcome_label,
        warning=warning_text,
    )


def _build_lesson_tags(
    *,
    trade: TradeRecord,
    outcome_label: ReviewOutcomeLabel,
    warnings: list[str],
) -> list[str]:
    tags: list[str] = []
    if trade.side == "SKIP":
        tags.append("good_skip")
    if outcome_label in {"failure", "invalidated"}:
        tags.append("quality_risk_underestimated")
    if outcome_label == "success":
        tags.append("good_exit")
    if warnings:
        tags.append("data_window_limited")
    return tags[:3]


def json_safe_list(value: object) -> list:
    if isinstance(value, list):
        return value
    return []


def _normalize_did_follow_plan(
    *,
    did_follow_plan: DidFollowPlan,
    trade: Optional[TradeRecord],
) -> tuple[DidFollowPlan, list[str]]:
    if trade is None:
        return did_follow_plan, []

    alignment = trade.strategy_alignment
    warnings: list[str] = []
    if alignment == "not_aligned" and did_follow_plan == "yes":
        warnings.append("did_follow_plan_auto_adjusted_from_yes_to_no_due_to_trade_alignment")
        return "no", warnings
    if alignment == "partially_aligned" and did_follow_plan == "yes":
        warnings.append("did_follow_plan_auto_adjusted_from_yes_to_partial_due_to_trade_alignment")
        return "partial", warnings
    return did_follow_plan, warnings


def _merge_warning_messages(*, base_messages: list[str], extra_messages: list[str]) -> list[str]:
    merged: list[str] = []
    for item in base_messages + extra_messages:
        if item and item not in merged:
            merged.append(item)
    return merged
