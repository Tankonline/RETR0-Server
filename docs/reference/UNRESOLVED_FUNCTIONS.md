# Unresolved Functions and Items

Functions and bindings whose role, binding or behaviour is not yet established. When an item is resolved, move it to the bottom section with its evidence.

## Open

| ID | Item | ABI | Address | What is known | What is missing |
|---|---|---|---|---|---|
| U-01 | Generic `RegisterNatives` helper | armv7 | `FUN_00d8a8fc` (ELF `0xd7a8fc`) | Calls `RegisterNatives(env, cls, methods, n)` with caller-supplied arguments | Which callers use it; assumed to be starlightsecurity (MEDIUM) |
| U-02 | Second armv7 `…, 7` registration site | armv7 | Near `DAT_00e0f828` | Table size matches ServerEventBus (7) | Exact containing function (decompiler output attributed it ambiguously) |
| U-04 | `glucentralservices.AndroidPlatform.onApplicationEvent` native body | arm64 | `0x163ffb4` | Non-exported; bound through table `0x1f8ad98` | Behaviour |
| U-06 | armv7 `PrizePackage.cpp` seed span over 1 MB (arm64 compact) | armv7 | `0x85a074`–`0x96af74` | Foreign seeds inside the span; the bracketing gap cap prevents mis-attribution | Why: [H] out-of-line template/inline copies in other compilation units |
| U-07 | Remaining physics internals | arm64 | `0x158e5bc` (low-speed lateral), `0x158e220` (4 body force points), `0x1573600` (phase B), `0x1585a2c` (phase A) | Solver, tyres A/B, drivetrain, contact/walls documented (PH-13..35) | Position-unit check (PH-42: 1 unit = 4 mm if consistent); g value. Spring question resolved: the suspension is kinematic (PH-36..41) |
| U-08 | Purpose of the force-fixed-step flag | arm64 | GOT `0x1f6f2e0` | Replaces frame dt with 16 | Who sets it (replay? automation?) |
| U-09 | `GameMode` slot 14 (pure virtual, overridden by 31/32 modes) | both | — | — | Role |
| U-05 | ~40,856 (arm64) / ~54,483 (armv7) functions with default names | both | — | — | Attribution, starting with source-path xrefs (roadmap B-01) |

## Resolved

| ID | Item | Resolution | Ref |
|---|---|---|---|
| R-01 | `GoogleNativeAdManager.adLoadedCallback` / `onCustomClickCallback` (arm64) | Registered from a stack-built table in `FUN_00ca7074` | `JNI_MAPPING.md` §5 |
| R-02 | `glucustomersupport.NativeBridge.destroy` | Table `0x1f8ace8`, entry 0 (tail-merged name string) | `JNI_MAPPING.md` §5 |
| R-04 | Callers of `realracing.Http`, `fmNfcManager`, `CC_AmazonStoreObserver/Worker_Class` | **Unreachable in this build (HIGH).** In JADX each class is referenced only by itself or its pair class. libRealRacing3 has no string naming any of them, so native code cannot `FindClass` them by literal. Only reflection with a runtime-built name is unexcluded | JADX grep; `strings.tsv` |
| R-03 | Absence of `JNI_OnLoad` in libRealRacing3 | Confirmed; registration is done by subsystem initialisers instead | `JNI_MAPPING.md` §2 |
