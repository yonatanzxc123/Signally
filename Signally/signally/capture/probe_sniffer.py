"""
802.11 Probe Request sniffer.

Phones broadcast probe requests over the air when scanning for known WiFi
networks. Capturing these frames lets us detect devices (and their real MACs)
before they associate with the network — and before MAC randomization kicks in
for association.

Requirements:
- A Wi-Fi adapter that supports monitor mode
- The adapter must already be placed in monitor mode before calling sniff()
  (on Linux: `sudo ip link set <iface> down && sudo iw <iface> set monitor none
              && sudo ip link set <iface> up`)
- Root / administrator privileges for raw frame capture

NOTE: Monitor mode is NOT supported by most Windows Wi-Fi drivers. This module
is intended for the Raspberry Pi / Linux deployment target described in the
Signally spec.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProbeResult:
    """A single probe-request observation."""

    mac_address: str          # source MAC from the 802.11 frame header
    ssid: str = ""            # SSID being searched for (empty = wildcard probe)


class ProbeSniffer:
    """
    Sniffs 802.11 probe request frames on a monitor-mode interface.

    Usage::

        sniffer = ProbeSniffer(iface="wlan0mon")
        results = sniffer.sniff(duration=30)
        for r in results:
            print(r.mac_address, r.ssid)
    """

    def __init__(self, iface: str) -> None:
        self.iface = iface

    def sniff(self, duration: int = 30) -> list[ProbeResult]:
        """
        Capture probe request frames for ``duration`` seconds.

        Returns a deduplicated list of ProbeResult, one per unique source MAC.
        (Only the first observed SSID for each MAC is kept — subsequent probes
        from the same device within the window are silently ignored.)
        """
        try:
            from scapy.all import sniff as scapy_sniff, Dot11, Dot11ProbeReq, Dot11Elt  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "scapy is required for probe sniffing. Install it with: pip install scapy"
            ) from exc

        seen: dict[str, ProbeResult] = {}

        def _handle(pkt) -> None:
            # Keep only management frames (type=0) that are probe requests (subtype=4)
            if not (pkt.haslayer(Dot11) and pkt.haslayer(Dot11ProbeReq)):
                return

            mac = pkt[Dot11].addr2
            if mac is None:
                return

            mac = mac.upper()

            # Skip broadcast / multicast source MACs (malformed frames)
            if mac in ("FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"):
                return

            if mac in seen:
                return  # already recorded this device

            ssid = ""
            if pkt.haslayer(Dot11Elt):
                elt = pkt[Dot11Elt]
                if elt.ID == 0 and elt.info:  # ID 0 = SSID element
                    try:
                        ssid = elt.info.decode("utf-8", errors="replace")
                    except Exception:
                        ssid = ""

            result = ProbeResult(mac_address=mac, ssid=ssid)
            seen[mac] = result
            logger.info(
                "Probe request: MAC=%s SSID=%r",
                mac,
                ssid if ssid else "<wildcard>",
            )

        import platform
        if platform.system() == "Windows":
            raise RuntimeError(
                "Probe request sniffing requires monitor mode, which Windows Wi-Fi "
                "drivers do not support. Run this on the Raspberry Pi (Linux) with a "
                "monitor-mode capable adapter such as the Alfa AWUS036ACH.\n\n"
                "To set up monitor mode on Linux:\n"
                "  sudo ip link set <iface> down\n"
                "  sudo iw <iface> set monitor none\n"
                "  sudo ip link set <iface> up\n"
                "Then pass the interface name (e.g. wlan1) to --iface."
            )

        logger.info(
            "Starting probe sniffer on interface %r for %ds", self.iface, duration
        )
        try:
            scapy_sniff(
                iface=self.iface,
                prn=_handle,
                timeout=duration,
                store=False,
            )
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Failed to open interface {self.iface!r} for sniffing. "
                "Make sure the adapter exists, is in monitor mode, and you have root privileges."
            ) from exc

        logger.info("Probe sniff complete: %d unique device(s) seen", len(seen))
        return list(seen.values())
