# CODITECT Crawl — Project Plan

**Project:** coditect-crawl
**Repository:** https://github.com/coditect-ai/coditect-crawl
**Track:** H.17.7 (Framework Autonomy — Crawler Tool Integration)
**Status:** In Progress
**Created:** 2026-02-23
**Owner:** AZ1.AI INC

---

## Overview

Major enhancement to the CODITECT `/crawl` command. Replaces the current stdlib-only HTML extraction with a professional 3-phase pipeline using best-in-class open-source tools selected through a full MoE evaluation (3 experts, 4 judges, Bronze quality gate passed at 7.6/10).

**Analysis:** [web-crawler-tool-evaluation-2026-02-23.md](web-crawler-tool-evaluation-2026-02-23.md)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CODITECT /crawl Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   URL ──► WebFetch / httpx                                       │
│              │                                                    │
│              ▼                                                    │
│   ┌─────────────────────┐     ┌──────────────────────────┐      │
│   │  Phase 1: Trafilatura│     │  SPA Detection Heuristic │      │
│   │  (always runs first) │────►│  word_count < 50?        │      │
│   │  Apache-2.0, 17 deps │     │  JS framework markers?   │      │
│   │  ~25 MB              │     │  noscript + bundle?      │      │
│   └─────────┬───────────┘     └──────────┬───────────────┘      │
│             │                             │                       │
│             │ sufficient content          │ SPA detected          │
│             ▼                             ▼                       │
│   ┌─────────────────────┐     ┌──────────────────────────┐      │
│   │  ExtractionResult    │     │  Phase 2: Crawl4AI       │      │
│   │  • markdown          │     │  (Playwright rendering)   │      │
│   │  • metadata          │     │  Apache-2.0, 90+ deps    │      │
│   │  • links             │     │  ~500 MB                  │      │
│   └─────────────────────┘     │  Fallback: Playwright     │      │
│                                │  direct + Trafilatura     │      │
│                                └──────────┬───────────────┘      │
│                                           │                       │
│                                           ▼                       │
│                                ┌──────────────────────────┐      │
│                                │  ExtractionResult         │      │
│                                └──────────────────────────┘      │
│                                                                  │
│   ═══════════════════════════════════════════════════════════    │
│                                                                  │
│   /crawl --deep                                                  │
│              │                                                    │
│              ▼                                                    │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Phase 3: Scrapy + scrapy-playwright                     │   │
│   │  • Request scheduling, dedup, rate limiting               │   │
│   │  • Concurrent page fetching                               │   │
│   │  • Trafilatura Item Pipeline for extraction               │   │
│   │  • scrapy-playwright for JS-heavy pages                   │   │
│   │  BSD-3-Clause, 36 deps, ~40 MB (+Playwright)             │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phases & Tasks

### Phase 1: Trafilatura Integration (Priority: P0)

**Goal:** Replace SimpleHTMLToText with Trafilatura for superior markdown extraction.
**Dependency:** `trafilatura>=2.0.0` (Apache-2.0, 17 deps, ~25 MB)
**Effort:** 1 day

| Task | Description | Status |
|------|-------------|--------|
| H.17.7.1.1 | Create `pyproject.toml` with Trafilatura dependency | [x] |
| H.17.7.1.2 | Create package structure (`src/coditect_crawl/`) | [x] |
| H.17.7.1.3 | Implement `extractors/trafilatura.py` — wrap `trafilatura.extract()` with markdown output | [x] |
| H.17.7.1.4 | Implement `extractors/fallback.py` — port current regex extraction as fallback | [ ] |
| H.17.7.1.5 | Implement `utils/models.py` — ExtractionResult, PageMetadata, Link dataclasses | [x] |
| H.17.7.1.6 | Implement `utils/links.py` — link extraction and categorization (port from categorize_links.py) | [ ] |
| H.17.7.1.7 | Implement public API in `__init__.py` — `extract()` function | [x] |
| H.17.7.1.8 | Write unit tests for Trafilatura extraction | [ ] |
| H.17.7.1.9 | Create HTML fixtures for deterministic testing | [ ] |
| H.17.7.1.10 | Extraction quality benchmark — 10 URLs comparing old vs new | [ ] |
| H.17.7.1.11 | Wire into `/crawl` skill — update `process_page.py` to use `coditect_crawl.extract()` | [ ] |

### Phase 2: Crawl4AI SPA Rendering (Priority: P1)

**Goal:** Add JavaScript rendering for SPA pages that Trafilatura cannot extract.
**Dependency:** `crawl4ai>=0.8.0` (Apache-2.0, 90+ deps, ~500 MB with Chromium)
**Effort:** 1 day

| Task | Description | Status |
|------|-------------|--------|
| H.17.7.2.1 | Implement `renderers/detector.py` — SPA detection heuristic | [x] (in models.py) |
| H.17.7.2.2 | Implement `renderers/crawl4ai.py` — AsyncWebCrawler wrapper | [ ] |
| H.17.7.2.3 | Implement `renderers/playwright.py` — direct Playwright fallback | [ ] |
| H.17.7.2.4 | Integrate SPA cascade in `__init__.py` — Trafilatura → detect → Crawl4AI → Playwright | [x] |
| H.17.7.2.5 | Write SPA detection unit tests with fixture HTML | [ ] |
| H.17.7.2.6 | Integration test: extract az1.ai (React SPA) | [ ] |
| H.17.7.2.7 | Update dashboard to show rendering method | [ ] |

### Phase 3: Scrapy Deep Crawl (Priority: P2)

**Goal:** Replace sequential WebFetch loop with Scrapy for `/crawl --deep` mode.
**Dependency:** `scrapy>=2.14.0`, `scrapy-playwright>=0.0.44` (BSD-3-Clause, 36 deps)
**Effort:** 1 day

| Task | Description | Status |
|------|-------------|--------|
| H.17.7.3.1 | Implement `orchestrators/scrapy_spider.py` — spider + Trafilatura pipeline | [ ] |
| H.17.7.3.2 | Implement `orchestrators/settings.py` — Scrapy config with scrapy-playwright | [ ] |
| H.17.7.3.3 | Implement `deep_crawl()` async API in `__init__.py` | [x] (stub) |
| H.17.7.3.4 | Feed output into session state and categorization pipeline | [ ] |
| H.17.7.3.5 | Integration test: deep crawl a documentation site | [ ] |
| H.17.7.3.6 | Update `/crawl --deep` command flow | [ ] |

### Phase 4: Integration & Documentation (Priority: P1)

**Goal:** Wire coditect-crawl into coditect-core `/crawl` skill and update all docs.

| Task | Description | Status |
|------|-------------|--------|
| H.17.7.4.1 | Update `skills/web-crawler/SKILL.md` to v3.0.0 | [ ] |
| H.17.7.4.2 | Update `skills/web-crawler/references/system-prompt.md` | [ ] |
| H.17.7.4.3 | Update `commands/crawl.md` with `--deep` mode | [ ] |
| H.17.7.4.4 | Update component-counts.json | [ ] |
| H.17.7.4.5 | Create ADR for crawler tool selection | [ ] |
| H.17.7.4.6 | CI/CD — GitHub Actions for pytest on push | [ ] |
| H.17.7.4.7 | First tagged release (v0.1.0) | [ ] |

---

## Tool Selection Summary

| Phase | Tool | License | Deps | Why |
|-------|------|---------|:---:|-----|
| 1 | **Trafilatura** | Apache-2.0 | 17 | Best F1 (0.958), lightest, academic backing |
| 2 | **Crawl4AI** | Apache-2.0 | 90+ | Native LLM markdown + Playwright rendering |
| 2 (fallback) | **Playwright** | Apache-2.0 | — | Microsoft-backed, eliminates Crawl4AI bus factor |
| 3 | **Scrapy** | BSD-3-Clause | 36 | Gold standard (59.9k stars, 594 contributors, 18 years) |
| — | ~~crawlee-python~~ | Apache-2.0 | 32 | Rejected: no markdown output, over-engineered for single-page |
| — | ~~Spider~~ | MIT | — | Rejected: Rust binary, harder Python integration than Scrapy |
| — | ~~Jina Reader~~ | Apache-2.0 | — | Rejected: Elastic acquisition relicense risk |
| — | ~~Firecrawl~~ | AGPL-3.0 | — | Excluded: license incompatible |

---

## License Compliance

All dependencies verified clean via `pip-licenses` scan (2026-02-23):

| Tool | GPL | AGPL | LGPL | Notes |
|------|:---:|:---:|:---:|-------|
| Trafilatura (17 deps) | 0 | 0 | 0 | `tld` is tri-licensed, choose MPL-1.1 |
| Crawl4AI (90+ deps) | 0 | 0 | 1 | `chardet` LGPLv2+ — weak copyleft, safe for import |
| Scrapy (36 deps) | 0 | 0 | 0 | All BSD/MIT/Apache/ZPL |

---

## Success Criteria

- [ ] `coditect_crawl.extract(url)` returns markdown superior to current regex extraction
- [ ] SPA detection correctly identifies React/Vue/Angular pages
- [ ] `coditect_crawl.deep_crawl(url)` crawls 100+ pages with dedup and rate limiting
- [ ] `/crawl` command transparently uses coditect-crawl pipeline
- [ ] All tests pass in CI
- [ ] v0.1.0 tagged and released

---

**Author:** AZ1.AI INC
**MoE Evaluation:** Bronze Quality Gate (7.6/10) — 3 experts, 4 judges
