import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://cafef.vn/"
}

def fetch_cafef_article_urls(symbol: str) -> List[str]:
    """
    Crawls the CafeF corporate events pool for a ticker and returns a deduplicated
    list of absolute article URLs (hrefs).
    """
    pool_url = f"https://cafef.vn/du-lieu/tin-doanh-nghiep/{symbol.lower()}/event.chn"
    print(f"🔍 Scanning CafeF pool for {symbol}: {pool_url}")
    
    article_urls = []
    
    try:
        response = httpx.get(pool_url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            print(f"⚠️ Failed to reach CafeF pool page. HTTP Status: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, "lxml")
        events_container = soup.select_one("div.tintucsukien #divEvents") or soup.select_one("div.tintucsukien")
        
        if not events_container:
            print(f"⚠️ Could not find 'tintucsukien' container for {symbol}.")
            return []
            
        # Extract href attributes from all article links
        for a_tag in events_container.select("ul > li a.docnhanhTitle"):
            raw_href = a_tag.get("href")
            if raw_href:
                full_url = urljoin("https://cafef.vn", raw_href.strip())
                if full_url not in article_urls:
                    article_urls.append(full_url)
            
        print(f"✅ Found {len(article_urls)} news article links for {symbol}.")
        return article_urls

    except Exception as e:
        print(f"❌ Error scraping CafeF URL pool for {symbol}: {e}")
        return []

if __name__ == "__main__":
    ticker = "POW"
    urls = fetch_cafef_article_urls(ticker)
    
    print("\nExtracted URLs:")
    for url in urls:
        print(f"• {url}")