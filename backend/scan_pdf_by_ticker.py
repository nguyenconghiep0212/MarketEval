import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from database.queries import get_unprocessed_pdf_articles, save_article_attachment
from src.source_crawlers.utils.pdf_handler import download_and_extract_pdf

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/marketeval")


async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) # type: ignore

    async with async_session() as session: # type: ignore
        # Fetch PDF files with from DB
        pdf_urls = await get_unprocessed_pdf_articles(session, ticker_symbol=["PNJ"])
        if not pdf_urls:
            print("⚠️ No unprocessed PDF articles found for the given ticker(s).")
            return
        
        print("=" * 60)
        print("🚀 STARTING PDF SCANNING PIPELINE")
        print("=" * 60)
        
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for pdf_url in pdf_urls:
                art_id = pdf_url["article_id"]
                symbol = pdf_url["ticker_id"]
                pdf_url_value = pdf_url["pdf_url"]
                is_pdf_download_url = pdf_url["is_pdf_download_url"]
                
                print(f"\n🔍 Processing PDF {pdf_url_value} for {symbol}...")

                pdf_processed_content = await download_and_extract_pdf(client, art_id, pdf_url_value, is_pdf_download_url)
                print(f"  ├─ Process {pdf_url_value} successfully")

                insert_pdf_count = 0
                if pdf_processed_content:
                    pdf_id = await save_article_attachment(session, art_id, pdf_processed_content)
                    if pdf_id:
                        insert_pdf_count += 1
                        now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{now_str}]   ├─ Save PDF {pdf_url_value} for {symbol}")
                    await asyncio.sleep(0.1)

                print(f"  └─ PDFs inserted: {insert_pdf_count}")

if __name__ == "__main__":
    asyncio.run(main())