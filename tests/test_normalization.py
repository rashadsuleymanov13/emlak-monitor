"""Tests for normalization utilities."""

from app.normalization import (
    normalize_text,
    transliterate,
    text_contains_any,
    matches_location,
    parse_price,
    parse_area,
    parse_floor_info,
)
from app.config import Config


class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("HELLO") == "hello"

    def test_strip(self):
        assert normalize_text("  hello  ") == "hello"


class TestTransliterate:
    def test_azerbaijani_chars(self):
        assert transliterate("əüöşçğı") == "euoscgi"

    def test_mixed(self):
        assert transliterate("nərimanov") == "nerimanov"


class TestTextContainsAny:
    def test_exact_match(self):
        assert text_contains_any("kupça var", ["kupça"]) is True

    def test_transliterated_match(self):
        assert text_contains_any("kupca var", ["kupça"]) is True

    def test_no_match(self):
        assert text_contains_any("gözəl mənzil", ["kupça"]) is False


class TestMatchesLocation:
    def test_nerimanov_azerbaijani(self):
        cfg = Config()
        assert matches_location("Nərimanov rayonu", cfg.target_locations) is True

    def test_nerimanov_ascii(self):
        cfg = Config()
        assert matches_location("Nerimanov rayonu", cfg.target_locations) is True

    def test_chapayev_azerbaijani(self):
        cfg = Config()
        assert matches_location("Çapayev küçəsi", cfg.target_locations) is True

    def test_chapayev_ascii(self):
        cfg = Config()
        assert matches_location("Chapayev kucesi", cfg.target_locations) is True

    def test_ataturk_variants(self):
        cfg = Config()
        assert matches_location("Atatürk parkı", cfg.target_locations) is True
        assert matches_location("Ataturk parki", cfg.target_locations) is True
        assert matches_location("Ata turk", cfg.target_locations) is True

    def test_xalqlar_dostlugu(self):
        cfg = Config()
        assert matches_location("Xalqlar dostluğu metrosu", cfg.target_locations) is True
        assert matches_location("xalqlar dostlugu", cfg.target_locations) is True

    def test_elmler_akademiyasi(self):
        cfg = Config()
        assert matches_location("Elmlər Akademiyası m.", cfg.target_locations) is True
        assert matches_location("elmler akademiyasi", cfg.target_locations) is True

    def test_demircizade(self):
        cfg = Config()
        assert matches_location("Dəmirçizadə küçəsi", cfg.target_locations) is True
        assert matches_location("Demircizade", cfg.target_locations) is True

    def test_serq_bazari(self):
        cfg = Config()
        assert matches_location("Şərq bazarı yaxınlığı", cfg.target_locations) is True
        assert matches_location("serq bazari", cfg.target_locations) is True

    def test_no_match(self):
        cfg = Config()
        assert matches_location("Yasamal", cfg.target_locations) is False


class TestParsePrice:
    def test_simple(self):
        assert parse_price("175000 AZN") == 175000

    def test_with_spaces(self):
        assert parse_price("175 000 AZN") == 175000

    def test_with_commas(self):
        assert parse_price("175,000") == 175000

    def test_manat(self):
        assert parse_price("175000 manat") == 175000

    def test_no_price(self):
        assert parse_price("no price here") is None


class TestParseArea:
    def test_m2(self):
        assert parse_area("75 m²") == 75.0

    def test_kv_m(self):
        assert parse_area("75 kv.m") == 75.0

    def test_decimal(self):
        assert parse_area("75.5 m²") == 75.5

    def test_no_area(self):
        assert parse_area("no area here") is None


class TestParseFloorInfo:
    def test_normal(self):
        assert parse_floor_info("7/16") == (7, 16)

    def test_with_spaces(self):
        assert parse_floor_info("7 / 16") == (7, 16)

    def test_no_info(self):
        assert parse_floor_info("no floor") == (None, None)
