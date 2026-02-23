"""Phase 1: Trafilatura-based HTML extraction.

Converts raw HTML to LLM-optimized markdown using Trafilatura.
Apache-2.0, 17 dependencies, ~25 MB install.
"""

from __future__ import annotations

import re

import trafilatura

from coditect_crawl.utils.models import ExtractionResult, Link, PageMetadata


def extract_with_trafilatura(
    url: str,
    *,
    html: str | None = None,
) -> ExtractionResult:
    """Extract content from a URL or HTML using Trafilatura.

    Args:
        url: The page URL (used for metadata and link resolution).
        html: Optional pre-fetched HTML string. If None, Trafilatura fetches the URL.

    Returns:
        ExtractionResult with markdown content, metadata, and links.
    """
    if html is None:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return ExtractionResult(url=url, fetch_method="trafilatura-failed")
        html = downloaded

    markdown = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        include_images=True,
        favor_recall=True,
    ) or ""

    metadata = _extract_metadata(html, url)
    metadata.word_count = len(markdown.split())
    links = _extract_links(html, url)

    return ExtractionResult(
        url=url,
        markdown=markdown,
        metadata=metadata,
        links=links,
        fetch_method="trafilatura",
        raw_html=html,
    )


def _extract_metadata(html: str, url: str) -> PageMetadata:
    """Extract page metadata using Trafilatura."""
    meta = trafilatura.extract_metadata(html, default_url=url)
    if meta is None:
        return PageMetadata(url=url)

    return PageMetadata(
        title=meta.title or "",
        author=meta.author or "",
        date=str(meta.date) if meta.date else "",
        description=meta.description or "",
        sitename=meta.sitename or "",
        url=url,
        language=meta.pagetype or "",
    )


def _extract_links(html: str, base_url: str) -> list[Link]:
    """Extract links from HTML with context."""
    from urllib.parse import urljoin, urlparse

    links = []
    base_domain = urlparse(base_url).netloc

    for match in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL):
        href, text = match.group(1), match.group(2)
        text = re.sub(r"<[^>]+>", "", text).strip()

        if href.startswith(("#", "javascript:", "mailto:")):
            continue

        full_url = urljoin(base_url, href)
        is_internal = urlparse(full_url).netloc == base_domain

        links.append(Link(url=full_url, text=text, is_internal=is_internal))

    return links
