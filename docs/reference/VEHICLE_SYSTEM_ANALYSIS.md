# Vehicle System Analysis

Last updated: 2026-11-18 · Status: **`.nct` data-file encryption solved and verified on all game files; suspension-data record layout read from the loader; wheel-radius fields identified. Car-appearance file fully parsed; `CarDesc+0x670` identified as the appearance record (wheel radii confirmed against real cars). Other per-file layouts not yet done.**
Addresses are arm64 ELF virtual addresses unless marked. Physics use of these data: `PHYSICS_ANALYSIS.md`.

## 1. The `.nct` data files

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| VH-01 | The installed game data holds **1,336 `.nct` files** under `files/.depot/`: 1,137 in `vehicles/data` (572 livery files, 565 others: one `<id>_<year>_<make_model>.bin.nct` per car plus shared tables such as `car.gearbox.nct`, `custom.tyres.nct`, `custom.wheels.nct`, `suspensionbehaviour.suspensiondata.nct`, `cardesc.list.nct`), 168 in `Tracks/data`, 31 in `data` | Directory listing of the owner's install | CONFIRMED |
| VH-02 | **Every `.nct` file is RC4-encrypted** with an 8-byte key, and the first **133 keystream bytes are discarded** (RC4-drop[133]). The file loader `0x12bc330` runs the RC4 key schedule (`j += S[i] + key[i & 7]`), then 133 PRGA steps without output, then XORs the file with the keystream. The key is a `.rodata` table at ELF `0x49c8f8` (Ghidra `0x59c8f8`). **The key is not written in this repository**; `SCRIPTS/nct_decode.py` reads it from the user's own `libRealRacing3.so` at run time | Pseudocode of `0x12bc330`; decoding all files | CONFIRMED |
| VH-03 | Verification: decoding all 1,336 files with VH-02 lowers the byte entropy of **1,335** of them by more than 1 bit/byte (encrypted ≈ 8 bits/byte), and decoded files show the expected structure (u32 counts, IEEE floats, length-prefixed `GAMETEXT_*` strings) | `nct_decode.py --check` (prints counts only) | CONFIRMED |
| VH-04 | The exception, `vehicles/data/carrepairs.repairs.nct` (6,418 bytes), has 12 bytes that look like a normal encrypted header, followed only by spaces and carriage returns (`20 0d` / `0d 20`). In this install the file appears **damaged or blanked**; whether the game then fails to load repair data, or falls back to defaults, is UNKNOWN | Hex dump | CONFIRMED (content); cause UNKNOWN |
| VH-05 | The same loader `0x12bc330` is called by the car-data loaders `0xc58be4` (per-category suffix scan: `.appearances`, `.wheels`, `.wheelpacks`, `.tyres`, `.tyrepacks`, `.suspension`, `.paints`, `.paintpacks`, `.decals`, `.decalpacks`, `.colours`, `.suspensiondata`, `.brakes`), `0xc5954c` (`custom.*`), `0xc5acb0` (suspension data) and `0xc5b164` (`car.brakes.nct`); `CarDataManager::load…` error strings sit next to them | String xrefs `PHYSICS/arm64-v8a_physics_string_xrefs.tsv`; pseudocode | CONFIRMED |

Decoded data is proprietary game content. It is written only under `03_ASSET_EXTRACTION/` (gitignored), never committed, and never written back into the game folder.

## 2. Suspension data (`suspensionbehaviour.suspensiondata.nct`)

Loader `0xc5acb0` → record reader `0xc5e904`; a second pass `0xc5ed88` applies further `*.suspensiondata.nct` files by record id.

```
u32 version            (read and discarded; = 1 in this install)
u32 count              -> table+0x138   (= 540 in this install)
count x {
    u32 id             -> entry+0x00            entries are 0xa0 bytes, array at table+0x140
    34 x u32           -> 0xc5e904(reader, entry+8): fields entry+0x10..+0x98 in file order, skipping
                          entry+0x2c; the last nine are: /100, x0.001 (4), x0.01 (2), then 2 raw ints
}
```

Size check (CONFIRMED): 8 + 540 × (4 + 34 × 4) = 75,608 bytes = the file's size.

All fields are stored as 4-byte integers, but some hold IEEE floats (record 0 has 0.2, 1.25, 1.3, 2.1). Field meanings are UNKNOWN except where the code reads them.

## 3. Wheel radius (answers OPEN_QUESTIONS Q22)

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| VH-06 | The object at `CarDesc+0x670` holds the **front wheel radius at `+0x24` and the rear wheel radius at `+0x34`** (floats, metres if PH-42's SI reading holds). Three independent uses agree: the world-step phase B `0xc28338` and the car-render code `0x10977a0` set wheel angular speed to `(speed/256) / radius` (the alternative branch in `0x10977a0` uses revolutions/s × 2π); the getter `0xc67390` returns `2·radius − x` per axle (a diameter minus a second value) | Pseudocode of all three | HIGH |
| VH-07 | **Correction to PHYSICS_ANALYSIS PH-32 / PH-40:** they called these fields suspension travel and attributed the object to `*.suspensiondata.nct`. The travel check `ground_gap ≤ 1.1 × r` and the displacement `car_z + mount − ground + r − ride_height` read naturally as wheel radius. The source file is now known: **`carappearances.appearances.nct`** (VH-08..VH-11). The earlier search missed the writer because Ghidra shows it as `int* + 0x19c` | VH-08 | CONFIRMED (correction and source) |

## 4. Car appearance data (`carappearances.appearances.nct`)

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| VH-08 | `0xc58be4` is **`CarDataManager::reloadCarData(const std::string&, std::vector<std::string>&)`**: each per-suffix handler is a `std::function` whose `target()` (e.g. `0xc61118`) compares against the mangled lambda type `ZN14CarDataManager13reloadCarData…E3$_0` (`$_0` = `.appearances.nct`, `$_1` = `.wheels.nct`, …). The `.appearances` lambda's call operator `0xc6110c` calls the file handler `0xc5c1f4` | Relocated `std::function` vtables at Ghidra `0x1f576f0` / `0x1f57770` (slots: …, call `0xd6110c`, `target` `0xd61118`); pseudocode | CONFIRMED |
| VH-09 | **`0xc60e84` links each `CarDesc` to its data records:** `+0x670` = appearance record whose id equals the int at `CarDesc+0x13c`; `+0x678` = record (stride 0x74) matched on the car id `CarDesc+0x00`; `+0x680` = suspension-data entry + 8 (the 0xa0-stride table at manager `+0x140`, §2) matched on the car id; `+0x5d0` = record (stride 0x20) matched on the car id | Pseudocode of `0xc60e84` (stores via `int*` offsets 0x19c, 0x19e, 0x1a0, 0x174) | CONFIRMED |
| VH-10 | **Appearance file layout (version 0x17):** `u32 version, u32 count (540)`, then per record `u32 id` + reader `0xc5dbb8` (record in memory 0x1a8 bytes; lookup by id `0xc5cb10`, by index `0xc5cd80`): string name → `+0x08` (the model folder: `0x155e64c` loads `vehicles/<name>`); 10 × f32 → `+0x20..+0x44`; 2 bools → `+0x144/+0x145`; 9 × f32 → `+0x48..+0x68`; string → `+0x70`; u32 n + n strings → vector `+0x148`; 2 × f32 → `+0x88/+0x8c`; u32 flag → `+0x90`, then 8 × f32 → `+0x94..+0xb0` only if set (defaults otherwise); 4 strings → `+0xb8/+0xd0/+0xe8/+0x100`; u32 → bool `+0x118`; two colours (3 × u8 + f32, stored as `f32·u8/255`) → `+0x11c..+0x124`, `+0x12c..+0x134`; 2 × f32 → `+0x13c/+0x140`; 5 × f32 → `+0x190..+0x1a0`. Strings are `u32 length + bytes` (≤ 0x800, `Reader.cpp`). **Size check: parsing all 540 records ends exactly at byte 162,235 = file size** (`SCRIPTS/appearance_read.py`) | Pseudocode of `0xc5c1f4`, `0xc5dbb8`, `0x1375978`, `0x1375be8`; full parse | CONFIRMED |
| VH-11 | **Wheel radii are metres and match real cars.** `+0x24` front / `+0x34` rear range 0.258–0.364 / 0.264–0.390 (medians 0.328 / 0.336). Examples: Bugatti Veyron SS 0.341 / 0.357 (real 265/35 R20 = 0.347, 365/30 R20 = 0.364); Ferrari F40 0.306 / 0.323 (real 245/40 R17 = 0.314, 335/35 R17 = 0.333); Porsche GT3 2010 0.340 / 0.340 (real ≈ 0.327 / 0.333). Agreement within about 2–4 % | Parsed data vs published tyre sizes | HIGH |
| VH-12 | Other `+0x20..+0x44` floats: `+0x20`/`+0x30` (e.g. 0.252 / 0.286 for the GT3, close to its 245 / 305 mm tyre widths, but the Veyron rear does not fit) and `+0x2c`/`+0x3c` are UNKNOWN; `+0x28`/`+0x38` are 0 for most cars | Parsed data | LOW (width guess); otherwise UNKNOWN |

## 5. Open items

- Record layouts of `car.gearbox.nct`, `custom.tyres.nct`, `custom.wheels.nct`, `car.brakes.nct` and the per-car `*.bin.nct` (CarDesc) files, each from its loader.
- ~~Find what sets `CarDesc+0x670`; cross-check the position scale~~ DONE (VH-09..VH-11; PH-42 updated).
- Meanings of the remaining appearance fields (VH-12) from their readers; records at `CarDesc+0x678` (stride 0x74) and `+0x5d0` (stride 0x20): which files.
- 167 files start with the same u32 `0xf81a6789` ([likely] a format magic; not yet examined).
