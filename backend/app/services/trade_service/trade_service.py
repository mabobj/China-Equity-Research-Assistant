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
    PositionCase,
    TradeListResponse,
    TradeRecord,
    UpdateTradeRequest,
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
            "strategy_alignment": request.strategy_alignment,
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
            "strategy_alignment": request.strategy_alignment,
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
        if "trade_date" in updates:
            updates["trade_date"] = updates["trade_date"].astimezone(timezone.utc).isoformat()
        if "symbol" in updates:
            updates["symbol"] = normalize_symbol(str(updates["symbol"]))
        if any(key in updates for key in ("price", "quantity", "amount")):
            merged_price = updates.get("price", current.get("price"))
            merged_quantity = updates.get("quantity", current.get("quantity"))
            merged_amount = updates.get("amount", current.get("amount"))
            updates["amount"] = _resolve_amount(merged_price, merged_quantity, merged_amount)
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

