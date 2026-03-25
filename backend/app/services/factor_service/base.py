"""Factor service base contracts."""

from typing import Protocol

from app.schemas.factor import FactorSnapshot
from app.schemas.technical import TechnicalSnapshot


class FactorSnapshotBuilder(Protocol):
    """Build factor snapshot from structured technical inputs."""

    def build_from_technical_snapshot(
        self,
        technical_snapshot: TechnicalSnapshot,
    ) -> FactorSnapshot:
        """Build one factor snapshot."""

