"""
Pydantic schemas for the Signally API.
"""

from datetime import datetime
from typing import Optional

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


class MessageResponse(BaseModel):
    message: str


class WifiProbingStartRequest(BaseModel):
    interface: Optional[str] = None
    mock_mode: bool = False


class WifiProbingStatusResponse(BaseModel):
    running: bool
    interface: Optional[str]
    mock_mode: bool
    started_at: Optional[datetime]
    last_error: Optional[str]


class SetCsiPresenceRequest(BaseModel):
    detected: bool
