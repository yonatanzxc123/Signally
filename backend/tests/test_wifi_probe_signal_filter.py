from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import Device
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
