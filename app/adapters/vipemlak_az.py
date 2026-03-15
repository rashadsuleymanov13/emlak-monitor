"""Adapter for vipemlak.az."""

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


class VipemlakAzAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "vipemlak.az"

    @property
    def base_url(self) -> str:
        return "https://vipemlak.az"

    def _parse_card(self, card) -> Listing | None:
        try:
            link = card.find("a", href=True)
            if not link:
                return None
            href = link["href"]
            if not href.startswith("http"):
                href = urljoin(self.base_url, href)

            listing_id = ""
            id_match = re.search(r'-(\d{4,})\.html', href)
            if id_match:
                listing_id = id_match.group(1)
            else:
                id_match = re.search(r'/(\d{4,})', href)
                if id_match:
                    listing_id = id_match.group(1)

            text = card.get_text(" ", strip=True)
            title = ""
            for tag in ["h3", "h4", "h2", "h5"]:
                el = card.find(tag)
                if el:
                    title = el.get_text(strip=True)
                    break
            if not title:
                title = link.get_text(strip=True)

            price = None
            m = re.search(r'([\d\s,.]+)\s*(?:Azn|AZN|azn|₼|manat)', text)
            if m:
                price = safe_int(m.group(1).replace(",", "").replace(".", "").replace(" ", ""))

            area = None
            m = re.search(r'(\d+[.,]?\d*)\s*m[²2]', text, re.IGNORECASE)
            if m:
                area = safe_float(m.group(1))

            floor, total_floors = parse_floor_info(text)

            location = ""
            m = re.search(r'([\wəüöşçğıƏÜÖŞÇĞİ]+\s+rayonu)', text)
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
        urls = [
            f"{self.base_url}/yeni-tikili-satilir",
            f"{self.base_url}/kohne-tikili-satilir",
        ]
        with httpx.Client(
            headers={"User-Agent": config.user_agent, "Accept": "text/html"},
            follow_redirects=True,
        ) as client:
            for url in urls:
                for page in range(1, 3):
                    page_url = f"{url}?page={page}" if page > 1 else url
                    logger.info(f"Fetching {page_url}")
                    try:
                        resp = client.get(page_url, timeout=15.0)
                        resp.raise_for_status()
                    except Exception as e:
                        logger.error(f"Failed: {e}")
                        continue

                    soup = BeautifulSoup(resp.text, "lxml")
                    # Find cards by link pattern
                    card_links = soup.find_all("a", href=re.compile(r'-\d{4,}\.html'))
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
                            if listing and listing.url and "/satilir" not in listing.url or listing.price:
                                listings.append(listing)

                    logger.info(f"Found {len(seen)} cards")
                    time.sleep(config.request_delay)

        logger.info(f"Total from {self.name}: {len(listings)}")
        return listings
