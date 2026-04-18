"""
Structured output models for presence and decision logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from signally.models.device import Device

@dataclass
class PresenceSnapshot:
    """
    Snapshot of which devices are currently considered present.
    """
    present_devices: List[Device] = field(default_factory=list)
    present_authorized_devices: List[Device] = field(default_factory=list)
    present_pending_devices: List[Device] = field(default_factory=list)
    present_blocked_devices: List[Device] = field(default_factory=list)

    @property
    def approved_user_present(self) -> bool:
        return len(self.present_authorized_devices) > 0


@dataclass
class DecisionResult:
    """
    Final decision after combining CSI detection and Wi-Fi/device state.
    """
    csi_presence_detected: bool
    approved_user_present: bool
    decision: str
    reason: str

    authorized_devices: List[Device] = field(default_factory=list)
    pending_devices: List[Device] = field(default_factory=list)
    blocked_devices: List[Device] = field(default_factory=list)