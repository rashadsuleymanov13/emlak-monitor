"""State management using SQLite for deduplication."""

import sqlite3
import hashlib
import os
from typing import Optional

from app.config import config


def _get_db_path() -> str:
    return config.db_path


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Initialize the database and return a connection."""
    path = db_path or _get_db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_listings (
            dedup_key TEXT PRIMARY KEY,
            listing_id TEXT,
            url TEXT,
            title TEXT,
            price INTEGER,
            source TEXT,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notified INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    return conn


def get_dedup_key(listing_id: str, url: str, title: str, price: Optional[int], area: Optional[float]) -> str:
    """Generate dedup key: prefer listing_id, then url hash, then fingerprint."""
    if listing_id:
        return f"id:{listing_id}"
    if url:
        return f"url:{hashlib.sha256(url.encode()).hexdigest()[:16]}"
    fingerprint = f"{title}|{price}|{area}"
    return f"fp:{hashlib.sha256(fingerprint.encode()).hexdigest()[:16]}"


def is_seen(conn: sqlite3.Connection, dedup_key: str) -> bool:
    """Check if a listing has been seen before."""
    row = conn.execute(
        "SELECT 1 FROM seen_listings WHERE dedup_key = ?", (dedup_key,)
    ).fetchone()
    return row is not None


def mark_seen(
    conn: sqlite3.Connection,
    dedup_key: str,
    listing_id: str = "",
    url: str = "",
    title: str = "",
    price: int = 0,
    source: str = "",
    notified: bool = False,
) -> None:
    """Mark a listing as seen."""
    conn.execute(
        """INSERT OR IGNORE INTO seen_listings
           (dedup_key, listing_id, url, title, price, source, notified)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (dedup_key, listing_id, url, title, price, source, int(notified)),
    )
    conn.commit()


def is_first_run(conn: sqlite3.Connection) -> bool:
    """Check if this is the first run (no seed done yet)."""
    row = conn.execute(
        "SELECT value FROM run_metadata WHERE key = 'seeded'"
    ).fetchone()
    return row is None


def mark_seeded(conn: sqlite3.Connection) -> None:
    """Mark that initial seeding is complete."""
    conn.execute(
        "INSERT OR REPLACE INTO run_metadata (key, value) VALUES ('seeded', '1')"
    )
    conn.commit()


def reset_state(db_path: Optional[str] = None) -> None:
    """Delete the state database."""
    path = db_path or _get_db_path()
    if os.path.exists(path):
        os.remove(path)


def get_seen_count(conn: sqlite3.Connection) -> int:
    """Get the total number of seen listings."""
    row = conn.execute("SELECT COUNT(*) FROM seen_listings").fetchone()
    return row[0] if row else 0
