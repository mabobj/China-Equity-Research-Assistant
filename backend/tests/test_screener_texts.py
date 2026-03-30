"""选股文案规范化测试。"""

from app.services.screener_service.texts import (
    ensure_chinese_short_reason,
    normalize_candidate_display_fields,
)


def test_ensure_chinese_short_reason_replaces_legacy_english_template() -> None:
    """历史英文模板应回退为中文可读短理由。"""
    reason = ensure_chinese_short_reason(
        list_type="WATCH_BREAKOUT",
        short_reason=(
            "is worth tracking, but breakout confirmation is still needed. "
            "优势: 趋势改善 | 风险: 财务字段缺失较多"
        ),
    )
    assert "is worth tracking" not in reason
    assert "优势:" in reason


def test_normalize_candidate_display_fields_repairs_mojibake_name_and_reason() -> None:
    """常见乱码文本应被纠偏为可读中文。"""
    fields = normalize_candidate_display_fields(
        name="娣辩汉缁囷肌",
        list_type="WATCH_BREAKOUT",
        short_reason="浼樺娍: 鐭湡瓒嬪娍鏀瑰杽 | 椋庨櫓: 璐㈠姟瀛楁缂哄け杈冨",
        headline_verdict=(
            "娣辩汉缁囷肌 is worth tracking, but breakout confirmation is still needed. "
            "浼樺娍: 鐭湡瓒嬪娍鏀瑰杽 | 椋庨櫓: 璐㈠姟瀛楁缂哄け杈冨"
        ),
        top_positive_factors=["鐭湡瓒嬪娍鏀瑰杽"],
        top_negative_factors=["璐㈠姟瀛楁缂哄け杈冨"],
        risk_notes=["璐㈠姟瀛楁缂哄け杈冨"],
        evidence_hints=["鐭湡瓒嬪娍鏀瑰杽"],
    )

    assert fields["name"] == "深纺织Ａ"
    assert "is worth tracking" not in str(fields["headline_verdict"])
    assert "优势:" in str(fields["short_reason"])
    assert fields["top_positive_factors"] == ["短期趋势改善"]
    assert fields["top_negative_factors"] == ["财务字段缺失较多"]
