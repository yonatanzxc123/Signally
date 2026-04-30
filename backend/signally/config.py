"""
Central configuration for Signally.

This file keeps all tunable values in one place so the system can later move
from local demo mode to Raspberry Pi + real CSI + real frontend integration
without changing business logic code.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional


def _detect_network_ssid() -> Optional[str]:
    try:
        result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=2)
        ssid = result.stdout.strip()
        return ssid if ssid else None
    except Exception:
        return None


NETWORK_SSID: Optional[str] = os.getenv("SIGNALLY_NETWORK_SSID") or _detect_network_ssid()

# Database
DATABASE_URL = os.getenv("SIGNALLY_DATABASE_URL", "sqlite:///signally.db")

#  ARP scanning
DEFAULT_SCAN_TARGET = os.getenv("SIGNALLY_DEFAULT_SCAN_TARGET", "192.168.1.0/24")
DEFAULT_SCAN_TIMEOUT = int(os.getenv("SIGNALLY_DEFAULT_SCAN_TIMEOUT", "2"))

# Presence logic
# A device is considered "currently present" if it was seen in the last X seconds.
PRESENCE_WINDOW_SECONDS = int(os.getenv("SIGNALLY_PRESENCE_WINDOW_SECONDS", "30"))

# Monitoring loop
MONITOR_INTERVAL_SECONDS = int(os.getenv("SIGNALLY_MONITOR_INTERVAL_SECONDS", "10"))

# WIFI probing 
UNASSOCIATED_IP_ADDRESS = os.getenv("SIGNALLY_UNASSOCIATED_IP_ADDRESS", "UNASSOCIATED")

EVENT_DEVICE_DELETED = "DEVICE_DELETED"

EVENT_WIFI_PROBING_STARTED = "WIFI_PROBING_STARTED"
EVENT_WIFI_PROBING_STOPPED = "WIFI_PROBING_STOPPED"
EVENT_WIFI_PROBING_ERROR = "WIFI_PROBING_ERROR"
EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW = "WIFI_PROBE_DEVICE_DISCOVERED_NEW"
EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN = "WIFI_PROBE_DEVICE_SEEN_AGAIN"

WIFI_PROBING_RECENT_EVENT_LIMIT = int(
    os.getenv("SIGNALLY_WIFI_PROBING_RECENT_EVENT_LIMIT", "500")
)



# Event types
EVENT_DEVICE_DISCOVERED_NEW = "DEVICE_DISCOVERED_NEW"
EVENT_DEVICE_SEEN_AGAIN = "DEVICE_SEEN_AGAIN"
EVENT_DEVICE_APPROVED = "DEVICE_APPROVED"
EVENT_DEVICE_BLOCKED = "DEVICE_BLOCKED"

EVENT_APPROVED_USER_PRESENT = "APPROVED_USER_PRESENT"
EVENT_NO_APPROVED_USER_PRESENT = "NO_APPROVED_USER_PRESENT"
EVENT_UNAUTHORIZED_PRESENCE_ALERT = "UNAUTHORIZED_PRESENCE_ALERT"
EVENT_BLOCKED_DEVICE_ALERT = "BLOCKED_DEVICE_ALERT"
EVENT_MONITORING_CYCLE_COMPLETED = "MONITORING_CYCLE_COMPLETED"