"""Workflow run artifact persistence."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from app.services.workflow_runtime.base import (
    WorkflowArtifact,
    WorkflowRunResult,
    WorkflowStepResult,
)


class FileWorkflowArtifactStore:
    """Persist workflow run artifacts as JSON files."""

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, result: WorkflowRunResult) -> WorkflowArtifact:
        artifact = WorkflowArtifact(
            run_id=result.run_id,
            workflow_name=result.workflow_name,
            status=result.status,
            started_at=result.started_at,
            finished_at=result.finished_at,
            input_summary=result.input_summary,
            steps=result.steps,
            final_output_summary=result.final_output_summary,
            final_output=(
                result.final_output.model_dump(mode="json")
                if result.final_output is not None
                else None
            ),
            error_message=result.error_message,
        )
        self.save_artifact(artifact)
        return artifact

    def save_artifact(self, artifact: WorkflowArtifact) -> None:
        file_path = self._get_file_path(artifact.run_id)
        file_path.write_text(
            json.dumps(self._serialize_artifact(artifact), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_run(self, run_id: str) -> WorkflowArtifact:
        file_path = self._get_file_path(run_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Workflow run '{run_id}' not found.")

        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return WorkflowArtifact(
            run_id=payload["run_id"],
            workflow_name=payload["workflow_name"],
            status=payload["status"],
            started_at=datetime.fromisoformat(payload["started_at"]),
            finished_at=(
                datetime.fromisoformat(payload["finished_at"])
                if payload.get("finished_at") is not None
                else None
            ),
            input_summary=payload.get("input_summary", {}),
            steps=tuple(
                WorkflowStepResult(
                    node_name=item["node_name"],
                    status=item["status"],
                    started_at=(
                        datetime.fromisoformat(item["started_at"])
                        if item.get("started_at") is not None
                        else None
                    ),
                    finished_at=(
                        datetime.fromisoformat(item["finished_at"])
                        if item.get("finished_at") is not None
                        else None
                    ),
                    message=item.get("message"),
                    input_summary=item.get("input_summary", {}),
                    output_summary=item.get("output_summary", {}),
                    error_message=item.get("error_message"),
                )
                for item in payload.get("steps", [])
            ),
            final_output_summary=payload.get("final_output_summary", {}),
            final_output=payload.get("final_output"),
            error_message=payload.get("error_message"),
        )

    def _get_file_path(self, run_id: str) -> Path:
        return self._root_dir / f"{run_id}.json"

    def _serialize_artifact(self, artifact: WorkflowArtifact) -> dict[str, Any]:
        payload = asdict(artifact)
        payload["started_at"] = artifact.started_at.isoformat()
        payload["finished_at"] = (
            artifact.finished_at.isoformat() if artifact.finished_at is not None else None
        )
        payload["steps"] = [self._serialize_step(step) for step in artifact.steps]
        return payload

    def _serialize_step(self, step: WorkflowStepResult) -> dict[str, Any]:
        payload = asdict(step)
        payload["started_at"] = (
            step.started_at.isoformat() if step.started_at is not None else None
        )
        payload["finished_at"] = (
            step.finished_at.isoformat() if step.finished_at is not None else None
        )
        return payload
