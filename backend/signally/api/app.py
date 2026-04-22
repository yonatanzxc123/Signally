"""
FastAPI application for Signally.

This API exposes:
- device/admin endpoints
- event endpoints
- monitoring endpoints
- demo simulation endpoints
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from signally.api.dependencies import (
    build_services,
    get_db_session,
    mock_csi_provider,
    mock_wifi_provider,
    seed_demo_owner_if_missing,
    set_wifi_mode,
    set_csi_mode,
    get_mode_state,
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
    ModeStateResponse,
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


@app.post("/monitoring/run-cycle", response_model=MonitoringCycleResponse)
def run_monitoring_cycle():
    session = get_db_session()
    try:
        services = build_services(session)
        result = services["monitoring_service"].run_cycle()

        return MonitoringCycleResponse(
            csi_presence_detected=result["csi_presence_detected"],
            approved_user_present=result["approved_user_present"],
            decision=result["decision"],
            reason=result["reason"],
            processed_devices_count=result["processed_devices_count"],
            present_devices_count=result["present_devices_count"],
            authorized_devices_count=result["authorized_devices_count"],
            pending_devices_count=result["pending_devices_count"],
            blocked_devices_count=result["blocked_devices_count"],
        )
    finally:
        session.close()


@app.get("/system/state", response_model=SystemStateResponse)
def get_system_state():
    session = get_db_session()
    try:
        services = build_services(session)
        presence_snapshot = services["presence_service"].get_presence_snapshot()
        decision = services["decision_service"].evaluate(
            csi_presence_detected=mock_csi_provider.is_presence_detected(),
            presence_snapshot=presence_snapshot,
        )

        return SystemStateResponse(
            csi_presence_detected=decision.csi_presence_detected,
            approved_user_present=decision.approved_user_present,
            decision=decision.decision,
            reason=decision.reason,
            present_devices=[to_device_response(device) for device in presence_snapshot.present_devices],
        )
    finally:
        session.close()


# -------------------------
# Demo endpoints
# -------------------------

@app.post("/demo/csi/set", response_model=MessageResponse)
def set_csi_presence(request: SetCsiPresenceRequest):
    mock_csi_provider.set_presence_detected(request.detected)
    return MessageResponse(
        message=f"CSI presence set to {request.detected}."
    )


@app.post("/demo/wifi/clear", response_model=MessageResponse)
def clear_wifi_devices():
    mock_wifi_provider.clear_visible_devices()
    return MessageResponse(message="Mock Wi-Fi visible devices cleared.")


@app.post("/demo/wifi/add-device", response_model=MessageResponse)
def add_wifi_device(request: SimulateDeviceRequest):
    mock_wifi_provider.add_visible_device(
        ip_address=request.ip_address,
        mac_address=request.mac_address,
    )
    return MessageResponse(
        message=f"Added visible mock device {request.mac_address} at {request.ip_address}."
    )


@app.post("/demo/wifi/set-owner-home", response_model=MessageResponse)
def set_owner_home():
    mock_wifi_provider.set_visible_devices(
        [
            DiscoveredDevice(
                ip_address="192.168.1.10",
                mac_address="AA:BB:CC:DD:EE:01",
            )
        ]
    )
    return MessageResponse(message="Mock Wi-Fi state set: owner is home.")


@app.post("/demo/wifi/set-owner-away", response_model=MessageResponse)
def set_owner_away():
    mock_wifi_provider.clear_visible_devices()
    return MessageResponse(message="Mock Wi-Fi state set: owner is away.")


@app.post("/demo/wifi/set-friend-arrival", response_model=MessageResponse)
def set_friend_arrival():
    mock_wifi_provider.set_visible_devices(
        [
            DiscoveredDevice(
                ip_address="192.168.1.20",
                mac_address="AA:BB:CC:DD:EE:99",
            )
        ]
    )
    return MessageResponse(message="Mock Wi-Fi state set: friend device arrived.")


@app.post("/demo/setup/approve-owner", response_model=MessageResponse)
def approve_owner_device():
    session = get_db_session()
    try:
        services = build_services(session)
        owner_mac = "AA:BB:CC:DD:EE:01"

        owner = services["device_service"].get_by_mac(owner_mac)
        if owner is None:
            services["device_service"].process_scan_results(
                [
                    DiscoveredDevice(
                        ip_address="192.168.1.10",
                        mac_address=owner_mac,
                    )
                ]
            )

        services["device_service"].update_status(owner_mac, DeviceStatus.AUTHORIZED)
        return MessageResponse(message="Owner device ensured in DB and marked as AUTHORIZED.")
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


@app.get("/modes", response_model=ModeStateResponse)
def get_modes():
    state = get_mode_state()
    return ModeStateResponse(
        wifi_mode=state["wifi_mode"],
        csi_mode=state["csi_mode"],
    )


@app.post("/modes/wifi", response_model=MessageResponse)
def switch_wifi_mode(request: WifiModeRequest):
    try:
        set_wifi_mode(request.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MessageResponse(message="Wi-Fi mode set to {0}.".format(request.mode))


@app.post("/modes/csi", response_model=MessageResponse)
def switch_csi_mode(request: CsiModeRequest):
    try:
        set_csi_mode(request.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MessageResponse(message="CSI mode set to {0}.".format(request.mode))