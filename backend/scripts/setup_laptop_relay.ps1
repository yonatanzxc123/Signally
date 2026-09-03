<#
.SYNOPSIS
    One-time (idempotent) setup of the laptop-side relay that lets a phone
    on the closed Wi-Fi network reach the Pi, which is only reachable over
    the private USB-Ethernet gadget link.

.DESCRIPTION
    The Pi has no presence on the closed Wi-Fi network (wlan0/wlan1 are
    both dedicated to passive CSI/probe monitor-mode capture, never
    associated). The laptop is the only device on both networks at once
    (Wi-Fi to the closed network, USB to the Pi at 10.12.194.1). This
    script adds a static Windows port-forward ("portproxy") rule so
    anything hitting the laptop's port 8000 - on ANY of its interfaces,
    including its closed-Wi-Fi IP - gets relayed to the Pi's backend.

    Point the phone's BackendConnectionPanel at the laptop's closed-Wi-Fi
    IP (printed at the end of this script), not the Pi's address directly.

    Safe to re-run: removes any existing rule with the same listen port
    before re-adding, so it never duplicates.

.PARAMETER ConnectAddress
    The Pi's address on the private USB link. Default: 10.12.194.1

.PARAMETER ConnectPort
    The Pi backend's port. Default: 8000

.PARAMETER ListenPort
    The port the laptop listens on for relayed traffic. Default: 8000
#>

param(
    [string]$ConnectAddress = "10.12.194.1",
    [int]$ConnectPort = 8000,
    [int]$ListenPort = 8000
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Re-run this script from an elevated (Run as Administrator) PowerShell window. portproxy and firewall rules both require admin rights."
    exit 1
}

Write-Host "Removing any existing portproxy rule on listenport=$ListenPort (safe if none exists)..."
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$ListenPort | Out-Null

Write-Host "Adding portproxy rule: 0.0.0.0:$ListenPort -> ${ConnectAddress}:${ConnectPort} ..."
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$ListenPort connectaddress=$ConnectAddress connectport=$ConnectPort

$firewallRuleName = "Signally API relay"
$existingRule = Get-NetFirewallRule -DisplayName $firewallRuleName -ErrorAction SilentlyContinue
if ($existingRule) {
    Write-Host "Firewall rule '$firewallRuleName' already exists, leaving it as-is."
} else {
    Write-Host "Adding firewall rule '$firewallRuleName' (allow inbound TCP $ListenPort)..."
    New-NetFirewallRule -DisplayName $firewallRuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $ListenPort | Out-Null
}

Write-Host ""
Write-Host "Current portproxy rules:"
netsh interface portproxy show v4tov4

Write-Host ""
Write-Host "This laptop's IPv4 addresses (give the phone the Wi-Fi one, on the closed network):"
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne "127.0.0.1" } |
    Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize

Write-Host ""
Write-Host "Verify end-to-end once the laptop is on the closed Wi-Fi:"
Write-Host "  curl.exe http://<this-laptop-wifi-ip>:$ListenPort/system/state"
Write-Host "Phone connection panel URL:"
Write-Host "  http://<this-laptop-wifi-ip>:$ListenPort"
