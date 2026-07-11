"""Persisted CSI baseline statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from signally.db.base import Base
from signally.utils.time_utils import utc_now


class CsiBaseline(Base):
    __tablename__ = "csi_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), default="NEXMON")
    provider_metadata: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mean_amplitude: Mapped[float] = mapped_column(Float, default=0.0)
    variance: Mapped[float] = mapped_column(Float, default=0.0)
    stddev: Mapped[float] = mapped_column(Float, default=0.0)
    mean_abs_delta: Mapped[float] = mapped_column(Float, default=0.0)
    threshold: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    packet_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
