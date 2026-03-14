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

from typing import List

from scapy.all import ARP, Ether, srp  # type: ignore

from signally.network_scanner.dto import DiscoveredDevice


class NetworkScanner:
    """
    Scans the local network using ARP broadcast requests.

    ARP scan logic:
    1. Send a broadcast Ethernet frame.
    2. Ask every host in the target subnet: "Who has this IP?"
    3. Collect replies containing IP and MAC addresses.
    """

    def scan(self, target_cidr: str, timeout: int = 2) -> List[DiscoveredDevice]:
        """
        Perform an ARP scan over the given CIDR range.

        Example target: 192.168.1.0/24
        """

        arp_request = ARP(pdst=target_cidr)
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = broadcast / arp_request

        answered, _ = srp(packet, timeout=timeout, verbose=False)

        discovered: List[DiscoveredDevice] = []
        for _, response in answered:
            discovered.append(
                DiscoveredDevice(
                    ip_address=str(response.psrc),
                    mac_address=str(response.hwsrc).upper(),
                )
            )

        return discovered
