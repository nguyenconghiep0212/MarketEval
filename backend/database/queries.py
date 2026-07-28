from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def upsert_ticker(
    session: AsyncSession,
    symbol: str,
    company_name: str,
    sector: Optional[str] = None
) -> None:
    """Inserts or updates a ticker record in the database."""
    query = text("""
        INSERT INTO tickers (symbol, company_name, sector, is_active)
        VALUES (:symbol, :company_name, :sector, TRUE)
        ON CONFLICT (symbol) 
        DO UPDATE SET 
            company_name = EXCLUDED.company_name,
            sector = EXCLUDED.sector,
            is_active = TRUE;
    """)
    await session.execute(
        query,
        {"symbol": symbol.upper(), "company_name": company_name, "sector": sector}
    )


async def get_active_tickers(session: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieves all active tickers from the database as a list of dictionaries."""
    query = text("SELECT id, symbol, company_name, sector FROM tickers WHERE is_active = TRUE")
    result = await session.execute(query)
    rows = result.mappings().all()
    return [dict(row) for row in rows]


async def get_ticker_id_by_symbol(session: AsyncSession, symbol: str) -> Optional[int]:
    """Gets the database ID for a given ticker symbol."""
    query = text("SELECT id FROM tickers WHERE symbol = :symbol AND is_active = TRUE")
    result = await session.execute(query, {"symbol": symbol.upper()})
    row = result.fetchone()
    return row[0] if row else None


async def is_content_hash_duplicate(session: AsyncSession, content_hash: str) -> bool:
    """Checks if an article with the given content hash already exists."""
    query = text("SELECT EXISTS(SELECT 1 FROM news_articles WHERE content_hash = :hash)")
    result = await session.execute(query, {"hash": content_hash})
    return bool(result.scalar())


async def insert_news_article(
    session: AsyncSession,
    ticker_id: Optional[int],
    source_url: str,
    publisher: str,
    published_at: Any,
    headline: str,
    raw_content: str,
    cleaned_content: str,
    content_hash: str,
) -> None:
    """Inserts a new news article into the database."""
    query = text("""
        INSERT INTO news_articles (
            ticker_id, source_url, publisher, published_at, headline, raw_content, cleaned_content, content_hash
        ) VALUES (
            :ticker_id, :source_url, :publisher, :published_at, :headline, :raw_content, :cleaned_content, :content_hash
        ) ON CONFLICT (source_url) DO NOTHING;
    """)
    await session.execute(
        query,
        {
            "ticker_id": ticker_id,
            "source_url": source_url,
            "publisher": publisher,
            "published_at": published_at,
            "headline": headline,
            "raw_content": raw_content,
            "cleaned_content": cleaned_content,
            "content_hash": content_hash,
        }
    )
    
async def get_active_tickers_with_sources(session: AsyncSession, publisher: str) -> List[Dict[str, Any]]:
    """Fetches active tickers and their specific pool_url for a given publisher."""
    query = text("""
        SELECT t.id, t.symbol, cs.pool_url
        FROM tickers t
        JOIN crawler_sources cs ON t.id = cs.ticker_id
        WHERE t.is_active = TRUE AND cs.publisher = :publisher
    """)
    res = await session.execute(query, {"publisher": publisher})
    return [{"id": row.id, "symbol": row.symbol, "pool_url": row.pool_url} for row in res.fetchall()]


async def save_articles(session: AsyncSession, ticker_id: int, articles: List[Dict[str, Any]]) -> int:
    """
    Inserts parsed articles into news_articles using ON CONFLICT DO NOTHING.
    Logs any article that was parsed but skipped as a duplicate.
    """
    query = text("""
        INSERT INTO news_articles (ticker_id, source_url, publisher, headline, raw_content, content_hash, published_at)
        VALUES (:ticker_id, :source_url, :publisher, :headline, :raw_content, :content_hash, :published_at)
        ON CONFLICT (content_hash) DO NOTHING;
    """)

    inserted_count = 0
    for art in articles:
        result = await session.execute(query, {
            "ticker_id": ticker_id,
            "source_url": art["source_url"],
            "publisher": art["publisher"],
            "headline": art["headline"],
            "raw_content": art["raw_content"],
            "content_hash": art["content_hash"],
            "published_at": art.get("published_at")
        })
        
        if result.rowcount > 0:
            inserted_count += 1
        else:
            print(f"  ⏭️ Parsed but skipped (Already in DB): {art['source_url']}")

    await session.commit()
    return inserted_count