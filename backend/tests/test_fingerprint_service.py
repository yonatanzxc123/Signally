from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import Device
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


def test_hostname_can_infer_iphone(monkeypatch):
    session = build_session()
    device = add_device(session)
    service = FingerprintService(session)
    monkeypatch.setattr(service, "_get_vendor", lambda _: None)
    monkeypatch.setattr(service, "_get_hostname", lambda _: "Yoni-iPhone")

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.device_category == "PHONE"
    assert fingerprint.manufacturer == "Apple"
    assert fingerprint.display_name == "Yoni-iPhone"
    assert "HOSTNAME" in fingerprint.signals
    assert fingerprint.confidence >= 0.8


def test_vendor_can_infer_smart_tv(monkeypatch):
    session = build_session()
    device = add_device(session)
    service = FingerprintService(session)
    monkeypatch.setattr(service, "_get_vendor", lambda _: "Roku Inc.")
    monkeypatch.setattr(service, "_get_hostname", lambda _: None)

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.device_category == "TV"
    assert fingerprint.manufacturer == "Roku"
    assert fingerprint.display_name == "Roku Tv"
    assert "MAC_VENDOR" in fingerprint.signals


def test_probe_ssids_hint_phone_when_other_signals_missing(monkeypatch):
    session = build_session()
    device = add_device(session)
    EventService(session).log_event(
        event_type="WIFI_PROBE_DEVICE_DISCOVERED_NEW",
        details="frame_type=probe_req; ssid=HomeWiFi; rssi=-55; interface=; channel=",
        device_mac=device.mac_address,
    )
    service = FingerprintService(session)
    monkeypatch.setattr(service, "_get_vendor", lambda _: None)
    monkeypatch.setattr(service, "_get_hostname", lambda _: None)

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.device_category == "PHONE"
    assert fingerprint.confidence == 0.4
    assert fingerprint.randomized_mac is True
    assert "WIFI_PROBE_SSIDS" in fingerprint.signals


def test_offline_oui_fallback_infers_observed_samsung_phone(monkeypatch):
    session = build_session()
    device = add_device(
        session,
        mac_address="38:8A:06:9A:3B:3C",
        ip_address="10.100.102.21",
    )
    service = FingerprintService(session)
    monkeypatch.setattr(service, "_get_hostname", lambda _: None)

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.manufacturer == "Samsung"
    assert fingerprint.device_category == "PHONE"
    assert fingerprint.display_name == "Samsung Phone"
    assert "MAC_VENDOR" in fingerprint.signals


def test_hostname_hint_overrides_missing_reverse_dns(monkeypatch):
    session = build_session()
    device = add_device(session)
    service = FingerprintService(session)
    monkeypatch.setattr(service, "_get_vendor", lambda _: None)
    monkeypatch.setattr(service, "_get_hostname", lambda _: None)

    service.set_hostname_hint(device.mac_address, "Kitchen-Samsung-TV")
    fingerprint = service.fingerprint_device(device)

    assert fingerprint.device_category == "TV"
    assert fingerprint.manufacturer == "Samsung"
    assert fingerprint.hostname == "Kitchen-Samsung-TV"
    assert "HOSTNAME_HINT" in fingerprint.signals


def test_randomized_mac_is_flagged_and_oui_is_not_trusted(monkeypatch):
    session = build_session()
    device = add_device(
        session,
        mac_address="3A:8A:06:9A:3B:3C",
        ip_address="10.100.102.21",
    )
    service = FingerprintService(session)
    monkeypatch.setattr(service, "_get_hostname", lambda _: None)

    fingerprint = service.fingerprint_device(device)

    assert fingerprint.randomized_mac is True
    assert fingerprint.manufacturer is None
    assert fingerprint.device_category == "UNKNOWN"
    assert fingerprint.display_name == "Randomized MAC Device"
    assert "RANDOMIZED_MAC" in fingerprint.signals
