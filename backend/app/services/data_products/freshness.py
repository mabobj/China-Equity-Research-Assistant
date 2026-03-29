"""Freshness policy helpers for daily products."""

from __future__ import annotations

from datetime import date, timedelta


def resolve_last_closed_trading_day(today: date | None = None) -> date:
    """Return the last closed trading day conservatively.

    We intentionally do not chase today's daily bar on page access. Even on a
    weekday, the default target is the previous trading day.
    """

    anchor = today or date.today()
    candidate = anchor - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def is_current_for_as_of_date(
    *,
    as_of_date: date,
    today: date | None = None,
) -> bool:
    """Whether a daily product is current under the default freshness policy."""

    return as_of_date >= resolve_last_closed_trading_day(today=today)
