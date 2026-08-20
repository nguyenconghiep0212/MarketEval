from typing import List, Dict, Any, Optional, Set
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# --------------------------------------------------------------------------
# The 4 standard crawl sources every ticker should have, mirroring the URL
# patterns from backend/database/seed_db.py. Kept here as the single source
# of truth so ticker creation and the backfill endpoint stay in sync.
# --------------------------------------------------------------------------

DEFAULT_SOURCE_PUBLISHERS: List[str] = [
    "CafeF",
    "Vietstock",
    "StockBiz",
    "StockBiz_Financial_Report",
]


def build_default_source_urls(symbol: str) -> Dict[str, str]:
    """Generates the standard pool_url for each of the 4 default publishers."""
    symbol_lower = symbol.lower()
    symbol_upper = symbol.upper()
    return {
        "CafeF": f"https://cafef.vn/du-lieu/tin-doanh-nghiep/{symbol_lower}/event.chn",
        "Vietstock": f"https://finance.vietstock.vn/{symbol_upper}/tin-tuc-su-kien.htm",
        "StockBiz": f"https://web.stockbiz.vn/Stocks/{symbol_upper}/CompanyNews.aspx",
        "StockBiz_Financial_Report": f"https://web.stockbiz.vn/Stocks/{symbol_upper}/CompanyReports.aspx",
    }


async def get_existing_source_publishers(session: AsyncSession, ticker_id: int) -> Set[str]:
    """Returns the set of publishers that already have a crawler_sources row for this ticker."""
    query = text("SELECT publisher FROM crawler_sources WHERE ticker_id = :ticker_id")
    result = await session.execute(query, {"ticker_id": ticker_id})
    return {row[0] for row in result.fetchall()}


async def add_missing_crawler_sources(session: AsyncSession, ticker_id: int, symbol: str) -> int:
    """
    Inserts crawler_sources rows for any of the 4 standard publishers not
    already present for this ticker. Safe to call repeatedly — only inserts
    what's actually missing (checked at the application level, since
    crawler_sources has no unique constraint on (ticker_id, publisher) to
    rely on for ON CONFLICT). Returns the number of rows inserted.

    NOTE: does not commit — caller controls the transaction.
    """
    existing = await get_existing_source_publishers(session, ticker_id)
    urls = build_default_source_urls(symbol)
    missing = {pub: url for pub, url in urls.items() if pub not in existing}

    if not missing:
        return 0

    query = text("""
        INSERT INTO crawler_sources (ticker_id, publisher, pool_url)
        VALUES (:ticker_id, :publisher, :pool_url);
    """)
    for publisher, pool_url in missing.items():
        await session.execute(
            query, {"ticker_id": ticker_id, "publisher": publisher, "pool_url": pool_url}
        )
    return len(missing)


async def get_tickers_with_missing_sources(session: AsyncSession) -> List[Dict[str, Any]]:
    """Finds every ticker that has fewer than the 4 standard crawler_sources
    rows — covers both brand-new tickers with zero sources and older ones
    that were only partially seeded."""
    expected_count = len(DEFAULT_SOURCE_PUBLISHERS)
    query = text("""
        SELECT t.id, t.symbol, COUNT(cs.id) AS source_count
        FROM tickers t
        LEFT JOIN crawler_sources cs ON cs.ticker_id = t.id
        GROUP BY t.id, t.symbol
        HAVING COUNT(cs.id) < :expected_count
        ORDER BY t.symbol;
    """)
    result = await session.execute(query, {"expected_count": expected_count})
    return [
        {"id": row.id, "symbol": row.symbol, "source_count": row.source_count}
        for row in result.fetchall()
    ]


async def seed_missing_sources_for_all_tickers(session: AsyncSession) -> Dict[str, Any]:
    """
    Backfills crawler_sources for every ticker missing one or more of the 4
    standard sources. Intended for the 'Seed Missing Sources' button so
    existing tickers (added before source auto-seeding existed, or seeded
    only partially) get caught up in one action.
    """
    tickers = await get_tickers_with_missing_sources(session)
    details: List[Dict[str, Any]] = []
    total_sources_added = 0

    for t in tickers:
        added = await add_missing_crawler_sources(session, t["id"], t["symbol"])
        if added:
            details.append({"symbol": t["symbol"], "sources_added": added})
            total_sources_added += added

    await session.commit()

    return {
        "tickers_checked": len(tickers),
        "tickers_updated": len(details),
        "total_sources_added": total_sources_added,
        "details": details,
    }


# --------------------------------------------------------------------------
# Existing ticker CRUD, updated to auto-seed sources on creation
# --------------------------------------------------------------------------

async def get_all_tickers(session: AsyncSession) -> List[Dict[str, Any]]:
    """Fetches all tickers (both active and inactive), including how many of
    the 4 standard crawler sources have been seeded for each — lets the UI
    surface which tickers still need the backfill button."""
    query = text("""
        SELECT
            t.id, t.symbol, t.company_name, t.sector, t.is_active,
            COUNT(cs.id) AS source_count
        FROM tickers t
        LEFT JOIN crawler_sources cs ON cs.ticker_id = t.id
        GROUP BY t.id, t.symbol, t.company_name, t.sector, t.is_active
        ORDER BY t.symbol ASC;
    """)
    result = await session.execute(query)
    return [dict(row) for row in result.mappings().all()]


async def add_ticker(
    session: AsyncSession, symbol: str, company_name: str, sector: str
) -> Optional[int]:
    """
    Inserts a new ticker AND seeds its 4 default crawler sources in the same
    transaction. Returns the new ticker's id, or None if the symbol already
    exists (no ticker row inserted, no sources touched).
    """
    query = text("""
        INSERT INTO tickers (symbol, company_name, sector, is_active)
        VALUES (:symbol, :company_name, :sector, TRUE)
        ON CONFLICT (symbol) DO NOTHING
        RETURNING id;
    """)
    result = await session.execute(query, {
        "symbol": symbol.upper(),
        "company_name": company_name,
        "sector": sector
    })
    row = result.fetchone()
    if not row:
        await session.rollback()
        return None

    ticker_id = row[0]
    await add_missing_crawler_sources(session, ticker_id, symbol.upper())
    await session.commit()
    return ticker_id

async def toggle_ticker_status(session: AsyncSession, ticker_id: int, is_active: bool) -> None:
    """Updates the is_active status of a ticker."""
    query = text("UPDATE tickers SET is_active = :is_active WHERE id = :ticker_id;")
    await session.execute(query, {"is_active": is_active, "ticker_id": ticker_id})
    await session.commit()

async def delete_ticker(session: AsyncSession, ticker_id: int) -> None:
    """
    Deletes a ticker. 
    WARNING: Because of ON DELETE CASCADE in your schema, this will wipe all 
    associated news_articles, article_attachments, article_embeddings, and
    crawler_sources.
    """
    query = text("DELETE FROM tickers WHERE id = :ticker_id;")
    await session.execute(query, {"ticker_id": ticker_id})
    await session.commit()