"""Push notification via ntfy.sh."""

import httpx
import logging

from app.config import config
from app.models import Listing

logger = logging.getLogger(__name__)


def format_notification(listing: Listing) -> str:
    """Format a listing into a mobile-friendly notification message."""
    parts = [
        f"🏠 {listing.source.upper()}",
        f"📋 {listing.title}",
    ]
    if listing.price is not None:
        parts.append(f"💰 {listing.price:,} {listing.currency}")
    if listing.area is not None:
        parts.append(f"📐 {listing.area} m²")
    if listing.floor is not None and listing.total_floors is not None:
        parts.append(f"🏢 Mərtəbə: {listing.floor}/{listing.total_floors}")
    elif listing.floor is not None:
        parts.append(f"🏢 Mərtəbə: {listing.floor}")
    if listing.location:
        parts.append(f"📍 {listing.location}")
    if listing.has_title_deed:
        parts.append("✅ Kupça var")
    if listing.is_mortgage_ready:
        parts.append("✅ İpoteka mümkündür")
    parts.append(f"🔗 {listing.url}")
    return "\n".join(parts)


def send_notification(listing: Listing, dry_run: bool = False) -> bool:
    """Send push notification for a listing via ntfy."""
    message = format_notification(listing)
    title = f"Yeni elan: {listing.source}"

    if dry_run:
        logger.info(f"[DRY-RUN] Would send notification:\n{message}")
        return True

    url = f"{config.ntfy_url}/{config.ntfy_topic}"
    try:
        response = httpx.post(
            url,
            content=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": "high",
                "Tags": "house",
            },
            timeout=10.0,
        )
        if response.status_code == 200:
            logger.info(f"Notification sent for: {listing.title}")
            return True
        else:
            logger.error(f"ntfy returned {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False
