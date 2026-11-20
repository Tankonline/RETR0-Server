# Race System Analysis

Last updated: 2026-11-14 · Status: **game-mode class hierarchy and the race-frame structure recovered; rules, timing and AI not yet analysed.**
Addresses are ELF virtual addresses (arm64 unless stated).

## 1. Game modes: `GameMode` hierarchy (from recovered vtables, B-02)

`GameMode` has a 60-slot vtable (arm64 vtable `0x1e98158`). **32 classes** share at least 30% of its slots and are its subclasses (CONFIRMED by vtable sharing; names from RTTI):

`StandardRaceMode`, `StandardRaceMode_Base`, `TimeTrialMode`, `DragRaceMode`, `EnduranceMode`, `NASCARMode`, `EliminationMode`, `HunterMode`, `HeadToHeadMode`, `FuelMode`, `SpeedSnapMode`, `SpeedRecordMode`, `SpeedGateMode`, `AutocrossMode`, `ConeChallengeMode`, `BellRingMode`, `SplitScreenMode`, `P2PMultiplayerMode`, `P2PMultiplayerModeLAN`, `P2PMultiplayerModeRaceMetrics`, `PromotionalRaceMode`, `PromotionalAutocrossMode`, `PromotionalSpeedSnapMode`, `SoloMode`, `SandboxMode`, `TutorialMode`, `DemoMode`, `TrackPreviewMode`, `TrackPerformanceProfilingMode`, `AiPerformanceMeasuringMode`, `CarDebugViewerMode`, `CarRenderTool::CarRenderGameMode`.

Full per-class override lists are reproducible with `SCRIPTS/vtable_recovery.py`. The output is in `02_NATIVE_ENGINE/ANALYSIS/VTABLES/<abi>/`.

### `GameMode` vtable slots identified so far

| Slot | Role | Evidence | Confidence |
|---|---|---|---|
| 0, 1 | Destructors (Itanium D1/D0) | Overridden by every subclass; standard ABI layout | HIGH |
| 14 | Pure virtual in `GameMode`, overridden by 31/32 subclasses | `__cxa_pure_virtual` slot | CONFIRMED (abstract); role unknown |
| 38 | **`OnTrackLoaded`** | `StandardRaceMode` override `0x103c0cc` logs `"StandardRaceMode_Base::OnTrackLoaded [start]"` | CONFIRMED |
| 45 | **Per-frame mode update(dt)** | `StandardRaceMode` override `0x103c974(mode, dt)`: iterates racer objects (stride 0x1fb0) calling `0xf6a9f8(racer, dt)`, then runs a race state machine (states 1/2) with a race timer at `mode+0x178` and events `0x12ed244(mode, 4|5, …)` | HIGH |
| 49, 50 | Event handlers taking `(mode, int)` that forward to the player car's controller at `mode+0x250` | `0x103ccd8`, `0x103cdd0` | MEDIUM |
| 3 | `StandardRaceMode` override `0xff5fc4` returns `count(+0x178) - 1` | Pseudocode | MEDIUM (lap or checkpoint count accessor) |

## 2. Frame structure while racing

See `PHYSICS_ANALYSIS.md` §2. In summary: the play-state update scales dt, updates per-car audio and camera, runs the **fixed 16 ms simulation loop** (`0xb150d0`), then runs per-car timers, HUD and managers.

## 3. Global race-state fields (system object)

| Offset (arm64) | Meaning | Evidence | Confidence |
|---|---|---|---|
| `+0x1c0` | Scene id: 1 Game, 2 Splash, 3 Front end | `Enter Scene` strings | CONFIRMED |
| `+0x1b18` | Race sub-state (values 1, 3, 4, 5 observed; 5 disables some simulation steps) | Frame limiter and simulation conditions | MEDIUM |
| `+0x1b24` | Accumulated race time (ms, scaled) | `+= dt_s` per frame | HIGH |
| `+0x5508` | Car array (43 × 0xaa0) | Loops | CONFIRMED |
| `+0x54f0` | Player car index | Indexing | CONFIRMED |
| `+0x104f8` | Fixed-step accumulator | PH-01 | CONFIRMED |

armv7 uses different offsets for the same fields (for example the accumulator at `+0xe100` and car stride 0x928). Never reuse arm64 offsets on armv7.

## 4. Next steps

1. Identify slot 14 and the remaining lifecycle slots (begin/end race, results) from the decompiled overrides.
2. Racer object (0x1fb0) and `0xf6a9f8`: lap counting and timing.
3. The race state machine at `mode+0x2e`/`+0x178`: countdown, racing, finished.
