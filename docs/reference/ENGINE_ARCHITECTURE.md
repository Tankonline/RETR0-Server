# Engine Architecture (seed)

Last updated: 2026-11-14 · Status: **seeded from static evidence only**. No call-graph or control-flow validation has been done yet (roadmap B-01 to B-05).

## 1. Evidence used

| Evidence | Nature | Location |
|---|---|---|
| Original source-file names (506 files, 81 directories) from assert/log strings | Literal strings in the binary: CONFIRMED that these files existed in the build | `02_NATIVE_ENGINE/SYMBOLS/<abi>/libRealRacing3/SOURCE/` |
| RTTI type names (about 5,100) | Literal typeinfo strings, demangled: CONFIRMED that the classes exist | `…/RTTI_GROUPS.md` |
| Library imports (`NEEDED`) and third-party version strings | CONFIRMED | P2 report |

Build root seen in every path: `E:\dev\builds\r3_update_a\source\` (1,506 occurrences on arm64).

## 2. Original source layout → subsystem (directory names are CONFIRMED; the role column is inference)

| `src\` directory | Files named | Matching RTTI groups | Inferred role | Confidence of role |
|---|---|---|---|---|
| `frontend2\` (incl. `power\`, `reward_cards\`, `DemoModes\`) | 156 | `FrontEnd2::` (505) | Menus and screens | HIGH |
| `Cloudcell\` (incl. `CloudcellApi\`) | 53 | `cc::` (125) | Online client: accounts, assets, cloud save, config | HIGH |
| `GameModes\` | 42 | `*Task`, `*Mode` classes | Race/game mode logic | MEDIUM |
| `mt3D\`, `mercury\` | 37 + 1 | `mtShader*`, `mtTextureManager` | Renderer (GL; `mercury\mercShader_GL.cpp`) | MEDIUM |
| `Character\` | 31 | `Characters::` (34) | Player profile, garage, currencies, tuning save data | HIGH |
| `third_party\` | 24 | Skia, Json, pugi | Bundled libraries | HIGH |
| `gui\` | 20 | `Gui*` | UI toolkit under the front end | MEDIUM |
| `power\` | 10 | `CarPerformance`, `MotorsportCrew` | Car performance model (`CarPerformance`, `Power2CarPerformance`, `LegacyCarPerformance`, `PerformanceRating`, `TuningData`) | MEDIUM |
| `Career\`, `Championships\`, `RookieChampionship\` | 9 + 3 + 1 | `CareerEvents::`, `RookieChampionship::` | Career structure | HIGH |
| `FeatSystem\`, `JobSystem\` | 9 + 5 | `FeatSystem::`, `JobSystem::` | Goals and objectives | HIGH |
| `ndPlatform\` (`ndAndroid\`) | 8 | `ndSingleton*` | Platform abstraction (Android) | HIGH (`GoogleNativeAd_Android.cpp` confirmed in JNI work) |
| `audio\` | 6 | `audio::` (9) | FMOD-based audio (`FMODSoundDevice`, `EngineRampB`, `RaceSoundsManager`, `SoundBufferLoader`) | HIGH |
| `AI\` (incl. `MachineLearning\`) | 4 | `CarAi*`, `MachineLearning::` | Opponent AI plus an ML agent/sensor interface | MEDIUM |
| `Save\` | 2 (+1 header) | `SaveSystem::` (5) | Local save (`SaveManager.cpp`, `FMUserData.cpp`, `SerialiserEnumHandler.h`) | HIGH |
| `Store\`, `MTX\` | 3 + 2 | `Store::` | Store and purchases | HIGH |
| `net\` | 1 | `fmRUDP::`, `NetEventListener_LAN_P2P` | P2P/LAN multiplayer (`P2PLanCommunicationInterface.cpp`) | MEDIUM |
| `Streaming\` | 1 | — | File streaming (`FileStreaming.cpp`) | MEDIUM |
| `Track\` (+ `src\TrackManager.cpp`, `TrackDesc.cpp`) | 1 + root | — | Track loading and ambience | MEDIUM |
| `src\` root files | 56 | — | Mixed; to be attributed | — |

The full per-file list, with assert line numbers and string offsets, is in `SOURCE/source_files.tsv`. Those string offsets are the anchors for roadmap task B-01.

## 3. Runtime layering (CONFIRMED edges only)

```
Android (Java)                         Native (libRealRacing3)
UnpackAssetsActivity ──► MainActivity ──JNI exports (124)──► ndPlatform / game core
    GLView (GLES 2.0) ── onViewCreatedJNI / onViewRenderJNI ──► renderer (mt3D / mercury)
    touch/key/lifecycle *JNI ─────────────────────────────────► input + app state
Glu SDK Java bridges ◄── RegisterNatives (6 registrars) ────── Glu C++ cores (gluads, glucentralservices, customer support, starlightsecurity)
                                    libfmodex.so ◄── audio\FMODSoundDevice
                                    libNimble.so / EA::Nimble C++ ◄── Cloudcell / identity
                                    libcurl + OpenSSL (static) ◄── HTTP
```

## 4. Function attribution (B-01, arm64)

1,144 functions are attributed to original source files through path-string xrefs (1,133 CONFIRMED single-file). The full map is in `02_NATIVE_ENGINE/ANALYSIS/SOURCE_ATTRIBUTION/arm64-v8a_FUNCTION_SOURCE_MAP.md`, and the per-function TSV is `arm64-v8a_function_map.tsv`. Largest groups: `frontend2` 259, `Character` 134, `mt3D` 123, `GameModes` 92, `Cloudcell` 88, `power` 44.

B-01 has since been extended and validated: **4,012 (arm64) / 4,199 (armv7)** functions are attributed, and compilation units are contiguous with the same link order on both ABIs. See `NATIVE_FUNCTION_CATALOGUE.md`.

## 5. Startup and frame loop (B-03 / B-04)

Evidence: JADX (Java side); Ghidra call trees and pseudocode in `02_NATIVE_ENGINE/ANALYSIS/STARTUP/<abi>/` (`CALLTREES.md`, `*_tree_annotated.tsv`, `*_decomp.c`). Addresses are ELF virtual addresses. "Attr." gives the B-01 source attribution.

### 5.1 Threads and Java drivers (CONFIRMED, JADX)

| Java call | Thread | Native entry |
|---|---|---|
| `MainActivity.onCreate` → `onCreateJNI()` (only if `checkStorage`) | UI thread | `Java_…_onCreateJNI` |
| `onStartJNI()` / `onStopJNI()` / `onDestroyJNI()` | UI thread | |
| `onResumeJNI()`, `onPauseJNI()` (via `PauseRunnable`), key events, message callbacks | **GL thread** (`GLSurfaceView.queueEvent`) | |
| `GLRenderer.onSurfaceCreated` → `onViewCreatedJNI()` | GL thread | |
| `GLRenderer.onSurfaceChanged` → `OnViewChanged(w, h, orientation, rotation)` | GL → UI | `onViewChangedJNI` |
| `GLRenderer.onDrawFrame` → `onViewRenderJNI(orientation, rotation)`, **skipped when `MainActivity.getGameState() == 5`** | GL thread, continuous render mode | `Java_…_onViewRenderJNI` |

`GLView` sets `setPreserveEGLContextOnPause(true)` and uses a custom `ConfigChooser` and `ContextFactory`.

### 5.2 Native startup (arm64)

| Step | Function (ELF) | Evidence | Confidence |
|---|---|---|---|
| `onCreateJNI` logs `"CREATE"` through `0x109fa18`, then, if the global activity pointer is null, `operator_new(0x540)` and constructs it | ctor `0x12ac2dc` | Pseudocode; the ctor references `getApiLevel`, `finishActivity`, `setSkipOnDestroyJNI`, `device UID: %s` | CONFIRMED (flow). Calling the 0x540 object "ndActivity" is HIGH: its frame method is in `ndActivity.cpp` (CONFIRMED) |
| `onStartJNI` / `onResumeJNI` log `"START"` / `"RESUME"` and call every listener in a list at activity `+0x38/+0x40` with event code **0** (start) or **1** (resume) | exports | Pseudocode (`listener->vtbl[0x30](listener, &code)`) | CONFIRMED |
| `onResumeJNI` also sets resume flags (`+0x4d2`, `+0x4dc = 1`) and may start music (`0x12ad2e0`: `startMusic`, `startMusic disabled during download`) | | Strings | CONFIRMED |
| `onViewCreatedJNI` → `0x12ad504`: `"VIEW CREATED"`, `"Invalidating GL objects..."`, `showSplash` | | Strings | CONFIRMED |
| First frames of Update run the **loading sequence**: `langs.utf8` text, shader feature files (`feats/…`, `*** Shader load total`), `materials/materials.bin`, `particles/particles.bin`, `LoadingScreen_Firemint.xml`, settings (`Settings.cpp`) | `0x1405868` and callees | Strings and call tree | CONFIRMED (presence); HIGH (order) |

### 5.3 Per-frame path (arm64; armv7 correlated)

```
GLRenderer.onDrawFrame (Java)
+- onViewRenderJNI                      arm64 0x12b3614: returns if activity == null
   +- ndActivity frame  [ndActivity.cpp, CONFIRMED]   arm64 0x12aea7c  (armv7: inlined into the JNI function)
      +- now = timer()   (virtual call, global system object vtbl+0x38, via 0x10b2f5c)
      +- dt_ms = now - last; if dt_ms < 0 then 16
      +- FrameState publish: width, height, dt_s = dt_ms/1000.0, input flags     arm64 0x12b4824 | armv7 0xb08fec
      +- if !swapFlag: Update(dt_ms) then Render()  else: Render() then Update(dt_ms)   (swapFlag = global PTR_DAT_02078e98)
      |    Update wrapper arm64 0x12b4448 | armv7 0xb08d1c: one-time Init 0x1404be8, then Update 0x1405868   [system_share.cpp, HIGH]
      |    Render wrapper arm64 0x12b43a0 | armv7 0xb08cb4: Render 0x1405fe4                                  [system_share.cpp, HIGH]
      +- end of frame: 0x12b4940
      +- splash hide after ~5 frames once ready (Java hideSplash / hideLoadingSplash)
      +- frame limiter: in some states (system +0x1c0 == 3, or == 1 with sub-state in {1,4,6}) usleep((41 - frame_ms) ms), ~24 fps cap (both ABIs)
      +- per-phase timings kept in a ring buffer in the activity (offsets 0x90..0x360, index +0x4a0)
```

**Update(system, dt_ms)** (`0x1405868`, `system_share.cpp`):
1. Accumulates time (`+0xf8 += dt`, `+0xfc = dt`).
2. `dt' = AutomationController.AdjustDt(dt)` (`0xf01708`; the current test's vtbl+0x18, or dt unchanged when no test is running), followed by an automation command-log hook (`/cmdLog.tsv`, `STARTING AUTOMATION RUN`).
3. `AutomationController.Update(dt')` (`0xf0174c`). **Correction (2026-11-14):** this object at `system+0x78` is the **AutomationController** (test automation; its factory `0xf00af0` logs `AutomationController::CreateTest: unknown test case specified` and builds test cases 0–5). It is *not* a scene manager. When the game's scene id changes it logs `Enter Scene Game/Front end/splash` and forwards to the running test (vtbl+0x20).
4. Runs the loading sequence until it is done (§5.2).
5. **Clamps dt to 100 ms** (`if (99 < dt) dt = 100`; present on both ABIs), then updates four sub-managers (`0x13c3cc0` × 4) and the game update `0x13b6d44(system, dt)`.

**Scene IDs** (global system object `+0x1c0`): **1 = Game**, **2 = Splash**, **3 = Front end** (CONFIRMED from the `Enter Scene …` strings). The vtable roles previously listed here (`+0x18` AdjustDt, `+0x20` Update, `+0x58` Exit) belong to **automation test objects**, not game scenes (corrected). The game-side race update is reached through the play state and `GameMode` (see `PHYSICS_ANALYSIS.md` §2 and `RACE_SYSTEM_ANALYSIS.md`).

**Render** (`0x1405fe4`, `system_share.cpp`) reaches the Dear ImGui debug UI (`ImGui Metrics`, `Close All Windows`), a draw-cache statistics overlay (`draw:%d hit:%d miss:%d evict:%d`) and a play-timing script (`scripts/play_timing.txt`).

### 5.4 Implications

- **Timestep:** the top-level loop is variable-timestep in integer milliseconds (clamped to 100 ms), **but the race simulation runs at a fixed 16 ms step with an accumulator** (CONFIRMED on both ABIs; `PHYSICS_ANALYSIS.md` PH-01).
- **Rendering** is single-threaded on the GL thread and coupled to Update in the same frame.
- **Reconstruction:** a replacement host needs a GLES2 surface, a ms clock, the Java lifecycle → JNI ordering in §5.1, and the scene state machine contract (§5.3).

## 6. Next steps

These are B-01 to B-05 in `RECONSTRUCTION_ROADMAP.md`. Every edge added here must cite a function address and its evidence.

## Function recovery (arm64, 2026-11-14)

Ghidra's auto-analysis had placed only **72.0 %** of `.text` in functions (39,984 in `.text`; 41,836 program-wide). 5.78 MB of disassembled code in 9,515 ranges belonged to no function and never appeared in pseudocode, call trees or xrefs.

With the owner's approval, `RETR0_RecoverFunctions.java` was run on a **working copy** (`02_NATIVE_ENGINE/GHIDRA/arm64-v8a_recovered`). The original project is unchanged, and a verified backup is in `BACKUPS/GHIDRA_arm64-v8a_before_function_recovery_20261114_174935`.

| Measure | Before | After |
|---|---|---|
| Functions (program) | 41,836 | **90,504** (+48,056) |
| `.text` in functions | 72.0 % | **98.79 %** (remainder is data or padding inside `.text`) |
| Code outside any function | 5.78 MB / 9,515 ranges | **0** |

How the 48,056 functions were found:
- 48,049 from code addresses referenced from data;
- 7 from gap starts;
- 0 from call targets, which Ghidra had already covered.

| Body size | Count |
|---|---|
| ≤ 8 B | 11,568 |
| 9–32 B | 12,693 |
| 33–256 B | 18,798 |
| > 256 B | 4,997 |

**19,236 (40.0 %) of the new entries are vtable slot targets** recovered from RTTI (`VTABLES/arm64-v8a/vtable_slots.tsv`), so they are confirmed virtual methods (HIGH). The others are referenced from other data (function-pointer tables, `std::function` vtables, callbacks): MEDIUM until checked. All keep default `FUN_` names; nothing was renamed.

**Use the recovered copy for future analysis.** Analyses run before this date used the original project and may have missed code in the former gaps.

## Function recovery (armv7, 2026-11-14)

Done on a **working copy** (`02_NATIVE_ENGINE/GHIDRA/armeabi-v7a_recovered`). The original project is unchanged, and a verified backup is in `BACKUPS/GHIDRA_armeabi-v7a_before_function_recovery_20261114_175442` (SHA-256 list beside it).

| Step | Script | Result |
|---|---|---|
| Baseline | `RETR0_Coverage.java` | 53,431 functions in `.text`, **79.8 %** coverage. 1.26 MB of disassembled code outside functions, plus ~2.5 MB of `.text` never disassembled |
| 1. Disassembled orphans | `RETR0_RecoverFunctions.java` (4 rounds) | +13,530 functions (1,156 from data pointers, 12,374 from gap starts) → 86.57 % |
| 2. Never-disassembled code | `RETR0_RecoverUndisassembled.java` (new, ARMv7 only) | 152,820 relocations scanned. Every in-place pointer into `.text` that hit undisassembled bytes was taken as an entry: **odd = Thumb** (entry = value−1), even = ARM. TMode was set, the code disassembled and the function created. +10,654 functions (run 1: 1,258, stopped on a context conflict; run 2 with conflict handling: 9,396). 918 pointers failed (disassembly or function creation did not succeed; not inspected) |
| 3. Follow-up rounds | `RETR0_RecoverFunctions.java` | +552, then +375 → **89.81 %**, with only 824 bytes of disassembled code outside functions |

**After steps 1–3:** 78,565 functions in `.text` (80,630 program-wide). Coverage **79.8 % → 89.81 %**. **After step 4 (below): 79,519 functions, 90.68 %.**

| New functions | Are RTTI vtable targets |
|---|---|
| From data pointers | 84.6 % |
| From gap starts | 68.8 % |
| From relocated pointers into never-disassembled code | 46.2 % (run 2), 39.6 % (run 1) |

That makes them HIGH for the vtable-confirmed ones and MEDIUM for the rest. All keep default `FUN_` names.

**Remainder investigated** (`RETR0_GapAnalysis.java`, read-only; `FUNCTIONS/recovery_armv7/gaps/`). The 1.89 MB outside functions after step 3:

| Category | Bytes | Share |
|---|---|---|
| Decodes as Thumb code (≥ 8 valid instructions) | 931 KB | 49.3 % |
| Data Ghidra already defined (inline constants) | 644 KB | 34.1 % |
| Unknown | 148 KB | 7.8 % |
| Decodes as ARM code | 82 KB | 4.3 % |
| Referenced from instructions (literal pools / tables) | 48 KB | 2.5 % |
| Padding (0x00 / 0xFF / Thumb NOP fill) | 35 KB | 1.8 % |

The largest Thumb runs start with standard prologues (`push {r4-r7,lr}; add r7,sp,#12; push.w …`) after `0xD4D4` trap-fill padding: real functions that nothing references by pointer.

Of the 918 failed relocated pointers, **910 do not decode as code in either mode** (pointers to data inside `.text`), 7 decode but did not become functions, and 1 decodes only in the other mode.

| Step | Script | Result |
|---|---|---|
| 4. Prologue recovery | `RETR0_RecoverPrologues.java` (new; working copy) | In each gap, skip padding and accept the first address only if it is a standard prologue: Thumb `PUSH {..,LR}` (0xB5xx), Thumb `PUSH.W {..,LR}`, or ARM `STMDB SP!,{..,LR}`. Repeated in rounds. **+811 functions** (808 Thumb, 3 ARM; 127 KB), then +143 from a follow-up `RETR0_RecoverFunctions` round → **90.68 %** (79,519 functions in `.text`; 81,584 program-wide) |

None of the 811 is a vtable target, as expected for unreferenced code, so they are MEDIUM (prologue evidence only). Cross-check: bytes read by instructions in the remaining gaps rose from 48 KB to 140 KB, because the new functions load literal pools that sit next to them.

**Final remainder (1.73 MB, `prologues/gaps_after/gap_summary.tsv`):**

| Category | Bytes | Share |
|---|---|---|
| Thumb-decodable runs without a prologue | 648 KB | 37.5 % |
| Defined data | 644 KB | 37.3 % |
| Unknown | 173 KB | 10.0 % |
| Literal pools / tables | 140 KB | 8.1 % |
| ARM-decodable | 87 KB | 5.0 % |
| Padding | 35 KB | 2.0 % |

The Thumb-decodable runs are small (10,176 runs, about 64 B average) and have no prologue, so they are most likely **fragments of existing functions** (unresolved switch cases, code after calls Ghidra treated as non-returning). They were deliberately **not** turned into separate functions, because that would invent false function boundaries. Resolving them needs per-function work: jump-table recovery, and fixing non-returning flags.

**Use the recovered copies for future analysis** on both architectures.

