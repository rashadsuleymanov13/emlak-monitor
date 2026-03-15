"""Base adapter for real estate sites."""

from abc import ABC, abstractmethod
from typing import List

from app.models import Listing


class BaseAdapter(ABC):
    """Abstract base class for site adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the site."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL of the site."""
        ...

    @abstractmethod
    def fetch_listings(self) -> List[Listing]:
        """Fetch current listings from the site. Returns all available listings."""
        ...
