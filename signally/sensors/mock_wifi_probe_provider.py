"""
Mock Wi-Fi probe provider for demos and tests.

This provider lets us simulate visible devices without depending on a real
network scan, which is very useful before hardware is ready.
"""

from __future__ import annotations

from typing import List

from signally.network_scanner.dto import DiscoveredDevice


class MockWifiProbeProvider:
    """
    Mock provider with manually controlled visible devices.
    """

    def __init__(self, visible_devices: list[DiscoveredDevice] | None = None) -> None:
        self._visible_devices = visible_devices or []

    def scan_devices(
        self,
        target_cidr: str | None = None,
        timeout: int | None = None,
    ) -> List[DiscoveredDevice]:
        """
        Return the currently simulated visible devices.
        The target and timeout parameters are accepted for API compatibility.
        """
        return list(self._visible_devices)

    def set_visible_devices(self, devices: list[DiscoveredDevice]) -> None:
        self._visible_devices = list(devices)

    def clear_visible_devices(self) -> None:
        self._visible_devices = []

    def add_visible_device(self, ip_address: str, mac_address: str) -> None:
        self._visible_devices.append(
            DiscoveredDevice(ip_address=ip_address, mac_address=mac_address.upper())
        )