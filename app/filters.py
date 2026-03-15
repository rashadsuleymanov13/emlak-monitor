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
    return listing.total_floors not in cfg.exclude_total_floors


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


def listing_matches(listing: Listing, cfg: Config) -> bool:
    """Check if a listing passes all filters."""
    return (
        passes_price_filter(listing, cfg)
        and passes_area_filter(listing, cfg)
        and passes_floor_filter(listing, cfg)
        and passes_location_filter(listing, cfg)
        and passes_title_deed_filter(listing, cfg)
        and passes_mortgage_filter(listing, cfg)
    )
