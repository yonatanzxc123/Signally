"""
Wi-Fi probe provider.
"""

from typing import List, Optional

from signally.config import DEFAULT_SCAN_TARGET, DEFAULT_SCAN_TIMEOUT
from signally.network_scanner.dto import DiscoveredDevice
from signally.network_scanner.scanner import NetworkScanner


class WifiProbeProvider:
    def __init__(
        self,
        scanner: Optional[NetworkScanner] = None,
        default_target: str = DEFAULT_SCAN_TARGET,
        default_timeout: int = DEFAULT_SCAN_TIMEOUT,
    ) -> None:
        self.scanner = scanner or NetworkScanner()
        self.default_target = default_target
        self.default_timeout = default_timeout

    def scan_devices(
        self,
        target_cidr: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> List[DiscoveredDevice]:
        effective_target = target_cidr or self.default_target
        effective_timeout = timeout if timeout is not None else self.default_timeout
        return self.scanner.scan(effective_target, timeout=effective_timeout)