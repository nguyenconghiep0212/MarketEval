import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://web.stockbiz.vn/"
}

def fetch_stockbiz_article_urls(symbol: str) -> List[str]:
    """
    Crawls the StockBiz company news pool for a ticker and returns a deduplicated
    list of absolute article URLs (hrefs).
    """
    pool_url = f"https://web.stockbiz.vn/Stocks/{symbol.upper()}/CompanyNews.aspx"
    print(f"🔍 Scanning StockBiz pool for {symbol}: {pool_url}")
    
    article_urls = []
    
    try:
        response = httpx.get(pool_url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            print(f"⚠️ Failed to reach StockBiz pool page. HTTP Status: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, "lxml")
        container = soup.select_one("#mod_top_company_news")
        
        if not container:
            print(f"⚠️ Could not find '#mod_top_company_news' container for {symbol}.")
            return []
            
        # Target links inside the news title table cells
        for a_tag in container.select("td.news_title a[href]"):
            raw_href = a_tag.get("href")
            if raw_href:
                full_url = urljoin("https://web.stockbiz.vn", raw_href.strip())
                if full_url not in article_urls:
                    article_urls.append(full_url)
                    
        print(f"✅ Found {len(article_urls)} news article links for {symbol}.")
        return article_urls

    except Exception as e:
        print(f"❌ Error scraping StockBiz URL pool for {symbol}: {e}")
        return []

if __name__ == "__main__":
    ticker = "VNM"
    urls = fetch_stockbiz_article_urls(ticker)
    
    print("\nSample Extracted StockBiz URLs:")
    for url in urls:
        print(f"• {url}")