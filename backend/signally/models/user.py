"""
User model — app authentication only.
"""

from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, Integer, String
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
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=utc_now)
