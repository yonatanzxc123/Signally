"""
Scapy-based 802.11 management-frame detector with optional mock mode.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional

from scapy.all import AsyncSniffer  # type: ignore
from scapy.layers.dot11 import Dot11, Dot11Elt  # type: ignore

from signally.wifi_probing.dto import WifiProbeDetection

_MANAGEMENT_SUBTYPES = {
    0: "assoc_req",
    2: "reassoc_req",
    4: "probe_req",
    5: "probe_resp",
    8: "beacon",
    11: "auth",
}


class WifiProbeDetector:
    def __init__(self, interface: Optional[str] = None, mock_mode: bool = False) -> None:
        self.interface = interface
        self.mock_mode = mock_mode
        self._sniffer = None  # type: Optional[AsyncSniffer]
        self._mock_queue = queue.Queue()

    def add_mock_detection(
        self,
        mac_address: str,
        ssid: Optional[str] = None,
        rssi: Optional[int] = None,
        frame_type: str = "probe_req",
        channel: Optional[int] = None,
    ) -> None:
        detection = WifiProbeDetection(
            mac_address=mac_address.upper(),
            ssid=ssid,
            rssi=rssi,
            frame_type=frame_type,
            interface=self.interface,
            channel=channel,
        )
        self._mock_queue.put(detection)

    def run(
        self,
        on_detection: Callable[[WifiProbeDetection], None],
        stop_event: threading.Event,
    ) -> None:
        if self.mock_mode:
            self._run_mock(on_detection=on_detection, stop_event=stop_event)
            return

        if not self.interface:
            raise ValueError("A monitor-mode interface is required for real Wi-Fi probing")

        self._sniffer = AsyncSniffer(
            iface=self.interface,
            store=False,
            prn=lambda packet: self._handle_packet(packet, on_detection),
        )
        self._sniffer.start()

        try:
            while not stop_event.is_set():
                time.sleep(0.2)
        finally:
            if self._sniffer is not None and self._sniffer.running:
                self._sniffer.stop(join=True)
            self._sniffer = None

    def _run_mock(
        self,
        on_detection: Callable[[WifiProbeDetection], None],
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.is_set():
            try:
                detection = self._mock_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            on_detection(detection)

    def _handle_packet(self, packet, on_detection: Callable[[WifiProbeDetection], None]) -> None:
        detection = self._parse_packet(packet)
        if detection is not None:
            on_detection(detection)

    def _parse_packet(self, packet) -> Optional[WifiProbeDetection]:
        if not packet.haslayer(Dot11):
            return None

        dot11 = packet[Dot11]
        if int(getattr(dot11, "type", -1)) != 0:
            return None

        subtype = int(getattr(dot11, "subtype", -1))
        frame_type = _MANAGEMENT_SUBTYPES.get(subtype)
        if frame_type is None:
            return None

        mac_address = str(getattr(dot11, "addr2", "") or getattr(dot11, "addr3", "")).upper()
        if not mac_address:
            return None

        return WifiProbeDetection(
            mac_address=mac_address,
            frame_type=frame_type,
            ssid=self._extract_ssid(packet),
            rssi=self._extract_rssi(packet),
            interface=self.interface,
            channel=self._extract_channel(packet),
        )

    def _extract_ssid(self, packet) -> Optional[str]:
        elt = packet.getlayer(Dot11Elt)
        while elt is not None:
            if getattr(elt, "ID", None) == 0:
                raw_info = getattr(elt, "info", b"")
                if isinstance(raw_info, bytes):
                    decoded = raw_info.decode(errors="ignore")
                else:
                    decoded = str(raw_info)
                return decoded or None
            elt = elt.payload.getlayer(Dot11Elt)
        return None

    def _extract_rssi(self, packet) -> Optional[int]:
        value = getattr(packet, "dBm_AntSignal", None)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _extract_channel(self, packet) -> Optional[int]:
        elt = packet.getlayer(Dot11Elt)
        while elt is not None:
            if getattr(elt, "ID", None) == 3:
                raw_info = getattr(elt, "info", b"")
                if isinstance(raw_info, bytes) and raw_info:
                    return int(raw_info[0])
            elt = elt.payload.getlayer(Dot11Elt)
        return None
