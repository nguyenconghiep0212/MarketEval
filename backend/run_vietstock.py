import asyncio
from datetime import datetime 
import os
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from backend.src.source_crawlers.vietstock_parser import fetch_vietstock_urls, parse_vietstock_article
from backend.database.queries.article import get_active_tickers_with_sources, save_articles

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/marketeval")
REQUEST_DELAY_SECONDS = 0.1


async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) # type: ignore

    async with async_session() as session: # type: ignore
        # Fetch tickers with their specific Vietstock URL from DB
        tickers = await get_active_tickers_with_sources(session, publisher="Vietstock")
        if not tickers:
            print("⚠️ No active tickers with Vietstock sources found. Seed the DB first!")
            return

        print("=" * 60)
        print("🚀 STARTING VIETSTOCK INGESTION PIPELINE")
        print("=" * 60)

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for item in tickers:
                ticker_id = item["id"]
                symbol = item["symbol"]
                pool_url = item["pool_url"]
                
                print(f"\n🔍 Processing Vietstock for {symbol}...")

                # 1. Discover URLs using DB source
                obj = await fetch_vietstock_urls(pool_url)
                print(f"  ├─ Discovered {len(obj)} URLs")

                # 2. Extract article contents and save to DB
                insert_article_count = 0
                insert_pdf_count = 0
                duplicate_skip_count = 0
                for item in obj:
                    url = item.url
                    published_date = item.published_date or datetime.now()
                    art = await parse_vietstock_article(client, published_date, url)
                    if art:
                        art_id = await save_articles(session, ticker_id, art)
                        if art_id:
                            insert_article_count += 1
                            now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            print(f"[{now_str}]   ├─ Successfully processed Vietstock Article {url} for {symbol}")
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
    print("✅ VIETSOCK INGESTION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())