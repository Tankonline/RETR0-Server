# Save System Analysis

Last updated: 2026-11-14 · Status: **location, container, obfuscation, checksum and the complete body encoding CONFIRMED; all 8 `doc/*.2.dat` files parse byte-exactly. Key schema mapped (names). Protected `[EHV]` values deliberately not decoded (§2b). Cloud-save path identified only.**

Addresses are arm64 ELF virtual addresses (Ghidra = ELF + `0x100000`). Evidence lives in `02_NATIVE_ENGINE/ANALYSIS/SAVE/`. Decompiler output is pseudocode, not EA source.

**Data handling:** save files were only **read**, in memory, from the separately held game-data copy (`<game>/files/`). Nothing was modified. The obfuscation key is **not** reproduced in this repository: tools read it at run time from the user's own `libRealRacing3.so`.

## 1. Location and files

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| SV-01 | Base directory is a Java-provided path obtained by `0x12b7ee0` through a JNI call on the activity. It matches `Platform.getExternalStorageDir` → `getExternalFilesDir(null)` = `/sdcard/Android/data/com.ea.games.r3_row/files` | `0x12b7ee0` pseudocode; the Java unpacker uses the same base plus `/apk/`; the game-data copy has the same layout | HIGH |
| SV-02 | Directory helpers append fixed suffixes: **`/doc/`** (`0x12a57f0`, save directory), **`/.depot/`** (`0x12a59a4`, backups and asset depot), `/apk/` (`0x12a5640`) | String xrefs of the helpers | CONFIRMED |
| SV-03 | **Save files** live in `files/doc/`: `character.2.dat` (main career/garage save; 639 KB in the sample), `player_profile.2.dat`, `gs.2.dat`, `loadout.2.dat`, `nrc.bin.2.dat`, `sv.2.dat`, `ttss.2.dat`, `replayCache.2.dat`, plus other formats (`friendsList.pld`, `mgrRacerSettings.bin`, `rmFDetails.bin`, `rres.bin`) and a `CC_Data/` folder. Code names `character`, `player_profile` / `profile` | Directory listing of the game-data copy; strings in `0x13a434c` / `0x13a50fc` | CONFIRMED |
| SV-04 | **Backups:** `files/.depot/<name>.2.dat.bak` (`"%s.bak"`); a temporary copy `"%s/%s.0"` is made before a load; a manual `CharacterBackup.dat` ("Backup Current Save Locally" / "Restore Previous Local Backup") exists in a debug menu (`0x13a5500`) | Loader `0x139dbb8` strings; `.depot` listing | CONFIRMED |
| SV-05 | The `.2.` infix is part of the name pattern `"%s/%s.%s"` (`0x139dbb8`); the name builder `0x139e52c` hard-codes it as `"%s.2.%s"` (NETWORKING NW-28). The same container is used for `customisation/*.2.cc_cust` car-customisation files received in garage responses (NW-27, NW-29) | Format strings | CONFIRMED (fixed literal, not a slot number); why `2` UNKNOWN |

## 2. Container format (FMUserData files)

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| SV-06 | **Obfuscation:** every byte on disk is `plain XOR key[i mod 64]`, where `key` is a fixed 64-byte constant (63 bytes + NUL) at `.rodata 0x52fa90`. It is applied in both directions by the `FileBuffer` I/O class (vtable `0x1eeb930`; write `0x15ab3a4`, read `0x15ab2c8`) | Pseudocode; validated on 9 files (SV-09) | CONFIRMED |
| SV-07 | **Header** (plaintext, **big-endian** u32s, written by `0x15abc6c` via `0x15aaab8`): `magic 0xABCFFCBA`, `version 5`, `total_size` (= file size), **`field_a` = number of key-dictionary entries**, **`field_b` = number of ints in the key dictionary** (singles + array pairs) | Pseudocode + byte-exact parse of 8 files (e.g. `character`: 925 entries; 665 + 38,995 = 39,660) | CONFIRMED |
| SV-08 | **Body** = key dictionary, root value table, child tables, trailer. Full encoding in §2b | Pseudocode + byte-exact parse | CONFIRMED |
| SV-09 | **Validation:** `SCRIPTS/save_format_check.py` decoded `character`, `gs`, `loadout`, `nrc.bin`, `player_profile`, `replayCache`, `sv`, `ttss` (`*.2.dat`) and `character.2.dat.bak`. All 9: magic OK, version 5, size field = file size, XOR checksum OK | Script output (2026-11-14) | CONFIRMED |
| SV-10 | **Write procedure** (`0x15aba78`): a dirty flag (`+0x240`) gates writing; it serialises once into a counting buffer to get the size (warns above 1 MiB, "getting dangerously large"), opens the file (`FileBuffer::openWrite`), serialises again and checks the written size equals the expected size | Pseudocode | CONFIRMED |
| SV-11 | Values are typed. Readers reject type mismatches (`FMUserData.cpp:1011` "Wrong type for value [%s] ... it's not a bool!"), invalid enum names ("Invalid enum name '%s' found in save data"), and corrupt garage cars ("Garage car was not properly serialised … removed from the player's garage") | Strings + xrefs (`0x15aeea0`, `0x1541014`) | CONFIRMED (behaviour); type tag encoding UNKNOWN |
| SV-12 | Serialisation framework: `SaveSystem::Serialiser`, `FMUserDataSerialiser`, `ToMemorySerialiser` / `FromMemorySerialiser`, with per-type callbacks `bool(Serialiser*, SaveSystem::SaveKey, T&)` (e.g. `CalendarDate`, `Character::DeviceHistory`, `RecPack*Offer`) | RTTI | CONFIRMED (types exist) |

## 2b. Body encoding (clean-room decoder `SCRIPTS/save_decode.py`)

Primitive types: **varint** = unsigned LEB128, 32-bit (`0x15aab14`); u16be (`0x15aaa58`); u32be (`0x15aaab8`); float = 4 raw little-endian bytes (`0x15aab94`); **flagged string** = characters followed by one flag byte 0/1, which also terminates the string (`0x15aabec`).

| Part | Encoding | Evidence |
|---|---|---|
| **Key dictionary** (`field_a` entries, `std::map<string, …>`) | `name` + flag. **Flag 0:** `varint id`. **Flag 1 (array):** `varint n`, then `n × (varint index+1, varint id)` | `0x15abc6c` |
| **Root value table** (`+0x250`) | `u32be n`, then n × `{u16be key (high bit = escape: low 15 bits, then a further u16be holding id>>15), u8 type, payload}` | `0x15b3a84` |
| Value types (type byte, low 3 bits = kind) | **0 bool:** `0x00`/`0x08` · **1 int:** `(v+1)·8+1` for −1 ≤ v ≤ 14, else `0x81` + varint · **2 float:** + 4 bytes · **3 string:** + chars + `0x00` · **4 varint:** + varint · **5 blob:** + u32be length + bytes | `0x15b3a84` |
| **Child tables** (`+0x268..0x270`, 24-byte vector elements) | `u32be count`, then count × value table (same encoding) | `0x15abc6c` |
| Trailer | XOR of all preceding plaintext bytes | `0x15ab3a4` |

| ID | Finding | Confidence |
|---|---|---|
| SV-18 | **Byte-exact parse:** all 8 `doc/*.2.dat` files (`character`, `gs`, `loadout`, `nrc.bin`, `player_profile`, `replayCache`, `sv`, `ttss`) parse to exactly the checksum byte with the encoding above | CONFIRMED |
| SV-19 | **Key interning:** in the flat file `player_profile`, the 50 names map to ids 0–49 and the root table has exactly those 50 keys, so the format is **name → id → typed value**. In hierarchical files, array ids mostly reference child-table indices (e.g. 19,290 of 38,995 in `character`) | CONFIRMED (flat); HIGH (hierarchical reference rules; the remaining id targets need the reader `0x15aa49c` to settle) |
| SV-20 | **Key names are C++ member paths** (`m_xp.m_totalEarned`, `saleManager.m_sales`, `timeManager.m_nTimeServerCached`), and arrays are written as `IDX:[id]…` (254 in `character`). `character` groups: `m_garage` (61 names), `m_CurrencyWallet` (55), `m_careerProgress` (21), `m_dailyRewards`, `m_driverPoints`, `m_raceStats`, `lts`, `m_xp`, `m_CarPerformance`, `m_money`, `m_goldenWrenches`, `UltimateDriver`, `m_Championships`, `saleManager`, `targetedSaleManager`, `sponsorCollection`, `raceTeamManager`, `m_MotorsportCrew`, `m_PowerPlayerState` … | CONFIRMED (names) |
| SV-21 | **`player_profile` = settings:** assists (`nSteeringAssist`, `tractionAssist`, `vnBrakePercent`), cameras (`cameraView`, `bBonnetCamHigh`), HUD (`bHudVisible`, `bShowMinimap`), units (`bKilometerUnits`), audio (`volume`, `musicVolume`), controls (`controlMethod`, sensitivities), `language`, marketing-consent flags, quick-race options | CONFIRMED (names) |
| SV-22 | **Protected values:** 82 `[EHV]` and 26 `[H]` names in `character`, mostly on currency and reward values (e.g. `…m_MDollarReward[EHV].nValue`, `…m_allTrophyBonusXP[EHV]` with matching `[H]`). This is consistent with an obfuscated value plus a hash (**tamper protection**). **Deliberately not decoded:** it is not needed to understand the structure, and decoding it mainly enables editing currency. Revisit only if a legitimate migration need requires it, with the owner's approval | CONFIRMED (presence); scheme UNKNOWN by choice |

| SV-23 | **Wide-key threshold:** the table writer escapes keys when `(int)key > 0x7ffe` (`0x15b3a84`), so key `0x7fff` is stored escaped (`0xffff` + `0x0000`); keys ≥ 0x80000000 would not be escaped (signed compare). Found because one value in `character` uses key 0x7fff | CONFIRMED |
| SV-24 | **C++ codec** `06_RECONSTRUCTION/SOURCE/save/UserDataFile.{h,cpp}` (clean-room, from the writer functions): parse → re-serialise is **byte-identical for all 9 real files** (8 `doc/*.2.dat` + `character.2.dat.bak`), every structure count equals `save_decode.py`, 0 non-canonical values; g++ 16.2 and MSVC 14.50. Checked read-only with `retr0_save_check` (key read from the user's library at run time; output = counts only) | CONFIRMED |
| SV-25 | **No player name in the local save (2026-11-19).** Field names of all 8 `doc/*.2.dat` files (structure only, `save_decode.py`, on copies) contain no player/user/display name. Identity fields are numeric: `m_nCCMemberId`, `nCCMemberId`, `nRTMemberId`, plus `m_bPlayerLoggedIntoSocialNetwork`, `m_bHasReceivedFacebookLoginGold` and the race team's `m_MetaData.m_teamInfo.strName`. The game's only name UI is in the Facebook sign-in (`0x1519c98` popup, `0x1519f34` handler → `FacebookManager::FinishLoggingIn` `0x1c7e53c`), which hands the name to CloudCell. Leaderboards take the player's display name from the social sign-ins (`cc::StatManager` `0x1cc93d0`), and other players' names come from server replies (e.g. `m_sCCMemberName` in ghost records). `doc/CC_Data/{6,8,12473}` (21-321 bytes) do not decode with the clean-room codec; contents UNKNOWN. App `shared_prefs` hold SDK settings only. **Implication:** a username must be kept by the server (e.g. set through promo-code sub-sync 10632) and appears only on server-fed screens | HIGH (no save field); CC_Data contents UNKNOWN |
| SV-26 | **Where the client shows a player name (2026-11-19).** (1) `FrontEnd2::ESportsMainMenu` label `LABEL_PLAYER_NAME` (`0xd9bf40`) reads the name from the platform-account object `DAT_0209c230` (getter wrapper `0xcfe908`, vtable slot +0xc0) with fallback "Player"; its `BTN_CHANGE_RACER_NAME` (`0xd9c924`) opens an "Enter Player Name" text box. The LAN lobby sends the name as `SET_PLAYER_NAME` (`0xbafca0`). The object is created only when `DAT_0209c238` (build/platform mode) is non-zero (`0xcfe12c` → `0xcfe28c`, types 1-7); in the normal mobile game the menu is not reachable (MEDIUM: mode value not observed at runtime). (2) Leaderboard and online names come from social sign-ins or the server (SV-25). (3) `GAMETEXT_PLAYER` at `0xb091d4`/`0xf10248` is the "Player N" split-screen label; `AICannotUsePlayerDriverName` (`0x135debc`) is a server variable about the driver model, not a name. **Implication:** a local name file is readable by a patch, but the normal game has no screen that shows the player's own name; a patch must also put it on a screen | HIGH (code); MEDIUM (mode) |
| SV-27 | **The "Guest" name and the RETR0 username (2026-11-20).** The player name on Profile (`ProfileMenu` `0x10a5570`; title label set by `0x10d5f38`) and in the race results comes from `0x135e944`. It returns a `std::string` **by value (result address in x8)**: first from the platform-account object (`0xcfe908`, empty on phones), then from CloudCell `MemberManager` (vt+0x80 member, vt+0x30 name), which yields "Guest" without a social sign-in. `MemberManager` keeps its member record in `doc/CC_Data/6` (`0x1cac2c4`: magic `0xd904`, versioned length-prefixed strings; per-sign-in-type blocks of 0x60 bytes from member+0x20, active type at +0x580). Not from the text table (diagnostic run 26: no lookup returned "Guest"); the static "Guest" string at `0x1f9c198` is a link-scheme prefix, not the name (run 27). **RETR0 client:** `name_entry` hooks `0x135e944`, runs it, and replaces the result with `doc/retr0_username.txt` (read once per start); `promo_entry` hooks `0x1516b1c` and writes the typed racing code (minus a leading "NAME ") to that file. The file is separate from the encoded saves | Disassembly of `0x135e944` and its Profile call site `0x10a5708`; runs 26-29 | CONFIRMED (Profile); race results owner-confirmed |

## 3. SaveManager behaviour

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| SV-13 | `SaveManager` must be updated, and saves loaded, **only on the main thread** (asserts at `SaveManager.cpp:387/699/912`) | Strings in `0x13a1e20`, `0x13a434c`, `0x13a50fc` | CONFIRMED |
| SV-14 | `SaveManager` publishes `SaveActionEventType` events. Subscribers include `UserValidationManager`, `MTXManager`, `Championships::ChampionshipData`, `UltraDrive::UltimateDriverManager`, `Lts::LtsDataContainer`, `Characters::OfferwallGiftUserData` | RTTI of `std::function`/bind instantiations | CONFIRMED (subscribers); event values UNKNOWN |
| SV-15 | Load failure shows `GAMETEXT_SAVE_GAME_ERROR_MESSAGE` ("Unable to load save"). The loader falls back to the temporary copy or the `.bak` ("Temporary Backup Loaded", "Cached Backup Loaded") | `0x13a434c`, `0x139dbb8` | CONFIRMED (strings, flow); exact order MEDIUM |

## 4. Cloud save (discontinued service)

| ID | Finding | Confidence |
|---|---|---|
| SV-16 | `cc::GameSaveManager` (`src\Cloudcell\CloudcellApi\GameSaveManager.cpp`; armv7 `0x151d1bc`–`0x151e648`) uploads and downloads the save as a `cc::BinaryBlob` (`ActiveUpload_Struct`, `GameSaveMember_Struct`), with UI `FrontEnd2::ProfileLoadSaveScreen` and `CloudSaveLogInPrompt`. The flag `m_bHasSaveChangedSinceLastUpload` tracks pending uploads. A hash check exists on sync ("Didn't match its hash. Corrupt Sync?", `0x1cdbf08`) | CONFIRMED (components); **protocol decoded: NETWORKING_ANALYSIS §8.15 (NW-57..59)** |
| SV-17 | Local save and load do **not** depend on the cloud: the local path is complete (SV-06..10), and the cloud is a separate upload/restore feature | HIGH (no cloud call inside the local write/read path examined); runtime behaviour without the server still to be checked |

## 5. Reconstruction implications

- A clean-room **container codec** (XOR stream + header + checksum) is fully specified and validated. `SCRIPTS/save_format_check.py` is the reader prototype; the key must come from the user's own binary.
- Body decoded (§2b) and a C++ reader/writer exists (SV-24). Next: map key names to game meaning (career, garage, currency) for roadmap D-01; any write must target copies only.
- Never write to original saves; any writer must target copies only.

## 6. Next steps

1. Read the loader `0x15aa49c` / `0x15aeea0` to settle the id-reference rules in hierarchical files (SV-19).
2. Relate `m_garage` / `m_careerProgress` entries to car and event ids from the game data (needs CarDesc / career data formats).
3. Cross-check on armv7 (same files, so the format must match).
