"""Data transfer objects for network scanning."""

from dataclasses import dataclass


@dataclass
class DiscoveredDevice:
    """Simple in-memory representation of a discovered device."""

    ip_address: str
    mac_address: str