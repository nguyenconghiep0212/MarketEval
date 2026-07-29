import hashlib
import re
from datetime import datetime
from typing import Dict, Optional, Any
import fitz
import httpx
from sqlalchemy import UUID

def generate_content_hash(headline: str, body: str) -> str:
    """Generates a SHA-256 fingerprint for article deduplication."""
    combined = f"{headline.strip().lower()}{body.strip().lower()}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def parse_vietnamese_datetime(raw_str: Optional[str]) -> Optional[datetime]:
    """
    Extracts and parses datetime objects from Vietnamese news date strings.
    Handles inputs like:
      - "Thứ 2, 06/07/2026, 00:00"
      - "Thứ Bảy, 11/07/2026 - 08:30"
      - "16-07-2026 - 00:01 AM"
      - "06/07/2026 00:00"
      - "06/07/2026"
    """
    if not raw_str:
        return None

    # Regex matches DD/MM/YYYY or DD-MM-YYYY, plus optional HH:MM (with optional AM/PM)
    pattern = r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})(?:[,\s\-]+(\d{1,2}:\d{2}(?:\s*[AP]M)?))?'
    match = re.search(pattern, raw_str, re.IGNORECASE)

    if not match:
        return None

    date_part, time_part = match.groups()
    normalized_date = date_part.replace("-", "/")

    if time_part:
        clean_time = time_part.strip().upper()
        full_str = f"{normalized_date} {clean_time}"

        # 1. Try 12-hour format with AM/PM (e.g., "16/07/2026 00:01 AM")
        try:
            return datetime.strptime(full_str, "%d/%m/%Y %I:%M %p")
        except ValueError:
            pass

        # 2. Try 24-hour format (e.g., "06/07/2026 00:00")
        try:
            return datetime.strptime(full_str, "%d/%m/%Y %H:%M")
        except ValueError:
            pass

    # Fallback to date only
    try:
        return datetime.strptime(normalized_date, "%d/%m/%Y")
    except ValueError:
        return None
    
async def download_and_extract_pdf(client: httpx.AsyncClient, article_id: UUID, pdf_url: str) -> Optional[Dict[str, Any]]:
    """Downloads an attached PDF and extracts its text contents."""
    try:
        res = await client.get(pdf_url, follow_redirects=True)
        if res.status_code != 200 or len(res.content) < 100:
            return None

        # Parse in-memory PDF bytes
        doc = fitz.open(stream=res.content, filetype="pdf")
        extracted_pages = []
        for page in doc:
            text = page.get_text("text").strip()
            if text:
                extracted_pages.append(text)

        full_text = "\n\n".join(extracted_pages)

        if len(full_text.strip()) < 30:
            print(f"  ⚠️ PDF empty or scanned image without selectable text: {pdf_url}")
            return None

        filename = pdf_url.split("/")[-1].split("?")[0]

        return {
            "article_id": article_id,
            "file_url": pdf_url,
            "file_name": filename,
            "raw_content": full_text,
            "content_hash": generate_content_hash(filename, full_text)
        }
    except Exception as e:
        print(f"  ❌ Failed to download/parse PDF at {pdf_url}: {e}")
        return None