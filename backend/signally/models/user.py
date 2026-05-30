"""
User and device ownership models.

Users represent people the app understands. A user can own one or more
approved devices, and the user's role controls what they can do in the app.
"""

from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from signally.db.base import Base
from signally.utils.time_utils import utc_now


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    FAMILY = "FAMILY"
    GUEST = "GUEST"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=utc_now)


class DeviceOwner(Base):
    __tablename__ = "device_owners"

    mac_address: Mapped[str] = mapped_column(
        String(17),
        ForeignKey("devices.mac_address"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=utc_now)
