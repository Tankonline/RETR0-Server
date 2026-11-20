# 03 · Tools and environment

## Analysis tools

| Tool | Version | Used for |
|---|---|---|
| JADX | 1.5.6 | Decompiling the DEX code to Java-like source (`jadx -d <out> -j 16 --show-bad-code <apk>`) |
| APKTool | 3.0.3 | Decoding the manifest and resources; baksmali/smali for the client's Java patch |
| Ghidra | 12.2 (Temurin JDK 25) | Native analysis of `libRealRacing3.so` (arm64 and armv7); headless scripts for bulk work |
| Python | 3.14 (venv, always run with `-I`) | All analysis scripts and the server; `lief`, `capstone` and `defusedxml` for analysis only |
| capstone | 5.0 | Disassembly checks: hook sites, branch targets, scanning code for address loads |
| Android NDK | 28.2.13676358 | `clang --target=aarch64-linux-android`, `ld.lld`, `llvm-objcopy`, `llvm-nm`, `llvm-cxxfilt` |
| Android build-tools | 36.0.0 | `zipalign`, `apksigner` |
| Frida | 17.27.0 | Java-level runtime hooks during research (recording and redirecting requests) |
| ADB | 36.0.2 | Emulator control, logcat, file transfer |
| MSYS2 zlib | `ucrt64` `zlib1.dll` | Classic zlib for byte-exact pack rebuilding (Python's zlib-ng gives different bytes) |

The server itself needs **only Python 3 with the standard library**.

## Ghidra working method

- Two kinds of Ghidra databases: the **original imports** (never written to) and **`*_recovered` working copies**
  for anything that writes (function recovery, boundary repair), each made after a verified backup.
- Read-only scripts run with `analyzeHeadless … -readOnly -postScript <Script>.java`. The project wrote its own
  scripts for statistics, cross-references, string and constant searches, call trees with pseudocode, source-file
  attribution, JNI-table calls, coverage and gap analysis.
- Ghidra used an image base of `0x100000`: a Ghidra label is the ELF address + `0x100000`.

## The test emulator

| Setting | Value |
|---|---|
| Image | Android 14 (API 34), Google APIs, **x86_64**, rooted (`su`) |
| AVD | 10 GB RAM, 32 GB data, host GPU, 6 cores |
| ARM code | Runs through Android's ARM translator (`libndk_translation`); the game installs as `arm64-v8a` |
| Network | Locked: all traffic blocked except loopback, replies, and DNS to a logging resolver on the PC that answers nothing |
| Server access | `adb reverse tcp:8780 tcp:8780` carries the emulator's `127.0.0.1:8780` to the PC |

Why x86_64: the Android emulator cannot run arm64 system images on an x86_64 host. A consequence is that Frida
cannot hook the game's native (translated) code, only its Java code, which is why every runtime hook in this project
is at the Java level.

Why locked: so that nothing the game does can reach EA or any other service while it is being studied. See
[research-tools/avd_network_lock.sh](../research-tools/avd_network_lock.sh).

## Hardware acceleration (Windows)

The emulator needs the Windows Hypervisor Platform. If another emulator (e.g. LDPlayer) turned it off, run as
administrator `bcdedit /set hypervisorlaunchtype auto` and restart; `emulator -accel-check` should then pass.
