# 06 · The CloudCell network protocol

Everything here was decoded from the client's code and confirmed against requests recorded on the locked test
emulator. Full findings with addresses: [reference/NETWORKING_ANALYSIS.md](reference/NETWORKING_ANALYSIS.md)
(NW-17 onwards). The clean-room implementation is
[`server/services/cloudcell_codec/cloudcell_codec.py`](../server/services/cloudcell_codec/cloudcell_codec.py).

All integers are **little-endian u32** unless stated. `lp` means a length-prefixed string: `u32 length` + bytes.
`bool32` is a u32 that must be 0 or 1.

## 1. Endpoints

| Request | Purpose | Server answer |
|---|---|---|
| `POST https://0037-connect.cloudcell.com/time` (empty body) | Server time | HTTP 200, empty body, header **`X-Request-Start: <Unix seconds>`** |
| `POST https://0037-connect.cloudcell.com/CC_Sync.php` | All sync traffic (batched) | Boxed binary reply (below) |
| `POST https://0037-assets.cloudcell.com//assetman/assetManDownloadPackHash.php` | Asset-manager fallback | Not needed when the CDN answers |
| `GET https://firemonkeys.akamaized.net//rr3/live/<list>/<md5>.bin` + `Range` | Asset packs | HTTP 206 with the byte range ([09-asset-cdn.md](09-asset-cdn.md)) |

## 2. Boxing

Every sync body is wrapped twice: `Box(Box(body, ZLIB), XOR)`. The reply is unwrapped the same way, twice.

```
box        = u32 checksum(rest) · u32 box_type · payload
  type 1 (ZLIB):  payload = u32 inflated_length · zlib stream (level 9)
  type 2 (XOR):   payload = u8 seed · data[i] XOR ((seed + 3·i) & 0xFF)
checksum   = over signed bytes in groups of four (a, b, c, d): sum += a·b·c / d   (32-bit wrap)
```

The XOR "seed" travels in each message; there is no secret key.

## 3. Sync request

```
u32 0x22                          protocol version 34
u32, u32, u32                     ids from the CloudCell object
lp                                identity string
u32 n · n × (u32 tag, lp)         cached identity list (tags 0, 1, 3, 6, 4, 5)
lp, lp, lp
auth extension                    written by the active auth manager (guest client: LegacyManager)
sub-sync records, back to back:   u32 type · u32 param · u32 0 · u32 length · payload
```

## 4. Sync reply

```
u32 ok                  0 → every queued sub-sync completes with an EMPTY part
u32 value               passed to a CloudCell sub-object (meaning not identified)
── member header (read by the active auth manager, LegacyManager 0x1cfb784) ──
u32 member_id           "CC: Member changed [Member Id: N]" when it differs from the client's
bool32 is_developer     "CC: Member Is Developer"
u32 device_id           "CC: Device Id: N"
u32 u_b                 (meaning not identified)
bool32 flag             (meaning not identified)
── parts, one per queued sub-sync, in queue order ──
u32 length · bytes      handed to that sub-sync's callback as a BinaryBlob
── optional ──
u32 n · n × u32         ids kept by the SyncManager (meaning not identified)
```

The member header was missing from the RETR0 server until 2026-11-20, which made every non-empty reply arrive
garbled. See [features/sync-reply-header-fix.md](features/sync-reply-header-fix.md).

## 5. Sub-syncs

About **101 types**: 21 implemented as request classes and 80 queued directly. Each has a `(type, param)` pair; the
reply part is read by a callback in the order shown in the catalogue.
→ [reference/NETWORKING_ANALYSIS.md](reference/NETWORKING_ANALYSIS.md) §8 and the direct sub-sync catalogue.

Sub-syncs the RETR0 server answers today:

| Type / param | Name | Server behaviour |
|---|---|---|
| 13 / 448 | FileManager | Pushes published files (seed files) when versions differ |
| 10631 / 5245 | Game config | Seed defaults from your own `CC_SeedData.bin` |
| 10712 / 4373 | Server variables | Configurable list (empty by default) |
| 10660 / 5638 | Cloud-save upload request | Returns a local upload URL (`/retr0/cloudsave/…`) |
| 10555 / 5757 | Cloud-save validate | "valid" |
| 10768 / 0 | PvP servers | Empty list |
| 10480 / 5610 | Fetch gifts | From a local admin queue (parked, [features/gifts.md](features/gifts.md)) |
| 10481 / 1 | Claim gifts | Marks gifts delivered |
| 10632 / 2369 | Racing code | Accepts every code (the client uses it to set the player name) |
| anything else | | Empty part |

## 6. Authentication

The full **federated** auth flow (auth request, member id + token in the reply, token in later syncs) is decoded and
implemented in the server ([reference/NETWORKING_ANALYSIS.md](reference/NETWORKING_ANALYSIS.md) NW-80..NW-83).
This 14.0.1 client, however, runs as a **guest**: its log says `CC_SYNC_MANAGER_AUTHENTICATION : DISABLED` and
`Member is guest`, it never sends an auth request, and its batches carry the legacy auth extension. The server
accepts that and answers.

## 7. Example: the racing code (10632 / 2369)

```
request:  lp code
reply:    lp code (must equal the sent code) · bool32 ok · [if ok] lp reward list
          ok=1 → "code accepted" popup; ok=0 → "incorrect code"; empty part → "Connection error"
```
