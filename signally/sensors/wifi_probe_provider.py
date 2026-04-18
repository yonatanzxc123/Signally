"""
Wi-Fi probe provider.

This provider uses the current NetworkScanner as the practical source of
device visibility. Later, if needed, this provider can be replaced by a more
advanced Wi-Fi probing mechanism without changing the business logic layer.
"""

from __future__ import annotations

from typing import List

from signally.config import DEFAULT_SCAN_TARGET, DEFAULT_SCAN_TIMEOUT
from signally.network_scanner.dto import DiscoveredDevice
from signally.network_scanner.scanner import NetworkScanner


class WifiProbeProvider:
    """
    Provider responsible for discovering visible devices through the current
    Wi-Fi / ARP scanning mechanism.
    """

    def __init__(
        self,
        scanner: NetworkScanner | None = None,
        default_target: str = DEFAULT_SCAN_TARGET,
        default_timeout: int = DEFAULT_SCAN_TIMEOUT,
    ) -> None:
        self.scanner = scanner or NetworkScanner()
        self.default_target = default_target
        self.default_timeout = default_timeout

    def scan_devices(
        self,
        target_cidr: str | None = None,
        timeout: int | None = None,
    ) -> List[DiscoveredDevice]:
        """
        Scan for visible devices using the current scanner implementation.
        """
        effective_target = target_cidr or self.default_target
        effective_timeout = timeout if timeout is not None else self.default_timeout
        return self.scanner.scan(effective_target, timeout=effective_timeout)
    
    