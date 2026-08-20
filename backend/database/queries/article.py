from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import UUID, text, bindparam


async def upsert_ticker(
    session: AsyncSession, symbol: str, company_name: str, sector: Optional[str] = None
) -> None:
    """Inserts or updates a ticker record in the backend.database."""
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
        INSERT INTO news_articles (ticker_id, source_url, publisher, headline, raw_content, pdf_url, is_pdf_download_url, content_hash, published_at)
        VALUES (:ticker_id, :source_url, :publisher, :headline, :raw_content, :pdf_url, :is_pdf_download_url, :content_hash, :published_at)
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
            "is_pdf_download_url": article.get("is_pdf_download_url", False),
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
            
    # 3. If no rows were returned, ON CONFLICT DO NOTHING caught a duplicate
    return None

async def save_financial_report(
    session: AsyncSession, ticker_id: int, financial_report: Dict[str, Any]
) -> Optional[UUID]:
    """
    Inserts parsed financial reports into financial_analysis_articles using ON CONFLICT DO NOTHING.
    Logs any financial report that was parsed but skipped as a duplicate.
    """
    query = text("""
        INSERT INTO financial_analysis_articles (ticker_id, source_url, publisher, headline, raw_content, pdf_url, is_pdf_download_url, content_hash, published_at)
        VALUES (:ticker_id, :source_url, :publisher, :headline, :raw_content, :pdf_url, :is_pdf_download_url, :content_hash, :published_at)
        ON CONFLICT (content_hash) DO NOTHING
        RETURNING id;
    """)

    result = await session.execute(
        query,
        {
            "ticker_id": ticker_id,
            "source_url": financial_report["source_url"],
            "publisher": financial_report["publisher"],
            "headline": financial_report["headline"],
            "raw_content": financial_report["raw_content"],
            "pdf_url": financial_report["pdf_url"],
            "is_pdf_download_url": financial_report.get("is_pdf_download_url", False),
            "content_hash": financial_report["content_hash"],
            "published_at": financial_report.get("published_at"),
        },
    )
    
    # 2. Safely check if the database returned any rows before fetching
    if result.returns_rows: # type: ignore
        row = result.fetchone()
        if row:
            inserted_id = row[0]
            # print(f"Inserted ID: {inserted_id}")
            return inserted_id
            
    # 3. If no rows were returned, ON CONFLICT DO NOTHING caught a duplicate
    return None


async def is_article_hash_exists(session: AsyncSession, content_hash: str) -> bool:
    """Checks if an article with the exact normalized content hash already exists."""
    query = text("SELECT 1 FROM news_articles WHERE content_hash = :content_hash LIMIT 1;")
    result = await session.execute(query, {"content_hash": content_hash})
    return result.scalar() is not None

async def is_financial_report_hash_exists(session: AsyncSession, content_hash: str) -> bool:
    """Checks if an article with the exact normalized content hash already exists."""
    query = text("SELECT 1 FROM financial_analysis_articles WHERE content_hash = :content_hash LIMIT 1;")
    result = await session.execute(query, {"content_hash": content_hash})
    return result.scalar() is not None

async def get_unindexed_news_articles(
    session: AsyncSession, limit: int = 10
) -> List[Dict[str, Any]]:
    """Fetches news articles that don't have embeddings generated yet."""
    query = text("""
        SELECT na.id, na.headline, na.raw_content
        FROM news_articles na
        LEFT JOIN article_embeddings ae ON ae.news_article_id = na.id
        WHERE ae.id IS NULL AND na.raw_content IS NOT NULL AND na.raw_content != ''
        LIMIT :limit;
    """)
    result = await session.execute(query, {"limit": limit})
    return [dict(row) for row in result.mappings().all()]


async def get_unindexed_financial_articles(
    session: AsyncSession, limit: int = 10
) -> List[Dict[str, Any]]:
    """Fetches financial analysis articles that don't have embeddings generated yet."""
    query = text("""
        SELECT fa.id, fa.headline, fa.raw_content
        FROM financial_analysis_articles fa
        LEFT JOIN article_embeddings ae ON ae.financial_analysis_id = fa.id
        WHERE ae.id IS NULL AND fa.raw_content IS NOT NULL AND fa.raw_content != ''
        LIMIT :limit;
    """)
    result = await session.execute(query, {"limit": limit})
    return [dict(row) for row in result.mappings().all()]


async def get_articles_by_tickers(
    session: AsyncSession, symbols: List[str], limit_per_ticker: int = 10
) -> List[Dict[str, Any]]:
    """
    Fetches news articles AND financial reports for the given ticker symbols,
    combined into a single feed per ticker, ranked by published_at (most recent
    first), and capped at `limit_per_ticker` items PER ticker (not globally).

    Uses ROW_NUMBER() OVER (PARTITION BY ticker_symbol ...) so each ticker in
    `symbols` gets its own independent top-N window, regardless of how many
    tickers are requested or how unevenly articles are distributed among them.
    """
    if not symbols:
        return []

    query = text("""
        WITH combined AS (
            SELECT
                'news' AS source_type,
                na.id,
                na.ticker_id,
                t.symbol AS ticker_symbol,
                na.source_url,
                na.publisher,
                na.published_at,
                na.headline,
                na.raw_content,
                na.pdf_url,
                na.created_at
            FROM news_articles na
            JOIN tickers t ON na.ticker_id = t.id
            WHERE t.symbol IN :symbols

            UNION ALL

            SELECT
                'financial_report' AS source_type,
                fa.id,
                fa.ticker_id,
                t.symbol AS ticker_symbol,
                fa.source_url,
                fa.publisher,
                fa.published_at,
                fa.headline,
                fa.raw_content,
                fa.pdf_url,
                fa.created_at
            FROM financial_analysis_articles fa
            JOIN tickers t ON fa.ticker_id = t.id
            WHERE t.symbol IN :symbols
        ),
        ranked AS (
            SELECT
                combined.*,
                ROW_NUMBER() OVER (
                    PARTITION BY ticker_symbol
                    ORDER BY published_at DESC NULLS LAST, created_at DESC
                ) AS rn
            FROM combined
        )
        SELECT
            source_type, id, ticker_id, ticker_symbol, source_url, publisher,
            published_at, headline, raw_content, pdf_url, created_at
        FROM ranked
        WHERE rn <= :limit_per_ticker
        ORDER BY ticker_symbol ASC, published_at DESC NULLS LAST;
    """).bindparams(bindparam("symbols", expanding=True))

    symbols_upper = [s.upper() for s in symbols]
    result = await session.execute(
        query,
        {"symbols": symbols_upper, "limit_per_ticker": limit_per_ticker},
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]