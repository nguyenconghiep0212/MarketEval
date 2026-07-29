from typing import Optional, List, Dict, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import UUID, text


async def upsert_ticker(
    session: AsyncSession, symbol: str, company_name: str, sector: Optional[str] = None
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
        {"symbol": symbol.upper(), "company_name": company_name, "sector": sector},
    )


async def get_active_tickers(session: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieves all active tickers from the database as a list of dictionaries."""
    query = text(
        "SELECT id, symbol, company_name, sector FROM tickers WHERE is_active = TRUE"
    )
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
    query = text(
        "SELECT EXISTS(SELECT 1 FROM news_articles WHERE content_hash = :hash)"
    )
    result = await session.execute(query, {"hash": content_hash})
    return bool(result.scalar())


async def get_active_tickers_with_sources(
    session: AsyncSession, publisher: str
) -> List[Dict[str, Any]]:
    """Fetches active tickers and their specific pool_url for a given publisher."""
    query = text("""
        SELECT t.id, t.symbol, cs.pool_url
        FROM tickers t
        JOIN crawler_sources cs ON t.id = cs.ticker_id
        WHERE t.is_active = TRUE AND cs.publisher = :publisher
    """)
    res = await session.execute(query, {"publisher": publisher})
    return [
        {"id": row.id, "symbol": row.symbol, "pool_url": row.pool_url}
        for row in res.fetchall()
    ]


async def save_articles(
    session: AsyncSession, ticker_id: int, article: Dict[str, Any]
) -> Optional[UUID]:
    """
    Inserts parsed articles into news_articles using ON CONFLICT DO NOTHING.
    Logs any article that was parsed but skipped as a duplicate.
    """
    query = text("""
        INSERT INTO news_articles (ticker_id, source_url, publisher, headline, raw_content, pdf_url, content_hash, published_at)
        VALUES (:ticker_id, :source_url, :publisher, :headline, :raw_content, :pdf_url, :content_hash, :published_at)
        ON CONFLICT (content_hash) DO NOTHING
        RETURNING id;
    """)

    result = await session.execute(
        query,
        {
            "ticker_id": ticker_id,
            "source_url": article["source_url"],
            "publisher": article["publisher"],
            "headline": article["headline"],
            "raw_content": article["raw_content"],
            "pdf_url": article["pdf_url"],
            "content_hash": article["content_hash"],
            "published_at": article.get("published_at"),
        },
    )
    
    # 2. Safely check if the database returned any rows before fetching
    if result.returns_rows: # type: ignore
        row = result.fetchone()
        if row:
            inserted_id = row[0]
            # print(f"Inserted ID: {inserted_id}")
            return inserted_id
            
    # 3. If no rows were returned, it means ON CONFLICT DO NOTHING caught a duplicate
    print(f"  ⏭️ Parsed but skipped (Already in DB): {article['source_url']}")
    return None


async def save_article_attachment(
    session: AsyncSession, article_id: UUID, pdf_data: Dict[str, Any]
) -> Optional[UUID]:
    """
    Inserts a single PDF attachment linked to an article_id.
    Returns the number of inserted rows.
    """
    query = text("""
        INSERT INTO article_attachments (article_id, file_url, file_name, raw_content, content_hash)
        VALUES (:article_id, :file_url, :file_name, :raw_content, :content_hash)
        ON CONFLICT (content_hash) DO NOTHING;
    """)

    result = await session.execute(
        query,
        {
            "article_id": article_id,
            "file_url": pdf_data["file_url"],
            "file_name": pdf_data["file_name"],
            "raw_content": pdf_data["raw_content"],
            "content_hash": pdf_data["content_hash"],
        },
    )

    if result.rowcount > 0: # type: ignore
        await session.commit()
        return article_id
    else:
        print(f"  ⏭️ Parsed but skipped (Already in DB): {pdf_data['file_url']}")
        return None
