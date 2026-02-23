"""Data models for extraction results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageMetadata:
    """Metadata extracted from a web page."""

    title: str = ""
    author: str = ""
    date: str = ""
    description: str = ""
    sitename: str = ""
    url: str = ""
    content_type: str = "text/html"
    language: str = ""
    word_count: int = 0


@dataclass
class Link:
    """A link extracted from a web page."""

    url: str
    text: str = ""
    context: str = ""
    is_internal: bool = False


@dataclass
class ExtractionResult:
    """Result of extracting content from a web page."""

    url: str
    markdown: str = ""
    metadata: PageMetadata = field(default_factory=PageMetadata)
    links: list[Link] = field(default_factory=list)
    fetch_method: str = "trafilatura"
    raw_html: str = ""

    def is_likely_spa(self) -> bool:
        """Detect if the page is likely a JavaScript SPA with insufficient content."""
        if self.metadata.word_count > 50:
            return False

        spa_markers = [
            "__NEXT_DATA__",
            "react-root",
            "__nuxt",
            "ng-app",
            "ng-version",
            'id="app"',
            'id="root"',
            "window.__INITIAL_STATE__",
        ]
        html_lower = self.raw_html.lower()
        has_marker = any(marker.lower() in html_lower for marker in spa_markers)

        has_noscript = "<noscript" in html_lower
        has_js_bundle = any(
            pattern in html_lower
            for pattern in ["/static/js/main.", "/_next/", "runtime~main", "/chunks/"]
        )

        return has_marker or (has_noscript and has_js_bundle)
