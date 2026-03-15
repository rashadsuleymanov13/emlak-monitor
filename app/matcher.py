"""Main matching engine - coordinates adapters, filters, state, and notifications."""

import logging
from typing import List

from app.adapters import ALL_ADAPTERS
from app.config import config
from app.filters import listing_matches
from app.models import Listing
from app.notifier import send_notification
from app.state import (
    init_db,
    get_dedup_key,
    is_seen,
    mark_seen,
    is_first_run,
    mark_seeded,
    get_seen_count,
)

logger = logging.getLogger(__name__)


def run_monitor(dry_run: bool = False) -> dict:
    """
    Main monitoring loop.

    1. Fetch listings from all adapters
    2. Filter listings
    3. Check state for new listings
    4. Send notifications for new matches
    5. Update state

    Returns stats dict.
    """
    conn = init_db()
    first_run = is_first_run(conn)
    stats = {
        "total_fetched": 0,
        "total_matched": 0,
        "new_listings": 0,
        "notifications_sent": 0,
        "errors": 0,
        "seeding": first_run,
    }

    if first_run:
        logger.info("=== FIRST RUN: Seeding existing listings (no notifications) ===")
    else:
        logger.info("=== Checking for new listings ===")

    all_matched: List[Listing] = []
    filter_stats: dict = {}

    for adapter_cls in ALL_ADAPTERS:
        adapter = adapter_cls()
        logger.info(f"Fetching from {adapter.name}...")

        try:
            listings = adapter.fetch_listings()
            stats["total_fetched"] += len(listings)
            logger.info(f"  Got {len(listings)} listings from {adapter.name}")
        except Exception as e:
            logger.error(f"  Error fetching from {adapter.name}: {e}")
            stats["errors"] += 1
            continue

        for listing in listings:
            if listing_matches(listing, config, log_stats=filter_stats):
                stats["total_matched"] += 1
                dedup_key = get_dedup_key(
                    listing.listing_id, listing.url,
                    listing.title, listing.price, listing.area
                )

                if not is_seen(conn, dedup_key):
                    if first_run:
                        # First run: seed without notification
                        mark_seen(
                            conn, dedup_key,
                            listing_id=listing.listing_id,
                            url=listing.url,
                            title=listing.title,
                            price=listing.price or 0,
                            source=listing.source,
                            notified=False,
                        )
                        logger.info(f"  [SEED] {listing.title} - {listing.price} AZN")
                    else:
                        # Not first run: this is a NEW listing
                        stats["new_listings"] += 1
                        all_matched.append(listing)
                        logger.info(f"  [NEW] {listing.title} - {listing.price} AZN")

                        if send_notification(listing, dry_run=dry_run):
                            stats["notifications_sent"] += 1

                        mark_seen(
                            conn, dedup_key,
                            listing_id=listing.listing_id,
                            url=listing.url,
                            title=listing.title,
                            price=listing.price or 0,
                            source=listing.source,
                            notified=True,
                        )

    if first_run:
        mark_seeded(conn)
        logger.info(f"Seeding complete. {get_seen_count(conn)} listings seeded.")

    conn.close()

    if filter_stats:
        logger.info(f"Filter rejections: {filter_stats}")

    logger.info(
        f"Stats: fetched={stats['total_fetched']}, "
        f"matched={stats['total_matched']}, "
        f"new={stats['new_listings']}, "
        f"notified={stats['notifications_sent']}, "
        f"errors={stats['errors']}"
    )

    return stats
