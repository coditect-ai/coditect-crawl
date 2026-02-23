"""Phase 2 fallback: Direct Playwright rendering + Trafilatura extraction.

Hot-swap fallback when Crawl4AI is unavailable or fails. Uses Playwright
directly for JS rendering, then pipes the rendered HTML through Trafilatura
for markdown extraction.

This eliminates the Crawl4AI single-maintainer bus factor risk (ADR-215).

Requires: pip install playwright && playwright install chromium
License: Apache-2.0 (Playwright is Microsoft-maintained)
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlparse

from coditect_crawl.utils.models import ExtractionResult, Link, PageMetadata


def render_spa_playwright(url: str, *, timeout: int = 30000) -> ExtractionResult:
    """Render a JavaScript SPA page using Playwright directly.

    Launches a headless Chromium browser, navigates to the URL, waits for
    network idle, then extracts the rendered HTML. Pipes through Trafilatura
    for markdown conversion.

    Args:
        url: The URL to render and extract.
        timeout: Page load timeout in milliseconds (default: 30s).

    Returns:
        ExtractionResult with rendered markdown content.

    Raises:
        ImportError: If playwright is not installed.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(_render_playwright_async(url, timeout=timeout))
            ).result()
    else:
        return asyncio.run(_render_playwright_async(url, timeout=timeout))


async def _render_playwright_async(
    url: str, *, timeout: int = 30000
) -> ExtractionResult:
    """Async implementation: Playwright render + Trafilatura extract.

    Args:
        url: The URL to render.
        timeout: Page load timeout in milliseconds.

    Returns:
        ExtractionResult with rendered content.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            page = await context.new_page()

            await page.goto(url, wait_until="networkidle", timeout=timeout)

            # Wait a bit for any lazy-loaded content
            await page.wait_for_timeout(1000)

            # Get the fully rendered HTML
            rendered_html = await page.content()
            title = await page.title() or url

            await context.close()
        finally:
            await browser.close()

    # Extract markdown using Trafilatura on the rendered HTML
    markdown = ""
    metadata = PageMetadata(title=title, url=url)

    try:
        import trafilatura

        markdown = trafilatura.extract(
            rendered_html,
            url=url,
            output_format="markdown",
            include_links=True,
            include_tables=True,
            include_images=True,
            favor_recall=True,
        ) or ""

        # Extract metadata from rendered page
        meta = trafilatura.extract_metadata(rendered_html, default_url=url)
        if meta:
            metadata = PageMetadata(
                title=meta.title or title,
                author=meta.author or "",
                date=str(meta.date) if meta.date else "",
                description=meta.description or "",
                sitename=meta.sitename or "",
                url=url,
                language=meta.pagetype or "",
                word_count=len(markdown.split()),
            )
        else:
            metadata.word_count = len(markdown.split())
    except ImportError:
        # Trafilatura not available — use basic regex extraction
        from coditect_crawl.extractors.fallback import extract_with_fallback

        fallback_result = extract_with_fallback(url, html=rendered_html)
        markdown = fallback_result.markdown
        metadata = fallback_result.metadata or metadata
        metadata.word_count = len(markdown.split())

    # Extract links from rendered HTML
    links = _extract_links_from_html(rendered_html, url)

    return ExtractionResult(
        url=url,
        markdown=markdown,
        metadata=metadata,
        links=links,
        fetch_method="playwright-direct",
        raw_html=rendered_html,
    )


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
