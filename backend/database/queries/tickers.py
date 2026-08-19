from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def get_all_tickers(session: AsyncSession) -> List[Dict[str, Any]]:
    """Fetches all tickers (both active and inactive)."""
    query = text("SELECT id, symbol, company_name, sector, is_active FROM tickers ORDER BY symbol ASC;")
    result = await session.execute(query)
    return [dict(row) for row in result.mappings().all()]

async def add_ticker(
    session: AsyncSession, symbol: str, company_name: str, sector: str
) -> bool:
    """Inserts a new ticker into the database."""
    query = text("""
        INSERT INTO tickers (symbol, company_name, sector, is_active)
        VALUES (:symbol, :company_name, :sector, TRUE)
        ON CONFLICT (symbol) DO NOTHING;
    """)
    result = await session.execute(query, {
        "symbol": symbol.upper(),
        "company_name": company_name,
        "sector": sector
    })
    await session.commit()
    return result.rowcount > 0

async def toggle_ticker_status(session: AsyncSession, ticker_id: int, is_active: bool) -> None:
    """Updates the is_active status of a ticker."""
    query = text("UPDATE tickers SET is_active = :is_active WHERE id = :ticker_id;")
    await session.execute(query, {"is_active": is_active, "ticker_id": ticker_id})
    await session.commit()

async def delete_ticker(session: AsyncSession, ticker_id: int) -> None:
    """
    Deletes a ticker. 
    WARNING: Because of ON DELETE CASCADE in your schema, this will wipe all 
    associated news_articles, article_attachments, and article_embeddings.
    """
    query = text("DELETE FROM tickers WHERE id = :ticker_id;")
    await session.execute(query, {"ticker_id": ticker_id})
    await session.commit()