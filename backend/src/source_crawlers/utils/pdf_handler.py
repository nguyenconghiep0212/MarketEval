from backend.src.source_crawlers.utils.generate_content_hash import generate_content_hash
from typing import Dict, Optional, Any
import fitz
import httpx
from sqlalchemy import UUID
import pdfplumber
import io
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream
from io import BytesIO

# Reuse a single converter instance across requests to avoid reloading models
doc_converter = DocumentConverter()
    
async def download_and_extract_pdf(client: httpx.AsyncClient, article_id: UUID, pdf_url: str, is_download_url: bool = False) -> Optional[Dict[str, Any]]:
    """Downloads an attached PDF and extracts its text contents."""
    try:
        res = await client.get(pdf_url, follow_redirects=True)
        if res.status_code != 200 or len(res.content) < 100:
            return None

        # Parse in-memory PDF bytes
        # doc = fitz.open(stream=res.content, filetype="pdf")
        # extracted_pages = []
        # for page in doc:
        #     text = page.get_text("text").strip()
        #     if text:
        #         extracted_pages.append(text)
        # full_text = "\n\n".join(extracted_pages)
        
        # Using docling for better extraction
        full_text = convert_pdf_to_markdown(pdf_url) if not is_download_url else await parse_pdf_from_download_url(client, pdf_url)

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
    
def extract_pdf_with_pdfplumber(pdf_bytes: bytes) -> str:
    extracted_text = []
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            # layout=True maintains visual spatial layout (columns, tables)
            text = page.extract_text(layout=True)
            if text:
                extracted_text.append(text)
                
    return "\n\n".join(extracted_text)

def convert_pdf_to_markdown(pdf_path_or_url: str) -> str:
    result = doc_converter.convert(pdf_path_or_url)
    return result.document.export_to_markdown()

async def parse_pdf_from_download_url(client: httpx.AsyncClient, download_url: str) -> str:
    # 1. Fetch raw PDF bytes using your crawler's HTTP client
    response = await client.get(download_url, follow_redirects=True)
    response.raise_for_status()

    # 2. Wrap bytes in a DocumentStream
    pdf_stream = DocumentStream(
        name="downloaded_report.pdf",
        stream=BytesIO(response.content)
    )

    # 3. Pass stream to Docling
    result = doc_converter.convert(pdf_stream)
    return result.document.export_to_markdown()