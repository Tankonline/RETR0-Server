# Project RETR0 — Master Reverse-Engineering Report

Subject: Real Racing 3 Android client 14.0.1 (`com.ea.games.r3_row`, versionCode 14001). APK SHA-256 `dcfe3788…dcad1d5f`.
Last updated: 2026-11-14.

This file is the **index and current status**. Detailed evidence lives in the linked documents. The decompiler outputs referenced here are reconstructions, **not** EA's original source.

## 1. Document index

| Document | Scope | State |
|---|---|---|
| `07_DOCUMENTATION/00_INITIAL_ASSESSMENT.md` | Environment, tools, first inventory | complete |
| `01_ANDROID_ANALYSIS/P1_ANDROID_LAYER.md` | DEX census, manifest, boot path, signing (stands in for `ANDROID_APPLICATION_ANALYSIS.md` until that is written) | complete for P1 scope |
| `02_NATIVE_ENGINE/P2_NATIVE_ENGINE.md` | Library copies, symbol/RTTI harvest, statically linked third-party code, Ghidra setup and statistics | complete |
| `07_DOCUMENTATION/JNI_MAPPING.md` | Java ↔ native bindings, `RegisterNatives`, cross-ABI JNI correlation | complete for Phase A |
| `07_DOCUMENTATION/ENGINE_ARCHITECTURE.md` | Engine layout from original source-file names and RTTI | seeded |
| `07_DOCUMENTATION/UNRESOLVED_FUNCTIONS.md` | Open and resolved items | live |
| `07_DOCUMENTATION/RECONSTRUCTION_ROADMAP.md` | **Task tracker** and phase plan | live |
| `07_DOCUMENTATION/FINDINGS_LOG.md` / `OPEN_QUESTIONS.md` | Chronological findings and questions | live |
| `07_DOCUMENTATION/TOOLCHAIN_AND_REPRODUCIBILITY.md` | Exact commands, tool versions, gotchas | live |

| `07_DOCUMENTATION/NATIVE_FUNCTION_CATALOGUE.md` | Function → original source-file attribution, validation, subsystem anchors | complete for B-01 |

| `07_DOCUMENTATION/PHYSICS_ANALYSIS.md` | Timestep model, race-frame structure, physics data inputs | in progress |
| `07_DOCUMENTATION/RACE_SYSTEM_ANALYSIS.md` | GameMode hierarchy, race-state fields | in progress |

| `07_DOCUMENTATION/SAVE_SYSTEM_ANALYSIS.md` | Save location, files, container format, SaveManager, cloud-save components | in progress |

| `07_DOCUMENTATION/NETWORKING_ANALYSIS.md` | Network stacks, TLS behaviour, environments, endpoint inventory, offline evidence, replacement principles | first pass |

Not yet created, because no evidence-backed content exists yet (they will be created when their Phase C task starts): `VEHICLE_SYSTEM_ANALYSIS.md`, `FRONTEND_ANALYSIS.md`, `SAVE_SYSTEM_ANALYSIS.md`, `NETWORKING_ANALYSIS.md`, `AUDIO_SYSTEM_ANALYSIS.md`, `ANDROID_APPLICATION_ANALYSIS.md`.

## 2. Status summary

| Area | Status | Headline |
|---|---|---|
| Evidence integrity | DONE | Original APK read-only; all 28 libraries and 6 DEX files hashed |
| Android layer | DONE (P1 scope) | 42,335 classes, about 950 of them game/EA/Glu. Launcher unpacks the bundled `res.zip`, then starts `MainActivity`, which loads Nimble → fmodex → RealRacing3 |
| Native symbol recovery | DONE | About 5,100 RTTI types; **506 original source-file names** from assert strings; third-party versions identified |
| Ghidra databases | DONE (both ABIs) | arm64 41,165 functions; armv7 54,793 |
| JNI | DONE | 124 export bindings; 6 `RegisterNatives` registrars (Glu SDKs plus a game ad bridge); no `JNI_OnLoad`; 12 legacy natives have no implementation and are unreachable |
| Startup and frame loop | DONE (first pass) | Java GL thread → `ndActivity` frame → Update(dt ms, clamp 100) / Render (`system_share.cpp`) → scene state machine. See `ENGINE_ARCHITECTURE.md` §5 |
| Engine architecture | IN PROGRESS | 4,012 arm64 / 4,199 armv7 functions attributed to original `.cpp` files (B-01, validated). See `NATIVE_FUNCTION_CATALOGUE.md`. See `ENGINE_ARCHITECTURE.md` |
| Physics / race | IN PROGRESS | Fixed 16 ms step; per-car step located; GameMode hierarchy recovered |
| Vehicle, UI, save, audio, network | NOT STARTED (entry points identified) | See roadmap Phase C |
| Reconstruction | STARTED | First clean-room component: CloudCell BinaryBlob codec (`06_RECONSTRUCTION/BACKEND/cloudcell_codec`), tests in `08_TESTING` |

## 3. Key confirmed findings

| ID | Finding | Confidence | Ref |
|---|---|---|---|
| K-01 | libRealRacing3 is stripped. Only 124 `Java_*` exports exist; internal function names are unrecoverable from symbols | CONFIRMED | P2 §2 |
| K-02 | The binary embeds **1,506 assert/log strings with original source paths** (`E:\dev\builds\r3_update_a\source\src\…\File.cpp:line`), naming 506 files in 81 directories | CONFIRMED | `SYMBOLS/*/libRealRacing3/SOURCE/` |
| K-03 | Statically linked: OpenSSL 3.3.0, libcurl 8.7.1, zlib 1.2.5, Dear ImGui 1.80 WIP, Skia, JsonCpp, pugixml. FMOD Ex is dynamic (`libfmodex.so`) | CONFIRMED (version strings, RTTI, `NEEDED`) | P2 §3 |
| K-04 | No `JNI_OnLoad`. Glu SDK components and the Google native-ad bridge register their natives during subsystem initialisation | CONFIRMED | JNI_MAPPING §2–3 |
| K-05 | `network_security_config` allows cleartext only to `127.0.0.1` | CONFIRMED | P1 §3 |
| K-07 | The top-level loop is variable-timestep in integer ms, clamped to 100 ms. Scenes: 1 Game, 2 Splash, 3 Front end. A ~41 ms frame cap applies in some states | CONFIRMED (both ABIs) | ENGINE_ARCHITECTURE §5.3 |
| K-08 | The race simulation uses a **fixed 16 ms step (62.5 Hz) with an accumulator**; the 16 is a `.rodata` constant on both ABIs. There are up to 43 cars (arm64 struct 0xaa0 bytes) | CONFIRMED | PHYSICS_ANALYSIS PH-01 |
| K-10 | Physics world step `0xb15684` (arm64): phases per car, car-car AABB broadphase (1500 units), and **exact fixed-point position integration** `pos += (vel*dt_ms) >> 10` with remainder carry | CONFIRMED | PHYSICS_ANALYSIS §2a |
| K-11 | Physics encodings: angular velocity in 2^-24 rev/ms, orientation in 24-bit binary angles, velocity ×256; mass stored in **pounds** in car data (×0.453592). Tyre model A: slip-angle curve `1500·α + 200·max(α−6, 0)`, quarter-weight friction limit, surface μ from material flags (1.0/0.8/0.7/0.65/0.6/0.5) | CONFIRMED | PHYSICS_ANALYSIS §2b |
| K-12 | Default tyre model B adds longitudinal drive/brake and aero drag `0.602·0.26·v²` (½·ρ_air·Cd with ρ = 1.204 kg/m³), suggesting SI units. Suspension travel limit is 1.1 × suspension-data travel; post-contact caps are 140 (speed) and 4 rad/s; no explicit spring formula found yet | CONFIRMED (constants) | PHYSICS_ANALYSIS PH-27..36 |
| K-13 | **The suspension and vertical motion are kinematic** (no spring/damper): gravity plus aero downforce `v²·k·7/m`, ground clamp with 4 wheels, geometric per-wheel displacement from travel and ride height. Velocity is in m/s (20 km/h threshold constant) | CONFIRMED/HIGH | PHYSICS_ANALYSIS PH-36..42 |
| K-14 | **Local saves:** `files/doc/<name>.2.dat` (e.g. `character`, `player_profile`), backups in `files/.depot/*.bak`; container = XOR with a 64-byte constant key, big-endian header (magic 0xABCFFCBA, version 5, size), 1-byte XOR checksum. Validated on 9 real files | CONFIRMED | SAVE_SYSTEM_ANALYSIS |
| K-15 | Save body = interned key dictionary (C++ member-path names, `IDX:[id]` arrays) + typed value tables (bool/int/float/string/varint/blob). The clean-room decoder parses all 8 saves byte-exactly; currency values are tamper-protected (`[EHV]`/`[H]`) | CONFIRMED | SAVE_SYSTEM_ANALYSIS §2b |
| K-16 | Networking: CloudCell HTTP goes native → Java `HttpURLConnection` with a process-wide permissive TLS trust manager (no CA validation, no pinning, any hostname). Native libcurl/OpenSSL serve Nimble/Glu; fmRUDP serves multiplayer. Explicit offline states and offline UI exist; runtime offline behaviour is untested | CONFIRMED (static) | NETWORKING_ANALYSIS |
| K-17 | CloudCell sync = `POST CC_Sync.php` with a batched binary BinaryBlob body: little-endian, `Box(Box(body, zlib-9), rolling-XOR)` with a custom checksum; auth packet layout and state enum recovered. A clean-room codec with passing tests exists (wire compatibility unverified) | CONFIRMED (static) | NETWORKING_ANALYSIS §8 |
| K-18 | Sync batches carry sub-sync records `{u32 type, u32 param, u32 0, u32 len, payload}`; responses carry `u32 len + bytes` per sub-sync in order. 22 request classes recovered; type ids 10448–10788 for 20 of them (e.g. PvP servers = 10768, garage = 10607, leaderboards 10477–10788) | CONFIRMED/HIGH | NETWORKING_ANALYSIS §8.6–8.8 |
| K-09 | 32 `GameMode` subclasses (race modes) recovered from vtables | CONFIRMED | RACE_SYSTEM_ANALYSIS §1 |
| K-06 | The launcher does not download anything. Main game data lives in `<extFilesDir>/.depot/` | CONFIRMED | P1 §4 |

## 4. Highest-priority next work

See `RECONSTRUCTION_ROADMAP.md` → "Highest-priority next tasks". In short:

1. **B-01**: attribute functions to original source files through xrefs to the source-path strings.
2. **B-03 / B-04**: native startup and the per-frame loop from the `MainActivity` JNI entry points.
3. **C-01 / C-06**: vehicle performance (`src\power\*`) and saves (`src\Save\*`, `GameSaveManager`).
