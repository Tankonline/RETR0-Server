# Project RETR0 — Initial Assessment

Date: 2026-11-14 · Scope: read-only inspection. Nothing in `00_ORIGINAL` was modified.

Each finding is tagged **[C]** (confirmed, from the tool output named) or **[H]** (hypothesis, still to verify).

---

## 1. Project tree

| Path | Contents | Status |
|---|---|---|
| `00_ORIGINAL/APK/real-racing-3-14-0-1.apk` | 105,189,283 bytes | present |
| `00_ORIGINAL/METADATA/RR3_APK_Inventory.txt` | Earlier zip inventory with SHA-256 | present |
| `00_ORIGINAL/GAME_DATA`, `OBB` | — | **empty** (assets are kept outside this project) |
| `01_ANDROID_ANALYSIS/{APKTOOL,JADX,MANIFEST}` | — | **empty** |
| `02_NATIVE_ENGINE/{GHIDRA,IDA,LIBRARIES,SYMBOLS}` | — | **empty** |
| `03_…` – `06_…`, `08_TESTING`, `AI_AGENTS`, `GITHUB`, `SCRIPTS` | Folder skeleton only | **empty** |
| `07_DOCUMENTATION/` | Two environment diagnostics and `python-requirements.txt` (UTF-16 encoded) | present |
| `BACKUPS/User_PATH_Backup_20261114_003110.txt` | Backup of the user PATH | present |
| `Project_RETR0_Diagnostic.py` | Environment diagnostic script | present |
| `.venv/` | Python 3.14.2 venv with capstone 5.0.9, lief 1.0.0, construct 2.10.70 and Jupyter | working |
| `TOOLS/` (2.4 GB) | APKTool, JADX, Ghidra, Blender, Noesis, plus the original download zips | see §2 |

There is no git repository at the project root.

## 2. Tools

| Tool | Location | Check | Result |
|---|---|---|---|
| APKTool 3.0.3 | `TOOLS/APKtool/apktool_3.0.3.jar` | `--version` → `3.0.3` | **[C] works** (default Java 11) |
| JADX 1.5.6 | `TOOLS/JADX/bin/jadx` | `--version` → `1.5.6` | **[C] works** |
| Ghidra 12.2 | `TOOLS/GHIDRA/ghidra_12.2_PUBLIC` | `application.properties`: `java.min=25` | **[C] installed; needs JDK 25.** JDK 25 is at `C:\Program Files\Eclipse Adoptium\jdk-25.0.5.8-hotspot`, but the default `java` is 11 and `JAVA_HOME` is unset |
| Blender 5.2.4 | `TOOLS/BLENDER/5.2.4/…/blender.exe` | zip SHA-256 matches the official `.sha256` | **[C] present** (portable). A registered Blender 5.1.2 install also exists |
| Noesis 4.474 | `TOOLS/NOESIS/Noesis64.exe` | ReadMe version | **[C] present** |
| Python 3.14.2 | `.venv` | `pyvenv.cfg` | **[C] works** |
| Android SDK | `%LOCALAPPDATA%\Android\Sdk` | build-tools 36.0.0 (`aapt2`), NDK 26/27/28 | **[C] present.** NDK `llvm-readelf`/`llvm-objdump` can disassemble ARM |
| adb / fastboot | WinGet platform-tools 36.0.2 | — | **[C] works** |
| git 2.56.1, ffmpeg 7.1.1, node 26 | PATH | — | **[C] works** |
| JDKs | `jdk-11` (default), `jdk-21.0.10`, `jdk-25.0.5.8`, JRE 8, Android Studio JBR | — | **[C] present** |
| IDA | — | — | not installed; `02_NATIVE_ENGINE/IDA` is unused |

None of the tools are on PATH; all are called by full path.

## 3. Decompilation status

**Update 2026-11-14:** P0 and P1 are complete. See `01_ANDROID_ANALYSIS/P1_ANDROID_LAYER.md`. Original state at assessment time: decompilation had not started.

## 4. Original APK

| Field | Value |
|---|---|
| SHA-256 | `dcfe3788004444bd69e2fb839c18a973b488e94f46f1b818b6c005afdcad1d5f` — **[C] matches** `RR3_APK_Inventory.txt` |
| Package | `com.ea.games.r3_row` (aapt2) |
| Version | `14.0.1` / versionCode `14001`, targetSdk 36 |
| Launcher activity | `com.firemint.realracing.UnpackAssetsActivity` |
| ABIs | `arm64-v8a`, `armeabi-v7a` |
| Signature | v1 JAR signature `META-INF/EAMKEYST.{SF,DSA}` (v2/v3 blocks not checked yet) |
| DEX | `classes.dex` … `classes5.dex` (DEX v038; 8.56, 8.40, 8.19, 9.13, 1.82 MB) and `assets/audience_network.dex` (DEX v035, 3.80 MB, Facebook Audience Network) |
| File attributes | Was not read-only at first; **set to ReadOnly in P0** (2026-11-14) |

Note: `info.txt` at the APK root belongs to the Singular SDK (`Singular-v9.4.1`). It is not the game's build info.

**Permissions [C]:** INTERNET, ACCESS_NETWORK_STATE/WIFI_STATE, CAMERA (ARCore), POST_NOTIFICATIONS, BILLING, AD_ID and AdServices attribution/topics, FOREGROUND_SERVICE, RECEIVE_BOOT_COMPLETED, SCHEDULE_EXACT_ALARM, USE_BIOMETRIC/FINGERPRINT, USE_CREDENTIALS, C2DM RECEIVE, install referrer, legacy external storage (maxSdk 23).

## 5. Native libraries

Every library is stored uncompressed in the APK. There are 14 libraries per ABI.

| Library | arm64-v8a | armeabi-v7a | Notes |
|---|---|---|---|
| **libRealRacing3.so** | 33.1 MB | 23.7 MB | Main engine. See below |
| libNimble.so | 5.8 KB | 4.1 KB | Tiny JNI shim (`JNI_OnLoad` + 2 C++ exports). [H] The EA Nimble logic lives in Java |
| libfmodex.so | 1.27 MB | 1.06 MB | FMOD Ex. 1026/934 exports with symbol names, so it is well documented |
| libfuelmetrics.so | 4.24 MB | 3.58 MB | EA "Fuel" metrics/telemetry (`com.ea.fuel.metrics.FuelMetrics` JNI) |
| libc++_shared.so | ✓ | ✓ | NDK runtime |
| libarcore_sdk_c/jni.so | ✓ | ✓ | Google ARCore. Linked by libRealRacing3 |
| libcrashlytics*.so (4) | ✓ | ✓ | Firebase Crashlytics NDK |
| libapplovin-native-crash-reporter.so, libgluads_shared.so, libtapjoy.so | ✓ | ✓ | Ads and offerwall SDKs |

**libRealRacing3.so [C] (lief):**
- arm64 SHA-256 `57edb631…aa73051`, build-id `2de55b89018a3c996c8ef863db591296`.
- armv7 SHA-256 `fb8ef2b2…5aa30da`, build-id `be0523be417fdab9f20b68f3cb7cadfa`.
- **Fully stripped.** There is no `.symtab` and no `.debug_*`. The only exports are **124 `Java_*` JNI functions**, with 0 C++ exports. Function names must come from strings, RTTI, JNI cross-references and the FMOD/libc++ import names.
- `NEEDED`: libz, libandroid, liblog, libm, libNimble, libfmodex, libGLESv2, libEGL, libarcore_sdk_c/jni, libc++_shared, libfuelmetrics, libdl, libc. The engine renders with **OpenGL ES** (no Vulkan import).
- `.comment` lists four clang versions (9.0.8, 12.0.9, 14.0.6, 17.0.2) and LLD 12.0.9. [H] This suggests prebuilt static third-party code was linked into the engine.
- JNI namespaces seen: `com.firemint.realracing.MainActivity` (input and lifecycle), `com.firemonkeys.cloudcellapi.*` (CloudCell online layer, e.g. `FacebookWorker`), `csdk.gluads.*`, `csdk.glucentralservices.*` (`ServerEventBus`, `AndroidPlatform`) and `csdk.starlightsecurity.*`. [H] The `csdk.*` names point to Glu-branded SDK components inside the native binary.

The full survey output is in the session scratchpad. It will be copied into `02_NATIVE_ENGINE/SYMBOLS` once that phase is approved.

## 6. Missing or needed items

| Item | Impact | Proposed fix |
|---|---|---|
| Ghidra's Java setting | Ghidra won't launch on the default Java 11 | Set `JAVA_HOME_OVERRIDE` in Ghidra's `support/launch.properties` to the existing JDK 25 path (no download) |
| Git repository | No change tracking yet | `git init` with a `.gitignore` that excludes `TOOLS/`, `.venv/`, `00_ORIGINAL/APK/*.apk` and large generated output |
| APK read-only attribute | The original could be modified by accident | `attrib +R` |
| OBB / game data in project | Not needed now (assets are kept separately) | Reference the external game-data path in the docs instead of copying it |
| Android device or emulator for dynamic tests | Needed later for save/runtime checks | adb is ready. A test device or AVD image is required later |
| `python-requirements.txt` is UTF-16 | `pip install -r` may fail | Re-save as UTF-8 if ever used |

Nothing needs to be downloaded for the next phases.

## 7. Prioritised roadmap

Each phase writes only into its own folder. Long jobs run in the background and log to a file.

**P0 — Project hygiene (small, needs approval)**
1. Set `attrib +R` on the original APK. Record its hashes in `00_ORIGINAL/METADATA/CHECKSUMS.sha256`.
2. Run `git init` with a `.gitignore` that tracks docs, scripts and small analysis output only.
3. Point Ghidra at JDK 25.
4. Create `07_DOCUMENTATION/OPEN_QUESTIONS.md` and `FINDINGS_LOG.md`.

**P1 — Android layer**
1. `apktool d` → `01_ANDROID_ANALYSIS/APKTOOL` (manifest, resources, smali for all 5 DEX files).
2. `jadx` → `01_ANDROID_ANALYSIS/JADX` (Java/Kotlin output, plus a per-DEX class and package census).
3. Document every activity, service, receiver, provider and intent filter, plus the boot path `UnpackAssetsActivity` → `MainActivity`.
4. Classify packages as **game** (`com.firemint.*`, `com.firemonkeys.*`, `com.ea.*`), **EA platform** (Nimble/Synergy, Fuel) or **third-party** (ads, analytics, Firebase, Play services).

**P2 — Native engine setup**
1. Copy the four target `.so` files for both ABIs into `02_NATIVE_ENGINE/LIBRARIES/<abi>/` with checksums.
2. Export JNI, imports, strings and RTTI typeinfo names into `02_NATIVE_ENGINE/SYMBOLS`. RTTI is the main naming source for a stripped C++ binary.
3. Build a two-way **Java ↔ native JNI map**: the 124 exports, `native` methods from JADX and any `RegisterNatives` calls.
4. Run a Ghidra headless import and auto-analysis for `arm64` and `armv7` in separate projects under `02_NATIVE_ENGINE/GHIDRA`, in the background with logs.

**P3 — Engine system map.** Use RTTI class families, string clusters and FMOD/GLES/zlib import call-sites to identify the subsystems: rendering, assets/depot, physics, AI, race/event logic, UI, audio, CloudCell/network, save. Flag third-party code that is statically linked.

**P4 — Local progression and saves.** Trace file I/O and SharedPreferences paths in Java and native code. Identify the save file location, format, integrity checks and encryption, then confirm on a device or emulator. Also cross-check the existing game-data copy.

**P5 — Networking.** Using client code only, list the endpoints, hostnames, protocols (HTTP/JSON, protobuf `.proto` files in the APK root) and auth flows for CloudCell/Synergy/Nimble, Fuel metrics and the Glu `csdk` services. No contact with EA infrastructure.

**P6 — Offline-independence matrix.** For each feature (career, time trials, showroom, store/currency, events, multiplayer, ads, telemetry), record whether it works offline, degrades, or fails without a server. Note the code path that decides each case.

**P7 — Reconstruction design.** Write specs for replacement components such as stub/local service endpoints and a local save and progression authority. Keep new code under `06_RECONSTRUCTION`, clearly separate from the analysis.

## 8. Open questions

1. Does `UnpackAssetsActivity` expect an OBB, or does it download assets? If it downloads, from which source?
2. Is the native boot path tied to a server handshake (CloudCell/Synergy) before the main menu appears?
3. Are saves stored locally and authoritatively, or are they server-synced, encrypted or signed?
4. How much engine logic sits in the statically linked `csdk.*` (Glu) components compared with Firemonkeys code?
5. Does `JNI_OnLoad` (not exported by libRealRacing3) exist, or does every binding rely on `Java_*` symbol names? This needs checking in Ghidra.
6. Does the APK also carry v2/v3 signature blocks? This matters for any later re-signed test build.
