<#
.SYNOPSIS
    Sets (or reverts) a static IP on the laptop's Wi-Fi adapter for the
    closed Signally-Demo network.

.DESCRIPTION
    The TP-Link router's DHCP reservation for this laptop's MAC proved
    unreliable across a router reboot (confirmed 2026-09-03 - even a full
    release/renew still returned a different address than the one
    reserved). Since the phone's saved backend-connection URL depends on
    the laptop having a known, stable IP, this sets a static IP directly
    on the Wi-Fi adapter instead of trusting the router's DHCP server.

    Run this AFTER connecting to Signally-Demo, before starting the ARP
    agent or expecting the phone to reach the relay.

    Run with -Revert BEFORE reconnecting to any other Wi-Fi network (e.g.
    Tali) - a static IP left in place would break connectivity anywhere
    else, since 192.168.0.4/24 is specific to Signally-Demo's subnet.

.PARAMETER Revert
    Switch back to automatic (DHCP) addressing instead of setting the
    static IP. Use this before leaving Signally-Demo.
#>

param(
    [switch]$Revert
)

$ErrorActionPreference = "Stop"
$AdapterName = "Wi-Fi"
$StaticIP = "192.168.0.4"
$SubnetMask = "255.255.255.0"
$Gateway = "192.168.0.1"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Re-run this script from an elevated (Run as Administrator) PowerShell window."
    exit 1
}

if ($Revert) {
    Write-Host "Reverting $AdapterName to automatic (DHCP) addressing..."
    netsh interface ipv4 set address name="$AdapterName" source=dhcp
    netsh interface ipv4 set dnsservers name="$AdapterName" source=dhcp
    Write-Host "Done. Safe to reconnect to a normal Wi-Fi network now."
} else {
    Write-Host "Setting $AdapterName to static ${StaticIP} for Signally-Demo..."
    netsh interface ipv4 set address name="$AdapterName" source=static address=$StaticIP mask=$SubnetMask gateway=$Gateway
    Start-Sleep -Seconds 2
    Write-Host "Confirming:"
    Get-NetIPAddress -InterfaceAlias $AdapterName -AddressFamily IPv4 | Select-Object IPAddress
    Write-Host ""
    Write-Host "Phone connection panel URL: http://${StaticIP}:8000"
    Write-Host "Remember to run with -Revert before reconnecting to any other Wi-Fi network."
}
