"""
Structured models for three-layer correlation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from signally.models.device import Device
from signally.models.security_mode import SecurityMode


@dataclass
class ConnectedPresenceSnapshot:
    connected_devices: List[Device] = field(default_factory=list)
    authorised_connected_devices: List[Device] = field(default_factory=list)
    pending_connected_devices: List[Device] = field(default_factory=list)
    blocked_connected_devices: List[Device] = field(default_factory=list)
    admin_connected_devices: List[Device] = field(default_factory=list)
    family_connected_devices: List[Device] = field(default_factory=list)
    guest_connected_devices: List[Device] = field(default_factory=list)

    @property
    def approved_user_present(self) -> bool:
        return len(self.authorised_connected_devices) > 0

    @property
    def admin_present(self) -> bool:
        return len(self.admin_connected_devices) > 0

    @property
    def family_present(self) -> bool:
        return len(self.family_connected_devices) > 0

    @property
    def guest_present(self) -> bool:
        return len(self.guest_connected_devices) > 0


@dataclass
class NearbyPresenceSnapshot:
    nearby_devices: List[Device] = field(default_factory=list)
    unknown_nearby_devices: List[Device] = field(default_factory=list)
    blocked_nearby_devices: List[Device] = field(default_factory=list)
    effective_unknown_nearby_devices: List[Device] = field(default_factory=list)
    ignored_authorized_duplicate_count: int = 0
    first_unknown_seen_at: Optional[datetime] = None
    window_seconds: int = 30

    @property
    def effective_unknown_nearby_count(self) -> int:
        return len(self.effective_unknown_nearby_devices)


@dataclass
class CorrelationContext:
    csi_presence_detected: bool
    nearby_device_count: int
    connected_presence: ConnectedPresenceSnapshot
    nearby_presence: NearbyPresenceSnapshot = field(default_factory=NearbyPresenceSnapshot)
    security_mode: SecurityMode = SecurityMode.HOME


@dataclass
class CorrelationDecision:
    decision: str
    severity: str
    reason: str
    csi_presence_detected: bool
    nearby_device_count: int
    approved_user_present: bool
    security_mode: SecurityMode = SecurityMode.HOME
    admin_present: bool = False
    family_present: bool = False
    guest_present: bool = False
    current_intruder_count: int = 0
    ignored_authorized_duplicate_count: int = 0
    admin_review_grace_active: bool = False
    notification_audience: List[str] = field(default_factory=list)
