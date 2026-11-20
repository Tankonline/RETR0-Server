# P2 — Native Engine Setup Report

Date: 2026-11-14 · Inputs: the 4 target libraries × 2 ABIs, copied byte-for-byte from the original APK.

**[C]** = confirmed from the output or file cited · **[H]** = hypothesis.
Every name below was **recovered from the binary**: export symbols, RTTI typeinfo-name strings or literal strings. Nothing was invented. The binaries are stripped, so internal function names are *not* available, and Ghidra shows functions as `FUN_xxxxxxxx` until someone analyses and names them.

## 1. Working copies [C]

`02_NATIVE_ENGINE/LIBRARIES/<abi>/` holds `libRealRacing3.so`, `libNimble.so`, `libfmodex.so` and `libfuelmetrics.so`, set read-only. `LIBRARIES.sha256` passes `sha256sum -c` and matches `00_ORIGINAL/METADATA/CHECKSUMS.sha256`.

## 2. Symbol harvest — `SCRIPTS/native_symbols.py` → `SYMBOLS/<abi>/<lib>/`

| ABI | Library | Exports | Imports | Strings ≥5 | RTTI types | URL/host strings | RegisterNatives entries |
|---|---|---|---|---|---|---|---|
| arm64 | libRealRacing3 | 124 | 684 | 69,789 | **5,058** | 63 | 5 |
| armv7 | libRealRacing3 | 124 | 716 | 126,446 | **5,127** | 62 | 7 |
| arm64 / armv7 | libfmodex | 1026 / 934 | 94 / 110 | 3,446 / 2,634 | 33 / 13 | 0 | 0 |
| arm64 / armv7 | libfuelmetrics | 19 | 242 / 233 | 11,669 / 12,521 | 148 | 6 | 0 |
| arm64 / armv7 | libNimble | 3 | 5 / 6 | 43 / 63 | 0 | 1 | 0 |

Files per library: `exports.tsv`, `imports.tsv`, `strings.tsv` (file offset and section), `rtti_types.tsv` (mangled and demangled), `urls.txt` and `jni_register_tables.tsv`. libRealRacing3 also has `RTTI_GROUPS.md`.

**RTTI is the main naming source.** The binary has no `.symtab`, but C++ typeinfo-name strings remain in `.rodata` for about 5,100 polymorphic classes. Each one was confirmed by demangling with `llvm-cxxfilt` from NDK 28.

## 3. Engine system map from RTTI (arm64) [C names, H roles]

The counts are unique types per group. The role column is inferred from the class names only.

| Group | Types | Example classes (verbatim) | Inferred role [H] |
|---|---|---|---|
| `std::` | 2,452 | — | libc++ templates (lambdas, `function`, `shared_ptr` control blocks) |
| `FrontEnd2::` | 505 | `CarPurchaseScreen`, `CareerGroupScreen`, `AssetDownloadScreen`, `ChampionshipRoundHubScreen` | Menus and UI screens |
| `Sk*` (global + `Sk…::`) | ~330 | `SkBitmap`, `SkLinearGradient`, `SkTypeface` | **Skia** 2D graphics (statically linked) |
| `mtShader*`, `mtTextureManager`, `mtShaderUniformCache*` | ~230 | `mtShaderUniformCacheGL…` | Renderer (GL) |
| `cc::` | 125 | `AccountManager`, `AssetManager`, `GameSaveManager`, `HttpRequestManager`, `BanningManager`, `EnvironmentManager`, `GameConfigManager` | **CloudCell** client: online services, assets, cloud save, config |
| `FeatSystem::` / `JobSystem::` | 107 / 38 | `FastestLapFeat`, `FaultlessRaceFeat`, `AchievementManager`, `WinRaceFeatGroup` | Goals, achievements and event objectives |
| `EA::` | 90 | `EA::Nimble::Base::NimbleCppHttpClient`, `…BridgeSynergyRequestCallback`, `EA::EADP::PushNotification::…` | EA Nimble/Synergy C++ side |
| `Framework::` | 52 | `Event`, `SafeEvent`, `SingleFireEvent` | Event framework |
| `m3g::` | 39 | `World`, `Mesh`, `SkinnedMesh`, `Deserializer`, `AnimationTrack`, `Texture2D` | Scene graph named after **M3G** (JSR-184). [H] Firemint's legacy model/scene format and loader |
| `Characters::` | 34 | `Car`, `Garage`, `CarUpgrade`, `Gold`, `RDollars`, `MDollars`, `Reward_Car` | **Player profile**: cars, garage, currencies, rewards |
| `Car*` (global) | 38+ | `CarEntity`, `CarPerformance`, `CarAiClassic`, `CarAiNASCARClassic`, `CarDamageTask`, `CarLiveryManager`, `CarBodyPart_Door` | Vehicle entity, AI, damage, livery |
| `fmRUDP::` | 24 | `ClockSyncPacket`, `DataAckPacket`, `BroadcastDiscoveryPacket`, `PingPacket` | Firemint **reliable-UDP** layer (real-time multiplayer; has LAN discovery) |
| `Net*` / `Online*` | ~15 | `NetEventListener_LAN_P2P`, `NetEventListener_Bot`, `OnlineMultiplayerScheduleSync` | Multiplayer session logic, including LAN P2P |
| `Quests::` | 13 | `LeMansQuestManager`, `F12019GPQuestManager`, `TutorialQuestManager` | Special event / quest managers |
| `CareerEvents::` | 6 | `CareerStream`, `CareerTier`, `EventResolver` | Career structure |
| `SaveSystem::` | 5 | `Serialiser`, `FMUserDataSerialiser`, `ToMemorySerialiser`, `FromMemorySerialiser` | **Local save serialisation** (P4 entry point) |
| `audio::` | 9 | `FMODSoundDevice`, `NullSoundDevice`, `CarEngineDebugger`, `MusicPlayer` | Audio abstraction over FMOD |
| `PopCap::ServicePlatform::` | 13 | `IMarketingComponent`, `INetworker`, `FallBackAdImpl` | PopCap service platform (marketing/ads) |
| `gluads` / `glucentralservices` / `glucustomersupport` / `starlightsecurity` / `revsdk` / `gluanalytics` | 32 | — | Glu SDK C++ cores (statically linked) |
| `Json::`, `pugi::` | 4, 3 | — | JsonCpp, pugixml |
| `MachineLearning::` | 3 | `StreamWriter`, `MemoryBufferWriter` | [H] Telemetry or data-export writers |

The full lists are in `SYMBOLS/<abi>/libRealRacing3/RTTI_GROUPS.md`.

### Third-party code statically linked into libRealRacing3 [C, from version or licence strings]

| Component | Evidence string |
|---|---|
| OpenSSL **3.3.0** | `OpenSSL 3.3.0 9 Apr 2024` |
| libcurl **8.7.1** | `libcurl/8.7.1` and curl.se doc URLs |
| zlib **1.2.5** (deflate/inflate) | `deflate 1.2.5 Copyright 1995-2010 …` (libz.so is also dynamically linked) |
| Dear ImGui **1.80 WIP** | `Dear ImGui %s`, `1.80 WIP` (debug UI) |
| Skia | ~330 `Sk*` RTTI types |
| JsonCpp, pugixml | `Json::`, `pugi::` RTTI |

## 4. Java ↔ native JNI map — `SCRIPTS/jni_map.py` → `SYMBOLS/JNI_MAP.tsv`

| Binding | arm64 | armv7 | Meaning |
|---|---|---|---|
| `export` (game/EA/Glu) | 124 | 124 | Java `native` method ↔ `Java_*` symbol, **all 124 exports matched** |
| `register` (game/EA/Glu) | 5 | 7 | Bound by a `RegisterNatives` table found through RELATIVE relocations: `csdk.glucustomersupport.NativeBridge` ×4, `csdk.glucentralservices.util.AndroidPlatform.onApplicationEvent`, plus armv7 only `GoogleNativeAdManager.adLoadedCallback` and `onCustomClickCallback` |
| `unbound` (game/EA/Glu) | 15 | 13 | No export, no table entry and **no name string** in libRealRacing3: `realracing.Http.{complete,data,error,header}Callback`, `fmNfcManager.*JNI`, `CC_AmazonStoreObserver_Class.*`, `NativeBridge.destroy`, and the `GoogleNativeAdManager` pair on arm64 |
| `unbound` (third-party) | 287 | 287 | ARCore, Tapjoy, AppLovin and others; these bind to their own libraries (not mapped) |
| `export-orphan` | 5 | 5 | Native export with no Java declaration: `MainActivity.isTegraGPU`, `MainActivity.initialiseCrashlytics` (libRealRacing3), FMOD's `org.fmod.FMODAudioDevice` ×2, `FuelMetrics.NativeCallback` |

Findings:
- **[C]** Most bindings use exported `Java_*` names. `RegisterNatives` is used only for a few Glu bridges.
- **[C]** The Java classes `com.firemint.realracing.Http`, `fmNfcManager` and `CC_AmazonStoreObserver_Class` have **no native implementation** in this build (the method names don't even appear as strings). Calling them would throw `UnsatisfiedLinkError`. [H] They are legacy, dead paths. Native HTTP goes through the statically linked libcurl and OpenSSL and/or `cc::AndroidHttpRequestWorker`.
- **[H]** arm64 contains the string `adLoadedCallback` but no table was detected, so it may use a different table layout. To check in Ghidra.
- **[C]** FMOD's Java helper class `org.fmod.FMODAudioDevice` is **absent from the DEX** while libfmodex exports its natives. [H] The game drives audio output from native code (Android audio APIs).

## 5. Network-relevant strings (evidence for P5 only; nothing was contacted) [C]

The hostnames embedded in libRealRacing3 include the `*.cloudcell.com` family (`0037-connect.cloudcell.com`, `0037-assets.cloudcell.com`, `0037-mp3/mp6.cloudcell.com`, `be01prr3mp01.cloudcell.com`, plus stage, sandbox and dev variants), `0037-draper.cloudcell.ea.com`, `draper.k.awspopcap.com`, `firemonkeys.akamaized.net`, the EA MCT hosts (`prd1.accnt.ea-mct-live.com`, `prd1.echo.ea-mct-live.com`) and the Glu hosts (`*.glulive.com`). The full list is in `SYMBOLS/<abi>/libRealRacing3/urls.txt`. [H] The prefix `0037` looks like a CloudCell game ID for RR3.

## 6. Ghidra projects

`SCRIPTS/ghidra_import.cmd <abi> <project>` runs headless import and full auto-analysis of the 4 libraries. Settings: 12 GB heap, `-max-cpu 12`, a 6-hour per-file timeout, and `-overwrite`.

| Project | Location | Status |
|---|---|---|
| `RR3_arm64` | `02_NATIVE_ENGINE/GHIDRA/arm64-v8a/` | _see §6.1_ |
| `RR3_armv7` | `02_NATIVE_ENGINE/GHIDRA/armeabi-v7a/` | _see §6.1_ |

Setup issues fixed during this phase:
1. Bash → cmd quoting breaks on the project path's spaces, so the analysis is now launched through a `.cmd` wrapper from PowerShell.
2. Ghidra rejects paths containing `\..`, so the wrapper normalises the project root.
3. A `Start-Job` launch was killed when its shell exited; the analysis now runs as a tracked background task. That interrupted run left a partial project, which `-overwrite` replaces.

Statistics script: `SCRIPTS/ghidra/RETR0_ProgramStats.java` is read-only. It reports function counts, `FUN_` defaults and whether a `JNI_OnLoad` symbol exists.

### 6.1 Analysis results

**arm64 (`RR3_arm64`)**: import and full auto-analysis of all 4 libraries succeeded (exit 0) in about 13 minutes (01:27 → 01:40). The log has 8 `ERROR` lines, all function-creation conflicts such as "body contains referring thunk", which do not stop the analysis. Ghidra rebases the libraries at image base `0x100000`, so ELF virtual address `X` appears in Ghidra as `X + 0x100000`.

| Program | Functions | Still `FUN_` (unnamed) | Thunks | External | JNI export functions | `JNI_OnLoad` |
|---|---|---|---|---|---|---|
| libRealRacing3.so | **41,165** | 40,856 (99.2%) | 3,100 | 671 | 124 | **no** |
| libfmodex.so | 2,813 | 2,008 | 576 | 93 | 2 | no |
| libfuelmetrics.so | 6,942 | 6,740 | 551 | 241 | 3 | yes |
| libNimble.so | 20 | 15 | 11 | 5 | 0 | yes |

(Produced by `RETR0_ProgramStats.java`, run read-only.)

- **[C]** libRealRacing3 has no `JNI_OnLoad` symbol. Ghidra finds **no direct references** to the arm64 `RegisterNatives` tables at `0x1f8ad00` and `0x1f8ae40` (`RETR0_XrefsTo.java`). [H] The tables are reached through computed pointers that the auto-analysis did not resolve. Q5 and Q11 stay open for manual analysis.

**armv7 (`RR3_armv7`)**: import and analysis of all 4 libraries succeeded (exit 0; 01:27 → 01:53). The log has 13 `ERROR` lines, again function-creation conflicts.

| Program | Functions | Still `FUN_` | Thunks | External | JNI export functions | `JNI_OnLoad` |
|---|---|---|---|---|---|---|
| libRealRacing3.so | **54,793** | 54,483 | 3,192 | 702 | 124 | **no** |
| libfmodex.so | 2,557 | 1,699 | 296 | 112 | 2 | no |
| libfuelmetrics.so | 6,969 | 6,768 | 527 | 231 | 3 | yes |
| libNimble.so | 15 | 10 | 9 | 5 | 0 | yes |

**Update (Phase A):** the `RegisterNatives` call sites have been located on both ABIs, and the unbound callbacks are resolved. See `07_DOCUMENTATION/JNI_MAPPING.md`, which replaces §4's "unbound" and "[H] arm64 table" notes.
