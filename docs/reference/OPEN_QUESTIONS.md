# Open Questions

When a question is answered, move it to **Resolved** and add the answer, its evidence and a link to the matching `FINDINGS_LOG.md` entry.

## Open

| # | Question | Area | How to answer |
|---|---|---|---|
| Q1 | **Partly answered (see Resolved).** Who fills `<extFilesDir>/.depot/`, and from where? Native code, `AndroidAssetManagerService`, or both? | Boot / Network | JADX `AndroidAssetManagerService`; native depot code |
| Q2 | Does any startup step wait for CloudCell/Synergy now that the servers are gone? Static evidence suggests offline play is designed in (NW-13..16) | Network | Runtime test with networking disabled (owner approval) |
| Q4 | How much engine logic is in the `csdk.*` (Glu) components compared with Firemonkeys code? | Native | RTTI and strings census |
| Q8 | Which SDK owns `gatewayprotocol.v1` (608 protobuf classes in classes5)? | Network | JADX package references |
| Q9 | Does native TLS (libcurl + OpenSSL 3.3.0) use its own CA bundle or pinning, separate from Android's network config? | Network | Ghidra: curl option setup (CAINFO, PINNEDPUBLICKEY) |
| Q20 | ~~Should undefined code be turned into functions?~~ **Done 2026-11-14 on a backed-up working copy (owner approved): coverage 72.0 % → 98.79 %** (ENGINE_ARCHITECTURE "Function recovery") | Native | `RETR0_RecoverFunctions.java` |
| Q21 | armv7 remainder: **answered in part** (ENGINE_ARCHITECTURE, armv7 recovery): unreferenced prologue-led functions recovered (+811, 90.68 %); 910 of 918 failed pointers point to data. **Still open:** 648 KB of small prologue-less Thumb-decodable runs, [likely] fragments of existing functions (switch cases / non-returning-call artefacts), and 173 KB unknown. **2026-11-17:** the two suggested causes are ruled out — no switch tables are unrecovered (all jump-table warnings are tail calls) and all 422 no-return flags are correct (`BOUNDARY_REPAIR/README.md`); next lead: 6,914 armv7 call sites to non-returning functions are followed by undefined bytes (literal pools?). **2026-11-17 (later): largely ANSWERED** — the bytes were real functions missing from Ghidra: 5,416 functions created at `.ARM.exidx` starts; undefined armv7 .text 1.08 MB → 0.40 MB, unknown 658 KB → 160 KB (`BOUNDARY_REPAIR/README.md` §6). Remaining: 1,893 exidx starts inside merged Ghidra functions | Native | `FUNCTIONS/recovery_armv7/prologues/` |
| Q22 | **ANSWERED 2026-11-18 (HIGH): yes, wheel radii (front +0x24, rear +0x34) — VEHICLE_SYSTEM_ANALYSIS VH-06/VH-07; the object is probably not suspension data and its source file is still unknown.** Update: source is `carappearances.appearances.nct` via `0xc60e84` (VH-09..VH-11), values in metres match real cars. ~~Are suspension-data fields `+0x24`/`+0x34` the front/rear **wheel radii** rather than suspension travel? World-step phase B (`0xc28338`) divides car speed by them to spin the wheels (PHYSICS_ANALYSIS §2c). Check against the `.suspensiondata.nct` values of a known car (2026-11-18)~~ | Physics | `SOURCE_EVIDENCE/world_step/`, `PHYSICS/arm64-v8a/tick_phases/at_0xc28338_decomp.c` |
| Q13 | How is `[EHV]`/`[H]` protection computed (not pursued, see SV-22)? (The `.2.` infix part is answered: a fixed literal `"%s.2.%s"` in the name builder `0x139e52c`, NW-28; why `2` remains unknown.) | Saves | Loader `0x139dbb8`; owner decision for EHV |

## Resolved

| # | Answer | Evidence |
|---|---|---|
| Q1a | The launcher does not download anything and does not use an OBB. It unpacks the bundled `res/raw/res.zip` into `<extFilesDir>/apk/`, gated by `checksum.md5` | `P1_ANDROID_LAYER.md` §4 |
| Q5a | The 124 game JNI methods bind through exported `Java_*` symbols. `RegisterNatives` tables cover 5 (arm64) / 7 (armv7) Glu bridge methods | `P2_NATIVE_ENGINE.md` §4 |
| Q5 | There is no `JNI_OnLoad`. `RegisterNatives` is called by 6 subsystem registrars per ABI | `JNI_MAPPING.md` |
| Q11 | The arm64 GoogleNativeAd table is built on the stack inside `FUN_00ca7074`, so static table scanning cannot see it | `JNI_MAPPING.md` §3 |
| Q3 | Saves are local and authoritative: `files/doc/*.2.dat`, XOR-obfuscated with a fixed key, with an XOR checksum; cloud save is a separate upload/restore feature | `SAVE_SYSTEM_ANALYSIS.md` SV-06..17 |
| Q10 | `FMUserData` is the local save container; `cc::GameSaveManager` is the cloud upload/download of the save blob | `SAVE_SYSTEM_ANALYSIS.md` |
| Q12 | Header `field_a` = number of key-dictionary entries; `field_b` = number of ints in the dictionary | `SAVE_SYSTEM_ANALYSIS.md` SV-07 |
| Q7 | `CloudcellTrustManager` does not pin and does not validate the CA chain. It only checks expiry when the SSL-check flag is set; hostname verification is disabled, process-wide | `NETWORKING_ANALYSIS.md` NW-06/07 |
| Q6 | v2 and v3 signatures verify; 1 signer, `CN=EAM`, DSA-1024 | `P1_ANDROID_LAYER.md` §6 |
