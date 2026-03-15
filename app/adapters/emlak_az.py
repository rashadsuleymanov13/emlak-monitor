"""Adapter for emlak.az - standard HTML scraping."""

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


class EmlakAzAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "emlak.az"

    @property
    def base_url(self) -> str:
        return "https://emlak.az"

    def _parse_listing_card(self, card, soup_context=None) -> Listing | None:
        """Parse a single listing card element."""
        try:
            # Find the main link
            link = card.find("a", href=True)
            if not link:
                return None

            href = link.get("href", "")
            if not href:
                return None
            if not href.startswith("http"):
                href = urljoin(self.base_url, href)

            # Extract listing ID from URL pattern like /1306873-satilir-...
            listing_id = ""
            id_match = re.search(r'/(\d+)-', href)
            if id_match:
                listing_id = id_match.group(1)

            # Get title
            title_el = card.find("h6") or card.find("h5") or card.find("h4")
            title = ""
            if title_el:
                title_link = title_el.find("a")
                title = title_link.get_text(strip=True) if title_link else title_el.get_text(strip=True)
            if not title:
                img = card.find("img")
                title = img.get("alt", "") if img else link.get_text(strip=True)

            # Get all text content
            text = card.get_text(" ", strip=True)

            # Parse price
            price = None
            price_match = re.search(r'([\d\s.,]+)\s*AZN', text)
            if price_match:
                price = safe_int(price_match.group(1).replace(".", "").replace(",", ""))

            # Parse area from title or text
            area = None
            area_match = re.search(r'(\d+[.,]?\d*)\s*(?:m[²2]|kv)', text, re.IGNORECASE)
            if area_match:
                area = safe_float(area_match.group(1))

            # Parse floor info from "Mərtəbə: X" pattern
            floor, total_floors = None, None
            floor_match = re.search(r'[Mm]ərtəbə[:\s]*(\d+)\s*/?\s*(\d+)?', text)
            if floor_match:
                floor = safe_int(floor_match.group(1))
                total_floors = safe_int(floor_match.group(2)) if floor_match.group(2) else None
            else:
                # Try X/Y pattern
                floor, total_floors = parse_floor_info(text)

            # Parse location from paragraphs
            location = ""
            paragraphs = card.find_all("p")
            for p in paragraphs:
                p_text = p.get_text(strip=True)
                # Skip price and floor paragraphs
                if "AZN" in p_text or "Mərtəbə" in p_text:
                    continue
                if len(p_text) > 5 and not p_text.isdigit():
                    location = p_text
                    break

            # Check document status
            doc_text = text.lower()
            has_title_deed = None
            if "sənəd" in doc_text or "kupça" in doc_text or "çıxarış" in doc_text:
                for p in paragraphs:
                    p_text = p.get_text(strip=True)
                    if "Sənəd" in p_text:
                        if "Kupça" in p_text or "kupça" in p_text or "Çıxarış" in p_text:
                            has_title_deed = True

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
                has_title_deed=has_title_deed if has_title_deed else text_contains_any(text, TITLE_DEED_KEYWORDS) or None,
                is_mortgage_ready=has_mortgage,
                source=self.name,
                raw_text=text,
            )
        except Exception as e:
            logger.debug(f"Error parsing listing card: {e}")
            return None

    def fetch_listings(self) -> List[Listing]:
        """Fetch listings from emlak.az."""
        listings = []
        pages_to_fetch = 3  # First 3 pages

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
                    f"{self.base_url}/elanlar/"
                    f"?ann_type=1&property_type=1&page={page}"
                )
                logger.info(f"Fetching {url}")

                try:
                    resp = client.get(url, timeout=15.0)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"Failed to fetch page {page}: {e}")
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # Try multiple selectors for listing cards
                cards = []

                # Look for common listing container patterns
                for selector in [
                    "div.ticket",
                    "div.announce",
                    "div.item",
                    "div.listing",
                    "div.card",
                    "article",
                    "div.product",
                    "div.ann-item",
                    "div.elan",
                ]:
                    cards = soup.select(selector)
                    if cards:
                        logger.debug(f"Found {len(cards)} cards with selector: {selector}")
                        break

                # If no specific cards found, try finding by link pattern
                if not cards:
                    # Find all links that match listing URL pattern
                    all_links = soup.find_all("a", href=re.compile(r'/\d+-satilir-'))
                    seen_parents = set()
                    for link in all_links:
                        parent = link.parent
                        if parent and id(parent) not in seen_parents:
                            # Walk up to find a reasonable container
                            container = parent
                            for _ in range(3):
                                if container.parent and container.parent.name not in ("body", "html", "[document]"):
                                    container = container.parent
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
