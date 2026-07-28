import httpx
from bs4 import BeautifulSoup
from typing import List, Optional, Dict
from crawlers.utils import generate_content_hash

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://finance.vietstock.vn"
}

def fetch_vietstock_urls_authenticated(symbol: str, page: int = 1, page_size: int = 10) -> List[str]:
    page_url = f"https://finance.vietstock.vn/{symbol.upper()}/tin-tuc-su-kien.htm"
    api_url = "https://finance.vietstock.vn/data/GetNews"
    article_urls = []
    
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=12.0) as client:
            init_res = client.get(page_url)
            if init_res.status_code != 200:
                return []
                
            soup = BeautifulSoup(init_res.text, "lxml")
            token_input = soup.select_one("input[name='__RequestVerificationToken']")
            if not token_input or not token_input.get("value"):
                return []
                
            csrf_token = token_input["value"]
            
            payload = {
                "code": symbol.upper(),
                "type": "-1",
                "page": str(page),
                "pageSize": str(page_size),
                "__RequestVerificationToken": csrf_token
            }
            client.headers["Referer"] = page_url
            api_res = client.post(api_url, data=payload)
            
            if api_res.status_code == 200:
                data = api_res.json()
                for item in data:
                    url_path = item.get("Url") or item.get("URL")
                    if url_path:
                        full_url = f"https://vietstock.vn{url_path}" if url_path.startswith("/") else url_path
                        if full_url not in article_urls:
                            article_urls.append(full_url)
    except Exception as e:
        print(f"  ❌ Vietstock discovery error for {symbol}: {e}")
        
    return article_urls


async def parse_vietstock_article(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, str]]:
    """Extracts headline, raw body text, and content_hash for a Vietstock article."""
    try:
        res = await client.get(url, headers={"User-Agent": HEADERS["User-Agent"]})
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "lxml")
        
        # Vietstock specific selectors
        headline_el = soup.select_one("h1.article-title") or soup.select_one("h1.title") or soup.select_one("h1")
        content_div = soup.select_one(".article-content") or soup.select_one("#channel-detail-content") or soup.select_one(".content")

        if not headline_el or not content_div:
            return None

        for el in content_div.select("script, style, iframe, .relate-news, .social-share"):
            el.decompose()

        headline = headline_el.get_text(strip=True)
        body = content_div.get_text(separator=" ", strip=True)

        if not headline or not body:
            return None

        return {
            "source_url": url,
            "publisher": "Vietstock",
            "headline": headline,
            "raw_content": body,
            "content_hash": generate_content_hash(headline, body)
        }
    except Exception as e:
        print(f"  ⚠️ Vietstock parse error at {url}: {e}")
        return None