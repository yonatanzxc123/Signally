"""
Abstract CSI provider.

CSI is responsible for low-level presence detection.
At this stage we do not yet have the hardware, so this class defines the
interface that real CSI implementations must follow later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CsiDetectionProvider(ABC):
    """
    Interface for CSI-based presence detection.
    """

    @abstractmethod
    def is_presence_detected(self) -> bool:
        """
        Return True if the CSI layer currently detects presence/activity.
        """
        raise NotImplementedError

    def get_presence_strength(self) -> float | None:
        """
        Optional future extension:
        return a numeric presence signal strength if available.
        For now, the default implementation returns None.
        """
        return None