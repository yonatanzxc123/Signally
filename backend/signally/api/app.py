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
from signally.config import MONITOR_INTERVAL_SECONDS
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
    AuthResponse,
    ConnectedInspectionResponse,
    DeviceResponse,
    EventResponse,
    LoginRequest,
    MessageResponse,
    SetCsiPresenceRequest,
    SetSecurityModeRequest,
    SecurityModeResponse,
    SignupRequest,
    WifiProbingStartRequest,
    WifiProbingStatusResponse,
    SystemStateResponse,
    MonitoringCycleResponse,
    UserCreateRequest,
    UserResponse,
)
from signally.config import EVENT_SECURITY_MODE_CHANGED
from signally.models.security_mode import SecurityMode
from signally.models.user import UserRole
from signally.services.connected_inspection_service import ConnectedInspectionService


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
            nearby_presence = WifiProbingService(session).get_presence_snapshot()
            security_state = services["security_mode_service"].get_state()

            context = CorrelationContext(
                csi_presence_detected=csi_detected,
                nearby_device_count=nearby_presence.nearby_probe_count,
                connected_presence=connected_presence,
                nearby_presence=nearby_presence,
                security_mode=security_state.mode,
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


def to_device_response(device) -> DeviceResponse:
    return DeviceResponse(
        mac_address=device.mac_address,
        ip_address=device.ip_address,
        status=device.status.value if hasattr(device.status, "value") else str(device.status),
        first_seen=device.first_seen,
        last_seen=device.last_seen,
        owner_role=device.owner_role,
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


def to_security_mode_response(state) -> SecurityModeResponse:
    mode = state.mode.value if hasattr(state.mode, "value") else str(state.mode)
    return SecurityModeResponse(
        mode=mode,
        armed=mode == SecurityMode.AWAY.value,
        updated_by_role=state.updated_by_role,
        updated_at=state.updated_at,
    )

def to_connected_inspection_response(result) -> ConnectedInspectionResponse:
    return ConnectedInspectionResponse(
        device_category=result.device_category,
        confidence=result.confidence,
        hostname=result.hostname,
        mdns_services=result.mdns_services,
        nmap_device_type=result.nmap_device_type,
        nmap_os=result.nmap_os,
        open_ports=result.open_ports,
        signals=result.signals,
    )


def parse_actor_role(value: Optional[str]) -> UserRole:
    if not value:
        return UserRole.ADMIN
    try:
        return UserRole(value.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown user role: {0}".format(value))


def select_current_unknown_devices(connected_presence):
    return connected_presence.pending_connected_devices



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


@app.get("/auth/me", response_model=AuthResponse)
def get_me(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ")
    from signally.services.auth_service import decode_token
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    session = get_db_session()
    try:
        from sqlalchemy import select
        from signally.models.user import User
        user = session.scalar(select(User).where(User.id == int(payload["sub"])))
        if not user:
            raise HTTPException(status_code=401, detail="User no longer exists")
        return {
            "token": token,
            "user_id": user.id,
            "display_name": user.display_name,
            "role": user.role.value,
            "email": user.email,
        }
    finally:
        session.close()


@app.post("/auth/signup", response_model=AuthResponse)
def signup(request: SignupRequest):
    if request.password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    try:
        role = UserRole(request.role.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")
    if role == UserRole.GUEST:
        raise HTTPException(status_code=400, detail="Cannot sign up as guest")
    session = get_db_session()
    try:
        from signally.services.auth_service import AuthService
        try:
            return AuthService(session).signup(
                display_name=request.display_name,
                email=request.email,
                password=request.password,
                role=role,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    finally:
        session.close()


@app.post("/auth/login", response_model=AuthResponse)
def login(request: LoginRequest):
    session = get_db_session()
    try:
        from signally.services.auth_service import AuthService
        try:
            return AuthService(session).login(email=request.email, password=request.password)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
    finally:
        session.close()


@app.get("/security-mode", response_model=SecurityModeResponse)
def get_security_mode():
    session = get_db_session()
    try:
        services = build_services(session)
        return to_security_mode_response(services["security_mode_service"].get_state())
    finally:
        session.close()


@app.post("/security-mode", response_model=SecurityModeResponse)
def set_security_mode(
    request: SetSecurityModeRequest,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    session = get_db_session()
    try:
        services = build_services(session)
        actor_role = parse_actor_role(x_signally_user_role)
        try:
            state = services["security_mode_service"].set_mode(
                mode=request.mode,
                actor_role=actor_role,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        services["event_service"].log_event(
            event_type=EVENT_SECURITY_MODE_CHANGED,
            details="Security mode set to {0} by {1}".format(
                state.mode.value if hasattr(state.mode, "value") else str(state.mode),
                actor_role.value,
            ),
        )
        return to_security_mode_response(state)
    finally:
        session.close()


@app.post("/scan", response_model=list[DeviceResponse])
def scan_network():
    session = get_db_session()
    try:
        scanner = NetworkScanner()
        discovered = scanner.scan()

        services = build_services(session)
        processed = services["device_service"].process_scan_results(discovered)

        return [
            to_device_response(device)
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
            to_device_response(device)
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
            to_device_response(device)
            for device in devices
        ]
    finally:
        session.close()


@app.post("/devices/approve-all", response_model=list[DeviceResponse])
def approve_all_pending_devices(
    request: ApproveDeviceRequest,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    try:
        owner_role = UserRole(request.owner_role.upper())
        if owner_role not in (UserRole.FAMILY, UserRole.GUEST):
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=400, detail="Role must be FAMILY or GUEST")
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            devices = services["admin_manager"].approve_all_pending_devices(
                owner_role=owner_role,
                actor_role=parse_actor_role(x_signally_user_role),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return [
            to_device_response(device)
            for device in devices
        ]
    finally:
        session.close()


@app.post("/devices/{mac_address}/approve", response_model=DeviceResponse)
def approve_device(
    mac_address: str,
    request: ApproveDeviceRequest,
    x_signally_user_role: Optional[str] = Header(default=None),
):
    try:
        owner_role = UserRole(request.owner_role.upper())
        if owner_role not in (UserRole.FAMILY, UserRole.GUEST):
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=400, detail="Role must be FAMILY or GUEST")
    session = get_db_session()
    try:
        services = build_services(session)
        try:
            device = services["admin_manager"].approve_device(
                mac_address,
                actor_role=parse_actor_role(x_signally_user_role),
                owner_role=owner_role,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return to_device_response(device)
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
        return to_device_response(device)
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


@app.post("/devices/{mac_address}/inspect", response_model=ConnectedInspectionResponse)
def inspect_connected_device(
    mac_address: str,
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
            result = ConnectedInspectionService(session).inspect_device(device)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return to_connected_inspection_response(result)
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
            message="Database reset complete. Deleted {0} device(s), {1} event(s), {2} user(s).".format(
                result["deleted_devices"],
                result["deleted_events"],
                result["deleted_users"],
            )
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


@app.get("/wifi_probing/probe-count")
def get_wifi_probe_count():
    session = get_db_session()
    try:
        snapshot = WifiProbingService(session).get_presence_snapshot()
        return {"nearby_probe_count": snapshot.nearby_probe_count}
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


@app.get("/system/state", response_model=SystemStateResponse)
def get_system_state():
    """ Frontend requirement: Gets the current correlated state """
    session = get_db_session()
    try:
        services = build_services(session)
        csi_detected = csi_provider.is_presence_detected()
        connected_presence = services["presence_service"].get_presence_snapshot()
        nearby_presence = WifiProbingService(session).get_presence_snapshot()
        security_state = services["security_mode_service"].get_state()

        context = CorrelationContext(
            csi_presence_detected=csi_detected,
            nearby_device_count=nearby_presence.nearby_probe_count,
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
            security_mode=security_state.mode,
        )

        decision = services["correlation_service"].evaluate(context)

        return SystemStateResponse(
            security_mode=security_state.mode.value,
            security_mode_updated_by_role=security_state.updated_by_role,
            security_mode_updated_at=security_state.updated_at,
            csi_presence_detected=csi_detected,
            approved_user_present=connected_presence.approved_user_present,
            admin_present=connected_presence.admin_present,
            family_present=connected_presence.family_present,
            guest_present=connected_presence.guest_present,
            decision=decision.decision,
            reason=decision.reason,
            present_devices=[
                to_device_response(d)
                for d in connected_presence.connected_devices
            ],
            nearby_device_count=decision.nearby_device_count,
            current_intruder_count=decision.current_intruder_count,
            current_unknown_devices=[
                to_device_response(d)
                for d in select_current_unknown_devices(connected_presence)
            ],
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
        nearby_presence = WifiProbingService(session).get_presence_snapshot()
        security_state = services["security_mode_service"].get_state()

        context = CorrelationContext(
            csi_presence_detected=csi_detected,
            nearby_device_count=nearby_presence.nearby_probe_count,
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
            security_mode=security_state.mode,
        )
        decision = services["correlation_service"].evaluate(context)
        
        return MonitoringCycleResponse(
            security_mode=security_state.mode.value,
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
            nearby_device_count=decision.nearby_device_count,
            current_intruder_count=decision.current_intruder_count,
            admin_review_grace_active=decision.admin_review_grace_active,
            notification_audience=decision.notification_audience,
        )
    finally:
        session.close()
