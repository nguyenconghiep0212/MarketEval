import asyncio
from typing import Optional

from backend.src.nlp.sentiment import SentimentEngine

_sentiment_engine: Optional[SentimentEngine] = None
_sentiment_engine_lock = asyncio.Lock()


async def get_sentiment_engine() -> SentimentEngine:
    """
    Lazily loads and caches a single SentimentEngine instance for the whole
    process. Loading the underlying transformer model (uitnlp/visobert) is
    expensive — several seconds at minimum — so it must happen once, not on
    every /analyze-sentiment call. The double-checked lock avoids two
    concurrent requests both triggering a full model load simultaneously.

    Model construction itself is synchronous/blocking, so it's run in a
    worker thread via asyncio.to_thread to avoid stalling the event loop
    during the (one-time) load.
    """
    global _sentiment_engine
    if _sentiment_engine is None:
        async with _sentiment_engine_lock:
            if _sentiment_engine is None:  # re-check inside the lock
                _sentiment_engine = await asyncio.to_thread(SentimentEngine)
    return _sentiment_engine