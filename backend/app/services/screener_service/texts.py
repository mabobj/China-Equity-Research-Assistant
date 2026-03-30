"""选股文案构建与中文规范化。"""

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

_LATIN_MOJIBAKE_HINTS: Final[tuple[str, ...]] = (
    "Ã",
    "Â",
    "â",
    "æ",
    "å",
    "ç",
    "è",
    "é",
    "ê",
    "ï",
    "ð",
    "¤",
    "¥",
)

_CN_MOJIBAKE_HINTS: Final[tuple[str, ...]] = (
    "濞ｈ京",
    "娣辩",
    "缁囷",
    "閻",
    "鐠",
    "鍝",
    "顦",
    "濮",
    "亼",
    "娴",
    "婀",
    "搾",
    "瀣",
    "妞",
    "閺",
    "＄",
    "◢",
    "鍥",
    "姹夌",
    "鏉堝",
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
    """按分档生成默认中文简述。"""
    mapping = {
        "READY_TO_BUY": "趋势与触发条件相对协同，可继续跟踪执行窗口。",
        "WATCH_PULLBACK": "趋势仍可观察，更适合等待回踩确认后再评估。",
        "WATCH_BREAKOUT": "趋势仍可观察，更适合等待突破确认后再评估。",
        "RESEARCH_ONLY": "当前信号分化，先保留研究跟踪，不建议直接执行。",
        "AVOID": "当前风险收益不匹配，维持回避。",
    }
    return mapping.get(list_type, "当前信号仍需更多确认。")


def normalize_display_text(text: str | None) -> str:
    """标准化展示文本并尝试修复常见乱码。"""
    if not text:
        return ""
    normalized = text.strip()
    if not normalized:
        return ""
    repaired = _repair_mojibake(normalized)
    return repaired.strip()


def normalize_display_text_list(values: list[str] | None) -> list[str]:
    """标准化列表文本并去重保序。"""
    if not values:
        return []
    deduped: list[str] = []
    for item in values:
        normalized = normalize_display_text(item)
        if not normalized:
            continue
        if normalized in deduped:
            continue
        deduped.append(normalized)
    return deduped


def normalize_candidate_display_fields(
    *,
    name: str,
    list_type: str,
    short_reason: str | None,
    headline_verdict: str | None,
    top_positive_factors: list[str] | None = None,
    top_negative_factors: list[str] | None = None,
    risk_notes: list[str] | None = None,
    evidence_hints: list[str] | None = None,
) -> dict[str, object]:
    """统一候选展示字段的中文与编码口径。"""
    normalized_name = normalize_display_text(name) or name
    normalized_short_reason = ensure_chinese_short_reason(
        list_type=list_type,
        short_reason=short_reason,
    )
    normalized_headline = ensure_chinese_headline_verdict(
        name=normalized_name,
        list_type=list_type,
        short_reason=normalized_short_reason,
        headline_verdict=headline_verdict,
    )
    return {
        "name": normalized_name,
        "short_reason": normalized_short_reason,
        "headline_verdict": normalized_headline,
        "top_positive_factors": normalize_display_text_list(top_positive_factors),
        "top_negative_factors": normalize_display_text_list(top_negative_factors),
        "risk_notes": normalize_display_text_list(risk_notes),
        "evidence_hints": normalize_display_text_list(evidence_hints),
    }


def ensure_chinese_headline_verdict(
    *,
    name: str,
    list_type: str,
    short_reason: str,
    headline_verdict: str | None,
) -> str:
    """确保 headline_verdict 为简体中文可读文本。"""
    normalized_name = normalize_display_text(name) or name
    normalized_short_reason = ensure_chinese_short_reason(
        list_type=list_type,
        short_reason=short_reason,
    )
    normalized_headline = normalize_display_text(headline_verdict)
    if not normalized_headline:
        return build_headline_verdict(normalized_name, list_type, normalized_short_reason)
    if _contains_legacy_english(normalized_headline):
        return build_headline_verdict(normalized_name, list_type, normalized_short_reason)
    return normalized_headline


def ensure_chinese_short_reason(
    *,
    list_type: str,
    short_reason: str | None,
) -> str:
    """确保 short_reason 输出为中文模板，不夹杂历史英文句式。"""
    normalized = normalize_display_text(short_reason)
    if not normalized:
        return build_short_reason(list_type)

    if _contains_legacy_english(normalized):
        # 历史缓存常见“英文句子 + 优势/风险”拼接，尽量保留中文片段。
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


def _repair_mojibake(text: str) -> str:
    if text == "":
        return text

    candidates = _candidate_repairs(text)
    if len(candidates) == 1:
        return text

    original_score = _text_quality_score(text)
    best_text = text
    best_score = original_score
    for candidate in candidates[1:]:
        candidate_score = _text_quality_score(candidate)
        if candidate_score > best_score:
            best_text = candidate
            best_score = candidate_score

    # 文本中明显存在乱码特征时，放宽替换阈值，优先提升可读性。
    if _has_mojibake_signature(text) and best_score >= original_score - 1:
        return best_text
    if best_score >= original_score + 2:
        return best_text
    return text


def _candidate_repairs(text: str) -> list[str]:
    candidates = [text]
    for fixed in (
        _decode_latin1_as_utf8(text),
        _decode_gbk_as_utf8(text),
        _decode_gb18030_as_utf8(text),
        _decode_cp936_as_utf8(text),
    ):
        if not fixed or fixed in candidates:
            continue
        candidates.append(fixed)
    return candidates


def _decode_latin1_as_utf8(text: str) -> str:
    try:
        raw = text.encode("latin1")
    except UnicodeEncodeError:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _decode_gbk_as_utf8(text: str) -> str:
    try:
        raw = text.encode("gbk")
    except UnicodeEncodeError:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _decode_gb18030_as_utf8(text: str) -> str:
    try:
        raw = text.encode("gb18030")
    except UnicodeEncodeError:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _decode_cp936_as_utf8(text: str) -> str:
    try:
        raw = text.encode("cp936")
    except UnicodeEncodeError:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _text_quality_score(text: str) -> int:
    score = 0
    score += sum(1 for char in text if _is_cjk_char(char))
    score += sum(1 for char in text if _is_full_width_char(char))
    score -= sum(3 for char in text if char in _LATIN_MOJIBAKE_HINTS)
    score -= sum(4 for token in _CN_MOJIBAKE_HINTS if token in text)
    score -= sum(6 for char in text if _is_private_use_char(char))
    score -= text.count("�") * 6
    score -= text.count("锟") * 4
    return score


def _has_mojibake_signature(text: str) -> bool:
    if any(_is_private_use_char(char) for char in text):
        return True
    if any(token in text for token in _CN_MOJIBAKE_HINTS):
        return True
    latin_hint_count = sum(1 for char in text if char in _LATIN_MOJIBAKE_HINTS)
    return latin_hint_count >= 2


def _is_private_use_char(char: str) -> bool:
    code = ord(char)
    return 0xE000 <= code <= 0xF8FF


def _is_cjk_char(char: str) -> bool:
    code = ord(char)
    return 0x4E00 <= code <= 0x9FFF


def _is_full_width_char(char: str) -> bool:
    code = ord(char)
    return 0xFF00 <= code <= 0xFFEF
