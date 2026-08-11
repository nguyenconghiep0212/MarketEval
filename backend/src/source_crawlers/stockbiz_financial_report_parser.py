import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Optional, Dict, Any
from backend.src.source_crawlers.utils import generate_content_hash, parse_datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://web.stockbiz.vn"
}

async def fetch_stockbiz_financial_report_urls(client: httpx.AsyncClient, pool_url: str) -> List[str]:
    """Step 1: Extract news URLs using the database-provided pool_url."""
    article_urls = []
    
    try:
        res = await client.get(pool_url, headers=HEADERS)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "lxml")
        for a_tag in soup.select('.dataTable a[id*="_lnkTitle"]'):
            raw_href = a_tag.get("href")
            print(f"  🔗 Raw StockBiz link: {raw_href}")
            if raw_href:
                full_url = urljoin("https://web.stockbiz.vn", raw_href.strip()) # type: ignore
                if full_url not in article_urls:
                    article_urls.append(full_url)
    except Exception as e:
        print(f"  ❌ StockBiz URL discovery error at {pool_url}: {e}")
        
    return article_urls


async def parse_stockbiz_financial_report_article(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, Any]]:
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
            soup.select_one("table[id*='_tblReportDetail'] tr:first-child td:last-child")
        )
        date_el = (
            soup.select_one("table[id*='_tblReportDetail'] table tr td:nth-of-type(2)")
        )
        
        content_div = (
            soup.select_one("#content_com_main > table:last-child td:last-child")
        )
        
        pdf_a = (
            soup.select_one("a[id*='_lnkDownload']")
        )

        if not headline_el:
            print(f"  ⚠️ Parse failed (Missing headline tags): {url}")
            return None

        if not content_div:
            print(f"  ⚠️ Parse failed (Missing content tags): {url}")
            return None

        for el in content_div.select("script, style, iframe, .link-content-footer, .vouchers, .relate-news, .pT22"):
            el.decompose()
    
        headline = headline_el.get_text(strip=True)
        body = content_div.get_text(separator=" ", strip=True)
        published_at = parse_datetime(date_el.get_text(strip=True)) if date_el else datetime.now()
        pdf_url = urljoin("https://web.stockbiz.vn/", pdf_a["href"].strip()) if pdf_a else None  # type: ignore

        return {
            "source_url": url,
            "publisher": "StockBiz",
            "headline": headline,
            "raw_content": body,
            "published_at": published_at,
            "pdf_url": pdf_url,
            "is_pdf_download_url": True,
            "content_hash": generate_content_hash(headline, body)
        }
    except Exception as e:
        print(f"  ⚠️ StockBiz parse error at {url}: {e}")
        return None