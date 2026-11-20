# P1 — Android Layer Report

Date: 2026-11-14 · Input: `00_ORIGINAL/APK/real-racing-3-14-0-1.apk` (read-only, SHA-256 `dcfe3788…dcad1d5f`)

**[C]** = confirmed from the file or tool output cited. **[H]** = hypothesis.
JADX output is a *decompilation*: it reconstructs equivalent Java and is not EA's original source. Names come from the DEX metadata, which this build did not obfuscate for game classes.

## 1. Tool runs

| Tool | Command (abridged) | Output | Result |
|---|---|---|---|
| APKTool 3.0.3 (JDK 21) | `apktool d -o 01_ANDROID_ANALYSIS/APKTOOL/rr3_14.0.1 <apk>` | 270 MB: manifest, `res/`, `smali` … `smali_classes5`, `assets`, `lib`, `unknown` | **Exit 0** — log `LOGS/apktool.log` |
| JADX 1.5.6 (JDK 21, `-Xmx16g`) | `jadx -d 01_ANDROID_ANALYSIS/JADX/rr3_14.0.1 -j 16 --show-bad-code <apk>` | 158 MB, 24,649 `.java` files (17,770 top-level classes processed) | **Finished with 78 decompilation errors.** This is normal for a project this size: the affected methods are kept as raw or "bad" code (`--show-bad-code`). Log `LOGS/jadx.log`. Exit code 1 is caused only by that error count |
| `SCRIPTS/dex_census.py` | Direct DEX parser, no decompiler | `DEX_CENSUS/` | 6 DEX files, 42,335 classes, 431 Java `native` methods |
| `SCRIPTS/manifest_report.py` | Parses APKTool's manifest | `MANIFEST/MANIFEST_REPORT.md`, `components.tsv` | 117 components |
| `apksigner verify -v` | — | — | See §6 |

The output folders are git-ignored because they are large and can be regenerated. The scripts and reports are tracked.

## 2. DEX files [C]

| DEX | Classes | Method refs | Dominant content |
|---|---|---|---|
| classes.dex | 8,713 | 65,057 | AndroidX, AppLovin |
| **classes2.dex** | 9,505 | 60,228 | **Game Java code** (`com.firemint.realracing`, `com.firemonkeys.cloudcellapi`, `com.ea.nimble`, `com.ea.eadp`), Facebook SDK, Google Play, ironSource, Fyber |
| classes3.dex | 10,837 | 65,289 | Google Play services, Firebase, ARCore, protobuf, Gson |
| classes4.dex | 8,701 | 57,055 | **Glu `csdk.*` Java bridges**, Mintegral, Unity Ads, Vungle, Tapjoy, ironSource |
| classes5.dex | 2,103 | 19,972 | `gatewayprotocol.v1` (608 classes, protobuf-generated), Apache HTTP, kotlinx.coroutines |
| assets/audience_network.dex | 2,476 | 21,428 | Facebook Audience Network, loaded at runtime |

**Game, EA and Glu code makes up about 950 of the 42,335 classes (~2%).** The rest is ads, analytics or platform SDKs. In detail:

| Package | Classes | Role (from class names) |
|---|---|---|
| `com.ea.nimble` | 312 | EA Nimble platform: identity, MTX, tracking, push, web views |
| `com.firemint.realracing` | 161 | Game shell: activities, GL view, input, audio stream, notifications, NFC, controllers |
| `com.firemonkeys.cloudcellapi` | 112 | CloudCell: HTTP, TLS trust manager, store workers, Facebook/Google Play workers, asset-manager service |
| `com.ea.eadp` | 27 | EADP push notifications |
| `csdk.gluads.*` | ~150 | Glu ads mediation (MAX, ironSource, Tapjoy) |
| `csdk.glucentralservices.*` | ~55 | Glu central services: consent, device tiers, KV store, network, event bus, web view |
| `csdk.glucustomersupport.*` | ~76 | Customer support (Helpshift) |
| `csdk.starlightsecurity.*` | 18 | "Starlight security" platform bridge |
| `com.ea.fuel`, `com.ea.ironmonkey`, `csdk.revsdk` | 1 each | Metrics and other single-class shims |

The full table is in `DEX_CENSUS/dex_package_census.csv`.

### Java `native` methods (Java side of JNI) [C]

431 in total; the full list is in `DEX_CENSUS/java_native_methods.tsv`. Grouped by owner:

| Owner | Count | Native library [H until P2 map] |
|---|---|---|
| `com.google.ar.core` | 256 | libarcore_sdk_jni |
| `com.firemint.realracing` | 50 | libRealRacing3 |
| `com.firemonkeys.cloudcellapi` | 39 | libRealRacing3 |
| `com.tapjoy.internal` | 24 | libtapjoy |
| `csdk.gluads` | 15 | libRealRacing3 / libgluads_shared |
| `com.ea.nimble.bridge` | 13 | libNimble / libRealRacing3 |
| `csdk.glucentralservices.*` | 17 | libRealRacing3 |
| `csdk.glucustomersupport` | 5 | libRealRacing3 |
| `com.applovin.impl.sdk` | 4 | libapplovin-native-crash-reporter |
| `csdk.starlightsecurity.platform` | 3 | libRealRacing3 |
| Crashlytics NDK, `com.ea.fuel.metrics`, gms tasks | 5 | own libraries |

For comparison, libRealRacing3 exports exactly 124 `Java_*` symbols. The ~125 game-side natives above roughly match that. P2 will match them name by name.

## 3. Manifest [C]

- Package `com.ea.games.r3_row`; minSdk **26**, targetSdk 36; versionName 14.0.1 / versionCode 14001.
- Application class: `androidx.multidex.MultiDexApplication`, with `largeHeap=true`, `extractNativeLibs=false` (the `.so` files load straight from the APK), `isGame=true` and `sensorLandscape`.
- `uses-feature glEsVersion=0x20000` (**GLES 2.0 minimum**). Camera, accelerometer, touchscreen and gamepad are all optional.
- **`network_security_config.xml` allows cleartext HTTP only to `127.0.0.1`** (with subdomains); everything else must use TLS. This matters for P7: a local replacement service on loopback would be allowed plain HTTP by the platform config. Any app-level TLS pinning (`CloudcellTrustManager`) is a separate question for P5.
- Meta-data `com.ea.nimble.configuration = live`. Nimble MTX verification, tracking and Push-TNG keys are referenced by resource ID. Credential values have been deliberately left out of the docs.
- Firebase analytics, Crashlytics and performance collection are all `false` by default in meta-data. Facebook auto-init and auto-logging are off.

### Components

| Kind | Game / EA / Glu | Third-party |
|---|---|---|
| Activities | 5 | 61 |
| Services | 6 | 15 |
| Receivers | 5 | 16 |
| Providers | 0 | 9 |

Game, EA and Glu components:

| Kind | Name | Exported | Notes |
|---|---|---|---|
| activity | `com.firemint.realracing.UnpackAssetsActivity` | yes | **LAUNCHER**; deep links `rr3://` and `vnd.google.deeplink` |
| activity | `com.firemint.realracing.MainActivity` | — | The game activity |
| activity | `com.ea.nimble.CustomTabActivity`, `com.ea.nimble.WebView` | — | Nimble web UI |
| activity | `com.ea.nimble.AuthResultActivity` | yes | OAuth/auth redirect (VIEW/BROWSABLE) |
| service | `com.firemint.realracing.DelayedNotificationService` | yes | Local notifications |
| service | `com.firemint.realracing.RRPushService` | no | FCM `MESSAGING_EVENT` |
| service | `com.firemint.realracing.RRPushTNGIntentService` | — | Push |
| service | `com.firemonkeys.cloudcellapi.AndroidAssetManagerService` | no | [H] background asset or depot downloads |
| service | `com.ea.nimble.pushtng.NimblePushTNGIntentService` / `…BroadcastReceiver` | — / no | Push |
| receiver | `com.ea.nimble.ReferrerReceiver` | yes | Install referrer |
| receiver | `com.firemint.realracing.LocalNotificationBroadcastReceiver` | yes | Local notifications |
| receiver | `com.firemint.realracing.BootReceiver` | yes | `BOOT_COMPLETED` (reschedules notifications) |
| receiver | `com.firemint.realracing.RRPushTNGBroadcastForwarder` | yes | EADP push forward |
| receiver | `com.ea.nimble.NimbleLocalNotificationReceiver` | no | Local notifications |

All third-party components (ads, Firebase, Play services, Facebook and others) are listed in `MANIFEST/MANIFEST_REPORT.md`.

## 4. Boot path [C, from JADX]

```
Launcher ─► UnpackAssetsActivity.onCreate
            ├─ ANRWatchDog → Crashlytics
            ├─ CheckStorage(): external storage must be "mounted", otherwise a STORAGE_ERROR dialog
            └─ ExtractAndLaunch()
                 ├─ game already running → TransitionToGameActivity()
                 └─ UnpackAssetsAsyncTask(<extDir>)  where <extDir> = getExternalFilesDir(null)
                       (or the legacy /Android/data/<pkg>, chosen by Platform.ShouldUseLegacyExternalFilesDir)
                       └─ Platform.extractRes(extDir, extDir + "/apk/")
                            ├─ compares res/raw/checksum.md5 (bundled: f2ba88a9…) with <extDir>/apk/checksum.md5
                            ├─ reads <extDir>/.depot/asset_list_base.txtCache.txt (asset cache list)
                            ├─ if different: unzips res/raw/res.zip (12.1 MB, 1,550 entries under res/) → <extDir>/apk/
                            └─ writes checksum.md5 → success
            OnExtractionComplete → TransitionToGameActivity() → MainActivity (same intent)

MainActivity  <clinit>: System.loadLibrary(com.ea.nimble.Global.NIMBLE_ID = "Nimble"), "fmodex", "RealRacing3"
              onCreate → creates GLView (GLES) → lifecycle forwarded to native:
              onCreateJNI, onStartJNI, onResumeJNI, onViewCreatedJNI, onViewChangedJNI, onViewRenderJNI(w,h),
              onTouch{Begin,Move,End,Cancel}JNI, onKey{Pressed,Released}, onPauseJNI, onStopJNI, onDestroyJNI …
```

**Answer to Q1 (partial):** the launcher **does not download anything**. It only unpacks the bundled `res/raw/res.zip` into `<extDir>/apk/`. The main game data is kept separately under `<extDir>/.depot/` (the "depot"). [H] Downloading or validating the depot happens later, from native code and/or `AndroidAssetManagerService`. Q1 remains open for that part.

## 5. Notable Java-side classes for later phases

| Class | Why it matters | Phase |
|---|---|---|
| `com.firemint.realracing.Platform` | Storage paths, asset extraction, gallery save, asset manager. It is the native→Java helper surface | P4 |
| `com.firemint.realracing.Http`, `cloudcellapi.HttpRequest`, `HttpThread` | Java HTTP transport used by native code | P5 |
| `cloudcellapi.CloudcellTrustManager`, `TLSSocketFactory`, `Security` | TLS trust and possible certificate pinning | P5 / P7 |
| `cloudcellapi.GooglePlayWorker`, `CC_AmazonStoreWorker_Class`, Nimble MTX | Store and in-app purchase flows | P5 / P6 |
| `com.firemint.realracing.NimbleManager` + `com.ea.nimble.*` | EA identity and services initialisation | P5 / P6 |
| `com.firemint.realracing.CheatView` | Developer cheat-input UI (`onCheatInputDone` native) | P3 |
| `com.firemint.realracing.CarLiveryBaker` | Livery rendering helper | P3 |
| `gatewayprotocol.v1.*` (classes5) | Protobuf gateway protocol, generated code ([H] owner SDK still to identify) | P5 |

## 6. Signing [C]

`apksigner`: **v2 and v3 verified**, 1 signer, `CN=EAM, OU=EAM, O=EAM, L=LA, ST=CA, C=US`, DSA-1024, certificate SHA-256 `5bff7d61…a5f0d2`. The v1 (JAR) files `META-INF/EAMKEYST.*` are present. apksigner reports v1 as not verified, [H] because it does not check v1 when minSdk ≥ 24. **This answers Q6.** Any rebuilt test APK will need a different key, so it cannot install over a stock installation.
