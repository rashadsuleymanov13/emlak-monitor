"""Adapter for evv.az."""

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
from app.normalization import text_contains_any, parse_floor_info, TITLE_DEED_KEYWORDS, MORTGAGE_KEYWORDS
from app.utils import safe_int, safe_float

logger = logging.getLogger(__name__)


class EvvAzAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "evv.az"

    @property
    def base_url(self) -> str:
        return "https://www.evv.az"

    def _parse_card(self, card) -> Listing | None:
        try:
            link = card.find("a", href=True)
            if not link:
                return None
            href = link["href"]
            if not href.startswith("http"):
                href = urljoin(self.base_url, href)

            listing_id = ""
            id_match = re.search(r'-(\d{4,})', href)
            if id_match:
                listing_id = id_match.group(1)

            text = card.get_text(" ", strip=True)
            title = ""
            for tag in ["h3", "h4", "h2"]:
                el = card.find(tag)
                if el:
                    title = el.get_text(strip=True)
                    break
            if not title:
                title = link.get_text(strip=True)

            price = None
            m = re.search(r'([\d\s,.]+)\s*(?:₼|AZN|azn|manat)', text)
            if m:
                price = safe_int(m.group(1).replace(",", "").replace(".", "").replace(" ", ""))

            area = None
            m = re.search(r'(\d+[.,]?\d*)\s*m[²2]', text, re.IGNORECASE)
            if m:
                area = safe_float(m.group(1))

            floor, total_floors = None, None
            m = re.search(r'(\d+)\s*/\s*(\d+)\s*(?:mərtəbə)?', text)
            if m:
                floor, total_floors = safe_int(m.group(1)), safe_int(m.group(2))

            location = ""
            m = re.search(r'([\wəüöşçğıƏÜÖŞÇĞİ]+(?:\s+rayonu)?),?\s*Bakı', text)
            if m:
                location = m.group(1)

            return Listing(
                listing_id=listing_id, url=href, title=title, price=price,
                area=area, floor=floor, total_floors=total_floors, location=location,
                description=text[:500],
                has_title_deed=text_contains_any(text, TITLE_DEED_KEYWORDS) or None,
                is_mortgage_ready=text_contains_any(text, MORTGAGE_KEYWORDS) or None,
                source=self.name, raw_text=text,
            )
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def fetch_listings(self) -> List[Listing]:
        listings = []
        with httpx.Client(
            headers={"User-Agent": config.user_agent, "Accept": "text/html"},
            follow_redirects=True,
        ) as client:
            for page in range(1, 4):
                url = f"{self.base_url}/dasinmaz-emlak-satis?type=1&page={page}"
                logger.info(f"Fetching {url}")
                try:
                    resp = client.get(url, timeout=15.0)
                    resp.raise_for_status()
                except Exception as e:
                    logger.error(f"Failed: {e}")
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # Find listing links by pattern
                card_links = soup.find_all("a", href=re.compile(r'otaqli-menzil|menzil.*satis'))
                seen = set()
                for lnk in card_links:
                    container = lnk
                    for _ in range(4):
                        if container.parent and container.parent.name not in ("body", "html", "[document]"):
                            container = container.parent
                        else:
                            break
                    if id(container) not in seen:
                        seen.add(id(container))
                        listing = self._parse_card(container)
                        if listing and listing.url:
                            listings.append(listing)

                # Also try generic card selectors
                if not listings:
                    for sel in [".card", ".listing", ".item", "article"]:
                        cards = soup.select(sel)
                        if cards:
                            for c in cards:
                                listing = self._parse_card(c)
                                if listing and listing.url:
                                    listings.append(listing)
                            break

                logger.info(f"Page {page}: {len(listings)} total")
                time.sleep(config.request_delay)

        logger.info(f"Total from {self.name}: {len(listings)}")
        return listings
