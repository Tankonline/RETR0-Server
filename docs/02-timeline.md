# 02 · Timeline: everything the project did

This is the project's history in order. Each step names the main result and where it is documented. IDs such as
`NW-93` or `SP-14` refer to findings in the [reference set](reference/).

## Phase 0 · Baseline (2026-11-14)

- Took the original APK (`real-racing-3-14-0-1.apk`, 100.3 MB, 1,822 archive entries, SHA-256
  `dcfe3788…dcad1d5f`) as **immutable evidence**; recorded hashes of the APK, its 28 native libraries and 6 DEX files.
- Set up the project structure, toolchain checks and a Git repository for analysis outputs.
  → [reference/00_INITIAL_ASSESSMENT.md](reference/00_INITIAL_ASSESSMENT.md),
  [reference/TOOLCHAIN_AND_REPRODUCIBILITY.md](reference/TOOLCHAIN_AND_REPRODUCIBILITY.md)

## Phase 1 · Android layer (2026-11-14)

- Decompiled all DEX code with JADX and decoded resources and smali with APKTool.
- Census: 42,335 classes, about 950 of them game, EA or Glu code. Mapped the manifest, permissions, the boot path
  (launcher unpacks `res.zip`, then `MainActivity` loads Nimble → FMOD Ex → RealRacing3) and the signing scheme.
- Found that `network_security_config` allows cleartext HTTP **only to `127.0.0.1`**, which later made the local
  server possible without TLS.

## Phase 2 · Native engine (2026-11-14)

- Copied out both builds of `libRealRacing3.so` (arm64 31.6 MB, armv7 22.6 MB); harvested ~5,100 C++ RTTI type
  names and the statically linked libraries (OpenSSL 3.3.0, libcurl 8.7.1, zlib 1.2.5, Dear ImGui 1.80, Skia, JsonCpp,
  pugixml).
- Imported both ABIs into Ghidra 12.2 (arm64: 41,165 functions on first analysis; armv7: 54,793).
- Mapped all 124 JNI exports to their Java declarations and found the 6 `RegisterNatives` registrars (no `JNI_OnLoad`).
  → [reference/JNI_MAPPING.md](reference/JNI_MAPPING.md)
- **Recovered 506 original source-file names** from 1,506 assert/log strings (`E:\dev\builds\r3_update_a\source\src\…\File.cpp:line`)
  and attributed ~4,000 functions per ABI to their original `.cpp` files.
  → [reference/NATIVE_FUNCTION_CATALOGUE.md](reference/NATIVE_FUNCTION_CATALOGUE.md)
- Traced native startup and the frame loop on both ABIs. → [reference/ENGINE_ARCHITECTURE.md](reference/ENGINE_ARCHITECTURE.md)

## Phase 3 · Systems analysis (2026-11-14 to 2026-11-15)

- **Physics:** fixed 16 ms simulation step with an accumulator; fixed-point position integration; two tyre models;
  kinematic (not spring-damper) suspension; units. → [reference/PHYSICS_ANALYSIS.md](reference/PHYSICS_ANALYSIS.md)
- **Race modes:** 32 `GameMode` subclasses recovered. → [reference/RACE_SYSTEM_ANALYSIS.md](reference/RACE_SYSTEM_ANALYSIS.md)
- **Saves:** location (`files/doc/*.2.dat`), container format, and the full body encoding decoded and validated
  read-only on real save files (byte-exact parse). → [reference/SAVE_SYSTEM_ANALYSIS.md](reference/SAVE_SYSTEM_ANALYSIS.md)
- **Networking:** network stacks, TLS behaviour (CloudCell trusts any certificate), environments and endpoints;
  the CloudCell sync framing decoded; **first clean-room component: the BinaryBlob codec, with tests**.
- Decoded sub-sync batching and the payloads of player rank, garage, PvP servers, upload vehicles, customisation,
  six leaderboards, sales, multiplayer, saved-game download, cloud save, data requests and Race Teams.
- Catalogued all **80 directly queued sub-syncs** (request layouts and reply read orders) and confirmed with a
  whole-library scan that no others exist. → [reference/NETWORKING_ANALYSIS.md](reference/NETWORKING_ANALYSIS.md)
- Recovered missing functions on backed-up Ghidra working copies: arm64 coverage **72.0% → 98.8%** of `.text`,
  armv7 79.8% → 90.7%.

## Phase 4 · First server pieces (2026-11-15)

- Local replacement service, first slice: sync header and auth request/reply decoded; auth, sync dispatch and a
  cloud-save store implemented (43 tests).
- Runtime test plan written and approved by the owner; server selection decoded (fixed table, HTTPS on 443).
- Decoded `CC_SeedData.bin` (the bundled seed archive): game config, localised texts, the **store catalogue**
  (556 products, exact parse and byte-identical rebuild), achievements, a web-file manifest.
- FileManager sync decoded; the service can publish files to the client.

## Phase 5 · Reconstruction groundwork (2026-11-17 to 2026-11-18)

- Build-system audit (CMake/Ninja/NDK present; GLES2/EGL-only renderer).
- C++ reconstructions of the BinaryBlob codec, simulation timing, fixed-point integration, the save-file codec and
  the world-step scheduler (not part of this repository).
- Bulk pseudocode export and function-boundary repair using the unwind tables (+5,416 armv7 functions; 1,554
  merged functions split).
- Decoded the `.nct` car data files and inventoried every game-data file format.
  → [reference/ASSET_FORMAT_INVENTORY.md](reference/ASSET_FORMAT_INVENTORY.md),
  [reference/VEHICLE_SYSTEM_ANALYSIS.md](reference/VEHICLE_SYSTEM_ANALYSIS.md)

## Phase 6 · Running the game against our own server (2026-11-18)

- Built a **network-locked x86_64 test emulator** (Android 14, rooted) whose only route out is DNS to a logging
  resolver on the PC that answers nothing. → [research-tools/](../research-tools/)
- **Run 1:** the game starts, tries to sync, crashes on missing data (an exclusion-list mistake, corrected).
- **Run 3 (fresh install):** reaches the "needs to download 1025 MB" screen; first view of the download flow.
- **Run 4:** a Java-level Frida hook on `HttpRequest.init` records **11,357 requests in 5 minutes**: every CloudCell
  and CDN request passes through that one Java class.
- Decoded the **asset download protocol** exactly (pack layout, key hash, `FMASZ1` compression, MD5 checks) and
  verified it against every recorded byte range. → [09-asset-cdn.md](09-asset-cdn.md)
- **Runs 5–9:** served the CDN from the owner's own data. Missing originals forced **edited lists** inside a
  length-matched `res.zip`. **Run 9: the full download completes with 0 errors.**
- Packaged everything into a single server folder with start/stop/status control.

## Phase 7 · Online again (2026-11-18 to 2026-11-19)

- **Runs 12–13:** answered `/time` (server time in the `X-Request-Start` header) and the guest client's `CC_Sync.php`
  batches. **The game no longer shows OFFLINE.**
- **Runs 14–15:** served the owner's modified asset files through the pack builder, then reverted.

## Phase 8 · Features (2026-11-19 to 2026-11-20)

- **Runs 16–23 · Store preservation grants.** The server gift channel was mapped but froze the game, so the BUY
  buttons were patched instead to grant currency through the game's own non-purchase award.
  → [features/store-grants.md](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/store-grants.md), [features/gifts.md](features/gifts.md)
- **Run 24 · Special events.** The "internet connection is required" popup turned out to be the timed Frida hook
  detaching mid-session. → [features/special-events.md](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/special-events.md)
- **Run 25 · RETR0 client.** The redirect was built into the APK, so Frida is no longer needed to play.
  → [features/server-redirect.md](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/server-redirect.md)
- **Runs 26–29 · Username.** Traced where "Guest" comes from, added a name file set through Enter Racing Code, and
  found and fixed a long-standing server bug (the missing sync reply member header).
  → [features/username.md](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/username.md), [features/sync-reply-header-fix.md](features/sync-reply-header-fix.md)

Every runtime run, with setup and evidence: [reference/RUNTIME_TEST_PLAN.md](reference/RUNTIME_TEST_PLAN.md).
