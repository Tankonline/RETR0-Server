# Networking Analysis

Last updated: 2026-11-14 · Status: **first pass plus CloudCell sync framing decoded (§8); from static evidence only.** No original server was contacted, probed or resolved. The original services were shut down on 20 March 2026; every host below is documented as historical evidence, **not** as a dependency.

Addresses are arm64 ELF virtual addresses. Evidence: JADX (`com.firemonkeys.cloudcellapi.*`, `com.ea.nimble.*`), `02_NATIVE_ENGINE/SYMBOLS/*/libRealRacing3/{strings.tsv,urls.txt}`, B-01 source attribution (`src\Cloudcell\*`, 53 files).

## 1. Network stacks in the client

| ID | Stack | Used by | Transport | Evidence | Confidence |
|---|---|---|---|---|---|
| NW-01 | **CloudCell** (Firemonkeys online layer, `cc::` 125 RTTI classes) | Sync, accounts/members, friends, cloud save, assets, events, store helpers | Native `cc::HttpRequestManager` / `cc::AndroidHttpRequestWorker` → **Java** `com.firemonkeys.cloudcellapi.HttpRequest` (`init(url, method, …, timeout, …)`, `post()`) → `HttpThread` → `HttpURLConnection`. Results return through the exported natives `HttpRequest.{header,data,complete,error}Callback` | JADX `HttpRequest`/`HttpThread`; JNI_MAP; RTTI; source file `CloudcellApi\Android\AndroidHttpRequestWorker.cpp` | CONFIRMED |
| NW-02 | **EA Nimble / Synergy** | EA device/Synergy IDs, MTX (purchases), push (Push-TNG), tracking, "Synergy Director" configuration (e.g. `nexus.proxy` URL) | Java `com.ea.nimble.*` (`SynergyNetwork`, `SynergyRequest`) plus the C++ side `EA::Nimble::Base::NimbleCpp*` (HTTP and socket clients) | JNI signatures in strings; RTTI | CONFIRMED |
| NW-03 | **Native libcurl 8.7.1 + OpenSSL 3.3.0** (static) | [likely] Glu SDK cores and Nimble C++ calls to `/accnt/v1`, `/gevs/v1`, `/revid/v1`, `/personalization/v2/games`, `/proxy/identity/geoagerequirements`, `/verifications/*` | curl; OpenSSL default CA directory `/system/etc/security/cacerts` | Strings (`… with curl code %d on connection %s`, paths) | CONFIRMED (presence); exact caller mapping MEDIUM |
| NW-04 | **fmRUDP** (Firemint reliable UDP) | Real-time multiplayer and LAN play | UDP; packets `Init/Data/Ack/Ping/ClockSync/BroadcastDiscovery`; `P2PLanCommunicationInterface.cpp`; "Connecting to game server: %s" | RTTI, strings | CONFIRMED (components); protocol not yet analysed |
| NW-05 | Glu `csdk.*` services, ads SDKs, Firebase, Facebook | Ads, consent, analytics, crash reporting | Their own stacks | P1 report | CONFIRMED |

## 2. TLS behaviour (CloudCell Java path)

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| NW-06 | `HttpRequest.initSSLContext()` installs, **process-wide** (`HttpsURLConnection.setDefault*`), an `SSLContext` built with `CloudcellTrustManager` and `ALLOW_ALL_HOSTNAME_VERIFIER` | JADX `HttpRequest.java:106-115` | CONFIRMED |
| NW-07 | `CloudcellTrustManager.checkServerTrusted` performs **no CA chain validation and no pinning**. It only rejects certificates whose `notAfter` precedes the server-provided time, and only when the request's SSL-check flag is set. Hostname verification is disabled | JADX `CloudcellTrustManager.java` | CONFIRMED |
| NW-08 | `network_security_config` allows cleartext only to `127.0.0.1`; everything else must use TLS (P1) | APKTool | CONFIRMED |
| NW-09 | Native curl path: CA directory present; a `sha256//` pin format string exists but belongs to libcurl itself. **Whether any request sets pinning is not established** | Strings | UNKNOWN (open Q9) |

**Implications:** (1) Preservation builds must not be used with real accounts, because this trust manager makes the app's HTTPS trivially interceptable. (2) An **independently operated** replacement service with its own certificate would be accepted by the CloudCell Java path. This is a technical observation, **not** a licence to impersonate EA domains (see §6).

## 3. Server selection and environments

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| NW-10 | `cc::EnvironmentManager` holds the active CloudCell environment ("EnvironmentManager Initialized. Active Environment: [%s]", "Cloudcell Environment changed from [%s] to [%s]"). `SyncManager` re-targets its "SyncDomain" when the environment changes | Strings; `EnvironmentManager.cpp` attributed | CONFIRMED (behaviour); environment list MEDIUM |
| NW-11 | **A built-in (debug/cheat) server switch persists** across restarts and reinstalls: "Do you want to save the CC sync server change? … the server will still stay set to this" | String | CONFIRMED (feature exists); storage location UNKNOWN |
| NW-12 | Environment host families in the binary: `0037-connect` (live), `0037-connect-stage`, `connect-sandbox`, `connect-dev-ss` (all `*.cloudcell.com`). `0037` is consistently the RR3 prefix | `urls.txt` | CONFIRMED (strings); per-environment roles MEDIUM |

## 4. Endpoint and host inventory (historical evidence; nothing contacted)

| Area | Hosts (strings) | Paths (strings) | Confidence of pairing |
|---|---|---|---|
| CloudCell sync and auth | `0037-connect[-stage].cloudcell.com`, `connect-sandbox`, `connect-dev-ss`, `s.cloudcell.com` | `CC_Sync.php` ("CC Syncing", `AuthenticateCloudcellSync`, member/device ids, server time) | MEDIUM |
| Asset delivery | CDN `firemonkeys.akamaized.net` (`/gameasset/direct/realracing3/`); fallback `0037-assets.cloudcell.com`, `04u-assets-stage` | `/assetman/assetManDownloadPackHash.php`, `/assetman/assetManGetUserList.php` ("Downloading from CDN has failed! Reverting to Cloudcell server", `CLOUDCELL_FallbackAssetServerEnabled`) | HIGH |
| Multiplayer game servers | `0037-mp3`, `0037-mp6`, `be01prr3mp01` (`*.cloudcell.com`) | fmRUDP over UDP | MEDIUM |
| Customisation sharing | — | `/customisation/friends/`, `/customisation/omp/`, `/customisation/thumbnails/` | MEDIUM |
| PopCap service platform ("Draper") | `0037-draper.cloudcell.ea.com`(.cn), `draper.k.awspopcap.com`, `draper-staging.popcap.com` | — | LOW (role) |
| EA MCT | `prd1.accnt.ea-mct-live.com`, `prd1.echo.ea-mct-live.com` | `/accnt/v1`, `/verifications/*` | MEDIUM |
| Glu central services | `prd1.gevs.glulive.com`, `prd1.revid.centech.glulive.com`, `prd1.personalization.centech.glulive.com`, `gpis-prod.revtech.glulive.com` | `/gevs/v1`, `/revid/v1`, `/personalization/v2/games` | MEDIUM |
| Help / legal / web | `help.ea.com`, `tos.ea.com`, `help.paradise.cloudcell.com` (`/Support/index.php?`) | — | HIGH (web pages) |

## 5. Offline behaviour (evidence, not yet runtime-tested)

| ID | Finding | Confidence |
|---|---|---|
| NW-13 | CloudCell has an explicit online/offline state ("CC: Cloudcell is Online/Offline", "Changed Offline") | CONFIRMED |
| NW-14 | Offline UI and logic paths exist: `RaceTeamManager::DisplayOfflineContributionWarning`, `FrontEnd2::MDollarPopupContent::UpdateOfflineLayout`, "Falling back to generic Offline M$ Forfeit logic", connection-error dialogs scoped to specific screens (`ProfileLoadSaveScreen`, `OpenInternalURL`) | CONFIRMED (presence) |
| NW-15 | Saves are local and authoritative (SAVE_SYSTEM_ANALYSIS SV-17); the launcher downloads nothing (P1 §4); asset downloads have retries and a fallback | CONFIRMED |
| NW-16 | **Assessment:** core single-player play is designed to work offline, with online-only features (multiplayer, cloud save, events/LTS sync, store, friends) degrading. **Not yet verified at runtime after the shutdown**, including whether any startup step waits for CloudCell or Synergy | MEDIUM (needs a device or emulator test with networking disabled, with the owner's approval) |

## 6. Reconstruction design principles (independent replacement)

- **Do not impersonate EA:** no DNS hijacking of EA/CloudCell domains, no reuse of EA credentials, no collection of EA account data.
- Prefer the **client's own selection mechanisms** (environment and sync-server switch, NW-10/11; `127.0.0.1` cleartext allowance, NW-08) to point a test build at an **independently operated** local service with its own endpoints, data and authentication.
- First targets, by value to offline preservation: (1) sync/config bootstrap responses so the client reaches the "online" state locally; (2) asset manifest (`assetManDownloadPackHash`) for depot validation; (3) server time. Multiplayer (fmRUDP) comes last.
- Each endpoint's request and response shape must be documented from client code (request builders and response parsers in `src\Cloudcell\*`) before any server is written. That work is the next step.

## 8. CloudCell sync protocol (static decode, arm64)

Evidence: `02_NATIVE_ENGINE/ANALYSIS/NETWORK/arm64-v8a/` (pseudocode, call trees). **Not validated against captured traffic** (none exists in the project, and the servers are gone).

### 8.1 Transport

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| NW-17 | Sync requests are **`POST` to `CC_Sync.php`** on the SyncManager's current sync domain (`SyncManager+0x90`), with a global timeout and two flags; the request object (`0x1c754a0`) builds `https://` or `http://` URLs. Sent by `SyncManager` `0x1d03520` ("CC Syncing"); no request is sent when sync is disabled ("Unable to Sync, SyncManager disabled!") | Pseudocode (`0x54534f50` = "POST", inline "CC_Sync.php") | CONFIRMED |
| NW-18 | The body is a **binary `cc::BinaryBlob`**, not form fields. The Java layer still labels POST bodies `application/x-www-form-urlencoded` (HttpThread) | Pseudocode + JADX | CONFIRMED |
| NW-19 | Requests are **batched**: components queue sub-requests into a pending blob (`SyncManager+0x78`) and each response part is dispatched in order to the queued request objects (`0x1d05bb0`). A response must match the outstanding request handle ("Sync received response that doesn't match request!") | `0x1d03520`, `0x1d03c7c` | CONFIRMED (structure); per-sub-request formats NOT YET DECODED |

### 8.2 BinaryBlob framing ("BoxData" / "UnboxData")

All integers are **little-endian** (raw ARM writes via `BinaryBlob::Write` `0x1cbdd28`).

| Field | Type | Notes |
|---|---|---|
| checksum | u32 | custom checksum over everything from offset 8 (§8.3) |
| box type | u32 | 0 plain · 1 zlib · 2 rolling-XOR (any other value logs "Unknown encryption type") |
| payload (type 0) | bytes | data |
| payload (type 1) | u32 uncompressed length + zlib stream | `compress2(level 9)` with bundled zlib 1.2.5 (`0x15b5408`); errors `Z_BUF_ERROR` / `Z_MEM_ERROR` |
| payload (type 2) | u8 seed + data XOR rolling key | key byte `i` = `(seed + 3·i) mod 256`; seed = `rand()` after `srand(time(NULL))` |

| ID | Finding | Confidence |
|---|---|---|
| NW-20 | Requests are wrapped as **`Box(Box(body, 1), 2)`** (compress, then XOR). Responses are unwrapped by calling `UnboxData` twice, each verifying the checksum (`0x1cbd8f0`, `0x1d03c7c`) | CONFIRMED |
| NW-21 | Response body starts with a u32 status (non-zero → a further u32 follows) before the per-request parts. **Superseded by NW-60** | CONFIRMED (see §8.16) |

### 8.3 Checksum (`0x1cb9734`)

Over signed bytes in groups of four `(a, b, c, d)`: `v = a·b·c` (using only the bytes present); if `d` exists and is non-zero, `v = v / d` (C integer division); `sum += v` (32-bit wrap). CONFIRMED from pseudocode.

### 8.4 Authentication request (`AuthenticateCloudcellSync`, `0x1d00364`)

| Order | Field | Notes |
|---|---|---|
| 1 | **`PackBlobHeader`** (`0x1d00f38`, `FederatedAuthenticationManager.cpp`) | u32 `0x22` (34, [likely] protocol version); u32, u32 from the Cloudcell object (`+0x38` → [likely] game/app identifiers); u32 from a sub-object; then length-prefixed strings (u32 length + bytes) from the device/identity objects |
| 2 | u32 auth state | Enum: 0 `LEGACY`, 1 `INITIATE`, 2 `AUTHENTICATE_SUCCESS`, 3 `AUTHENTICATED`, 4 `REAUTHENTICATE`, 5 `MEMBER_CONFLICT`, 6 `DEVICE_CONFLICT`, 7 `SOCIAL_AUTH_CHANGED`, 8 `REAUTHENTICATE_STRICT` (string table `0x1f66a68`) |
| 3 | u32 member id | |
| 4 | u32 N, then N × identity records | each: u32 index + four length-prefixed strings (0x60-byte source record; [likely] provider / user id / token / name) |
| 5 | u32 flag | |
| → | `Box(…, 1)`, `Box(…, 2)`, `POST CC_Sync.php` | |

Auth results seen in strings: `AUTH_SUCCESS`, `AUTH_CHANGED`, `AUTH_SERVER_FAILURE`, `AUTH_REQUIRES_FLUSH`, `AUTH_REQUIRES_RESET`, `AUTH_MEMBER_CONFLICT`. Named sub-sync types surviving in strings: `CC_SYNC_MANAGER_AUTHENTICATION`, `RR3_SUB_SYNC_TYPE_GET_PVP_SERVERS`, `SYNC_TYPE_LOAD_SELECTED_PROFILE` (most enum names are not present).

### 8.6 Sub-sync batching (SyncManager V34)

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| NW-22 | Protocol version **34**: `SyncManagerV34.cpp`'s `PackBlobHeader` (`0x1d04438`) writes u32 `0x22`, two u32 ids from the Cloudcell object, a u32 from a sub-object, a length-prefixed string, then further length-prefixed strings from identity objects | Pseudocode; source path string | CONFIRMED (fields after the first four only partly named) |
| NW-23 | **Queueing:** `SyncManager::QueueSubSync(blob, type, param, callback)` (`0x1d02e14`, a region Ghidra left undefined; found by ADRP/ADD scan) constructs a 0x70-byte `SubSync` (`0x1d05a54`): payload blob `+0`, **type `+0x18`, param `+0x1c`**, global sequence id `+0x20` (logged, **not sent**), callback `+0x30/+0x50`, done/cancelled flags `+0x60/+0x61`. Log: "CC: Sub Sync Queued: %d" | Capstone disassembly | CONFIRMED |
| NW-24 | **Request batch** (built around `0x1d03240`, "Sending Sync with SubSyncs"): `PackBlobHeader`, then per sub-sync **`u32 type, u32 param, u32 0, u32 length, payload`** (`0x1d05af4`), then `Box(1)`, `Box(2)`, POST. No count field was observed between the header and the records | Disassembly | CONFIRMED (records); "no count" MEDIUM |
| NW-25 | **Response:** after the status field(s) (NW-21), each queued sub-sync, in queue order, receives **`u32 length + bytes`** (`SubSync::CompleteSync`, `0x1d05bb0`), passed as a `BinaryBlob` to its callback. Cancelled sub-syncs are logged ("Cancelled SubSync Received") and skipped | Pseudocode | CONFIRMED |
| NW-26 | **Request classes** derive from `CC_Helpers::Sync` (common Cancel slot `0xcf0fc0`). `Sync::Queue` (`0xcf1018`) passes the object's `(type +8, param +0xc)` to `QueueSubSync` and stores the returned id at `+0x10` | Vtable recovery (22 classes share the slot); pseudocode | CONFIRMED |

### 8.7 Sub-sync type table (constructor constants)

Recovered with `SCRIPTS/find_vtable_ctors.py`: each constructor loads one 8-byte constant into `+8` = (type, param).

| Class | type | param |
|---|---|---|
| `CC_Helpers::SyncSales` | 10448 | 5440 |
| `CC_Helpers::PlayerRankSync` | 10452 | 6 |
| `CC_Helpers::SyncUserPN` | 10455 | 4240 |
| `CC_Helpers::DownloadSavedGameSync`, `…DownloadRandomProgressSaveGameSync` | 10469 | 3496 |
| `CC_Helpers::LeaderBoardSync` | 10477 | 3573 |
| `CC_Helpers::LeaderBoardGroupSync` | 10484 | 3574 |
| `CC_Helpers::LeaderBoardFriendsSync` | 10486 | 5040 |
| `CC_Helpers::LeaderBoardEntrySync` | 10514 | 1468 |
| `CC_Helpers::LeaderBoardCCMemberIdSync` | 10516 | 1900 |
| `CC_Helpers::OnlineMultiplayerFinishedMatchSync`, `…DisconnectionSync` | 10532 | 5431 |
| `CC_Helpers::UploadVehiclesSync` | 10545 | 2387 |
| `CC_Helpers::OnlineMultiplayerMemberStatusSync` | 10548 | 1731 |
| `CC_Helpers::GetPlayerGarageSync` | 10607 | 3491 |
| `CC_Helpers::OnlineMultiplayerStartMatchSync` | 10626 | 2218 |
| `CC_Helpers::GetCustomisationInfoSync` | 10630 | 2322 |
| `PingTestGetServersSync` (`RR3_SUB_SYNC_TYPE_GET_PVP_SERVERS`) | 10768 | 0 |
| `CC_Helpers::LeaderBoardValidateSync` | 10788 | 5338 |
| `FrontEnd2::DataRequestSubSync`, `OnlineMultiplayerScheduleSync` | not found by the scan ([likely] runtime-supplied types) | — |

Confidence: HIGH (the constant is stored where `Sync::Queue` reads type/param; the PvP log string confirms the class identity). The meaning of `param` (sub-command, version or schema id) is UNKNOWN; for `PlayerRankSync` it is 6.

### 8.8 Individual sub-syncs decoded so far

| Sub-sync | Request payload | Response | Confidence |
|---|---|---|---|
| PvP server list (10768) | **empty** (`PingTestGetServersSync` slot 2 queues an empty blob) | list of (host string, port int), logged `"%s:%d"`; retried after 240,001 ms | Request CONFIRMED; response field encoding MEDIUM (parser not yet read) |
| Server time (`ServerTimeManager`, `0x1cefd8c`) | separate request; also reads HTTP response headers (`unordered_map` overload) | NTP-style: server time + offset estimated from the request midpoint `(t_send + t_recv)/2`, round trip used as the error bound, several samples kept and outliers rejected | Algorithm HIGH; request/response bytes UNKNOWN |

The codec now has `pack_subsync`, `parse_subsyncs` and `pack_response_parts` (tests 14/14).

### 8.9 Per-type payloads decoded

Each `CC_Helpers::Sync` subclass uses vtable **slot 2 = build and queue the request** and **slot 3 = parse the response part**. Several of these handlers lie in code Ghidra left undefined; `RETR0_CallTree.java` now creates such functions **in memory only** (headless `-readOnly`, nothing saved) to decompile them.

| Sub-sync (type/param) | Request payload (slot 2) | Response part (slot 3) | Confidence |
|---|---|---|---|
| **PlayerRankSync** (10452/6) | `u32` = object field `+0x50` ([likely] member id) (`0xcdd160`) | `u32 rank`. **If the part is empty, the client reports rank 500** (`0xcdd1e8`) | CONFIRMED (layout); field meaning MEDIUM |
| **GetPlayerGarageSync** (10607/3491) | `u32` = object field `+0x50` ([likely] member id) (`0xceb5c8`) | `lp-string` (u32 length + bytes), `u32 count`, then per car: `u32` ([likely] car id), `u32`, `lp-blob` deserialised into a car object by `0xceb9ac` (`0xceb6f4`) | Framing CONFIRMED; field meanings and blob contents MEDIUM/UNKNOWN |
| **PingTestGetServersSync** (10768/0) | **empty** | `u32 n` (**= 2 × entries**), then per entry `lp-string host`, `u32 port`; the client then **shuffles** the list with `rand()` (`0xbbbe54`) | CONFIRMED |

Codec additions: `player_rank_request/response`, `garage_request`, `garage_response`, `pvp_servers_response` / `parse_pvp_servers_response`, `lp_string`, plus the type/param constants. Tests: **20/20** (after §8.10 additions).

**Offline implication:** a local independent service can answer `PlayerRankSync` with any rank (or the client falls back to 500), and answer the PvP list with an empty or local server list. The garage response can carry car blobs produced by the save-format writer (§8.10).

### 8.10 Garage car blob = `.cc_cust` user-data file; vehicle upload and customisation info

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| NW-27 | The per-car `lp-blob` of the garage response is handled by `0xceb9ac`: it **writes the blob verbatim** (`fopen "wb"` / `fwrite`) to `<files>/.depot/customisation/random_temp.2.cc_cust`, **loads it with the user-data (FMUserData) save loader** `0x139dbb8` (`"customisation/random_temp"`, folder `"customisation"`, extension `"cc_cust"`), then deserialises it into a car-customisation object (`0xc9cc58`) | Pseudocode in `NETWORK/arm64-v8a/garage/` | CONFIRMED |
| NW-28 | The file name comes from the builder `0x139e52c` with format `"%s.2.%s"`, so the `.2.` infix is a **fixed part of every user-data file name** written by these helpers (saves `*.2.dat`, customisation `*.2.cc_cust`) | Format string and call arguments | CONFIRMED (the literal); why it is `2` UNKNOWN (likely a format generation) |
| NW-29 | **Verification:** the user's own `.depot/customisation/random_temp.2.cc_cust.bak` (a blob previously received from the server) parses **byte-exactly** with `SCRIPTS/save_decode.py` (structure only): version 5, size 516, 20 dictionary keys, 2 tables, checksum OK. Keys include `m_nCarId`, `m_nPaintJobIndex`, `m_decalData`, `m_nWheelStyleId`, `m_nTyreStyleId`, `m_fTyreRatio`, front/rear suspension height and wheel width, `m_bPristine`, `m_bFactoryDecalsRemoved`, `m_bCanPaintBaseTexture`, `m_nSuspensionTypeId`, `m_nCCMemberId`, `m_sCCMemberName`, `m_sCCSyncServer`, and version markers `Ver6`/`Ver7` | Decoder output (names only, values not printed) | CONFIRMED |

| NW-30 | **UploadVehiclesSync** (10545/2387) request (`0xcec53c`): `u32 flag` (object byte `+0x68`), `u32 count`, then per car: `u32` ([likely] car id, from `0xca3d64`), **`lp-blob` = the car's complete `.cc_cust` file** (the client first saves the car with the user-data writer to `.depot/customisation/%03d.2.cc_cust`, then reads the file back memory-mapped via `0x12a48f8`), `u32 0`, `u32` (car field `+0x170` & 1) | Pseudocode in `NETWORK/arm64-v8a/customisation/` | Layout CONFIRMED; meanings of flag, id and the last bit MEDIUM/UNKNOWN |
| NW-31 | UploadVehiclesSync response (`0xcecb78`): `u32 status`; if non-zero, `u32 count` + `count × u32` (returned ids). Status 0 or an empty part → the callback receives an empty result | Pseudocode | CONFIRMED (layout); meaning of returned ids UNKNOWN |
| NW-32 | **GetCustomisationInfoSync** (10630/2322) request (`0xced408`): `u32 count`, then `count × (u32, u32)` from an 8-byte-entry vector at `+0x50` | Pseudocode | CONFIRMED (layout); field meaning UNKNOWN ([likely] member/car pairs) |
| NW-33 | GetCustomisationInfoSync response (`0xced508`): `u32 count`, then per `ResultInfo` (0x40 bytes in memory): `u32, u32, bool, u32, u32, u32, bool, lp-string, u32`. **Bools are u32 values that must be 0 or 1** (`BinaryBlob.h` `UnpackBool` asserts otherwise). An empty part logs "GetCustomisationInfo sync returned EoF" and yields an empty list. Consumers: `FrontEnd2::YourGarageList` / `YourGarageScreen` (RTTI of the bound callbacks) | Pseudocode; RTTI | Layout CONFIRMED; field meanings UNKNOWN |
| NW-34 | **ResultInfo fields named from their consumers.** Callbacks found through the `std::function` GOT slots next to the bound-functor vtables: `YourGarageList` `0xefa444`, `YourGarageScreen` `0xefa8f8`. In-memory offsets → meaning: `+0x00` **CC member id** (matched against the car's customisation block at car `+0x48`, whose first fields are `m_nCCMemberId`, `m_sCCMemberName`, `m_sCCSyncServer`); `+0x04` **car id** (matched against car `+0x40`); `+0x10` → car flags (car `+0x170`) **bit 0** (setter `0xca3074` also stamps a time at car `+0x168`); `+0x38` → car flags **bit 1**; `+0x18` **name valid** (screen shows the title only when true); `+0x20` **member name** (the list writes it into the car's `m_sCCMemberName` with the current sync server via `0xc9c67c`; the screen upper-cases it into `GAMETEXT_PLAYERS_CARS`). `+0x08` (bool), `+0x0c`, `+0x14` are **not read** by these consumers | Pseudocode in `NETWORK/arm64-v8a/customisation/` | Member id, car id, name, name-valid, bit targets CONFIRMED; what the two flag bits mean UNKNOWN; three fields UNKNOWN |
| NW-35 | **Request pairs** are `(CC member id, car id)`, one per garage car with downloaded customisation. A car whose customisation was authored on another CloudCell server is not queried: its flag bit 0 is cleared and the client logs "Customisation downloaded for nCCMemberId:%d, nCarId:%d, was authored on a different Cloudcell server: %s" (string `0x4956ef`). The same flag bit 0 is what `UploadVehiclesSync` sends as its last per-car field (NW-30) | Disassembly `0xefa048`–`0xefa0d8` | HIGH |

The live `random_temp.2.cc_cust` (not only the `.bak`) also parses byte-exactly (20 keys). No `customisation/NNN.2.cc_cust` upload files exist in the local data copy (they are written just before an upload).

**Reconstruction implication:** an independent service can build garage responses with the same writer as the save tools (D-01): one `.cc_cust` container per car, wrapped by `garage_response()`. The meanings of the response's leading string and the two `u32` fields per car are still MEDIUM/UNKNOWN.

### 8.11 Leaderboard sub-syncs

Handlers from vtable slots 2/3 (pseudocode in `NETWORK/arm64-v8a/leaderboards/`). Offsets in brackets are where each value lands in the client's 0xc8-byte entry object; names are only given where the code shows a use.

**Request key (shared by LeaderBoard, Group, Friends, Entry, CCMemberId):** `u32 board` (object `+0x50`), `u32 n`, `n × u32` (`+0x58` vector). Then:

| Sub-sync | Request after the key | Response part |
|---|---|---|
| **LeaderBoardSync** 10477/3573 (`0xce0310` / `0xce06a8`) | `u32 ×4` (`+0x70, +0x74, +0x78, +0x7c`); `+0x70` and `+0x78` are copied into the result ([likely] range parameters) | `u32 own_index`, `u32`, `u32`, `u32 count`, then `count ×` **main entry** |
| **LeaderBoardGroupSync** 10484/3574 (`0xce1c10` / `0xce1e08`) | `u32` (`+0x70`) | `u32`, `u32`, `u32 count`, then per row `lp-string, u32, u32, u32`; rows are then sorted client-side |
| **LeaderBoardFriendsSync** 10486/5040 (`0xce2224` / `0xce2510`) | raw pre-packed bytes (pointer `+0x70`, length `+0x78`) | `u32 count`, then `count ×` **friends entry** |
| **LeaderBoardEntrySync** 10514/1468 (`0xce3838` / `0xce3944` → `0xce3ad4`) | `u32, u32` (`+0x70, +0x74`) | **one short entry**, no count |
| **LeaderBoardCCMemberIdSync** 10516/1900 (`0xce45f4` / `0xce4808`) | `u32 count` + `count × u32` (`+0x70` vector; [likely] member ids) | `u32 count`, then `count ×` **short entry** |
| **LeaderBoardValidateSync** 10788/5338 (`0xce126c` / `0xce1558`) | no shared key: `u32` (from the event object found by id `+0x50`), `u32 count`, then per eligible owned car `u32` (`0xca3180`), `u32` (`0xca4400`) | `bool32 valid`, `u32 value`, `u32` (read and discarded). Empty part → callback `(received=0, valid=true, value=-1)` |

**Entry records.** All share a **core**: `lp-string name [+0x00]`, `u32 [+0x18]`, `lp-string [+0x20]`, `lp-string [+0x38]`, `lp-blob` (**read and skipped**), `lp-string [+0x50]`.

| Record | After the core |
|---|---|
| main | `lp-string [+0x68]`, `u32 [+0x8c]`, `f32 [+0x90]` (raw float bits; the client adds 0.01 when > 0; default −1.0), `lp-string [+0x98]`, `u32 [+0x84]`, `u32 [+0x88]`, `u32 n + n × u32 [+0xb0]`, `u32 [+0x80]` |
| friends | `u32 [+0x84]`, `u32 [+0x88]`, `u32 [+0x8c]`, `f32 [+0x90]`, `lp-string [+0x98]`, `u32 [+0x80]`, `lp-string [+0x68]` (same fields, different order) |
| short | `u32 [+0x84]`, `u32 [+0x88]`, `u32 [+0x8c]` |

| ID | Finding | Confidence |
|---|---|---|
| NW-36 | Wire layouts above (request keys, six response formats, three entry variants) | CONFIRMED (read order and destinations); field meanings UNKNOWN except where stated |
| NW-37 | **Anonymous names:** when a global client setting is on, every main/CCMemberId entry whose index differs from the header's first `u32` has its name replaced by `GAMETEXT_ANONYMOUS_RACER`, so that `u32` is [likely] the local player's own row index | MEDIUM |
| NW-38 | **Client cache:** LeaderBoard, Friends and CCMemberId first look up a global cache (`PTR_DAT_020708b8`, keyed by object `+0x80`/`+0x88`) and answer from it without a request when the key matches; LeaderBoard results are stored back (`0xcdfe64`) | HIGH |
| NW-39 | **Alternate data path = Rookie Championship synthetic leaderboards** (traced, §8.12). LeaderBoardSync and GroupSync ignore the wire data while the Rookie Championship is active and show **locally generated** standings instead | CONFIRMED |

Codec: `lb_key`, `leaderboard_request`, `lb_core`, `leaderboard_entry_main/friends/short`, `leaderboard_response`, `leaderboard_group_response`, `leaderboard_validate_response`, plus constants. Tests **23/23**.

### 8.12 Rookie Championship: locally generated leaderboards

Pseudocode in `NETWORK/arm64-v8a/leaderboards/altpath/`.

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| NW-40 | The flag object is **`RookieChampionship::RookieChampionshipManager`**: constructor `0x1382a74` stores the vtable `0x1ecdb80` (RTTI) and saves `this` to the global behind GOT slot `0x1f6d840` | Disassembly; vtable recovery | CONFIRMED |
| NW-41 | **Active check** `0x13833cc` returns true when manager `+0x08` (enabled) is set **and** state `+0x0c` ≠ 5 **and** the current game-mode value (global `0x1f6d5d8` → `+0x478` → `+4`) ≠ 0x14. State is set to 3, 4 and 5 as the championship progresses (writes at `0x1381370`, `0x13858e8`, `0x1384bc8`, `0x13860c0`); 5 = finished. `0x1383a14` returns the current round index (`+0x10` in states 0/3, `+0x14` in state 4, otherwise 2) | Pseudocode; store scan | Logic CONFIRMED; state names and mode 0x14 UNKNOWN |
| NW-42 | **Generator** `0x1389440` (main board) / `0x1389828` (group): fills the per-round opponent rows with **random scores** from a PCG32 generator (`0x10a2738`) within round-specific ranges (with a +1000 spread), inserts the player's own name (from the player profile), sorts the scores, places the player's row, and hands the built board (`0xcdf9e0`, `0xcdf75c`) to the leaderboard callback. No network data is used | Pseudocode | HIGH |
| NW-43 | **What enables it:** the manager reads the switches **`Rookie_Enable`** (key/value lookup `0x9a2530`, parsed as an integer) and **`enable_rookie`** (a boolean fetched from Java through JNI, `0x12b9db0`) while loading (`0x1382ce8`–`0x1382d78`). `0x1384b40` clears the enabled byte when the tutorial completes (strings `CompleteTutorial`, `activate_rookie_crash_fix`, `Progression`) | Strings and stores; Java class behind `0x12b9db0` not yet identified | MEDIUM |

| NW-44 | **`enable_rookie` = Firebase Remote Config.** `0x12b9db0` calls the Java static method stored at JNI-helper `+0x290`, which the init code (`0x12b6f34`) fills with `com/firemint/realracing/Platform.GetBooleanValueFromRemoteConfig(String)Z`. In Java this is `MainActivity.instance.getFirebaseRemoteConfigInstance().getBoolean(key)`. `MainActivity` sets a 3600 s fetch interval and calls `fetchAndActivate()` but **sets no in-app defaults**, so without a fetched or cached config Firebase returns its static default **false** | Disassembly; JADX `Platform.java:1551`, `MainActivity.java:451-453` | CONFIRMED |
| NW-45 | **`Rookie_Enable` = a CloudCell ServerVariables entry.** `0x9a2530(key, default, &out)` asks the `ServerVariables` store (global GOT `0x1f6d7a8`, lookup `0x13c2654`, debug panel "server_variables") for `key` with the default converted to a string, then `out = atoi(result)`. The store is saved locally as `doc/sv.2.dat` (schema `ServerVariables.m_Variables`, `keys`, `values`, `size`, `mapV2`) | Disassembly; strings `ServerVariables`, `m_Variables`, `vars`, `dat`; `save_decode.py` on `sv.2.dat` | HIGH |
| NW-46 | **Decision logic at load** (`0x1382c90`–`0x1382d78`): if the championship state (`+0x0c`) is **non-zero** (already started) it stays **enabled** regardless of either switch. Otherwise `v = Rookie_Enable` (**default 1**), `enabled = (v == 0)`, and only when `v == 0` is `enabled` replaced by Firebase `enable_rookie`. As written, a **non-zero or missing `Rookie_Enable` disables** the championship for players who have not started it. The inverted sense is surprising: the comparison is `cmp w8,#0; cset eq`, the default argument is `mov w1,#1` | Disassembly; verified in NW-48 | Logic **CONFIRMED**; design intent UNKNOWN |
| NW-47 | **Local data check (read-only, names only):** neither `Rookie_Enable` nor `enable_rookie` appears in any decrypted `doc/*.2.dat` or `.depot/*.bak` in the local copy. Firebase's own cache lives in app-private storage, which the local copy does not include | Byte search of decrypted saves | CONFIRMED (for this copy) |

| NW-48 | **Missing-key behaviour confirmed.** `0xd37600` formats the default with `"%d"` (string at `0x38c97f`), so default 1 → `"1"`. The ServerVariables lookup `0x13c2654` searches a `std::map<string,string>` at store `+0x60` (`0xc925ec`); when the key is absent it copies the **default string** and returns false (the caller ignores the return). So a missing `Rookie_Enable` yields `atoi("1") = 1` → championship **off**, and Firebase is not consulted. A server value of `"0"` is the only way the Firebase switch gets a say | Pseudocode of all three helpers | CONFIRMED |
| NW-49 | **Other ways the enabled byte is set to 1:** the setter `0x13833b4` is called from (a) `0x14e9028`, the operator() of the `FrontEnd2::PauseMenu::CreatePauseTweaksCheatButtons` lambda `$_8` (std::function vtable `0x1edf380`), a **debug cheat button labelled "Force Rookie FTUE"** (string at `0x14e0500` region), and (b) `0x14ddf20`, for which no caller or reference was found in a branch/relocation scan (UNKNOWN). Both call `0x13832ec` afterwards ([likely] start the championship) | Branch scan; relocations; RTTI | (a) CONFIRMED; (b) caller UNKNOWN |

**Offline implication:** this is **not** a general offline mode. It only covers leaderboards shown during the Rookie Championship (the new-player series). With no server and no Firebase cache, a player who has **not started** the championship would not get it (NW-46); one who already started keeps it. Other leaderboards still need a replacement service (§8.11), or a client-side change to return local data, which is outside this static analysis. The sources of the two switches are traced in NW-44..47 below.

### 8.13 Sales and online multiplayer sub-syncs

Pseudocode in `NETWORK/arm64-v8a/sales_mp/`. "MP" = the online-multiplayer match object reached through global `0x1f6d5d8` → `+0x54c0` → `+0x188`; player objects come from `0x13e6828(match, i)` and carry the CloudCell member id at `+0x290`.

| Sub-sync | Request (slot 2) | Response part (slot 3) | Confidence |
|---|---|---|---|
| **SyncSales** 10448/5440 | **empty** (`0xcf13b0`) | the whole part is handed **unparsed** to the callback (`0xcf1420`); the sales format is decoded by the consumer, not here | CONFIRMED (framing); sales payload format not yet traced |
| **OnlineMultiplayerMemberStatusSync** 10548/1731 | `u32` (MP `+0x120`), `u32` (byte `+0x14`) (`0xce9eb8`) | content **ignored**: non-empty → callback(1), empty → callback(0) (`0xcea000`) | CONFIRMED |
| **OnlineMultiplayerStartMatchSync** 10626/2218 | **match header** (below), `u32` (byte `+0x58`), `u32` (`0x13e653c(MP)`), `u32 n`, then per player `u32 member_id`, `u32` (protected value at player `+0x90`), then `u32` car id (`0xca3d64`), four `u32` from the car's performance object (`0x13f4df4`, `0x13f4dfc`, `0x13f4d4c`, `0x13f4d44`), `u32` (byte `+0x59`) (`0xce70f8`) | `u32`, `u32` (stored as a protected value), `u32 ×4`, `u32` (protected), `u32`, `u32 count`, then per player `u32 member_id`, `u32 value`, `u32 blob_len`, and when `blob_len > 0`: the blob (**an opponent `.cc_cust` file**, written to `.depot/customisation/omp/%d_%03d.cc_cust` unless it is the local player's) and a `u32` (`0xce76a8`) | Layout CONFIRMED; meanings MEDIUM/UNKNOWN |
| **OnlineMultiplayerFinishedMatchSync** 10532/5431 | match header, `u32` (byte `+0x58`), `u32` (`0x13e653c`), `u32 ×5` (`+0x94…+0xa4`), `u32 n`, per player `u32 member_id`, `u32` and `u32` from two per-member maps (`+0x80`, `+0x68`; 0 when absent), `u32` (player byte `+0x7e`, or 0 in one condition), then `u32` (byte `+0xa8`), `u32` (byte `+0x90`) (`0xce85dc`) | similar header to StartMatch (8 values incl. two protected), `u32 count`, per player 6 `u32`, then further per-member maps; a final `u32 > 0` sets a result flag (`0xce8e3c`, string `OnlineMultiplayerMatchInfo`) | Request CONFIRMED; response read order CONFIRMED, field meanings UNKNOWN |
| **OnlineMultiplayerDisconnectionSync** (same type 10532/5431) | match header, `u32` (`+0x14`), `u32` (`+0x18`), a fixed run of constants (`0,0,-1,0,0,0,0,1`), `u32` (player member id `+0x290`), `0,0`, `u32` (player byte `+0x7e`), `0`, `u32` (byte `+0x1c`) (`0xce9c38`) | **no-op** (`0xce9eb4` returns immediately) | CONFIRMED |
| **OnlineMultiplayerScheduleSync** (type supplied at run time) | **empty** (`0xf710f0`) | large schedule structure: header `u32`s, three `lp-string`s, nine counted `u32` lists, further strings and ~20 `u32`s, then four more lists; Elo/reward settings are read here (`m_nEloOffset`, `m_nEloDivVariable`, `m_nEloMinGoldReward`, `m_nEloMaxGoldReward`) (`0xf711fc`) | Read order CONFIRMED; field meanings UNKNOWN |

**Match header** (start, finish, disconnect): `u32 0x1D2D` (constant 7469), `u32` (MP `+0x11c`), `u32` (MP `+0x120`), `u32`, `u32` (sync object `+0x50/+0x54`, or `+0x14/+0x18` for disconnect).

| ID | Finding | Confidence |
|---|---|---|
| NW-50 | Sales sync is a pull with an empty request; the reply is opaque to the sync class and parsed by the callback owner | CONFIRMED |
| NW-51 | Online multiplayer start/finish/disconnect share a header beginning with the constant `0x1D2D`; start-match responses deliver each opponent's car as a `.cc_cust` file (same container as the garage, §8.10) | CONFIRMED |
| NW-52 | Member-status and disconnection replies carry no data the client uses, so a replacement service can answer them with any (or an empty) part | CONFIRMED |

Codec: `sales_request`, `mp_member_status_request`, `mp_start_match_response`, constants. Tests **25/25**.

### 8.14 Saved-game download (DownloadSavedGameSync / DownloadRandomProgressSaveGameSync, 10469/3496)

Pseudocode in `NETWORK/arm64-v8a/savedgame/`.

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| NW-53 | **Requests:** `DownloadSavedGameSync` sends one `u32` (object `+0x14`, the maximum number of saves wanted) (`0xcdd284`); `DownloadRandomProgressSaveGameSync` sends the constant **50** (`0xcddda4`) | Pseudocode | CONFIRMED |
| NW-54 | **Response** (`0xcdd30c`, `0xcdde2c`): `u32 count`, then per save `u32 id`, `u32` (meaning UNKNOWN), `lp-string description`, `lp-string URL`. An empty part logs "Invalid blob size returned."; a count below 0 or above the requested maximum logs "Invalid save game count returned." and the client **calls `exit(1)`** | Pseudocode | CONFIRMED |
| NW-55 | **Second stage:** for each entry the client issues an **HTTP GET** to the URL (request object via `0x1c761a0`, method string "GET"). The callback `0xcdd844` wraps the body in a BinaryBlob, **unboxes it once** (logs ", Unbox failure" if that fails), writes it to `../../<id>.bin`, and appends a line `"%u, %s, %s%s"` (id, time, description with commas replaced by dots, failure note) to `save_game_descriptions_<YYYY_MM_DD_HH_MM>.csv` | Pseudocode; strings | CONFIRMED |
| NW-56 | **Purpose:** this looks like **developer/QA tooling** for bulk-downloading other players' saves, not the player-facing cloud-save restore: it exits on bad counts, writes to `../../`, and keeps a CSV log; the random variant is triggered near the message "Too many game save sync errors encountered while trying to download random save games." (`0xcd6b50`, caller `0xcd6aac`) | Behaviour and strings | MEDIUM (no player-facing UI path found yet) |

**Reconstruction implication:** not needed for normal play. The player's own cloud save restore remains a separate, not yet decoded path (SAVE_SYSTEM_ANALYSIS).

Codec: `download_saved_game_request`, `saved_game_list_response`, constant. Tests **26/26**.

### 8.15 Player cloud save (`cc::GameSaveManager`)

Pseudocode in `NETWORK/arm64-v8a/cloudsave/`. The manager (vtable `0x1f65368`, methods `0x1ce7a10`–`0x1ceb1fc`) uses the same sub-sync queue as the game-level syncs, with its **own type ids** (some much lower than the `CC_Helpers` range), plus plain **HTTP GET/PUT** for the save bytes.

| Operation | Sub-sync (type/param) | Request | Reply | Confidence |
|---|---|---|---|---|
| **List saves** `QueueDownloadList` (`0x1ce9da0`) | **47 / 7277** | `u32 1` | parser `0x1ce9fb8`: `bool32`, `bool32`, `u32 groups`; per group `lp-string`, `u32 n`; per save `bool32`, `u32`, `u32`, `lp-string`, `lp-string`, `u32`, `u32`, `u32`; then, for every save again, an `lp-string` stored at entry `+0x50` (the **download URL**, may be empty). Result → `callback(bool, bool, vector<GameSaveMember_Struct>)` (consumer `CC_Helpers::CloudSaveList`) | Read order CONFIRMED; field names partly UNKNOWN |
| **Download** (`0x1ce926c`) | if the entry's URL is **empty**: `QueueDownloadSync` **48 / 809** | `u32 save_id` (entry `+4`), `u32 0` | parser `0x1ce994c`: `bool32`, `lp-blob` (the save) | CONFIRMED |
| | if the URL is **set**: `QueueDirectDownload` | **HTTP GET** of the URL (request object `0x1c761a0`, method "GET") | body = the save | CONFIRMED |
| **Upload** (`0x1ce842c`; rate-limited: skipped unless forced or ≥ 43,200 s since the last upload) | normal: **10660 / 5638** (`0x1ce887c`) | `u32` flag (`+8`), `lp-string` (`+0x28`), `lp-string` (`+0x40`) | handler `0x1ce8d88`: `u32 status` (must be 0), `lp-string` (kept in the upload record `+0x98`), `lp-string URL`; the client then sends the **boxed save with HTTP PUT** to that URL | CONFIRMED |
| | alternate (when the caller's 4th argument is set; description becomes "CORRUPT"): **22 / 2816** (`0x1ce8a28`) | `u32` (`+8`), `u32` (`+9`), `lp-blob` (the boxed save, inline), `lp-string`, `lp-string`, `u32 0`, empty | — | Request CONFIRMED; when it is used MEDIUM |
| **Validate** `QueueValidate` (`0x1cea864`) | **10555 / 5757** | `lp-string` | parser `0x1ceab68`: `bool32` | CONFIRMED |

| ID | Finding | Confidence |
|---|---|---|
| NW-57 | Cloud save is a **two-stage** protocol: sub-syncs carry metadata (list, upload slot, validate), while the save bytes normally travel over plain HTTP (**PUT** for upload to a server-given URL, **GET** for download when the list provides a URL); the sync channel carries the bytes only as a fallback (types 48 and 22) | CONFIRMED |
| NW-58 | The save uploaded is the boxed (`BinaryBlob::BoxData`) form of the local save; the earlier SV-16 hash check ("Didn't match its hash. Corrupt Sync?") applies on download | HIGH |
| NW-59 | Uploads are throttled to at most once every **12 hours** (`last + 0xa8c0` seconds) unless forced | HIGH |

**Reconstruction implication:** an independent service can support cloud save with four sub-sync handlers (47, 48, 10660, 10555) and a simple HTTP store for PUT/GET. It must answer **10660 with status 0 and a URL it controls**; it must never point clients at EA URLs. Since the local save is authoritative (SV-17), this is optional for single-device play.

Codec: `gsm_upload_request`, `gsm_upload_response`, `gsm_download_response`, `gsm_validate_response`, constants. Tests **27/27**.

### 8.16 Whole sync response, SyncUserPN, DataRequestSubSync

Evidence: `NETWORK/arm64-v8a/misc/` (pseudocode, and `sync_response_handler_0x1d03c80.asm.txt`).

| ID | Finding | Confidence |
|---|---|---|
| NW-60 | **Sync reply body** (handler `0x1d03ca0`, log "CC: [%d] Sync response received"): the reply must belong to the outstanding request (otherwise "Sync received response that doesn't match request!"). It is unboxed **twice**. Then `u32 ok`: **0 → every queued sub-sync completes with an empty part** (`0x1d03f68` path). Otherwise `u32 value` is passed to a CloudCell sub-object (vtable `+0x148` → `+0xa0`; meaning UNKNOWN), a further readiness check runs, and each queued sub-sync receives its `u32 len + bytes` part in order (`0x1d05bb0`). If bytes remain: `u32 n` + `n × u32`, inserted into a set kept by the SyncManager (`+0x50`, cleared first; meaning UNKNOWN) | CONFIRMED (layout); two meanings UNKNOWN |
| NW-61 | **SyncUserPN** 10455/4240: request (`0xcf1a28`, only when a CloudCell sub-object is ready) `u32` (`+0x14`), `u32` (`+0x18`), `lp-string` (`+0x38`), then a list of string pairs (`+0x20` vector, 0x30-byte entries): pairs the client can map to a cached id are counted, the others are sent as `u32 n_unresolved` + `n × (lp-string, lp-string)`, followed by `u32 n_resolved` and the resolved ids. Reply: **ignored** (`0xcf1dfc` is empty). What "PN" stands for is UNKNOWN | Request layout HIGH; meaning UNKNOWN |
| NW-62 | **FrontEnd2::DataRequestSubSync** (type/param given at run time; `DataRequestPopup.cpp`): request `u32 kind` (`+0x14`) and, only when `kind ≠ 0`, `u32` (`+0x18`) (`0xab3644`). Reply `bool32`, `u32`, `u32`, stored as the popup's pending result ("Attempting to overwrite a sync result that is pending") (`0xab36f8`). [likely] the player data-request (privacy) feature | CONFIRMED (layout) |

With these, every `CC_Helpers::Sync`-derived class (21 + base) has a decoded request and reply framing. **This was not the whole protocol**: see §8.17 for ~80 further sub-syncs queued directly.

Codec: `sync_response_body` (the full reply body before boxing), `data_request_request/response`, constant. Tests **28/28**.

### 8.17 Coverage audit: directly queued sub-syncs (2026-11-14)

**Why:** §8.6–8.16 covered the 21 classes derived from `CC_Helpers::Sync` plus `GameSaveManager`. A whole-binary scan found many more call sites that queue sub-syncs **directly** through the SyncManager (`blr` via vtable `+0x10` with immediate type/param in `w2`/`w3`, the same pattern as `GameSaveManager`).

**Method (all read-only, reproducible):**
1. Capstone scan of all of `.text` → 168 call sites, 83 (type, param) pairs.
2. Ghidra `RETR0_DecompileContaining.java` (new) decompiled the containing function of every site. 54 sites lie in code Ghidra has **not assigned to any function**; for those, `RETR0_CallTree.java` decompiled from a prologue-heuristic start.
3. `SCRIPTS/subsync_disasm_layout.py` (new) reads each request layout straight from the disassembly: PackData calls between the BinaryBlob constructor and the queue call. **Validated** against the hand-decoded cloud-save messages: 47 → `u32`, 48 → `u32 u32`, 10555 → `lp`, 10660 → `u32 lp lp` all match.
4. `SCRIPTS/subsync_catalogue.py` (new) merges request layouts, reply read orders (UnpackData sequence of GOT-loaded code pointers near the queue call), strings, source files and RTTI class names.

**Result:** `NETWORK/arm64-v8a/direct_subsyncs/CATALOGUE.md` (and `.tsv`), and the generated `06_RECONSTRUCTION/BACKEND/cloudcell_codec/subsync_table.py` (80 entries).
- **3 false positives** were removed: (1,1) OpenSSL, (4,4) graphics, (16,24) SQLite.
- **80 real direct sub-syncs**, all with a request layout (11 have no PackData between constructor and queue call: empty, or a blob built elsewhere).
- **57** of the 80 have a candidate reply read order.

Named senders include:

| Area | Type ids (examples) |
|---|---|
| Achievements | 2, 20, 10463 |
| Text (TextManager) | 11 |
| Files (FileManager) | 13 |
| Server config (GameConfigManager) | 10631 |
| Gifts (GiftManager) | 10480, 10481, 10790 |
| Banning (BanningManager) | 10547 |
| Social / friends | 10556 |
| Authentication | 10714 (SimpleAuthenticationManager.cpp), 10738 |
| Customer support | 10716 |
| Store purchases | 10704 (Nimble transaction), 10767 (NimbleStoreHandler.cpp, VerifyNimblePurchaseDetails) |
| Race teams | 10669–10690 cluster, 10673 (RaceTeamManager.cpp), 10675 |
| Saves | 10735 (SaveManager.cpp) |
| Multiplayer schedule | 10785 (OnlineMultiplayerSchedule.cpp) |
| Time-trial ghosts | 10694 ("RR3 Time Trial Ghost") |
| Twitter sign-in | 10443 |
| Promotions | 10632 |
| Usage-sharing opt-in | 10781 |
| Missing time-trial progress | 10784 |
| Main menu (FrontEnd2::MainMenuManager) | 10781 |

| ID | Finding | Confidence |
|---|---|---|
| NW-63 | The sync protocol has **~101 sub-sync types**: 21 class-based + 80 directly queued. The direct ones were previously undocumented | Scan count CONFIRMED; per-entry request layout HIGH (validated method); reply layouts MEDIUM (handler choice is heuristic) |
| NW-64 | Most direct sub-syncs carry **only field widths**, not meanings. Each is a lead for a focused pass like §8.9–8.16 | — |

**Ghidra coverage (new, `RETR0_Coverage.java`):** 39,984 functions cover **72.0 %** of `.text` (15.5 of 21.6 MB). **5.78 MB of disassembled code in 9,515 ranges belongs to no function** (3,442 ranges ≥ 256 B), so it never appears in decompiler output, call trees or xrefs. This is why these sub-syncs were missed. **Resolved the same day with the owner's approval on a backed-up working copy** (see ENGINE_ARCHITECTURE / TOOLCHAIN "Function recovery"): coverage is now **98.79 %** and no code lies outside a function. All 168 queue sites now decompile inside real functions (`direct_subsyncs/containing_recovered/`). For the **63** sub-syncs where both extraction methods apply, the pseudocode layout and the disassembly layout **agree in every case**; the other 17 rely on the disassembly layout alone.

### 8.18 Direct sub-syncs: owners, features and named fields (2026-11-14)

Method: `RETR0_CallerContext.java` (new, read-only) walked up to 5 levels of callers from every sender on the recovered arm64 copy. It recorded the strings each caller uses and which RTTI vtable slots point at it (`direct_subsyncs/callers/callers.tsv`). Senders with no class were then placed using the function-to-source-file map (`SOURCE_ATTRIBUTION/arm64-v8a_expanded.tsv`); those placements are marked "[by file order]". The machine-readable result is `06_RECONSTRUCTION/BACKEND/cloudcell_codec/subsync_features.py`: an owner, feature and confidence for **all 80** direct sub-syncs, plus field names where they are established.

| Owner group | Sub-syncs | Basis |
|---|---|---|
| CloudCell managers (Achievement, Text, File, Stat, Piracy, Banning, GameConfig, CommunityEvent, auth, CustomerSupport, VersionUpdate, MemberManager, SocialMedia, Gift, Twitter, GameSaveManager) | 2, 11, 13, 20, 22, 32, 47, 48, 68, 80, 82, 10443–10445, 10463, 10480, 10481, 10547, 10555, 10556, 10631, 10660–10663, 10714, 10716, 10738, 10790 | Sender or caller is a vtable slot of the class, or its assert path names the file |
| **Race Teams** (`RaceTeamManager.cpp`) | 10669–10690, 10725, 10766 | Source attribution BRACKETED-HIGH; caller UI classes `RaceTeam*Page/Tab`; reply strings `GAMETEXT_RACE_TEAMS_*` |
| Purchases | 10704 (NimbleMTX record), 10767 (VerifyNimblePurchaseDetails), 10632 (promo code), 10609 (targeted sales [by file order]) | Log strings, GAMETEXT ids |
| Results / racing | 10451 race result upload, 10694–10696 time-trial ghost, 10476 ghost download, 10565 report abuse, 10785 multiplayer schedule | `UploadResultTask`, "RR3 Time Trial Ghost", `TimeTrialMode`, telemetry labels |
| RacerManager | 10446 (`loadOpponents`), 10472 (friends list), 10458, 10459, 10419 | Log strings; file order |
| Server variables / maintenance | 10712, 10715, 10739, 10806, 10742, 25 | `ServerVariableService` vtable; `ServerMaintenanceService` (file order, std::function vtables nearby); `Maintenance_KillSwitch` caller |
| Front end / debug | 10567, 10733, 10734 (MainMenuCheatScreen), 10735, 10737, 10748, 10762, 10781, 10784, 10796, 10797, 10688, 10606 | Caller vtables and strings |

| ID | Finding | Confidence |
|---|---|---|
| NW-65 | **Server variables (10712/4373)**, `ServerVariableService` (`0x13c1f70` / reply `0x13c20f4`). Request: one `u32`, obtained from Cloudcell vtable `+0x90` → object vtable `+0x1d8` (meaning UNKNOWN). Reply: `u32 count`, then `count × (lp key, lp value)`. The client clears its map first and stores each pair through `0x13c2470`. This is the wire form of the ServerVariables that gate features such as `Rookie_Enable` (NW-46) and `RRTV_Enabled` | HIGH |
| NW-66 | *(Superseded in part by NW-72: the echoed value is the player's Race Teams member id.)* **Race Teams shared header.** Every Race Teams reply handler reads its first `u32` into global `0x1f6d5d8` → `+0x1608` (e.g. `0xfab688`, `0xfb3a80`, `0xfb5434`, `0xfb6364`). Every Race Teams request sends that slot back as its first field (`rt_token`), so a replacement server must echo a value. Most requests then send `rt_local` (`0xcd6c00`: global → `+0x10500` → `+0x58` → `+0x58`; only RaceTeamManager calls it; meaning UNKNOWN). Create/search requests end with `*(0x1f6d710)+4` (UNKNOWN) and `utc_offset_hours` | Round trip CONFIRMED; meanings UNKNOWN |
| NW-67 | `0x14168bc` returns the device UTC offset in whole hours: `(mktime(localtime(t)) − mktime(gmtime(t))) / 3600` | CONFIRMED |
| NW-68 | **Race Teams operations** by sender and reply strings: 10669 search (reply: token, count, per-team u32 + 4 strings + bool + 2 u32), 10670 create (4 strings, then a bool; reply error codes NAME/TAG_UNAVAILABLE, PROFANITY; on success stores team id at `+0x1550` and 4 strings at `+0x1568..+0x15b0`), 10671 join (team id, bool), 10674 leave, 10678 rewards (team id `+0x1550`), 10680 invite member (`member, −1`) or request membership (`−1, team`), 10685 accept invite, 10686 decline invite, 10687 members/manage, 10690 wall, 10676 add contribution, 10766 restore contribution. The order of the 4 create strings (name/tag/description/motto) is not verified. *Refined by NW-72..77 (name and tag order now known; invites use 10681)* | Features HIGH/MEDIUM per entry (see `subsync_features.py`) |
| NW-69 | **Report Abuse (10565/2016)** `0xceceac`: request `u32 reportee_member_id, u32 reportee_car_id`. The same values feed the telemetry event "Report Abuse / Inappropriate Customisation" with labels "Reportee CC Member Id" / "Reportee Car Id" (the reporter id is the local member id, not sent). Called from YourGarageScreen and race-results `BTN_REPORT` | HIGH |
| NW-70 | **NimbleMTX record transaction (10704/5986)** `0x1c78da4`: `lp transaction_id, lp receipt, lp item_sku, u32 timestamp, lp ?`. Values come from Java `com.ea.nimble.mtx.NimbleMTXTransaction` through a method table (`0x1977548`, names at ELF `0x1f8d990`): index 0 `getTransactionId`, 1 `getItemSku`, 6 `getTimeStamp`, 7 `getReceipt`, 8 `getAdditionalInfo`. For one store (string compared against `PTR 0x1f6fa08`, [likely] Google Play), transaction id and receipt are replaced by `additionalInfo["orderId"]` and `["token"]`. Log: "MTX Record Nimble transaction on CC: trans:%s receipt:%s" | HIGH (timestamp unit UNKNOWN) |
| NW-71 | Unresolved field meanings are listed as `?` in `subsync_features.py`; 13 entries are MEDIUM/LOW on ownership only (file-order or a single caller) | — |

### 8.19 Race Teams sub-syncs in detail (2026-11-14)

Sources: `NETWORK/arm64-v8a/race_teams/` (pseudocode of every sender, reply handler and the Race Teams UI code that calls them; read-only), plus capstone disassembly of the create page and the reply jump table. Machine-readable result: `subsync_features.py` (`SUBSYNC_FEATURES`, `RACE_TEAMS_HELPER_SUBSYNCS`, `RT_STATUS`).

**Team record** kept by the client at global `0x1f6d5d8` (filled by the create, join and team-info replies; cleared by `0xfb0aec`):

| Offset | Field | Evidence |
|---|---|---|
| `+0x1550` | team id | Sent back by rewards, members, wall, invite and post-message requests; reset to −1 |
| `+0x1554` | ? (the debug panel treats values > 1 as "no events") | UNKNOWN |
| `+0x1558` | [likely] leader member id | Create copies my own id into it; join reads it from the reply |
| `+0x155c` | is private | Info tab shows `GAMETEXT_PRIVATE`/`PUBLIC`; toggle confirm texts |
| `+0x1568` / `+0x1580` | name / tag | Reply order; tag length is checked as 3–4 characters on the create page |
| `+0x1598` | motto | Info-tab motto edit callback (`0xeba220`, reached via std::function at ELF `0x1f72b50`) writes it |
| `+0x15b0` | description | Description edit callback (`0xeba650`, ELF `0x1f72b58`) writes it |
| `+0x15f8` | have team | Set to 1 by create and join |
| `+0x1608` | my Race Teams member id | See NW-72 |

| ID | Finding | Confidence |
|---|---|---|
| NW-72 | **Supersedes the "rt_token" reading in NW-66.** The first u32 of every Race Teams request and reply is the **local player's Race Teams member id** (global `+0x1608`). The request page declines the player's own requests by calling `0xfbb8e4(+0x1608, −1, 0)`. The results tab (`0xec7234`) compares list entries against `+0x1608` to find "me". `0xa68c14` resets it to −1. The second header field (`0xcd6c00`) is sent by **every** Race Teams request, including 10673/10674/10685/10686, which the catalogue had shown as a single unknown u32 | HIGH |
| NW-73 | **Create team 10670**: request header, `u32 0`, `lp name`, `lp tag`, two more strings (motto and description), `bool32 is_private`, `u32 *(0x1f6d710)+4`, `u32 utc_offset_hours`. The first two strings come from create-page fields `+0x2a8` (checked as ≥ 5 characters, `NAME_LENGTH`) and `+0x2c0` (3–4 characters, `TAG_LENGTH`); the order of the last two (page `+0x2d8`, `+0x2f0`) is not verified. Reply: member id, `u32 status` (0 ok, 1 name taken, 2 tag taken, 3 generic, 4 profanity), then on success `u32 team_id, u32 ?, lp name, lp tag, lp motto, lp description, bool32 is_private` | HIGH (s3/s4 order UNKNOWN) |
| NW-74 | **Seven Race Teams sub-syncs are queued through helper `0xfb2cc4`** instead of a direct SyncManager vtable call, so the catalogue (§8.17) missed them: 10679/2819 kick member, 10681/2821 invite member, 10682/2822 edit team info (`u32 team_id, lp description, lp motto, bool32 is_private`), 10683/2905 accept a membership request, 10684/2906 decline a membership request, 10689/2923 post a wall message (`u32 team_id, lp message`), 10726/3586 (team id + a value from `0xfb8514`; meaning UNKNOWN). Existing pairs also gained senders: 10672 (`0xfb7228`) and 10686 (cancel invite, `0xfbac14`/`0xfbb0e0`). Found by scanning `0xfa8000–0xfc8000` for `mov w2,#type; mov w3,#param` before a call (31 queue sites). The direct sub-sync total is therefore **at least 87** (whole-library scan: exactly 87 constant pairs, NW-79) | HIGH |
| NW-75 | **Shared reply status codes** (join `0xfb5434`, request membership `0xfb9418` via jump table at ELF `0x4f7c76`, invite `0xfb8990`/`0xfb8dd0`): 0 success, 1 already on a team, 2 too many members, 3 too many requests, 4 already requested membership, 5 blocked, 6 not authorised, 8 team is private, 9 locked. Other replies use their own codes: create (above), leave 10674 (0 ok, 2 locked, else generic), kick 10679 (2 locked), post message 10689 (1 profanity, 2 connection error) | HIGH |
| NW-76 | **Join 10671** reply: member id, status, then on success `u32 team_id, u32 ?, lp name, lp tag, lp motto, lp description, u32 leader_member_id, bool32 is_private`. **Leave 10674** reply: member id, `u32 ?`, `lp ?`, `bool32 is_private`, `u32 status`. **Request membership 10680** reply: member id, status, `lp team_name` (`[szTeamName]`) | HIGH (layout); single `?` fields UNKNOWN |
| NW-77 | **10675** is "get team info" (4 senders: progress task, loading page/toaster deep link with −1 = own team, info tab, leaderboard popup); its reply (`0xfafcac`/`0xfb0e00`) fills the whole team record. **10686** carries either the header only (decline invite) or 3 extra u32 (cancel invite: `member, 0, x` or `0, member, x`) | HIGH / MEDIUM |
| NW-78 | Not yet named: search results (10669), members (10687), wall (10690), rewards (10678) and sync (10673) reply entries; the 12 contribution fields (10676); `+0x1554`; `rt_local`; `*(0x1f6d710)+4` | — |

### 8.20 Whole-library queue-call scan (2026-11-14)

Two read-only scans over the whole arm64 `.text` (capstone + LIEF on `02_NATIVE_ENGINE/LIBRARIES/arm64-v8a/libRealRacing3.so`; outputs in `NETWORK/arm64-v8a/queue_scan/`):

1. `SCRIPTS/subsync_queue_scan.py`: every call (`bl`/`blr`) preceded, with no call in between, by constant `movz w2,#type` and `movz w3,#param`, in code that called the BinaryBlob constructor `0x1cbd578` or PackData `0x1cbdd28` in the previous 600 instructions. **113 call sites, 91 distinct pairs.** All 87 previously known direct pairs (80 catalogued + the 7 Race Teams helper pairs from NW-74) were found again (recall check). The 4 remaining pairs are **false positives**:

| Pair | Site | Why it is not a sub-sync |
|---|---|---|
| (2, 1) | `0xfae4b0` → `0x14baa24` | Distance/unit text formatter (`GAMETEXT_UNIT_KILOMETRES` …) |
| (3, 3) | `0x15299d4` → `0x9ce3f0` | Arithmetic helper (count/amount arguments), no queue call |
| (16, 15604) | `0x1d13f60` → `0x1d14000` | Constructor of `cc::social::SocialManager<cc::social::twitter::TwitterWorker>` (vtable via reloc at ELF `0x1f7e630` → `0x1f68978`); stores the two values at `+0x108`/`+0x10c`. `+0x10c` is later packed into blobs and `+0x108` is passed to `0x1cb9204`; neither is used as a queue type/param |
| (32, 32) | `0x108b0bc` … → `0x1e18750` | `__strncpy_chk2` (libc PLT) |

2. `SCRIPTS/subsync_queue_residual.py`: queue-style virtual calls (`ldr xR,[xR,#0x10]; blr xR`) after a BinaryBlob constructor whose `w2` is **not** a constant. 175 constructors, **11 such calls**. None is a queue call: each passes only `x0`/`x1` (several are the blob's Box steps with `w1` = 1 or 2).

| ID | Finding | Confidence |
|---|---|---|
| NW-79 | **No further helper-queued sub-syncs exist beyond NW-74.** The sync protocol therefore has **108 known sub-sync types**: 87 queued with constant type/param, plus 21 class-based `CC_Helpers::Sync` subclasses whose (type, param) is an 8-byte constructor constant (§8.7). Two class-based syncs (`DataRequestSubSync`, `OnlineMultiplayerScheduleSync`) get their type at run time | HIGH for constant-pair queue sites. Not covered: a type built by arithmetic, loaded from a literal pool / `orr` encoding, or passed in from a caller beyond the 14-instruction window |

### 8.21 Request headers and authentication reply (2026-11-15)

Sources: `NETWORK/arm64-v8a/subsync/at_0x1d04438_decomp.c` (V34 `PackBlobHeader`), `NETWORK/arm64-v8a/auth/` (federated auth header `0x1d00f38`, auth sender `0x1d00364`, auth reply handler `0x1d0131c`), capstone disassembly of `0x1d0095c`. The handler address was resolved from the relocated callback pointer at ELF `0x1f7e4e8` → `0x1d0131c`; the federated manager's vtable (no RTTI) is the run of relocated pointers at `0x1f66a28` (slot 2 `0x1d0035c`, slot 3 `0x1d0095c`).

| ID | Finding | Confidence |
|---|---|---|
| NW-80 | **Batched sync request header** (V34): `u32 0x22`, `u32` ×3 (Cloudcell `+0x38` [0], [1]; a sub-object vt+0x20), `lp` (vt+0x18 object vt+0x60), then a cached list **`u32 n` + n × (`u32 tag`, `lp`)** built once with tags 0, 1, 3, 6, 4, 5 (sources: Cloudcell `+0x10` vt+0x30/+0x28/+0x40/+0x88 and `+0x38` strings at +0xa8/+0x90), then three `lp` (`+0x10` vt+0x58, +0x78, +0x80), then the **auth extension** written by the active auth manager through Cloudcell vt+0xa0 → vt+0x18 | CONFIRMED (layout); string meanings UNKNOWN |
| NW-81 | **Federated auth extension** (`0x1d0095c`, slot 3): `u32 3`, `u32 member_id` (member manager), `lp token` (the token stored at manager `+8` by the auth reply). So every sync carries the token issued by the server. `LegacyManager`/`SimpleManager` have their own slot-3 writers (`0x1cfb554`, `0x1cfc67c`); which manager is active at run time is MEDIUM (the federated one sends the auth request and receives the reply) | Layout CONFIRMED (assembly); active manager MEDIUM |
| NW-82 | **Auth request** (`0x1d00364`): federated header `0x1d00f38` = `u32 0x22`, `u32` ×3, **7 × `lp`**; then `u32 state`, `u32 member_id`, `u32 n`, n × (`u32 index`, 4 × `lp`), `u32 flag`; boxed (1, 2) and POSTed to `CC_Sync.php` like a sync | CONFIRMED |
| NW-83 | **Auth reply** (`FederatedManager::AuthenticationCallback` `0x1d0131c`): unbox ×2; `u32 ok` (0 → state `REAUTHENTICATE_STRICT`); `u32 value` (passed to Cloudcell vt+0x148 → +0xa0, the same sink as the sync reply's value, NW-60); `u32 new_state` (clamped to 8). If 2 (`AUTHENTICATE_SUCCESS`): `u32 member_id`, `bool32 is_developer` ("Member Is Developer"), `u32` (→ vt+0x150 obj +0x18), `u32` (→ vt+0x140 obj +0xe0), `bool32`, `lp token`, `u32 token timeout` (expiry = now + timeout, logged as "NewAuthTokenTimeout"). The client then sets state 3 `AUTHENTICATED`. State 5 (`MEMBER_CONFLICT`) carries a further conflict package | CONFIRMED (read order); three fields UNKNOWN |
| NW-85 | **Server selection is a fixed table and sync always uses HTTPS.** `GetDefaultDomain` (`0x1cf098c`, `EnvironmentManager.cpp`) maps environment 0–6 × service kind to built-in hosts (`firemonkeys.akamaized.net` for one service kind; `connect-sandbox`, `connect-dev-ss`, `-stage`/`-lt`/`-be` variants of `%04u-%s%s.cloudcell.com`, and `stage-connect.rr3.exos.fm` for environment 6). The EnvironmentManager registers 13 (environment, kind) pairs at init (`0x1cf1174`). The debug cheat behind "Save CC Server?" (`0xe3b43c`) only persists a choice between these. There is no free-text host entry; the `localhost`/`127.0.0.1` strings belong to libcurl (`0x19a…`–`0x19e…`). The request object (`0x1c754a0`) enables TLS exactly when the port is 443, and the port passed by the sync/auth senders is the `.rodata` constant 443 (ELF `0x5ff3d4`, via GOT `0x1f6e6d8`) | CONFIRMED (static); which environment the shipped build activates is UNKNOWN until runtime |
| NW-86 | **Request URL assembly.** `0x1c754a0(out, method, host, path, port, tls, flag)` stores method `+0x20`, host `+0x38`, path `+0x50`, port `+0x80`, `+0xb0 = (port == 443)`, `+0xb5 = (port == 443) & tls`. `0x1c756d8` builds `(+0xb0 ? "https://" : "http://") + host + ':' + port + '/' + path`. The sync sender `0x1d03520` passes ("POST", SyncManager `+0x90`, "CC_Sync.php", 443, 1, 1) | CONFIRMED (pseudocode + assembly) |
| NW-84 | First independent replacement service: `06_RECONSTRUCTION/BACKEND/local_service/` (auth + batched sync dispatch + cloud-save store; empty parts for unhandled sub-syncs). 43 tests pass (`08_TESTING`). Not yet tested against the real client | Implementation, not evidence |

Runtime test plan (not approved, not run): `08_TESTING/RUNTIME_TEST_PLAN.md`.

### 8.22 Bundled CloudCell seed data (`CC_SeedData.bin`, 2026-11-15)

`res/raw/res.zip` → `res/CC_SeedData.bin` (296,657 bytes) is read at start-up by the CloudCell FileManager (`0x1c70a80`, "CC: Filemanager initializing..."; file name referenced from Cloudcell init `0xcd1014`). Evidence: `NETWORK/arm64-v8a/seed_data/`. Reader: `SCRIPTS/seed_data_decode.py`, tests `08_TESTING/test_seed_data.py` (synthetic data only; no game data is committed).

| ID | Finding | Confidence |
|---|---|---|
| NW-90 | **Game config.** The GameConfig sync (10631/5245, sender `0x1cee6e4`) reply is handled by `0x1cee7c8` → `0x1cee984`: `u32 n`, n × (`u32 config_id`, `lp value`), each stored through GameConfigManager slot 4 (`0x1cee240`, "CC: Updated GameConfig '%d' -> %s"); slot 6 (`0x1cee574`) reads the same list. Seed file `1` holds a 5-word header (observed 0x870d, 17, 0, **15710** = game id, 1; meanings of the other four UNKNOWN), that list (20 values, ids 1–17 and 87–91: store URLs, app/push ids, public keys) and a trailing `u32 0`; it parses exactly. The local service now answers 10631 with these defaults read at start-up from the user's own `CC_SeedData.bin` (`--seed-data`), overridable in `state.json` | Reply layout CONFIRMED; header fields UNKNOWN |
| NW-91 | **Store catalogue (seed file `12`).** `u32 magic 654321`, `u32 version 10`, `u32 count`, then per product: `u32 product_id`, `lp name`, `lp title`, `lp price_string` (e.g. "$4.99"), `f32 price`, `u32`×5 (only the third varies: 1 in 492 products, 0 in 64; [likely] consumable), `lp metadata` ("type:pack id:3", parsed by the `StoreProducts.cpp` functions `0xcee2e0`/`0xceee4c`/`0xcef53c`/`0xcef614`), `lp` (always empty), `lp sku_na`, `lp sku_row` (`RR3IOS_…_NA/_ROW`), `lp` (always empty), 7 × `lp` store ids (two of them Amazon NA/ROW package names; the others UNKNOWN). The shipped catalogue has **556 products** (metadata types: adjustable_pack 421, pack 77, adhoc 33, wrench 7, money 6, mdollars 6, early_access 2, vip_tier1–3, recurring_reward), parses exactly and **rebuilds byte-identically**. Field names come from content and from the debug panels `0xa7f5c8` / `0xb89804` (Name, IsValid, Telemetry Price, Store Price, Consumable, Product Id NA/ROW; iTunes/Google/Amazon NA/ROW SKUs). The binary reader itself was not located | Layout CONFIRMED (exact parse + identical rebuild); field names MEDIUM |
| NW-92 | **FileManager sync (13/448).** Request (`0x1c73bf8`): no count; for each file the client knows, `lp name`, `u32 version` (file record `+0x20`). Reply (`0x1c73da0`; an empty part changes nothing): `u32 n`, n × (`bool32 is_directory`, `lp name`, `u32 version`, and only for files `u32 size` + bytes, written through the FileManager file API (vt `+0x40` open, `+0x60` write, `+0x50` close) and logged "new: <name>"), then `u32 m`, m × `lp name` deleted ("del: <name>"). The seed archive is FileManager's initial file store (NW-87), so seed files such as `12` (store catalogue) are FileManager files and can be replaced this way. Which version the client reports for seed-provided files is UNKNOWN until runtime | Layout CONFIRMED (pseudocode); version semantics UNKNOWN |
| NW-93 | **Sync reply member header (corrects NW-60, 2026-11-20).** After `u32 ok` and `u32 value`, the sync reply carries a header read by the active auth manager (`cc::auth::LegacyManager` `0x1cfb784`, via Cloudcell vt+0xa0 then +0x20) **before** the per-sub-sync parts: `u32 member_id` (logs "CC: Member changed [Member Id: %d]" when it differs), `bool32 is_developer`, `u32 device_id` ("CC: Device Id: %d"; Cloudcell vt+0x150 +0x18), `u32 u_b` (vt+0x140 +0xe0), `bool32 flag`. The local service omitted it until 2026-11-20, so the client read the first parts' lengths and bytes as these fields: empty parts read as zeros (unnoticed); a 13-byte racing-code reply produced "Member Id: 13" and the handler got an empty blob ("Connection error"). **Likely** also the cause of the gift freezes (SP-11/SP-12, ~250k-800k `UnpackData` asserts): a long gift part misread the same way. The service now sends the header, echoing the client's member id | Pseudocode `0x1d03c7c`, `0x1cfb784`; logcat runs 28-29 | CONFIRMED (layout); gift-freeze link MEDIUM |
| NW-94 | **Racing code (promo code) 10632/2369.** Submit `0x1516b1c(this, const char* code)`: after the already-entered check (`0x1638540` on character+0x478) it sends `lp code` and registers `0x15170e0`. Reply: `lp code` (must equal the sent code), `bool32 ok`, and when ok an `lp` reward list (parsed by `0xdd0da0`; each reward awarded with `0xc879fc(r, 0, 1)`), then GAMETEXT_PROMO_CODE_SUCCESSFUL_GENERIC; ok=0 shows GAMETEXT_PROMO_CODE_FAIL_INCORRECT; an empty reply shows the connection error. The local service answers every non-empty code with ok and no rewards (the RETR0 client uses it as the username setter, SV-27) | Pseudocode; runs 28-29 | CONFIRMED |
| NW-87 | **Archive format "NomNomNom":** magic `NomNomNom` (9 bytes), `u32 dir_bytes`, then records until `dir_bytes` are consumed: `u32 type` (0 = file, otherwise directory), `u32 name_len`, name, and for files `u32 size`. File data follows back to back from `13 + dir_bytes`. A corrupt header logs "Seed data file corrupt!". The shipped file parses exactly: 46 files, 0 directories, 294,951 data bytes ending at end-of-file | CONFIRMED (loader pseudocode + exact parse) |
| NW-88 | **Contents.** 41 named files are CloudCell web-browser assets (PNG loading/close/background images, `twitter_signin.html`, three `*_automagic_const.js`). Five files with numeric names are BinaryBlob containers boxed twice (XOR outside, zlib inside; checksums valid with the clean-room codec): `1` (1,673 B unpacked) game configuration (store URLs, push-service ids, public keys); `3` (104,788 B) localised texts (`TEXT_RR3_…` keys); `5` (1,639 B) the manifest of the bundled web files; `7` (3,554 B) Google Play Games achievement ids; `12` (150,319 B) store product catalogue (packs, prices, SKUs). Identification is by content; the internal layouts of the five blobs are not decoded yet | Container CONFIRMED; roles HIGH (content) |
| NW-89 | The client warns "Game Config Value [ConfigId: %d] [Default: '%s'] not found - Do you need to update your CC_SeedData.bin?" (`0x1cee17c`), so blob `1` is the default the GameConfigManager falls back to. **For the local service:** the client already ships default config, texts, store catalogue and achievement ids, so a replacement service can start from these defaults instead of inventing data (the data itself stays in the game files and is not redistributed) | HIGH |

### 8.5 Reconstruction status

- **Clean-room codec:** `06_RECONSTRUCTION/BACKEND/cloudcell_codec/cloudcell_codec.py` (box/unbox, checksum, `wrap_request`/`unwrap`). Tests in `08_TESTING/test_cloudcell_codec.py`: **10/10 pass**, covering round trips, the documented arithmetic, rolling-key bytes and tamper detection. Wire compatibility is **unverified** until a real client talks to it in a controlled local test.
- **Still to decode:** per-type payload and response formats (each class's request builder and response parser, §8.7), the response status field(s), and the server-time request.

## 7. Next steps

1. Leaderboard follow-ups: confirm the `Rookie_Enable` not-found path (NW-46) and the entry field meanings; ServerVariables storage layout in `sv.2.dat` (wire form now decoded, NW-65); Race Teams remaining fields (`rt_local`, `+0x1554`, create s3/s4 order, list-reply entries; NW-78); other helper-queued sub-syncs outside RaceTeamManager (NW-74 method) (relevant to any replacement service); the cloud-save list field meanings (§8.15), the two UNKNOWN values in the sync reply (NW-60), the sales payload consumer (NW-50) and the multiplayer schedule fields; the meaning of car flag bits 0/1 and the three unread `ResultInfo` fields (NW-34); the response status fields (NW-21).
2. Q9: curl option setup (CAINFO / PINNEDPUBLICKEY) in the Glu and Nimble C++ code.
3. Runtime offline test (owner approval required).
