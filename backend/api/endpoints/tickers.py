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
    delete_ticker
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
    """Fetch all tickers (active and inactive) for the management UI."""
    try:
        tickers = await get_all_tickers(session)
        return {"tickers": tickers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ticker(ticker: TickerCreate, session: AsyncSession = Depends(get_db)):
    """Add a new ticker to the watchlist."""
    success = await add_ticker(session, ticker.symbol, ticker.company_name, ticker.sector)
    if not success:
        raise HTTPException(status_code=400, detail=f"Ticker {ticker.symbol} already exists.")
    return {"message": f"Successfully added {ticker.symbol}."}

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