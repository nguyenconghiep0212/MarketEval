import httpx
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Any
from backend.src.source_crawlers.utils import generate_content_hash, parse_datetime
from playwright.async_api import async_playwright
from datetime import datetime
from pydantic import BaseModel

class ArticleItem(BaseModel):
    url: str
    published_date: Optional[datetime] = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://finance.vietstock.vn",
}

async def fetch_vietstock_urls(pool_url: str, max_clicks: int = 2) -> List[ArticleItem]:
    async with async_playwright() as p:
        # Launch a real headless Chromium browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Load HTML structure without waiting for endless background scripts
        await page.goto(pool_url, wait_until="domcontentloaded", timeout=15000)
        
        # 2. Wait explicitly for news link elements to render in DOM
        await page.wait_for_selector("a.stock-news__title", timeout=10000)
        
        # 3. Simulate clicking 'Xem thêm' to load more articles
        load_more_btn = page.locator("#stock-news-content .stock-news__button-see-more")
        
        for click_num in range(max_clicks):
            if await load_more_btn.is_visible():
                print(f"  🖱️ Clicking 'Xem thêm' ({click_num + 1}/{max_clicks})...")
                
                # Store current number of articles to verify new ones loaded
                old_count = await page.locator("a.stock-news__title").count()
                
                await load_more_btn.click()
                
                # Wait up to 3 seconds for new items to get injected into the DOM
                await page.wait_for_timeout(3000)
                
                new_count = await page.locator("a.stock-news__title").count()
                print(f"     └─ Articles count: {old_count} -> {new_count}")
                
                # If count didn't change, we reached the end of the news list
                if new_count == old_count:
                    print("  ℹ️ No more news to load.")
                    break
            else:
                print("  ℹ️ 'Xem thêm' button not found or hidden.")
                break
        
        # 4. Extract links using the fully rendered DOM
        tags = await page.eval_on_selector_all(
            ".stock-news__table-body tr",
                """elements => elements.map(tr => {
                    const link = tr.querySelector("a.stock-news__title") || tr.querySelector(".stock-news__title a");
                    const date = tr.querySelector(".stock-news__colu-publish-date");
                    const time = tr.querySelector(".stock-news__colu-publish-hours");
                    return {
                        url: link ? link.href : null,
                        date_str: date ? date.innerText.trim() : null,
                        time_str: time ? time.innerText.trim() : null
                    };
            })"""
        )
        res = []
        for item in tags:
            url = item["url"]
            date_str = item["date_str"]
            time_str = item["time_str"]
            if date_str and time_str:
                published_date = parse_datetime(f"{date_str} {time_str}")
            else:
                published_date = parse_datetime(date_str) if date_str else None
            print(f"  🔗 Raw Vietstock link: {url} | Published Date: {published_date}")
            res.append(ArticleItem(url=url, published_date=published_date))
        await browser.close()
        return res

async def parse_vietstock_article(
    client: httpx.AsyncClient, published_date: datetime, url: str
) -> Optional[Dict[str, Any]]:
    """Extracts headline, raw body text, and content_hash for a Vietstock article."""
    try:
        res = await client.get(url, headers={"User-Agent": HEADERS["User-Agent"]})
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "lxml")

        # Vietstock specific selectors
        headline_el = (
            soup.select_one("h1.article-title") or
            soup.select_one("h1.title") or
            soup.select_one("h1")
        )
        content_div = (
            soup.select("div#vst_detail > p:not(.pAuthor, .pTitle, .pSource)")
        )
        date_el = (
            soup.select_one("span.article-date")
        )
        pdf_url = (
            soup.select_one("div#vst_detail > table a[href]")
        )

        if not headline_el or not content_div:
            return None

        for content in content_div:
            for el in content.select(
                "script, style, iframe, .relate-news, .social-share"
            ):
                el.decompose()

        headline = headline_el.get_text(strip=True)
        body = " ".join([content.get_text(separator=" ", strip=True) for content in content_div])
        published_at = parse_datetime(date_el.get_text(strip=True)) if date_el else datetime.now()
        
        if pdf_url and pdf_url.get("href"):
            raw_href = str(pdf_url["href"]).strip()
            # Normalize relative URLs if needed
            pdf_url = f"https://vietstock.vn{raw_href}" if raw_href.startswith("/") else raw_href
       
        if not headline or not body:
            print(f"  ⚠️ Parse failed (Missing layout tags): {url}")
            return None

        return {
            "source_url": url,
            "publisher": "Vietstock",
            "headline": headline,
            "raw_content": body,
            "published_at": published_at or published_date,
            "pdf_url": pdf_url,
            "content_hash": generate_content_hash(headline, body)
        }
    except Exception as e:
        print(f"  ⚠️ Vietstock parse error at {url}: {e}")
        return None
