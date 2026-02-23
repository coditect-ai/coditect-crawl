"""Phase 2: Crawl4AI SPA rendering.

Uses Crawl4AI's AsyncWebCrawler (Playwright-based) to render JavaScript-heavy
pages and extract LLM-optimized markdown. Activated when SPA detection heuristic
triggers (low word count + JS framework markers).

Requires: pip install coditect-crawl[spa]
License: Apache-2.0
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlparse

from coditect_crawl.utils.models import ExtractionResult, Link, PageMetadata


def render_spa(url: str, *, timeout: int = 30000) -> ExtractionResult:
    """Render a JavaScript SPA page and extract content.

    Synchronous wrapper around the async Crawl4AI pipeline.
    Uses Playwright (Chromium) to execute JavaScript, then extracts
    LLM-optimized markdown via Crawl4AI's built-in extractor.

    Args:
        url: The URL to render and extract.
        timeout: Page load timeout in milliseconds (default: 30s).

    Returns:
        ExtractionResult with rendered markdown content.

    Raises:
        ImportError: If crawl4ai is not installed.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an async context — use nest_asyncio or run in thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(_render_spa_async(url, timeout=timeout))).result()
    else:
        return asyncio.run(_render_spa_async(url, timeout=timeout))


async def _render_spa_async(url: str, *, timeout: int = 30000) -> ExtractionResult:
    """Async implementation of SPA rendering via Crawl4AI.

    Args:
        url: The URL to render.
        timeout: Page load timeout in milliseconds.

    Returns:
        ExtractionResult with rendered content.
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

    browser_config = BrowserConfig(
        headless=True,
        browser_type="chromium",
    )

    run_config = CrawlerRunConfig(
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "header", "aside", "noscript"],
        page_timeout=timeout,
        wait_until="networkidle",
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

        if not result.success:
            return ExtractionResult(
                url=url,
                fetch_method="crawl4ai-failed",
            )

        markdown = result.markdown or ""
        raw_html = result.html or ""

        # Extract metadata from Crawl4AI result
        meta_dict = result.metadata or {}
        metadata = PageMetadata(
            title=meta_dict.get("title", "") or _extract_title(raw_html, url),
            description=meta_dict.get("description", ""),
            language=meta_dict.get("language", ""),
            url=url,
            word_count=len(markdown.split()),
        )

        # Extract links from rendered HTML
        links = _extract_links_from_html(raw_html, url)

        return ExtractionResult(
            url=url,
            markdown=markdown,
            metadata=metadata,
            links=links,
            fetch_method="crawl4ai-playwright",
            raw_html=raw_html,
        )


def _extract_title(html: str, url: str) -> str:
    """Extract title from HTML as fallback."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return match.group(1).strip() if match else url


def _extract_links_from_html(html: str, base_url: str) -> list[Link]:
    """Extract links from rendered HTML."""
    links = []
    base_domain = urlparse(base_url).netloc

    for match in re.finditer(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL
    ):
        href, text = match.group(1), match.group(2)
        text = re.sub(r"<[^>]+>", "", text).strip()

        if href.startswith(("#", "javascript:", "mailto:")):
            continue

        full_url = urljoin(base_url, href)
        is_internal = urlparse(full_url).netloc == base_domain

        links.append(Link(url=full_url, text=text, is_internal=is_internal))

    return links
