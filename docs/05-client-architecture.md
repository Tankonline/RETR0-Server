# 05 · Client architecture: what we learned about the game

A summary of the Android client (RR3 14.0.1, `com.ea.games.r3_row`, versionCode 14001). Each section points to
the detailed reference document.

## Layers

```
 Java (DEX)             Activities, Android services, SDKs (Nimble, Glu, Firebase, Facebook, ads)
   │  JNI (124 exports + 6 RegisterNatives registrars)
 libRealRacing3.so      the engine: game loop, rendering (GLES2/EGL), physics, race modes, front end,
                        saves, CloudCell client, asset manager
 libNimble.so, libfmodex.so, libfuelmetrics.so ...   EA Nimble, FMOD Ex audio, metrics
```

- **Boot:** the launcher unpacks `res.zip` (asset lists and small resources) from the APK, then `MainActivity`
  loads Nimble → FMOD Ex → RealRacing3. The game's data lives under `Android/data/com.ea.games.r3_row/files/`:
  `.depot/` (content), `doc/` (saves), `apk/` (unpacked `res.zip`).
- **Frame loop:** the Java GL thread calls into native code each frame; Update (integer milliseconds, clamped to
  100 ms) then Render; scenes are Game, Splash and Front end.
  → [reference/ENGINE_ARCHITECTURE.md](reference/ENGINE_ARCHITECTURE.md)
- **JNI:** → [reference/JNI_MAPPING.md](reference/JNI_MAPPING.md)

## Simulation and races

- Fixed **16 ms** simulation step (62.5 Hz) with an accumulator; up to 43 cars.
- Exact fixed-point position integration `pos += (vel * dt_ms) >> 10` with remainder carry.
- Two tyre models (slip-angle curve; drive/brake and aero drag), surface friction from material flags.
- Suspension and vertical motion are **kinematic** (gravity + aero downforce, ground clamp), not a spring-damper.
- 32 `GameMode` subclasses (race types).
  → [reference/PHYSICS_ANALYSIS.md](reference/PHYSICS_ANALYSIS.md),
  [reference/RACE_SYSTEM_ANALYSIS.md](reference/RACE_SYSTEM_ANALYSIS.md),
  [reference/VEHICLE_SYSTEM_ANALYSIS.md](reference/VEHICLE_SYSTEM_ANALYSIS.md)

## Saves

- Local and authoritative: `files/doc/*.2.dat` (`character`, `player_profile`, `gs`, `sv`, `loadout`, `ttss`, …).
- Container: every byte XORed with a fixed 64-byte table from the library, big-endian header (magic `0xABCFFCBA`,
  version 5, size), XOR checksum. Body: an interned dictionary of C++ member-path names plus typed value tables.
  Currency values are tamper-protected (`[EHV]`/`[H]`) and were deliberately **not** decoded.
- The save holds **no player name**: the name comes from the online account (see
  [features/username.md](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/username.md)).
- CloudCell keeps its own small data files in `files/doc/CC_Data/<id>` (e.g. id 6 = the member record).
  → [reference/SAVE_SYSTEM_ANALYSIS.md](reference/SAVE_SYSTEM_ANALYSIS.md)

## CloudCell: the online client

CloudCell is the game's own online layer (`src\Cloudcell\CloudcellApi\…` in the source paths).

- **Transport:** native code builds requests, and the Java class `com.firemonkeys.cloudcellapi.HttpRequest` performs
  them with `HttpURLConnection`, using a process-wide trust manager that accepts **any** certificate and host name.
- **Hosts:** a fixed table: `0037-connect.cloudcell.com` (sync), `0037-assets.cloudcell.com` (asset manager),
  `firemonkeys.akamaized.net` (CDN), multiplayer hosts (`fmRUDP` over UDP, not served here).
- **Sync:** one endpoint, `POST /CC_Sync.php`, carrying batches of **sub-syncs** (about 101 types). Time comes from
  `POST /time`. → [06-network-protocol.md](06-network-protocol.md)
- **Managers:** `SyncManager`, `MemberManager` (the local member record), auth managers (`LegacyManager` is the one
  this guest client uses), `GiftManager`, `GameSaveManager`, `FileManager`, `AssetManager`, `StatManager`.

## Other online parts (not served)

EA Nimble/Synergy, Glu central services, Firebase, Facebook, ads, Helpshift. The game carries on without them;
their requests simply fail on the locked emulator.

## Assets

- `res.zip` holds **1,236 asset lists**; each line is `/path<TAB>md5<TAB>stored size<TAB>size`.
- The asset manager downloads packs per list from the CDN with HTTP Range requests and checks every file's MD5.
  → [09-asset-cdn.md](09-asset-cdn.md), [reference/ASSET_DOWNLOAD_PROTOCOL.md](reference/ASSET_DOWNLOAD_PROTOCOL.md)
- Content formats: [reference/ASSET_FORMAT_INVENTORY.md](reference/ASSET_FORMAT_INVENTORY.md)

## Store

- The static store catalogue (556 products: currency packages, packs, cars, offers) ships in seed file 12.
- Purchases go through EA Nimble MTX / Google Play; the game also has a **non-purchase** reward path (used by its
  free offerwall rewards), which the store-grants feature reuses.
  → [features/store-grants.md](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/store-grants.md),
  [reference/STORE_PRESERVATION_GRANTS.md](reference/STORE_PRESERVATION_GRANTS.md)
