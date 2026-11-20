# 04 · How the game was decompiled

"Decompiling" RR3 means two very different jobs: the **Java/Kotlin layer** (DEX bytecode, which decompiles back to
readable Java) and the **native engine** (`libRealRacing3.so`, stripped ARM machine code, which can only be
analysed). This chapter describes both, and the rules the project kept to.

## 1. Evidence first

1. The original APK is hashed and kept read-only. Every library and DEX file inside it is hashed too.
2. All work happens on copies. Outputs that can be regenerated (JADX/APKTool trees, Ghidra databases) are kept out
   of version control; scripts and results are kept in.
3. Every finding gets an ID, the evidence it rests on (address, string, log line, recording) and a confidence label.

## 2. The Java layer

| Step | How |
|---|---|
| Unpack | The APK is a zip: 6 DEX files, 28 native libraries (arm64-v8a and armeabi-v7a), `assets/`, resources |
| Decompile | `jadx -d <out> -j 16 --show-bad-code <apk>` → Java-like source for 42,335 classes |
| Resources | `apktool d <apk>` → readable `AndroidManifest.xml`, resources, and **smali** (an assembly form of DEX) |
| Census | A script counts classes per package and separates game/EA/Glu code (~950 classes) from SDKs |
| Boot path | Read from the decompiled launcher and `MainActivity`: unpack `res.zip`, then load Nimble → FMOD Ex → RealRacing3 |
| JNI map | Every `native` Java method matched to the exported `Java_*` symbol in the library (124 bindings) |

Key results for this project: CloudCell's native code sends **all** its HTTP through one Java class,
`com.firemonkeys.cloudcellapi.HttpRequest`, and the network security config allows plain HTTP only to `127.0.0.1`.
Both made a local server and a small Java patch possible.

JADX output is a reconstruction, not EA's original source, and it is not published.

## 3. The native engine

`libRealRacing3.so` holds the whole game engine (C++). It is **stripped**: apart from the 124 JNI exports there are
no function names. The method was:

### 3.1 Harvest what the binary still says about itself

- **RTTI:** C++ run-time type information gives ~5,100 class names (`FrontEnd2::…`, `cc::…`, `CarAi…`), demangled
  with `llvm-cxxfilt`, and points to each class's vtable.
- **Source paths:** 1,506 assert/log strings contain original paths such as
  `E:\dev\builds\r3_update_a\source\src\Racers\RacerManager.cpp:3382`. They name **506 source files in 81
  folders**. Every function that references such a string is attributed to that file (validated, then expanded to
  neighbouring functions with bracket checks): ~4,000 functions per ABI.
- **Log strings** such as `"CC: [%d] Sync response received"` or `"[Facebook] Name finalized by user"` tie functions
  to behaviour.
- **Third-party code:** version strings identify statically linked OpenSSL, libcurl, zlib, ImGui, Skia, JsonCpp and
  pugixml, so those functions can be set aside.

### 3.2 Ghidra

- Both ABIs imported and auto-analysed (arm64 41,165 functions, armv7 54,793 at first).
- **Function recovery** on working copies: arm64 coverage of `.text` went from 72.0% to **98.8%** (+48,056
  functions); armv7 from 79.8% to 90.7%, using relocated code pointers, prologue patterns and finally the
  `.ARM.exidx` / `.eh_frame` unwind tables to split merged functions.
- Bulk **pseudocode export** of every function to text files, grouped by source-file attribution or RTTI evidence, so
  that whole subsystems can be searched with ordinary tools (`grep`). This export is a private research aid only.

### 3.3 Tracing a feature

The same loop was used for every subsystem and feature in this repository:

1. **Find an anchor:** a log string, a UI text key (`GAMETEXT_…`), a UI layout file name, an RTTI class or a JNI call.
2. **Read the function** in pseudocode, then **check the disassembly** where details matter (calling conventions,
   exact instructions, constants).
3. **Follow callers and callees** (Ghidra cross-references, call-tree scripts, or scanning code for `adrp`/`add`
   pairs that load an address).
4. **Confirm at run time** on the emulator: logcat lines, recorded requests, or a temporary diagnostic build that logs
   a value (see [the RETR0 client](https://github.com/Tankonline/RETR0-Client/blob/main/docs/how-the-client-is-patched.md)).
5. **Write it down** with ID, evidence and confidence.

Example: the username feature started from the word "Guest" on screen. A diagnostic build proved it was *not* a text
lookup; the Profile screen's code led to the function `0x135e944`, and its disassembly showed it returns a string
through register `x8`. See [features/username.md](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/username.md).

### 3.4 Naming and confidence rules

- Functions keep neutral names (`FUN_…` or the address) unless strong evidence names them (an original source path,
  a log string, an RTTI vtable).
- No mass renaming by heuristics. Old and new names are recorded.
- arm64 and armv7 are analysed separately; addresses and layouts are never assumed to match.
- Confidence: **CONFIRMED** (direct, ideally independent evidence) · **HIGH** · **MEDIUM** · **LOW** · **UNKNOWN**.

## 4. Data formats

Formats were decoded from the code that reads them, then verified on real files without modifying them:

- **Saves** (`files/doc/*.2.dat`): XOR-obfuscated container, big-endian header, checksum; body = interned key
  dictionary + typed value tables. A clean-room decoder parses all save files byte-exactly.
  → [reference/SAVE_SYSTEM_ANALYSIS.md](reference/SAVE_SYSTEM_ANALYSIS.md)
- **Seed data** (`CC_SeedData.bin`): an archive of five boxed blobs (config, texts, store catalogue, achievements,
  web manifest). → [reference/NETWORKING_ANALYSIS.md](reference/NETWORKING_ANALYSIS.md) NW-88..NW-92
- **Game data:** `.z` (zlib), `.nct` and several other types (RC4-drop[133]), textures, models.
  → [reference/ASSET_FORMAT_INVENTORY.md](reference/ASSET_FORMAT_INVENTORY.md)
- **Asset lists and packs** for downloads. → [09-asset-cdn.md](09-asset-cdn.md)

## 5. The network protocol

Decoded statically from the CloudCell code (`src\Cloudcell\CloudcellApi\…`), then confirmed against real requests
recorded on the locked emulator. → [06-network-protocol.md](06-network-protocol.md)
