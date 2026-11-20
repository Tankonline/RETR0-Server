# 01 · Project overview

## Why

Real Racing 3 (RR3) is a mobile racing game published by Electronic Arts. Its official online services were shut
down on **20 March 2026**. The Android client still starts, but:

- a **fresh install** cannot download its ~1.5 GB of game content (cars, tracks, UI), so it cannot be played;
- the game's **CloudCell** sync service is gone, so the game shows *OFFLINE*;
- features gated on being online stay locked: Grand Prix / Special Events, the store, gifts and more.

Project RETR0 set out to **preserve, understand and independently reconstruct** the client-side behaviour of the
game, and to build a replacement server that a single player can run on their own PC.

## Goals

1. Understand the Android client from evidence: Java code, native engine, data formats, network protocol.
2. Document it precisely, with evidence and confidence for every finding.
3. Independently implement replacement components, starting with the parts needed to play again.
4. Never depend on, contact or impersonate EA's original infrastructure.

## Ground rules

- The original APK and game data are **immutable evidence**. All work happens on copies.
- No EA code, assets or keys are redistributed. Server code is clean-room.
- Nothing contacts EA servers; everything listens on `127.0.0.1`.
- Findings carry confidence labels; nothing is presented as fact without evidence.
- Pseudocode from a decompiler is a research aid, never presented as original source.

See [13-legal-and-ethics.md](13-legal-and-ethics.md).

## What was achieved

| Area | Result |
|---|---|
| Decompilation | Java layer fully decompiled; native engine (`libRealRacing3.so`, arm64 and armv7) analysed in Ghidra, 98.8% of arm64 `.text` covered by recovered functions, 506 original source-file names recovered from embedded strings |
| Protocol | CloudCell sync framing, auth, 80+ sub-sync types catalogued; the asset download protocol fully decoded and verified byte-exactly |
| Server | DNS logger, CDN server built from the owner's data, CloudCell sync service; the game downloads all content and shows online |
| Client | A patched client that talks to the local server with no Frida, plus three preservation features: special events unlocked, store grants, a chosen player name |
| Saves | The local save container and body format decoded and validated read-only on real files |
| Physics | Fixed 16 ms simulation step, fixed-point integration, tyre models and kinematic suspension documented |

## The pieces

```
 Your Android emulator                         Your PC (127.0.0.1)
 ┌──────────────────────────┐                  ┌──────────────────────────────────────┐
 │ RR3 + RETR0 client patch │  adb reverse     │ cdn   :8780  asset packs + router     │
 │  HttpRequest.init ──────────────────────────► │       └─ CC_Sync.php ──► sync :8781   │
 │  (CloudCell/CDN → :8780) │  tcp:8780        │ dns   :53    logs lookups, answers no │
 └──────────────────────────┘                  └──────────────────────────────────────┘
```

Details: [07-server.md](07-server.md) and [10-retr0-client.md](10-retr0-client.md).
