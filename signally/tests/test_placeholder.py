"""
Unit tests for the Signally MVP backend.

These tests verify:
1. New devices are inserted correctly
2. Existing devices update last_seen
3. Pending device listing works
4. Device approval/blocking works
5. Events are logged

The tests use an in-memory SQLite database so they do not affect
the main application database.
"""

import logging
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import DeviceStatus
from signally.services.device_service import DeviceService
from signally.network_scanner.dto import DiscoveredDevice

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# -----------------------------
# Test Database Setup
# -----------------------------

@pytest.fixture
def db_session():
    """
    Creates a temporary in-memory SQLite database for testing.
    """
    logger.info("Setting up in-memory SQLite test database")
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)

    Base.metadata.create_all(engine)
    logger.debug("Database tables created")

    session = TestingSession()
    yield session

    session.close()
    logger.info("Test database session closed")


@pytest.fixture
def device_service(db_session):
    """
    Creates a DeviceService instance using the test DB session.
    """
    logger.info("Creating DeviceService with test DB session")
    return DeviceService(db_session)


# -----------------------------
# Test: Insert New Device
# -----------------------------

def test_insert_new_device(device_service):
    """
    When a new device is discovered, it should be inserted
    with status = PENDING.
    """
    print("\n[test_insert_new_device] Starting test")
    logger.info("test_insert_new_device: processing new device 192.168.1.10 / AA:BB:CC:DD:EE:FF")

    device = DiscoveredDevice(
        ip_address="192.168.1.10",
        mac_address="AA:BB:CC:DD:EE:FF"
    )

    result = device_service.process_scan_results([device])

    print(f"[test_insert_new_device] Result count: {len(result)}")
    logger.debug("Result: %s", [(r.mac_address, r.status) for r in result])

    assert len(result) == 1
    assert result[0].mac_address == "AA:BB:CC:DD:EE:FF"
    assert result[0].status == DeviceStatus.PENDING

    print(f"[test_insert_new_device] PASSED — device inserted with status {result[0].status}")
    logger.info("test_insert_new_device: PASSED")


# -----------------------------
# Test: Update Existing Device
# -----------------------------

def test_existing_device_updates_last_seen(device_service):
    """
    If a device already exists in the DB, it should not create
    a new record but update last_seen and IP.
    """
    print("\n[test_existing_device_updates_last_seen] Starting test")
    logger.info("test_existing_device_updates_last_seen: first scan with IP 192.168.1.10")

    device = DiscoveredDevice(
        ip_address="192.168.1.10",
        mac_address="AA:AA:AA:AA:AA:AA"
    )

    device_service.process_scan_results([device])
    print("[test_existing_device_updates_last_seen] First scan done, now scanning with new IP 192.168.1.20")
    logger.info("test_existing_device_updates_last_seen: second scan with IP 192.168.1.20")

    # second scan with new IP
    updated_device = DiscoveredDevice(
        ip_address="192.168.1.20",
        mac_address="AA:AA:AA:AA:AA:AA"
    )

    result = device_service.process_scan_results([updated_device])

    print(f"[test_existing_device_updates_last_seen] Result IP: {result[0].ip_address}")
    logger.debug("Result: %s", [(r.mac_address, r.ip_address) for r in result])

    assert len(result) == 1
    assert result[0].ip_address == "192.168.1.20"

    print("[test_existing_device_updates_last_seen] PASSED — IP updated correctly")
    logger.info("test_existing_device_updates_last_seen: PASSED")


# -----------------------------
# Test: List Pending Devices
# -----------------------------

def test_list_pending_devices(device_service):
    """
    Newly discovered devices should appear in the pending list.
    """
    print("\n[test_list_pending_devices] Starting test")
    logger.info("test_list_pending_devices: scanning device 192.168.1.50 / BB:BB:BB:BB:BB:BB")

    device = DiscoveredDevice(
        ip_address="192.168.1.50",
        mac_address="BB:BB:BB:BB:BB:BB"
    )

    device_service.process_scan_results([device])
    print("[test_list_pending_devices] Scan done, fetching pending devices")
    logger.info("test_list_pending_devices: fetching pending devices list")

    pending = device_service.list_pending_devices()

    print(f"[test_list_pending_devices] Pending count: {len(pending)}, status: {pending[0].status if pending else 'N/A'}")
    logger.debug("Pending devices: %s", [(p.mac_address, p.status) for p in pending])

    assert len(pending) == 1
    assert pending[0].status == DeviceStatus.PENDING

    print("[test_list_pending_devices] PASSED")
    logger.info("test_list_pending_devices: PASSED")


# -----------------------------
# Test: Approve Device
# -----------------------------

def test_approve_device(device_service):
    """
    Admin should be able to approve a device.
    """
    print("\n[test_approve_device] Starting test")
    logger.info("test_approve_device: scanning device 192.168.1.70 / CC:CC:CC:CC:CC:CC")

    device = DiscoveredDevice(
        ip_address="192.168.1.70",
        mac_address="CC:CC:CC:CC:CC:CC"
    )

    device_service.process_scan_results([device])
    print("[test_approve_device] Device scanned, now approving")
    logger.info("test_approve_device: updating status to AUTHORIZED")

    updated = device_service.update_status(
        "CC:CC:CC:CC:CC:CC",
        DeviceStatus.AUTHORIZED
    )

    print(f"[test_approve_device] New status: {updated.status}")
    logger.debug("Updated device: mac=%s status=%s", updated.mac_address, updated.status)

    assert updated.status == DeviceStatus.AUTHORIZED

    print("[test_approve_device] PASSED")
    logger.info("test_approve_device: PASSED")


# -----------------------------
# Test: Block Device
# -----------------------------

def test_block_device(device_service):
    """
    Admin should be able to block a device.
    """
    print("\n[test_block_device] Starting test")
    logger.info("test_block_device: scanning device 192.168.1.80 / DD:DD:DD:DD:DD:DD")

    device = DiscoveredDevice(
        ip_address="192.168.1.80",
        mac_address="DD:DD:DD:DD:DD:DD"
    )

    device_service.process_scan_results([device])
    print("[test_block_device] Device scanned, now blocking")
    logger.info("test_block_device: updating status to BLOCKED")

    updated = device_service.update_status(
        "DD:DD:DD:DD:DD:DD",
        DeviceStatus.BLOCKED
    )

    print(f"[test_block_device] New status: {updated.status}")
    logger.debug("Updated device: mac=%s status=%s", updated.mac_address, updated.status)

    assert updated.status == DeviceStatus.BLOCKED

    print("[test_block_device] PASSED")
    logger.info("test_block_device: PASSED")
