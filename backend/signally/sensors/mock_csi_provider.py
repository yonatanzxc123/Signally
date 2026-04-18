"""
Mock CSI provider for demos and tests.
"""

from typing import Optional

from signally.sensors.csi_provider import CsiDetectionProvider


class MockCsiDetectionProvider(CsiDetectionProvider):
    def __init__(
        self,
        presence_detected: bool = False,
        presence_strength: Optional[float] = None,
    ) -> None:
        self._presence_detected = presence_detected
        self._presence_strength = presence_strength

    def is_presence_detected(self) -> bool:
        return self._presence_detected

    def get_presence_strength(self) -> Optional[float]:
        return self._presence_strength

    def set_presence_detected(self, value: bool) -> None:
        self._presence_detected = value

    def set_presence_strength(self, value: Optional[float]) -> None:
        self._presence_strength = value