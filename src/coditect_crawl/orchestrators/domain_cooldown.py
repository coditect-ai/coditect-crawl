"""Domain cooldown tracking across sessions.

Tracks when each domain was last crawled and enforces minimum cooldown
periods between crawl sessions. Persists to a JSON file so cooldowns
survive process restarts.

Usage:
    from coditect_crawl.orchestrators.domain_cooldown import DomainCooldown

    cooldown = DomainCooldown()

    # Check before crawling
    remaining = cooldown.check("docs.example.com")
    if remaining > 0:
        print(f"Domain on cooldown — wait {remaining:.0f}s")

    # Record after crawling
    cooldown.record("docs.example.com", pages=11, got_429=True)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse


# Default cooldown periods (seconds)
DEFAULT_COOLDOWN = 300        # 5 minutes between crawls of same domain
RATE_LIMITED_COOLDOWN = 900   # 15 minutes if we got 429'd
HEAVY_CRAWL_COOLDOWN = 600   # 10 minutes if we crawled 20+ pages


def _default_db_path() -> Path:
    """Default cooldown DB location."""
    data_dir = Path.home() / "PROJECTS" / ".coditect-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "crawl-domain-cooldowns.json"


class DomainCooldown:
    """Track and enforce per-domain crawl cooldowns across sessions."""

    def __init__(self, db_path: Path | None = None):
        self._path = db_path or _default_db_path()
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    @staticmethod
    def _domain(url_or_domain: str) -> str:
        """Normalize to bare domain."""
        if "://" in url_or_domain:
            return urlparse(url_or_domain).netloc
        return url_or_domain

    def check(self, url_or_domain: str) -> float:
        """Check cooldown for a domain.

        Returns:
            Seconds remaining in cooldown (0 if clear to crawl).
        """
        domain = self._domain(url_or_domain)
        entry = self._data.get(domain)
        if not entry:
            return 0.0

        last_crawl = entry.get("last_crawl", 0)
        cooldown = entry.get("cooldown", DEFAULT_COOLDOWN)
        elapsed = time.time() - last_crawl
        remaining = cooldown - elapsed

        return max(0.0, remaining)

    def record(
        self,
        url_or_domain: str,
        *,
        pages: int = 0,
        got_429: bool = False,
    ) -> None:
        """Record a completed crawl and set appropriate cooldown.

        Args:
            url_or_domain: The domain or URL that was crawled.
            pages: Number of pages crawled.
            got_429: Whether we received any 429 responses.
        """
        domain = self._domain(url_or_domain)

        # Determine cooldown based on what happened
        if got_429:
            cooldown = RATE_LIMITED_COOLDOWN
        elif pages >= 20:
            cooldown = HEAVY_CRAWL_COOLDOWN
        else:
            cooldown = DEFAULT_COOLDOWN

        self._data[domain] = {
            "last_crawl": time.time(),
            "cooldown": cooldown,
            "pages": pages,
            "got_429": got_429,
        }
        self._save()

    def clear(self, url_or_domain: str) -> None:
        """Clear cooldown for a domain."""
        domain = self._domain(url_or_domain)
        self._data.pop(domain, None)
        self._save()

    def status(self) -> dict[str, float]:
        """Return all domains with remaining cooldown > 0."""
        now = time.time()
        active = {}
        for domain, entry in self._data.items():
            remaining = entry.get("cooldown", 0) - (now - entry.get("last_crawl", 0))
            if remaining > 0:
                active[domain] = remaining
        return active
