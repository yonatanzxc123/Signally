"""
FastAPI application for Signally.

This API exposes:
- device/admin endpoints
- event endpoints
- monitoring endpoints
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from signally.api.dependencies import (
    build_services,
    get_db_session,
)
from signally.api.schemas import (
    DeviceResponse,
    EventResponse,
    MessageResponse,
    MonitoringCycleResponse,
    SetCsiPresenceRequest,
    SimulateDeviceRequest,
    SystemStateResponse,
    WifiModeRequest,
    CsiModeRequest,
)
from signally.db.init_db import initialize_database
from signally.models.device import DeviceStatus
from signally.network_scanner.dto import DiscoveredDevice
from signally.network_scanner.scanner import NetworkScanner


app = FastAPI(title="Signally API", version="1.0.0")


def to_device_response(device) -> DeviceResponse:
    return DeviceResponse(
        mac_address=device.mac_address,
        ip_address=device.ip_address,
        status=device.status.value if hasattr(device.status, "value") else str(device.status),
        first_seen=device.first_seen,
        last_seen=device.last_seen,
    )


def to_event_response(event) -> EventResponse:
    return EventResponse(
        id=event.id,
        event_type=event.event_type,
        device_mac=event.device_mac,
        details=event.details,
        created_at=event.created_at,
    )


@app.on_event("startup")
def on_startup() -> None:
    initialize_database()
    seed_demo_owner_if_missing()


@app.get("/health", response_model=MessageResponse)
def health() -> MessageResponse:
    return MessageResponse(message="Signally API is running.")


# TEMPORARY: direct ARP scan endpoint used until Raspberry Pi handles scanning.
# Remove this endpoint and wire scan button to POST /monitoring/run-cycle once Pi is integrated.
@app.post("/scan", response_model=list[DeviceResponse])
def scan_network():
    session = get_db_session()
    try:
        scanner = NetworkScanner()
        discovered = scanner.scan()
        services = build_services(session)
        processed = services["device_service"].process_scan_results(discovered)
        return [to_device_response(d) for d in processed]
    finally:
        session.close()


@app.get("/devices", response_model=list[DeviceResponse])
def list_devices():
    session = get_db_session()
    try:
        services = build_services(session)
        devices = services["device_service"].list_all_devices()
        return [to_device_response(device) for device in devices]
    finally:
        session.close()


@app.get("/devices/pending", response_model=list[DeviceResponse])
def list_pending_devices():
    session = get_db_session()
    try:
        services = build_services(session)
        devices = services["admin_manager"].list_pending_devices()
        return [to_device_response(device) for device in devices]
    finally:
        session.close()


@app.post("/devices/{mac_address}/approve", response_model=DeviceResponse)
def approve_device(mac_address: str):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            device = services["admin_manager"].approve_device(mac_address)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return to_device_response(device)
    finally:
        session.close()


@app.post("/devices/{mac_address}/block", response_model=DeviceResponse)
def block_device(mac_address: str):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            device = services["admin_manager"].block_device(mac_address)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return to_device_response(device)
    finally:
        session.close()


@app.get("/events", response_model=list[EventResponse])
def list_events(limit: int = 50):
    session = get_db_session()
    try:
        services = build_services(session)
        events = services["event_service"].list_recent_events(limit=limit)
        return [to_event_response(event) for event in events]
    finally:
        session.close()






@app.delete("/devices/{mac_address}", response_model=MessageResponse)
def delete_device(mac_address: str):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            services["admin_manager"].delete_device(mac_address)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return MessageResponse(message="Device deleted successfully.")
    finally:
        session.close()    



@app.delete("/admin/devices", response_model=MessageResponse)
def clear_all_devices():
    session = get_db_session()
    try:
        services = build_services(session)
        deleted_count = services["admin_manager"].delete_all_devices()
        return MessageResponse(
            message="Deleted {0} device(s) from the database.".format(deleted_count)
        )
    finally:
        session.close()


@app.delete("/admin/events", response_model=MessageResponse)
def clear_all_events():
    session = get_db_session()
    try:
        services = build_services(session)
        deleted_count = services["admin_manager"].delete_all_events()
        return MessageResponse(
            message="Deleted {0} event(s) from the database.".format(deleted_count)
        )
    finally:
        session.close()


@app.delete("/admin/reset", response_model=MessageResponse)
def reset_database_content():
    session = get_db_session()
    try:
        services = build_services(session)
        result = services["admin_manager"].reset_database_content()
        return MessageResponse(
            message="Database reset complete. Deleted {0} device(s) and {1} event(s).".format(
                result["deleted_devices"],
                result["deleted_events"],
            )
        )
    finally:
        session.close()



# Wifi probing endpoints
@app.post("/wifi_probing/start", response_model=MessageResponse)
def start_wifi_probing(request: WifiProbingStartRequest):
    try:
        wifi_probing_state.start(interface=request.interface, mock_mode=request.mock_mode)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MessageResponse(message="Wi-Fi probing started.")


@app.post("/wifi_probing/stop", response_model=MessageResponse)
def stop_wifi_probing():
    wifi_probing_state.stop()
    return MessageResponse(message="Wi-Fi probing stopped.")


@app.get("/wifi_probing/status", response_model=WifiProbingStatusResponse)
def get_wifi_probing_status():
    state = wifi_probing_state.status()
    return WifiProbingStatusResponse(
        running=state["running"],
        interface=state["interface"],
        mock_mode=state["mock_mode"],
        started_at=state["started_at"],
        last_error=state["last_error"],
    )


@app.get("/wifi_probing/devices", response_model=list[DeviceResponse])
def list_wifi_probing_devices(limit: int = 50):
    session = get_db_session()
    try:
        service = WifiProbingService(session)
        devices = service.list_recent_devices(limit=limit)
        return [to_device_response(device) for device in devices]
    finally:
        session.close()

