# Asset Format Inventory

Last updated: 2026-11-18 · Status: **first full census of the game depot; container layer (encryption / compression / known standards) identified for every file type; inner layouts known only for `.nct` suspension data.** Answers audit task 19.

Source: the verified copy `00_ORIGINAL/GAME_DATA/com.ea.games.r3_row/files/.depot` (44,966 files, hash list `00_ORIGINAL/METADATA/GAME_DATA.sha256`). Addresses are arm64 ELF virtual addresses.

How to reproduce:
- `python -I SCRIPTS/asset_census.py <depot> --out 03_ASSET_EXTRACTION/_census/depot_census.tsv` (headers and counts only)
- `02_NATIVE_ENGINE/ANALYSIS/ASSETS/arm64-v8a_asset_string_xrefs.tsv` (functions that reference each file suffix; `RETR0_StringXrefs.java`, read-only, patterns in `asset_ext_patterns.txt`)
- the RC4 check in AF-02 reused `SCRIPTS/nct_decode.py` (`rc4_drop`, entropy test); it printed counts only

## 1. Container layer

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| AF-01 | **`.z` files are a u32 little-endian uncompressed size followed by one zlib stream.** All 22,936 `.etc.dds.z` / `.rgb.pvr.z` files have a zlib header at byte 4; 40 of each were fully inflated and the output length equalled the size field every time | `asset_census.py` | CONFIRMED |
| AF-02 | **The `.nct` cipher (VH-02: RC4, 8-byte key, drop 133) also protects other types:** `.gui` 2,383/2,383 (decodes to XML), `.plist` 41/41 (XML), `.feats` 42/42 (XML), `.rr_ai` 60/60, `.lights` 31/32 (the last is too small for the test), `.dat` 3/9, one `.html`, and the root files `economy.bin`, `economyf.bin`, `crew.bin`, `coll.bin`. Every other type tested (`.bin` elsewhere, `.pvs`, `.fmc`, `.spline`, `.banim`, `.evt`, `.points`, `.txt`, `.bak`, `.cc_cust`) is **not** RC4 with this key | Full-file entropy test plus decoded first bytes (XML `<?xm`, `<Sha`) | CONFIRMED |
| AF-03 | Inside the `.z` files: `.etc.dds.z` → a standard **DDS** file (`DDS `); `.rgb.pvr.z` and plain `.pvr` → a header starting with u32 `0x34` (52), the size of the **legacy PVR v2** header. The engine's texture-suffix check `0x11d02cc` recognises `.ptc.pvr[.z]`, `.atc.dds[.z]`, `.dxt.dds[.z]`, `.etc.dds[.z]`, `.rgb.pvr[.z]`, `.rgbm.pvr[.z]`, `.pvr[.z]`; this install only contains the ETC and RGB variants | Inflated first bytes; pseudocode of `0x11d02cc` | CONFIRMED (inner headers); full texture layouts: see the separate texture-converter project |
| AF-04 | **`.m3g` files all start with the 12-byte JSR-184 (Mobile 3D Graphics) file identifier.** The engine has an `m3g::` namespace (e.g. `m3g::ByteArrayInputStream`, `m3g::CompositingMode` RTTI). Whether the object sections follow JSR-184 exactly, or carry RR3-specific extensions, is not yet checked | Census (5,357/5,357); RTTI strings | CONFIRMED (identifier); body format UNKNOWN |
| AF-05 | The 30 `.txt` files in the depot root include the localisation tables (`text_<lang>.txt`, `gametext.txt`) and `asset_list_base.txtCache.txt` (12 MB). 16 are plain text; the others (first bytes `86 5f ed ..`) are **encoded some other way** (not the `.nct` RC4) | Census; RC4 test negative | CONFIRMED (not plain, not this RC4); encoding UNKNOWN |

## 2. Per-type inventory

Sizes are from the census. "Loader" lists functions that reference the suffix string; it is a starting point, not a traced loader.

| Type | Files | Size | Where | Container | Loader lead (arm64 ELF) | Status |
|---|---|---|---|---|---|---|
| `.m3g` meshes / scenes | 5,357 | 4.42 GB | vehicles (5,137), Tracks, driver | JSR-184 identifier | `0x155e64c` (from `CarAppearance.cpp`; builds `vehicles/` + name from `*(CarDesc+0x670)+8`), `0x14d3314` (`cutscene_objects.m3g`) | Not started |
| `.rgb.pvr.z` textures | 4,622 | 2.76 GB | gui_assets, customisation, Tracks | AF-01 + PVR v2 | `0x11d02cc`, `0x11d05d8`, `0x11d097c` | Handled in the external texture converter |
| `.etc.dds.z` textures | 18,314 | 1.61 GB | Tracks, gui_assets | AF-01 + DDS (ETC) | same | Handled in the external texture converter |
| `.bin` | 1,618 | 679 MB | vehicles 924 (`ff ff ff ff`), Shaders/bin 522 (`61 8f 00 00`), Tracks 138 (`fe fe fe fe`), root tables | plain, except the four RC4 root files in AF-02 | various | Not started (`CC_SeedData.bin` already read, see SAVE_SYSTEM_ANALYSIS) |
| `.pvs` (track visibility, by name) | 61 | 171 MB | Tracks | plain, magic `a1 c1 f1 0f` (60/61) | no direct suffix string (name built at run time) | Not started |
| `.wav` | 648 | 129 MB | audio/sfx, audio/Vehicles | standard RIFF/WAVE | `.sounddef` loader `0xc0d318` | Playable as-is; game wiring not traced |
| `.txt` | 30 | 58 MB | root, scripts | see AF-05 | — | Not started |
| `.fmc` | 62 | 39 MB | Tracks (one per track layout) | plain, u32 `3` (52/62) | no direct suffix string | Not started |
| `.atlas` sprite atlases | 4,391 | 33 MB | gui_assets, Tracks | plain XML (`<atl…`) | `0xbf7d40` (`sprites.atlas`, `.android.atlas`) | Readable as text; not documented |
| `.mp3` music | 17 | 33 MB | audio/music | standard MPEG audio | — | Playable as-is |
| `.banim` animations | 496 | 32 MB | Tracks, driver, Menu | plain; first bytes `0x/1x 7f 7f 7f` | `0x1561060` (`driver/driver.banim`), `0x104ba54` (tutorial cut-scenes), `0xc54898` (`_wing.banim`) | Not started |
| `.gui` UI layouts | 2,383 | 25 MB | gui/processed | RC4 (AF-02) → XML | `0x10ba138` | Decodable; layout schema not documented |
| `.nct` car/track tables | 1,336 | 24 MB | vehicles/data, Tracks/data, data | RC4 (VH-02) | `0x12bc330` and the car-data loaders (VH-05) | Decodable; suspension layout known (VEHICLE_SYSTEM_ANALYSIS §2) |
| `.dds` | 20 | 21 MB | Tracks | standard DDS | — | Readable with standard tools |
| `.png` / `.jpg` / `.gif` / `.svg` | 243 | 17 MB | CC_Data, sponsorship, vector_images, webimage_cache | standard | — | Readable as-is |
| `.rr_ai` AI racing data | 60 | 11 MB | Tracks (one per layout) | RC4 (AF-02); decoded u32 `6` (60/60, likely a version) | `0x141d774` (track loader; adds `/processed`) | Decodable; layout not started |
| `.decomp` | 722 | 2.9 MB | audio/Vehicles | plain text (`v8_0…`, `v12_…`) | `0xc02ff8` (`%s.decomp`) | Readable; meaning not traced |
| `.spline` track splines | 60 | 2.3 MB | Tracks | plain, `ff ff 0a 00` (60/60) | no direct suffix string | Not started |
| `.pvr` | 93 | 2.3 MB | vehicles/shaders, hud | PVR v2 | `%s.pvr` `0x12bdbf8`; shadows `0xc96554` | External texture converter |
| `.points` | 958 | 0.7 MB | vehicles, vehicles/wheels | plain, starts `02 00 xx 00` | `0x1561060` (`.points`, `_int.points`) | Not started |
| `.evt` | 274 | 0.6 MB | gamemodes | plain | (the `#csdk.*.evt` strings are SDK event names, not these files) | Not started |
| `.lights` | 32 | 0.4 MB | Tracks | RC4 (AF-02); decoded u32 `1` | no direct suffix string | Decodable; layout not started |
| `.feats` shader features | 42 | 0.4 MB | feats | RC4 → XML | `0x11caea0` ("Loading shader features file") | Decodable |
| `.plist` | 41 | 0.3 MB | eds | RC4 → XML | `0x13c9ffc` | Decodable |
| `.dashplanes` / `.hudplanes` | 357 | 0.1 MB | vehicles, root | plain, u32 `4`/`5` | `0x1561060`, `0xc9bb3c`, `0xf682a0` | Not started |
| `.sounddef` / `.mlr` / `.mix` / `.dsp` | 344 | 0.08 MB | audio/sfx | plain, u32 `3` (sounddef) | `0xc0d318`, `0xc0c468`, `0xc0bc14` (`ramps.mlr`), `0xc14324` (`listener.mix/.dsp`) | Not started |
| `.vsh` / `.fsh` / `.xsh` shaders | 103 | 0.08 MB | Shaders | not plain text; bytes 2–3 are `31 42` ("1B") in every file, bytes 0–1 vary (an encoding or hash, UNKNOWN) | `0x148aa80` (`2dflat`), `0x11ccd04` (`car_low.vsh`), `0x144b718` | Not started |
| `.trackdata` | 11 | 0.02 MB | Tracks | plain, u32 `1` | `0x141f6c0` | Not started |
| fonts `.otf` / `.ttf`, `.mp4`, `.html`, `.js`, `.css`, `.json`, `.xml` | 108 | 9.5 MB | root, help, CC_Data | standard | — | Readable as-is |

## 3. Files that are not game content

| Files | Why it matters |
|---|---|
| `character.2.dat.bak`, `prof.dat`, `prof_sim.dat`, `ctd.dat`, `UDSF.2.dat(.bak)`, `whatsnew.dat`, `upgrades.dat`, and every `*.2.dat.bak` (`gs`, `loadout`, `nrc.bin`, `player_profile`, `replayCache`, `sv`, `ttss`) (depot root) | Player save, profile and state files, not shipped data. **Correction 2026-11-18:** `0.dat` and `18.dat` are NOT saves: they are u32-count + u16 lookup tables (1024 / 512 entries) loaded by number through the engine's `%d.dat` path; the game crashes (null dereference) when `18.dat` is missing (RUNTIME_TEST_PLAN §9, run 1). Treat as user data: do not decode or commit them; work on copies only (see SAVE_SYSTEM_ANALYSIS) |
| `customisation/friends/*.cc_cust`, `*.bak`, `*.meta` (≈ 560 files) | Liveries downloaded from **other players** (`/customisation/friends/%d_%03d.cc_cust`, loaders `0x1353138`, `0xb0d13c`; OMP variant `0xce8540`). Possibly third-party personal content: do not publish or decode beyond format work |
| `webimage_cache/*.jpg` | Cached web images |

## 4. Open items, in suggested order

1. **`.m3g`**: parse the section/object table of one car file and compare it with the JSR-184 object types; then check what `m3g::` code does differently. Biggest asset class (4.4 GB).
2. **Track set** (`.spline`, `.rr_ai`, `.trackdata`, `.lights`, `.pvs`, `.fmc`): one file of each per layout. Trace the track loader `0x141d774` → `0x151a3ec` (Ghidra address) to see how the names are built and which reader each file goes to.
3. ~~**`CarDesc+0x670`**~~ DONE 2026-11-18, CONFIRMED (VEHICLE_SYSTEM_ANALYSIS VH-08..VH-11; appearance file fully parsed by `SCRIPTS/appearance_read.py`): `0x155e64c` reads a model name at `*(CarDesc+0x670)+8`, so the object at `+0x670` is very likely the car's **appearance** record (MEDIUM). This links VH-06/VH-07: the wheel radii would then come from the `.appearances` `.nct` data. Check the `.appearances` reader.
4. `.gui` / `.atlas` / `.feats` schemas (all XML once decoded): document the element names from the reader code, not from the files alone.
5. `.txt` encoding (AF-05), `.banim`, `.points`, `.dashplanes`, shaders, audio definitions.

Decoded or converted output goes only under `03_ASSET_EXTRACTION/` (gitignored, Markdown excepted).
