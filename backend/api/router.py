from fastapi import APIRouter
from backend.api.endpoints import news, tickers, risk, crawler

api_router = APIRouter()

# Include endpoint modules with clean URL prefixes and OpenAPI tags
api_router.include_router(tickers.router, prefix="/tickers", tags=["Tickers"])
api_router.include_router(news.router, prefix="/news", tags=["News"])
api_router.include_router(crawler.router, prefix="/crawl", tags=["Crawl"])
# api_router.include_router(risk.router, prefix="/risk", tags=["Risk Signals"])