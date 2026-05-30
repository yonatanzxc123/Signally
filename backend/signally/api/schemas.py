"""
Pydantic schemas for the Signally API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
    detected: bool
    strength: Optional[float]


class SystemStateResponse(BaseModel):
    security_mode: str = "HOME"
    security_mode_updated_by_role: Optional[str] = None
    security_mode_updated_at: Optional[datetime] = None
    csi_presence_detected: bool
    approved_user_present: bool
    admin_present: bool = False
    family_present: bool = False
    guest_present: bool = False
    decision: str
    reason: str
    present_devices: list[DeviceResponse]
    current_intruder_count: int = 0
    current_unknown_devices: list[DeviceResponse] = []
    admin_review_grace_active: bool = False
    notification_audience: list[str] = []

class MonitoringCycleResponse(BaseModel):
    security_mode: str = "HOME"
    csi_presence_detected: bool
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
    admin_review_grace_active: bool = False
    notification_audience: list[str] = []


class UserResponse(BaseModel):
    id: int
    display_name: str
    role: str
    created_at: datetime


class UserCreateRequest(BaseModel):
    display_name: str
    role: str


class AssignDeviceRequest(BaseModel):
    user_id: int
    mark_authorized: bool = True


class ApproveDeviceRequest(BaseModel):
    owner_name: Optional[str] = None
    owner_role: str = "GUEST"


class SetDeviceHostnameHintRequest(BaseModel):
    hostname: str


class SecurityModeResponse(BaseModel):
    mode: str
    armed: bool
    updated_by_role: str
    updated_at: datetime


class SetSecurityModeRequest(BaseModel):
    mode: str


class WifiProbingStartRequest(BaseModel):
    interface: Optional[str] = None
    mock_mode: bool = False

class WifiProbingStatusResponse(BaseModel):
    running: bool
    interface: Optional[str] = None
    mock_mode: bool
    started_at: Optional[datetime] = None
    last_error: Optional[str] = None
