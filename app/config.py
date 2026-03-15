"""Configuration for the real estate monitor."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    price_min: int = 150_000
    price_max: int = 200_000
    area_min: int = 60
    area_max: int = 90
    exclude_total_floors: List[int] = field(default_factory=lambda: [5])
    require_title_deed: bool = True
    require_mortgage_ready: bool = True
    target_locations: List[str] = field(default_factory=lambda: [
        "Təbriz küçəsi",
        "Çapayev",
        "Nərimanov",
        "Gənclik",
        "Qara Qarayev",
        "Ayna Sultanov",
        "Atatürk parkı ətrafı",
    ])
    ntfy_topic: str = "rs-emlak"
    ntfy_url: str = "https://ntfy.sh"
    interval_minutes: int = 5
    db_path: str = "data/state.db"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    request_delay: float = 2.0  # seconds between requests


config = Config()
