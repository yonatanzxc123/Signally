"""
Event model.

Every meaningful system action can be recorded here. For the MVP,
we use it to log device detections and admin actions.
"""

from __future__ import annotations

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from signally.db.base import Base
from signally.utils.time_utils import utc_now


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    device_mac: Mapped[str | None] = mapped_column(String(17), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=utc_now)
