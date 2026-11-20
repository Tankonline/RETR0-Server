# Reconstruction Roadmap and Task Tracker

Statuses: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `NEEDS REVIEW` · `DONE`.
A task is DONE only when its output has been checked and documented.
Last updated: 2026-11-14.

## Completed foundation (P0–P2)

| ID | Task | Status | Evidence |
|---|---|---|---|
| F-01 | Original APK integrity, read-only, checksums | DONE | `00_ORIGINAL/METADATA/CHECKSUMS.sha256` |
| F-02 | APKTool and JADX decompilation | DONE (JADX: 78 method-level errors) | `01_ANDROID_ANALYSIS/P1_ANDROID_LAYER.md` |
| F-03 | DEX census, manifest components, boot path | DONE | P1 report §2–4 |
| F-04 | Native library working copies (4 libraries × 2 ABIs) | DONE | `02_NATIVE_ENGINE/LIBRARIES/LIBRARIES.sha256` |
| F-05 | Symbol, string, RTTI and URL harvest | DONE | `02_NATIVE_ENGINE/SYMBOLS/` |
| F-06 | Original source-file layout (506 file names) | DONE | `SYMBOLS/*/libRealRacing3/SOURCE/SOURCE_TREE.md` |
| F-07 | Ghidra import and auto-analysis, arm64 | DONE (41,165 functions) | P2 report §6.1 |
| F-08 | Ghidra import and auto-analysis, armv7 | DONE (exit 0; statistics in `JNI_MAPPING.md` §6) | `GHIDRA/LOGS/armeabi-v7a_console.log` |

## Phase A — Finish initial analysis

| ID | Task | Status | Notes |
|---|---|---|---|
| A-01 | Verify both Ghidra projects | DONE | see F-07 and F-08 |
| A-02 | Locate `RegisterNatives` call sites (arm64) | DONE | 6 true registrars; see `JNI_MAPPING.md` |
| A-03 | Locate `RegisterNatives` call sites (armv7) | DONE | 6 true registrars, matching arm64; see `JNI_MAPPING.md` §6 |
| A-04 | Resolve the ~15 unbound game callbacks | DONE (arm64) | 3 resolved as runtime registration; 12 confirmed to have no native implementation in this build |
| A-05 | `JNI_OnLoad` investigation | DONE | No `JNI_OnLoad` in libRealRacing3. Registration is done by subsystem init functions running after load (see JNI_MAPPING) |
| A-06 | Cross-architecture function correlation (JNI exports + registrars) | DONE (JNI scope); IN PROGRESS for the wider engine | `JNI_MAPPING.md` §6 |

## Phase B — Engine architecture

| ID | Task | Status | Approach |
|---|---|---|---|
| B-01 | Map source files → functions | DONE | Seeds: arm64 1,144 / armv7 1,399 functions from path-string xrefs. B-01b bracket expansion validated (leave-one-out 100% / 99.8%, header seeds excluded): **4,012 / 4,199 functions attributed**. Files are in the same link order on both ABIs (98.9%). See `NATIVE_FUNCTION_CATALOGUE.md` |
| B-01c | Extend attribution: gaps between files (shared link order), third-party code identification | NOT STARTED | Optional; lower confidence than B-01b |
| B-02 | Map RTTI → vtables → virtual methods | DONE (first pass) | `SCRIPTS/vtable_recovery.py`: arm64 3,813 vtables / 3,136 classes / 67,618 slots; armv7 3,926 / 3,208 / 70,808. Validated: 90.4% / 99.3% of attributed slots point into the class's own `.cpp` |
| B-03 | Trace native startup from `MainActivity.onCreateJNI` / `onViewCreatedJNI` / `onViewRenderJNI` | DONE (first pass) | `ENGINE_ARCHITECTURE.md` §5.1–5.2. Open: the 0x540 activity constructor internals and the one-time Init `0x1404be8` contents |
| B-04 | Identify the main game loop (per-frame path from `onViewRenderJNI`) | DONE (first pass) | `ENGINE_ARCHITECTURE.md` §5.3: ndActivity frame → Update(dt ms, clamped 100) / Render in `system_share.cpp` → SceneManager (1 Game / 2 Splash / 3 Front end). Correlated on armv7. Open: the Game scene's update (vtbl+0x20) down to the race and physics step |
| B-05 | Subsystem dependency graph | NOT STARTED | Call graph between file-attributed function clusters |
| B-06 | `ENGINE_ARCHITECTURE.md` and `NATIVE_FUNCTION_CATALOGUE.md` | IN PROGRESS (catalogue holds the B-01 attribution) | |

## Phase C — Game functionality (priority order)

| ID | Subsystem | Status | Entry points already known |
|---|---|---|---|
| C-01 | Vehicle systems | NOT STARTED | `src\power\CarPerformance.cpp`, `Power2CarPerformance.cpp`, `LegacyCarPerformance.cpp`, `TuningData.cpp`; RTTI `CarEntity`, `CarPerformance`, `Characters::Car`, `CarUpgrade*` |
| C-02 | Physics and simulation | IN PROGRESS | **Fixed 16 ms step with accumulator** found (both ABIs); **physics world step `0xb15684`** located with phases, fixed-point integration (`>>10`) and car-car broadphase (arm64); `0x133b0a4` turned out to be the per-car camera; rigid-body solver, tyre model A (slip-angle curve, surface μ table) and drivetrain constants documented; `.nct` physics data loaders identified. See `PHYSICS_ANALYSIS.md`. Next: decompile the per-car step |
| C-03 | Front-end and UI | NOT STARTED | `src\frontend2\*` (156 files), RTTI `FrontEnd2::` (505) |
| C-04 | Race management | IN PROGRESS | 32 `GameMode` subclasses recovered; slot 38 = OnTrackLoaded, slot 45 = per-frame update; car array 43 × 0xaa0. See `RACE_SYSTEM_ANALYSIS.md`. Entry points: `srcGameModes*` (42 files), `RacerManager.cpp`, `TrackManager.cpp` |
| C-05 | Career progression | NOT STARTED | `src\Career\*`, `CareerEvents::`, `FeatSystem`, `JobSystem` |
| C-06 | Save systems | IN PROGRESS | Location, container and **full body encoding** CONFIRMED (byte-exact parse of all 8 saves); key schema mapped; `[EHV]` protected values intentionally not decoded. Next: id-reference rules, link to game data. See `SAVE_SYSTEM_ANALYSIS.md` |
| C-07 | Audio | NOT STARTED | `src\audio\*` (FMODSoundDevice, EngineRampB, RaceSoundsManager, SoundBufferLoader) |
| C-08 | Networking | IN PROGRESS | First pass: 5 network stacks; CloudCell runs over Java HttpURLConnection with a permissive trust manager (no CA check, no pinning, all hostnames); environments and a persistent sync-server switch; host/endpoint inventory; offline paths. See `NETWORKING_ANALYSIS.md`. **Sync framing and batching decoded** (POST CC_Sync.php, BinaryBlob, zlib + rolling XOR, custom checksum, v34 header, sub-sync records and response parts, auth packet) and a **sub-sync type table for 20 classes**; payloads decoded for player rank, garage (car blob = `.cc_cust` save-format file), vehicle upload, customisation info, PvP server list, all six leaderboard types, sales, online multiplayer saved-game download (QA tool) and the player cloud save (GameSaveManager: sub-syncs 47/48/10660/10555 + HTTP PUT/GET). SyncUserPN, DataRequestSubSync and the full reply body (status, parts, trailing id list). All 21 Sync classes decoded at framing level. **Audit: 80 more directly queued sub-syncs catalogued (request layouts; 57 with reply read orders); Ghidra covers only 72 % of .text with functions.** Undefined functions recovered on backed-up copies (arm64 coverage 98.79 %, armv7 90.68 %; armv7 remainder classified); both layout methods agree on all 63 comparable sub-syncs. Next: focused passes on the direct sub-syncs needed by a test server (config, auth, gifts, store) |

## Phase D — Reconstruction (blocked until the relevant Phase C item is NEEDS REVIEW or later)

| ID | Component | Status |
|---|---|---|
| D-01 | Save-file reader/writer (clean-room, from `SAVE_SYSTEM_ANALYSIS.md`) | IN PROGRESS (structural reader `SCRIPTS/save_decode.py` parses every save byte-exactly; a writer must reproduce key interning, the checksum and the XOR stream, and must target copies only) |
| D-02 | Vehicle data model and loader | BLOCKED on C-01 |
| D-03 | Offline replacement for CloudCell bootstrap and config (local, independently operated) | IN PROGRESS: local service first slice (auth, sync dispatch, cloud-save store; `06_RECONSTRUCTION/BACKEND/local_service`, NW-80..84). Earlier: clean-room codec `06_RECONSTRUCTION/BACKEND/cloudcell_codec` (tests 29/29). Endpoint logic blocked on sub-request formats |

## Phase E — Validation

| ID | Task | Status |
|---|---|---|
| E-01 | Test harness under `08_TESTING/` for reconstructed components | IN PROGRESS (pytest; `test_cloudcell_codec.py` 29/29) |

## Highest-priority next tasks

1. **C-02: value of g, armv7 correlation, position-unit check (PH-42).** The vertical model is kinematic (PH-36..41). Solver, tyre models A and B (B is the default, with drag ½ρCd), contact, walls and limits are documented (PHYSICS_ANALYSIS §2b).
2. **C-01 / C-06: vehicle performance and save code.** Their source files are already identified, and both feed the first reconstruction targets.
3. **B-02: RTTI → vtable → class methods.** Complements B-01 for files without asserts.
