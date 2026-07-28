import time
from typing import Dict, List

# --- Import Seed Tickers ---
from database.seed_tickers import INITIAL_TICKERS

# --- Import Modular Crawler Functions ---
from src.source_crawlers.cafef import fetch_cafef_article_urls
from src.source_crawlers.vietstock import fetch_vietstock_urls_authenticated
from src.source_crawlers.stockbiz import fetch_stockbiz_article_urls


def run_url_discovery_pipeline() -> Dict[str, Dict[str, List[str]]]:
    print("=" * 65)
    print("🚀 STARTING TICKER URL POOL DISCOVERY PIPELINE")
    print("=" * 65)
    
    pipeline_summary = {}

    for idx, item in enumerate(INITIAL_TICKERS, start=1):
        symbol = item["symbol"]
        company = item["company_name"]
        print(f"\n[{idx}/{len(INITIAL_TICKERS)}] Processing Ticker: {symbol} ({company})")

        # 1. CafeF Discovery
        cafef_urls = fetch_cafef_article_urls(symbol)
        print(f"  ├─ CafeF:     {len(cafef_urls)} URLs found")
        time.sleep(0.5)

        # 2. Vietstock Discovery (Auth / Handshake Flow)
        vietstock_urls = fetch_vietstock_urls_authenticated(symbol)
        print(f"  ├─ Vietstock: {len(vietstock_urls)} URLs found")
        time.sleep(0.5)

        # 3. StockBiz Discovery
        stockbiz_urls = fetch_stockbiz_article_urls(symbol)
        print(f"  └─ StockBiz:  {len(stockbiz_urls)} URLs found")
        time.sleep(0.5)

        # Master Deduplicated Pool for this ticker
        unique_ticker_urls = set(cafef_urls + vietstock_urls + stockbiz_urls)

        pipeline_summary[symbol] = {
            "cafef": cafef_urls,
            "vietstock": vietstock_urls,
            "stockbiz": stockbiz_urls,
            "all_unique": list(unique_ticker_urls)
        }

        print(f"  🎯 TOTAL UNIQUE URLs FOR {symbol}: {len(unique_ticker_urls)}")

    print("\n" + "=" * 65)
    print("✅ URL POOL DISCOVERY COMPLETED")
    print("=" * 65)

    return pipeline_summary


if __name__ == "__main__":
    results = run_url_discovery_pipeline()