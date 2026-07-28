import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/marketeval")

from seed_tickers import INITIAL_TICKERS

async def seed_database():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            print("🌱 Seeding Tickers and Crawler Sources...")
            
            for item in INITIAL_TICKERS:
                symbol = item["symbol"]
                company = item["company_name"]
                sector = item["sector"]

                # 1. Upsert Ticker
                query_ticker = text("""
                    INSERT INTO tickers (symbol, company_name, sector)
                    VALUES (:symbol, :company_name, :sector)
                    ON CONFLICT (symbol) DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        sector = EXCLUDED.sector
                    RETURNING id;
                """)
                res = await session.execute(query_ticker, {"symbol": symbol, "company_name": company, "sector": sector})
                ticker_id = res.scalar_one()

                # 2. Seed Crawler Sources for each ticker
                sources = [
                    ("CafeF", f"https://cafef.vn/du-lieu/tin-doanh-nghiep/{symbol.lower()}/event.chn"),
                    ("Vietstock", f"https://finance.vietstock.vn/{symbol.upper()}/tin-tuc-su-kien.htm"),
                    ("StockBiz", f"https://web.stockbiz.vn/Stocks/{symbol.upper()}/CompanyNews.aspx")
                ]

                for publisher, pool_url in sources:
                    query_source = text("""
                        INSERT INTO crawler_sources (ticker_id, publisher, pool_url)
                        VALUES (:ticker_id, :publisher, :pool_url)
                        ON CONFLICT DO NOTHING;
                    """)
                    await session.execute(query_source, {
                        "ticker_id": ticker_id,
                        "publisher": publisher,
                        "pool_url": pool_url
                    })

            print("✅ Seeding completed successfully!")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_database())