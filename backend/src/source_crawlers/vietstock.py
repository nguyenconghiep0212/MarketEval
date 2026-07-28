import httpx
from bs4 import BeautifulSoup
from typing import List

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://finance.vietstock.vn"
}

def fetch_vietstock_urls_authenticated(symbol: str, page: int = 1, page_size: int = 10) -> List[str]:
    page_url = f"https://finance.vietstock.vn/{symbol.upper()}/tin-tuc-su-kien.htm"
    api_url = "https://finance.vietstock.vn/data/GetNews"
    
    # httpx.Client maintains cookies (ASP.NET_SessionId, __RequestVerificationToken) across calls
    with httpx.Client(headers=BASE_HEADERS, follow_redirects=True, timeout=12.0) as client:
        
        # --- STEP 1: Establish Session & Extract Anti-Forgery Token ---
        print(f"🔑 Handshaking with Vietstock session for {symbol}...")
        init_res = client.get(page_url)
        
        if init_res.status_code != 200:
            print(f"⚠️ Initial page load failed: {init_res.status_code}")
            return []
            
        soup = BeautifulSoup(init_res.text, "lxml")
        token_input = soup.select_one("input[name='__RequestVerificationToken']")
        
        if not token_input or not token_input.get("value"):
            print("⚠️ Could not extract __RequestVerificationToken from page HTML.")
            return []
            
        csrf_token = token_input["value"]
        
        # --- STEP 2: Query API with Extracted Token & Established Cookies ---
        payload = {
            "code": symbol.upper(),
            "type": "-1",
            "page": str(page),
            "pageSize": str(page_size),
            "__RequestVerificationToken": csrf_token
        }
        
        # Update Referer header to match current ticker context
        client.headers["Referer"] = page_url
        
        print(f"🚀 Querying /data/GetNews endpoint...")
        api_res = client.post(api_url, data=payload)
        
        if api_res.status_code != 200:
            print(f"❌ API call failed with HTTP status: {api_res.status_code}")
            return []
            
        data = api_res.json()
        
        # --- STEP 3: Parse Article Links ---
        article_urls = []
        for item in data:
            url_path = item.get("Url") or item.get("URL")
            if url_path:
                full_url = f"https://vietstock.vn{url_path}" if url_path.startswith("/") else url_path
                if full_url not in article_urls:
                    article_urls.append(full_url)
                    
        print(f"✅ Successfully retrieved {len(article_urls)} news article URLs!")
        return article_urls

if __name__ == "__main__":
    urls = fetch_vietstock_urls_authenticated("VNM", page=1, page_size=10)
    for u in urls:
        print(f"• {u}")