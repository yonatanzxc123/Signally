"""
Mock Wi-Fi probe provider for demos and tests.
"""

from typing import List, Optional

from signally.network_scanner.dto import DiscoveredDevice


class MockWifiProbeProvider:
    def __init__(self, visible_devices: Optional[List[DiscoveredDevice]] = None) -> None:
        self._visible_devices = visible_devices or []

    def scan_devices(
        self,
        target_cidr: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> List[DiscoveredDevice]:
        return list(self._visible_devices)

    def set_visible_devices(self, devices: List[DiscoveredDevice]) -> None:
        self._visible_devices = list(devices)

    def clear_visible_devices(self) -> None:
        self._visible_devices = []

    def add_visible_device(self, ip_address: str, mac_address: str) -> None:
        self._visible_devices.append(
            DiscoveredDevice(ip_address=ip_address, mac_address=mac_address.upper())
        )