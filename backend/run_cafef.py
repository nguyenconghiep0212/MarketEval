import asyncio
from datetime import datetime 
import os
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from backend.src.source_crawlers.cafef_parser import fetch_cafef_urls, parse_cafef_article
from backend.database.queries import get_active_tickers_with_sources, save_articles

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/marketeval")
REQUEST_DELAY_SECONDS = 0.1


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
                urls = await fetch_cafef_urls(client, pool_url)
                print(f"  ├─ Discovered {len(urls)} URLs")

                # 2. Extract article contents and save to DB
                insert_article_count = 0
                insert_pdf_count = 0
                duplicate_skip_count = 0
                for url in urls:
                    art = await parse_cafef_article(client, url)
                    if art:
                        art_id = await save_articles(session, ticker_id, art)
                        if art_id:
                            insert_article_count += 1
                            now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            print(f"[{now_str}]   ├─ Successfully processed CafeF Article {url} for {symbol}")
                            if art.get("pdf_url"): 
                                insert_pdf_count += 1
                        else:
                            duplicate_skip_count += 1
                            print(f"  ⏭️ Duplicate content detected for {url}. Skipped.")
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)

                await session.commit()

                print(f"  ├─ Articles inserted: {insert_article_count}")
                print(f"  ├─ Duplicates skipped: {duplicate_skip_count}")
                print(f"  └─ PDFs detected: {insert_pdf_count}")

    await engine.dispose()
    print("\n" + "=" * 60)
    print("✅ CAFEF INGESTION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())