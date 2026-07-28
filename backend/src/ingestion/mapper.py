import re
from typing import Optional, List
from sqlalchemy import text
from database.connection import AsyncSessionLocal
from database.queries import get_active_tickers


class TickerMapper:
    """Scans article text to detect and map ticker references."""

    @staticmethod
    def detect_ticker(headline: str, content: str, active_symbols: List[str]) -> Optional[str]:
        """Looks for exact uppercase ticker symbols in headline or body content."""
        text_to_search = f"{headline} {content}"
        
        for symbol in active_symbols:
            # Word boundary regex search to avoid partial word matching
            pattern = rf"\b{re.escape(symbol)}\b"
            if re.search(pattern, text_to_search):
                return symbol
        return None

    @classmethod
    async def map_unmapped_articles(cls) -> int:
        """Finds articles with NULL ticker_id and attempts auto-mapping."""
        async with AsyncSessionLocal() as session:
            tickers = await get_active_tickers(session)
            if not tickers:
                print("No active tickers found in database to map against.")
                return 0

            symbol_map = {t["symbol"]: t["id"] for t in tickers}
            active_symbols = list(symbol_map.keys())

            query = text("SELECT id, headline, cleaned_content FROM news_articles WHERE ticker_id IS NULL")
            result = await session.execute(query)
            unmapped = result.fetchall()

            mapped_count = 0
            for row in unmapped:
                article_id, headline, content = row[0], row[1], row[2] or ""
                detected_symbol = cls.detect_ticker(headline, content, active_symbols)

                if detected_symbol:
                    ticker_id = symbol_map[detected_symbol]
                    update_stmt = text(
                        "UPDATE news_articles SET ticker_id = :ticker_id WHERE id = :article_id"
                    )
                    await session.execute(update_stmt, {"ticker_id": ticker_id, "article_id": article_id})
                    mapped_count += 1
                    print(f"Mapped article '{headline[:35]}...' -> Ticker [{detected_symbol}]")

            await session.commit()
            print(f"Auto-mapping finished. Tagged {mapped_count} articles.")
            return mapped_count


if __name__ == "__main__":
    import asyncio
    asyncio.run(TickerMapper.map_unmapped_articles())