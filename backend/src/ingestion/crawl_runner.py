import asyncio
from datetime import datetime
import traceback
from typing import AsyncGenerator, Dict, List, Any, Optional

import httpx
from sqlalchemy import text

from backend.database.connection import AsyncSessionLocal
from backend.database.queries.article import save_articles, save_financial_report
from backend.src.source_crawlers.cafef_parser import fetch_cafef_urls, parse_cafef_article
from backend.src.source_crawlers.vietstock_parser import fetch_vietstock_urls, parse_vietstock_article
from backend.src.source_crawlers.stockbiz_parser import fetch_stockbiz_urls, parse_stockbiz_article
from backend.src.source_crawlers.stockbiz_financial_report_parser import (
    fetch_stockbiz_financial_report_urls,
    parse_stockbiz_financial_report_article,
)

import asyncio
import sys
from typing import Optional

REQUEST_DELAY_SECONDS = 0.1


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def _get_ticker_sources(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetches the active ticker's id plus all of its seeded crawler_sources
    (publisher -> pool_url), keyed by publisher."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT t.id AS ticker_id, cs.publisher, cs.pool_url
                FROM tickers t
                JOIN crawler_sources cs ON cs.ticker_id = t.id
                WHERE t.symbol = :symbol AND t.is_active = TRUE
            """),
            {"symbol": symbol.upper()},
        )
        rows = result.mappings().all()
        if not rows:
            return None
        return {
            "ticker_id": rows[0]["ticker_id"],
            "sources": {row["publisher"]: row["pool_url"] for row in rows},
        }


async def _run_http_source(
    symbol: str,
    ticker_id: int,
    publisher_label: str,
    pool_url: str,
    fetch_urls_fn,
    parse_article_fn,
    save_fn,
    queue: "asyncio.Queue[Optional[str]]",
) -> None:
    """
    Generic runner for the sources that share the (client, pool_url) -> urls
    and (client, url) -> article signature: CafeF, StockBiz news, and
    StockBiz financial reports. Vietstock uses Playwright with a different
    signature, so it has its own runner below.
    """
    await queue.put(f"[{symbol}] [{publisher_label}] Starting…")
    inserted = duplicates = errors = 0
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            urls = await fetch_urls_fn(client, pool_url)
            await queue.put(f"[{symbol}] [{publisher_label}] Discovered {len(urls)} URL(s)")

            async with AsyncSessionLocal() as session:
                for url in urls:
                    try:
                        art = await parse_article_fn(client, url)
                    except Exception as e:
                        errors += 1
                        await queue.put(f"[{symbol}] [{publisher_label}] ⚠️ Parse error at {url}: {e}")
                        continue

                    if art:
                        art_id = await save_fn(session, ticker_id, art)
                        if art_id:
                            inserted += 1
                            await queue.put(f"[{symbol}] [{publisher_label}] ✓ {art['headline'][:70]}")
                        else:
                            duplicates += 1
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)
                await session.commit()
    except Exception as e:
        await queue.put(f"[{symbol}] [{publisher_label}] ❌ Fatal error _run_http_source: {e}")
        return

    await queue.put(
        f"[{symbol}] [{publisher_label}] Done — {inserted} inserted, {duplicates} duplicate(s), {errors} error(s)"
    )


async def _run_vietstock_source(
    symbol: str, ticker_id: int, pool_url: str, queue: "asyncio.Queue[Optional[str]]"
) -> None:
    """Vietstock uses Playwright for URL discovery and a differently-shaped
    parse function, so it can't share _run_http_source."""
    await queue.put(f"[{symbol}] [Vietstock] Starting…")
    inserted = duplicates = errors = 0
    try:
        items = await fetch_vietstock_urls(pool_url)
        await queue.put(f"[{symbol}] [Vietstock] Discovered {len(items)} URL(s)")

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            async with AsyncSessionLocal() as session:
                for item in items:
                    published_date = item.published_date or datetime.now()
                    try:
                        art = await parse_vietstock_article(client, published_date, item.url)
                    except Exception as e:
                        errors += 1
                        await queue.put(f"[{symbol}] [Vietstock] ⚠️ Parse error at {item.url}: {e}")
                        continue

                    if art:
                        art_id = await save_articles(session, ticker_id, art)
                        if art_id:
                            inserted += 1
                            await queue.put(f"[{symbol}] [Vietstock] ✓ {art['headline'][:70]}")
                        else:
                            duplicates += 1
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)
                await session.commit()
    except Exception as e:
        
        error_details = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(f"[{symbol}] [Vietstock] Detailed Fatal error:\n{error_details}")
        
        await queue.put(f"[{symbol}] [Vietstock] ❌ Fatal error _run_vietstock_source: {e}")
        return

    await queue.put(
        f"[{symbol}] [Vietstock] Done — {inserted} inserted, {duplicates} duplicate(s), {errors} error(s)"
    )


async def _crawl_ticker(symbol: str, queue: "asyncio.Queue[Optional[str]]") -> None:
    """Crawls all seeded sources for a single ticker CONCURRENTLY (each
    source is its own task), so a slow source (e.g. Vietstock's Playwright
    page) doesn't block the others for this same ticker."""
    await queue.put(f"[{symbol}] ==== Starting crawl ====")
    try:
        info = await _get_ticker_sources(symbol)
    except Exception as e:
        await queue.put(f"[{symbol}] ❌ Failed to look up sources: {e}")
        return

    if not info:
        await queue.put(
            f"[{symbol}] ⚠️ No active ticker / crawler sources found — "
            f"seed sources on the Ticker Management page first. Skipping."
        )
        return

    ticker_id = info["ticker_id"]
    sources = info["sources"]

    tasks = []
    if "CafeF" in sources:
        tasks.append(_run_http_source(
            symbol, ticker_id, "CafeF", sources["CafeF"],
            fetch_cafef_urls, parse_cafef_article, save_articles, queue,
        ))
    if "StockBiz" in sources:
        tasks.append(_run_http_source(
            symbol, ticker_id, "StockBiz", sources["StockBiz"],
            fetch_stockbiz_urls, parse_stockbiz_article, save_articles, queue,
        ))
    if "StockBiz_Financial_Report" in sources:
        tasks.append(_run_http_source(
            symbol, ticker_id, "StockBiz Financial Report", sources["StockBiz_Financial_Report"],
            fetch_stockbiz_financial_report_urls, parse_stockbiz_financial_report_article,
            save_financial_report, queue,
        ))
    if "Vietstock" in sources:
        tasks.append(_run_vietstock_source(symbol, ticker_id, sources["Vietstock"], queue))

    if not tasks:
        await queue.put(f"[{symbol}] ⚠️ Ticker has no recognized crawler sources configured.")
    else:
        await asyncio.gather(*tasks, return_exceptions=True)

    await queue.put(f"[{symbol}] ==== Crawl finished ====")


async def run_crawl_for_tickers(symbols: List[str]) -> AsyncGenerator[str, None]:
    """
    Crawls every ticker in `symbols` CONCURRENTLY (one asyncio task per
    ticker), yielding log lines as an async generator as soon as they're
    produced by any ticker's task — lines from different tickers are
    naturally interleaved as work completes, not run one-ticker-at-a-time.
    """
    queue: "asyncio.Queue[Optional[str]]" = asyncio.Queue()
    unique_symbols = list(dict.fromkeys(s.upper() for s in symbols))  # dedupe, keep order

    async def _runner():
        try:
            tasks = [_crawl_ticker(sym, queue) for sym in unique_symbols]
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await queue.put(None)  # sentinel — always signals stream end, even on error

    runner_task = asyncio.create_task(_runner())

    yield f"🚀 Starting crawl for {len(unique_symbols)} ticker(s): {', '.join(unique_symbols)}"
    while True:
        line = await queue.get()
        if line is None:
            break
        yield line

    await runner_task
    yield "✅ All crawls finished."