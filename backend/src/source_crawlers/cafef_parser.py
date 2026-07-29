import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Optional, Dict, Any
from src.source_crawlers.utils import generate_content_hash, parse_vietnamese_datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://cafef.vn/"
}

def fetch_cafef_urls(pool_url: str) -> List[str]:
    """Step 1: Extract news URLs using the database-provided pool_url."""
    article_urls = []
    
    try:
        res = httpx.get(pool_url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "lxml")
        container = soup.select_one("div.tintucsukien #divEvents") or soup.select_one("div.tintucsukien")
        if not container:
            return []
            
        for a_tag in container.select("ul > li a.docnhanhTitle"):
            raw_href = a_tag.get("href")
            print(f"  🔗 Raw CafeF link: {raw_href}")
            if raw_href:
                full_url = urljoin("https://cafef.vn", raw_href.strip()) # type: ignore
                if full_url not in article_urls:
                    article_urls.append(full_url)
    except Exception as e:
        print(f"  ❌ CafeF URL discovery error at {pool_url}: {e}")
        
    return article_urls


async def parse_cafef_article(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, Any]]:
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
            soup.select_one("h1.title") or 
            soup.select_one("h1.title-detail") or 
            soup.select_one(".text_noibat_cacbaikhac") or
            soup.select_one(".news-title") or 
            soup.select_one("h1")
        )
        
        date_el = (
            soup.select_one("#ContentPlaceHolder1_ChiTietTin1_NewsContent1_lblNgay") or
            soup.select_one("span.pdate") or
            soup.select_one(".pdate") or
            soup.select_one("span.pdate-detail") or 
            soup.select_one("span[data-role='publishdate']")
        )
        
        content_div = (
            soup.select_one(".knc-content") or 
            soup.select_one(".detail-content") or 
            soup.select_one("#newscontent") or 
            soup.select_one(".totalcontentdetail") or 
            soup.select_one(".content")
        )
        
        pdf_a = (
            soup.select_one("div.FileWrapper a[href$='.pdf']")
        )

        if not headline_el or not content_div:
            print(f"  ⚠️ Parse failed (Missing layout tags): {url}")
            return None

        for el in content_div.select("script, style, iframe, .link-content-footer, .vouchers, .relate-news, .pT22"):
            el.decompose()

        headline = headline_el.get_text(strip=True)
        body = content_div.get_text(separator=" ", strip=True)
        published_at = parse_vietnamese_datetime(date_el.get_text(strip=True)) if date_el else "Unknown"
        pdf_url = pdf_a["href"] if pdf_a else None

        if not headline or len(body) < 50:
            print(f"  ⚠️ Parse failed (Content too short): {url}")
            return None

        return {
            "source_url": url,
            "publisher": "CafeF",
            "headline": headline,
            "raw_content": body,
            "published_at": published_at,
            "pdf_url": pdf_url,
            "content_hash": generate_content_hash(headline, body)
        }
    except Exception as e:
        print(f"  ⚠️ CafeF parse error at {url}: {e}")
        return None