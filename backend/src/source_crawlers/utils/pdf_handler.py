from backend.src.source_crawlers.utils.generate_content_hash import generate_content_hash
from typing import Dict, Optional, Any
import fitz
import httpx
import io
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream
from io import BytesIO

import os

# 1. Limit thread allocation for Intel Hybrid Architecture (2 P-cores + 8 E-cores)
os.environ["DOCLING_NUM_THREADS"] = "8"
os.environ["OMP_NUM_THREADS"] = "8"

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    EasyOcrOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

accel = AcceleratorOptions(num_threads=8, device=AcceleratorDevice.CPU)
ocr_config = EasyOcrOptions(
    lang=["vi", "en"],
    force_full_page_ocr=False  # CRITICAL: Only OCR the image boxes, not whole pages
)
pipeline_options = PdfPipelineOptions(
    accelerator_options=accel,
    do_ocr=True,
    ocr_options=ocr_config,
    do_chart_extraction=True,
    table_structure_options=TableStructureOptions(mode=TableFormerMode.ACCURATE, do_cell_matching=True)
    
)

doc_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options, 
            backend=PyPdfiumDocumentBackend
        )
    }
)


async def download_and_extract_pdf(
    client: httpx.AsyncClient,
    pdf_url: str,
    is_download_url: bool = False,
) -> Optional[Dict[str, Any]]:
    """Downloads an attached PDF and extracts its text contents."""
    try:
        res = await client.get(pdf_url, follow_redirects=True)
        if res.status_code != 200 or len(res.content) < 100:
            return None

        # Parse in-memory PDF bytes directly with pymupdf
        # doc = fitz.open(stream=res.content, filetype="pdf")
        # extracted_pages = []
        # for page in doc:
        #     text = page.get_text("text").strip()
        #     if text:
        #         extracted_pages.append(text)
        # full_text = "\n\n".join(extracted_pages)
         
        # Using docling for better extraction
        full_text = (
            convert_pdf_to_markdown(pdf_url)
            if not is_download_url
            else await parse_pdf_from_download_url(client, pdf_url)
        )

        if len(full_text.strip()) < 30:
            print(f"  ⚠️ PDF empty or scanned image without selectable text: {pdf_url}")
            return None

        filename = pdf_url.split("/")[-1].split("?")[0]

        return {
            "file_url": pdf_url,
            "file_name": filename,
            "raw_content": full_text,
            "content_hash": generate_content_hash(filename, full_text),
        }
    except Exception as e:
        print(f"  ❌ Failed to download/parse PDF at {pdf_url}: {e}")
        return None


def convert_pdf_to_markdown(pdf_path_or_url: str) -> str:
    result = doc_converter.convert(pdf_path_or_url)
    return result.document.export_to_markdown()


async def parse_pdf_from_download_url(
    client: httpx.AsyncClient, download_url: str
) -> str:
    # 1. Fetch raw PDF bytes using your crawler's HTTP client
    response = await client.get(download_url, follow_redirects=True)
    response.raise_for_status()

    # 2. Wrap bytes in a DocumentStream
    pdf_stream = DocumentStream(
        name="downloaded_report.pdf", stream=BytesIO(response.content)
    )

    # 3. Pass stream to Docling
    result = doc_converter.convert(pdf_stream)
    return result.document.export_to_markdown()
