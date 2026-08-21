from typing import List
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.src.ingestion.crawl_runner import run_crawl_for_tickers

router = APIRouter()


class CrawlRequest(BaseModel):
    tickers: List[str] = Field(
        ...,
        min_length=1,
        description="Ticker symbols to crawl, e.g. ['PNJ', 'VNM']",
    )


@router.post("/run")
async def run_crawl(payload: CrawlRequest):
    """
    Streams crawl progress as newline-delimited plain text — one log line
    per chunk, flushed as soon as it happens.

    Every ticker in `tickers` is crawled CONCURRENTLY (asyncio.gather), and
    within each ticker, all of its crawler sources (CafeF, Vietstock,
    StockBiz news, StockBiz financial reports) also run concurrently. Log
    lines from different tickers/sources are interleaved in the stream as
    they're produced, not printed one ticker at a time.

    Consume with a streaming HTTP client, e.g.:
        requests.post(url, json={"tickers": [...]}, stream=True)
        for line in response.iter_lines(decode_unicode=True): ...
    """
    async def log_stream():
        async for line in run_crawl_for_tickers(payload.tickers):
            yield line + "\n"

    return StreamingResponse(log_stream(), media_type="text/plain")