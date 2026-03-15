"""Text normalization utilities for Azerbaijani real estate text."""

import re
import unicodedata
from typing import List, Tuple

# Transliteration map: Azerbaijani special chars -> ASCII equivalents
_TRANSLIT_MAP = {
    "ə": "e",
    "Ə": "E",
    "ü": "u",
    "Ü": "U",
    "ö": "o",
    "Ö": "O",
    "ş": "s",
    "Ş": "S",
    "ç": "c",
    "Ç": "C",
    "ğ": "g",
    "Ğ": "G",
    "ı": "i",
    "İ": "I",
}

# Location name variants for matching
LOCATION_VARIANTS: List[Tuple[str, List[str]]] = [
    # Metro stansiyaları
    ("xalqlar dostluğu", [
        "xalqlar dostlugu", "xalqlar dostluğu",
        "xalqlar", "dostluq", "dostlugu",
    ]),
    ("qara qarayev", [
        "qara qarayev", "qarayev", "gara garayev", "qarayev m.",
    ]),
    ("nəriman nərimanov", [
        "nerimanov", "narimanov", "nərimanov", "neriman nerimanov",
        "nəriman nərimanov", "n.nərimanov",
    ]),
    ("gənclik", ["genclik", "ganclik", "gənclik"]),
    ("elmlər akademiyası", [
        "elmler akademiyasi", "elmlər akademiyası",
        "elmler", "akademiya",
    ]),
    # Küçə / məhəllə / landmark
    ("təbriz küçəsi", ["tebriz", "tabriz", "təbriz"]),
    ("çapayev", ["chapayev", "capayev", "çapayev"]),
    ("ayna sultanova", [
        "ayna sultanova", "ayna sultanov", "sultanova",
    ]),
    ("atatürk parkı", [
        "ataturk", "atatürk", "ata turk", "ata türk",
        "ataturk parki", "atatürk parkı",
    ]),
    ("əbdüləzəl dəmirçizadə", [
        "demircizade", "dəmirçizadə", "demirchizade",
        "abdulezal", "əbdüləzəl",
    ]),
    ("şərq bazarı", [
        "serq bazari", "şərq bazarı", "şərq bazar",
        "serq bazar", "sharq bazar",
    ]),
]

# Title deed keywords
TITLE_DEED_KEYWORDS = [
    "kupça", "kupca", "kupçalı", "kupcali",
    "çıxarış", "cixaris", "çixariş", "cixarish",
    "kupçası var", "kupcasi var",
    "sənəd", "sened",
]

# Mortgage keywords
MORTGAGE_KEYWORDS = [
    "ipoteka", "ipotekaya yararlı", "ipotekaya yararli",
    "ipoteka mümkündür", "ipoteka mumkundur",
    "kreditə yararlı", "kredite yararli",
    "kredit", "ipotekali", "ipotekalı",
    "kredit mümkündür", "kredit mumkundur",
]


def normalize_text(text: str) -> str:
    """Lowercase, strip, normalize unicode, transliterate."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFC", text)
    return text


def transliterate(text: str) -> str:
    """Convert Azerbaijani characters to ASCII equivalents."""
    result = []
    for ch in text:
        result.append(_TRANSLIT_MAP.get(ch, ch))
    return "".join(result)


def text_contains_any(text: str, keywords: List[str]) -> bool:
    """Check if normalized text contains any of the keywords."""
    norm = normalize_text(text)
    trans = transliterate(norm)
    for kw in keywords:
        kw_norm = normalize_text(kw)
        kw_trans = transliterate(kw_norm)
        if kw_norm in norm or kw_trans in trans:
            return True
    return False


def matches_location(text: str, target_locations: List[str]) -> bool:
    """Check if text matches any target location using fuzzy matching."""
    norm = normalize_text(text)
    trans = transliterate(norm)

    for canonical, variants in LOCATION_VARIANTS:
        canonical_norm = normalize_text(canonical)
        # Check if this location is in target list
        location_targeted = False
        for target in target_locations:
            target_norm = normalize_text(target)
            if (target_norm in canonical_norm
                    or canonical_norm in target_norm
                    or transliterate(target_norm) in transliterate(canonical_norm)):
                location_targeted = True
                break

        if not location_targeted:
            continue

        # Check if text matches any variant
        for variant in variants:
            v_norm = normalize_text(variant)
            v_trans = transliterate(v_norm)
            if v_norm in norm or v_trans in trans:
                return True

        # Also check canonical name
        if canonical_norm in norm or transliterate(canonical_norm) in trans:
            return True

    return False


def parse_price(text: str) -> int | None:
    """Extract price in AZN from text."""
    text = normalize_text(text)
    text = text.replace(" ", "").replace("\u00a0", "")
    match = re.search(r'(\d[\d\s.,]*)\s*(?:azn|man|manat)?', text)
    if match:
        num_str = match.group(1).replace(",", "").replace(".", "").replace(" ", "")
        try:
            return int(num_str)
        except ValueError:
            return None
    return None


def parse_area(text: str) -> float | None:
    """Extract area in m2 from text."""
    text = normalize_text(text)
    match = re.search(r'(\d+[.,]?\d*)\s*(?:m²|m2|kv\.?\s*m)', text)
    if match:
        num_str = match.group(1).replace(",", ".")
        try:
            return float(num_str)
        except ValueError:
            return None
    return None


def parse_floor_info(text: str) -> tuple[int | None, int | None]:
    """Extract floor and total floors from text like '7/16'."""
    text = normalize_text(text)
    match = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if match:
        try:
            return int(match.group(1)), int(match.group(2))
        except ValueError:
            return None, None
    return None, None
