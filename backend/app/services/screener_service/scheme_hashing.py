"""Utilities for stable screener scheme hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize_scheme_payload(payload: dict[str, Any]) -> str:
    """Build a deterministic JSON string for scheme hashing."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def hash_scheme_config(payload: dict[str, Any]) -> str:
    """Return a stable hash for a scheme configuration payload."""

    canonical = canonicalize_scheme_payload(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

