"""
Device model.

Represents a device known to the system.
"""

from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from signally.db.base import Base
from signally.utils.time_utils import utc_now


class DeviceStatus(str, enum.Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    BLOCKED = "BLOCKED"


class Device(Base):
    __tablename__ = "devices"

    mac_address: Mapped[str] = mapped_column(String(17), primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    first_seen: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=utc_now)
    last_seen: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=utc_now)
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus),
        nullable=False,
        default=DeviceStatus.PENDING,
    )
