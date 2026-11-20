# Toolchain and Reproducibility

How every analysis output in this repository was produced. Update this file whenever a command or tool changes.

## Tools actually used (verified 2026-11-14)

| Tool | Path used | Version check | Notes |
|---|---|---|---|
| APKTool | `TOOLS\APKtool\apktool_3.0.3.jar` (run with `C:\Program Files\Java\jdk-21.0.10`) | `--version` → 3.0.3 | `CLAUDE.md` also mentions `C:\tools\APKTool`; the in-project jar was used for all outputs |
| JADX | `TOOLS\JADX\bin\jadx.bat` (JDK 21, `JAVA_OPTS=-Xmx16g`) | `--version` → 1.5.6 | |
| Ghidra | `TOOLS\GHIDRA\ghidra_12.2_PUBLIC` | `application.version=12.2` | `support\launch.properties` has `JAVA_HOME_OVERRIDE` set to Temurin JDK 25.0.5.8. The original file is backed up at `BACKUPS\ghidra_launch.properties.orig` |
| Python | `.venv\Scripts\python.exe` 3.14.2, always run with `-I` | | Uses lief 1.0.0, capstone 5.0.9, defusedxml 0.7.1 |
| llvm-cxxfilt | `%LOCALAPPDATA%\Android\Sdk\ndk\28.2.13676358\toolchains\llvm\prebuilt\windows-x86_64\bin\` | | Demangles RTTI names |
| aapt2 / apksigner | `%LOCALAPPDATA%\Android\Sdk\build-tools\36.0.0\` | | |

## Pipeline

| Step | Command | Output (git-tracked?) |
|---|---|---|
| Checksums | `sha256sum` and a zip-member hash script | `00_ORIGINAL/METADATA/CHECKSUMS.sha256` (yes) |
| Resource / manifest decode | `java -jar apktool_3.0.3.jar d -o 01_ANDROID_ANALYSIS/APKTOOL/rr3_14.0.1 <apk>` | APKTOOL/ (no, regenerable) |
| Java decompilation | `jadx -d 01_ANDROID_ANALYSIS/JADX/rr3_14.0.1 -j 16 --show-bad-code <apk>` | JADX/ (no) |
| DEX census | `python -I SCRIPTS/dex_census.py <apk> 01_ANDROID_ANALYSIS/DEX_CENSUS` | yes |
| Manifest report | `python -I SCRIPTS/manifest_report.py <APKTOOL manifest> 01_ANDROID_ANALYSIS/MANIFEST` | yes |
| Native lib copies | Extracted from the APK zip and checked with `sha256sum -c LIBRARIES.sha256`; files set read-only | LIBRARIES/ (no; `.sha256` stays local) |
| Symbol harvest | `python -I SCRIPTS/native_symbols.py 02_NATIVE_ENGINE/LIBRARIES 02_NATIVE_ENGINE/SYMBOLS <llvm-cxxfilt>` | yes |
| RTTI groups | `python -I SCRIPTS/rtti_groups.py <rtti_types.tsv> <RTTI_GROUPS.md>` | yes |
| Source-path layout | `python -I SCRIPTS/source_paths.py <strings.tsv> <SOURCE dir>` | yes |
| JNI map | `python -I SCRIPTS/jni_map.py .` | yes |
| Source attribution | `RETR0_SourceAttribution.java` and `RETR0_ExportFunctions.java`, then `python -I SCRIPTS/source_attribution_summary.py`, `source_attribution_expand.py` and `source_xabi_map.py` | `02_NATIVE_ENGINE/ANALYSIS/{SOURCE_ATTRIBUTION,FUNCTIONS}` (yes) |
| Vtable recovery | `python -I SCRIPTS/vtable_recovery.py <lib.so> <rtti_types.tsv> <strings.tsv> <expanded.tsv> <out>` | `02_NATIVE_ENGINE/ANALYSIS/VTABLES` (yes) |
| Call-tree annotation | `python -I SCRIPTS/annotate_calltree.py <tree_dir> <expanded.tsv> [depth]` | `ANALYSIS/{STARTUP,GAME_SCENE,PHYSICS}` (yes) |
| Save container check | `python -I SCRIPTS/save_format_check.py <arm64 libRealRacing3.so> <file.dat>…` (read-only; reads the key from the given library at run time, prints no key or content) | stdout only |
| Save structure decode | `python -I SCRIPTS/save_decode.py <arm64 libRealRacing3.so> <file.dat>… [--names N]` (read-only; structure and key names only unless `--values`) | stdout only |
| Reconstruction tests | `.venv\Scripts\python.exe -m pytest 08_TESTING -q` | stdout |
| Constructor constants | `python -I SCRIPTS/find_vtable_ctors.py <lib.so> <vtables.tsv> <class-regex> <lo> <hi> [window]` (capstone; finds code loading a class vtable, resolves `ldr d0` constants) | stdout |
| Direct sub-sync audit | capstone scan → `RETR0_DecompileContaining.java` (headless `-readOnly`) → `python -I SCRIPTS/subsync_disasm_layout.py <so> <qsites.json>` → `python -I SCRIPTS/subsync_catalogue.py <qsites.json> <dir> <md> <tsv> <expanded.tsv>` | `NETWORK/arm64-v8a/direct_subsyncs/` |
| Function coverage | `RETR0_Coverage.java` (headless `-readOnly`) | log line `RETR0_COVERAGE` |
| **Function recovery (writes; working copy only)** | 1) back up `02_NATIVE_ENGINE/GHIDRA/arm64-v8a` to `BACKUPS/GHIDRA_arm64-v8a_before_function_recovery_<ts>` and verify by SHA-256 (list beside it). 2) copy to `02_NATIVE_ENGINE/GHIDRA/arm64-v8a_recovered`. 3) headless on the copy **without** `-readOnly`: `-postScript RETR0_RecoverFunctions.java libRealRacing3.so <out_dir> 4` | `02_NATIVE_ENGINE/ANALYSIS/FUNCTIONS/recovery/` (`recovered_functions.tsv`, `recovery_run.log`) |
| **armv7 never-disassembled code (writes; working copy only)** | after the backup + copy steps, run headless on `armeabi-v7a_recovered` without `-readOnly`: `RETR0_RecoverUndisassembled.java libRealRacing3.so <out> measure` (read-only report), then `... apply`, then `RETR0_RecoverFunctions.java` again | `02_NATIVE_ENGINE/ANALYSIS/FUNCTIONS/recovery_armv7/` |
| Gap classification / prologue recovery (armv7) | `RETR0_GapAnalysis.java <out> [failed.tsv]` (read-only), then on the working copy only: `RETR0_RecoverPrologues.java <out> 40` | `FUNCTIONS/recovery_armv7/gaps/`, `.../prologues/` |
| Sub-sync owner attribution (read-only) | `RETR0_CallerContext.java libRealRacing3.so <out> 5 40 @0x<sender> ...` on `arm64-v8a_recovered` with `-readOnly` | `NETWORK/arm64-v8a/direct_subsyncs/callers/`, `.../fields/` |
| Whole-library sub-sync queue scan (read-only) | `.venv\Scripts\python -I SCRIPTS\subsync_queue_scan.py <libRealRacing3.so> <out.tsv>` and `SCRIPTS\subsync_queue_residual.py` (same args); needs `lief`, `capstone` in `.venv` | `NETWORK/arm64-v8a/queue_scan/` |
| Local replacement service | `.venv\Scripts\python -I 06_RECONSTRUCTION\BACKEND\local_service\retr0_local_service.py --data-dir <dir>`; tests: `.venv\Scripts\python -m pytest -q 08_TESTING` | `06_RECONSTRUCTION/BACKEND/local_service/README.md` |
| Seed data reader | `.venv\Scripts\python -I SCRIPTS\seed_data_decode.py <CC_SeedData.bin> [--extract <new dir outside the repo>]` | listing only; extract outside the repo |
| Ghidra import + analysis | From PowerShell: ``& cmd.exe /c "`"<root>\SCRIPTS\ghidra_import.cmd`" <abi> <project>"`` | GHIDRA/ (no; large databases) |
| Ghidra read-only scripts | `analyzeHeadless <proj_dir> <proj> -process [<file>] -recursive -noanalysis -readOnly -scriptPath SCRIPTS\ghidra -postScript <Script>.java <args>` | ANALYSIS/ (yes) |

## Ghidra scripts (`SCRIPTS/ghidra/`, all read-only)

| Script | Purpose | Args |
|---|---|---|
| `RETR0_ProgramStats.java` | Function counts, default `FUN_` names, JNI export functions, `JNI_OnLoad` presence | none |
| `RETR0_XrefsTo.java` | References to given ELF virtual addresses (adds the image base) | `<program> <vaddr>...` |
| `RETR0_SourceAttribution.java` | Function → source file through xrefs to `\source\src\` path strings (scans every non-`.text` block, because `.rodata` sits in the R+X segment) | `<program> <out_tsv>` |
| `RETR0_ExportFunctions.java` | Full function list (entry, size, name, thunk, caller/callee counts) | `<program> <out_tsv>` |
| `RETR0_CallTree.java` | Breadth-first call trees from symbols or `@0xELF` addresses, with pseudocode to a depth. If a root has no function, it disassembles and creates one **in memory only** (always run with `-readOnly`) | `<program> <out> <maxDepth> <decompDepth> <maxNodes> <roots…>` |
| `RETR0_StringXrefs.java` | Functions referencing strings that match regexes (use `@file` for patterns, because `cmd.exe` mangles `^ | ( )`) | `<program> <out_tsv> <regex|@file>…` |
| `RETR0_ScalarUses.java` | Functions using given immediate/displacement constants (struct strides, field offsets) | `<program> <out_tsv> <hex>…` |
| `RETR0_JniEnvCalls.java` | Finds loads at a JNIEnv table offset (slot × pointer size) and decompiles the functions containing them | `<program> <out_dir> [Name:slot ...]` |

## Known gotchas

1. **The project path contains spaces.** Bash → `cmd` quoting breaks `.bat` arguments, so launch Ghidra from PowerShell through `cmd.exe /c` with the wrapper.
2. **Ghidra rejects path elements that start with `.`** (for example `SCRIPTS\..`). The wrapper normalises its root with `%%~fI`.
3. **`cmd.exe` splits arguments on `=`.** Ghidra script arguments therefore use `Name:value`.
4. **`Start-Job` dies with its PowerShell session.** Long runs must use a tracked background task.
5. **Ghidra image bases differ by ABI: arm64 `0x100000`, armv7 `0x10000`.** ELF virtual address = Ghidra address − image base. The scripts compute this from `getImageBase()`. Never convert by hand with a fixed base (this caused wrong armv7 addresses in `JNI_MAPPING.md` §3, since corrected).
6. **JNIEnv offset scans give false positives.** Structure fields at the same offset also match (3 of 9 `RegisterNatives` hits on arm64 were false). Small offsets such as `FindClass` = `0x30` match thousands of unrelated loads, so that scan was cancelled and its partial output deleted.
7. Python on Windows writes CRLF unless told otherwise, and `sha256sum -c` needs LF line endings.
8. `RETR0_StringXrefs.java` originally ended strings at `\n` and missed most `CC: …\n` log strings. Fixed 2026-11-14: tab/CR/LF are now accepted and escaped in the TSV. Earlier string-xref runs may have missed newline-terminated strings.
9. Some code regions are **not defined as functions** by Ghidra's auto-analysis (e.g. `0x1d02c60`–`0x1d03520`, where `SyncManager` queue and send code lives), so call trees and xrefs skip them. Use a capstone ADRP/ADD scan to find references in such regions.

## Native build tools (audit 2026-11-17)

Not used yet: no C/C++ code exists. Already installed and recorded in `BUILD_SYSTEM_AND_GRAPHICS_DEPENDENCIES.md`: CMake 3.22.1 + Ninja 1.10.2 (Android SDK), CMake 4.1.1 + Ninja 1.12.1 (VS 2026), MSVC 14.50 / 14.29, NDK 26.1 / 27.0 / 28.2, MSYS2 GCC 16.2.0. ANGLE and Emscripten deliberately not installed.
