from datetime import datetime, timezone

from pydantic import ValidationError

from signally.api.schemas import ArpObservationRequest
from signally.network_scanner.arp_scan_tracker import ArpScanTracker


def test_arp_observation_normalizes_mac_and_ip():
    item = ArpObservationRequest(ip_address="192.168.1.7", mac_address="aa-bb-cc-dd-ee-ff")
    assert item.mac_address == "AA:BB:CC:DD:EE:FF"
    assert item.ip_address == "192.168.1.7"


def test_arp_observation_rejects_invalid_values():
    try:
        ArpObservationRequest(ip_address="not-an-ip", mac_address="not-a-mac")
    except ValidationError:
        pass
    else:
        raise AssertionError("invalid ARP observation was accepted")


def test_scan_tracker_rejects_replayed_scan_id():
    tracker = ArpScanTracker()
    now = datetime.now(timezone.utc)
    assert tracker.reserve("scan-1") is True
    assert tracker.reserve("scan-1") is False
    tracker.complete("scan-1", now, now, 2)
    assert tracker.reserve("scan-1") is False
    assert tracker.status().last_device_count == 2


def test_scan_tracker_allows_retry_after_failed_processing():
    tracker = ArpScanTracker()
    assert tracker.reserve("scan-retry") is True
    tracker.release("scan-retry")
    assert tracker.reserve("scan-retry") is True
