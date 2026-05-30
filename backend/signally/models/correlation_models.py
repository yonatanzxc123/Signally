"""
Structured models for three-layer correlation.
"""

from dataclasses import dataclass, field
from typing import List

from signally.models.device import Device


@dataclass
class ConnectedPresenceSnapshot:
    connected_devices: List[Device] = field(default_factory=list)
    authorised_connected_devices: List[Device] = field(default_factory=list)
    pending_connected_devices: List[Device] = field(default_factory=list)
    blocked_connected_devices: List[Device] = field(default_factory=list)

    @property
    def approved_user_present(self) -> bool:
        return len(self.authorised_connected_devices) > 0


@dataclass
class CorrelationContext:
    csi_presence_detected: bool
    nearby_device_count: int
    connected_presence: ConnectedPresenceSnapshot


@dataclass
class CorrelationDecision:
    decision: str
    severity: str
    reason: str
    csi_presence_detected: bool
    nearby_device_count: int
    approved_user_present: bool
