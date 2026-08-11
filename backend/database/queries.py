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
            await session.commit()
            # print(f"Inserted ID: {inserted_id}")
            return inserted_id
            
    # 3. If no rows were returned, it means ON CONFLICT DO NOTHING caught a duplicate
    print(f"  ⏭️ Parsed but skipped (Already in DB): {article['source_url']}")
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
            await session.commit()
            # print(f"Inserted ID: {inserted_id}")
            return inserted_id
            
    # 3. If no rows were returned, it means ON CONFLICT DO NOTHING caught a duplicate
    print(f"  ⏭️ Parsed but skipped (Already in DB): {financial_report['source_url']}")
    return None


async def save_article_attachment(
    session: AsyncSession,
    pdf_data: Dict[str, Any],
    news_article_id: Optional[UUID] = None,
    financial_analysis_id: Optional[UUID] = None,
) -> Optional[UUID]:
    """
    Inserts a single PDF attachment linked to EITHER news_article_id OR financial_analysis_id.
    Returns the newly created attachment UUID, or None if skipped (already exists in DB).
    """
    # 1. Enforce mutually exclusive parent IDs (XOR check)
    if (news_article_id is None) == (financial_analysis_id is None):
        raise ValueError("Must supply exactly ONE parent ID: either news_article_id OR financial_analysis_id.")

    # 2. SQL Query with RETURNING id
    query = text("""
        INSERT INTO article_attachments (
            news_article_id, 
            financial_analysis_id, 
            file_url, 
            file_name, 
            raw_content, 
            content_hash
        )
        VALUES (
            :news_article_id, 
            :financial_analysis_id, 
            :file_url, 
            :file_name, 
            :raw_content, 
            :content_hash
        )
        ON CONFLICT (content_hash) DO NOTHING
        RETURNING id;
    """)

    result = await session.execute(
        query,
        {
            "news_article_id": news_article_id,
            "financial_analysis_id": financial_analysis_id,
            "file_url": pdf_data["file_url"],
            "file_name": pdf_data.get("file_name"),
            "raw_content": pdf_data["raw_content"],
            "content_hash": pdf_data["content_hash"],
        },
    )

    # 3. Fetch the inserted attachment UUID
    inserted_id: Optional[UUID] = result.scalar_one_or_none()

    if inserted_id:
        await session.commit()
        return inserted_id
    else:
        print(f"  ⏭️ Parsed but skipped (Already in DB): {pdf_data['file_url']}")
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

async def get_unprocessed_pdf_articles(
    session: AsyncSession, ticker_symbol: List[str]
) -> List[Dict[str, Any]]:
    """Fetches unprocessed PDFs from both news and financial analysis articles for the given ticker symbols."""
    
    # Note: No parentheses around :symbols when using expanding=True
    query = text("""
                SELECT 
                        'news' AS parent_type,
                        na.id AS parent_id,
                        na.ticker_id,
                        na.pdf_url,
                        na.is_pdf_download_url,
                        na.headline
                FROM news_articles na
                JOIN tickers t ON na.ticker_id = t.id
                LEFT JOIN article_attachments aa ON aa.news_article_id = na.id
                WHERE t.symbol IN :symbols
                    AND na.pdf_url IS NOT NULL
                    AND aa.id IS NULL

                UNION ALL

                SELECT
                        'financial' AS parent_type,
                        fa.id AS parent_id,
                        fa.ticker_id,
                        fa.pdf_url,
                        fa.is_pdf_download_url,
                        fa.headline
                FROM financial_analysis_articles fa
                JOIN tickers t ON fa.ticker_id = t.id
                LEFT JOIN article_attachments aa ON aa.financial_analysis_id = fa.id
                WHERE t.symbol IN :symbols
                    AND fa.pdf_url IS NOT NULL
                    AND aa.id IS NULL
    """).bindparams(bindparam("symbols", expanding=True))
    
    # Pass a LIST [str] instead of a tuple
    symbols_list = [ts.upper() for ts in ticker_symbol]
    result = await session.execute(query, {"symbols": symbols_list})
    
    rows = result.mappings().all()
    return [dict(row) for row in rows]