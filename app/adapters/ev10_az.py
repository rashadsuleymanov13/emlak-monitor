"""Adapter for ev10.az - HTML scraping with Material-UI components."""

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


class Ev10AzAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "ev10.az"

    @property
    def base_url(self) -> str:
        return "https://ev10.az"

    def _parse_listing_card(self, card) -> Listing | None:
        """Parse a single listing card from ev10.az."""
        try:
            # Find link to individual listing
            link = card.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")
            if not href:
                return None
            if not href.startswith("http"):
                href = urljoin(self.base_url, href)

            # Extract listing ID from /posting/XXXXX pattern
            listing_id = ""
            id_match = re.search(r'/posting/(\d+)', href)
            if id_match:
                listing_id = id_match.group(1)

            # Get all text content from card
            text = card.get_text(" ", strip=True)

            # Get title - look for h tags or main text element
            title = ""
            for tag in ["h3", "h4", "h2", "h5", "h6"]:
                title_el = card.find(tag)
                if title_el:
                    title = title_el.get_text(strip=True)
                    break
            if not title:
                # Try img alt
                img = card.find("img")
                if img:
                    title = img.get("alt", "")
            if not title:
                title = link.get_text(strip=True)

            # Parse price - "90,000 AZN" pattern
            price = None
            price_match = re.search(r'([\d\s,.]+)\s*AZN', text)
            if price_match:
                price_str = price_match.group(1).replace(",", "").replace(".", "").replace(" ", "")
                price = safe_int(price_str)

            # Parse area - "180m²" or "75 m²" pattern
            area = None
            area_match = re.search(r'(\d+[.,]?\d*)\s*m[²2]', text, re.IGNORECASE)
            if area_match:
                area = safe_float(area_match.group(1))

            # Parse rooms from title - "3 otaqlı" or "3 otaq"
            rooms = None
            rooms_match = re.search(r'(\d+)\s*otaq', text, re.IGNORECASE)
            if rooms_match:
                rooms = safe_int(rooms_match.group(1))

            # Parse floor info
            floor, total_floors = None, None
            floor_match = re.search(r'(\d+)\s*/\s*(\d+)\s*(?:mərtəbə|mertebe)?', text)
            if floor_match:
                floor = safe_int(floor_match.group(1))
                total_floors = safe_int(floor_match.group(2))
            else:
                floor_match = re.search(r'[Mm]ərtəbə[:\s]*(\d+)', text)
                if floor_match:
                    floor = safe_int(floor_match.group(1))

            # Parse location
            location = ""
            # Try to find location from text patterns
            loc_match = re.search(r'(Bakı|Sumqayıt|Xırdalan|[\w]+\s+(?:rayonu|r-nu|r\.))', text)
            if loc_match:
                location = loc_match.group(1)

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
                rooms=rooms,
                location=location,
                description=text[:500],
                has_title_deed=has_title_deed,
                is_mortgage_ready=has_mortgage,
                source=self.name,
                raw_text=text,
            )
        except Exception as e:
            logger.debug(f"Error parsing ev10 card: {e}")
            return None

    def fetch_listings(self) -> List[Listing]:
        """Fetch listings from ev10.az."""
        listings = []
        pages_to_fetch = 3

        with httpx.Client(
            headers={
                "User-Agent": config.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "az,en;q=0.5",
            },
            follow_redirects=True,
        ) as client:
            for page in range(1, pages_to_fetch + 1):
                url = (
                    f"{self.base_url}/elanlar/alqi-satqi/baki/menzil"
                    f"?page_number={page}"
                )
                logger.info(f"Fetching {url}")

                try:
                    resp = client.get(url, timeout=15.0)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"Failed to fetch page {page}: {e}")
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # Find listing cards - try multiple selectors
                cards = []

                # ev10.az uses Material-UI, try common patterns
                # Look for links to /posting/ pages
                posting_links = soup.find_all("a", href=re.compile(r'/posting/\d+'))
                seen_parents = set()
                for link_el in posting_links:
                    # Walk up to find the card container
                    container = link_el
                    for _ in range(5):
                        parent = container.parent
                        if parent and parent.name not in ("body", "html", "[document]"):
                            # Check if parent has multiple children (likely a card)
                            if len(list(parent.children)) > 1:
                                container = parent
                                break
                            container = parent
                        else:
                            break
                    if id(container) not in seen_parents:
                        seen_parents.add(id(container))
                        cards.append(container)

                logger.info(f"Found {len(cards)} listing cards on page {page}")

                for card in cards:
                    listing = self._parse_listing_card(card)
                    if listing and listing.url:
                        listings.append(listing)

                time.sleep(config.request_delay)

        logger.info(f"Total listings fetched from {self.name}: {len(listings)}")
        return listings
