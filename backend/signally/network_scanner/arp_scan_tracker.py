"""Track laptop ARP scan submissions, replay IDs, and scanner health."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Optional


@dataclass(frozen=True)
class ArpScanStatus:
    healthy: bool
    last_scan_id: Optional[str]
    last_captured_at: Optional[datetime]
    last_received_at: Optional[datetime]
    last_device_count: int


class ArpScanTracker:
    def __init__(self, replay_window: int = 256) -> None:
        self._lock = Lock()
        self._seen = set()
        self._reserved = set()
        self._order = deque(maxlen=replay_window)
        self._last_scan_id = None
        self._last_captured_at = None
        self._last_received_at = None
        self._last_device_count = 0

    def reserve(self, scan_id: str) -> bool:
        with self._lock:
            if scan_id in self._seen or scan_id in self._reserved:
                return False
            self._reserved.add(scan_id)
            return True

    def complete(self, scan_id: str, captured_at: datetime, received_at: datetime, device_count: int) -> None:
        with self._lock:
            self._reserved.discard(scan_id)
            if len(self._order) == self._order.maxlen:
                self._seen.discard(self._order[0])
            self._order.append(scan_id)
            self._seen.add(scan_id)
            self._last_scan_id = scan_id
            self._last_captured_at = captured_at
            self._last_received_at = received_at
            self._last_device_count = device_count

    def release(self, scan_id: str) -> None:
        """Allow a scan to be retried when downstream processing fails."""
        with self._lock:
            self._reserved.discard(scan_id)

    def status(self) -> ArpScanStatus:
        with self._lock:
            return ArpScanStatus(
                healthy=self._last_received_at is not None,
                last_scan_id=self._last_scan_id,
                last_captured_at=self._last_captured_at,
                last_received_at=self._last_received_at,
                last_device_count=self._last_device_count,
            )


arp_scan_tracker = ArpScanTracker()
