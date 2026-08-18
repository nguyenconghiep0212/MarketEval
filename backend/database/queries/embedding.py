from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def insert_article_embedding(
    session: AsyncSession,
    chunk_index: int,
    chunk_text: str,
    embedding: List[float],
    news_article_id: Optional[UUID] = None,
    financial_analysis_id: Optional[UUID] = None,
    attachment_id: Optional[UUID] = None,
) -> UUID:
    """Inserts a single text chunk embedding into article_embeddings."""
    sql = text("""
        INSERT INTO article_embeddings (
            news_article_id, 
            financial_analysis_id, 
            attachment_id, 
            chunk_index, 
            chunk_text, 
            embedding
        )
        VALUES (
            :news_article_id, 
            :financial_analysis_id, 
            :attachment_id, 
            :chunk_index, 
            :chunk_text, 
            :embedding
        )
        RETURNING id;
    """)

    result = await session.execute(
        sql,
        {
            "news_article_id": news_article_id,
            "financial_analysis_id": financial_analysis_id,
            "attachment_id": attachment_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "embedding": str(embedding),
        },
    )
    return result.scalar_one()


async def search_similar_embeddings(
    session: AsyncSession, 
    query_vector: List[float], 
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Performs Cosine Distance vector search across news, financial analysis, and attachments."""
    sql = text("""
        SELECT 
            ae.id AS embedding_id,
            ae.chunk_text,
            1 - (ae.embedding <=> :query_vector) AS cosine_similarity,
            COALESCE(na.headline, fa.headline, att.file_name, 'Unknown Source') AS title,
            CASE 
                WHEN ae.news_article_id IS NOT NULL THEN 'news_article'
                WHEN ae.financial_analysis_id IS NOT NULL THEN 'financial_analysis'
                WHEN ae.attachment_id IS NOT NULL THEN 'attachment'
            END AS source_type
        FROM article_embeddings ae
        LEFT JOIN news_articles na ON ae.news_article_id = na.id
        LEFT JOIN financial_analysis_articles fa ON ae.financial_analysis_id = fa.id
        LEFT JOIN article_attachments att ON ae.attachment_id = att.id
        ORDER BY ae.embedding <=> :query_vector ASC
        LIMIT :top_k;
    """)

    result = await session.execute(
        sql, 
        {"query_vector": str(query_vector), "top_k": top_k}
    )
    return [dict(row) for row in result.mappings().all()]


async def insert_article_embeddings_batch(
    session: AsyncSession,
    chunks_data: List[Dict[str, Any]]
) -> None:
    """Bulk inserts multiple text chunks and embeddings at once."""
    if not chunks_data:
        return

    sql = text("""
        INSERT INTO article_embeddings (
            news_article_id, financial_analysis_id, attachment_id, 
            chunk_index, chunk_text, embedding
        )
        VALUES (
            :news_article_id, :financial_analysis_id, :attachment_id, 
            :chunk_index, :chunk_text, :embedding
        )
    """)
    
    # Executemany equivalent for async SQLAlchemy
    await session.execute(sql, chunks_data)
    
async def _upsert_risk_assessment(session: AsyncSession, parent_column: str, record_id: Any, score: float) -> None:
    """
    Inserts or updates the sentiment score in the risk_assessments table.
    `parent_column` must be either 'news_article_id' or 'financial_analysis_id'.
    """
    query = text(f"""
        INSERT INTO risk_assessments ({parent_column}, sentiment_score)
        VALUES (:id, :score)
        ON CONFLICT ({parent_column}) 
        DO UPDATE SET 
            sentiment_score = EXCLUDED.sentiment_score, 
            evaluated_at = CURRENT_TIMESTAMP;
    """)
    await session.execute(query, {"id": record_id, "score": score})