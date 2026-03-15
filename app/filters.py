"""Filter logic for listings."""

from app.config import Config
from app.models import Listing
from app.normalization import (
    text_contains_any,
    matches_location,
    TITLE_DEED_KEYWORDS,
    MORTGAGE_KEYWORDS,
)


def passes_price_filter(listing: Listing, cfg: Config) -> bool:
    if listing.price is None:
        return False
    return cfg.price_min <= listing.price <= cfg.price_max


def passes_area_filter(listing: Listing, cfg: Config) -> bool:
    if listing.area is None:
        return False
    return cfg.area_min <= listing.area <= cfg.area_max


def passes_floor_filter(listing: Listing, cfg: Config) -> bool:
    if listing.total_floors is None:
        return True  # Don't exclude if unknown
    return cfg.min_total_floors <= listing.total_floors <= cfg.max_total_floors


def passes_location_filter(listing: Listing, cfg: Config) -> bool:
    searchable = f"{listing.title} {listing.location} {listing.description}"
    return matches_location(searchable, cfg.target_locations)


def passes_title_deed_filter(listing: Listing, cfg: Config) -> bool:
    if not cfg.require_title_deed:
        return True
    if listing.has_title_deed is True:
        return True
    searchable = f"{listing.title} {listing.description} {listing.raw_text}"
    return text_contains_any(searchable, TITLE_DEED_KEYWORDS)


def passes_mortgage_filter(listing: Listing, cfg: Config) -> bool:
    if not cfg.require_mortgage_ready:
        return True
    if listing.is_mortgage_ready is True:
        return True
    searchable = f"{listing.title} {listing.description} {listing.raw_text}"
    return text_contains_any(searchable, MORTGAGE_KEYWORDS)


def listing_matches(listing: Listing, cfg: Config, log_stats: dict | None = None) -> bool:
    """Check if a listing passes all filters."""
    if not passes_price_filter(listing, cfg):
        if log_stats is not None:
            log_stats["fail_price"] = log_stats.get("fail_price", 0) + 1
        return False
    if not passes_area_filter(listing, cfg):
        if log_stats is not None:
            log_stats["fail_area"] = log_stats.get("fail_area", 0) + 1
        return False
    if not passes_floor_filter(listing, cfg):
        if log_stats is not None:
            log_stats["fail_floor"] = log_stats.get("fail_floor", 0) + 1
        return False
    if not passes_location_filter(listing, cfg):
        if log_stats is not None:
            log_stats["fail_location"] = log_stats.get("fail_location", 0) + 1
        return False
    if not passes_title_deed_filter(listing, cfg):
        if log_stats is not None:
            log_stats["fail_kupca"] = log_stats.get("fail_kupca", 0) + 1
        return False
    if not passes_mortgage_filter(listing, cfg):
        if log_stats is not None:
            log_stats["fail_ipoteka"] = log_stats.get("fail_ipoteka", 0) + 1
        return False
    return True
