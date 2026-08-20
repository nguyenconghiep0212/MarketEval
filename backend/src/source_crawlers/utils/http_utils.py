"""HTTP utilities for reliable web scraping with retry logic."""
import asyncio
import httpx
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for HTTP retry behavior."""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        timeout: float = 15.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.timeout = timeout


async def fetch_with_retry(
    url: str,
    client: Optional[httpx.AsyncClient] = None,
    headers: Optional[Dict[str, str]] = None,
    retry_config: Optional[RetryConfig] = None,
) -> Optional[httpx.Response]:
    if retry_config is None:
        retry_config = RetryConfig()

    should_close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=retry_config.timeout)

    try:
        for attempt in range(retry_config.max_retries + 1):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{retry_config.max_retries + 1})")
                response = await client.get(url, headers=headers or {})

                if response.status_code >= 500:
                    if attempt < retry_config.max_retries:
                        delay = min(retry_config.base_delay * (retry_config.backoff_factor ** attempt), retry_config.max_delay)
                        logger.warning(f"Server error ({response.status_code}). Retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Server error ({response.status_code}) after {attempt + 1} attempts")
                        return None

                if response.status_code == 200:
                    logger.info(f"Successfully fetched {url}")
                    return response

                logger.warning(f"HTTP {response.status_code} for {url}")
                return response
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
                if attempt < retry_config.max_retries:
                    delay = min(retry_config.base_delay * (retry_config.backoff_factor ** attempt), retry_config.max_delay)
                    logger.warning(f"Network error ({type(e).__name__}): {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Network error after {attempt + 1} attempts: {e}")
                    return None
        return None
    finally:
        if should_close_client:
            await client.aclose()


async def fetch_batch_urls(
    urls: list[str],
    headers: Optional[Dict[str, str]] = None,
    max_concurrent: int = 3,
    retry_config: Optional[RetryConfig] = None,
) -> Dict[str, Optional[httpx.Response]]:
    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_limited(url: str):
            async with semaphore:
                return url, await fetch_with_retry(url, client, headers, retry_config)

        tasks = [fetch_limited(url) for url in urls]
        results = await asyncio.gather(*tasks)

        return {url: response for url, response in results}
