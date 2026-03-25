"""分析员观点集合构建器。"""

from __future__ import annotations

from app.schemas.debate import AnalystViewsBundle
from app.schemas.review import StockReviewReport
from app.schemas.intraday import TriggerSnapshot
from app.services.debate_service.event_analyst import build_event_analyst_view
from app.services.debate_service.fundamental_analyst import (
    build_fundamental_analyst_view,
)
from app.services.debate_service.sentiment_analyst import build_sentiment_analyst_view
from app.services.debate_service.technical_analyst import build_technical_analyst_view


def build_analyst_views_bundle(
    review_report: StockReviewReport,
    trigger_snapshot: TriggerSnapshot,
) -> AnalystViewsBundle:
    """组装四类 analyst 结构化观点。"""
    return AnalystViewsBundle(
        technical=build_technical_analyst_view(
            review_report.technical_view,
            trigger_snapshot,
        ),
        fundamental=build_fundamental_analyst_view(review_report.fundamental_view),
        event=build_event_analyst_view(review_report.event_view),
        sentiment=build_sentiment_analyst_view(review_report.sentiment_view),
    )
