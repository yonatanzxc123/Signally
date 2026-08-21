# Signally Correlation Flow

## Purpose

The correlation service combines three independent signals into one security
decision. It does not treat every signal as a person or device.

```text
Laptop ARP scan ─┐
Pi CSI detector ─┼─> SystemStateService ─> CorrelationService ─> SAFE/REVIEW/ALERT
Pi Wi-Fi probe  ─┘
```

The frontend requests `GET /system/state` every second and displays the returned
decision, reason, and sensor health.

## Inputs

### ARP: network identity

The laptop scans the classroom network through its Wi-Fi adapter and submits
IP/MAC observations to the Pi through USB gadget networking:

```text
Laptop ARP agent -> POST /arp/ingest -> DeviceService -> presence snapshot
```

The existing database classifies observed devices as:

- `AUTHORIZED`: approved Admin, Family, or Guest device;
- `PENDING`: unknown device;
- `BLOCKED`: explicitly blocked device.

ARP is the only source that contributes identified devices to
`current_intruder_count`.

### CSI: physical motion

Nexmon CSI packets arrive continuously on the Pi. The detector compares the
current normalized motion metric with a quiet-room baseline and threshold.

CSI answers “is physical motion crossing the tripwire?” It does not identify a
device or person, so it does not increase the intruder count.

### Wi-Fi probing: nearby activity

The Pi's USB Wi-Fi adapter remains in monitor mode. Strong client probe-request
frames seen during the rolling window become nearby-activity evidence.

Probe MAC addresses may be randomized. Probe activity can influence a decision,
but it is not a reliable person/device count.

## Processing

`SystemStateService` reads one snapshot from each source and passes a
`CorrelationContext` to `CorrelationService`:

```text
Security mode: HOME or AWAY
Connected ARP presence: authorized, pending, blocked, roles
CSI: recent motion true/false
Probing: recent activity true/false
```

The engine evaluates rules in priority order:

1. Blocked ARP device -> `ALERT / CRITICAL`.
2. Unknown ARP device in Home -> `REVIEW`.
3. Unknown ARP device in Away -> review-grace handling, then `ALERT`.
4. CSI motion in Away -> currently `ALERT / MEDIUM`.
5. Probe-only activity in Away -> `ALERT / MEDIUM`.
6. CSI motion in Home without approved presence -> `REVIEW / LOW`.
7. CSI motion in Home with approved presence -> `SAFE`.
8. No suspicious evidence -> `SAFE`.

Blocked and identified unknown devices have priority over sensor-only evidence.
When both CSI and probing are active without a higher-priority ARP result, CSI
is the primary reason and both evidence flags remain visible in `/system/state`.

## Examples

```text
HOME + approved ARP + CSI motion
-> SAFE: expected trusted presence
```

```text
HOME + no approved ARP + CSI motion
-> REVIEW: physical activity in relaxed mode
```

```text
AWAY + blocked ARP device
-> ALERT / CRITICAL
```

```text
AWAY + probe activity, no CSI or connected unknown device
-> ALERT / MEDIUM, intruder count remains zero
```

```text
AWAY + CSI motion
-> ALERT / MEDIUM, intruder count remains zero
```

## Confirmed CSI Policy

The system is armed when `security_mode == AWAY`. A positive CSI detection while
armed must create an alert:

```text
security_mode == AWAY AND csi_presence_detected == true
-> ALERT / MEDIUM
```

Here, "CSI motion while armed," "CSI detection in Away," and "Away + CSI" all
describe the same condition. CSI does not identify a device or person, so the
alert's `current_intruder_count` remains zero.

## Detailed Runtime Call Chain

There are two ways `SystemStateService.collect_state()` runs:

```text
Frontend GET /system/state
    -> run_scan=False
    -> persist_alerts=False
    -> return a fresh decision for display

BackgroundMonitor every 10 seconds
    -> run_scan=True
    -> local Pi ARP scan only when enabled
    -> persist_alerts=True
    -> save ALERT events with cooldown protection
```

In the classroom architecture, `SIGNALLY_LOCAL_ARP_SCAN_ENABLED=false` prevents
the background monitor from scanning the Pi's USB subnet. Laptop-submitted ARP
observations still enter the same database independently.

The one-second frontend polling makes the displayed decision responsive, but it
does not itself persist alerts. Persisted alert latency is controlled by the
background-monitor interval and CSI's recent-motion latch.

## ARP Path in Detail

The laptop agent performs this loop:

```text
Scapy Ethernet broadcast / ARP request on laptop Wi-Fi
    -> collect unique MAC/IP responses
    -> assign UUID scan_id and UTC captured_at
    -> POST /arp/ingest over USB gadget networking
```

The Pi validates the shared ingest token, IP/MAC syntax, identifiers, capture
timestamp age, and duplicate or concurrently processing scan IDs. The scan
tracker reserves an ID before database work. Success records scanner health;
failure releases the ID so the laptop can retry.

Each observation then passes through the existing `DeviceService`:

```text
new MAC
    -> create PENDING Device
    -> set first_seen and last_seen
    -> log DEVICE_DISCOVERED_NEW

known MAC
    -> update IP and last_seen
    -> preserve AUTHORIZED/PENDING/BLOCKED status and owner role
    -> log DEVICE_SEEN_AGAIN
```

`PresenceService` reads recent discovery/seen events and considers a device
present only inside `SIGNALLY_PRESENCE_WINDOW_SECONDS` (30 seconds by default).
Guest authorization can expire and return the device to `PENDING`.

## CSI Path in Detail

The real CSI provider runs continuously in its own thread:

```text
UDP/5500 Nexmon frame
    -> validate header and 64/128/256-subcarrier width
    -> decode I/Q pairs into amplitudes
    -> Hampel-filter per-frame outliers
    -> normalize amplitude vector
    -> calculate temporal variance over rolling frames
    -> compare metric with baseline * factor
    -> publish one atomic CsiState snapshot
```

Startup assumes a quiet room. The detector fills its complete rolling window,
then learns the median of several full-window metrics. Detection is disabled
until calibration completes.

`CsiState` separates:

- `currently_detected`: newest detector result;
- `recently_detected`: latched evidence retained for monitoring;
- `receiving_data`: whether valid packets arrived recently;
- `ready`: fresh stream with completed calibration;
- metric, baseline, threshold, confidence, counters, and last error.

`SystemStateService` correlates `recently_detected`, allowing a short crossing to
survive between monitoring cycles. A failed/stale real stream stays visibly
real and unhealthy; it does not silently become mock no-motion data.

## Wi-Fi Probe Path in Detail

`WifiProbingState` owns a sniffer thread on monitor-mode `wlan1`. Only client
`probe_req` frames passing `SIGNALLY_WIFI_PROBING_STRONG_RSSI_MIN` are persisted.
Beacons, responses, authentication, and association frames are ignored.

Accepted probes become events, not device rows. The 30-second default window
exposes activity, observation count, diagnostic unique-MAC count, and first
observation time. Unique MACs can rise and fall because probes are intermittent
and addresses are randomized; they are not an intruder count.

## Decision Object and Count Semantics

Every rule returns a `CorrelationDecision` containing decision, severity, human
reason, mode, active role flags, evidence summary, notification audience, and
`current_intruder_count`.

```text
PENDING connected ARP device -> contributes to intruder count
BLOCKED connected device     -> forces at least one for critical reporting
CSI motion                   -> never contributes a count
Probe activity/random MAC    -> never contributes a count
```

## Rule Precedence Consequences

The engine returns after the first matching rule, so order is behavior:

| Evidence | Mode | Current first matching result |
|---|---|---|
| Blocked ARP + anything | Any | `ALERT / CRITICAL` |
| Pending ARP | Home | `REVIEW / MEDIUM` |
| Pending ARP + Admin within review grace | Away | `REVIEW / MEDIUM` |
| Pending ARP after grace/no Admin | Away | `ALERT`, High with CSI |
| CSI without a higher ARP rule | Away | currently `ALERT / MEDIUM` |
| Probe without CSI/higher ARP rule | Away | `ALERT / MEDIUM` |
| CSI, no approved device | Home | `REVIEW / LOW` |
| CSI + approved device | Home | `SAFE / LOW` |

A pending-device Admin-review rule currently occurs before the CSI-only Away
rule. Therefore simultaneous pending ARP, Admin grace and CSI returns Review;
the standalone Away + CSI branch is reached only when no higher rule matched.

## Alert Persistence

A displayed decision and a persisted alert are different:

```text
CorrelationDecision
    -> returned whenever state is collected

Persisted alert Event
    -> created only with persist_alerts=True
    -> normally performed by BackgroundMonitor
```

Blocked alerts attach the first blocked MAC. Other alerts attach the first
pending MAC when available; sensor-only alerts have no device MAC. Details store
the mode, reason, device counts, probe count, and CSI state. The configured alert
cooldown prevents identical details from being stored repeatedly.

## API and Frontend Mapping

`GET /system/state` returns the authoritative decision together with raw CSI,
probe activity, ARP health, device lists/counts, roles, and recent alerts. The
frontend does not reproduce the correlation rules. It polls system state every
second and displays the backend result; device/event lists have slower polling.

## Health and Failure Semantics

- Missing/stale CSI is health failure, not proof of an empty room.
- Pi-local ARP scan failure records `scan_error` instead of crashing collection.
- Laptop ARP freshness is exposed through `/arp/status` and system state.
- Probe-thread failure is stored as probing `last_error` and logged.
- ARP replay/health tracking resets on backend restart; devices/events persist.
- Frontend polling refreshes decisions; the background monitor persists alerts.

## Main Implementation Files

- `signally/services/system_state_service.py`: evidence assembly.
- `signally/services/correlation_service.py`: ordered rules.
- `signally/services/presence_service.py`: recent ARP presence.
- `signally/services/device_service.py`: device persistence/status.
- `signally/sensors/csi_provider.py`: UDP receiver and atomic CSI state.
- `signally/sensors/csi_detector.py`: baseline and motion calculation.
- `signally/wifi_probing/wifi_probing_service.py`: probe events/window.
- `signally/network_scanner/arp_scan_tracker.py`: replay and scanner health.
- `signally/api/app.py`: API mapping and ingestion endpoints.
- `SignallyApp/src/screens/HomeScreen.tsx`: polling and display.

## Exact Code Walkthrough

The references below describe the current implementation, not only the intended
architecture. Line numbers are useful starting points and may move after edits;
the function names are the stable reference.

### 1. The frontend asks for the combined state

`SignallyApp/src/screens/HomeScreen.tsx:93` configures React Query to refresh
every 1,000 ms. The request itself is defined by `getSystemState()` in
`SignallyApp/src/api/client.ts:222`, which calls `GET /system/state`.

The route is `get_system_state()` in `signally/api/app.py:799`. It creates the
services and calls:

```python
collect_state(run_scan=False, persist_alerts=False)
```

Consequently, a frontend refresh reads the latest evidence and evaluates it,
but it neither starts an ARP scan nor writes a new alert event.

### 2. The periodic monitoring cycle performs side effects

At backend startup, `on_startup()` in `signally/api/app.py:238` starts the
`BackgroundMonitor` when `SIGNALLY_AUTO_START_MONITORING` is enabled.
`BackgroundMonitor.run_once()` in
`signally/services/background_monitor.py:63` calls:

```python
collect_state(run_scan=True, persist_alerts=True)
```

The loop repeats using `SIGNALLY_MONITOR_INTERVAL_SECONDS`, which defaults to
10 seconds in `signally/config.py:41`. This is the path that may perform a local
ARP scan and persist an `ALERT`. The manual equivalent is
`POST /monitoring/run-cycle` in `signally/api/app.py:812`.

### 3. Laptop ARP results enter the backend

The laptop agent builds the destination `/arp/ingest` in
`scripts/laptop_arp_agent.py:41`. `ingest_arp_scan()` in
`signally/api/app.py:430` then performs these exact checks:

1. Lines 434-437 require the configured ingestion token and compare the
   `X-Signally-Ingest-Token` header.
2. Lines 439-443 normalize `captured_at` and reject future or stale scans. The
   default maximum age is 30 seconds (`signally/config.py:75`).
3. Lines 445-446 call `ArpScanTracker.reserve(scan_id)` and reject a duplicate
   scan ID with HTTP 409.
4. Lines 448-454 normalize each MAC address and construct
   `DiscoveredDevice` values.
5. Lines 458-459 pass the values to
   `DeviceService.process_scan_results()`.
6. Lines 460-465 mark the scan complete and update ingestion health.

`DeviceService.process_scan_results()` in
`signally/services/device_service.py:35` creates unseen devices as `PENDING`
and refreshes the `last_seen`/IP data for known devices without erasing their
approved or blocked status.

Replay and health metadata live in memory in `ArpScanTracker` at
`signally/network_scanner/arp_scan_tracker.py:21`; the device records themselves
live in the database. Therefore a backend restart forgets received scan IDs and
last-ingestion health, but it does not forget approved/pending/blocked devices.

For the classroom laptop-driven architecture,
`SIGNALLY_LOCAL_ARP_SCAN_ENABLED=false` is required. Otherwise the
`run_scan=True` monitoring path at `system_state_service.py:101` can also try to
scan from the Pi.

### 4. ARP records become connected-presence evidence

`PresenceService.get_present_devices()` in
`signally/services/presence_service.py:43` selects devices whose `last_seen` is
inside the connected-device presence window. `get_presence_snapshot()` at line
74 partitions those records into:

- approved/authorised connected devices;
- pending connected devices;
- blocked connected devices;
- Admin, Family, and Guest presence flags.

This is why ARP evidence can identify a known person or an unknown connected
device, while CSI and randomized probes cannot.

### 5. CSI packets become motion evidence

`RealCsiDetectionProvider._capture_loop()` in
`signally/sensors/csi_provider.py:189` owns the UDP receive loop. For each valid
Nexmon packet it parses amplitudes and calls `CsiMotionDetector.update()` at
`signally/sensors/csi_detector.py:121`.

The detector fills a rolling window, establishes a baseline, calculates the
motion metric and compares it with its threshold. The provider publishes the
result from `get_state()` at `csi_provider.py:157`:

- line 171 sets `currently_detected` from the newest ready reading;
- line 172 sets `recently_detected` from the detection latch;
- the same state includes stream freshness, readiness, metric, baseline,
  threshold, confidence, frame counters and error information.

`SystemStateService.collect_state()` reads that state at lines 109-122 and uses
`recently_detected` as `csi_presence_detected`. Thus a brief tripwire crossing
can still participate in a correlation cycle after the immediate metric falls.
`GET /csi/status` at `signally/api/app.py:793` exposes the same provider state
for diagnostics.

### 6. Probe frames become nearby-activity evidence

`WifiProbingState.start()` in
`signally/wifi_probing/wifi_probing_state.py:30` starts the sniffer thread.
`WifiProbeDetector._parse_packet()` at
`signally/wifi_probing/wifi_probe_detector.py:96` accepts probe-request frames
and extracts MAC, SSID, RSSI and channel.

`WifiProbingService.handle_detection()` at
`signally/wifi_probing/wifi_probing_service.py:35` persists an accepted event.
`_has_strong_signal()` at line 88 requires RSSI greater than or equal to
`SIGNALLY_WIFI_PROBING_STRONG_RSSI_MIN`, default `-60 dBm` in
`signally/config.py:90`.

`get_presence_snapshot()` at line 44 reads recent probe events and returns
activity plus a diagnostic unique-MAC count. The correlation engine uses this
as activity evidence. It does not treat that count as people because client MAC
addresses can be randomized and probe transmissions are intermittent.

### 7. All evidence is assembled once

`SystemStateService.collect_state()` in
`signally/services/system_state_service.py:93` is the integration point. In
order, it:

1. optionally performs Pi-local ARP (`lines 101-108`);
2. reads CSI (`lines 109-123`);
3. reads connected ARP presence and recent probe activity (`lines 124-125`);
4. reads Home/Away mode (`line 126`);
5. constructs `CorrelationContext` (`lines 128-134`);
6. invokes `CorrelationService.evaluate()` (`line 135`);
7. persists only an `ALERT` when requested (`lines 137-138`);
8. returns raw evidence and the decision in one `SystemStateSnapshot`.

### 8. Exact correlation rules and code instances

All rules are in `CorrelationService.evaluate()` at
`signally/services/correlation_service.py:17`. Every branch returns immediately,
so a later rule cannot override an earlier one.

#### Rule 1: blocked connected device

At lines 22 and 35, any device present in `blocked_connected_devices` returns
`ALERT / CRITICAL`. This applies in both Home and Away and wins over CSI, probes,
approved presence and pending-device rules. The intruder count is forced to at
least one at line 46.

#### Rule 2: pending connected device in Home

At lines 51-68, `connected_intruder_count > 0 and not away_mode` returns
`REVIEW / MEDIUM`. If Admin review grace is active, only Admin is the intended
audience; otherwise Admin and Family are included.

#### Rule 3: pending device in Away with Admin grace

At lines 71-86, a pending connected device plus `admin_present` and an active
grace window returns `REVIEW / MEDIUM` for Admin. Because this is above the CSI
branch, simultaneous CSI does not change this result.

The grace calculation is `_is_admin_review_grace_active()` at lines 185-202.
It chooses the earliest pending-device `first_seen` or probe `first_probe_seen_at`
and compares its age with `SIGNALLY_ADMIN_REVIEW_GRACE_SECONDS`, default 30
seconds in `signally/config.py:38`.

#### Rule 4: pending device in Away without applicable grace

At lines 89-104, any remaining pending connected device returns an Alert. Its
severity is `HIGH` when CSI is also detected and `MEDIUM` otherwise. This is the
only current branch where CSI explicitly upgrades an ARP decision.

#### Rule 5: CSI in Away without a higher-priority ARP result

At lines 107-120, `away_mode and csi_detected` currently returns
`ALERT / MEDIUM`, even when an approved device is present. It reports zero
intruders because CSI proves motion, not identity or a device count.

This is the confirmed armed-tripwire rule: `away_mode` means the system is armed
and `csi_detected` means CSI detected movement. The result is an Alert even if
there is no ARP-identified device, while the intruder count remains zero.

#### Rule 6: probe activity in Away

At lines 124-137, Away plus recent probe activity returns `ALERT / MEDIUM` if no
higher rule matched. It also reports zero intruders. The activity can come from
`probe_activity_detected` or a positive diagnostic probe count (lines 27-28).

#### Rule 7: CSI in Home with no approved user

At lines 141-154, CSI plus Home mode and no approved connected user returns
`REVIEW / LOW` for Admin. This means “physical activity needs review,” not “one
intruder exists.”

#### Rule 8: CSI in Home with an approved user

At lines 157-169, CSI plus Home mode and approved presence returns `SAFE / LOW`
with the reason that an authorized user is present.

#### Rule 9: fallback

At lines 172-182, any state not matched above returns `SAFE / LOW` and “No
unknown activity detected.”

### 9. When an Alert is written to the database

`SystemStateService._persist_alert()` at
`signally/services/system_state_service.py:158` attaches a blocked-device Alert
to the first blocked MAC. Otherwise it attaches an unauthorized-presence Alert
to the first pending MAC, or no MAC for CSI/probe-only evidence.

`AlertService.raise_unauthorized_presence_alert()` and
`raise_blocked_device_alert()` are at
`signally/services/alert_service.py:36` and `:57`. The default duplicate-alert
cooldown is 60 seconds (`signally/config.py:43`). `REVIEW` and `SAFE` decisions
are never persisted by the `persist_alerts` condition at
`system_state_service.py:137`.

### 10. What the frontend actually displays

`to_system_state_response()` in `signally/api/app.py:158` maps the decision,
CSI state, probe activity, device partitions, ingestion health and recent
alerts into one response. `HomeScreen.tsx` refreshes that response every second.
The frontend does not independently decide whether evidence is Safe, Review or
Alert; changing the correlation policy belongs in `CorrelationService`.

Device and event contexts refresh every five seconds in
`SignallyApp/src/context/DevicesContext.tsx:48` and
`SignallyApp/src/context/EventsContext.tsx:56`. This explains why the main state
can visibly change before a device/event list catches up.

## Source Excerpts

This section contains actual excerpts from the implementation. Each block names
its source directly above it.

### Laptop: perform and submit an ARP scan

Source: `backend/scripts/laptop_arp_agent.py`, functions `scan()` and `submit()`.

```python
def scan(target: str, interface: str | None, timeout: float) -> list[dict[str, str]]:
    answered, _ = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target),
        iface=interface,
        timeout=timeout,
        verbose=False,
    )
    seen: dict[str, str] = {}
    for _, response in answered:
        seen[str(response.hwsrc).upper()] = str(response.psrc)
    return [
        {"mac_address": mac, "ip_address": ip}
        for mac, ip in sorted(seen.items())
    ]


def submit(url: str, token: str, scanner_id: str, devices: list[dict[str, str]]) -> None:
    payload = {
        "scan_id": str(uuid.uuid4()),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "scanner_id": scanner_id,
        "devices": devices,
    }
    response = httpx.post(
        url.rstrip("/") + "/arp/ingest",
        headers={"X-Signally-Ingest-Token": token},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
```

This is the code that makes ARP a laptop responsibility. It scans the laptop's
selected network interface, then sends the observations to the Pi backend over
the configured backend address, which can be the USB-gadget IP.

### Pi backend: validate and accept the laptop ARP result

Source: `backend/signally/api/app.py`, function `ingest_arp_scan()`.

```python
@app.post("/arp/ingest", response_model=ArpIngestionResponse)
def ingest_arp_scan(
    request: ArpIngestionRequest,
    x_signally_ingest_token: Optional[str] = Header(default=None),
):
    if not ARP_INGEST_TOKEN:
        raise HTTPException(status_code=503, detail="ARP ingestion token is not configured")
    if x_signally_ingest_token != ARP_INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid ARP ingestion token")

    received_at = utc_now()
    captured_at = _normalized_utc(request.captured_at)
    age = (received_at - captured_at).total_seconds()
    if age < -5 or age > ARP_INGEST_MAX_AGE_SECONDS:
        raise HTTPException(status_code=422, detail="ARP scan is stale or has an invalid timestamp")

    if not arp_scan_tracker.reserve(request.scan_id):
        raise HTTPException(status_code=409, detail="ARP scan ID was already processed")

    discovered = [
        DiscoveredDevice(
            ip_address=item.ip_address.strip(),
            mac_address=item.mac_address.strip().upper(),
        )
        for item in request.devices
    ]
    session = get_db_session()
    try:
        services = build_services(session)
        processed = services["device_service"].process_scan_results(discovered)
        arp_scan_tracker.complete(
            request.scan_id,
            captured_at,
            received_at,
            len(request.devices),
        )
        return ArpIngestionResponse(
            accepted=True,
            processed_devices_count=len(processed),
            received_at=received_at,
        )
    except Exception:
        arp_scan_tracker.release(request.scan_id)
        raise
    finally:
        session.close()
```

The API rejects unauthenticated, stale and replayed submissions before passing
the devices into the persistent `DeviceService`.

### Wi-Fi probing: accept activity without creating a person count

Source: `backend/signally/wifi_probing/wifi_probing_service.py`, functions
`handle_detection()` and `get_presence_snapshot()`.

```python
def handle_detection(self, detection: WifiProbeDetection) -> None:
    if detection.frame_type != "probe_req" or not self._has_strong_signal(detection):
        return
    self.event_service.log_event(
        event_type=EVENT_WIFI_PROBE_NEARBY_ACTIVITY,
        details=self._build_details(detection),
        device_mac=detection.mac_address,
    )

def get_presence_snapshot(
    self,
    window_seconds: int = CURRENT_UNKNOWN_WINDOW_SECONDS,
) -> NearbyPresenceSnapshot:
    events = self._list_probe_events(window_seconds=window_seconds)

    seen_macs: Set[str] = set()
    first_probe_seen_at = None

    for event in events:
        if not event.device_mac:
            continue
        mac = event.device_mac.upper()
        event_time = self._event_time(event.created_at)
        if first_probe_seen_at is None or event_time < first_probe_seen_at:
            first_probe_seen_at = event_time
        seen_macs.add(mac)

    return NearbyPresenceSnapshot(
        nearby_probe_count=len(seen_macs),
        probe_activity_detected=len(events) > 0,
        probe_observation_count=len(events),
        first_probe_seen_at=first_probe_seen_at,
        window_seconds=window_seconds,
    )
```

The unique-MAC value is retained for diagnostics, but later correlation code
does not add it to `current_intruder_count`.

### CSI: expose immediate and latched detection separately

Source: `backend/signally/sensors/csi_provider.py`, method
`RealCsiDetectionProvider.get_state()`.

```python
def get_state(self) -> CsiState:
    now = time.monotonic()
    with self._lock:
        receiving = self._last_packet_time > 0 and now - self._last_packet_time < self._stale_after_seconds
        ready = receiving and self._detector.ready and now - self._started_time >= self._warmup_seconds
        recent = ready and self._last_detection_time > 0 and now - self._last_detection_time <= self._detection_hold_seconds
        packet_at = None
        if self._last_packet_time > 0:
            age = max(0.0, now - self._last_packet_time)
            packet_at = datetime.fromtimestamp(time.time() - age, tz=timezone.utc)
        return CsiState(
            provider_mode="real",
            receiving_data=receiving,
            ready=ready,
            currently_detected=ready and self._detected,
            recently_detected=recent,
            motion_metric=self._strength,
            baseline=self._detector.baseline,
            threshold=self._detector.threshold,
            baseline_factor=self._detector.baseline_factor,
            confidence=self._confidence,
            frames_received=self._frames_received,
            invalid_frames=self._invalid_frames,
            last_packet_at=packet_at,
            last_error=self._last_error,
        )
```

`currently_detected` represents the newest metric. `recently_detected` remains
true for the configured hold time, allowing the slower correlation cycle to see
a short crossing.

### Integration point: assemble all evidence and call the engine

Source: `backend/signally/services/system_state_service.py`, method
`SystemStateService.collect_state()`.

```python
if hasattr(self.csi_provider, "get_state"):
    csi_state = self.csi_provider.get_state()
else:
    detected = self.csi_provider.is_presence_detected()
    csi_state = CsiState(
        provider_mode="legacy",
        receiving_data=True,
        ready=True,
        currently_detected=detected,
        recently_detected=detected,
        motion_metric=self.csi_provider.get_presence_strength(),
    )
csi_detected = csi_state.recently_detected
csi_strength = csi_state.motion_metric
connected_presence = self.presence_service.get_presence_snapshot()
nearby_presence = self.wifi_probing_service.get_presence_snapshot()
security_state = self.security_mode_service.get_state()

context = CorrelationContext(
    csi_presence_detected=csi_detected,
    nearby_device_count=nearby_presence.nearby_probe_count,
    connected_presence=connected_presence,
    nearby_presence=nearby_presence,
    security_mode=security_state.mode,
)
decision = self.correlation_service.evaluate(context)

if persist_alerts and decision.decision == "ALERT":
    self._persist_alert(decision, connected_presence, nearby_presence, csi_detected)
```

This is the exact junction where CSI, ARP presence, probing and security mode
become one `CorrelationContext`.

### Correlation setup: derive the facts used by every branch

Source: `backend/signally/services/correlation_service.py`, method
`CorrelationService.evaluate()`.

```python
approved_present = context.connected_presence.approved_user_present
admin_present = context.connected_presence.admin_present
family_present = context.connected_presence.family_present
guest_present = context.connected_presence.guest_present
blocked_present = len(context.connected_presence.blocked_connected_devices) > 0
csi_detected = context.csi_presence_detected
security_mode = context.security_mode
away_mode = security_mode == SecurityMode.AWAY
connected_intruder_count = len(context.connected_presence.pending_connected_devices)
nearby_probe_count = context.nearby_presence.nearby_probe_count
nearby_probe_activity = (
    context.nearby_presence.probe_activity_detected or nearby_probe_count > 0
)
current_intruder_count = connected_intruder_count
review_grace_active = self._is_admin_review_grace_active(context)
```

Notice that only `pending_connected_devices` determines the intruder count.

### Correlation Rule 1: blocked ARP device

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
if blocked_present:
    return CorrelationDecision(
        decision="ALERT",
        severity="CRITICAL",
        reason="A blocked device is active on the network.",
        security_mode=security_mode,
        csi_presence_detected=csi_detected,
        nearby_device_count=context.nearby_device_count,
        approved_user_present=approved_present,
        admin_present=admin_present,
        family_present=family_present,
        guest_present=guest_present,
        current_intruder_count=max(1, current_intruder_count),
        notification_audience=["ADMIN", "FAMILY"],
    )
```

### Correlation Rule 2: pending ARP device while Home

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
if connected_intruder_count > 0 and not away_mode:
    audience = ["ADMIN"] if review_grace_active else ["ADMIN", "FAMILY"]
    return CorrelationDecision(
        decision="REVIEW",
        severity="MEDIUM",
        reason="Unknown activity detected while Home mode is active.",
        security_mode=security_mode,
        csi_presence_detected=csi_detected,
        nearby_device_count=context.nearby_device_count,
        approved_user_present=approved_present,
        admin_present=admin_present,
        family_present=family_present,
        guest_present=guest_present,
        current_intruder_count=current_intruder_count,
        admin_review_grace_active=review_grace_active,
        notification_audience=audience,
    )
```

### Correlation Rule 3: pending ARP device with Admin grace

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
if connected_intruder_count > 0 and admin_present and review_grace_active:
    return CorrelationDecision(
        decision="REVIEW",
        severity="MEDIUM",
        reason="Suspicious activity detected while Away mode is active. Admin review window is active.",
        security_mode=security_mode,
        csi_presence_detected=csi_detected,
        nearby_device_count=context.nearby_device_count,
        approved_user_present=approved_present,
        admin_present=admin_present,
        family_present=family_present,
        guest_present=guest_present,
        current_intruder_count=current_intruder_count,
        admin_review_grace_active=True,
        notification_audience=["ADMIN"],
    )
```

### Correlation Rule 4: pending ARP device in Away

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
if connected_intruder_count > 0:
    return CorrelationDecision(
        decision="ALERT",
        severity="HIGH" if csi_detected else "MEDIUM",
        reason="Suspicious activity detected while Away mode is active.",
        security_mode=security_mode,
        csi_presence_detected=csi_detected,
        nearby_device_count=context.nearby_device_count,
        approved_user_present=approved_present,
        admin_present=admin_present,
        family_present=family_present,
        guest_present=guest_present,
        current_intruder_count=current_intruder_count,
        notification_audience=["ADMIN", "FAMILY"],
    )
```

CSI changes this rule's severity from Medium to High.

### Correlation Rule 5: CSI-only evidence in Away

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
if away_mode and csi_detected:
    return CorrelationDecision(
        decision="ALERT",
        severity="MEDIUM",
        reason="Physical presence detected while Away mode is armed.",
        security_mode=security_mode,
        csi_presence_detected=True,
        nearby_device_count=context.nearby_device_count,
        approved_user_present=approved_present,
        admin_present=admin_present,
        family_present=family_present,
        guest_present=guest_present,
        current_intruder_count=0,
        notification_audience=["ADMIN", "FAMILY"],
    )
```

This is the confirmed behavior: Away means armed, so a CSI detection produces
an Alert. It does not increment the intruder count because CSI supplies physical
motion evidence rather than identity evidence.

### Correlation Rule 6: probe activity in Away

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
if away_mode and nearby_probe_activity:
    return CorrelationDecision(
        decision="ALERT",
        severity="MEDIUM",
        reason="Unknown wireless activity detected nearby.",
        security_mode=security_mode,
        csi_presence_detected=False,
        nearby_device_count=context.nearby_device_count,
        approved_user_present=approved_present,
        admin_present=admin_present,
        family_present=family_present,
        guest_present=guest_present,
        current_intruder_count=0,
        notification_audience=["ADMIN", "FAMILY"],
    )
```

### Correlation Rule 7: CSI in Home, no approved user

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
if csi_detected and not approved_present and not away_mode:
    return CorrelationDecision(
        decision="REVIEW",
        severity="LOW",
        reason="Physical presence detected while Home mode is active.",
        security_mode=security_mode,
        csi_presence_detected=csi_detected,
        nearby_device_count=context.nearby_device_count,
        approved_user_present=False,
        admin_present=admin_present,
        family_present=family_present,
        guest_present=guest_present,
        notification_audience=["ADMIN"],
    )
```

### Correlation Rule 8: CSI in Home with approved user

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
if csi_detected and approved_present and not away_mode:
    return CorrelationDecision(
        decision="SAFE",
        severity="LOW",
        reason="Authorized user is present in the monitored area.",
        security_mode=security_mode,
        csi_presence_detected=csi_detected,
        nearby_device_count=context.nearby_device_count,
        approved_user_present=True,
        admin_present=admin_present,
        family_present=family_present,
        guest_present=guest_present,
    )
```

### Correlation Rule 9: safe fallback

Source: `backend/signally/services/correlation_service.py`, method `evaluate()`.

```python
return CorrelationDecision(
    decision="SAFE",
    severity="LOW",
    reason="No unknown activity detected.",
    security_mode=security_mode,
    csi_presence_detected=False,
    nearby_device_count=context.nearby_device_count,
    approved_user_present=approved_present,
    admin_present=admin_present,
    family_present=family_present,
    guest_present=guest_present,
)
```

### Grace-period calculation

Source: `backend/signally/services/correlation_service.py`, method
`_is_admin_review_grace_active()`.

```python
pending_devices = context.connected_presence.pending_connected_devices
first_probe_seen_at = context.nearby_presence.first_probe_seen_at

if not pending_devices and first_probe_seen_at is None:
    return True

if pending_devices:
    first_seen = min(device.first_seen for device in pending_devices)
    if first_seen.tzinfo is None:
        first_seen = first_seen.replace(tzinfo=timezone.utc)
else:
    first_seen = first_probe_seen_at

if first_probe_seen_at is not None and first_probe_seen_at < first_seen:
    first_seen = first_probe_seen_at

return (utc_now() - first_seen).total_seconds() < ADMIN_REVIEW_GRACE_SECONDS
```

The timer starts at the earliest relevant pending-device/probe observation. It
is not a synchronization wait between CSI and ARP.

### Background cycle: the path that may save alerts

Source: `backend/signally/services/background_monitor.py`, methods `run_once()`
and `_run_loop()`.

```python
def run_once(self) -> None:
    session = self.session_factory()
    try:
        SystemStateService(
            session=session,
            csi_provider=self.csi_provider,
        ).collect_state(run_scan=True, persist_alerts=True)
    finally:
        session.close()

def _run_loop(self) -> None:
    while not self._stop_event.is_set():
        try:
            self.run_once()
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Background monitoring cycle failed: %s", exc)

        self._stop_event.wait(self.interval_seconds)
```

### Frontend state refresh: read-only correlation polling

Source: `SignallyApp/src/screens/HomeScreen.tsx`, `useQuery()` for
`system-state`.

```tsx
const { data: systemState } = useQuery({
  queryKey: ['system-state'],
  queryFn: api.getSystemState,
  // CSI is processed continuously on the Pi; refresh its correlated UI state
  // quickly without tying this cadence to the slower ARP scan interval.
  refetchInterval: 1_000,
  refetchIntervalInBackground: true,
  retry: false,
});
```

Source: `SignallyApp/src/api/client.ts`, API mapping.

```typescript
getSystemState: () => request<ApiSystemState>('/system/state'),
```

Source: `backend/signally/api/app.py`, function `get_system_state()`.

```python
@app.get("/system/state", response_model=SystemStateResponse)
def get_system_state():
    session = get_db_session()
    try:
        services = build_services(session)
        snapshot = services["system_state_service"].collect_state(
            run_scan=False,
            persist_alerts=False,
        )
        return to_system_state_response(snapshot)
    finally:
        session.close()
```

Together these excerpts prove that frontend polling reads the correlated state
once per second but does not itself run ARP or persist Alert events.
