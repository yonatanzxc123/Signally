"""
DTOs for Wi-Fi probing detections.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from signally.utils.time_utils import utc_now


@dataclass
class WifiProbeDetection:
    mac_address: str
    frame_type: str
    seen_at: datetime = field(default_factory=utc_now)
    ssid: Optional[str] = None
    rssi: Optional[int] = None
    interface: Optional[str] = None
    channel: Optional[int] = None
