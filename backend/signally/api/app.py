"""
FastAPI application for Signally.

Current backend focus:
- device/admin endpoints
- event endpoints
- ARP scan endpoint
- Wi-Fi probing endpoints
- simple CSI flag endpoint (to be changed)
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
import threading
import time
from signally.config import MONITOR_INTERVAL_SECONDS
from signally.db.init_db import initialize_database
from signally.network_scanner.scanner import NetworkScanner
from signally.wifi_probing.wifi_probing_service import WifiProbingService


from signally.api.dependencies import (
    build_services,
    csi_provider,
    get_db_session,
    wifi_probing_state,
)
from signally.models.correlation_models import CorrelationContext
from signally.api.schemas import (
    DeviceResponse,
    EventResponse,
    MessageResponse,
    SetCsiPresenceRequest,
    WifiProbingStartRequest,
    WifiProbingStatusResponse,
)


def run_background_monitor():
    """ Background thread: Runs ARP, gathers Probes, and evaluates Correlation. """
    while True:
        try:
            session = get_db_session()
            scanner = NetworkScanner()
            discovered = scanner.scan()
            
            services = build_services(session)
            services["device_service"].process_scan_results(discovered)
            
            # --- CORRELATION EVALUATION ---
            csi_detected = csi_provider.is_presence_detected()
            connected_presence = services["presence_service"].get_presence_snapshot()
            nearby_devices = WifiProbingService(session).list_recent_devices(limit=50)
            
            context = CorrelationContext(
                csi_presence_detected=csi_detected,
                nearby_device_count=len(nearby_devices),
                connected_presence=connected_presence
            )
            
            decision = services["correlation_service"].evaluate(context)
            
            if decision.decision == "ALERT":
                services["alert_service"].raise_unauthorized_presence_alert()
            elif decision.decision == "HIGH_ALERT":
                services["alert_service"].raise_blocked_device_alert()
                
            session.close()
        except Exception as e:
            print(f"Monitor Loop Error: {e}")
        
        time.sleep(MONITOR_INTERVAL_SECONDS)


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
    
    # 1. Start the ARP & Correlation background loop
    threading.Thread(target=run_background_monitor, daemon=True).start()
    
    # 2. Auto-start the Wi-Fi Probing Layer (Layer 2)
    # Using mock_mode=True until we  getsthe physical Wi-Fi adapter
    try:
        wifi_probing_state.start(interface=None, mock_mode=True)
        print("[STARTUP] Layer 2 Wi-Fi Probing started in MOCK mode.")
    except Exception as e:
        print(f"[STARTUP] Could not start Wi-Fi probing: {e}")


@app.get("/health", response_model=MessageResponse)
def health() -> MessageResponse:
    return MessageResponse(message="Signally API is running.")


@app.post("/scan", response_model=list[DeviceResponse])
def scan_network():
    session = get_db_session()
    try:
        scanner = NetworkScanner()
        discovered = scanner.scan()

        services = build_services(session)
        processed = services["device_service"].process_scan_results(discovered)

        return [to_device_response(device) for device in processed]
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


@app.get("/events", response_model=list[EventResponse])
def list_events(limit: int = 50):
    session = get_db_session()
    try:
        services = build_services(session)
        events = services["event_service"].list_recent_events(limit=limit)
        return [to_event_response(event) for event in events]
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


@app.post("/wifi_probing/mock-detection", response_model=MessageResponse)
def add_mock_wifi_probe_detection(
    mac_address: str,
    ssid: Optional[str] = None,
    rssi: Optional[int] = None,
    frame_type: str = "probe_req",
    channel: Optional[int] = None,
):
    try:
        wifi_probing_state.add_mock_detection(
            mac_address=mac_address,
            ssid=ssid,
            rssi=rssi,
            frame_type=frame_type,
            channel=channel,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return MessageResponse(message="Mock Wi-Fi probing detection added.")


@app.post("/csi/set", response_model=MessageResponse)
def set_csi_presence(request: SetCsiPresenceRequest):
    csi_provider.set_detected(request.detected)
    return MessageResponse(message="CSI presence set to {0}.".format(request.detected))


@app.get("/csi/status")
def get_csi_status():
    return {
        "presence_detected": csi_provider.is_presence_detected(),
        "presence_strength": csi_provider.get_presence_strength(),
    }

@app.get("/nearby/devices", response_model=list[DeviceResponse])
def list_nearby_devices(limit: int = 50):
    """ Instructor Requirement: API to get nearby unassociated devices """
    session = get_db_session()
    try:
        service = WifiProbingService(session)
        devices = service.list_recent_devices(limit=limit)
        return [to_device_response(device) for device in devices]
    finally:
        session.close()

@app.get("/system/state", response_model=SystemStateResponse)
def get_system_state():
    """ Frontend requirement: Gets the current correlated state """
    session = get_db_session()
    try:
        services = build_services(session)
        csi_detected = csi_provider.is_presence_detected()
        connected_presence = services["presence_service"].get_presence_snapshot()
        nearby_devices = WifiProbingService(session).list_recent_devices(limit=50)
        
        context = CorrelationContext(
            csi_presence_detected=csi_detected,
            nearby_device_count=len(nearby_devices),
            connected_presence=connected_presence
        )
        
        decision = services["correlation_service"].evaluate(context)
        
        return SystemStateResponse(
            csi_presence_detected=csi_detected,
            approved_user_present=connected_presence.approved_user_present,
            decision=decision.decision,
            reason=decision.reason,
            present_devices=[to_device_response(d) for d in connected_presence.connected_devices]
        )
    finally:
        session.close()

@app.post("/monitoring/run-cycle", response_model=MonitoringCycleResponse)
def run_monitoring_cycle():
    """ Frontend requirement: Manually trigger a full cycle """
    session = get_db_session()
    try:
        scanner = NetworkScanner()
        discovered = scanner.scan()
        services = build_services(session)
        services["device_service"].process_scan_results(discovered)
        
        csi_detected = csi_provider.is_presence_detected()
        connected_presence = services["presence_service"].get_presence_snapshot()
        nearby_devices = WifiProbingService(session).list_recent_devices(limit=50)
        
        context = CorrelationContext(
            csi_presence_detected=csi_detected,
            nearby_device_count=len(nearby_devices),
            connected_presence=connected_presence
        )
        decision = services["correlation_service"].evaluate(context)
        
        return MonitoringCycleResponse(
            csi_presence_detected=csi_detected,
            approved_user_present=connected_presence.approved_user_present,
            decision=decision.decision,
            reason=decision.reason,
            processed_devices_count=len(discovered),
            present_devices_count=len(connected_presence.connected_devices),
            authorized_devices_count=len(connected_presence.authorised_connected_devices),
            pending_devices_count=len(connected_presence.pending_connected_devices),
            blocked_devices_count=len(connected_presence.blocked_connected_devices)
        )
    finally:
        session.close()