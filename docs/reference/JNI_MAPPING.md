# JNI Mapping — Java ↔ libRealRacing3

Last updated: 2026-11-14 · Confidence labels follow `CLAUDE.md` §7.

Ghidra addresses = ELF virtual address + image base: **`0x100000` on arm64, `0x10000` on armv7** (corrected 2026-11-14; the armv7 addresses in §3 were first converted with the wrong base). This document gives **ELF virtual addresses** unless marked "Ghidra".

## 1. Sources

| Artifact | Producer |
|---|---|
| `02_NATIVE_ENGINE/SYMBOLS/JNI_MAP.tsv` | `SCRIPTS/jni_map.py`: export-name matching plus static `RegisterNatives` table detection |
| `02_NATIVE_ENGINE/ANALYSIS/JNI/<abi>/libRealRacing3.so_RegisterNatives_{hits.tsv,callers.c}` | `SCRIPTS/ghidra/RETR0_JniEnvCalls.java`: functions loading JNIEnv slot 215 (arm64 `0x6b8`, armv7 `0x35c`), with Ghidra decompiler pseudocode |
| Table contents below | Read from the ELF using RELATIVE and symbol relocations (lief) |

## 2. Binding mechanisms

| ID | Finding | ABI | Evidence | Confidence |
|---|---|---|---|---|
| JNI-01 | **libRealRacing3 has no `JNI_OnLoad`.** Neither the symbol table nor Ghidra's analysis finds one | both | lief exports; `RETR0_ProgramStats` `JNI_OnLoad_symbol=false` | CONFIRMED |
| JNI-02 | **124 Java natives bind by exported `Java_*` symbol name** (default JVM lookup). All 124 exports match a Java `native` declaration, except the orphans in §5 | both | `JNI_MAP.tsv` | CONFIRMED |
| JNI-03 | **`RegisterNatives` is called from 6 subsystem initialisers** that run after the library loads. Most are Glu SDK bridges, plus one game-side ad bridge. The registered function pointers are mostly the *same* exported `Java_*` functions (redundant registration) | both | §3 | CONFIRMED (arm64), HIGH (armv7: same tables; the starlightsecurity call goes through a generic helper) |

## 3. `RegisterNatives` call sites

### arm64 (6 true sites out of 9 offset hits; 3 false positives were structure fields at `+0x6b8`)

| Registrar (Ghidra name) | ELF entry | Java class (FindClass / loader string) | Table (ELF) | n | Confidence |
|---|---|---|---|---|---|
| `FUN_00ca7074` (log tag `GoogleNativeAd_Android::BindJavaMethods`, source `src\ndPlatform\ndAndroid\GoogleNativeAd_Android.cpp`) | `0xba7074` | `com/firemint/realracing/GoogleNativeAdManager` | **stack-built** (`local_78`) | 2 | CONFIRMED |
| `FUN_016c6e90` | `0x15c6e90` | `csdk/glucustomersupport/NativeBridge` | `0x1f8ace8` | 5 | CONFIRMED |
| `FUN_017402a8` | `0x16402a8` | `csdk/glucentralservices/util/AndroidPlatform` | `0x1f8ad98` | 10 | CONFIRMED |
| `FUN_01787e44` | `0x1687e44` | `csdk/glucentralservices/eventbus/ServerEventBus` | `0x1f8ae88` | 7 | CONFIRMED |
| `FUN_017b10e0` | `0x16b10e0` | `csdk/gluads/GluAdsNativeBridge` (SDK version string `7.6.4-ec99fc8`) | `0x1f8af30` | 15 | CONFIRMED |
| `FUN_01e2bf58` | `0x1d2bf58` | `csdk/starlightsecurity/platform/AndroidPlatform` | `0x1f93860` | 3 | CONFIRMED |

### armv7 (correlated)

| Registrar | ELF entry | Call | Matches arm64 | Confidence |
|---|---|---|---|---|
| `FUN_005bfd00` | `0x5afd00` | `RegisterNatives(env, cls, &local_38, 2)` (stack table) | GoogleNativeAd | HIGH |
| `FUN_00d79430` | `0xd69430` | `…, 5` | glucustomersupport NativeBridge | HIGH |
| `FUN_00ddb730` | `0xdcb730` | `…, 10`, then a second site `…, 7` | glucentralservices AndroidPlatform and ServerEventBus | HIGH |
| `FUN_00e2d71c` | `0xe1d71c` | `…, 0xf` | GluAdsNativeBridge | HIGH |
| `FUN_00d8a8fc` | `0xd7a8fc` | Generic helper `RegisterNatives(env, cls, param_2, param_3)` | [likely] starlightsecurity (3) | MEDIUM |

False positives on armv7: `FUN_00650b54` and `FUN_011b8b68` (structure fields at `+0x35c`).

## 4. Table contents (arm64, read from the ELF)

| Class | Method | Signature | Native target |
|---|---|---|---|
| GoogleNativeAdManager | `adLoadedCallback` | `(JLcom/google/android/gms/ads/nativead/NativeCustomFormatAd;I)V` | non-exported |
| GoogleNativeAdManager | `onCustomClickCallback` | `(JL…/NativeCustomFormatAd;Ljava/lang/String;)V` | non-exported |
| glucustomersupport.NativeBridge | `destroy` | `(J)V` | `0x15c8efc` |
| | `onQueryNotificationCount` | `(JJLjava/lang/String;)V` | `0x15c8f5c` |
| | `onHelpshiftSessionStarted` / `…Ended` | `(JLjava/lang/String;)V` | `0x15c9074` / `0x15c9184` |
| | `getCurrentActivity` | `(J)Landroid/app/Activity;` | `0x15c9294` |
| glucentralservices.util.AndroidPlatform | `onHTTPResponse`, `onDownloadResponse`, `onTimerEvent`, `onShowConsentComplete`, `onConsentEvent`, `deleteConsentCallbacks`, `onShowWebViewComplete`, `onShowCMPConsentFormComplete`, `onRequestCMPConsentInfoComplete` | see `ANALYSIS/JNI` | exported `Java_*` |
| | `onApplicationEvent` | `(Ljava/lang/String;)V` | **`0x163ffb4` (non-exported)** |
| glucentralservices.eventbus.ServerEventBus | `getMIDHandleEvent`, `shared`, `globalToken`, `subscribe`, `unsubscribe`, `publish`, `publishError` | — | exported `Java_*` |
| gluads.GluAdsNativeBridge | 15 methods (`destroy`, `onPlacementEvent`, `onRewardReceived`, `initAnzuSDK`, `loadNativeAd`, `showNativeAd`, …) | — | exported `Java_*` |
| starlightsecurity.platform.AndroidPlatform | `onApplicationEvent`, `onHandleEvent`, `onTimerEvent` | — | exported `Java_*` |

## 5. Resolution of the earlier "unbound" callbacks (P2 §4)

| Java method(s) | Earlier status | Resolution | Confidence |
|---|---|---|---|
| `GoogleNativeAdManager.adLoadedCallback`, `onCustomClickCallback` (arm64) | unbound | Registered from a **stack-built** table in `FUN_00ca7074`, which the static table scanner cannot see | CONFIRMED |
| `glucustomersupport.NativeBridge.destroy` | unbound | First entry of the table at `0x1f8ace8`. The scanner missed it because the linker tail-merged the `"destroy"` string, so the name pointer points inside a longer string | CONFIRMED |
| `com.firemint.realracing.Http.{complete,data,error,header}Callback` (4) | unbound | **No native implementation**: no export, no registration, and the method names are absent from the binary's strings | HIGH; the Java class is also unreachable (R-04) |
| `com.firemint.realracing.fmNfcManager.{GetNfcDataToTransmitJNI,NfcMessageReceivedJNI}` (2) | unbound | No native implementation (same evidence) | HIGH |
| `com.firemonkeys.cloudcellapi.CC_AmazonStoreObserver_Class.*` (6) | unbound | No native implementation (same evidence) | HIGH |

Orphan exports (native side with no Java declaration): `MainActivity.isTegraGPU`, `MainActivity.initialiseCrashlytics` (libRealRacing3), `org.fmod.FMODAudioDevice.fmodGetInfo/fmodProcess` (libfmodex; the class is not in the DEX), and `com.ea.fuel.metrics.FuelMetrics.NativeCallback` (libfuelmetrics). CONFIRMED absent from the DEX.

## 6. Cross-architecture correlation

| Metric | arm64 | armv7 |
|---|---|---|
| Functions (Ghidra) | 41,165 | 54,793 |
| Default `FUN_` names | 40,856 | 54,483 |
| Thunks | 3,100 | 3,192 |
| JNI export functions | 124 | 124 |
| `JNI_OnLoad` | none | none |
| `RegisterNatives` call sites | 6 | 6 (one through a helper) |

The higher armv7 function count is expected: Thumb/ARM interworking stubs and different inlining. Function counts are **not** comparable one-to-one. Correlate functions by export name, shared string xrefs or source-path strings, not by address.

## 7. Reconstruction implications

- A replacement native library must export the 124 `Java_*` symbols. It does not need a `JNI_OnLoad`.
- The Glu bridges (ads, customer support, central services, security) are self-registering SDK components. An offline build can stub them on the Java side without touching game logic.
- `realracing.Http`, NFC and Amazon-store natives are absent, and their Java classes are unreachable. JADX shows no references from outside the classes themselves, and the native library never names them (UNRESOLVED_FUNCTIONS R-04). They are legacy code to be ignored for reconstruction.
