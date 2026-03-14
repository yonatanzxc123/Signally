"""Data transfer objects for network scanning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DiscoveredDevice:
    """Simple in-memory representation of a discovered device."""

    ip_address: str
    mac_address: str
