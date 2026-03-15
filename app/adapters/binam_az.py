"""Adapter for binam.az."""

import re
import logging
import time
from typing import List
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter
from app.models import Listing
from app.config import config
from app.normalization import text_contains_any, parse_floor_info, TITLE_DEED_KEYWORDS, MORTGAGE_KEYWORDS
from app.utils import safe_int, safe_float

logger = logging.getLogger(__name__)


class BinamAzAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "binam.az"

    @property
    def base_url(self) -> str:
        return "https://binam.az"

    def _parse_card(self, card) -> Listing | None:
        try:
            link = card.find("a", href=True)
            if not link:
                # Card itself might be the link
                if card.name == "a" and card.get("href"):
                    link = card
                else:
                    return None

            href = link["href"]
            if not href.startswith("http"):
                href = urljoin(self.base_url, href)

            # ID from /items/499369-...
            listing_id = ""
            id_match = re.search(r'/items/(\d+)', href)
            if id_match:
                listing_id = id_match.group(1)

            text = card.get_text(" ", strip=True)
            title = ""
            h = card.find("h3") or card.find("h4") or card.find("h2")
            if h:
                title = h.get_text(strip=True)
            if not title:
                img = card.find("img")
                title = img.get("alt", "") if img else link.get_text(strip=True)

            price = None
            m = re.search(r'([\d\s,.]+)\s*(?:AZN|azn|₼)', text)
            if m:
                price = safe_int(m.group(1).replace(",", "").replace(".", "").replace(" ", ""))

            area = None
            m = re.search(r'(\d+[.,]?\d*)\s*m[²2]', text, re.IGNORECASE)
            if m:
                area = safe_float(m.group(1))

            floor, total_floors = parse_floor_info(text)

            location = ""
            # "Bakı / Yasamal" pattern
            m = re.search(r'Bakı\s*/\s*([\wəüöşçğıƏÜÖŞÇĞİ\s]+)', text)
            if m:
                location = m.group(1).strip()
            else:
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
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "linux", "mobile": False},
        )
        for page in range(1, 4):
            url = f"{self.base_url}/items?item_type_id=1&estate_type_id=1&page={page}"
            logger.info(f"Fetching {url}")
            try:
                resp = scraper.get(url, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                logger.error(f"Failed: {e}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # binam.az uses <a href="/items/XXXXX"> as card containers
            card_links = soup.find_all("a", href=re.compile(r'/items/\d+'))
            seen_ids = set()
            for lnk in card_links:
                href = lnk["href"]
                id_match = re.search(r'/items/(\d+)', href)
                lid = id_match.group(1) if id_match else href
                if lid in seen_ids:
                    continue
                seen_ids.add(lid)

                # Use the link itself or walk up
                container = lnk
                if len(lnk.get_text(strip=True)) < 10:
                    for _ in range(3):
                        if container.parent and container.parent.name not in ("body", "html", "[document]"):
                            container = container.parent
                        else:
                            break

                listing = self._parse_card(container)
                if listing and listing.url:
                    listings.append(listing)

            logger.info(f"Page {page}: found {len(seen_ids)} cards")
            time.sleep(config.request_delay)

        logger.info(f"Total from {self.name}: {len(listings)}")
        return listings
