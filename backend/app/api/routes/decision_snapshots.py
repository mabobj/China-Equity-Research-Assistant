"""决策快照路由。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_decision_snapshot_service
from app.schemas.journal import (
    CreateDecisionSnapshotRequest,
    DecisionSnapshotListResponse,
    DecisionSnapshotRecord,
)

router = APIRouter(prefix="/decision-snapshots", tags=["decision-snapshots"])


@router.post("", response_model=DecisionSnapshotRecord)
def create_decision_snapshot(
    request: CreateDecisionSnapshotRequest,
    service: Any = Depends(get_decision_snapshot_service),
) -> DecisionSnapshotRecord:
    try:
        return service.create_snapshot(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Decision snapshot is temporarily unavailable.",
        ) from exc


@router.get("/{snapshot_id}", response_model=DecisionSnapshotRecord)
def get_decision_snapshot(
    snapshot_id: str,
    service: Any = Depends(get_decision_snapshot_service),
) -> DecisionSnapshotRecord:
    snapshot = service.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Decision snapshot not found.")
    return snapshot


@router.get("", response_model=DecisionSnapshotListResponse)
def list_decision_snapshots(
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    service: Any = Depends(get_decision_snapshot_service),
) -> DecisionSnapshotListResponse:
    return service.list_snapshots(symbol=symbol, limit=limit)

