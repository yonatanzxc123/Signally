"""
Pydantic schemas for the Signally API.
"""

from datetime import datetime
import ipaddress
import re
from typing import Optional

from pydantic import BaseModel, field_validator

_MAC_PATTERN = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class ConnectedInspectionResponse(BaseModel):
    device_category: str
    confidence: float
    hostname: Optional[str] = None
    mdns_services: list[str]
    nmap_device_type: Optional[str] = None
    nmap_os: Optional[str] = None
    open_ports: list[str]
    signals: list[str]


class DeviceResponse(BaseModel):
    mac_address: str
    ip_address: Optional[str] = None
    status: str
    first_seen: datetime
    last_seen: datetime
    owner_user_id: Optional[int] = None
    owner_name: Optional[str] = None
    owner_role: Optional[str] = None


class EventResponse(BaseModel):
    id: int
    event_type: str
    device_mac: Optional[str]
    details: str
    created_at: datetime


class MessageResponse(BaseModel):
    message: str


class SetCsiPresenceRequest(BaseModel):
    detected: bool


class CsiPresenceResponse(BaseModel):
    # Both legacy spellings are retained for existing /csi/status consumers.
    presence_detected: bool
    presence_strength: Optional[float] = None
    detected: bool
    strength: Optional[float] = None
    provider_mode: str
    receiving_data: bool
    ready: bool
    currently_detected: bool
    recently_detected: bool
    motion_metric: Optional[float] = None
    baseline: Optional[float] = None
    threshold: Optional[float] = None
    baseline_factor: float
    confidence: float
    frames_received: int
    invalid_frames: int
    last_packet_at: Optional[datetime] = None
    last_error: Optional[str] = None


class ArpObservationRequest(BaseModel):
    ip_address: str
    mac_address: str

    @field_validator("ip_address")
    @classmethod
    def valid_ip(cls, value: str) -> str:
        return str(ipaddress.ip_address(value.strip()))

    @field_validator("mac_address")
    @classmethod
    def valid_mac(cls, value: str) -> str:
        normalized = value.strip().replace("-", ":").upper()
        if not _MAC_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid MAC address")
        return normalized


class ArpIngestionRequest(BaseModel):
    scan_id: str
    captured_at: datetime
    scanner_id: str
    devices: list[ArpObservationRequest]

    @field_validator("scan_id", "scanner_id")
    @classmethod
    def nonempty_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 128:
            raise ValueError("Identifier must contain 1-128 characters")
        return value


class ArpIngestionResponse(BaseModel):
    accepted: bool
    processed_devices_count: int
    received_at: datetime


class ArpIngestionStatusResponse(BaseModel):
    healthy: bool
    last_scan_id: Optional[str] = None
    last_captured_at: Optional[datetime] = None
    last_received_at: Optional[datetime] = None
    last_device_count: int = 0


class SystemStateResponse(BaseModel):
    mode: str = "HOME"
    security_mode: str = "HOME"
    security_mode_updated_by_role: Optional[str] = None
    security_mode_updated_at: Optional[datetime] = None
    csi_presence_detected: bool
    csi: CsiPresenceResponse
    probe_activity_detected: bool = False
    probe_observation_count: int = 0
    arp_scanner_healthy: bool = False
    arp_last_received_at: Optional[datetime] = None
    approved_user_present: bool
    admin_present: bool = False
    family_present: bool = False
    guest_present: bool = False
    decision: str
    reason: str
    present_devices: list[DeviceResponse]
    current_intruder_count: int = 0
    known_devices: int = 0
    unknown_devices: int = 0
    nearby_probe_count: int = 0
    current_unknown_devices: list[DeviceResponse] = []
    admin_review_grace_active: bool = False
    notification_audience: list[str] = []
    recent_alerts: list[EventResponse] = []

class MonitoringCycleResponse(BaseModel):
    mode: str = "HOME"
    security_mode: str = "HOME"
    csi_presence_detected: bool
    csi: CsiPresenceResponse
    probe_activity_detected: bool = False
    probe_observation_count: int = 0
    arp_scanner_healthy: bool = False
    arp_last_received_at: Optional[datetime] = None
    approved_user_present: bool
    admin_present: bool = False
    family_present: bool = False
    guest_present: bool = False
    decision: str
    reason: str
    processed_devices_count: int
    present_devices_count: int
    authorized_devices_count: int
    pending_devices_count: int
    blocked_devices_count: int
    current_intruder_count: int = 0
    nearby_probe_count: int = 0
    admin_review_grace_active: bool = False
    notification_audience: list[str] = []
    scan_error: Optional[str] = None
    recent_alerts: list[EventResponse] = []


class UserResponse(BaseModel):
    id: int
    display_name: str
    role: str
    created_at: datetime


class UserCreateRequest(BaseModel):
    display_name: str
    role: str


class ApproveDeviceRequest(BaseModel):
    owner_role: str  # must be FAMILY or GUEST


class SetDeviceHostnameHintRequest(BaseModel):
    hostname: str


class SecurityModeResponse(BaseModel):
    mode: str
    armed: bool
    updated_by_role: str
    updated_at: datetime


class SetSecurityModeRequest(BaseModel):
    mode: str


class SignupRequest(BaseModel):
    display_name: str
    email: str
    password: str
    confirm_password: str
    role: str = "ADMIN"


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: int
    display_name: str
    role: str
    email: str


class WifiProbingStartRequest(BaseModel):
    interface: Optional[str] = None
    mock_mode: bool = False

class WifiProbingStatusResponse(BaseModel):
    running: bool
    interface: Optional[str] = None
    mock_mode: bool
    started_at: Optional[datetime] = None
    last_error: Optional[str] = None
