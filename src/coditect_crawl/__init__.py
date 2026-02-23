"""CODITECT Crawl — Intelligent web content extraction pipeline.

Three-phase layered architecture:
  Phase 1: Trafilatura (static HTML → LLM-optimized markdown)
  Phase 2: Crawl4AI (SPA/JS rendering → markdown)
  Phase 3: Scrapy (bulk/deep crawl orchestration)
"""

__version__ = "0.1.0"

from coditect_crawl.utils.models import ExtractionResult, PageMetadata

__all__ = [
    "extract",
    "deep_crawl",
    "ExtractionResult",
    "PageMetadata",
]


def extract(url: str, *, html: str | None = None, spa: bool = False) -> ExtractionResult:
    """Extract content from a URL or raw HTML into LLM-optimized markdown.

    Uses Trafilatura (Phase 1) by default. If spa=True and content appears
    JS-rendered, falls back to Crawl4AI or Playwright (Phase 2).

    Args:
        url: The URL to extract from (used for metadata even if html is provided).
        html: Optional pre-fetched HTML. If None, fetches the URL.
        spa: Enable SPA detection and rendering fallback.

    Returns:
        ExtractionResult with markdown, metadata, and extracted links.
    """
    from coditect_crawl.extractors.trafilatura import extract_with_trafilatura

    result = extract_with_trafilatura(url, html=html)

    if spa and result.is_likely_spa():
        try:
            from coditect_crawl.renderers.crawl4ai import render_spa

            result = render_spa(url)
        except ImportError:
            try:
                from coditect_crawl.renderers.playwright import render_spa_playwright

                result = render_spa_playwright(url)
            except ImportError:
                pass  # Return Trafilatura result as-is

    return result


async def deep_crawl(
    url: str,
    *,
    max_depth: int = 2,
    max_pages: int = 100,
    spa: bool = False,
) -> list[ExtractionResult]:
    """Crawl a site following links, extracting content from each page.

    Uses Scrapy (Phase 3) for orchestration with Trafilatura extraction.

    Args:
        url: Starting URL for the crawl.
        max_depth: Maximum link-following depth.
        max_pages: Maximum number of pages to crawl.
        spa: Enable Playwright rendering for JS-heavy pages.

    Returns:
        List of ExtractionResult objects, one per crawled page.
    """
    from coditect_crawl.orchestrators.scrapy_spider import run_deep_crawl

    return await run_deep_crawl(
        url, max_depth=max_depth, max_pages=max_pages, spa=spa
    )
