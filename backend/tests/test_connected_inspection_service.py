from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.services.connected_inspection_service import ConnectedInspectionService


def build_service():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return ConnectedInspectionService(session_factory())


def test_mdns_services_classify_tv():
    service = build_service()

    category, confidence = service._classify_from_mdns(["_googlecast._tcp", "Living Room TV"])

    assert category == "TV"
    assert confidence >= 0.8


def test_mdns_services_classify_printer():
    service = build_service()

    category, confidence = service._classify_from_mdns(["_ipp._tcp", "Office Printer"])

    assert category == "PRINTER"
    assert confidence >= 0.8


def test_nmap_result_classifies_router():
    service = build_service()

    category, confidence = service._classify_from_nmap(
        device_type="router",
        os_name="embedded Linux",
        open_ports=["80/http"],
    )

    assert category == "ROUTER"
    assert confidence >= 0.7
