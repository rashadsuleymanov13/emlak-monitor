"""Adapter for ebaz.az - React SPA, tries HTML parsing."""

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

    def _try_api(self, client: httpx.Client) -> List[Listing]:
        """Try to find and use a REST/JSON API."""
        listings = []
        # Common API patterns for React SPAs
        api_urls = [
            f"{self.base_url}/api/posts?category=apartment&type=sale&page=1",
            f"{self.base_url}/api/v1/posts?category=1&type=1",
            f"{self.base_url}/api/listings?type=sale",
            f"{self.base_url}/api/announcements?type=1&category=1",
        ]
        for api_url in api_urls:
            try:
                resp = client.get(api_url, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        # Try common keys
                        for key in ["data", "items", "posts", "results", "listings", "announcements"]:
                            if key in data and isinstance(data[key], list):
                                items = data[key]
                                break
                        if not items and "data" in data and isinstance(data["data"], dict):
                            for key in ["items", "posts", "results"]:
                                if key in data["data"] and isinstance(data["data"][key], list):
                                    items = data["data"][key]
                                    break

                    if items:
                        logger.info(f"Found API at {api_url} with {len(items)} items")
                        for item in items[:100]:
                            if not isinstance(item, dict):
                                continue
                            lid = str(item.get("id", ""))
                            url = item.get("url", "") or item.get("link", "")
                            if not url and lid:
                                url = f"{self.base_url}/elan/{lid}"
                            title = item.get("title", "") or item.get("name", "")
                            price = safe_int(str(item.get("price", ""))) if item.get("price") else None
                            area = safe_float(str(item.get("area", "") or item.get("square", ""))) if (item.get("area") or item.get("square")) else None
                            location = item.get("location", "") or item.get("address", "") or item.get("region", "")
                            if isinstance(location, dict):
                                location = location.get("name", "")

                            listings.append(Listing(
                                listing_id=lid, url=url, title=title, price=price,
                                area=area, location=str(location),
                                floor=safe_int(str(item.get("floor", ""))) if item.get("floor") else None,
                                total_floors=safe_int(str(item.get("total_floor", "") or item.get("floor_count", ""))) if (item.get("total_floor") or item.get("floor_count")) else None,
                                has_title_deed=item.get("document") or text_contains_any(str(item), TITLE_DEED_KEYWORDS) or None,
                                is_mortgage_ready=text_contains_any(str(item), MORTGAGE_KEYWORDS) or None,
                                source=self.name, raw_text=str(item)[:500],
                            ))
                        return listings
            except Exception:
                continue
        return []

    def _try_html(self, client: httpx.Client) -> List[Listing]:
        """Fallback HTML parsing."""
        listings = []
        urls_to_try = [
            f"{self.base_url}/elanlar/menzil/satilir",
            f"{self.base_url}/elanlar?category=menzil&type=satilir",
            f"{self.base_url}/search?type=sale&category=apartment",
            self.base_url,
        ]
        for url in urls_to_try:
            try:
                resp = client.get(url, timeout=15.0)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")

                # Check for embedded JSON data
                for script in soup.find_all("script"):
                    if script.string and ("listings" in script.string or "posts" in script.string):
                        # Try to extract JSON
                        json_match = re.search(r'(?:listings|posts|items)\s*[=:]\s*(\[.+?\]);', script.string, re.DOTALL)
                        if json_match:
                            try:
                                items = json.loads(json_match.group(1))
                                for item in items[:100]:
                                    if isinstance(item, dict):
                                        lid = str(item.get("id", ""))
                                        listings.append(Listing(
                                            listing_id=lid,
                                            url=item.get("url", f"{self.base_url}/elan/{lid}"),
                                            title=item.get("title", ""),
                                            price=safe_int(str(item.get("price", ""))) if item.get("price") else None,
                                            area=safe_float(str(item.get("area", ""))) if item.get("area") else None,
                                            source=self.name,
                                        ))
                                if listings:
                                    return listings
                            except json.JSONDecodeError:
                                pass

                # Try finding listing links
                card_links = soup.find_all("a", href=re.compile(r'/elan/\d+|/posting/\d+|/item/\d+'))
                if card_links:
                    seen = set()
                    for lnk in card_links:
                        href = lnk["href"]
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
                        id_match = re.search(r'/(\d+)', href)
                        lid = id_match.group(1) if id_match else ""
                        price_m = re.search(r'([\d\s,.]+)\s*(?:AZN|₼)', text)
                        area_m = re.search(r'(\d+[.,]?\d*)\s*m[²2]', text, re.IGNORECASE)
                        listings.append(Listing(
                            listing_id=lid, url=href, title=lnk.get_text(strip=True),
                            price=safe_int(price_m.group(1).replace(" ", "")) if price_m else None,
                            area=safe_float(area_m.group(1)) if area_m else None,
                            source=self.name, raw_text=text[:500],
                        ))
                    if listings:
                        return listings

            except Exception as e:
                logger.debug(f"HTML parse failed for {url}: {e}")
                continue
        return []

    def fetch_listings(self) -> List[Listing]:
        with httpx.Client(
            headers={"User-Agent": config.user_agent, "Accept": "text/html,application/json"},
            follow_redirects=True,
        ) as client:
            # Try API first (React SPA)
            listings = self._try_api(client)
            if listings:
                logger.info(f"Got {len(listings)} from API")
                return listings

            # Fallback to HTML
            listings = self._try_html(client)
            logger.info(f"Total from {self.name}: {len(listings)}")
            return listings
