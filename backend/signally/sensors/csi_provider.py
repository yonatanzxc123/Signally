"""CSI presence provider abstractions."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from signally.config import CSI_REAL_PROVIDER_ENABLED
from signally.models.csi_baseline import CsiBaseline
from signally.sensors.nexmon.nexmon_provider import NexmonCsiProvider
from signally.sensors.sensing_snapshot import SensingProviderStatus, SensingSnapshot


class CsiDetectionProvider:
    def is_presence_detected(self) -> bool:
        raise NotImplementedError

    def get_presence_strength(self) -> Optional[float]:
        return None

    def get_snapshot(self, session: Optional[Session] = None) -> SensingSnapshot:
        return SensingSnapshot.mock()


class FlagCsiDetectionProvider(CsiDetectionProvider):
    """Manual/mock CSI provider for tests and classroom fallback demos."""

    def __init__(self, detected: bool = False, strength: Optional[float] = None) -> None:
        self._detected = detected
        self._strength = strength

    def is_presence_detected(self) -> bool:
        return self._detected

    def get_presence_strength(self) -> Optional[float]:
        return self._strength

    def get_snapshot(self, session: Optional[Session] = None) -> SensingSnapshot:
        return SensingSnapshot.mock(
            detected=self._detected,
            confidence=self._strength,
            status=SensingProviderStatus.MOCK,
            reason="Mock CSI provider is active. No real Nexmon packets are being used.",
        )

    def set_detected(self, value: bool) -> None:
        self._detected = value
        if value and self._strength is None:
            self._strength = 1.0

    def set_strength(self, value: Optional[float]) -> None:
        self._strength = value


class RealCsiDetectionProvider(NexmonCsiProvider):
    """Compatibility alias for the real Nexmon-backed provider."""


class AutoFallbackCsiProvider(CsiDetectionProvider):
    def __init__(self, real_enabled: bool = CSI_REAL_PROVIDER_ENABLED):
        self.real = RealCsiDetectionProvider(auto_start=True) if real_enabled else None
        self.mock = FlagCsiDetectionProvider()
        self._mock_override_active = False

    def get_snapshot(self, session: Optional[Session] = None) -> SensingSnapshot:
        if self.real is None:
            return self.mock.get_snapshot(session)

        real_snapshot = self.real.get_snapshot(session)
        if self._mock_override_active and real_snapshot.provider_status != SensingProviderStatus.OK:
            mock_snapshot = self.mock.get_snapshot(session)
            mock_snapshot.provider_status = SensingProviderStatus.FALLBACK
            mock_snapshot.reason = (
                "Mock CSI fallback is active because real Nexmon CSI is not ready: {0}".format(
                    real_snapshot.provider_status
                )
            )
            mock_snapshot.raw_summary["real_provider_status"] = real_snapshot.provider_status
            return mock_snapshot

        return real_snapshot

    def is_presence_detected(self) -> bool:
        return self.get_snapshot().presence_detected

    def get_presence_strength(self) -> Optional[float]:
        return self.get_snapshot().confidence

    def set_detected(self, value: bool) -> None:
        self._mock_override_active = True
        self.mock.set_detected(value)

    def set_strength(self, value: Optional[float]) -> None:
        self._mock_override_active = True
        self.mock.set_strength(value)

    def clear_mock_override(self) -> None:
        self._mock_override_active = False

    def start_calibration(self) -> dict:
        if self.real is None:
            raise RuntimeError("Real Nexmon CSI provider is disabled.")
        return self.real.start_calibration()

    def stop_calibration(self, session: Session) -> CsiBaseline:
        if self.real is None:
            raise RuntimeError("Real Nexmon CSI provider is disabled.")
        return self.real.stop_calibration(session)

    def get_baseline(self, session: Session) -> Optional[CsiBaseline]:
        if self.real is None:
            return None
        return self.real.get_baseline(session)

    def delete_baseline(self, session: Session) -> int:
        if self.real is None:
            return 0
        return self.real.delete_baseline(session)

    def stop(self) -> None:
        if self.real is not None:
            self.real.stop()
