"""Adapter for bina.az - uses GraphQL API (Next.js + Apollo)."""

import re
import json
import logging
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter
from app.models import Listing
from app.config import config
from app.normalization import (
    text_contains_any,
    TITLE_DEED_KEYWORDS,
    MORTGAGE_KEYWORDS,
)
from app.utils import safe_int, safe_float

logger = logging.getLogger(__name__)

# GraphQL query to fetch listings
ITEMS_QUERY = """
query GetItems($filter: ItemFilter!, $first: Int, $after: String, $sort: SortType) {
  itemsConnection(filter: $filter, first: $first, after: $after, sort: $sort) {
    totalCount
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        slug
        price
        currency
        area
        floor
        allFloor
        roomCount
        hasDocuments
        hasMortgage
        city {
          name
        }
        location {
          name
        }
        category {
          name
        }
      }
    }
  }
}
"""


class BinaAzAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "bina.az"

    @property
    def base_url(self) -> str:
        return "https://bina.az"

    def _find_graphql_endpoint(self, client: httpx.Client) -> Optional[str]:
        """Try to discover the GraphQL endpoint from the page source."""
        # Common GraphQL endpoints for Next.js apps
        endpoints = [
            f"{self.base_url}/graphql",
            f"{self.base_url}/api/graphql",
            f"{self.base_url}/v2/graphql",
        ]
        for ep in endpoints:
            try:
                resp = client.post(
                    ep,
                    json={"query": "{ __typename }"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    logger.info(f"Found GraphQL endpoint: {ep}")
                    return ep
            except Exception:
                continue
        return None

    def _fetch_via_graphql(self, client: httpx.Client, endpoint: str) -> List[Listing]:
        """Fetch listings via GraphQL API."""
        listings = []
        variables = {
            "filter": {
                "categoryId": "2",  # apartments
                "leased": False,
                "cityId": "1",  # Baku
            },
            "first": 50,
            "sort": "CREATED_AT",
        }

        try:
            resp = client.post(
                endpoint,
                json={"query": ITEMS_QUERY, "variables": variables},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

            edges = (
                data.get("data", {})
                .get("itemsConnection", {})
                .get("edges", [])
            )

            for edge in edges:
                node = edge.get("node", {})
                listing_id = str(node.get("id", ""))
                slug = node.get("slug", "")
                url = f"{self.base_url}/items/{listing_id}" if listing_id else ""
                if slug:
                    url = f"{self.base_url}/{slug}"

                location_name = ""
                loc = node.get("location")
                if loc:
                    location_name = loc.get("name", "")

                has_docs = node.get("hasDocuments")
                has_mortgage = node.get("hasMortgage")

                listing = Listing(
                    listing_id=listing_id,
                    url=url,
                    title=slug.replace("-", " ") if slug else "",
                    price=safe_int(str(node.get("price", ""))) if node.get("price") else None,
                    currency=node.get("currency", "AZN"),
                    area=safe_float(str(node.get("area", ""))) if node.get("area") else None,
                    floor=safe_int(str(node.get("floor", ""))) if node.get("floor") else None,
                    total_floors=safe_int(str(node.get("allFloor", ""))) if node.get("allFloor") else None,
                    rooms=safe_int(str(node.get("roomCount", ""))) if node.get("roomCount") else None,
                    location=location_name,
                    has_title_deed=has_docs,
                    is_mortgage_ready=has_mortgage,
                    source=self.name,
                )
                listings.append(listing)

        except Exception as e:
            logger.error(f"GraphQL fetch failed: {e}")

        return listings

    def _fetch_via_html(self, client: httpx.Client) -> List[Listing]:
        """Fallback: try to scrape from rendered HTML or parse __NEXT_DATA__."""
        listings = []
        pages_to_fetch = 3

        for page in range(1, pages_to_fetch + 1):
            page_listings = self._fetch_html_page(client, page)
            listings.extend(page_listings)
            if not page_listings:
                break
            import time
            time.sleep(config.request_delay)

        return listings

    def _fetch_html_page(self, client: httpx.Client, page: int) -> List[Listing]:
        """Fetch a single page of listings via HTML."""
        listings = []
        url = f"{self.base_url}/alqi-satqi/menziller/yeni-tikili?page={page}"

        try:
            resp = client.get(
                url,
                headers={
                    "User-Agent": config.user_agent,
                    "Accept": "text/html",
                },
                timeout=15.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Try to extract __NEXT_DATA__
            script = soup.find("script", id="__NEXT_DATA__")
            if script and script.string:
                try:
                    next_data = json.loads(script.string)
                    apollo_state = next_data.get("props", {}).get("apolloState", {})
                    if not apollo_state:
                        apollo_state = next_data.get("props", {}).get("pageProps", {}).get("apolloState", {})

                    # Parse items from Apollo cache
                    for key, value in apollo_state.items():
                        if key.startswith("Item:") and isinstance(value, dict):
                            listing_id = str(value.get("id", ""))
                            slug = value.get("slug", "")
                            item_url = f"{self.base_url}/{slug}" if slug else ""

                            loc_ref = value.get("location")
                            location_name = ""
                            if isinstance(loc_ref, dict) and "__ref" in loc_ref:
                                loc_data = apollo_state.get(loc_ref["__ref"], {})
                                location_name = loc_data.get("name", "")
                            elif isinstance(loc_ref, dict):
                                location_name = loc_ref.get("name", "")

                            listing = Listing(
                                listing_id=listing_id,
                                url=item_url,
                                title=slug.replace("-", " ") if slug else "",
                                price=safe_int(str(value.get("price", ""))) if value.get("price") else None,
                                area=safe_float(str(value.get("area", ""))) if value.get("area") else None,
                                floor=safe_int(str(value.get("floor", ""))) if value.get("floor") else None,
                                total_floors=safe_int(str(value.get("allFloor", ""))) if value.get("allFloor") else None,
                                rooms=safe_int(str(value.get("roomCount", ""))) if value.get("roomCount") else None,
                                location=location_name,
                                has_title_deed=value.get("hasDocuments"),
                                is_mortgage_ready=value.get("hasMortgage"),
                                source=self.name,
                            )
                            listings.append(listing)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse __NEXT_DATA__")

            # Also try to find listing cards in HTML
            if not listings:
                # bina.az uses .items-i class for listing cards
                cards = soup.select(".items-i")
                if not cards:
                    cards = soup.select("[class*='card'], [class*='item'], [class*='listing']")
                for card in cards:
                    link = card.find("a", href=True)
                    if not link:
                        continue
                    href = link["href"]
                    if not href.startswith("http"):
                        href = f"{self.base_url}{href}"

                    # Extract listing ID from URL
                    lid_match = re.search(r'/items?/(\d+)', href)
                    lid = lid_match.group(1) if lid_match else ""

                    # Get title from .name or link text
                    name_el = card.select_one(".name")
                    title = name_el.get_text(strip=True) if name_el else link.get_text(strip=True)
                    text = card.get_text(" ", strip=True)

                    # Parse price from .price-val or text
                    price = None
                    price_el = card.select_one(".price-val")
                    if price_el:
                        price = safe_int(price_el.get_text(strip=True))
                    else:
                        price_match = re.search(r'([\d\s]+)\s*(?:AZN|₼)', text)
                        if price_match:
                            price = safe_int(price_match.group(1))

                    # Parse area
                    area = None
                    area_match = re.search(r'([\d.,]+)\s*m[²2]', text)
                    if area_match:
                        area = safe_float(area_match.group(1))

                    # Parse floor from "X/Y mərtəbə" pattern
                    floor, total_floors = None, None
                    floor_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
                    if floor_match:
                        floor = safe_int(floor_match.group(1))
                        total_floors = safe_int(floor_match.group(2))

                    # Parse location from .location element
                    location = ""
                    loc_el = card.select_one(".location")
                    if loc_el:
                        location = loc_el.get_text(strip=True)

                    listing = Listing(
                        listing_id=lid,
                        url=href,
                        title=title,
                        price=price,
                        area=area,
                        floor=floor,
                        total_floors=total_floors,
                        location=location,
                        description=text,
                        has_title_deed=text_contains_any(text, TITLE_DEED_KEYWORDS),
                        is_mortgage_ready=text_contains_any(text, MORTGAGE_KEYWORDS),
                        source=self.name,
                        raw_text=text,
                    )
                    listings.append(listing)

        except Exception as e:
            logger.error(f"HTML scraping failed for {self.name}: {e}")

        return listings

    def fetch_listings(self) -> List[Listing]:
        """Fetch listings - try GraphQL first, fall back to HTML parsing."""
        with httpx.Client(
            headers={"User-Agent": config.user_agent},
            follow_redirects=True,
        ) as client:
            # Try GraphQL API first
            endpoint = self._find_graphql_endpoint(client)
            if endpoint:
                listings = self._fetch_via_graphql(client, endpoint)
                if listings:
                    logger.info(f"Got {len(listings)} listings from GraphQL API")
                    return listings

            # Fall back to HTML parsing
            logger.info("GraphQL not available, falling back to HTML parsing")
            return self._fetch_via_html(client)
