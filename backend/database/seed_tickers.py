import asyncio
from backend.database.connection import AsyncSessionLocal
from backend.database.queries import upsert_ticker

INITIAL_TICKERS = [
    {"symbol": "PNJ", "company_name": "Phu Nhuan Jewelry JSC", "sector": "Consumer Goods / Retail"},
    # {"symbol": "VNM", "company_name": "Vinamilk", "sector": "Consumer Goods / Dairy"},
    # {"symbol": "BID", "company_name": "BIDV Bank", "sector": "Banking"},
    # {"symbol": "POW", "company_name": "PetroVietnam Power", "sector": "Utilities / Energy"},
    # {"symbol": "HPG", "company_name": "Hoa Phat Group", "sector": "Materials / Steel"},
    # {"symbol": "VIC", "company_name": "Vingroup JSC", "sector": "Real Estate"},
    # {"symbol": "SSI", "company_name": "SSI Securities", "sector": "Financial Services"},
    # {"symbol": "FPT", "company_name": "FPT Corporation", "sector": "Technology"},
]


async def seed_tickers():
    print("Seeding initial ticker watchlist...")
    async with AsyncSessionLocal() as session:
        for ticker in INITIAL_TICKERS:
            await upsert_ticker(
                session=session,
                symbol=ticker["symbol"],
                company_name=ticker["company_name"],
                sector=ticker["sector"],
            )
        await session.commit()
    print("Ticker seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_tickers())