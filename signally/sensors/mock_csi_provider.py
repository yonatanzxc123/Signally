"""
Mock CSI provider for demos and tests.

This class allows us to simulate CSI presence detection before we have the
real Raspberry Pi + Wi-Fi adapter + CSI-capable hardware setup.
"""

from __future__ import annotations

from signally.sensors.csi_provider import CsiDetectionProvider


class MockCsiDetectionProvider(CsiDetectionProvider):
    """
    Mock CSI provider with manually controlled internal state.
    """

    def __init__(self, presence_detected: bool = False, presence_strength: float | None = None) -> None:
        self._presence_detected = presence_detected
        self._presence_strength = presence_strength

    def is_presence_detected(self) -> bool:
        return self._presence_detected

    def get_presence_strength(self) -> float | None:
        return self._presence_strength

    def set_presence_detected(self, value: bool) -> None:
        self._presence_detected = value

    def set_presence_strength(self, value: float | None) -> None:
        self._presence_strength = value