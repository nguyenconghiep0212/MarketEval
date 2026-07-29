import asyncio
import os
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from src.source_crawlers.cafef_parser import fetch_cafef_urls, parse_cafef_article
from database.queries import get_active_tickers_with_sources, save_articles, save_article_attachment
from src.source_crawlers.utils import download_and_extract_pdf, generate_content_hash

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/marketeval")


async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) # type: ignore

    async with async_session() as session: # type: ignore
        # Fetch tickers with their specific CafeF URL from DB
        tickers = await get_active_tickers_with_sources(session, publisher="CafeF")
        if not tickers:
            print("⚠️ No active tickers with CafeF sources found. Seed the DB first!")
            return

        print("=" * 60)
        print("🚀 STARTING CAFEF INGESTION PIPELINE")
        print("=" * 60)

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for item in tickers:
                ticker_id = item["id"]
                symbol = item["symbol"]
                pool_url = item["pool_url"]
                
                print(f"\n🔍 Processing CafeF for {symbol}...")

                # 1. Discover URLs using DB source
                urls = fetch_cafef_urls(pool_url)
                print(f"  ├─ Discovered {len(urls)} URLs")

                # 2. Extract article contents and save to DB
                insert_article_count = 0
                insert_pdf_count = 0
                for url in urls:
                    art = await parse_cafef_article(client, url)
                    if art:
                        art_id = await save_articles(session, ticker_id, art)
                        if art_id:
                            insert_article_count += 1
                            print(f"  ├─ Successfully processed CafeF Articles {url} for {symbol}")
                        if art_id and art.get("pdf_url"):
                            pdf_content = await download_and_extract_pdf(client, art_id, art["pdf_url"])
                            if pdf_content:
                                pdf_id = await save_article_attachment(session, art_id, pdf_content)
                                if pdf_id:
                                    insert_pdf_count += 1
                                    print(f"  ├─ Successfully processed CafeF PDF {pdf_content['file_url']} for {symbol}")
                    await asyncio.sleep(0.3)

                print(f"  ├─ Articles inserted: {insert_article_count}")
                print(f"  └─ PDFs inserted: {insert_pdf_count}")

    await engine.dispose()
    print("\n" + "=" * 60)
    print("✅ CAFEF INGESTION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())