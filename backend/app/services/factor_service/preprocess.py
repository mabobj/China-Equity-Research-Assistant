"""Factor preprocessing helpers."""


def clamp_score(value: float) -> int:
    """Clamp score into 0-100."""
    return max(0, min(100, int(round(value))))

