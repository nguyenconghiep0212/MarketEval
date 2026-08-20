from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import get_db
from backend.database.queries.article import get_active_tickers, get_articles_by_tickers

router = APIRouter()


# --- Pydantic Schema for the request body ---
class TickerNewsRequest(BaseModel):
    tickers: List[str] = Field(
        ...,
        min_length=1,
        description="List of ticker symbols to fetch news & financial reports for, e.g. ['PNJ', 'VNM']",
    )
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Max number of items (news + financial reports combined) to return PER ticker",
    )


@router.post("/article-by-tickers", response_model=Dict[str, List[Dict[str, Any]]])
async def fetch_news_by_tickers(
    payload: TickerNewsRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Fetch news articles AND financial reports for a set of tickers in one call.

    Request body:
        {
            "tickers": ["PNJ", "VNM", "HPG"],
            "limit": 10
        }

    `limit` is applied PER ticker (not globally) — each ticker in `tickers`
    gets up to `limit` most-recent items, combining both news_articles and
    financial_analysis_articles, ranked by published_at descending.

    Each returned item has a "source_type" field: "news" or "financial_report".
    """
    try:
        articles = await get_articles_by_tickers(
            session, symbols=payload.tickers, limit_per_ticker=payload.limit
        )
        return {"articles": articles}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch articles for tickers {payload.tickers}: {str(e)}",
        )