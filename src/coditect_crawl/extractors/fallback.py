"""Fallback HTML-to-markdown extractor using stdlib only.

Ported from coditect-core/skills/web-crawler/scripts/dashboard_server.py SimpleHTMLToText.
Used when Trafilatura is unavailable or fails.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from coditect_crawl.utils.models import ExtractionResult, Link, PageMetadata


class SimpleHTMLToText(HTMLParser):
    """Minimal HTML to readable text converter (stdlib only)."""

    SKIP_TAGS = frozenset({"script", "style", "nav", "footer", "header", "noscript"})
    BLOCK_TAGS = frozenset({
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "tr", "blockquote", "pre", "section", "article",
    })

    def __init__(self):
        super().__init__()
        self._result: list[str] = []
        self._skip = False
        self._href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip = True
        if tag in self.BLOCK_TAGS:
            self._result.append("\n")
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._result.append("#" * int(tag[1]) + " ")
        if tag == "li":
            self._result.append("- ")
        if tag == "br":
            self._result.append("\n")
        if tag == "a":
            for name, val in attrs:
                if name == "href" and val:
                    self._result.append("[")
                    self._href = val
                    break

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS:
            self._skip = False
        if tag == "a" and self._href is not None:
            self._result.append(f"]({self._href})")
            self._href = None
        if tag in self.BLOCK_TAGS:
            self._result.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._result.append(data)

    def get_text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self._result)).strip()


def extract_with_fallback(url: str, *, html: str | None = None) -> ExtractionResult:
    """Extract content using stdlib-only HTML parser (no external dependencies).

    This is the fallback when Trafilatura is not installed or fails.

    Args:
        url: The page URL.
        html: Raw HTML content. Required for fallback (no fetch capability).

    Returns:
        ExtractionResult with basic markdown content.
    """
    if html is None:
        return ExtractionResult(url=url, fetch_method="fallback-no-html")

    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = title_match.group(1).strip() if title_match else url

    # Convert HTML to text
    parser = SimpleHTMLToText()
    parser.feed(html)
    markdown = parser.get_text()

    # Extract links
    links = _extract_links_regex(html, url)

    return ExtractionResult(
        url=url,
        markdown=markdown,
        metadata=PageMetadata(
            title=title,
            url=url,
            word_count=len(markdown.split()),
        ),
        links=links,
        fetch_method="fallback-regex",
        raw_html=html,
    )


def _extract_links_regex(html: str, base_url: str) -> list[Link]:
    """Extract links using regex (no dependencies)."""
    from urllib.parse import urljoin, urlparse

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
