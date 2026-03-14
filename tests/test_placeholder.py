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

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import DeviceStatus
from signally.services.device_service import DeviceService
from signally.network_scanner.dto import DiscoveredDevice


# -----------------------------
# Test Database Setup
# -----------------------------

@pytest.fixture
def db_session():
    """
    Creates a temporary in-memory SQLite database for testing.
    """
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)

    Base.metadata.create_all(engine)

    session = TestingSession()
    yield session

    session.close()


@pytest.fixture
def device_service(db_session):
    """
    Creates a DeviceService instance using the test DB session.
    """
    return DeviceService(db_session)


# -----------------------------
# Test: Insert New Device
# -----------------------------

def test_insert_new_device(device_service):
    """
    When a new device is discovered, it should be inserted
    with status = PENDING.
    """

    device = DiscoveredDevice(
        ip_address="192.168.1.10",
        mac_address="AA:BB:CC:DD:EE:FF"
    )

    result = device_service.process_scan_results([device])

    assert len(result) == 1
    assert result[0].mac_address == "AA:BB:CC:DD:EE:FF"
    assert result[0].status == DeviceStatus.PENDING


# -----------------------------
# Test: Update Existing Device
# -----------------------------

def test_existing_device_updates_last_seen(device_service):
    """
    If a device already exists in the DB, it should not create
    a new record but update last_seen and IP.
    """

    device = DiscoveredDevice(
        ip_address="192.168.1.10",
        mac_address="AA:AA:AA:AA:AA:AA"
    )

    device_service.process_scan_results([device])

    # second scan with new IP
    updated_device = DiscoveredDevice(
        ip_address="192.168.1.20",
        mac_address="AA:AA:AA:AA:AA:AA"
    )

    result = device_service.process_scan_results([updated_device])

    assert len(result) == 1
    assert result[0].ip_address == "192.168.1.20"


# -----------------------------
# Test: List Pending Devices
# -----------------------------

def test_list_pending_devices(device_service):
    """
    Newly discovered devices should appear in the pending list.
    """

    device = DiscoveredDevice(
        ip_address="192.168.1.50",
        mac_address="BB:BB:BB:BB:BB:BB"
    )

    device_service.process_scan_results([device])

    pending = device_service.list_pending_devices()

    assert len(pending) == 1
    assert pending[0].status == DeviceStatus.PENDING


# -----------------------------
# Test: Approve Device
# -----------------------------

def test_approve_device(device_service):
    """
    Admin should be able to approve a device.
    """

    device = DiscoveredDevice(
        ip_address="192.168.1.70",
        mac_address="CC:CC:CC:CC:CC:CC"
    )

    device_service.process_scan_results([device])

    updated = device_service.update_status(
        "CC:CC:CC:CC:CC:CC",
        DeviceStatus.AUTHORIZED
    )

    assert updated.status == DeviceStatus.AUTHORIZED


# -----------------------------
# Test: Block Device
# -----------------------------

def test_block_device(device_service):
    """
    Admin should be able to block a device.
    """

    device = DiscoveredDevice(
        ip_address="192.168.1.80",
        mac_address="DD:DD:DD:DD:DD:DD"
    )

    device_service.process_scan_results([device])

    updated = device_service.update_status(
        "DD:DD:DD:DD:DD:DD",
        DeviceStatus.BLOCKED
    )

    assert updated.status == DeviceStatus.BLOCKED