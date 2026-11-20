# Native Function Catalogue — libRealRacing3

Last updated: 2026-11-14 · Covers roadmap B-01 and B-01b.

Ghidra function names are **unchanged** (`FUN_<addr>`). This catalogue attributes functions to **original source files** and does not give them descriptive names. Addresses are ELF virtual addresses (Ghidra = ELF + image base: arm64 `0x100000`, armv7 `0x10000`).

## 1. Data files

| File | Content |
|---|---|
| `02_NATIVE_ENGINE/ANALYSIS/FUNCTIONS/<abi>_libRealRacing3_functions.tsv` | Every function: entry, size, Ghidra name, name source, thunk flag, caller/callee counts (arm64 41,165; armv7 54,793) |
| `…/SOURCE_ATTRIBUTION/<abi>_function_sources.tsv` | Raw xrefs: function → source-path string (file, assert line) |
| `…/SOURCE_ATTRIBUTION/<abi>_function_map.tsv` | One row per directly attributed function: primary file, confidence, all files referenced, assert lines |
| `…/SOURCE_ATTRIBUTION/<abi>_expanded.tsv` | Seeds plus bracketed functions (B-01b) |
| `…/SOURCE_ATTRIBUTION/<abi>_FUNCTION_SOURCE_MAP.md`, `<abi>_EXPANSION.md` | Human-readable summaries |
| `…/SOURCE_ATTRIBUTION/CROSS_ABI_FILE_MAP.{tsv,md}` | Per-file address ranges on both ABIs |

## 2. Method and confidence

| Tier | Rule | Label | Count arm64 | Count armv7 |
|---|---|---|---|---|
| Seed | The function references an embedded `…\source\src\<file>:<line>` string of exactly **one** file | CONFIRMED | 1,133 | 1,385 |
| Multi-file seed | The function references several files (inlining or shared helpers) | MEDIUM | 11 | 14 |
| Bracketed | A non-thunk function strictly between two consecutive seeds of the same `.cpp`, at most `0x40000` bytes apart | HIGH (validated, §3) | 2,956 | 3,035 |
| **Total attributed** | | | **4,012 (9.7%)** | **4,199 (7.7%)** |

Header (`.h`) seeds stay CONFIRMED as "references this header", but they are **not** used to model compilation units or for bracketing. Header asserts are inlined into many `.cpp` files: on the first run, the seeds of `BinaryBlob.h`, `FrontEnd2.h` and `SerialiserEnumHandler.h` spanned 10–18 MB with 900–1,200 foreign seeds inside. They were excluded on that evidence.

## 3. Validation (from the `_EXPANSION.md` reports)

| Check | arm64 | armv7 |
|---|---|---|
| `.cpp` files with ≥2 seeds | 193 | 214 |
| …with no foreign seed inside their address span | **193 (100%)** | 212 (99.1%) |
| Leave-one-out: hide a seed, predict its file from its same-file neighbours | **481/481 (100%)** | 532/533 (99.8%) |
| Link order of the 362 files attributed on both ABIs (longest increasing subsequence) | 98.9% same order | |
| Files with identical seed counts on both ABIs | 275 / 362 | |

**Conclusion (HIGH):** compilation units are laid out contiguously, and the link order is shared between the two ABIs. A function inside a file's bracket almost certainly comes from that file.

## 4. Coverage limits

- About 90% of functions are still unattributed. Most belong to files with no assert strings, statically linked third-party code (Skia, OpenSSL, curl, ImGui, JsonCpp, pugixml, libc++ templates) or the edges of file spans (before the first and after the last seed).
- Next possible extensions, in order of reliability:
  1. Fill gaps **between** different files using the shared link order (armv7 ↔ arm64 file sequence).
  2. Identify third-party code by matching library version strings and known function shapes.
  3. Assign RTTI and vtables (roadmap B-02), which maps virtual methods to classes.

## 4b. Virtual tables (B-02)

`SCRIPTS/vtable_recovery.py` rebuilds Itanium vtables from RTTI through ELF relocations (typeinfo-name string → typeinfo object → vtable `[offset_to_top][typeinfo][slots…]`). Output: `02_NATIVE_ENGINE/ANALYSIS/VTABLES/<abi>/{vtables,vtable_slots}.tsv`.

| | arm64 | armv7 |
|---|---|---|
| typeinfo names located | 5,061 | 5,130 |
| vtables (incl. secondary) | 3,813 | 3,926 |
| classes with a vtable | 3,136 | 3,208 |
| virtual slots | 67,618 | 70,808 |
| attributed slots that point into the class's same-named `.cpp` | 161/178 (90.4%) | 134/135 (99.3%) |

The remaining mismatches are inherited base-class implementations, as expected.

## 5. Anomalies

| ID | Item | Status |
|---|---|---|
| U-06 | armv7 `src\Character\PrizePackage.cpp` seeds span `0x85a074`–`0x96af74` (over 1 MB, with foreign seeds inside); the arm64 span is compact (`0x1091098`–`0x10945b0`) | Open. [H] A template or inline function defined in the `.cpp` was emitted in other compilation units on armv7. Bracketing is unaffected because the gap cap stops it |
| — | `GameSaveManager.cpp` is attributed on armv7 only (4+3); on arm64 its assert-referencing code was inlined into callers | Noted. Use the armv7 range `0x151d1bc`–`0x151e648` as the anchor |

## 6. Key subsystem anchors (both ABIs)

| Source file | arm64 range (functions) | armv7 range (functions) |
|---|---|---|
| `src\power\CarPerformance.cpp` | `0x12f4d54`–`0x12f4ef8` (3+10) | `0xb39c6c`–`0xb39dec` (3+10) |
| `src\power\LegacyCarPerformance.cpp` | `0x12fa240`–`0x12fc328` (4+12) | `0xb3def0`–`0xb3f938` (4+9) |
| `src\power\Power2CarPerformance.cpp` | `0x1309fd8` (1) | `0xb49cb0`–`0xb4a410` (3+1) |
| `src\power\TuningData.cpp` | `0x1316664`–`0x1317168` (7+6) | `0xb52d0c`–`0xb536b8` (8+6) |
| `src\CarDataManager.cpp` | `0xc5b3c0`–`0xc5e304` (6+37) | `0x63a460`–`0x63c654` (6+36) |
| `src\Save\SaveManager.cpp` | `0x13a1e20`–`0x13a50fc` (3+12) | `0xbbdafc`–`0xbc0178` (3+13) |
| `src\Save\FMUserData.cpp` | `0x15aeea0`–`0x15af42c` (5) | `0xd58938`–`0xd58dc4` (5) |
| `src\Cloudcell\CloudcellApi\GameSaveManager.cpp` | — | `0x151d1bc`–`0x151e648` (4+3) |
| `src\Character\Garage.cpp` | `0x153db50`–`0x154d8d0` (13+134) | `0xcfc944`–`0xd0800c` (13+127) |
| `src\Character\Character.cpp` | `0x152c1c8`–`0x1537ae8` (6+97) | `0xceeea8`–`0xcf7bdc` (6+94) |
| `src\frontend2\FrontEnd2.cpp` | `0x14a48ec`–`0x14a9f58` (12+43) | `0xc88ab0`–`0xc8c0ec` (11+84) |

The full table is in `CROSS_ABI_FILE_MAP.tsv`.
