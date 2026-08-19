import asyncio
import os
from typing import List, Dict, Any, Optional, Callable
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

from backend.src.nlp.text_chunker import chunk_text
from backend.src.nlp.embeddings import EmbeddingEngine
from backend.src.nlp.sentiment import SentimentEngine
from backend.database.queries import insert_article_embeddings_batch, get_unindexed_financial_articles, get_unindexed_attachments, get_unindexed_news_articles, _upsert_risk_assessment

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/marketeval")


async def process_article_batch(
    session: AsyncSession,
    articles: List[Dict[str, Any]],
    article_type: str,
    embedding_engine: EmbeddingEngine,
    sentiment_engine: SentimentEngine,
    include_sentiment: bool = True,
    chunk_params: Optional[Dict[str, int]] = None,
) -> int:
    """
    Generic handler for processing articles of any type (news, financial, pdf).
    
    Args:
        session: Database session
        articles: List of article dicts with 'id' and 'raw_content'
        article_type: Type identifier ('news_article', 'financial_analysis', 'attachment')
        embedding_engine: Loaded embedding model
        sentiment_engine: Loaded sentiment model
        include_sentiment: Whether to analyze sentiment (skip for PDFs)
        chunk_params: Dict with 'max_words' and 'overlap_words' for chunking
    
    Returns:
        Number of articles processed
    """
    if not articles:
        return 0
    
    if chunk_params is None:
        chunk_params = {"max_words": 250, "overlap_words": 50}
    
    processed_count = 0
    
    for art in articles:
        article_id = art["id"]
        content = art.get("raw_content", "")
        
        if not content or not content.strip():
            continue
        
        # 1. SENTIMENT ANALYSIS (if applicable)
        if include_sentiment:
            score = sentiment_engine.analyze_text(content)  # ✅ Use full text, not truncated
            await _upsert_risk_assessment(session, f"{article_type}_id", article_id, score)
        
        # 2. CHUNK TEXT & GENERATE EMBEDDINGS
        chunks = chunk_text(content, **chunk_params)
        if not chunks:
            continue
        
        vectors = embedding_engine.generate_embeddings(chunks)
        
        # 3. PREPARE BATCH INSERT DATA (✅ Much faster than 1-by-1 inserts)
        embedding_data = []
        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            row = {
                "chunk_index": idx,
                "chunk_text": chunk,
                "embedding": str(vec),  # pgvector format
                article_type: article_id,  # news_article_id, financial_analysis_id, or attachment_id
                "news_article_id": article_id if article_type == "news_article" else None,
                "financial_analysis_id": article_id if article_type == "financial_analysis" else None,
                "attachment_id": article_id if article_type == "attachment" else None,
            }
            # Remove the dynamic key, keep only the three static ones
            embedding_data.append({
                "chunk_index": idx,
                "chunk_text": chunk,
                "embedding": str(vec),
                "news_article_id": article_id if article_type == "news_article" else None,
                "financial_analysis_id": article_id if article_type == "financial_analysis" else None,
                "attachment_id": article_id if article_type == "attachment" else None,
            })
        
        # 4. BATCH INSERT (single query for all chunks of this article)
        await insert_article_embeddings_batch(session, embedding_data)
        processed_count += 1
    
    await session.commit()
    return processed_count


async def run_intelligence_pipeline():
    print("=" * 60)
    print("🧠 STARTING INTELLIGENCE & VECTORIZATION PIPELINE")
    print("=" * 60)

    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Load models into memory once (better than reloading for each batch)
    embedding_engine = EmbeddingEngine()
    sentiment_engine = SentimentEngine()

    async with async_session() as session:
        # ---------------------------------------------------------
        # 1. PROCESS STANDARD NEWS ARTICLES
        # ---------------------------------------------------------
        news = await get_unindexed_news_articles(session, limit=20)
        print(f"\n📰 Found {len(news)} unindexed News Articles.")
        
        news_processed = await process_article_batch(
            session,
            news,
            "news_article",
            embedding_engine,
            sentiment_engine,
            include_sentiment=True,
        )
        print(f"   ✅ Processed {news_processed} articles with embeddings & sentiment")

        # ---------------------------------------------------------
        # 2. PROCESS FINANCIAL ANALYSIS ARTICLES
        # ---------------------------------------------------------
        fin_articles = await get_unindexed_financial_articles(session, limit=20)
        print(f"\n📊 Found {len(fin_articles)} unindexed Financial Analysis Articles.")
        
        fin_processed = await process_article_batch(
            session,
            fin_articles,
            "financial_analysis",
            embedding_engine,
            sentiment_engine,
            include_sentiment=True,
        )
        print(f"   ✅ Processed {fin_processed} articles with embeddings & sentiment")

        # ---------------------------------------------------------
        # 3. PROCESS PDF ATTACHMENTS (No Sentiment, Just Vectors)
        # ---------------------------------------------------------
        attachments = await get_unindexed_attachments(session, limit=20)
        print(f"\n📎 Found {len(attachments)} unindexed PDF Attachments.")
        
        att_processed = await process_article_batch(
            session,
            attachments,
            "attachment",
            embedding_engine,
            sentiment_engine,
            include_sentiment=False,
            chunk_params={"max_words": 300, "overlap_words": 50},  # PDFs need aggressive chunking
        )
        print(f"   ✅ Processed {att_processed} PDFs with embeddings")

    await engine.dispose()
    print("\n✅ INTELLIGENCE PIPELINE COMPLETED")
    print(f"   Total: {news_processed + fin_processed + att_processed} articles processed")


if __name__ == "__main__":
    asyncio.run(run_intelligence_pipeline())