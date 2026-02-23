# CODITECT Crawl — AI Agent Instructions

## Project Overview

`coditect-crawl` is the extraction pipeline library for the CODITECT `/crawl` skill. It provides a 3-phase layered architecture for converting web pages to LLM-optimized markdown.

## Architecture

```
Phase 1: Trafilatura    → Static HTML extraction (default, always available)
Phase 2: Crawl4AI       → SPA/JS rendering (optional, activated by detection heuristic)
Phase 3: Scrapy         → Bulk/deep crawl orchestration (optional, for --deep mode)
```

## Key Files

| File | Purpose |
|------|---------|
| `src/coditect_crawl/__init__.py` | Public API: `extract()`, `deep_crawl()` |
| `src/coditect_crawl/extractors/trafilatura.py` | Phase 1 extraction wrapper |
| `src/coditect_crawl/renderers/crawl4ai.py` | Phase 2 SPA rendering |
| `src/coditect_crawl/renderers/detector.py` | SPA detection heuristic |
| `src/coditect_crawl/orchestrators/scrapy_spider.py` | Phase 3 deep crawl |
| `pyproject.toml` | Dependencies and build config |

## Development

```bash
# Install in dev mode with all extras
pip install -e ".[all,dev]"

# Run tests
pytest tests/

# Run just Phase 1 tests (no browser deps)
pytest tests/ -m "not spa and not deep"
```

## Design Principles

1. **Graceful degradation**: If Crawl4AI unavailable, fall back to Playwright+Trafilatura. If Playwright unavailable, fall back to Trafilatura only.
2. **Minimal defaults**: `pip install coditect-crawl` gets Phase 1 only (~25 MB). SPA and deep crawl are optional extras.
3. **Hot-swappable**: Each phase uses an abstraction layer allowing tool replacement without API changes.
4. **Integration target**: This library is consumed by `coditect-core/skills/web-crawler/`. The `/crawl` command invokes functions from this package.

## Testing

- Unit tests: mock HTML → verify markdown output
- Integration tests: real URLs → verify extraction quality
- Fixtures in `tests/fixtures/` — HTML snapshots for deterministic testing
- Mark SPA tests with `@pytest.mark.spa` and deep crawl with `@pytest.mark.deep`

## Conventions

- Python 3.10+
- Type hints on all public functions
- Async API for SPA rendering and deep crawl
- Sync API for Phase 1 extraction
- All extractors return `ExtractionResult` dataclass
