"""Provider 能力矩阵与健康度策略。"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.provider import CapabilityPolicyReport
from app.services.data_service.providers.base import (
    ANNOUNCEMENT_CAPABILITY,
    DAILY_BAR_CAPABILITY,
    FINANCIAL_SUMMARY_CAPABILITY,
    INTRADAY_BAR_CAPABILITY,
    PROFILE_CAPABILITY,
    TIMELINE_CAPABILITY,
    UNIVERSE_CAPABILITY,
    MarketDataCapability,
)


@dataclass(frozen=True)
class CapabilityPolicy:
    """单个数据域的 provider 策略。"""

    capability: MarketDataCapability
    preferred_providers: tuple[str, ...]
    allow_stale_fallback: bool
    require_local_persistence: bool
    notes: str


_CAPABILITY_POLICIES: dict[MarketDataCapability, CapabilityPolicy] = {
    DAILY_BAR_CAPABILITY: CapabilityPolicy(
        capability=DAILY_BAR_CAPABILITY,
        preferred_providers=("tdx_api", "mootdx", "akshare", "baostock"),
        allow_stale_fallback=True,
        require_local_persistence=True,
        notes="日线是长期主链路输入，优先本地/局域网源；允许在远端失败时退回本地已落盘快照。",
    ),
    INTRADAY_BAR_CAPABILITY: CapabilityPolicy(
        capability=INTRADAY_BAR_CAPABILITY,
        preferred_providers=("tdx_api", "mootdx", "akshare", "baostock"),
        allow_stale_fallback=False,
        require_local_persistence=False,
        notes="分钟线偏实时，不接受 stale fallback；当前以可用性优先，不强制本地落盘。",
    ),
    TIMELINE_CAPABILITY: CapabilityPolicy(
        capability=TIMELINE_CAPABILITY,
        preferred_providers=("tdx_api", "mootdx", "akshare", "baostock"),
        allow_stale_fallback=False,
        require_local_persistence=False,
        notes="分时线偏实时展示，不接受 stale fallback。",
    ),
    UNIVERSE_CAPABILITY: CapabilityPolicy(
        capability=UNIVERSE_CAPABILITY,
        preferred_providers=("tdx_api", "akshare", "baostock"),
        allow_stale_fallback=True,
        require_local_persistence=True,
        notes="股票池属于基础索引数据，允许使用最近一次本地快照兜底。",
    ),
    PROFILE_CAPABILITY: CapabilityPolicy(
        capability=PROFILE_CAPABILITY,
        preferred_providers=("tdx_api", "akshare", "baostock", "cninfo"),
        allow_stale_fallback=True,
        require_local_persistence=True,
        notes="基础资料允许本地缓存兜底，但优先补齐完整字段。",
    ),
    ANNOUNCEMENT_CAPABILITY: CapabilityPolicy(
        capability=ANNOUNCEMENT_CAPABILITY,
        preferred_providers=("cninfo", "akshare"),
        allow_stale_fallback=False,
        require_local_persistence=True,
        notes="公告索引以正式披露源为准，不建议跨窗口使用 stale fallback。",
    ),
    FINANCIAL_SUMMARY_CAPABILITY: CapabilityPolicy(
        capability=FINANCIAL_SUMMARY_CAPABILITY,
        preferred_providers=("akshare", "baostock"),
        allow_stale_fallback=False,
        require_local_persistence=True,
        notes="财务摘要优先使用已清洗快照；不建议在显著过期场景下继续沿用旧值。",
    ),
}


def get_capability_policy(capability: MarketDataCapability) -> CapabilityPolicy | None:
    """返回单个 capability 的集中策略。"""

    return _CAPABILITY_POLICIES.get(capability)


def get_all_capability_policies() -> list[CapabilityPolicy]:
    """返回全部 capability 策略。"""

    return list(_CAPABILITY_POLICIES.values())


def get_preferred_provider_order(capability: MarketDataCapability) -> tuple[str, ...]:
    """返回 capability 对应的 provider 优先顺序。"""

    policy = get_capability_policy(capability)
    if policy is None:
        return tuple()
    return policy.preferred_providers


def build_capability_policy_reports() -> list[CapabilityPolicyReport]:
    """构建可直接暴露给上层的 capability 策略摘要。"""

    return [
        CapabilityPolicyReport(
            capability=policy.capability,
            preferred_providers=list(policy.preferred_providers),
            allow_stale_fallback=policy.allow_stale_fallback,
            require_local_persistence=policy.require_local_persistence,
            notes=policy.notes,
        )
        for policy in get_all_capability_policies()
    ]
