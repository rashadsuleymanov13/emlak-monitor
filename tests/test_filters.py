"""Tests for filter logic."""

import pytest
from app.config import Config
from app.models import Listing
from app.filters import (
    passes_price_filter,
    passes_area_filter,
    passes_floor_filter,
    passes_location_filter,
    passes_title_deed_filter,
    passes_mortgage_filter,
    listing_matches,
)


@pytest.fixture
def cfg():
    return Config()


def make_listing(**kwargs) -> Listing:
    defaults = {
        "listing_id": "test-1",
        "url": "https://example.com/1",
        "title": "3 otaqlı mənzil Nərimanov rayonu",
        "price": 175000,
        "area": 75.0,
        "floor": 3,
        "total_floors": 5,
        "location": "Nərimanov",
        "description": "Kupça var, ipotekaya yararlı",
        "has_title_deed": True,
        "is_mortgage_ready": True,
        "source": "bina.az",
    }
    defaults.update(kwargs)
    return Listing(**defaults)


class TestPriceFilter:
    def test_in_range(self, cfg):
        listing = make_listing(price=175000)
        assert passes_price_filter(listing, cfg) is True

    def test_at_min(self, cfg):
        listing = make_listing(price=150000)
        assert passes_price_filter(listing, cfg) is True

    def test_at_max(self, cfg):
        listing = make_listing(price=200000)
        assert passes_price_filter(listing, cfg) is True

    def test_below_min(self, cfg):
        listing = make_listing(price=149999)
        assert passes_price_filter(listing, cfg) is False

    def test_above_max(self, cfg):
        listing = make_listing(price=200001)
        assert passes_price_filter(listing, cfg) is False

    def test_none_price(self, cfg):
        listing = make_listing(price=None)
        assert passes_price_filter(listing, cfg) is False


class TestAreaFilter:
    def test_in_range(self, cfg):
        listing = make_listing(area=75.0)
        assert passes_area_filter(listing, cfg) is True

    def test_at_min(self, cfg):
        listing = make_listing(area=60.0)
        assert passes_area_filter(listing, cfg) is True

    def test_at_max(self, cfg):
        listing = make_listing(area=90.0)
        assert passes_area_filter(listing, cfg) is True

    def test_below_min(self, cfg):
        listing = make_listing(area=59.9)
        assert passes_area_filter(listing, cfg) is False

    def test_above_max(self, cfg):
        listing = make_listing(area=90.1)
        assert passes_area_filter(listing, cfg) is False

    def test_none_area(self, cfg):
        listing = make_listing(area=None)
        assert passes_area_filter(listing, cfg) is False


class TestFloorFilter:
    def test_excludes_6_floor_building(self, cfg):
        listing = make_listing(total_floors=6)
        assert passes_floor_filter(listing, cfg) is False

    def test_excludes_16_floor_building(self, cfg):
        listing = make_listing(total_floors=16)
        assert passes_floor_filter(listing, cfg) is False

    def test_excludes_25_floor_building(self, cfg):
        listing = make_listing(total_floors=25)
        assert passes_floor_filter(listing, cfg) is False

    def test_allows_5_floor_building(self, cfg):
        listing = make_listing(total_floors=5)
        assert passes_floor_filter(listing, cfg) is True

    def test_allows_3_floor_building(self, cfg):
        listing = make_listing(total_floors=3)
        assert passes_floor_filter(listing, cfg) is True

    def test_allows_26_floor_building(self, cfg):
        listing = make_listing(total_floors=26)
        assert passes_floor_filter(listing, cfg) is True

    def test_none_floors_passes(self, cfg):
        listing = make_listing(total_floors=None)
        assert passes_floor_filter(listing, cfg) is True


class TestLocationFilter:
    def test_nerimanov_match(self, cfg):
        listing = make_listing(title="Mənzil Nərimanov", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_nerimanov_transliterated(self, cfg):
        listing = make_listing(title="Menzil Nerimanov", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_chapayev(self, cfg):
        listing = make_listing(title="Çapayev küçəsi", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_chapayev_ascii(self, cfg):
        listing = make_listing(title="Chapayev kucesi", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_ataturk(self, cfg):
        listing = make_listing(title="", location="Atatürk parkı", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_ataturk_ascii(self, cfg):
        listing = make_listing(title="Ataturk", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_tebriz(self, cfg):
        listing = make_listing(title="Təbriz küçəsi", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_tebriz_ascii(self, cfg):
        listing = make_listing(title="Tebriz", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_genclik(self, cfg):
        listing = make_listing(title="Gənclik m/s", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_qarayev(self, cfg):
        listing = make_listing(title="Qara Qarayev", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_ayna_sultanov(self, cfg):
        listing = make_listing(title="Ayna Sultanova küçəsi", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_no_match(self, cfg):
        listing = make_listing(title="Yasamal rayonu", location="Yasamal", description="Gözəl mənzil")
        assert passes_location_filter(listing, cfg) is False


class TestTitleDeedFilter:
    def test_has_title_deed_flag(self, cfg):
        listing = make_listing(has_title_deed=True, description="")
        assert passes_title_deed_filter(listing, cfg) is True

    def test_kupca_in_text(self, cfg):
        listing = make_listing(has_title_deed=None, description="Kupça var")
        assert passes_title_deed_filter(listing, cfg) is True

    def test_cixaris_in_text(self, cfg):
        listing = make_listing(has_title_deed=None, description="Çıxarış var")
        assert passes_title_deed_filter(listing, cfg) is True

    def test_no_title_deed(self, cfg):
        listing = make_listing(has_title_deed=None, description="Gözəl mənzil", raw_text="")
        assert passes_title_deed_filter(listing, cfg) is False

    def test_disabled(self):
        cfg = Config(require_title_deed=False)
        listing = make_listing(has_title_deed=None, description="")
        assert passes_title_deed_filter(listing, cfg) is True


class TestMortgageFilter:
    def test_has_mortgage_flag(self, cfg):
        listing = make_listing(is_mortgage_ready=True, description="")
        assert passes_mortgage_filter(listing, cfg) is True

    def test_ipoteka_in_text(self, cfg):
        listing = make_listing(is_mortgage_ready=None, description="İpotekaya yararlı")
        assert passes_mortgage_filter(listing, cfg) is True

    def test_kredit_in_text(self, cfg):
        listing = make_listing(is_mortgage_ready=None, description="Kreditə yararlı")
        assert passes_mortgage_filter(listing, cfg) is True

    def test_no_mortgage(self, cfg):
        listing = make_listing(is_mortgage_ready=None, description="Gözəl mənzil", raw_text="")
        assert passes_mortgage_filter(listing, cfg) is False


class TestListingMatches:
    def test_full_match(self, cfg):
        listing = make_listing()
        assert listing_matches(listing, cfg) is True

    def test_fails_price(self, cfg):
        listing = make_listing(price=100000)
        assert listing_matches(listing, cfg) is False

    def test_fails_location(self, cfg):
        listing = make_listing(
            title="Yasamal", location="Yasamal", description="Kupça var ipoteka var"
        )
        assert listing_matches(listing, cfg) is False

    def test_passes_with_wrong_area(self, cfg):
        """Area is soft filter — should still match."""
        listing = make_listing(area=30.0)
        assert listing_matches(listing, cfg) is True

    def test_passes_with_wrong_floor(self, cfg):
        """Floor is soft filter — should still match."""
        listing = make_listing(total_floors=10)
        assert listing_matches(listing, cfg) is True

    def test_passes_without_kupca(self, cfg):
        """Title deed is soft filter — should still match."""
        listing = make_listing(has_title_deed=None, description="Gözəl mənzil Nərimanov", raw_text="")
        assert listing_matches(listing, cfg) is True
