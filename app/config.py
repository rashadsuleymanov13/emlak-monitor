"""Configuration for the real estate monitor."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    price_min: int = 170_000    # 170 min-dən aşağı YOX
    price_max: int = 190_000    # 190 min-dən yuxarı YOX
    area_min: int = 65          # sahə (kv) MƏCBURİ filtrdir: 65–80 m²
    area_max: int = 80
    # Mərtəbə/tikili filtri YOXDUR — köhnə və yeni tikili hamısı gəlir
    # Otaq sayı filtri YOXDUR — 1-dən 2-yə düzəldilmiş, 2 və ya 3 otaq — fərqi yoxdur,
    # əsas meyar sahədir (65–80 m²)
    require_title_deed: bool = True
    require_mortgage_ready: bool = False
    target_locations: List[str] = field(default_factory=lambda: [
        # --- Yalnız bu 3 ərazi ---
        "Həzi Aslanov",
        "Əhmədli",
        "Qara Qarayev",
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
