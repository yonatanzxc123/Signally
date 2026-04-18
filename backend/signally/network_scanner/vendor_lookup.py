"""MAC vendor lookup and device type classification."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from mac_vendor_lookup import MacLookup, VendorNotFoundError

logger = logging.getLogger(__name__)

_PHONE_VENDOR_KEYWORDS = [
    "apple",
    "samsung",
    "huawei",
    "xiaomi",
    "oneplus",
    "sony mobile",
    "motorola",
    "nokia",
    "htc corporation",
    "oppo",
    "vivo",
    "realme",
    "google",
    "zte",
    "lenovo",
    "lg electronics",
    "fairphone",
    "nothing technology",
]


class VendorLookup:
    def __init__(self) -> None:
        self._mac = MacLookup()

    def get_vendor(self, mac: str) -> Optional[str]:
        try:
            return self._mac.lookup(mac)
        except VendorNotFoundError:
            return None
        except Exception:
            logger.warning("Vendor lookup failed for MAC %s", mac)
            return None

    def get_device_type(self, vendor: Optional[str]) -> str:
        if vendor is None:
            return "UNKNOWN"
        vendor_lower = vendor.lower()
        if any(kw in vendor_lower for kw in _PHONE_VENDOR_KEYWORDS):
            return "PHONE"
        return "UNKNOWN"

    def enrich(self, mac: str) -> Tuple[Optional[str], str]:
        vendor = self.get_vendor(mac)
        device_type = self.get_device_type(vendor)
        return vendor, device_type