import asyncio
import os
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from src.source_crawlers.cafef_parser import fetch_cafef_urls, parse_cafef_article
from database.queries import get_active_tickers_with_sources, save_articles

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/marketeval")


async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
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

                # 2. Extract article contents
                parsed_articles = []
                for url in urls:
                    art = await parse_cafef_article(client, url)
                    if art:
                        parsed_articles.append(art)
                    await asyncio.sleep(0.3)

                print(f"  ├─ Successfully parsed {len(parsed_articles)} bodies")

                # 3. Save to database
                if parsed_articles:
                    inserted = await save_articles(session, ticker_id, parsed_articles)
                    print(f"  └─ 💾 Saved {inserted} NEW unique articles into PostgreSQL")
                else:
                    print(f"  └─ 💾 0 articles to save")

    await engine.dispose()
    print("\n" + "=" * 60)
    print("✅ CAFEF INGESTION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())