import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Optional, Dict
from crawlers.utils import generate_content_hash

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://web.stockbiz.vn/"
}

def fetch_stockbiz_article_urls(symbol: str) -> List[str]:
    pool_url = f"https://web.stockbiz.vn/Stocks/{symbol.upper()}/CompanyNews.aspx"
    article_urls = []
    
    try:
        res = httpx.get(pool_url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if res.status_code != 200:
            return []
            
        soup = BeautifulSoup(res.text, "lxml")
        container = soup.select_one("#mod_top_company_news")
        if not container:
            return []
            
        for a_tag in container.select("td.news_title a[href]"):
            raw_href = a_tag.get("href")
            if raw_href:
                full_url = urljoin("https://web.stockbiz.vn", raw_href.strip())
                if full_url not in article_urls:
                    article_urls.append(full_url)
    except Exception as e:
        print(f"  ❌ StockBiz discovery error for {symbol}: {e}")
        
    return article_urls


async def parse_stockbiz_article(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, str]]:
    """Extracts headline, raw body text, and content_hash for a StockBiz article."""
    try:
        res = await client.get(url, headers=HEADERS)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "lxml")
        
        # StockBiz specific selectors
        headline_el = soup.select_one(".news_title") or soup.select_one("h1")
        content_div = soup.select_one("#newscontent") or soup.select_one(".contentdetail") or soup.select_one(".news_body")

        if not headline_el or not content_div:
            return None

        for el in content_div.select("script, style, iframe, .relate-news"):
            el.decompose()

        headline = headline_el.get_text(strip=True)
        body = content_div.get_text(separator=" ", strip=True)

        if not headline or not body:
            return None

        return {
            "source_url": url,
            "publisher": "StockBiz",
            "headline": headline,
            "raw_content": body,
            "content_hash": generate_content_hash(headline, body)
        }
    except Exception as e:
        print(f"  ⚠️ StockBiz parse error at {url}: {e}")
        return None