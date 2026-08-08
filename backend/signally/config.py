"""
Central configuration for Signally.

This file keeps all tunable values in one place so the system can later move
from local demo mode to Raspberry Pi + real CSI + real frontend integration
without changing business logic code.
"""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# Database
DATABASE_URL = os.getenv("SIGNALLY_DATABASE_URL", "sqlite:///signally.db")

# Auth / JWT
JWT_SECRET = os.getenv("SIGNALLY_JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("SIGNALLY_JWT_EXPIRE_HOURS", "168"))  # 7 days

#  ARP scanning
DEFAULT_SCAN_TARGET = os.getenv("SIGNALLY_DEFAULT_SCAN_TARGET", "192.168.1.0/24")
DEFAULT_SCAN_TIMEOUT = int(os.getenv("SIGNALLY_DEFAULT_SCAN_TIMEOUT", "2"))

# Presence logic
# A device is considered "currently present" if it was seen in the last X seconds.
PRESENCE_WINDOW_SECONDS = int(os.getenv("SIGNALLY_PRESENCE_WINDOW_SECONDS", "30"))
LOCAL_ARP_SCAN_ENABLED = _env_bool("SIGNALLY_LOCAL_ARP_SCAN_ENABLED", True)
CURRENT_UNKNOWN_WINDOW_SECONDS = int(os.getenv("SIGNALLY_CURRENT_UNKNOWN_WINDOW_SECONDS", "30"))
ADMIN_REVIEW_GRACE_SECONDS = int(os.getenv("SIGNALLY_ADMIN_REVIEW_GRACE_SECONDS", "30"))

# Monitoring loop
MONITOR_INTERVAL_SECONDS = int(os.getenv("SIGNALLY_MONITOR_INTERVAL_SECONDS", "10"))
AUTO_START_MONITORING = _env_bool("SIGNALLY_AUTO_START_MONITORING", True)
ALERT_COOLDOWN_SECONDS = int(os.getenv("SIGNALLY_ALERT_COOLDOWN_SECONDS", "60"))

# Guest approval window
GUEST_APPROVAL_HOURS = int(os.getenv("SIGNALLY_GUEST_APPROVAL_HOURS", "24"))

# WIFI probing 
UNASSOCIATED_IP_ADDRESS = os.getenv("SIGNALLY_UNASSOCIATED_IP_ADDRESS", "UNASSOCIATED")
AUTO_START_WIFI_PROBING = _env_bool("SIGNALLY_AUTO_START_WIFI_PROBING", True)
WIFI_PROBING_INTERFACE = os.getenv("SIGNALLY_WIFI_PROBING_INTERFACE", "wlan1")
WIFI_PROBING_MOCK_MODE = _env_bool("SIGNALLY_WIFI_PROBING_MOCK_MODE", False)
WIFI_PROBING_FALLBACK_TO_MOCK = _env_bool("SIGNALLY_WIFI_PROBING_FALLBACK_TO_MOCK", True)

# CSI. Real CSI is intentionally opt-in until nexmon hardware is capturing.
CSI_REAL_PROVIDER_ENABLED = _env_bool("SIGNALLY_CSI_REAL_PROVIDER_ENABLED", False)
# Listen on every local interface because nexmon broadcasts frames on wlan0.
CSI_UDP_IP = os.getenv("SIGNALLY_CSI_UDP_IP", "0.0.0.0")
CSI_UDP_PORT = int(os.getenv("SIGNALLY_CSI_UDP_PORT", "5500"))
# Rolling window (frame count) the temporal variance is computed over.
CSI_VARIANCE_WINDOW = int(os.getenv("SIGNALLY_CSI_VARIANCE_WINDOW", "50"))
# Motion is flagged when the variance metric exceeds baseline * factor.
# Calibrate against a real empty-room baseline once hardware is running.
CSI_BASELINE_FACTOR = float(os.getenv("SIGNALLY_CSI_BASELINE_FACTOR", "1.3"))
# Frames to observe (assumed empty room) before any detection is emitted.
CSI_BASELINE_WARMUP = int(os.getenv("SIGNALLY_CSI_BASELINE_WARMUP", "30"))
# Outlier threshold (in MADs) for the per-frame Hampel filter.
CSI_HAMPEL_SIGMA = float(os.getenv("SIGNALLY_CSI_HAMPEL_SIGMA", "3.0"))
CSI_STALE_AFTER_SECONDS = float(os.getenv("SIGNALLY_CSI_STALE_AFTER_SECONDS", "3"))
CSI_DETECTION_HOLD_SECONDS = float(os.getenv("SIGNALLY_CSI_DETECTION_HOLD_SECONDS", "15"))
CSI_WARMUP_SECONDS = float(os.getenv("SIGNALLY_CSI_WARMUP_SECONDS", "3"))

# Laptop ARP ingestion over the private USB link.
ARP_INGEST_TOKEN = os.getenv("SIGNALLY_ARP_INGEST_TOKEN", "")
ARP_INGEST_MAX_AGE_SECONDS = int(os.getenv("SIGNALLY_ARP_INGEST_MAX_AGE_SECONDS", "30"))

EVENT_DEVICE_DELETED = "DEVICE_DELETED"
EVENT_GUEST_APPROVAL_EXPIRED = "GUEST_APPROVAL_EXPIRED"
EVENT_SECURITY_MODE_CHANGED = "SECURITY_MODE_CHANGED"

EVENT_WIFI_PROBING_STARTED = "WIFI_PROBING_STARTED"
EVENT_WIFI_PROBING_STOPPED = "WIFI_PROBING_STOPPED"
EVENT_WIFI_PROBING_ERROR = "WIFI_PROBING_ERROR"
EVENT_WIFI_PROBE_NEARBY_ACTIVITY = "WIFI_PROBE_NEARBY_ACTIVITY"

WIFI_PROBING_RECENT_EVENT_LIMIT = int(
    os.getenv("SIGNALLY_WIFI_PROBING_RECENT_EVENT_LIMIT", "500")
)

WIFI_PROBING_STRONG_RSSI_MIN = int(
    os.getenv("SIGNALLY_WIFI_PROBING_STRONG_RSSI_MIN", "-60")
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
