---
title: Readme
type: guide
component_type: guide
version: 1.0.0
audience: contributor
status: draft
summary: Auto-classified guide document
keywords:
- guide
tokens: ~1000
created: '2026-02-23'
updated: '2026-02-23'
tags:
- guide
---
# CODITECT Crawl

Intelligent web content extraction pipeline for the CODITECT `/crawl` skill.

## Architecture

Three-phase layered extraction pipeline:

```
Phase 1: WebFetch → Trafilatura        (static HTML → LLM-optimized markdown)
Phase 2: SPA Detection → Crawl4AI      (JS-rendered pages → markdown)
Phase 3: Scrapy + scrapy-playwright    (bulk/deep crawl orchestration)
```

## Installation

```bash
# Phase 1 only (lightweight, ~25 MB)
pip install coditect-crawl

# Phase 1 + Phase 2 SPA rendering (~500 MB, includes Chromium)
pip install coditect-crawl[spa]

# All phases including deep crawl (~540 MB)
pip install coditect-crawl[all]
```

## Quick Start

```python
from coditect_crawl import extract

# Single page extraction (Phase 1 — Trafilatura)
result = extract("https://example.com")
print(result.markdown)
print(result.metadata.title)
print(result.links)

# SPA extraction (Phase 2 — auto-detects JS need)
result = extract("https://react-spa.example.com", spa=True)

# Deep crawl (Phase 3 — Scrapy orchestration)
from coditect_crawl import deep_crawl

results = deep_crawl("https://docs.example.com", max_depth=2, max_pages=100)
for page in results:
    print(f"{page.url}: {len(page.markdown)} chars")
```

## Project Structure

```
coditect-crawl/
├── src/coditect_crawl/
│   ├── __init__.py           # Public API: extract(), deep_crawl()
│   ├── extractors/           # Phase 1: HTML → markdown
│   │   ├── trafilatura.py    # Trafilatura wrapper
│   │   └── fallback.py       # Regex fallback (current process_page.py logic)
│   ├── renderers/            # Phase 2: JS rendering
│   │   ├── crawl4ai.py       # Crawl4AI AsyncWebCrawler wrapper
│   │   ├── playwright.py     # Direct Playwright fallback
│   │   └── detector.py       # SPA detection heuristic
│   ├── orchestrators/        # Phase 3: Bulk crawling
│   │   ├── scrapy_spider.py  # Scrapy spider + Trafilatura pipeline
│   │   └── settings.py       # Scrapy configuration
│   └── utils/
│       ├── links.py          # Link extraction and categorization
│       └── models.py         # Data models (ExtractionResult, PageMetadata)
├── tests/
│   ├── unit/                 # Unit tests per module
│   ├── integration/          # End-to-end extraction tests
│   └── fixtures/             # HTML fixtures for testing
├── docs/                     # Architecture docs, ADRs
├── scripts/                  # Dev scripts
├── pyproject.toml            # Build config
└── CLAUDE.md                 # AI agent instructions
```

## Design Decisions

- **Trafilatura for extraction**: Best F1 score (0.958), lightest footprint, academic backing
- **Crawl4AI for SPA**: Only tool with native LLM-optimized markdown + Playwright
- **Scrapy for deep crawl**: Gold standard orchestration (59.9k stars, 18 years, BSD-3)
- **Abstraction layers**: Each phase is hot-swappable (e.g., Crawl4AI → Playwright+Trafilatura)

See [analysis document](docs/web-crawler-tool-evaluation-2026-02-23.md) for the full MoE evaluation.

## License

Apache-2.0 — See [LICENSE](LICENSE)

## Author

AZ1.AI INC — [coditect.ai](https://coditect.ai)
