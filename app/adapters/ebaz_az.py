"""Adapter for ebaz.az - React SPA, parse via sitemap and individual pages."""

import re
import json
import logging
import time
from typing import List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter
from app.models import Listing
from app.config import config
from app.normalization import text_contains_any, parse_floor_info, TITLE_DEED_KEYWORDS, MORTGAGE_KEYWORDS
from app.utils import safe_int, safe_float

logger = logging.getLogger(__name__)


class EbazAzAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "ebaz.az"

    @property
    def base_url(self) -> str:
        return "https://ebaz.az"

    def fetch_listings(self) -> List[Listing]:
        """Fetch listings from ebaz.az. Uses search URL with query params."""
        listings = []

        with httpx.Client(
            headers={
                "User-Agent": config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "az,en;q=0.5",
                "Referer": "https://ebaz.az/",
            },
            follow_redirects=True,
        ) as client:
            # ebaz.az URL pattern from sitemap: /?satis=&elan=menzil&seher=Bakı
            url = f"{self.base_url}/?satis=&elan=menzil&seher=Bak%C4%B1"
            logger.info(f"Fetching {url}")

            try:
                resp = client.get(url, timeout=15.0)
                resp.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to fetch {self.name}: {e}")
                return []

            html = resp.text

            # ebaz.az is a React SPA - check if there's embedded data
            # Look for __NEXT_DATA__, window.__data, or similar
            soup = BeautifulSoup(html, "lxml")

            # Try to find embedded JSON state
            for script in soup.find_all("script"):
                text = script.string or ""
                if not text:
                    continue

                # Look for any JSON data with listing info
                for pattern in [
                    r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                    r'window\.__data\s*=\s*({.+?});',
                    r'window\.__PRELOADED_STATE__\s*=\s*({.+?});',
                    r'"posts"\s*:\s*(\[.+?\])',
                    r'"items"\s*:\s*(\[.+?\])',
                    r'"listings"\s*:\s*(\[.+?\])',
                ]:
                    match = re.search(pattern, text, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            items = data if isinstance(data, list) else []
                            if isinstance(data, dict):
                                for key in ["posts", "items", "listings", "data"]:
                                    if key in data and isinstance(data[key], list):
                                        items = data[key]
                                        break
                            for item in items[:100]:
                                if not isinstance(item, dict):
                                    continue
                                lid = str(item.get("id", item.get("_id", "")))
                                listings.append(Listing(
                                    listing_id=lid,
                                    url=item.get("url", f"{self.base_url}/elan/{lid}"),
                                    title=item.get("title", ""),
                                    price=safe_int(str(item.get("price", ""))) if item.get("price") else None,
                                    area=safe_float(str(item.get("area", ""))) if item.get("area") else None,
                                    source=self.name,
                                ))
                            if listings:
                                logger.info(f"Found {len(listings)} from embedded JSON")
                                return listings
                        except (json.JSONDecodeError, TypeError):
                            pass

            # If no embedded data, try to find listing links in HTML
            card_links = soup.find_all("a", href=re.compile(
                r'/elan/menzil|/elan/[a-f0-9]{8}-|/posting/\d+'
            ))
            seen = set()
            for lnk in card_links:
                href = lnk.get("href", "")
                if href in seen:
                    continue
                seen.add(href)
                if not href.startswith("http"):
                    href = urljoin(self.base_url, href)

                container = lnk
                for _ in range(4):
                    if container.parent and container.parent.name not in ("body", "html", "[document]"):
                        container = container.parent
                    else:
                        break

                text = container.get_text(" ", strip=True)
                id_match = re.search(r'([a-f0-9-]{36}|\d{4,})', href)
                lid = id_match.group(1) if id_match else ""

                price = None
                m = re.search(r'([\d\s,.]+)\s*(?:AZN|₼)', text)
                if m:
                    price = safe_int(m.group(1).replace(" ", "").replace(",", ""))

                area = None
                m = re.search(r'(\d+[.,]?\d*)\s*m[²2]', text, re.IGNORECASE)
                if m:
                    area = safe_float(m.group(1))

                listings.append(Listing(
                    listing_id=lid, url=href,
                    title=lnk.get_text(strip=True),
                    price=price, area=area,
                    has_title_deed=text_contains_any(text, TITLE_DEED_KEYWORDS) or None,
                    source=self.name, raw_text=text[:500],
                ))

            if listings:
                logger.info(f"Found {len(listings)} from HTML links")
            else:
                logger.warning(f"{self.name} is a React SPA, no data accessible without JS")

        logger.info(f"Total from {self.name}: {len(listings)}")
        return listings
