"""交易记录服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.db.trade_review_store import TradeReviewStore, parse_iso_datetime, utc_now_iso
from app.schemas.journal import (
    CreateTradeFromCurrentDecisionRequest,
    CreateTradeRequest,
    DecisionSnapshotRecord,
    StrategyAlignment,
    TradeSide,
    PositionCase,
    TradeListResponse,
    TradeRecord,
    UpdateTradeRequest,
    validate_trade_reason_type_for_side,
)
from app.services.data_service.normalize import normalize_symbol
from app.services.decision_snapshot_service.decision_snapshot_service import (
    DecisionSnapshotService,
)


class TradeService:
    """管理交易记录的创建、查询与更新。"""

    def __init__(
        self,
        *,
        store: TradeReviewStore,
        decision_snapshot_service: DecisionSnapshotService,
    ) -> None:
        self._store = store
        self._decision_snapshot_service = decision_snapshot_service

    def create_trade(self, request: CreateTradeRequest) -> TradeRecord:
        snapshot = self._resolve_snapshot_for_create(request)
        trade_date = request.trade_date.astimezone(timezone.utc)
        amount = _resolve_amount(request.price, request.quantity, request.amount)
        strategy_alignment = _resolve_strategy_alignment(
            requested_alignment=request.strategy_alignment,
            snapshot_action=snapshot.action if snapshot else None,
            side=request.side,
            override_reason=request.alignment_override_reason,
        )
        now_iso = utc_now_iso()
        payload = {
            "trade_id": "tr-" + uuid4().hex[:16],
            "symbol": normalize_symbol(request.symbol),
            "side": request.side,
            "trade_date": trade_date.isoformat(),
            "price": request.price,
            "quantity": request.quantity,
            "amount": amount,
            "reason_type": request.reason_type,
            "note": request.note,
            "decision_snapshot_id": snapshot.snapshot_id if snapshot else request.decision_snapshot_id,
            "strategy_alignment": strategy_alignment,
            "alignment_override_reason": request.alignment_override_reason,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        self._store.create_trade_record(payload)
        return self._to_trade_record(payload=payload, snapshot=snapshot)

    def create_from_current_decision(
        self,
        request: CreateTradeFromCurrentDecisionRequest,
    ) -> TradeRecord:
        snapshot = self._decision_snapshot_service.create_from_symbol(
            symbol=request.symbol,
            use_llm=request.use_llm,
        )
        strategy_alignment = _resolve_strategy_alignment(
            requested_alignment=request.strategy_alignment,
            snapshot_action=snapshot.action,
            side=request.side,
            override_reason=request.alignment_override_reason,
        )
        trade_date = (request.trade_date or datetime.now(timezone.utc)).astimezone(timezone.utc)
        amount = _resolve_amount(request.price, request.quantity, request.amount)
        now_iso = utc_now_iso()
        payload = {
            "trade_id": "tr-" + uuid4().hex[:16],
            "symbol": normalize_symbol(request.symbol),
            "side": request.side,
            "trade_date": trade_date.isoformat(),
            "price": request.price,
            "quantity": request.quantity,
            "amount": amount,
            "reason_type": request.reason_type,
            "note": request.note,
            "decision_snapshot_id": snapshot.snapshot_id,
            "strategy_alignment": strategy_alignment,
            "alignment_override_reason": request.alignment_override_reason,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        self._store.create_trade_record(payload)
        return self._to_trade_record(payload=payload, snapshot=snapshot)

    def get_trade(self, trade_id: str) -> Optional[TradeRecord]:
        row = self._store.get_trade_record(trade_id)
        if row is None:
            return None
        snapshot = self._decision_snapshot_service.get_snapshot(
            str(row.get("decision_snapshot_id")),
        ) if row.get("decision_snapshot_id") else None
        return self._to_trade_record(payload=row, snapshot=snapshot)

    def list_trades(
        self,
        *,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 50,
    ) -> TradeListResponse:
        normalized_symbol = normalize_symbol(symbol) if symbol else None
        rows = self._store.list_trade_records(
            symbol=normalized_symbol,
            side=side,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
        items = [self._to_trade_record(payload=row) for row in rows]
        return TradeListResponse(count=len(items), items=items)

    def update_trade(self, trade_id: str, request: UpdateTradeRequest) -> Optional[TradeRecord]:
        current = self._store.get_trade_record(trade_id)
        if current is None:
            return None

        updates = request.model_dump(exclude_none=True)
        merged_side = str(updates.get("side", current.get("side")))
        merged_reason_type = str(updates.get("reason_type", current.get("reason_type")))
        validate_trade_reason_type_for_side(
            merged_reason_type,  # type: ignore[arg-type]
            merged_side,  # type: ignore[arg-type]
        )
        if "trade_date" in updates:
            updates["trade_date"] = updates["trade_date"].astimezone(timezone.utc).isoformat()
        if "symbol" in updates:
            updates["symbol"] = normalize_symbol(str(updates["symbol"]))
        if any(key in updates for key in ("price", "quantity", "amount")):
            merged_price = updates.get("price", current.get("price"))
            merged_quantity = updates.get("quantity", current.get("quantity"))
            merged_amount = updates.get("amount", current.get("amount"))
            updates["amount"] = _resolve_amount(merged_price, merged_quantity, merged_amount)
        merged_snapshot_id = str(
            updates.get("decision_snapshot_id", current.get("decision_snapshot_id")),
        ) if (updates.get("decision_snapshot_id", current.get("decision_snapshot_id"))) else None
        snapshot = self._decision_snapshot_service.get_snapshot(merged_snapshot_id) if merged_snapshot_id else None
        requested_alignment = str(
            updates.get("strategy_alignment", current.get("strategy_alignment", "unknown")),
        )
        override_reason = str(
            updates.get("alignment_override_reason", current.get("alignment_override_reason")),
        ) if updates.get("alignment_override_reason", current.get("alignment_override_reason")) else None
        updates["strategy_alignment"] = _resolve_strategy_alignment(
            requested_alignment=requested_alignment,  # type: ignore[arg-type]
            snapshot_action=snapshot.action if snapshot else None,
            side=merged_side,  # type: ignore[arg-type]
            override_reason=override_reason,
        )
        updates["alignment_override_reason"] = override_reason
        updates["updated_at"] = utc_now_iso()

        updated = self._store.update_trade_record(trade_id, updates)
        if updated is None:
            return None
        snapshot = self._decision_snapshot_service.get_snapshot(
            str(updated.get("decision_snapshot_id")),
        ) if updated.get("decision_snapshot_id") else None
        return self._to_trade_record(payload=updated, snapshot=snapshot)

    def build_position_cases(self, *, symbol: Optional[str] = None) -> list[PositionCase]:
        trades = self.list_trades(symbol=symbol, limit=500).items
        grouped: dict[str, list[TradeRecord]] = {}
        for trade in trades:
            grouped.setdefault(trade.symbol, []).append(trade)

        cases: list[PositionCase] = []
        for symbol_key, symbol_trades in grouped.items():
            ordered = sorted(symbol_trades, key=lambda item: item.trade_date)
            net_quantity = 0.0
            for item in ordered:
                quantity = float(item.quantity or 0)
                if item.side in {"BUY", "ADD"}:
                    net_quantity += quantity
                elif item.side in {"SELL", "REDUCE"}:
                    net_quantity -= quantity
            cases.append(
                PositionCase(
                    case_id="pc-" + uuid4().hex[:12],
                    symbol=symbol_key,
                    trade_ids=[item.trade_id for item in ordered],
                    review_ids=[],
                    opened_at=ordered[0].trade_date if ordered else None,
                    closed_at=ordered[-1].trade_date if ordered and net_quantity <= 0 else None,
                    net_quantity=net_quantity,
                    notes={},
                )
            )
        return cases

    def _resolve_snapshot_for_create(self, request: CreateTradeRequest) -> Optional[DecisionSnapshotRecord]:
        if request.decision_snapshot_id:
            snapshot = self._decision_snapshot_service.get_snapshot(request.decision_snapshot_id)
            if snapshot is None:
                raise ValueError("指定的 decision_snapshot_id 不存在。")
            return snapshot

        if request.auto_create_snapshot:
            return self._decision_snapshot_service.create_from_symbol(
                symbol=request.symbol,
                use_llm=request.use_llm,
            )
        return None

    def _to_trade_record(
        self,
        *,
        payload: dict,
        snapshot: Optional[DecisionSnapshotRecord] = None,
    ) -> TradeRecord:
        resolved_snapshot = snapshot
        if resolved_snapshot is None and payload.get("decision_snapshot_id"):
            resolved_snapshot = self._decision_snapshot_service.get_snapshot(
                str(payload["decision_snapshot_id"]),
            )

        return TradeRecord(
            trade_id=str(payload["trade_id"]),
            symbol=str(payload["symbol"]),
            side=str(payload["side"]),
            trade_date=parse_iso_datetime(str(payload["trade_date"])).astimezone(timezone.utc),
            price=payload.get("price"),
            quantity=payload.get("quantity"),
            amount=payload.get("amount"),
            reason_type=str(payload["reason_type"]),
            note=payload.get("note"),
            decision_snapshot_id=payload.get("decision_snapshot_id"),
            strategy_alignment=str(payload.get("strategy_alignment", "unknown")),
            alignment_override_reason=payload.get("alignment_override_reason"),
            created_at=parse_iso_datetime(str(payload["created_at"])).astimezone(timezone.utc),
            updated_at=parse_iso_datetime(str(payload["updated_at"])).astimezone(timezone.utc),
            decision_snapshot=resolved_snapshot,
        )


def _resolve_amount(
    price: Optional[float],
    quantity: Optional[int],
    amount: Optional[float],
) -> Optional[float]:
    if amount is not None:
        return amount
    if price is None or quantity is None:
        return None
    return round(price * quantity, 6)


def _infer_strategy_alignment(
    *,
    snapshot_action: Optional[str],
    side: TradeSide,
) -> StrategyAlignment:
    if not snapshot_action:
        return "unknown"

    normalized_action = str(snapshot_action).upper()

    if normalized_action in {"AVOID"}:
        if side in {"BUY", "ADD"}:
            return "not_aligned"
        return "aligned"

    if normalized_action in {"BUY", "BUY_NOW"}:
        if side in {"BUY", "ADD"}:
            return "aligned"
        return "not_aligned"

    if normalized_action in {"WATCH", "WAIT_PULLBACK", "WAIT_BREAKOUT", "RESEARCH_ONLY"}:
        if side == "SKIP":
            return "aligned"
        return "partially_aligned"

    return "unknown"


def _resolve_strategy_alignment(
    *,
    requested_alignment: StrategyAlignment,
    snapshot_action: Optional[str],
    side: TradeSide,
    override_reason: Optional[str],
) -> StrategyAlignment:
    inferred_alignment = _infer_strategy_alignment(
        snapshot_action=snapshot_action,
        side=side,
    )

    if requested_alignment == "unknown":
        return inferred_alignment

    if inferred_alignment in {"unknown", requested_alignment}:
        return requested_alignment

    if override_reason and override_reason.strip():
        return requested_alignment

    raise ValueError(
        "当前交易与原判断存在冲突，若要手动指定 strategy_alignment，请提供 alignment_override_reason。",
    )
