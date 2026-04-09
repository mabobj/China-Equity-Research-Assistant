"""Freshness policy helpers for daily products and point-in-time inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class AnalysisDateContext:
    """统一描述一次分析所使用的有效交易日。"""

    requested_as_of_date: date | None
    effective_as_of_date: date
    policy_name: str


def normalize_to_trading_weekday(value: date) -> date:
    """保守地把日期归一到最近一个工作日。"""

    candidate = value
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def resolve_last_closed_trading_day(today: date | None = None) -> date:
    """Return the last closed trading day conservatively.

    We intentionally do not chase today's daily bar on page access. Even on a
    weekday, the default target is the previous trading day.
    """

    anchor = today or date.today()
    return normalize_to_trading_weekday(anchor - timedelta(days=1))


def resolve_daily_analysis_context(
    as_of_date: date | None = None,
    *,
    today: date | None = None,
) -> AnalysisDateContext:
    """统一解析日级分析默认使用的有效交易日。"""

    if as_of_date is not None:
        effective_as_of_date = normalize_to_trading_weekday(as_of_date)
        return AnalysisDateContext(
            requested_as_of_date=as_of_date,
            effective_as_of_date=effective_as_of_date,
            policy_name="explicit_or_weekday_normalized",
        )

    effective_as_of_date = resolve_last_closed_trading_day(today=today)
    return AnalysisDateContext(
        requested_as_of_date=None,
        effective_as_of_date=effective_as_of_date,
        policy_name="last_closed_trading_day",
    )


def resolve_daily_analysis_as_of_date(
    as_of_date: date | None = None,
    *,
    today: date | None = None,
) -> date:
    """返回日级分析默认分析日。"""

    return resolve_daily_analysis_context(
        as_of_date=as_of_date,
        today=today,
    ).effective_as_of_date


def resolve_label_analysis_context(
    as_of_date: date | None = None,
    *,
    today: date | None = None,
    safety_buffer_days: int = 14,
) -> AnalysisDateContext:
    """统一解析标签/回测默认使用的安全分析日。"""

    if as_of_date is not None:
        effective_as_of_date = normalize_to_trading_weekday(as_of_date)
        return AnalysisDateContext(
            requested_as_of_date=as_of_date,
            effective_as_of_date=effective_as_of_date,
            policy_name="explicit_or_weekday_normalized",
        )

    anchor = resolve_last_closed_trading_day(today=today) - timedelta(days=safety_buffer_days)
    effective_as_of_date = normalize_to_trading_weekday(anchor)
    return AnalysisDateContext(
        requested_as_of_date=None,
        effective_as_of_date=effective_as_of_date,
        policy_name=f"last_closed_trading_day_minus_{safety_buffer_days}_days",
    )


def resolve_label_analysis_as_of_date(
    as_of_date: date | None = None,
    *,
    today: date | None = None,
    safety_buffer_days: int = 14,
) -> date:
    """返回标签/回测默认使用的安全分析日。"""

    return resolve_label_analysis_context(
        as_of_date=as_of_date,
        today=today,
        safety_buffer_days=safety_buffer_days,
    ).effective_as_of_date


def is_current_for_as_of_date(
    *,
    as_of_date: date,
    today: date | None = None,
) -> bool:
    """Whether a daily product is current under the default freshness policy."""

    return as_of_date >= resolve_daily_analysis_as_of_date(today=today)
