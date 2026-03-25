"""Lightweight workflow orchestration placeholder."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.workflow import WorkflowNodeRequest, WorkflowNodeResult


class WorkflowOrchestrator:
    """Reserve explicit workflow node orchestration for future expansion."""

    def start_node(self, request: WorkflowNodeRequest) -> WorkflowNodeResult:
        started_at = datetime.now(timezone.utc)
        return WorkflowNodeResult(
            node_type=request.node_type,
            status="completed",
            symbol=request.symbol,
            message=(
                "Workflow node placeholder completed. Future versions can resume "
                "from this node directly."
            ),
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )

