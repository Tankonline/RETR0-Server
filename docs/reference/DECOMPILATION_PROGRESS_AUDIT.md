# Project RETR0 — Decompilation and Reconstruction Progress Audit

Audit date: 2026-11-15. Repository state: `main` at `7f2fe64` (38 commits). Machine-readable tracker: `07_DOCUMENTATION/DECOMPILATION_PROGRESS.json`.

Every figure below was measured during this audit from the files named next to it, unless it is marked *(from earlier report, not re-measured)*. Where a number cannot be established it says **UNKNOWN**.

**Code categories.** The project's code falls into five kinds that are never interchangeable:

| # | Category | Exists in this project? |
|---|---|---|
| 1 | Original recovered code (EA's own source) | **No.** The APK contains compiled code only. None of EA's C++ or server code exists here or can be recovered from the client |
| 2 | Decompiled Java (JADX output) | Yes: 24,649 `.java` files, generated |
| 3 | Ghidra-generated pseudocode | Yes, for about 1,173 functions exported to files (plus any function on demand in the Ghidra projects) |
| 4 | Manually reconstructed C/C++ source | **None.** No `.cpp`/`.h`/CMake files exist outside third-party tools |
| 5 | Newly written replacement implementations | Yes, small: a Python CloudCell protocol codec and a Python save-file reader (1,257 lines incl. tests) |

---

## 1. Executive summary

**Short answer:** the project has a solid, well-documented *map* of the game, and an advanced, partly decoded understanding of its online protocol, save format and core physics constants. It has **almost no reconstructed game code**. Measured by "functions whose behaviour is documented", about **0.4 %** of the native engine is understood (328 of 90,504 arm64 functions cited with an interpretation). Measured by "game systems re-implemented as maintainable source", the figure is effectively **zero** outside the network codec and save reader.

What has been achieved:

- **Evidence and tooling are complete and reproducible.** Original APK hashed and read-only; JADX + APKTool outputs; two Ghidra databases with function coverage raised to **98.79 % (arm64)** and **90.68 % (armv7)** of `.text`; verified backups.
- **The game's structure is known.** The library embeds the names of **484 original source files** (arm64, measured here; an earlier count across ABIs gave 506). About **4,012 arm64 / 4,199 armv7 functions** are attributed to those files. **3,813 / 3,926 vtables** (3,136 / 3,208 classes) are recovered from RTTI, with 67,618 / 70,808 virtual-method slots.
- **JNI boundary is resolved.** 124 exports + 5 (arm64) / 7 (armv7) `RegisterNatives` bindings; the remaining unbound game natives are proven to have no implementation in this build.
- **Online protocol is largely decoded.** Wire format, envelope, **108 sub-sync types** with request layouts, and full field layouts for the main features (garage, leaderboards, cloud save, sales, multiplayer start, Race Teams core, server variables). A tested Python codec exists.
- **Save format is decoded.** Container and body encoding parse all 8 real saves byte-exactly.
- **Physics: core constants and structure.** Fixed 16 ms step, fixed-point integration, tyre models A/B constants, aero drag, kinematic suspension.

What is missing is the bulk of the work: turning ~90,000 native functions of a stripped C++ engine into named, typed, understood code, and then writing replacement source for rendering, physics, AI, UI, career, audio and assets. **The project is at the end of the "map the territory" stage and at the very start of "reconstruct the game".**

## 2. Overall reconstruction progress (measured)

| Measure | Value | Base | Evidence |
|---|---|---|---|
| `.text` covered by functions, arm64 | 98.79 % | 18.5 MB `.text` | `ENGINE_ARCHITECTURE.md` (function recovery), `FUNCTIONS/recovery/recovery_run.log` |
| `.text` covered by functions, armv7 | 90.68 % | 18,540,660 B | `FUNCTIONS/recovery_armv7/...` `RETR0_COVERAGE functions=79519 ... (90.68%)` |
| Functions known to exist | arm64 90,504; armv7 79,519 in `.text` (81,584 program-wide) | — | Recovery logs |
| Functions with a recovered original name | **0** (library is stripped; only 124 JNI exports + imports/thunks are named) | — | `MASTER_REVERSE_ENGINEERING_REPORT.md` K-01; function export: 3,262 non-`FUN_` names on arm64 are imports, thunks and exports |
| Functions attributed to an original `.cpp` file | arm64 4,012 (1,056 seeds + 2,956 bracketed); armv7 4,199 | 41,165 / 54,793 pre-recovery functions (9.7 % / 7.7 %); 4.4 % / 5.2 % of the recovered totals | `SOURCE_ATTRIBUTION/*_expanded.tsv` |
| Functions with Ghidra pseudocode exported to files | arm64 1,033; armv7 140 | 1.1 % / 0.2 % | 736 `.c` files under `02_NATIVE_ENGINE/ANALYSIS/` |
| Functions with a documented behavioural interpretation ("manually analysed") | **≈ 328** distinct code addresses cited in docs | 0.36 % of arm64 | Regex count of `` `0x…` `` code addresses in `07_DOCUMENTATION/*.md` (approximation: includes some call sites, excludes addresses cited without backticks) |
| Functions with reconstructed C/C++ | **0** | — | No C/C++ sources in the repo outside `TOOLS/` |
| Replacement implementations | 2 components (CloudCell codec; save reader) | — | `06_RECONSTRUCTION/BACKEND/cloudcell_codec/`, `SCRIPTS/save_decode.py` |
| Tests | 34 passing (codec) | — | `08_TESTING/test_cloudcell_codec.py`, run during this audit |

**Not computable honestly:** a single "% reconstructed" for the whole game. Any such number would be invented.

## 3. Java decompilation statistics

Measured over `01_ANDROID_ANALYSIS/JADX/rr3_14.0.1/sources` with a script written for this audit (method count is a declaration-regex approximation).

| Metric | Value |
|---|---|
| Classes processed by JADX (top-level) | 17,770 (`LOGS/jadx.log`) |
| DEX classes (incl. inner) | 42,335 across 6 DEX files *(from `DEX_CENSUS/dex_summary.md`)* |
| `.java` files written | 24,649 |
| Methods (declarations, approx.) | ≈ 166,700 |
| JADX run result | finished with errors, count 78; exit 1 |
| Methods JADX could not decompile | 140 "Code decompiled incorrectly" + 27 "Method dump skipped", in **147 files (0.6 %)** |
| JADX warning comments | 13,559 |
| Short/obfuscated-looking file names (`a/b.java` style) | 3,462 (almost all inside third-party SDKs) |
| Java `native` declarations | 474 in sources; 431 in the DEX census |

**Game-owned Java is small.** Almost everything is third-party SDK code (Google Play/Firebase 9,211 files, Facebook ads 2,380, Mintegral 1,821, Fyber 975, AppLovin 994, ironSource 467, Unity Ads 839, …).

| Game / EA package | Files | Methods | Decompile failures |
|---|---|---|---|
| `com/firemint/realracing` (the game's Java layer) | 45 | ≈ 594 | 0 |
| `com/ea/nimble` (EA platform SDK) | 140 | not counted | 0 |
| `com/glu/plugins` | 52 | not counted | not counted |
| `com/ea/*` total | 160 | — | — |

- **JNI relationships: mapped.** 124 export bindings, 5/7 `RegisterNatives` bindings, 6 registrar functions, no `JNI_OnLoad`. Of 15 (arm64) previously unbound game natives, 3 are runtime-registered and 12 have no native implementation and are unreachable (`JNI_MAPPING.md` §5, R-04). **Unresolved JNI methods affecting the game: 0.** The 287 "unbound 3p" natives belong to third-party SDKs whose libraries are not RR3's.
- **Genuinely understood:** the boot path, `MainActivity` / GL thread drivers, native library load order, CloudCell's Java HTTP transport (permissive TLS) and the Nimble purchase bridge. The rest is generated output only.
- **Clean source tree / independent compile:** **not attempted**. Game Java (45 files, 0 failures) is a realistic candidate to build against the Android SDK + Nimble stubs; the whole tree is not (147 files with failed methods, R8-obfuscated SDKs). No Gradle/Maven project exists for it.

## 4. Native decompilation statistics

| | arm64-v8a | armeabi-v7a |
|---|---|---|
| `libRealRacing3.so` exports / imports | 124 / 684 | 124 / 716 |
| RTTI types *(from `SYMBOLS/SUMMARY.tsv`)* | 5,061 | 5,130 |
| Vtables / classes / slots | 3,813 / 3,136 / 67,618 | 3,926 / 3,208 / 70,808 |
| Functions after Ghidra auto-analysis | 41,165 | 54,793 |
| Functions after recovery (working copy) | 90,504 | 79,519 (`.text`) |
| `.text` coverage | 98.79 % | 90.68 % |
| Original source files referenced | 484 (measured) | *(not re-measured; 506 across ABIs per earlier report)* |
| `.cpp` files attributed on both ABIs | 362 (20 arm64-only, 54 armv7-only) | — |
| Functions attributed to files | 4,012 | 4,199 |
| Pseudocode exported to files | 1,033 functions | 140 functions |
| Documented interpretations | ≈ 328 addresses (almost all arm64) | a handful (JNI, startup, timestep) |
| Recovered structures (field-level) | Partial: car struct stride 0xaa0 (43 cars), physics body/tyre fields, BinaryBlob, Sync/SubSync, team record, save container | — |
| Renamed functions in Ghidra | **0** by project policy (neutral `FUN_` names kept; meaning is in docs) | 0 |
| IDA databases | none (`02_NATIVE_ENGINE/IDA/` is empty) | none |

Other native libraries: `libfmodex.so` (FMOD Ex, third-party, 1,026 exports), `libfuelmetrics.so` (EA telemetry), `libNimble.so` (tiny loader). None is analysed beyond symbols; none is game logic.

**Unidentified functions:** about 86,500 arm64 functions (90,504 − ~4,012 attributed) have neither an original-file attribution nor a documented role. Their pseudocode can be produced on demand, but no one has read it.

## 5. ARM64 versus ARMv7 progress

- arm64 is the primary architecture: all networking, physics, save and Race Teams analysis was done there.
- armv7: Ghidra project, function recovery (90.68 %), vtables, source attribution, JNI map and the timestep constant are done. Remaining `.text` gap (1.73 MB) is classified: about 648 KB of prologue-less Thumb fragments (likely mis-split functions), 644 KB defined data, the rest literal pools/unknown.
- **Cross-architecture correlation** exists at the level of original `.cpp` files (362 shared files, `CROSS_ABI_FILE_MAP.tsv`), JNI exports and a few anchors. There is **no function-by-function arm64↔armv7 mapping** beyond that.
- For reconstruction, armv7 is useful mainly as a second witness (different inlining, different constants placement), not as separate work.

## 6. Game subsystem progress

Classification scale: Fully / Mostly / Partially reconstructed · Analysed but not reconstructed · Not yet investigated. "Reconstructed" means replacement source exists.

| Subsystem | Classification | Evidence |
|---|---|---|
| CloudCell sync protocol (envelope, sub-syncs) | **Partially reconstructed** | Codec + 34 tests; 108 sub-sync types catalogued; `NETWORKING_ANALYSIS.md` §8 (NW-01..79) |
| Garage / car customisation upload, leaderboards, sales, MP start, saved-game list, cloud save, server variables | **Partially reconstructed** (wire formats in codec) | `cloudcell_codec.py`, NW-27..71 |
| Race Teams (online) | **Partially reconstructed** | Header, team record, create/join/leave/request, status codes; list replies unnamed (NW-72..78) |
| Authentication | **Partially reconstructed** (updated 2026-11-15) | Request header, auth request and reply decoded (NW-80..83); local service issues member ids and tokens (`06_RECONSTRUCTION/BACKEND/local_service`); untested against the client |
| Online progression / multiplayer | Analysed but not reconstructed | MP start/status layouts; fmRUDP identified only by RTTI (24 types); no gameplay protocol decoded |
| Purchases (NimbleMTX) | Analysed but not reconstructed | Record/verify request fields (NW-70) |
| Save systems | **Partially reconstructed** | Byte-exact reader `SCRIPTS/save_decode.py` over 8 real saves; no writer; protected currency values deliberately not decoded (`SAVE_SYSTEM_ANALYSIS.md`) |
| Startup / main loop | Analysed but not reconstructed | Boot path, frame loop, scene state machine (K-07, `ENGINE_ARCHITECTURE.md` §5) |
| Vehicle physics (integration, timestep) | Analysed but not reconstructed | K-08, K-10, PH-01..42 |
| Tyres and grip | Analysed but not reconstructed | Tyre models A/B constants, surface μ table (K-11, K-12) |
| Suspension | Analysed but not reconstructed | Kinematic, no spring/damper (K-13) |
| Aerodynamics | Analysed but not reconstructed | Drag `0.602·0.26·v²`, downforce term (K-12, K-13) |
| Collision detection | Analysed but not reconstructed (partial) | Car-car AABB broadphase 1500 units; wall/ground contact callees located; narrowphase not documented |
| Drivetrain / engine power / gearbox | Analysed but not reconstructed (partial) | Drivetrain function `0x1588cf8` located; torque curves and gear logic not documented |
| Vehicle handling data / car data loading | Not yet investigated (entry points only) | C-01 NOT STARTED; `src\power\*` files identified |
| Damage | Not yet investigated | No findings |
| Race management / game modes | Analysed but not reconstructed (early) | 32 `GameMode` subclasses, two vtable slots, car array (K-09, `RACE_SYSTEM_ANALYSIS.md`, 3.6 KB doc) |
| AI drivers / opponent behaviour | Not yet investigated | `src\AI` 4 files named; 12 functions attributed; no analysis |
| Track systems | Not yet investigated | `src\Track` named only |
| Rendering / engine (mt3D, m3g, Skia) | Not yet investigated | 37 `mt3D` source files named; 123 functions attributed; no rendering analysis |
| Camera | Not yet investigated | — |
| Animation | Not yet investigated | — |
| Input and controls | Not yet investigated | Gyro/touch strings seen only |
| User interface / menus (`FrontEnd2`) | Not yet investigated (entry points only) | 156 source files, 505 RTTI classes, 259 attributed functions; screen classes used as caller evidence for networking |
| Career, events, rewards, currency | Not yet investigated | `Career`, `FeatSystem`, `JobSystem`, `Characters` identified; reward/currency only touched via save keys |
| Audio | Not yet investigated | `src\audio\*` and FMOD Ex identified |
| Asset management / formats | Container layer mapped (2026-11-18) | `ASSET_FORMAT_INVENTORY.md`: every depot file type classified (zlib `.z`, RC4 `.nct`/`.gui`/`.rr_ai`/..., JSR-184 `.m3g`, standard media); inner layouts known only for `.nct` suspension data; textures documented in the separate texture-converter project |

## 7. Recovered source code inventory

| Path | Category | Lines | Builds / tested |
|---|---|---|---|
| `06_RECONSTRUCTION/BACKEND/cloudcell_codec/cloudcell_codec.py` | 5 — replacement implementation (Python) | 550 | Yes, 34 tests pass |
| `06_RECONSTRUCTION/BACKEND/cloudcell_codec/subsync_table.py`, `subsync_features.py` | 5 — protocol data tables | 285 | Imported by tests |
| `SCRIPTS/save_decode.py`, `save_format_check.py` | 5 — clean-room save reader | 184 | Validated on 8 real saves; no unit tests |
| `08_TESTING/test_cloudcell_codec.py` | tests | 238 | 34 pass |
| `SCRIPTS/*.py`, `SCRIPTS/ghidra/*.java` (≈35 files) | analysis tooling, not game code | — | Used throughout |
| `02_NATIVE_ENGINE/ANALYSIS/**/*.c` (736 files) | 3 — Ghidra pseudocode | — | Not compilable by design |
| `01_ANDROID_ANALYSIS/JADX/` | 2 — decompiled Java | 24,649 files | Not built |
| C/C++ reconstructions | 4 | **0** | — |

## 8. Unresolved functions and systems

- Native: ≈ 86,500 arm64 functions with no attribution or documented role; 648 KB of armv7 fragments needing per-function repair.
- `UNRESOLVED_FUNCTIONS.md` and `OPEN_QUESTIONS.md` hold the specific open items (e.g. Q21 armv7 fragments; sales payload consumer; `sv.2.dat` layout; two unknown sync-reply values; Race Teams `rt_local`; contribution fields).
- Whole subsystems not yet opened: rendering, AI, UI, career/economy, audio, input, camera, animation, damage, tracks, asset formats.
- Server side: **does not exist in any artefact.** EA's server logic must be re-designed from client behaviour; it cannot be decompiled.

### 8b. Re-check 2026-11-15: what is still not decompiled or decoded

| Item | State | Needs |
|---|---|---|
| Game Java (`com/firemint`, `com/firemonkeys` 33 files, `com/ea`) | Decompiled, 0 failures | Nothing |
| JADX failures (147 files) | All in third-party SDKs except one Glu analytics file | Nothing for reconstruction |
| `libRealRacing3.so` | Imported, analysed, functions recovered (98.79 % / 90.68 %) | Understanding, not decompiling (pseudocode on demand) |
| `libfmodex.so` (FMOD Ex, third-party) | Analysed: 2,241 / 2,264 functions, 91.1 % / 84.7 % `.text` | Replace with a sound library; decompiling not needed |
| `libfuelmetrics.so` (EA telemetry) | Analysed: 6,463 / 6,515 functions, 85.6 % / 81.4 % | Not needed for gameplay |
| `libNimble.so` | Analysed (9 / 7 functions, a loader) | Nothing |
| 10 other libraries per ABI (AppLovin crash reporter, ARCore, `libc++_shared`, Crashlytics ×4, Glu ads, Tapjoy) | Not imported | Third-party; not needed |
| **Bundled game data `res/raw/res.zip`** (12.1 MB, 1,550 files) | **Not decoded** | `CC_SeedData.bin` (magic `NomNomNom`, CloudCell seed data), `economy.bin` and `ctd.dat` (apparently XOR-obfuscated), `materials.bin` (hashed names), `data.bin`; plus 1,236 depot asset lists, 103 GLSL shaders (readable source), 3 `.gui`, 42 `.feats`, 41 `.plist` |
| External game depot (`.depot/`, held outside the repo) | Not decoded in this repo | Car data, tracks, meshes: the asset-format track |

## 9. Buildability assessment

| Question | Answer |
|---|---|
| Source organised logically? | Analysis outputs: yes (per subsystem, per ABI). Reconstruction: one Python package; the `06_RECONSTRUCTION/APPLICATION` and `ASSETS` folders are empty |
| Understandable names? | In docs and codec: yes. In Ghidra: no (neutral `FUN_` names by policy; meanings live in docs with addresses) |
| Dependencies identified? | Yes at library level (OpenSSL 3.3.0, libcurl 8.7.1, zlib 1.2.5, Dear ImGui, Skia, JsonCpp, pugixml, FMOD Ex) |
| Function signatures / structures accurate? | Only for the few hundred functions analysed; not applied as types in Ghidra |
| Reconstructed code compiles? | The Python codec runs and is tested. No C/C++ exists to compile. Java not attempted |
| Systems executable independently? | Codec and save reader: yes. Nothing else |
| Can the native engine be replaced? | Not yet. Only physics constants and loop structure are known; rendering, asset loading, UI and AI are unanalysed |
| Future browser/desktop version? | Architecturally plausible (fixed-step deterministic-looking physics, data-driven content, protocol known), but nothing is built. It would need a new engine plus asset converters, not a recompiled original |
| Original APK runnable with a replacement server? | **Untested.** This is the cheapest route to a playable preservation build and has not been tried (needs approval: device/emulator, test saves) |

## 10. Major technical obstacles

| Obstacle | Solvable? | Notes |
|---|---|---|
| Stripped binary (no symbol names) | Partly | Source-file attribution + RTTI vtables give names for classes and files; function names must be assigned from behaviour, one by one |
| Scale (~90k functions) | Only by prioritisation | Reconstruct subsystems needed for a playable path, not the whole binary |
| Unknown memory layouts | Solvable incrementally | Requires per-class structure recovery (vtable constructors, field access patterns) and applying types in Ghidra |
| No runtime observation yet | Solvable with approval | Frida/gdb on an owned device or emulator would settle many static ambiguities (field meanings, units, unknown sync values) |
| armv7 fragments | Solvable | Jump-table recovery / non-returning flags per function; low priority |
| Missing server implementation | Not recoverable; re-implementable | Must be designed from client-side request/response handling (well under way) |
| Proprietary assets / formats | Solvable but separate track | Formats need decoders; assets themselves cannot be redistributed |
| Third-party engines (Skia, FMOD) | Replace, don't decompile | Use the public libraries or substitutes |
| Physics completeness | Needs new research + validation | Constants found; full algorithm needs end-to-end tracing and comparison against recorded runs |

## 11. Prioritised action plan

**Phase 1 — Complete the existing analysis (weeks).** Refresh the master report (its status table is stale). Finish Race Teams list replies, race-result upload and remaining sub-sync fields. Bring armv7 to parity only where it helps. Function-level arm64↔armv7 correlation for analysed functions.

**Phase 2 — Convert analysis into understandable source (ongoing).** Apply recovered structures as Ghidra types (on a backed-up copy); introduce a naming map (`docs name ↔ address`) that can be imported as Ghidra labels without mass-renaming policy violations; document algorithms per subsystem; start a C++ "reference reconstruction" for small, closed functions (physics step, tyre models) with tests derived from constants.

**Phase 3 — Reconstruct core systems (months+).** In order of leverage: save writer → car/vehicle data loader (C-01) → physics/tyres/suspension/drivetrain → race management/game modes → AI → UI flows → rendering/asset formats → audio.

**Phase 4 — Online replacement.** Local, independently operated CloudCell-compatible service built on the codec: bootstrap/auth replacement, server variables, saves, sales/catalogue, leaderboards (local), Race Teams (optional), multiplayer last.

**Phase 5 — Integration and validation.** First milestone: original APK + replacement service in an approved test environment. Then module-level comparison of reconstructed physics against instrumented runs. Then a standalone build.

## 12. Recommended next 20 tasks

| # | Task | Difficulty | Depends on |
|---|---|---|---|
| 1 | Refresh `MASTER_REVERSE_ENGINEERING_REPORT.md` status table from this audit | Low | — |
| 2 | Name Race Teams list replies (search, members, wall, rewards, sync) | Medium | — |
| 3 | Decode race-result upload record (10451, 17 × u32) | Medium | — |
| 4 | Decode RacerManager friends/opponents replies (10446, 10472) | Medium | — |
| 5 | Save writer (round-trip on test copies) | Medium | — |
| 6 | Unit tests for `save_decode.py` | Low | — |
| 7 | Minimal local CloudCell bootstrap service (auth, server variables, empty-safe replies) | Medium-High | 2–4 partly; codec |
| 8 | Approved runtime test plan: original APK against the local service on an owned device/emulator | Medium (needs approval) | 7 |
| 9 | C-01 vehicle data: car data file format and `CarPerformance` loader | High | — |
| 10 | Drivetrain: torque curve, gears, shifting | High | 9 |
| 11 | Collision narrowphase and wall response | High | — |
| 12 | Physics reference reconstruction in C++ (step, integration, tyre A/B) with constant-based tests | High | 9, 10 |
| 13 | GameMode lifecycle: map remaining vtable slots of the 32 modes | Medium | — |
| 14 | Career/events/rewards data model (`Career`, `FeatSystem`, `JobSystem`) | High | 5 |
| 15 | Apply recovered structs as Ghidra data types on a backed-up copy | Medium | — |
| 16 | Label import: docs-name → address map as Ghidra labels (non-destructive) | Low-Medium | 15 |
| 17 | AI driver analysis (`src\AI`) | High | 12, 13 |
| 18 | FrontEnd2 screen graph (navigation only) | Medium | — |
| 19 | Asset formats inventory in this repo (link to the external texture work; meshes/tracks next) | Medium | DONE 2026-11-18: `ASSET_FORMAT_INVENTORY.md` |
| 20 | Rendering pipeline survey (`mt3D`/`m3g`) | High | 19 |

## 13. Difficulty and dependencies

Difficulty and dependencies are given per task in §12 and in the JSON tracker. Critical paths:

- **Playable preservation build:** 7 → 8, with 2–5 strengthening it. This is the shortest path to a working game and needs no engine reconstruction.
- **Standalone reconstruction:** 9 → 10 → 12 → 13 → 17, in parallel with 19 → 20 and 18. This is a multi-month to multi-year effort.

## 14. How far are we, and what must be done

- **Understanding:** the online layer and save format are close to fully understood; physics is partly understood; everything else is mapped (file names, classes, entry points) but not understood.
- **Reconstruction:** two small replacement components exist; no game system has been rebuilt as source.
- **To get to a complete, maintainable codebase**, the realistic target is not "decompile everything" but "re-implement each system from documented behaviour", validated against the original. The remaining work is dominated by Phase 3 (core systems) and asset formats. The fastest tangible milestone is the original client running against an independently operated replacement service (tasks 5, 7, 8).
