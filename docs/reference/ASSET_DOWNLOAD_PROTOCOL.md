# Asset Download Protocol (CloudCell AssetManager)

Last updated: 2026-11-18 · Status: **CDN pack layout, range rules, per-file header, integrity check and stored-file format reconstructed and verified against recorded traffic and the owner's game data. The `assetManDownloadPackHash.php` reply format is not yet known.**

Addresses are arm64 ELF virtual addresses in `libRealRacing3.so` 14.0.1 (source file per assertion strings: `src\Cloudcell\CloudcellApi\AssetManager.cpp`). Runtime evidence: RUNTIME_TEST_PLAN §9 runs 3 and 4 (fresh install, network locked, nothing reached any server). Raw recordings: `08_TESTING/runtime/out/run3_fresh/`, `run4_record_fresh/` (gitignored).

## 1. Flow

1. First launch unpacks `res.zip` from the APK into `files/apk/` (asset lists included).
2. `StartListDownload` (`0x1cd5770`) loads a list (`res/asset_list_base.txt` first; the updates list is tried before it) through the parser `0x1cd3a54`, compares it with the local cache (`.depot/asset_list_base.txtCache.txt`) and queues what is missing.
3. The download step (`0x1cd691c`, vtable `cc::AssetManager`) groups queued entries into **requests** and sends them through Java `HttpRequest` (NW-01): CDN `GET` with `Range`, or CloudCell `POST //assetman/assetManDownloadPackHash.php`.
4. Received bytes are split per entry by `CallbackAssetServerData` (`0x1cd96fc` → `0x1cdbf08`), written to a temp file, MD5-checked and finalised (`0x1cdc7ac` → `FinaliseDownloadedAssetFile` `0x1cdd760`). Errors retry up to 8 times per file (`AssetDownloadError` `0x1cd8820`); after CDN failure the code can "revert to Cloudcell server".

## 2. Findings

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| AD-01 | **List line format:** `/path<TAB>md5<TAB>stored size<TAB>uncompressed size`; parser reads it with `fscanf("%511[^\t]\t%n%63[^\n]\n%n")` then `strtok("\t")` / `atoi` | `0x1cd3a54` | CONFIRMED |
| AD-02 | **CDN URL:** `https://firemonkeys.akamaized.net:443//rr3/live/<list name>/<md5 of the list file>.bin`; for this build `asset_list_base/10a2829c2abd31ec9a59da64ba0801d7.bin` = MD5 of `res/asset_list_base.txt` (LF line endings) | Recorded URL; MD5 of the list | CONFIRMED |
| AD-03 | **Pack layout:** the files of the list **in list order**, each as an **8-byte header + its stored bytes**; the parser keeps a running offset `off += stored + 8`, and sets entry `+0x20 = stored + 8`, `+0x24 = start`, `+0x28 = end (inclusive)`. Pack size for this list: 290,506,456 bytes | `0x1cd3a54` (lines with `local_3a8 = size + 8`); all 285 recorded ranges explained (AD-04) | CONFIRMED |
| AD-04 | **Range rules:** consecutive entries with the same pack and contiguous offsets are batched while the batch stays ≤ `0x7ffff` bytes → `Range: bytes=<first.start>-<last.end>` (134 recorded ranges, exact). A single entry larger than that is split into **N = ⌈(stored+8) / 524,288⌉ equal parts of ⌈(stored+8)/N⌉ bytes** (151 recorded ranges, e.g. `events.dat.nct` 28 × 516,483). Header `Accept-Encoding: identity` | `0x1cd5770`, `0x1cd691c` (`"bytes=%u-%u"`); recorded ranges | CONFIRMED |
| AD-05 | **Per-file header (8 bytes):** `u32 key` then `u32 length`. `key` must equal entry `+0x2c`; `length` becomes the byte count that is written, MD5-checked and finalised. Byte order little-endian [inferred from direct `int` reads on ARM64] | `0x1cdbf08` (8 bytes buffered at `+0x7c`, compared with entry `+0x2c`; `+0x80` → `+0x68`) | HIGH (LE not yet tested end-to-end) |
| AD-06 | **Key = djb2 hash of the path modulo `0x106d643d`:** `h = 5381; for each byte c (signed): h = h*33 + c (32-bit)`; `key = h % 0x106d643d` (empty path → 5381). Set by `0x1cd0c00`, which also parses the MD5 hex into four u32 at entry `+0x00..+0x0c` | `0x1cd0c00`; **1,129 of 1,129 distinct files in the recorded requests match** | CONFIRMED |
| AD-07 | **Integrity:** the MD5 of the received `length` bytes must equal the list MD5 (the MD5 of the *stored* form), else "didn't match its MD5, corrupt sync?" | `0x1cdc7ac` | CONFIRMED |
| AD-08 | **Stored form:** if a file starts with `FMASZ1`, the rest is a zlib stream inflated into the final file (`inflateInit "1.2.8"`); otherwise the bytes are the file. **The stored bytes are exactly `"FMASZ1" + compress(data)` with zlib's default settings (level 6, 15-bit window, default strategy)**, using classic zlib (Python 3.14's zlib-ng gives different bytes) | `0x1cdd760`; rebuilt from the owner's unpacked data: **445/445 compressed entries byte-identical (MD5)**, 117/118 uncompressed entries identical (1 differs in the copy), first 600 list entries | CONFIRMED |
| AD-09 | **`POST //assetman/assetManDownloadPackHash.php` request body:** `u32 w0`, `u32 1`, `u32 inflated size`, zlib stream of entries `u32 len + path`, `u32 32 + md5 hex`, `u32 key (AD-06)`. Built in `0x1cd691c` for the same batch as the CDN range. `w0` varies per request; not CRC-32/Adler-32 of the payload | Recorded bodies (2,530); `0x1cd691c` | CONFIRMED (layout); `w0` UNKNOWN |
| AD-10 | The reply to AD-09 is consumed by the same data path (AD-05) [inferred: same request object and callbacks], i.e. most likely the same `key + length + stored bytes` stream | Shared callbacks in `0x1cd691c` | MEDIUM |

## 3. Consequences for a replacement service

- A replacement CDN can be **rebuilt from the owner's own game data**: for each list, write `u32 key, u32 len, stored bytes` per entry in list order (AD-03/05/06/08), name it `<md5 of list>.bin`, and serve it with HTTP Range (already supported by `08_TESTING/runtime/recorder_server.py` rule `"dir"`). The MD5 check (AD-07) passes because the stored bytes are reproducible.
- Files missing from the owner's copy (37 of the first 600 entries: mostly excluded saves/caches) or changed in it (1 of 118 plain files) need handling: the client will retry and then report the error.
- Open: `w0` in AD-09, the reply format of `assetManDownloadPackHash.php` (AD-10), the updates list and per-track/per-car lists (same mechanism expected), and whether `/time` and `CC_Sync.php` answers gate the download.

## 4. Serving it (2026-11-18, RUNTIME_TEST_PLAN §9 runs 5–9)

- `SCRIPTS/asset_pack_build.py --list all` builds every pack from the owner's data (5.8 GB, 34,472 entries byte-exact, first matching source of several `--data` folders wins); the client accepted every served file that was present.
- **AD-11 (CONFIRMED):** `Platform.extractRes` re-extracts `files/apk/res.zip` into `files/apk/res/` at every launch, and recopies `res.zip` from the APK only when the file's length differs from the APK's raw resource. Edited lists therefore have to be inside a length-matched `res.zip` (`08_TESTING/runtime/make_edited_res_zip.py`); loose edits in `res/` are undone at the next start.
- With edited lists (`--drop-unavailable`, test devices only) the download runs without errors from the replacement CDN.
