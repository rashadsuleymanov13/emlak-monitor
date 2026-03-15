"""Data models for listings."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Listing:
    listing_id: str
    url: str
    title: str
    price: Optional[int] = None
    currency: str = "AZN"
    area: Optional[float] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    rooms: Optional[int] = None
    location: str = ""
    description: str = ""
    has_title_deed: Optional[bool] = None
    is_mortgage_ready: Optional[bool] = None
    source: str = ""
    raw_text: str = ""

    def fingerprint(self) -> str:
        """Fallback dedup key: title + price + area."""
        return f"{self.title}|{self.price}|{self.area}"
