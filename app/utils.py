"""Shared utilities."""

import time
import logging
import httpx

from app.config import config

logger = logging.getLogger(__name__)


def fetch_page(url: str, client: httpx.Client | None = None) -> str | None:
    """Fetch a page with rate limiting and error handling."""
    headers = {
        "User-Agent": config.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "az,en;q=0.5",
    }
    try:
        if client:
            resp = client.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        else:
            resp = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        time.sleep(config.request_delay)
        return resp.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def safe_int(value: str | None) -> int | None:
    """Safely parse an integer from a string."""
    if value is None:
        return None
    try:
        return int(value.replace(" ", "").replace("\u00a0", ""))
    except (ValueError, AttributeError):
        return None


def safe_float(value: str | None) -> float | None:
    """Safely parse a float from a string."""
    if value is None:
        return None
    try:
        return float(value.replace(" ", "").replace(",", ".").replace("\u00a0", ""))
    except (ValueError, AttributeError):
        return None
