"""Configuration for the real estate monitor."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    price_min: int = 0          # alt limit yoxdur — yalnız yuxarı hədd
    price_max: int = 170_000    # 170 min-dən yuxarı YOX
    area_min: int = 60          # area (kv) filtri DEAKTİVDİR — listing_matches-də istifadə olunmur
    area_max: int = 90
    # Mərtəbə/tikili filtri YOXDUR — köhnə və yeni tikili hamısı gəlir
    require_title_deed: bool = True
    require_mortgage_ready: bool = False
    target_locations: List[str] = field(default_factory=lambda: [
        # --- Bakı metrosu: bütün stansiyalar ---
        "İçərişəhər",
        "Sahil",
        "28 May",
        "Gənclik",
        "Nəriman Nərimanov",
        "Bakmil",
        "Ulduz",
        "Koroğlu",
        "Qara Qarayev",
        "Neftçilər",
        "Xalqlar dostluğu",
        "Əhmədli",
        "Həzi Aslanov",
        "Nizami Gəncəvi",
        "Elmlər Akademiyası",
        "İnşaatçılar",
        "20 Yanvar",
        "Memar Əcəmi",
        "Nəsimi",
        "Azadlıq prospekti",
        "Dərnəgül",
        "Cəfər Cabbarlı",
        "Xətai",
        "Avtovağzal",
        "8 Noyabr",
        # --- Qəsəbə / yaşayış kompleksi ---
        "Masazır",
        "Qurtuluş 93",
        # --- Küçə / məhəllə / landmark ---
        "Təbriz küçəsi",
        "Çapayev",
        "Ayna Sultanova",
        "Atatürk parkı",
        "Əbdüləzəl Dəmirçizadə",
        "Şərq bazarı",
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
