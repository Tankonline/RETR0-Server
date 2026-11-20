# 07 · The RETR0 server

Everything runs on your PC and listens on `127.0.0.1` only. It is plain Python 3 (standard library), controlled by
one PowerShell script.

## 1. Request path

```
 RR3 (RETR0 client) on the emulator
   │  native hook before HttpRequest.init: CloudCell / CDN host
   │      ──► http://127.0.0.1:8780/_retr0host/<original host><path>
   │      (the 0.1.0 Java client and the Frida hook send /<path> + header X-RETR0-Host instead)
   │  any DNS lookup ──► emulator resolver ──► PC 127.0.0.1:53 (dns service: logs, answers NXDOMAIN)
   ▼
 adb reverse tcp:8780 tcp:8780
   ▼
 PC: cdn service (recorder_server.py) on 127.0.0.1:8780
   ├─ host firemonkeys.akamaized.net  ──► file from cdn\rr3\live\… with HTTP Range (206)
   ├─ POST /time                      ──► 200 + X-Request-Start: <Unix seconds>
   ├─ POST /CC_Sync.php               ──► (with -WithSync) forwarded to the sync service on 127.0.0.1:8781
   └─ anything else                   ──► 404, recorded
```

## 2. Services

| Service | Program | Port | Started |
|---|---|---|---|
| `dns` | [`services/dns_logger.py`](../server/services/dns_logger.py) | UDP 127.0.0.1:53 | always |
| `cdn` | [`services/recorder_server.py`](../server/services/recorder_server.py) `--rules config/rules_cdn*.json` | TCP 127.0.0.1:8780 | always |
| `sync` | [`services/local_service/retr0_local_service.py`](../server/services/local_service/retr0_local_service.py) | TCP 127.0.0.1:8781 | with `-WithSync` |

- **dns** logs every hostname the emulator looks up to `runtime/dns_queries.jsonl` and answers none, so nothing
  can reach a real server by name.
- **cdn** is a rule-driven HTTP server. It takes the original host from a `/_retr0host/<host>/` path prefix (the
  native client) or the `X-RETR0-Host` header (Java client, Frida), routes on that host and the path, serves pack files with
  byte ranges, answers `/time`, forwards sync, and records every request (headers and bodies) to
  `runtime/recorder/`. Rules: [`config/rules_cdn.json`](../server/config/rules_cdn.json) (assets only) and
  [`config/rules_cdn_sync.json`](../server/config/rules_cdn_sync.json) (assets + sync).
- **sync** is the CloudCell replacement: it unboxes each batch, dispatches each sub-sync to a handler (or answers
  an empty part), builds the reply with the member header, and boxes it. Its state (member ids, tokens, cloud saves,
  published files, held gifts) lives in `runtime/sync_data/state.json`. It reads seed defaults from
  `data/CC_SeedData.bin`.
- **codec**: [`services/cloudcell_codec/`](../server/services/cloudcell_codec/) implements the boxing, the sync
  request/reply formats and every decoded sub-sync payload. It is shared by the sync service and the tests.

### Local admin endpoints (sync service, 127.0.0.1 only)

| Endpoint | Purpose |
|---|---|
| `PUT/GET /retr0/cloudsave/<member>/<key>` | Cloud-save blobs, at the URL the server hands out |
| `POST /retr0/admin/gift?product=<id>` | Queue a gift (catalogue currency ids only). **Parked**, see [features/gifts.md](features/gifts.md) |

## 3. Folder layout

```
server/
  retr0_server.cmd / .ps1     start | stop | status | restart   [-WithSync]
  client.ps1                  status | apply | restore | install-fresh | play   (the RETR0 client on the emulator)
                              ui-text | ui-text-restore   (button text: "Change Username (Restart Required)")
  play.cmd                    = client.ps1 play
  store_grant.ps1             old name, forwards to client.ps1
  config/                     recorder rules
  services/                   dns_logger.py, recorder_server.py, local_service/, cloudcell_codec/, seed_data_decode.py
  tools/                      asset_pack_build.py, make_edited_res_zip.py, apply_edited_lists.py
  ── created by you (never committed) ──
  python/                     a Python 3 venv                      (py -3 -m venv server\python)
  data/CC_SeedData.bin        from your own game install
  cdn/rr3/live/…              asset packs built from your own data
  client/                     edited res.zip and lists; client/apk/ your built RETR0 client APKs
  runtime/                    pid files, logs, recordings, sync state
```

## 4. Control script

- `start` starts each service hidden, records its PID, and waits until the port really listens. It refuses a port
  another program holds and names that program.
- `stop` stops only what it started (including the child process of the venv launcher).
- `status` shows each service, a live HTTP check and the number of packs.

## 5. Troubleshooting

| Symptom | Look at | Usual cause |
|---|---|---|
| `start` says a port is in use | its message | Another program holds 53/8780/8781 |
| Game shows **OFFLINE** | `runtime/sync.log` | Server started without `-WithSync`, or the client isn't the RETR0 client |
| "An internet connection is required" on events | `client.ps1 status` | The game isn't connected (not the RETR0 client, or no `adb reverse`): use `play.cmd` |
| "Connection error" after a sync feature | `runtime/sync.log` | A server older than the member-header fix |
| Download stalls with `didn't match its MD5` | logcat | A listed file isn't byte-exact: rebuild with `--drop-unavailable` |
| 404 for a pack | `runtime/recorder/requests.jsonl` | That list's pack is missing from `cdn/` |

Every hostname the game tried is in `runtime/dns_queries.jsonl`; every request it made is in `runtime/recorder/`.
