"""Security mode model.

Stores the shared Home/Away arm state for the current Signally household.
"""

from __future__ import annotations

import enum

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from signally.db.base import Base
from signally.utils.time_utils import utc_now


class SecurityMode(str, enum.Enum):
    HOME = "HOME"
    AWAY = "AWAY"


class SecurityState(Base):
    __tablename__ = "security_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    mode: Mapped[SecurityMode] = mapped_column(
        Enum(SecurityMode),
        nullable=False,
        default=SecurityMode.HOME,
    )
    updated_by_role: Mapped[str] = mapped_column(String(20), nullable=False, default="SYSTEM")
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=utc_now)
