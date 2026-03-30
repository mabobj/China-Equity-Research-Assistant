"""选股文案构建与兼容归一化。"""

from __future__ import annotations

from typing import Final

_ENGLISH_MARKERS: Final[tuple[str, ...]] = (
    "is actionable now, but still needs execution discipline.",
    "is worth tracking, but the better setup is a pullback.",
    "is worth tracking, but breakout confirmation is still needed.",
    "made the research list, but not the trading list yet.",
    "stays on the avoid side for now.",
    "needs more confirmation.",
)


def build_headline_verdict(name: str, list_type: str, short_reason: str) -> str:
    """生成统一的简体中文结论文案。"""
    prefix_map = {
        "READY_TO_BUY": f"{name} 当前具备执行条件，但仍需严格纪律。",
        "WATCH_PULLBACK": f"{name} 值得跟踪，更优方案是等待回踩确认。",
        "WATCH_BREAKOUT": f"{name} 值得跟踪，仍需突破确认后再执行。",
        "RESEARCH_ONLY": f"{name} 已进入研究池，但尚未进入交易池。",
        "AVOID": f"{name} 当前维持回避结论。",
    }
    prefix = prefix_map.get(list_type, f"{name} 仍需更多确认信号。")
    return f"{prefix} {short_reason}".strip()


def build_short_reason(list_type: str) -> str:
    """按分桶生成默认中文简述。"""
    mapping = {
        "READY_TO_BUY": "趋势与触发条件相对协同，可继续跟踪执行窗口。",
        "WATCH_PULLBACK": "趋势仍可观察，更适合等待回踩确认后再评估。",
        "WATCH_BREAKOUT": "趋势仍可观察，更适合等待突破确认后再评估。",
        "RESEARCH_ONLY": "当前信号分化，先保留研究跟踪，不建议直接执行。",
        "AVOID": "当前风险收益不匹配，维持回避。",
    }
    return mapping.get(list_type, "当前信号仍需更多确认。")


def ensure_chinese_headline_verdict(
    *,
    name: str,
    list_type: str,
    short_reason: str,
    headline_verdict: str | None,
) -> str:
    """确保输出文案为简体中文。

    对历史缓存中残留的英文模板自动回填为中文版本。
    """
    if not headline_verdict:
        return build_headline_verdict(name, list_type, short_reason)
    if _contains_legacy_english(headline_verdict):
        return build_headline_verdict(name, list_type, short_reason)
    return headline_verdict


def ensure_chinese_short_reason(
    *,
    list_type: str,
    short_reason: str | None,
) -> str:
    """确保 short_reason 输出为中文模板，不夹杂历史英文句式。"""
    if not short_reason:
        return build_short_reason(list_type)

    normalized = short_reason.strip()
    if not normalized:
        return build_short_reason(list_type)

    if _contains_legacy_english(normalized):
        # 历史缓存中常见“英文句子 + 优势/风险”拼接，尽量保留中文片段。
        for marker in ("优势:", "风险:"):
            marker_index = normalized.find(marker)
            if marker_index >= 0:
                candidate = normalized[marker_index:].strip(" |;")
                if candidate:
                    return candidate
        return build_short_reason(list_type)

    return normalized


def _contains_legacy_english(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in _ENGLISH_MARKERS):
        return True
    return " is " in lowered and "worth tracking" in lowered
