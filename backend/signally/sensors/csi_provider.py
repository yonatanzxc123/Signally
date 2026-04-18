"""
Abstract CSI provider.
"""

from abc import ABC, abstractmethod
from typing import Optional


class CsiDetectionProvider(ABC):
    @abstractmethod
    def is_presence_detected(self) -> bool:
        raise NotImplementedError

    def get_presence_strength(self) -> Optional[float]:
        return None


class AlwaysOnCsiProvider(CsiDetectionProvider):
    def is_presence_detected(self) -> bool:
        return True


class AlwaysOffCsiProvider(CsiDetectionProvider):
    def is_presence_detected(self) -> bool:
        return False