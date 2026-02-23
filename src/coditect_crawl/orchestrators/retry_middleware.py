"""Custom retry middleware with exponential backoff, jitter, and Retry-After support.

Replaces Scrapy's default RetryMiddleware for rate-limit-aware crawling.
Handles 429 responses by:
  1. Respecting Retry-After header if present
  2. Exponential backoff with random jitter (human-like)
  3. Logging backoff duration for observability
"""

from __future__ import annotations

import logging
import random
import time

from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

logger = logging.getLogger(__name__)


class BackoffRetryMiddleware(RetryMiddleware):
    """Retry middleware with exponential backoff and jitter for 429 responses.

    For 429 (Too Many Requests):
      - Checks Retry-After header first (seconds or HTTP-date)
      - Falls back to exponential backoff: base * 2^attempt + jitter
      - Jitter range: 0.5-1.5x (simulates human timing variance)

    For other retry codes (500, 502, etc.):
      - Uses standard Scrapy retry with a small fixed delay
    """

    # Backoff parameters
    BACKOFF_BASE = 2.0       # Base delay in seconds
    BACKOFF_MAX = 120.0      # Cap at 2 minutes
    JITTER_MIN = 0.5         # Multiply delay by 0.5-1.5 for jitter
    JITTER_MAX = 1.5
    FIXED_RETRY_DELAY = 1.0  # Delay for non-429 retries

    @classmethod
    def from_crawler(cls, crawler):
        mw = super().from_crawler(crawler)
        mw.crawler = crawler
        return mw

    def process_response(self, request, response):
        if request.meta.get("dont_retry", False):
            return response

        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            retry_count = request.meta.get("retry_times", 0)

            if response.status == 429:
                delay = self._get_429_delay(response, retry_count)
                logger.warning(
                    "429 on %(url)s — backing off %(delay).1fs "
                    "(attempt %(attempt)d/%(max)d)",
                    {
                        "url": request.url,
                        "delay": delay,
                        "attempt": retry_count + 1,
                        "max": self.max_retry_times,
                    },
                )
                # Sleep in the downloader thread (blocking is fine here —
                # Scrapy runs downloads in a thread pool via Twisted)
                time.sleep(delay)
            else:
                # Small fixed delay for server errors
                time.sleep(self.FIXED_RETRY_DELAY)

            return self._retry(request, reason, spider) or response

        return response

    def _get_429_delay(self, response, retry_count: int) -> float:
        """Calculate delay for a 429 response.

        Priority:
          1. Retry-After header (if present and parseable)
          2. Exponential backoff with jitter
        """
        # Check Retry-After header
        retry_after = response.headers.get(b"Retry-After")
        if retry_after:
            try:
                delay = float(retry_after)
                # Add small jitter even to server-specified delays
                jitter = random.uniform(0.8, 1.2)
                return min(delay * jitter, self.BACKOFF_MAX)
            except (ValueError, TypeError):
                pass  # Not a number — could be HTTP-date, fall through

        # Exponential backoff: base * 2^attempt
        delay = self.BACKOFF_BASE * (2 ** retry_count)

        # Apply jitter (human-like variance)
        jitter = random.uniform(self.JITTER_MIN, self.JITTER_MAX)
        delay *= jitter

        return min(delay, self.BACKOFF_MAX)
