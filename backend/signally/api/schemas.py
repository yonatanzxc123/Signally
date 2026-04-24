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


class SetCsiPresenceRequest(BaseModel):
    detected: bool


class CsiPresenceResponse(BaseModel):
    detected: bool
    strength: Optional[float]
