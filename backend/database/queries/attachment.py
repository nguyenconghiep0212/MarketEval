from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import UUID, text, bindparam

async def get_unindexed_attachments(
    session: AsyncSession, limit: int = 10
) -> List[Dict[str, Any]]:
    """Fetches attachments that don't have embeddings generated yet."""
    query = text("""
        SELECT aa.id, aa.file_name, aa.raw_content
        FROM article_attachments aa
        LEFT JOIN article_embeddings ae ON ae.attachment_id = aa.id
        WHERE ae.id IS NULL AND aa.raw_content IS NOT NULL AND aa.raw_content != ''
        LIMIT :limit;
    """)
    result = await session.execute(query, {"limit": limit})
    return [dict(row) for row in result.mappings().all()]


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