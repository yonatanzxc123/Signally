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
    assert fingerprint.confidence == 0.45
    assert "WIFI_PROBE_SSIDS" in fingerprint.signals
