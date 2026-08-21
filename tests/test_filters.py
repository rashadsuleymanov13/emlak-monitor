"""Tests for filter logic."""

import pytest
from app.config import Config
from app.models import Listing
from app.filters import (
    passes_price_filter,
    passes_area_filter,
    passes_location_filter,
    passes_title_deed_filter,
    passes_mortgage_filter,
    is_rent_listing,
    listing_matches,
)


@pytest.fixture
def cfg():
    return Config()


def make_listing(**kwargs) -> Listing:
    defaults = {
        "listing_id": "test-1",
        "url": "https://example.com/1",
        "title": "2 otaqlı mənzil Əhmədli",
        "price": 175000,
        "area": 75.0,
        "floor": 3,
        "total_floors": 5,
        "location": "Əhmədli",
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

    def test_below_min(self, cfg):
        # artıq alt limit var (170k) — aşağı qiymət keçməməlidir
        listing = make_listing(price=169999)
        assert passes_price_filter(listing, cfg) is False

    def test_at_min(self, cfg):
        listing = make_listing(price=170000)
        assert passes_price_filter(listing, cfg) is True

    def test_at_max(self, cfg):
        listing = make_listing(price=190000)
        assert passes_price_filter(listing, cfg) is True

    def test_above_max(self, cfg):
        listing = make_listing(price=190001)
        assert passes_price_filter(listing, cfg) is False

    def test_none_price(self, cfg):
        listing = make_listing(price=None)
        assert passes_price_filter(listing, cfg) is False


class TestAreaFilter:
    def test_in_range(self, cfg):
        listing = make_listing(area=75.0)
        assert passes_area_filter(listing, cfg) is True

    def test_at_min(self, cfg):
        listing = make_listing(area=65.0)
        assert passes_area_filter(listing, cfg) is True

    def test_at_max(self, cfg):
        listing = make_listing(area=80.0)
        assert passes_area_filter(listing, cfg) is True

    def test_below_min(self, cfg):
        listing = make_listing(area=64.9)
        assert passes_area_filter(listing, cfg) is False

    def test_above_max(self, cfg):
        listing = make_listing(area=80.1)
        assert passes_area_filter(listing, cfg) is False

    def test_none_area(self, cfg):
        listing = make_listing(area=None)
        assert passes_area_filter(listing, cfg) is False


class TestLocationFilter:
    def test_ehmedli_match(self, cfg):
        listing = make_listing(title="Mənzil Əhmədli", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_ehmedli_transliterated(self, cfg):
        listing = make_listing(title="Menzil Ehmedli", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_hezi_aslanov(self, cfg):
        listing = make_listing(title="Həzi Aslanov m/s", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_hezi_aslanov_ascii(self, cfg):
        listing = make_listing(title="Hezi Aslanov", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_qarayev(self, cfg):
        listing = make_listing(title="Qara Qarayev", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_qarayev_ascii(self, cfg):
        listing = make_listing(title="Gara Garayev metrosu", location="", description="")
        assert passes_location_filter(listing, cfg) is True

    def test_removed_location_nerimanov(self, cfg):
        """Nərimanov artıq hədəf deyil."""
        listing = make_listing(title="Mənzil Nərimanov", location="Nərimanov", description="")
        assert passes_location_filter(listing, cfg) is False

    def test_removed_location_ataturk(self, cfg):
        listing = make_listing(title="", location="Atatürk parkı", description="")
        assert passes_location_filter(listing, cfg) is False

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

    def test_no_mortgage(self):
        # require_mortgage_ready aktiv olanda ipoteka işarəsi olmayan elan keçməməlidir
        cfg = Config(require_mortgage_ready=True)
        listing = make_listing(is_mortgage_ready=None, description="Gözəl mənzil", raw_text="")
        assert passes_mortgage_filter(listing, cfg) is False


class TestRentFilter:
    def test_kiraye_in_title(self):
        listing = make_listing(title="Əhmədli kirayə mənzil")
        assert is_rent_listing(listing) is True

    def test_kiraye_ascii(self):
        listing = make_listing(title="Ehmedli kiraye verilir", description="")
        assert is_rent_listing(listing) is True

    def test_icare_in_description(self):
        listing = make_listing(title="Əhmədli mənzil", description="İcarəyə verilir")
        assert is_rent_listing(listing) is True

    def test_gunluk(self):
        listing = make_listing(title="Əhmədli günlük mənzil")
        assert is_rent_listing(listing) is True

    def test_kiraye_in_url(self):
        listing = make_listing(url="https://bina.az/kiraye/123", title="Əhmədli mənzil")
        assert is_rent_listing(listing) is True

    def test_satilir_not_rent(self):
        listing = make_listing(title="Əhmədli satılır mənzil", description="Kupça var")
        assert is_rent_listing(listing) is False


class TestListingMatches:
    def test_full_match(self, cfg):
        listing = make_listing()
        assert listing_matches(listing, cfg) is True

    def test_fails_price_high(self, cfg):
        listing = make_listing(price=200000)
        assert listing_matches(listing, cfg) is False

    def test_fails_price_low(self, cfg):
        listing = make_listing(price=150000)
        assert listing_matches(listing, cfg) is False

    def test_fails_location(self, cfg):
        listing = make_listing(
            title="Yasamal", location="Yasamal", description="Kupça var ipoteka var"
        )
        assert listing_matches(listing, cfg) is False

    def test_fails_small_area(self, cfg):
        """Sahə artıq məcburi filtrdir — 65-dən aşağı keçməməlidir."""
        listing = make_listing(area=55.0)
        assert listing_matches(listing, cfg) is False

    def test_fails_large_area(self, cfg):
        listing = make_listing(area=95.0)
        assert listing_matches(listing, cfg) is False

    def test_fails_unknown_area(self, cfg):
        """Sahəsi oxunmayan elan keçmir (kv məcburidir)."""
        listing = make_listing(area=None)
        assert listing_matches(listing, cfg) is False

    def test_area_stats_separate_unknown(self, cfg):
        stats: dict = {}
        listing_matches(make_listing(area=None), cfg, log_stats=stats)
        assert stats.get("fail_area_unknown") == 1
        listing_matches(make_listing(area=50.0), cfg, log_stats=stats)
        assert stats.get("fail_area") == 1

    def test_rooms_do_not_matter(self, cfg):
        """Otaq sayı filtri yoxdur — 1, 2 və ya 3 otaq fərq etmir."""
        for rooms in (1, 2, 3):
            listing = make_listing(rooms=rooms)
            assert listing_matches(listing, cfg) is True

    def test_high_rise_still_matches(self, cfg):
        """Mərtəbə/tikili filtri yoxdur — yeni hündürmərtəbəli də keçməlidir."""
        listing = make_listing(total_floors=20)
        assert listing_matches(listing, cfg) is True

    def test_old_low_rise_still_matches(self, cfg):
        """Köhnə tikili (az mərtəbəli) də keçməlidir."""
        listing = make_listing(total_floors=4)
        assert listing_matches(listing, cfg) is True

    def test_passes_without_kupca(self, cfg):
        """Title deed is soft filter — should still match."""
        listing = make_listing(has_title_deed=None, description="Gözəl mənzil Əhmədli", raw_text="")
        assert listing_matches(listing, cfg) is True

    def test_rejects_rent(self, cfg):
        """Kirayə elanı yer/qiymət uyğun olsa belə rədd edilməlidir."""
        listing = make_listing(title="Əhmədli kirayə mənzil")
        assert listing_matches(listing, cfg) is False
