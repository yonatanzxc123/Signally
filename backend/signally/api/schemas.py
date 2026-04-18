"""
Pydantic schemas for the Signally API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DeviceResponse(BaseModel):
    mac_address: str
    ip_address: str
    status: str
    first_seen: datetime
    last_seen: datetime


class EventResponse(BaseModel):
    id: int
    event_type: str
    device_mac: Optional[str]
    details: str
    created_at: datetime


class MonitoringCycleResponse(BaseModel):
    csi_presence_detected: bool
    approved_user_present: bool
    decision: str
    reason: str
    processed_devices_count: int
    present_devices_count: int
    authorized_devices_count: int
    pending_devices_count: int
    blocked_devices_count: int


class SystemStateResponse(BaseModel):
    csi_presence_detected: bool
    approved_user_present: bool
    decision: str
    reason: str
    present_devices: List[DeviceResponse]


class MessageResponse(BaseModel):
    message: str


class SetCsiPresenceRequest(BaseModel):
    detected: bool


class SimulateDeviceRequest(BaseModel):
    ip_address: str
    mac_address: str


class WifiModeRequest(BaseModel):
    mode: str


class CsiModeRequest(BaseModel):
    mode: str


class ModeStateResponse(BaseModel):
    wifi_mode: str
    csi_mode: str