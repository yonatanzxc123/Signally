"""
Network scanner module.

This module is responsible only for discovering devices on the network.
It does not know anything about the database.

This separation is important in OOP design:
- scanner => discovery responsibility
- services => business logic responsibility
- models => persistence responsibility
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import struct
from typing import List, Optional

from scapy.all import ARP, Ether, srp  # type: ignore

from signally.network_scanner.dto import DiscoveredDevice

logger = logging.getLogger(__name__)


def _get_local_subnet() -> Optional[str]:
    """
    Detect the local machine's IP and subnet mask, then return
    the network CIDR (e.g. '192.168.1.0/24').

    Works on Linux, macOS, and Windows without extra dependencies.
    Uses a UDP connect trick to find the outbound interface IP,
    then reads the subnet mask via a platform socket ioctl (Linux/macOS)
    or falls back to /24 on Windows.
    """
    import platform

    # Step 1: find the local IP used to reach the outside world
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except OSError:
        logger.warning("Could not determine local IP address")
        return None

    logger.debug("Local IP detected: %s", local_ip)

    # Step 2: get the subnet mask for that interface
    if platform.system() == "Windows":
        # On Windows, use socket.getaddrinfo or fall back to /24
        try:
            import subprocess
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
            )
            mask = _parse_windows_mask(result.stdout, local_ip)
        except Exception:
            mask = None

        if not mask:
            logger.debug("Windows mask detection failed, defaulting to /24")
            mask = "255.255.255.0"
    else:
        # Linux / macOS: use ioctl SIOCGIFNETMASK
        try:
            import fcntl
            import array

            SIOCGIFNETMASK = 0x891B  # Linux
            if platform.system() == "Darwin":
                SIOCGIFNETMASK = 0xC0206921

            # Find the interface name that has local_ip
            iface = _find_interface(local_ip)
            if iface is None:
                mask = "255.255.255.0"
            else:
                ifreq = struct.pack("16sH2s4s8s", iface.encode(), socket.AF_INET, b"\x00" * 2, b"\x00" * 4, b"\x00" * 8)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    res = fcntl.ioctl(s.fileno(), SIOCGIFNETMASK, ifreq)
                mask = socket.inet_ntoa(res[20:24])
        except Exception as exc:
            logger.debug("ioctl mask detection failed (%s), defaulting to /24", exc)
            mask = "255.255.255.0"

    logger.debug("Subnet mask: %s", mask)

    # Step 3: combine IP + mask → network CIDR
    network = ipaddress.IPv4Network(f"{local_ip}/{mask}", strict=False)
    cidr = str(network)
    logger.info("Auto-detected local subnet: %s", cidr)
    return cidr


def _parse_windows_mask(ipconfig_output: str, local_ip: str) -> Optional[str]:
    """Parse ipconfig output to find the subnet mask for the given IP."""
    lines = ipconfig_output.splitlines()
    found_ip = False
    for line in lines:
        if local_ip in line:
            found_ip = True
        if found_ip and "Subnet Mask" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                return parts[-1].strip()
    return None


def _find_interface(local_ip: str) -> Optional[str]:
    """Find the network interface name that holds the given IP (Linux/macOS)."""
    try:
        import subprocess
        result = subprocess.run(["ip", "addr"], capture_output=True, text=True)
        iface = None
        for line in result.stdout.splitlines():
            if line.startswith(" ") or line.startswith("\t"):
                if local_ip in line:
                    return iface
            else:
                parts = line.split(":")
                if len(parts) >= 2:
                    iface = parts[1].strip().split("@")[0]
    except Exception:
        pass
    return None


class NetworkScanner:
    """
    Scans the local network using ARP broadcast requests.

    ARP scan logic:
    1. Send a broadcast Ethernet frame.
    2. Ask every host in the target subnet: "Who has this IP?"
    3. Collect replies containing IP and MAC addresses.

    Can auto-detect the local subnet so you don't need to specify a CIDR.
    """

    def scan(self, target_cidr: Optional[str] = None, timeout: int = 2) -> List[DiscoveredDevice]:
        """
        Perform an ARP scan over the given CIDR range.

        If target_cidr is None, auto-detects the local subnet from
        the machine's active network interface (e.g. the WiFi network
        the machine is connected to).

        Example target: 192.168.1.0/24
        """
        if target_cidr is None:
            target_cidr = _get_local_subnet()
            if target_cidr is None:
                logger.error("Could not auto-detect local subnet. Pass target_cidr explicitly.")
                return []

        logger.info("Starting ARP scan on %s (timeout=%ds)", target_cidr, timeout)

        arp_request = ARP(pdst=target_cidr)
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = broadcast / arp_request

        answered, _ = srp(packet, timeout=timeout, verbose=False)

        discovered: List[DiscoveredDevice] = []
        for _, response in answered:
            device = DiscoveredDevice(
                ip_address=str(response.psrc),
                mac_address=str(response.hwsrc).upper(),
            )
            logger.debug("Found device: %s @ %s", device.mac_address, device.ip_address)
            discovered.append(device)

        logger.info("Scan complete: %d device(s) found", len(discovered))
        return discovered
