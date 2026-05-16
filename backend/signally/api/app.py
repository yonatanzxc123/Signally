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

from fastapi import FastAPI, Header, HTTPException
import threading
import time
from signally.config import CURRENT_UNKNOWN_WINDOW_SECONDS, MONITOR_INTERVAL_SECONDS
from signally.db.init_db import initialize_database
from signally.network_scanner.scanner import NetworkScanner
from signally.wifi_probing.wifi_probing_service import WifiProbingService
from scapy.all import get_if_list  


from signally.api.dependencies import (
    build_services,
    csi_provider,
    get_db_session,
    wifi_probing_state,
)
from signally.models.correlation_models import CorrelationContext
from signally.api.schemas import (
    ApproveDeviceRequest,
    AssignDeviceRequest,
    DeviceFingerprintResponse,
    DeviceResponse,
    EventResponse,
    MessageResponse,
    ProbeInfoResponse,
    SetDeviceHostnameHintRequest,
    SetCsiPresenceRequest,
    WifiProbingStartRequest,
    WifiProbingStatusResponse,
    SystemStateResponse,
    MonitoringCycleResponse,
    UserCreateRequest,
    UserResponse,
)
from signally.config import (
    EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW,
    EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
)
from signally.models.user import UserRole
from signally.services.fingerprint_service import FingerprintService
from signally.services.user_service import UserService


def run_background_monitor():
    """ Background thread: Runs ARP, gathers Probes, and evaluates Correlation. """
    while True:
        session = None
        try:
            session = get_db_session()
            scanner = NetworkScanner()
            discovered = scanner.scan()
            
            services = build_services(session)
            services["device_service"].process_scan_results(discovered)
            
            # --- CORRELATION EVALUATION ---
            csi_detected = csi_provider.is_presence_detected()
            connected_presence = services["presence_service"].get_presence_snapshot()
            nearby_presence = WifiProbingService(session).get_presence_snapshot(
                connected_presence=connected_presence,
                limit=50,
            )
            
            context = CorrelationContext(
                csi_presence_detected=csi_detected,
                nearby_device_count=len(nearby_presence.nearby_devices),
                connected_presence=connected_presence,
                nearby_presence=nearby_presence,
            )
            
            decision = services["correlation_service"].evaluate(context)
            
            if decision.decision == "ALERT":
                services["alert_service"].raise_unauthorized_presence_alert()
            elif decision.decision == "HIGH_ALERT":
                services["alert_service"].raise_blocked_device_alert()
        except Exception as e:
            print(f"Monitor Loop Error: {e}")
        finally:
            if session is not None:
                session.close()
        
        time.sleep(MONITOR_INTERVAL_SECONDS)


app = FastAPI(title="Signally API", version="1.0.0")


def to_device_response(
    device,
    user_service: UserService | None = None,
    fingerprint_service: FingerprintService | None = None,
) -> DeviceResponse:
    owner = user_service.get_device_owner(device.mac_address) if user_service else None
    fingerprint = (
        fingerprint_service.fingerprint_device(device, owner=owner)
        if fingerprint_service
        else None
    )
    return DeviceResponse(
        mac_address=device.mac_address,
        ip_address=device.ip_address,
        status=device.status.value if hasattr(device.status, "value") else str(device.status),
        first_seen=device.first_seen,
        last_seen=device.last_seen,
        owner_user_id=owner.id if owner else None,
        owner_name=owner.display_name if owner else None,
        owner_role=owner.role.value if owner else None,
        fingerprint=to_fingerprint_response(fingerprint) if fingerprint else None,
    )


def to_event_response(event) -> EventResponse:
    return EventResponse(
        id=event.id,
        event_type=event.event_type,
        device_mac=event.device_mac,
        details=event.details,
        created_at=event.created_at,
    )


def to_user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        display_name=user.display_name,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        created_at=user.created_at,
    )


def to_fingerprint_response(fingerprint) -> DeviceFingerprintResponse:
    return DeviceFingerprintResponse(
        manufacturer=fingerprint.manufacturer,
        device_category=fingerprint.device_category,
        display_name=fingerprint.display_name,
        confidence=fingerprint.confidence,
        hostname=fingerprint.hostname,
        randomized_mac=fingerprint.randomized_mac,
        primary_layer=fingerprint.primary_layer,
        connected=fingerprint.connected,
        signals=fingerprint.signals,
    )


def parse_actor_role(value: Optional[str]) -> UserRole:
    if not value:
        return UserRole.ADMIN
    try:
        return UserRole(value.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown user role: {0}".format(value))


def select_current_unknown_devices(connected_presence, nearby_presence):
    if connected_presence.pending_connected_devices:
        return connected_presence.pending_connected_devices
    return nearby_presence.effective_unknown_nearby_devices



@app.on_event("startup")
def on_startup() -> None:
    initialize_database()
    
    # 1. Start the ARP & Correlation background loop
    threading.Thread(target=run_background_monitor, daemon=True).start()
    
    # 2. Auto-Fallback for Layer 2 (Wi-Fi Probing)
    # This is the name we expect the Wavlink to have once in monitor mode
    EXPECTED_WIFI_INTERFACE = "wlan1"
    
    try:
        # VALIDATION STEP: Check if the interface is actually plugged in
        available_interfaces = get_if_list()
        
        if EXPECTED_WIFI_INTERFACE not in available_interfaces:
            raise ValueError(f"Interface {EXPECTED_WIFI_INTERFACE} is not connected.")

        # ATTEMPT: Try to bind to the physical Wavlink antenna
        wifi_probing_state.start(interface=EXPECTED_WIFI_INTERFACE, mock_mode=False)
        print(f"[STARTUP] SUCCESS: Layer 2 Wi-Fi Probing started in REAL mode on {EXPECTED_WIFI_INTERFACE}.")
        
    except Exception as hardware_error:
        # FALLBACK: Adapter missing or driver not loaded? Silently fall back to Mock!
        print(f"[STARTUP] Hardware bypass ({hardware_error}). Layer 2 falling back to MOCK mode.")
        wifi_probing_state.start(interface=None, mock_mode=True)

        

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

        return [
            to_device_response(device, services["user_service"], services["fingerprint_service"])
            for device in processed
        ]
    finally:
        session.close()


@app.get("/devices", response_model=list[DeviceResponse])
def list_devices():
    session = get_db_session()
    try:
        services = build_services(session)
        devices = services["device_service"].list_all_devices()
        return [
            to_device_response(device, services["user_service"], services["fingerprint_service"])
            for device in devices
        ]
    finally:
        session.close()


@app.get("/devices/pending", response_model=list[DeviceResponse])
def list_pending_devices():
    session = get_db_session()
    try:
        services = build_services(session)
        devices = services["admin_manager"].list_pending_devices()
        return [
            to_device_response(device, services["user_service"], services["fingerprint_service"])
            for device in devices
        ]
    finally:
        session.close()


@app.post("/devices/approve-all", response_model=list[DeviceResponse])
def approve_all_pending_devices(
    x_signally_user_role: Optional[str] = Header(default=None),
):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            devices = services["admin_manager"].approve_all_pending_devices(
                actor_role=parse_actor_role(x_signally_user_role),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return [
            to_device_response(device, services["user_service"], services["fingerprint_service"])
            for device in devices
        ]
    finally:
        session.close()


@app.post("/devices/{mac_address}/approve", response_model=DeviceResponse)
def approve_device(
    mac_address: str,
    request: Optional[ApproveDeviceRequest] = None,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            device = services["admin_manager"].approve_device(
                mac_address,
                actor_role=parse_actor_role(x_signally_user_role),
                owner_name=request.owner_name if request else None,
                owner_role=request.owner_role if request else UserRole.GUEST,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return to_device_response(
            device,
            services["user_service"],
            services["fingerprint_service"],
        )
    finally:
        session.close()


@app.post("/devices/{mac_address}/block", response_model=DeviceResponse)
def block_device(
    mac_address: str,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            device = services["admin_manager"].block_device(
                mac_address,
                actor_role=parse_actor_role(x_signally_user_role),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return to_device_response(
            device,
            services["user_service"],
            services["fingerprint_service"],
        )
    finally:
        session.close()


@app.delete("/devices/{mac_address}", response_model=MessageResponse)
def delete_device(
    mac_address: str,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            services["admin_manager"].delete_device(
                mac_address,
                actor_role=parse_actor_role(x_signally_user_role),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
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


@app.get("/devices/{mac_address}/fingerprint", response_model=DeviceFingerprintResponse)
def get_device_fingerprint(mac_address: str):
    session = get_db_session()
    try:
        services = build_services(session)
        device = services["device_service"].get_by_mac(mac_address)
        if device is None:
            raise HTTPException(status_code=404, detail="Device with MAC {0} was not found".format(mac_address))
        owner = services["user_service"].get_device_owner(device.mac_address)
        fingerprint = services["fingerprint_service"].fingerprint_device(device, owner=owner)
        return to_fingerprint_response(fingerprint)
    finally:
        session.close()


@app.post("/devices/{mac_address}/hostname-hint", response_model=DeviceFingerprintResponse)
def set_device_hostname_hint(
    mac_address: str,
    request: SetDeviceHostnameHintRequest,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            services["user_service"].require_admin(parse_actor_role(x_signally_user_role))
            device = services["device_service"].get_by_mac(mac_address)
            if device is None:
                raise ValueError("Device with MAC {0} was not found".format(mac_address))
            services["fingerprint_service"].set_hostname_hint(
                mac_address=device.mac_address,
                hostname=request.hostname,
            )
            owner = services["user_service"].get_device_owner(device.mac_address)
            fingerprint = services["fingerprint_service"].fingerprint_device(device, owner=owner)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return to_fingerprint_response(fingerprint)
    finally:
        session.close()


@app.get("/users", response_model=list[UserResponse])
def list_users():
    session = get_db_session()
    try:
        services = build_services(session)
        return [to_user_response(user) for user in services["user_service"].list_users()]
    finally:
        session.close()


@app.post("/users", response_model=UserResponse)
def create_user(
    request: UserCreateRequest,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            services["user_service"].require_admin(parse_actor_role(x_signally_user_role))
            user = services["user_service"].create_user(
                display_name=request.display_name,
                role=request.role,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return to_user_response(user)
    finally:
        session.close()


@app.post("/devices/{mac_address}/assign-user", response_model=DeviceResponse)
def assign_device_to_user(
    mac_address: str,
    request: AssignDeviceRequest,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            services["user_service"].require_admin(parse_actor_role(x_signally_user_role))
            device = services["user_service"].assign_device_to_user(
                mac_address=mac_address,
                user_id=request.user_id,
                mark_authorized=request.mark_authorized,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return to_device_response(
            device,
            services["user_service"],
            services["fingerprint_service"],
        )
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


def _get_vendor(mac_address: str) -> Optional[str]:
    try:
        from scapy.all import conf
        vendor = conf.manufdb.getManufLong(mac_address)
        return vendor if vendor else None
    except Exception:
        return None


def _parse_probe_details(details: str) -> dict:
    result = {}
    for part in details.split('; '):
        if '=' in part:
            key, _, value = part.partition('=')
            result[key.strip()] = value.strip()
    return result


@app.get("/probe-info/{mac_address}", response_model=ProbeInfoResponse)
def get_device_probe_info(mac_address: str):
    session = get_db_session()
    try:
        from signally.services.event_service import EventService
        event_service = EventService(session)
        events = event_service.list_events_for_device_by_types(
            device_mac=mac_address,
            event_types=[EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW, EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN],
            limit=200,
        )

        seen_ssids: list[str] = []
        latest_rssi: Optional[int] = None

        for event in events:
            parsed = _parse_probe_details(event.details)
            ssid = parsed.get('ssid', '').strip()
            if ssid and ssid not in seen_ssids:
                seen_ssids.append(ssid)
            if latest_rssi is None:
                raw_rssi = parsed.get('rssi', '').strip()
                if raw_rssi:
                    try:
                        latest_rssi = int(raw_rssi)
                    except ValueError:
                        pass

        services = build_services(session)
        device = services["device_service"].get_by_mac(mac_address)
        is_nearby_only = device is None or not device.ip_address or device.ip_address == 'UNASSOCIATED'

        return ProbeInfoResponse(
            mac_address=mac_address.upper(),
            vendor=_get_vendor(mac_address),
            known_ssids=seen_ssids,
            latest_rssi=latest_rssi,
            is_nearby_only=is_nearby_only,
        )
    finally:
        session.close()


@app.post("/wifi_probing/start", response_model=MessageResponse)
def start_wifi_probing(request: Optional[WifiProbingStartRequest] = None):
    request = request or WifiProbingStartRequest(mock_mode=True)
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
        user_service = UserService(session)
        fingerprint_service = FingerprintService(session)
        devices = service.list_recent_devices(limit=limit)
        return [
            to_device_response(device, user_service, fingerprint_service)
            for device in devices
        ]
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
        user_service = UserService(session)
        fingerprint_service = FingerprintService(session)
        devices = service.list_recent_devices(
            limit=limit,
            window_seconds=CURRENT_UNKNOWN_WINDOW_SECONDS,
        )
        return [
            to_device_response(device, user_service, fingerprint_service)
            for device in devices
        ]
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
        nearby_presence = WifiProbingService(session).get_presence_snapshot(
            connected_presence=connected_presence,
            limit=50,
        )
        
        context = CorrelationContext(
            csi_presence_detected=csi_detected,
            nearby_device_count=len(nearby_presence.nearby_devices),
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
        )
        
        decision = services["correlation_service"].evaluate(context)
        
        return SystemStateResponse(
            csi_presence_detected=csi_detected,
            approved_user_present=connected_presence.approved_user_present,
            admin_present=connected_presence.admin_present,
            family_present=connected_presence.family_present,
            guest_present=connected_presence.guest_present,
            decision=decision.decision,
            reason=decision.reason,
            present_devices=[
                to_device_response(
                    d,
                    services["user_service"],
                    services["fingerprint_service"],
                )
                for d in connected_presence.connected_devices
            ],
            current_intruder_count=decision.current_intruder_count,
            current_unknown_devices=[
                to_device_response(
                    d,
                    services["user_service"],
                    services["fingerprint_service"],
                )
                for d in select_current_unknown_devices(connected_presence, nearby_presence)
            ],
            ignored_authorized_duplicate_count=decision.ignored_authorized_duplicate_count,
            admin_review_grace_active=decision.admin_review_grace_active,
            notification_audience=decision.notification_audience,
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
        nearby_presence = WifiProbingService(session).get_presence_snapshot(
            connected_presence=connected_presence,
            limit=50,
        )
        
        context = CorrelationContext(
            csi_presence_detected=csi_detected,
            nearby_device_count=len(nearby_presence.nearby_devices),
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
        )
        decision = services["correlation_service"].evaluate(context)
        
        return MonitoringCycleResponse(
            csi_presence_detected=csi_detected,
            approved_user_present=connected_presence.approved_user_present,
            admin_present=connected_presence.admin_present,
            family_present=connected_presence.family_present,
            guest_present=connected_presence.guest_present,
            decision=decision.decision,
            reason=decision.reason,
            processed_devices_count=len(discovered),
            present_devices_count=len(connected_presence.connected_devices),
            authorized_devices_count=len(connected_presence.authorised_connected_devices),
            pending_devices_count=len(connected_presence.pending_connected_devices),
            blocked_devices_count=len(connected_presence.blocked_connected_devices),
            current_intruder_count=decision.current_intruder_count,
            ignored_authorized_duplicate_count=decision.ignored_authorized_duplicate_count,
            admin_review_grace_active=decision.admin_review_grace_active,
            notification_audience=decision.notification_audience,
        )
    finally:
        session.close()
