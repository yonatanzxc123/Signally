from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import Device
from signally.models.event import Event
from signally.services.device_service import DeviceService
from signally.wifi_probing.dto import WifiProbeDetection
import signally.wifi_probing.wifi_probing_service as wifi_probing_module
from signally.wifi_probing.wifi_probing_service import WifiProbingService


def build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_weak_probe_does_not_create_device(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "NETWORK_SSID", None)
    monkeypatch.setattr(wifi_probing_module, "WIFI_PROBING_STRONG_RSSI_MIN", -60)
    session = build_session()
    service = WifiProbingService(session)

    result = service.handle_detection(
        WifiProbeDetection(
            mac_address="AA:BB:CC:DD:EE:01",
            frame_type="probe_req",
            ssid="HomeWiFi",
            rssi=-75,
        )
    )

    assert result is None
    assert session.query(Device).count() == 0


def test_probe_without_rssi_does_not_create_device(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "NETWORK_SSID", None)
    session = build_session()
    service = WifiProbingService(session)

    result = service.handle_detection(
        WifiProbeDetection(
            mac_address="AA:BB:CC:DD:EE:02",
            frame_type="probe_req",
            ssid="HomeWiFi",
            rssi=None,
        )
    )

    assert result is None
    assert session.query(Device).count() == 0


def test_strong_probe_creates_device(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "NETWORK_SSID", None)
    monkeypatch.setattr(wifi_probing_module, "WIFI_PROBING_STRONG_RSSI_MIN", -60)
    session = build_session()
    service = WifiProbingService(session)

    result = service.handle_detection(
        WifiProbeDetection(
            mac_address="AA:BB:CC:DD:EE:03",
            frame_type="probe_req",
            ssid="HomeWiFi",
            rssi=-55,
        )
    )

    assert result is not None
    assert result.mac_address == "AA:BB:CC:DD:EE:03"
    assert session.query(Device).count() == 1
    assert session.query(Event).count() == 1


def test_strong_probe_seen_again_logs_event(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "NETWORK_SSID", None)
    monkeypatch.setattr(wifi_probing_module, "WIFI_PROBING_STRONG_RSSI_MIN", -60)
    session = build_session()
    service = WifiProbingService(session)

    detection = WifiProbeDetection(
        mac_address="AA:BB:CC:DD:EE:04",
        frame_type="probe_req",
        ssid="HomeWiFi",
        rssi=-55,
    )

    service.handle_detection(detection)
    result = service.handle_detection(detection)

    assert result is not None
    assert session.query(Device).count() == 1
    assert session.query(Event).count() == 2


def test_probe_update_does_not_clear_existing_ip(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "NETWORK_SSID", None)
    monkeypatch.setattr(wifi_probing_module, "WIFI_PROBING_STRONG_RSSI_MIN", -60)
    session = build_session()
    device_service = DeviceService(session)
    service = WifiProbingService(session)

    device_service.upsert_seen_device("AA:BB:CC:DD:EE:05", "192.168.1.25")

    result = service.handle_detection(
        WifiProbeDetection(
            mac_address="AA:BB:CC:DD:EE:05",
            frame_type="probe_req",
            ssid="HomeWiFi",
            rssi=-55,
        )
    )

    assert result is not None
    assert result.ip_address == "192.168.1.25"
