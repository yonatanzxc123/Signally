# Signally CSI Layer — Architecture & File Map

How CSI presence detection flows through the codebase, and how each file hands off
to the next. Everything below is identical whether frames come from **real nexmon
hardware** or the **synthetic replay script** — they both emit the same
nexmon-format UDP datagrams to UDP port 5500, and the software can't tell them
apart (that's why the replay is a faithful test).

## 1. End-to-end data flow

```mermaid
flowchart TD
    subgraph sources["FRAME SOURCES (interchangeable)"]
        A1["Real: nexmon_csi firmware<br/>on wlan0 (Pi 5, BCM43455c0)"]
        A2["Fake: scripts/csi_replay.py --synthetic<br/>(no hardware needed)"]
    end

    A1 -->|UDP datagrams| PORT["UDP 0.0.0.0:5500"]
    A2 -->|UDP datagrams| PORT

    PORT --> LOOP["RealCsiDetectionProvider._capture_loop<br/>(background thread, csi_provider.py)"]

    LOOP -->|raw bytes| PARSE["parse_csi_frame()<br/>csi_frame.py"]
    PARSE -->|"CsiFrame(amplitudes[])"| DET["CsiMotionDetector.update()<br/>csi_detector.py"]

    subgraph detlogic["detector internals"]
        H["hampel_filter()<br/>drop outlier subcarriers"] --> N["normalize amplitudes"]
        N --> V["temporal variance<br/>over rolling window"]
        V --> B["compare vs adaptive<br/>empty-room baseline"]
    end

    DET --> detlogic
    detlogic -->|"PresenceReading(detected, confidence, metric)"| STORE["provider stores<br/>_detected / _strength / _confidence"]

    STORE --> AUTO["AutoFallbackCsiProvider<br/>real if receiving, else mock"]
    AUTO --> SS["SystemStateService.collect_state()<br/>system_state_service.py"]
    SS -->|csi_presence_detected| CORR["CorrelationService.evaluate()<br/>correlation_service.py"]
    CORR --> API["/system/state + /csi/status<br/>api/app.py"]
    API --> APP["React Native app<br/>(polls the endpoints)"]
```

## 2. What each file does & who it calls

```mermaid
flowchart LR
    replay["scripts/csi_replay.py<br/>--------<br/>build fake frames,<br/>send over UDP"]
    frame["sensors/csi_frame.py<br/>--------<br/>parse_csi_frame()<br/>build_csi_frame()<br/>PURE bytes<->CsiFrame"]
    detector["sensors/csi_detector.py<br/>--------<br/>CsiMotionDetector<br/>hampel_filter()<br/>PURE, stateful math"]
    provider["sensors/csi_provider.py<br/>--------<br/>socket + thread<br/>Real / Mock / AutoFallback"]
    config["config.py<br/>--------<br/>CSI_* tunables"]
    deps["api/dependencies.py<br/>--------<br/>csi_provider singleton"]
    state["services/system_state_service.py"]
    corr["services/correlation_service.py"]
    app["api/app.py<br/>/csi/status, /csi/set,<br/>/system/state"]

    replay -->|imports build_csi_frame| frame
    provider -->|imports parse_csi_frame| frame
    provider -->|imports CsiMotionDetector| detector
    provider -->|reads defaults| config
    detector -->|no deps| config
    deps -->|instantiates| provider
    state -->|reads is_presence_detected| deps
    corr -->|consumes csi flag| state
    app -->|exposes| deps
    app --> state
```

## 3. The three layers (why it's split this way)

The earlier version was one big threaded class that mixed sockets, byte-parsing,
and detection math — impossible to unit-test. It's now three pieces with clean
seams:

| File | Responsibility | Pure? | Tested by |
|---|---|---|---|
| `sensors/csi_frame.py` | nexmon bytes ⇄ `CsiFrame` (amplitudes) | ✅ no I/O | `tests/test_csi_frame.py` |
| `sensors/csi_detector.py` | Hampel → variance → presence + confidence | ✅ no I/O | `tests/test_csi_detector.py` |
| `sensors/csi_provider.py` | UDP socket + thread; glues the two together | ❌ has I/O | end-to-end replay |

Because the first two are pure functions/classes, they're testable with synthetic
data and never need a socket or hardware.

## 4. Real vs. mock — the fallback switch

`AutoFallbackCsiProvider` is what the rest of the app talks to. It decides per-call
whether to trust real CSI or fall back to the manual mock:

```mermaid
flowchart TD
    Q["is_presence_detected() called"] --> C{"real provider exists<br/>AND got a frame in<br/>last 3 seconds?"}
    C -->|yes| R["return REAL detector result"]
    C -->|no| M["return MOCK value<br/>(set via POST /csi/set)"]
```

- Real provider only exists when `SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true`.
- `/csi/status` returning `presence_strength: null` = no real frames arriving,
  so it's serving the mock. This is the safe default, never a crash.
- `POST /csi/set {"detected": true}` drives the **mock** — use it to test the
  HOME/AWAY correlation reaction without any CSI frames at all.

## 5. Testing paths

```mermaid
flowchart LR
    subgraph nohw["No hardware (what you just ran)"]
        r1["csi_replay.py --synthetic"] -->|UDP 5500| b1["backend<br/>CSI_REAL_PROVIDER_ENABLED=true"]
        b1 --> s1["GET /csi/status flips<br/>detected true/false"]
    end
    subgraph hw["Real hardware (later)"]
        r2["nexmon on wlan0"] -->|UDP 5500| b2["same backend, unchanged"]
        b2 --> s2["GET /csi/status tracks<br/>real motion in the room"]
    end
```

The move from "no hardware" to "real hardware" is literally just **swapping the
frame source** — no code changes. See `docs/nexmon_csi_setup.md` for the Pi-side
firmware steps that make box `r2` real.
```
