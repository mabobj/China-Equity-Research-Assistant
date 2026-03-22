"""Root API router."""

from fastapi import APIRouter

from app.api.routes import health, research, reviews, screener, strategy, trades

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(research.router)
api_router.include_router(strategy.router)
api_router.include_router(screener.router)
api_router.include_router(trades.router)
api_router.include_router(reviews.router)
