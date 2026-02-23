"""Scrapy-based deep crawl orchestration for CODITECT.

Runs a Scrapy spider in a subprocess to avoid Twisted/asyncio reactor
conflicts. Each page is extracted via Trafilatura and returned as an
ExtractionResult.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import queue
from urllib.parse import urlparse

try:
    import scrapy
    from scrapy.linkextractors import LinkExtractor
except ImportError:
    raise ImportError(
        "Deep crawl requires Scrapy. Install with: pip install coditect-crawl[deep]"
    )

from coditect_crawl.utils.models import ExtractionResult, Link, PageMetadata


# ---------------------------------------------------------------------------
# Scrapy Item
# ---------------------------------------------------------------------------

class CrawlItem(scrapy.Item):
    """Raw page data passed from spider to pipeline."""

    url = scrapy.Field()
    html = scrapy.Field()
    depth = scrapy.Field()
    extraction_result = scrapy.Field()


# ---------------------------------------------------------------------------
# Spider
# ---------------------------------------------------------------------------

class CoditectSpider(scrapy.Spider):
    """Spider that crawls a site following internal links up to max_depth."""

    name = "coditect_deep"

    def __init__(
        self,
        start_url: str,
        max_depth: int = 2,
        spa: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.start_urls = [start_url]
        self.max_depth = max_depth
        self.spa = spa
        parsed = urlparse(start_url)
        self.allowed_domain = parsed.netloc
        self._link_extractor = LinkExtractor(allow_domains=[self.allowed_domain])

    def _playwright_meta(self) -> dict:
        """Build Playwright meta dict for SPA requests."""
        return {
            "playwright": True,
            "playwright_include_page": False,
            "playwright_page_goto_kwargs": {
                "wait_until": "domcontentloaded",
            },
        }

    async def start(self):
        for url in self.start_urls:
            meta: dict = {"depth": 0}
            if self.spa:
                meta.update(self._playwright_meta())
            yield scrapy.Request(url, callback=self.parse, meta=meta)

    def parse(self, response):
        current_depth = response.meta.get("depth", 0)

        # Yield item for pipeline processing
        item = CrawlItem()
        item["url"] = response.url
        item["html"] = response.text
        item["depth"] = current_depth
        yield item

        # Follow internal links if within depth limit
        if current_depth < self.max_depth:
            for link in self._link_extractor.extract_links(response):
                meta: dict = {"depth": current_depth + 1}
                if self.spa:
                    meta.update(self._playwright_meta())
                yield scrapy.Request(link.url, callback=self.parse, meta=meta)


# ---------------------------------------------------------------------------
# Item Pipeline — Trafilatura extraction
# ---------------------------------------------------------------------------

class TrafilaturaPipeline:
    """Converts raw HTML to ExtractionResult via Trafilatura."""

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        return pipeline

    def process_item(self, item):
        from coditect_crawl.extractors.trafilatura import extract_with_trafilatura

        url = item["url"]
        html = item["html"]

        result = extract_with_trafilatura(url, html=html)
        spa = getattr(self.crawler.spider, "spa", False)
        result.fetch_method = f"scrapy-deep{'-playwright' if spa else ''}"

        item["extraction_result"] = result
        return item


# ---------------------------------------------------------------------------
# Cross-process serialization helpers
# ---------------------------------------------------------------------------

def _extraction_result_to_dict(er: ExtractionResult) -> dict:
    """Serialize ExtractionResult for cross-process transfer via Queue."""
    return {
        "url": er.url,
        "markdown": er.markdown,
        "metadata": {
            "title": er.metadata.title,
            "author": er.metadata.author,
            "date": er.metadata.date,
            "description": er.metadata.description,
            "sitename": er.metadata.sitename,
            "url": er.metadata.url,
            "content_type": er.metadata.content_type,
            "language": er.metadata.language,
            "word_count": er.metadata.word_count,
        },
        "links": [
            {
                "url": link.url,
                "text": link.text,
                "context": link.context,
                "is_internal": link.is_internal,
            }
            for link in er.links
        ],
        "fetch_method": er.fetch_method,
        # raw_html intentionally excluded — too large for queue transfer
    }


def _dict_to_extraction_result(d: dict) -> ExtractionResult:
    """Deserialize dict back to ExtractionResult."""
    return ExtractionResult(
        url=d["url"],
        markdown=d["markdown"],
        metadata=PageMetadata(**d["metadata"]),
        links=[Link(**link) for link in d["links"]],
        fetch_method=d["fetch_method"],
        raw_html="",
    )


# ---------------------------------------------------------------------------
# Subprocess target
# ---------------------------------------------------------------------------

def _crawl_subprocess(
    url: str,
    max_depth: int,
    max_pages: int,
    spa: bool,
    result_queue: multiprocessing.Queue,
) -> None:
    """Run CrawlerProcess inside a child process with its own Twisted reactor."""
    import warnings
    warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")

    from scrapy.crawler import CrawlerProcess
    from scrapy import signals

    from coditect_crawl.orchestrators.settings import get_scrapy_settings

    settings = get_scrapy_settings(spa=spa, max_pages=max_pages)
    process = CrawlerProcess(settings=settings)

    def _on_item_scraped(item, response, spider):
        er = item.get("extraction_result")
        if er is not None:
            result_queue.put(_extraction_result_to_dict(er))

    crawler = process.create_crawler(CoditectSpider)
    crawler.signals.connect(_on_item_scraped, signal=signals.item_scraped)

    process.crawl(crawler, start_url=url, max_depth=max_depth, spa=spa)
    process.start()  # Blocks until crawl finishes


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def run_deep_crawl(
    url: str,
    *,
    max_depth: int = 2,
    max_pages: int = 100,
    spa: bool = False,
) -> list[ExtractionResult]:
    """Run a Scrapy deep crawl in a subprocess and return results.

    Spawns CrawlerProcess in a child process (spawn context) to avoid
    Twisted reactor conflicts with the caller's asyncio event loop.
    Results transfer back via multiprocessing.Queue.

    Args:
        url: Starting URL for the crawl.
        max_depth: Maximum link-following depth.
        max_pages: Maximum number of pages to crawl.
        spa: Enable Playwright rendering for JS-heavy pages.

    Returns:
        List of ExtractionResult objects, one per crawled page.
    """
    if spa:
        try:
            import scrapy_playwright  # noqa: F401
        except ImportError:
            raise ImportError(
                "SPA deep crawl requires scrapy-playwright. "
                "Install with: pip install coditect-crawl[deep]"
            )

    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()

    process = ctx.Process(
        target=_crawl_subprocess,
        args=(url, max_depth, max_pages, spa, result_queue),
    )
    process.start()

    # Wait for subprocess without blocking the event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: process.join(timeout=300))

    # Terminate if still running after timeout
    if process.is_alive():
        process.terminate()
        await loop.run_in_executor(None, lambda: process.join(timeout=5))

    # Drain results from the queue
    results: list[ExtractionResult] = []
    while True:
        try:
            result_dict = result_queue.get_nowait()
            results.append(_dict_to_extraction_result(result_dict))
        except queue.Empty:
            break

    return results
