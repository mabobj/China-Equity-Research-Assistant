"""通用文本规范化与轻量乱码修复。"""

from __future__ import annotations

from typing import Final

_LATIN_MOJIBAKE_HINTS: Final[tuple[str, ...]] = (
    "脙",
    "脗",
    "芒",
    "忙",
    "氓",
    "莽",
    "猫",
    "茅",
    "锚",
    "茂",
    "冒",
    "陇",
    "楼",
)

_CN_MOJIBAKE_HINTS: Final[tuple[str, ...]] = (
    "婵烇綀浜",
    "濞ｈ京",
    "缂佸浄",
    "闁",
    "閻",
    "閸",
    "椤",
    "婵",
    "浜",
    "濞",
    "濠",
    "鎼",
    "鐎",
    "濡",
    "锛",
    "鈼",
    "濮瑰",
    "閺夊牆",
)


def normalize_display_text(text: str | None) -> str:
    """标准化展示文本并尝试修复常见乱码。"""
    if not text:
        return ""
    normalized = text.strip()
    if not normalized:
        return ""
    repaired = _repair_mojibake(normalized)
    return repaired.strip()


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
    score -= text.count("锟") * 6
    score -= text.count("閿") * 4
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

