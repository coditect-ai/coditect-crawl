"""Scrapy settings for CODITECT deep crawl.

Polite defaults: respects robots.txt, AutoThrottle enabled, 8 concurrent requests.
Optional scrapy-playwright integration for SPA pages.

Rate limiting strategy (3 layers):
  1. Static: DOWNLOAD_DELAY + CONCURRENT_REQUESTS as floor
  2. Dynamic: AutoThrottle adjusts delay based on server latency
  3. Reactive: Retry with backoff on 429/5xx via RetryMiddleware
"""

from __future__ import annotations


def get_scrapy_settings(*, spa: bool = False, max_pages: int = 100) -> dict:
    """Build Scrapy settings dict.

    Args:
        spa: Enable scrapy-playwright for JS rendering.
        max_pages: Maximum pages to crawl (CLOSESPIDER_PAGECOUNT).

    Returns:
        dict suitable for CrawlerProcess(settings=...).
    """
    settings: dict = {
        # Identification
        "BOT_NAME": "coditect-crawl",
        "USER_AGENT": (
            "CoditectBot/0.1 (+https://coditect.ai/bot) "
            "Mozilla/5.0 (compatible)"
        ),
        # Politeness — static floor
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_TIMEOUT": 30,
        # AutoThrottle — dynamic adjustment based on server latency.
        # Starts at DOWNLOAD_DELAY, adjusts between START_DELAY and
        # MAX_DELAY based on response times. Backs off automatically
        # when the server slows down (e.g., approaching rate limits).
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 2.0,
        # Dedup & filtering
        "DUPEFILTER_CLASS": "scrapy.dupefilters.RFPDupeFilter",
        # Close conditions
        "CLOSESPIDER_PAGECOUNT": max_pages,
        # Pipelines
        "ITEM_PIPELINES": {
            "coditect_crawl.orchestrators.scrapy_spider.TrafilaturaPipeline": 300,
        },
        # Logging (suppress in subprocess)
        "LOG_LEVEL": "WARNING",
        "LOG_ENABLED": True,
        # Retry — use BackoffRetryMiddleware for exponential backoff + jitter
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "DOWNLOADER_MIDDLEWARES": {
            # Disable default retry, use our backoff-aware version
            "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
            "coditect_crawl.orchestrators.retry_middleware.BackoffRetryMiddleware": 550,
        },
        # Reactor (required for scrapy-playwright compatibility)
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        # Disable telnet (not needed in subprocess)
        "TELNETCONSOLE_ENABLED": False,
    }

    if spa:
        # Playwright is heavier — tighter concurrency, longer timeouts
        settings["CONCURRENT_REQUESTS"] = 2
        settings["CONCURRENT_REQUESTS_PER_DOMAIN"] = 1
        settings["DOWNLOAD_DELAY"] = 2.0
        settings["DOWNLOAD_TIMEOUT"] = 60
        settings["AUTOTHROTTLE_START_DELAY"] = 2.0
        settings["AUTOTHROTTLE_MAX_DELAY"] = 60.0
        settings["AUTOTHROTTLE_TARGET_CONCURRENCY"] = 1.0
        settings["PLAYWRIGHT_MAX_PAGES_PER_CONTEXT"] = 2
        settings.update({
            "DOWNLOAD_HANDLERS": {
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
            "PLAYWRIGHT_BROWSER_TYPE": "chromium",
            "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 45000,
            "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": None,
        })

    return settings
