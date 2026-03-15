"""Adapter for binatap.az - HTML scraping."""

import re
import logging
import time
from typing import List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter
from app.models import Listing
from app.config import config
from app.normalization import (
    text_contains_any,
    parse_floor_info,
    TITLE_DEED_KEYWORDS,
    MORTGAGE_KEYWORDS,
)
from app.utils import safe_int, safe_float

logger = logging.getLogger(__name__)


class BinatapAzAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "binatap.az"

    @property
    def base_url(self) -> str:
        return "https://binatap.az"

    def _parse_listing_card(self, card) -> Listing | None:
        """Parse a single listing card from binatap.az."""
        try:
            # Find link
            link = card.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")
            if not href:
                return None
            if not href.startswith("http"):
                href = urljoin(self.base_url, href)

            # Extract listing ID from URL pattern like _i78
            listing_id = ""
            id_match = re.search(r'_i(\d+)', href)
            if id_match:
                listing_id = id_match.group(1)
            else:
                # Try /NUMBER pattern
                id_match = re.search(r'/(\d+)(?:\?|$|\.)', href)
                if id_match:
                    listing_id = id_match.group(1)

            # Get title
            title = ""
            title_el = card.find("h3") or card.find("h4") or card.find("h2")
            if title_el:
                title = title_el.get_text(strip=True)
            if not title:
                img = card.find("img")
                title = img.get("alt", "") if img else link.get_text(strip=True)

            # Get all text
            text = card.get_text(" ", strip=True)

            # Parse price - look for .price element first
            price = None
            price_el = card.find(class_="price")
            if price_el:
                price_text = price_el.get_text(strip=True)
                price_match = re.search(r'([\d\s]+)', price_text)
                if price_match:
                    price = safe_int(price_match.group(1))
            else:
                price_match = re.search(r'([\d\s.,]+)\s*AZN', text)
                if price_match:
                    price = safe_int(price_match.group(1).replace(".", "").replace(",", ""))

            # Parse area - look for kv.m pattern
            area = None
            area_match = re.search(r'(\d+[.,]?\d*)\s*(?:kv\.?\s*m|m[²2])', text, re.IGNORECASE)
            if area_match:
                area = safe_float(area_match.group(1))

            # Parse floor info - "Mərtəbə: 19/16" pattern
            floor, total_floors = None, None
            floor_match = re.search(r'[Mm]ərtəbə[:\s]*(\d+)\s*/\s*(\d+)', text)
            if floor_match:
                floor = safe_int(floor_match.group(1))
                total_floors = safe_int(floor_match.group(2))
            else:
                floor, total_floors = parse_floor_info(text)

            # Parse location
            location = ""
            loc_el = card.find(class_="location")
            if loc_el:
                location = loc_el.get_text(strip=True)

            # Title deed and mortgage
            has_title_deed = text_contains_any(text, TITLE_DEED_KEYWORDS) or None
            has_mortgage = text_contains_any(text, MORTGAGE_KEYWORDS) or None

            return Listing(
                listing_id=listing_id,
                url=href,
                title=title,
                price=price,
                area=area,
                floor=floor,
                total_floors=total_floors,
                location=location,
                description=text[:500],
                has_title_deed=has_title_deed,
                is_mortgage_ready=has_mortgage,
                source=self.name,
                raw_text=text,
            )
        except Exception as e:
            logger.debug(f"Error parsing binatap card: {e}")
            return None

    def fetch_listings(self) -> List[Listing]:
        """Fetch listings from binatap.az."""
        listings = []

        with httpx.Client(
            headers={
                "User-Agent": config.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "az,en;q=0.5",
            },
            follow_redirects=True,
        ) as client:
            # Try multiple URL patterns for binatap.az
            urls_to_try = [
                f"{self.base_url}/search?type=sale&category=apartment",
                f"{self.base_url}/elanlar?tip=satilir&kateqoriya=menzil",
                f"{self.base_url}/mənzil",
                f"{self.base_url}/search",
                self.base_url,
            ]

            fetched_url = None
            soup = None

            for url in urls_to_try:
                try:
                    logger.info(f"Trying {url}")
                    resp = client.get(url, timeout=15.0)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "lxml")
                        # Check if page has listing content
                        if soup.find(class_="simple-prod") or soup.find(class_="product"):
                            fetched_url = url
                            break
                        # Also check for any listing-like elements
                        listing_links = soup.find_all("a", href=re.compile(r'_i\d+'))
                        if listing_links:
                            fetched_url = url
                            break
                    time.sleep(1)
                except Exception as e:
                    logger.debug(f"Failed to fetch {url}: {e}")
                    continue

            if not soup or not fetched_url:
                logger.warning(f"Could not find listing page on {self.name}")
                # Fetch homepage and look for listings there
                try:
                    resp = client.get(self.base_url, timeout=15.0)
                    soup = BeautifulSoup(resp.text, "lxml")
                    fetched_url = self.base_url
                except Exception as e:
                    logger.error(f"Failed to fetch {self.name} homepage: {e}")
                    return []

            logger.info(f"Parsing listings from {fetched_url}")

            # Try .simple-prod cards first (identified from site analysis)
            cards = soup.find_all(class_="simple-prod")
            if not cards:
                cards = soup.find_all(class_="product")
            if not cards:
                cards = soup.find_all(class_="prod-item")
            if not cards:
                # Try finding by link pattern
                all_links = soup.find_all("a", href=re.compile(r'_i\d+|/mənzil/|/apartment/'))
                seen_parents = set()
                for link_el in all_links:
                    parent = link_el.parent
                    for _ in range(3):
                        if parent and parent.parent and parent.parent.name not in ("body", "html"):
                            parent = parent.parent
                        else:
                            break
                    if parent and id(parent) not in seen_parents:
                        seen_parents.add(id(parent))
                        cards.append(parent)

            logger.info(f"Found {len(cards)} listing cards")

            for card in cards:
                listing = self._parse_listing_card(card)
                if listing and listing.url:
                    # Skip sold listings
                    if "satıldı" in (listing.raw_text or "").lower():
                        continue
                    listings.append(listing)

        logger.info(f"Total listings fetched from {self.name}: {len(listings)}")
        return listings
