# Complete C++ reconstruction - progress tracker

Generated 2026-11-18 00:39 at commit `8651124` by `SCRIPTS/reconstruction_progress.py`. Regenerate after every milestone.

**Rule:** these columns are different things and are never added together. Pseudocode is Ghidra output, not source. Reconstructed C++ is RETR0's own code, traceable to addresses in `06_RECONSTRUCTION/METADATA/reconstructed_functions.tsv`.

## libRealRacing3.so

| Stage | arm64-v8a | armeabi-v7a |
|---|---|---|
| Discovered (functions in Ghidra after recovery) | 91,020 | 87,882 |
| Eligible (non-thunk, non-external) | 83,072 | 81,131 |
| Decompiled + exported OK | 83,066 | 81,115 |
| Decompiler failed | 6 | 17 |
| Not yet processed | 0 | 0 |
| Attributed to an original source file | 4,012 | 4,199 |
| Understood (behaviour documented, approx.) | 328 | not counted |
| Reconstructed in C++ | 18 | 0 |
| Compiled | 18 | 0 |
| Validated by tests (vs. RETR0 Python codec / pseudocode) | 18 | 0 |
| Validated against the running original client | 0 | 0 |

## Reconstructed C++ components

| Component | Functions | Compiled | Tests | Runtime-validated |
|---|---|---|---|---|
| online/cloudcell | 10 | yes (MSYS2 g++ 16.2 (+ zlib 1.3.2); MSVC 14.50 /W4 (no zlib)) | cloudcell:gcc+zlib 47/47, cloudcell:msvc-nozlib 38/38 | no |
| save | 4 | yes (MSYS2 g++ 16.2 (+ zlib 1.3.2); MSVC 14.50 /W4 (no zlib)) | save:gcc 36/36, save:msvc 36/36, save:real-files-byte-identical 9/9 | no |
| sim | 4 | yes (MSYS2 g++ 16.2 (+ zlib 1.3.2); MSVC 14.50 /W4 (no zlib)) | sim:gcc 65/65, sim:msvc 65/65 | no |

## Java

JADX: 17,770 top-level classes, ~166,674 methods, 147 files with failed methods (third-party except one). Java is decompiled, not reconstructed; no Java reconstruction is planned beyond the JNI boundary.

## Structures

RTTI types: arm64-v8a 5,061, armeabi-v7a 5,130; vtables: arm64-v8a 3,813, armeabi-v7a 3,926. Layouts reconstructed in C++: cc::BinaryBlob (24 bytes, arm64), car body position/remainder/velocity fields (partial, arm64).

## Next

Priority order (owner's mission): core loop -> rendering -> vehicles -> physics -> tracks -> race -> AI -> collision -> frontend -> career -> economy -> audio -> input/camera -> saves -> online.
Next candidates by evidence strength: tyre model A + surface friction table (0x158d098); world step 0xb15684 phase order (needs its callees first); save container reader (SV-*).

Export audit detail: `06_RECONSTRUCTION/RECOVERED_PSEUDOCODE/export_reports/SUMMARY.md`.
