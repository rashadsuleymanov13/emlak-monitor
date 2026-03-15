"""Tests for state management and deduplication."""

import os
import tempfile
import pytest

from app.state import (
    init_db,
    get_dedup_key,
    is_seen,
    mark_seen,
    is_first_run,
    mark_seeded,
    reset_state,
    get_seen_count,
)


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = init_db(path)
    yield conn, path
    conn.close()
    if os.path.exists(path):
        os.remove(path)


class TestDedupKey:
    def test_prefers_listing_id(self):
        key = get_dedup_key("123", "https://example.com", "title", 100, 50.0)
        assert key == "id:123"

    def test_falls_back_to_url_hash(self):
        key = get_dedup_key("", "https://example.com/listing/456", "title", 100, 50.0)
        assert key.startswith("url:")
        assert len(key) > 4

    def test_falls_back_to_fingerprint(self):
        key = get_dedup_key("", "", "Nice apartment", 175000, 80.0)
        assert key.startswith("fp:")

    def test_same_id_same_key(self):
        k1 = get_dedup_key("abc", "", "", None, None)
        k2 = get_dedup_key("abc", "different-url", "different-title", 999, 999.0)
        assert k1 == k2

    def test_same_url_same_key(self):
        k1 = get_dedup_key("", "https://example.com/1", "", None, None)
        k2 = get_dedup_key("", "https://example.com/1", "different", 999, 999.0)
        assert k1 == k2


class TestState:
    def test_initial_not_seen(self, db):
        conn, _ = db
        assert is_seen(conn, "id:123") is False

    def test_mark_and_check(self, db):
        conn, _ = db
        mark_seen(conn, "id:123", listing_id="123")
        assert is_seen(conn, "id:123") is True

    def test_different_key_not_seen(self, db):
        conn, _ = db
        mark_seen(conn, "id:123")
        assert is_seen(conn, "id:456") is False

    def test_first_run_detection(self, db):
        conn, _ = db
        assert is_first_run(conn) is True
        mark_seeded(conn)
        assert is_first_run(conn) is False

    def test_seen_count(self, db):
        conn, _ = db
        assert get_seen_count(conn) == 0
        mark_seen(conn, "id:1")
        mark_seen(conn, "id:2")
        mark_seen(conn, "id:3")
        assert get_seen_count(conn) == 3

    def test_duplicate_mark_ignored(self, db):
        conn, _ = db
        mark_seen(conn, "id:1")
        mark_seen(conn, "id:1")  # Should not raise
        assert get_seen_count(conn) == 1


class TestReset:
    def test_reset_removes_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = init_db(path)
        mark_seen(conn, "id:1")
        conn.close()
        assert os.path.exists(path)
        reset_state(path)
        assert not os.path.exists(path)
