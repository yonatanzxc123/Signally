from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import Device
from signally.services.connected_inspection_service import ConnectedInspectionResult
from signally.services.event_service import EventService
from signally.services.fingerprint_service import FingerprintService


def build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def add_device(session, mac_address="AA:BB:CC:DD:EE:40", ip_address="192.168.1.40"):
    device = Device(mac_address=mac_address, ip_address=ip_address)
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def test_arp_connected_device_records_primary_layer():
    session = build_session()
    device = add_device(session)
    service = FingerprintService(session)

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.connected is True
    assert fingerprint.primary_layer == "ARP"
    assert fingerprint.confidence >= 0.3
    assert "ARP_CONNECTED" in fingerprint.signals


def test_probe_only_device_has_weaker_primary_layer():
    session = build_session()
    device = add_device(session, ip_address=None)
    service = FingerprintService(session)

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.connected is False
    assert fingerprint.primary_layer == "PROBING"
    assert "ARP_CONNECTED" not in fingerprint.signals


def test_cached_inspection_hostname_can_infer_phone(monkeypatch):
    session = build_session()
    device = add_device(session)
    service = FingerprintService(session)
    monkeypatch.setattr(
        service.inspection_service,
        "get_latest_result",
        lambda _: ConnectedInspectionResult(
            hostname="Yoni-iPhone",
            signals=["MDNS"],
        ),
    )

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.device_category == "PHONE"
    assert fingerprint.display_name == "Yoni-iPhone"
    assert "HOSTNAME" in fingerprint.signals
    assert fingerprint.confidence >= 0.8


def test_cached_connected_inspection_can_infer_smart_tv(monkeypatch):
    session = build_session()
    device = add_device(session)
    service = FingerprintService(session)
    monkeypatch.setattr(
        service.inspection_service,
        "get_latest_result",
        lambda _: ConnectedInspectionResult(
            device_category="TV",
            confidence=0.85,
            hostname="Living-Room-TV",
            mdns_services=["_googlecast._tcp"],
            signals=["MDNS"],
        ),
    )

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.device_category == "TV"
    assert fingerprint.display_name == "Living-Room-TV"
    assert "MDNS" in fingerprint.signals


def test_probe_ssids_hint_phone_when_other_signals_missing(monkeypatch):
    session = build_session()
    device = add_device(session)
    EventService(session).log_event(
        event_type="WIFI_PROBE_DEVICE_DISCOVERED_NEW",
        details="frame_type=probe_req; ssid=HomeWiFi; rssi=-55; interface=; channel=",
        device_mac=device.mac_address,
    )
    service = FingerprintService(session)

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.device_category == "PHONE"
    assert fingerprint.confidence == 0.4
    assert fingerprint.randomized_mac is True
    assert "WIFI_PROBE_SSIDS" in fingerprint.signals


def test_cached_inspection_hostname_can_infer_tv(monkeypatch):
    session = build_session()
    device = add_device(session)
    service = FingerprintService(session)
    monkeypatch.setattr(
        service.inspection_service,
        "get_latest_result",
        lambda _: ConnectedInspectionResult(
            hostname="Kitchen-Samsung-TV",
            signals=["MDNS"],
        ),
    )
    fingerprint = service.fingerprint_device(device)

    assert fingerprint.device_category == "TV"
    assert fingerprint.hostname == "Kitchen-Samsung-TV"
    assert "HOSTNAME" in fingerprint.signals


def test_randomized_mac_is_flagged_and_oui_is_not_trusted(monkeypatch):
    session = build_session()
    device = add_device(
        session,
        mac_address="3A:8A:06:9A:3B:3C",
        ip_address="10.100.102.21",
    )
    service = FingerprintService(session)

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.randomized_mac is True
    assert fingerprint.device_category == "UNKNOWN"
    assert fingerprint.display_name == "Randomized MAC Device"
    assert "RANDOMIZED_MAC" in fingerprint.signals
