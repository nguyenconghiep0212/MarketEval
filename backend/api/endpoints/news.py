import asyncio
from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import get_db
from backend.database.queries.article import (
    get_active_tickers,
    get_news_articles_by_tickers,
    get_articles_for_sentiment_analysis,
)
from backend.database.queries.embedding import _upsert_risk_assessment
from backend.src.nlp.engine_registry import get_sentiment_engine

router = APIRouter()


# --- Pydantic Schemas for request bodies ---
class TickerNewsRequest(BaseModel):
    tickers: List[str] = Field(
        ...,
        min_length=1,
        description="List of ticker symbols to fetch news for, e.g. ['PNJ', 'VNM']",
    )
    limit: int = Field(
        10,
        ge=1,
        description="Max number of news articles to return PER ticker",
    )


class AnalyzeSentimentRequest(BaseModel):
    article_ids: List[str] = Field(
        ...,
        min_length=1,
        description="news_articles UUIDs to analyze",
    )
    only_unscored: bool = Field(
        True,
        description=(
            "If True (default), skip any article that already has a "
            "sentiment_score — matches the 'Analyze Unscored' button. "
            "If False, force re-analyze every given article id, "
            "overwriting its existing score — matches 'Re-analyze Selected'."
        ),
    )


@router.get("/news/{ticker}", response_model=Dict[str, List[Dict[str, Any]]])
async def read_active_tickers(
    ticker: str,
    session: AsyncSession = Depends(get_db)
):
    """Fetch news for a specific stock ticker from PostgreSQL."""
    try:
        tickers = await get_active_tickers(session)
        return {"tickers": tickers}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch news for ticker {ticker}: {str(e)}",
        )


@router.post("/by-tickers", response_model=Dict[str, List[Dict[str, Any]]])
async def fetch_news_by_tickers(
    payload: TickerNewsRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Fetch news articles for a set of tickers in one call.

    Request body:
        {
            "tickers": ["PNJ", "VNM", "HPG"],
            "limit": 10
        }

    `limit` is applied PER ticker (not globally) — each ticker in `tickers`
    gets up to `limit` most-recent news_articles, ranked by published_at
    descending.

    NOTE: Financial reports are intentionally excluded here — their stored
    raw_content is just report-page boilerplate, not the actual PDF content,
    so they aren't useful for this feed. Use the PDF/attachment pipeline
    separately if you need financial report content.
    """
    try:
        articles = await get_news_articles_by_tickers(
            session, symbols=payload.tickers, limit_per_ticker=payload.limit
        )
        return {"articles": articles}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch articles for tickers {payload.tickers}: {str(e)}",
        )


@router.post("/analyze-sentiment")
async def analyze_sentiment(
    payload: AnalyzeSentimentRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Runs sentiment analysis for the given news articles and stores the
    resulting scores in risk_assessments.

    Request body:
        {
            "article_ids": ["uuid1", "uuid2", ...],
            "only_unscored": true
        }

    NOTE: the underlying transformer model is loaded once (lazily, on first
    call) and cached for the life of the process — the first request after
    a server restart will be noticeably slower than subsequent ones.
    """
    try:
        articles = await get_articles_for_sentiment_analysis(
            session, article_ids=payload.article_ids, only_unscored=payload.only_unscored
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load articles for analysis: {str(e)}",
        )

    skipped_already_scored = len(payload.article_ids) - len(articles)

    if not articles:
        return {
            "total_requested": len(payload.article_ids),
            "analyzed": 0,
            "skipped_already_scored": skipped_already_scored,
            "skipped_empty_content": 0,
            "message": (
                "Nothing to analyze — all requested articles already have a sentiment score."
                if payload.only_unscored
                else "No matching articles found for the given ids."
            ),
        }

    # Articles with no raw_content can't be analyzed — skip, don't error.
    articles_with_content = [a for a in articles if a.get("raw_content") and a["raw_content"].strip()]
    skipped_empty_content = len(articles) - len(articles_with_content)

    if not articles_with_content:
        return {
            "total_requested": len(payload.article_ids),
            "analyzed": 0,
            "skipped_already_scored": skipped_already_scored,
            "skipped_empty_content": skipped_empty_content,
            "message": "No article had usable content to analyze.",
        }

    try:
        engine = await get_sentiment_engine()
        texts = [a["raw_content"] for a in articles_with_content]
        # The actual model inference is synchronous/CPU-bound — run it in a
        # worker thread so it doesn't block the event loop for other
        # requests (e.g. the crawl-progress stream) while it runs.
        scores = await asyncio.to_thread(engine.analyze_texts_batch, texts)

        for art, score in zip(articles_with_content, scores):
            await _upsert_risk_assessment(session, "news_article_id", art["id"], score)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sentiment analysis failed: {str(e)}",
        )

    return {
        "total_requested": len(payload.article_ids),
        "analyzed": len(articles_with_content),
        "skipped_already_scored": skipped_already_scored,
        "skipped_empty_content": skipped_empty_content,
    }