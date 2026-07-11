"""Normalized sensing state exposed to the rest of Signally."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from signally.utils.time_utils import utc_now


class SensingProviderStatus:
    OK = "OK"
    NO_DATA = "NO_DATA"
    NO_BASELINE = "NO_BASELINE"
    ERROR = "ERROR"
    MOCK = "MOCK"
    FALLBACK = "FALLBACK"


@dataclass
class SensingSnapshot:
    source: str
    provider_status: str
    presence_detected: bool
    confidence: float = 0.0
    baseline_deviation: Optional[float] = None
    packets_per_second: float = 0.0
    last_packet_age_ms: Optional[int] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=utc_now)
    raw_summary: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def mock(
        cls,
        detected: bool = False,
        confidence: Optional[float] = None,
        status: str = SensingProviderStatus.MOCK,
        reason: str = "Mock CSI provider is active.",
    ) -> "SensingSnapshot":
        normalized_confidence = max(0.0, min(float(confidence or 0.0), 1.0))
        return cls(
            source="MOCK",
            provider_status=status,
            presence_detected=detected,
            confidence=normalized_confidence,
            baseline_deviation=normalized_confidence if detected else 0.0,
            reason=reason,
            raw_summary={"mock": True},
        )
