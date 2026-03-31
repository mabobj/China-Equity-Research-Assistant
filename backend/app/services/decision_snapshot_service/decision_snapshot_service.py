"""决策快照服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app.db.trade_review_store import (
    TradeReviewStore,
    parse_iso_date,
    parse_iso_datetime,
    utc_now_iso,
)
from app.schemas.journal import (
    CreateDecisionSnapshotRequest,
    DecisionSnapshotCreatePayload,
    DecisionSnapshotListResponse,
    DecisionSnapshotRecord,
    DecisionSourceRef,
)
from app.services.data_service.normalize import normalize_symbol
from app.services.research_service.research_manager import ResearchManager
from app.services.workspace_bundle_service.workspace_bundle_service import (
    WorkspaceBundleService,
)


class DecisionSnapshotService:
    """负责创建与查询决策快照。"""

    def __init__(
        self,
        *,
        store: TradeReviewStore,
        workspace_bundle_service: WorkspaceBundleService,
        research_manager: ResearchManager,
    ) -> None:
        self._store = store
        self._workspace_bundle_service = workspace_bundle_service
        self._research_manager = research_manager

    def create_snapshot(self, request: CreateDecisionSnapshotRequest) -> DecisionSnapshotRecord:
        if request.payload is not None:
            payload = self._build_from_payload(request.payload)
        else:
            if request.symbol is None:
                raise ValueError("缺少 symbol，无法生成决策快照。")
            payload = self._build_from_symbol(
                symbol=request.symbol,
                use_llm=request.use_llm,
            )
        self._store.create_decision_snapshot(payload)
        return self._to_record(payload)

    def create_from_symbol(
        self,
        *,
        symbol: str,
        use_llm: Optional[bool] = None,
    ) -> DecisionSnapshotRecord:
        payload = self._build_from_symbol(symbol=symbol, use_llm=use_llm)
        self._store.create_decision_snapshot(payload)
        return self._to_record(payload)

    def get_snapshot(self, snapshot_id: str) -> Optional[DecisionSnapshotRecord]:
        row = self._store.get_decision_snapshot(snapshot_id)
        if row is None:
            return None
        return self._to_record(row)

    def list_snapshots(
        self,
        *,
        symbol: Optional[str],
        limit: int = 20,
    ) -> DecisionSnapshotListResponse:
        normalized_symbol = normalize_symbol(symbol) if symbol else None
        rows = self._store.list_decision_snapshots(symbol=normalized_symbol, limit=limit)
        items = [self._to_record(row) for row in rows]
        return DecisionSnapshotListResponse(count=len(items), items=items)

    def _build_from_symbol(
        self,
        *,
        symbol: str,
        use_llm: Optional[bool],
    ) -> dict[str, Any]:
        normalized_symbol = normalize_symbol(symbol)
        bundle = self._workspace_bundle_service.get_workspace_bundle(
            normalized_symbol,
            use_llm=use_llm,
            force_refresh=False,
            request_id=None,
        )
        research = self._research_manager.get_research_report(normalized_symbol)
        source_refs = [
            DecisionSourceRef(
                module_name=item.item_name,
                as_of_date=item.as_of_date,
                freshness_mode=item.freshness_mode,
                source_mode=item.source_mode,
                note=None,
            ).model_dump(mode="json")
            for item in bundle.freshness_summary.items
        ]
        return {
            "snapshot_id": "ds-" + uuid4().hex[:16],
            "symbol": normalized_symbol,
            "as_of_date": research.as_of_date.isoformat(),
            "action": research.action,
            "confidence": research.confidence,
            "technical_score": research.technical_score,
            "fundamental_score": research.fundamental_score,
            "event_score": research.event_score,
            "overall_score": research.overall_score,
            "thesis": research.thesis,
            "risks": list(research.risks),
            "triggers": list(research.triggers),
            "invalidations": list(research.invalidations),
            "data_quality_summary": (
                research.data_quality_summary.model_dump(mode="json")
                if research.data_quality_summary is not None
                else None
            ),
            "confidence_reasons": list(research.confidence_reasons),
            "runtime_mode_requested": bundle.runtime_mode_requested,
            "runtime_mode_effective": bundle.runtime_mode_effective,
            "source_refs": source_refs,
            "created_at": utc_now_iso(),
        }

    def _build_from_payload(self, payload: DecisionSnapshotCreatePayload) -> dict[str, Any]:
        return {
            "snapshot_id": "ds-" + uuid4().hex[:16],
            "symbol": normalize_symbol(payload.symbol),
            "as_of_date": payload.as_of_date.isoformat(),
            "action": payload.action,
            "confidence": payload.confidence,
            "technical_score": payload.technical_score,
            "fundamental_score": payload.fundamental_score,
            "event_score": payload.event_score,
            "overall_score": payload.overall_score,
            "thesis": payload.thesis,
            "risks": list(payload.risks),
            "triggers": list(payload.triggers),
            "invalidations": list(payload.invalidations),
            "data_quality_summary": (
                payload.data_quality_summary.model_dump(mode="json")
                if payload.data_quality_summary is not None
                else None
            ),
            "confidence_reasons": list(payload.confidence_reasons),
            "runtime_mode_requested": payload.runtime_mode_requested,
            "runtime_mode_effective": payload.runtime_mode_effective,
            "source_refs": [item.model_dump(mode="json") for item in payload.source_refs],
            "created_at": utc_now_iso(),
        }

    def _to_record(self, payload: dict[str, Any]) -> DecisionSnapshotRecord:
        quality_payload = payload.get("data_quality_summary")
        return DecisionSnapshotRecord(
            snapshot_id=str(payload["snapshot_id"]),
            symbol=str(payload["symbol"]),
            as_of_date=parse_iso_date(str(payload["as_of_date"])),
            action=str(payload["action"]),
            confidence=int(payload["confidence"]),
            technical_score=int(payload["technical_score"]),
            fundamental_score=int(payload["fundamental_score"]),
            event_score=int(payload["event_score"]),
            overall_score=int(payload["overall_score"]),
            thesis=str(payload["thesis"]),
            risks=[str(item) for item in payload.get("risks", [])],
            triggers=[str(item) for item in payload.get("triggers", [])],
            invalidations=[str(item) for item in payload.get("invalidations", [])],
            data_quality_summary=quality_payload,
            confidence_reasons=[str(item) for item in payload.get("confidence_reasons", [])],
            runtime_mode_requested=payload.get("runtime_mode_requested"),
            runtime_mode_effective=payload.get("runtime_mode_effective"),
            source_refs=[DecisionSourceRef.model_validate(item) for item in payload.get("source_refs", [])],
            created_at=parse_iso_datetime(str(payload["created_at"])).astimezone(timezone.utc),
        )

