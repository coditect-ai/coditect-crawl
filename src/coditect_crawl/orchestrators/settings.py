"""Scrapy settings for CODITECT deep crawl.

Polite defaults: respects robots.txt, 1s download delay, 8 concurrent requests.
Optional scrapy-playwright integration for SPA pages.
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
        # Politeness
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_TIMEOUT": 30,
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
        # Retry
        "RETRY_TIMES": 2,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        # Reactor (required for scrapy-playwright compatibility)
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        # Disable telnet (not needed in subprocess)
        "TELNETCONSOLE_ENABLED": False,
    }

    if spa:
        settings.update({
            "DOWNLOAD_HANDLERS": {
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
            "PLAYWRIGHT_BROWSER_TYPE": "chromium",
            "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
        })

    return settings
