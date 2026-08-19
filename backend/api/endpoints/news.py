from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import get_db
from backend.database.queries.article import get_active_tickers

router = APIRouter()

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