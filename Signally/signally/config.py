"""
Central configuration for Signally.

This file keeps all tunable values in one place so the system can later move
from local demo mode to Raspberry Pi + real CSI + real frontend integration
without changing business logic code.
"""

from __future__ import annotations

import os

# Database
DATABASE_URL = os.getenv("SIGNALLY_DATABASE_URL", "sqlite:///signally.db")

# Wi-Fi / ARP scanning
DEFAULT_SCAN_TARGET = os.getenv("SIGNALLY_DEFAULT_SCAN_TARGET", "192.168.1.0/24")
DEFAULT_SCAN_TIMEOUT = int(os.getenv("SIGNALLY_DEFAULT_SCAN_TIMEOUT", "2"))

# Presence logic
# A device is considered "currently present" if it was seen in the last X seconds.
PRESENCE_WINDOW_SECONDS = int(os.getenv("SIGNALLY_PRESENCE_WINDOW_SECONDS", "30"))

# Monitoring loop
MONITOR_INTERVAL_SECONDS = int(os.getenv("SIGNALLY_MONITOR_INTERVAL_SECONDS", "10"))

# Demo mode
DEMO_MODE = os.getenv("SIGNALLY_DEMO_MODE", "true").lower() == "true"

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