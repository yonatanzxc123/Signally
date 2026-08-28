"""Persisted state used to turn repeated scans into presence transitions."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from signally.db.base import Base


class PresenceState(Base):
    __tablename__ = "presence_states"

    device_mac: Mapped[str] = mapped_column(String(17), primary_key=True)
    is_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consecutive_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_observed_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
