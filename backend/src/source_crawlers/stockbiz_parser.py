import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Optional, Dict, Any
from src.source_crawlers.utils import generate_content_hash, parse_datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://cafef.vn/"
}

def fetch_stockbiz_urls(pool_url: str) -> List[str]:
    """Step 1: Extract news URLs using the database-provided pool_url."""
    article_urls = []
    
    try:
        res = httpx.get(pool_url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "lxml")
        container = soup.select_one("div#mod_top_company_news")
        if not container:
            return []
            
        for a_tag in container.select("tr > td.news_title > b > a"):
            raw_href = a_tag.get("href")
            print(f"  🔗 Raw StockBiz link: {raw_href}")
            if raw_href:
                full_url = urljoin("https://stockbiz.vn", raw_href.strip()) # type: ignore
                if full_url not in article_urls:
                    article_urls.append(full_url)
    except Exception as e:
        print(f"  ❌ StockBiz URL discovery error at {pool_url}: {e}")
        
    return article_urls


async def parse_stockbiz_article(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, Any]]:
    """Step 2: Parse headline, published date, and body text."""
    if url.lower().endswith(".pdf") or ".doc" in url.lower() or "download" in url.lower():
        print(f"  ⏭️ Skipped (Document Link): {url}")
        return None

    try:
        res = await client.get(url, headers=HEADERS)
        if res.status_code != 200:
            print(f"  ⚠️ HTTP {res.status_code} for: {url}")
            return None

        soup = BeautifulSoup(res.text, "lxml")
        
        headline_el = (
            soup.select_one("div.news_title")
        )
        
        date_el = (
            soup.select_one("span.news_date")
        )
        
        content_div = (
            soup.select_one("span.news_content")
        )
        
        pdf_a = (
            soup.select_one("div.newsAttachment a[href]")
        )

        if not headline_el or not content_div:
            print(f"  ⚠️ Parse failed (Missing layout tags): {url}")
            return None

        for el in content_div.select("script, style, iframe, .link-content-footer, .vouchers, .relate-news, .pT22"):
            el.decompose()
    
        headline = headline_el.get_text(strip=True)
        body = content_div.get_text(separator=" ", strip=True)
        published_at = parse_datetime(date_el.get_text(strip=True)) if date_el else "Unknown"
        pdf_url = urljoin("https://web.stockbiz.vn/", pdf_a["href"].strip()) if pdf_a else None  # type: ignore

        if not headline or len(body) < 50:
            print(f"  ⚠️ Parse failed (Content too short): {url}")
            return None

        return {
            "source_url": url,
            "publisher": "StockBiz",
            "headline": headline,
            "raw_content": body,
            "published_at": published_at,
            "pdf_url": pdf_url,
            "content_hash": generate_content_hash(headline, body)
        }
    except Exception as e:
        print(f"  ⚠️ StockBiz parse error at {url}: {e}")
        return None