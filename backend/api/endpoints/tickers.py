from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import get_db
# Import the queries we just made
from backend.database.queries.tickers import (
    get_all_tickers,
    add_ticker,
    toggle_ticker_status,
    delete_ticker,
    seed_missing_sources_for_all_tickers,
    DEFAULT_SOURCE_PUBLISHERS,
)

router = APIRouter()

# --- Pydantic Schemas for Request Bodies ---
class TickerCreate(BaseModel):
    symbol: str
    company_name: str
    sector: str

class TickerToggle(BaseModel):
    is_active: bool

# --- API Endpoints ---
@router.get("/all", response_model=Dict[str, List[Dict[str, Any]]])
async def read_all_tickers(session: AsyncSession = Depends(get_db)):
    """Fetch all tickers (active and inactive) for the management UI, including
    how many of the 4 standard crawler sources each one has seeded."""
    try:
        tickers = await get_all_tickers(session)
        return {"tickers": tickers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ticker(ticker: TickerCreate, session: AsyncSession = Depends(get_db)):
    """Add a new ticker to the watchlist and auto-seed its 4 default crawler sources."""
    ticker_id = await add_ticker(session, ticker.symbol, ticker.company_name, ticker.sector)
    if ticker_id is None:
        raise HTTPException(status_code=400, detail=f"Ticker {ticker.symbol} already exists.")
    return {
        "message": f"Successfully added {ticker.symbol} and seeded its crawler sources.",
        "ticker_id": ticker_id,
        "sources_seeded": DEFAULT_SOURCE_PUBLISHERS,
    }

@router.post("/seed-sources")
async def seed_sources_for_existing_tickers(session: AsyncSession = Depends(get_db)):
    """
    Backfills crawler sources for any ticker missing one or more of the 4
    standard publishers — covers tickers added before source auto-seeding
    existed, or ones only partially seeded.
    """
    try:
        summary = await seed_missing_sources_for_all_tickers(session)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{ticker_id}/toggle")
async def update_ticker_status(
    ticker_id: int, payload: TickerToggle, session: AsyncSession = Depends(get_db)
):
    """Toggle a ticker ON or OFF."""
    await toggle_ticker_status(session, ticker_id, payload.is_active)
    return {"message": "Ticker status updated."}

@router.delete("/{ticker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_ticker(ticker_id: int, session: AsyncSession = Depends(get_db)):
    """Delete a ticker and cascade delete all its data."""
    await delete_ticker(session, ticker_id)
    return {"message": "Ticker deleted."}