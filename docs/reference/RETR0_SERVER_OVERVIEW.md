# RETR0 Server: Overview, How It Works, How To Run It

Last updated: 2026-11-18 · Status: **asset downloads work end to end from a fresh install; with `-WithSync`, `/time` and `CC_Sync.php` are answered and the game is no longer OFFLINE (runs 12–13). Most sub-syncs still get empty answers.**

This page is the overview. Details live in:
- `07_DOCUMENTATION/ASSET_DOWNLOAD_PROTOCOL.md`: the download protocol (AD-01..AD-11, with evidence)
- `08_TESTING/RUNTIME_TEST_PLAN.md` §4d, §4e, §9: emulator setup, tools, every test run
- `D:\RETR0_Server\README.md`: the package's own quick guide

---

## 1. What it is

Real Racing 3's official online services shut down on 20 March 2026. A fresh install of the game then can't download its ~1.5 GB of content and can't sync. The **RETR0 server** is an independently operated replacement that runs on this Windows PC:

- It serves the game's **asset downloads**, built from the owner's own copy of the game data.
- It **records** every request the game makes, which shows what the rest of the server must do.
- It **logs every hostname** the game looks up, and answers none of them, so nothing reaches EA.
- It can run an early **CloudCell sync** service. This is optional and not yet tested with the game.

Ground rules (from `CLAUDE.md`):
- Everything listens on `127.0.0.1` only. The server contains no EA code and never contacts EA infrastructure.
- The APK and `00_ORIGINAL` are never modified.
- Game content is built only from the owner's data and is never published.

## 2. The pieces

| Piece | Where | Role |
|---|---|---|
| **Server package** | `D:\RETR0_Server\` | Everything the server needs in one folder (§4) |
| Test emulator | AVD `RETR0_x86_64_34` (Android 14 x86_64, Google APIs, rooted, 10 GB RAM, 6 cores max) | Runs the unmodified RR3 14.0.1 APK; ARM code runs through Android's translator |
| Network lock | `08_TESTING/runtime/avd_network_lock.sh` | Blocks all emulator traffic except loopback, replies and DNS to the PC |
| Redirect hook | `08_TESTING/runtime/retr0_redirect_java.js` (Frida 17.27.0) | Rewrites the game's CloudCell and CDN requests to `http://127.0.0.1:8780`, and records them |
| Session runner | `08_TESTING/runtime/capture_run.py` | Starts the game under the hook for N minutes (`--minutes 0` = until the game exits; `play.cmd`) and saves the logs |
| Pack builder | `SCRIPTS/asset_pack_build.py` (copy in `D:\RETR0_Server\tools\`) | Builds the CDN packs from the owner's data |

## 3. How it works

### 3.1 Request path

```
 RR3 on the emulator
   │  Java HttpRequest.init(url) ── Frida hook (redirect) ──► http://127.0.0.1:8780/<path>
   │                                                            + header X-RETR0-Host: <original host>
   │  DNS lookups (any code) ──► emulator resolver 10.0.2.3 ──► PC 127.0.0.1:53 (dns_logger: NXDOMAIN)
   ▼
 adb reverse tcp:8780 tcp:8780  (over the adb link; the network lock leaves it open)
   ▼
 PC: recorder_server.py on 127.0.0.1:8780
   ├─ host firemonkeys.akamaized.net ──► file from cdn\rr3\live\... with HTTP Range (206)
   ├─ CC_Sync.php ──► (only with -WithSync) proxy to retr0_local_service.py on 127.0.0.1:8781
   └─ anything else ──► 404, recorded
```

The hook is in Java because the game's ARM engine code runs through Android's ARM translator on this x86_64 emulator, and Frida can't hook translated code. CloudCell's native layer sends all its HTTP through the Java class `com.firemonkeys.cloudcellapi.HttpRequest` (NW-01). That includes sync, the asset manager and CDN downloads.

### 3.2 How the asset download works (summary of ASSET_DOWNLOAD_PROTOCOL.md)

1. On first launch the game unpacks `res.zip` from the APK into `files/apk/res/`. It contains **1,236 asset lists**, each line being `/path<TAB>md5<TAB>stored size<TAB>size`.
2. For each list the game requests `https://firemonkeys.akamaized.net//rr3/live/<list name>/<MD5 of the list file>.bin`.
3. That pack holds every list entry, **in list order**, each as `u32 key`, `u32 length`, then the stored bytes:
   - `key` = djb2 hash of the path, modulo `0x106d643d`;
   - the stored bytes are the file itself, or `"FMASZ1"` + zlib-compressed file (classic zlib, default level).
4. It downloads byte ranges: small entries batched up to 512 KB, big files in equal parts. It checks each file's **MD5 against the list**, unpacks `FMASZ1`, and retries a failed file 8 times.

Evidence:
- **Code:** list parser `0x1cd3a54`, downloader `0x1cd691c`, data callback `0x1cd96fc`, key hash `0x1cd0c00`, MD5 check `0x1cdc7ac`, `FMASZ1` unpacking `0x1cdd760`.
- **Recordings:** 285 of 285 recorded byte ranges and 1,129 of 1,129 recorded keys match the model.
- **Rebuilds:** 445 of 445 compressed files rebuilt byte-identical from the owner's data.

### 3.3 Why there are "edited" lists

The game accepts a file only if its MD5 matches the list exactly. Some originals are missing from every copy of the game data on this PC:
- ~1,767 ETC textures, which were replaced by `.rgb.pvr.z` versions;
- some limited-time GUI art;
- low-detail track variants;
- a few files changed by later updates.

So, **on the test device only**:
- `asset_pack_build.py --drop-unavailable` writes **edited lists** without the entries we can't reproduce, and builds the packs from those lists. The pack names change to the edited lists' MD5s.
- The game re-extracts `files/apk/res.zip` on **every** launch, and replaces `res.zip` from the APK whenever its length differs from the APK's copy (AD-11). So the edited lists go inside an **edited `res.zip` of exactly the same length** (`make_edited_res_zip.py`).
- `apply_edited_lists.py` adds the owner's RGB versions of the dropped ETC textures, which is what the owner's own install used.

Effect: the download completes with no errors. The game simply doesn't have the dropped files.

## 4. The server package: `D:\RETR0_Server`

```
D:\RETR0_Server\
  retr0_server.cmd / .ps1   start | stop | status | restart  [-WithSync]
  README.md, OVERVIEW.md
  config\    rules_cdn.json, rules_cdn_sync.json
  services\  recorder_server.py, dns_logger.py, local_service\, cloudcell_codec\, seed_data_decode.py
  cdn\       rr3\live\<list>\<md5>.bin   (1,236 packs, 5.4 GB)
  client\    res.zip (edited, length-matched), lists\, *.report.tsv
  data\      CC_SeedData.bin
  tools\     asset_pack_build.py, make_edited_res_zip.py, apply_edited_lists.py
  python\    private Python 3.14 (standard library only)
  runtime\   *.pid, *.log, dns_queries.jsonl, recorder\requests.jsonl (+ bodies\), sync_data\
```

| Service | Program | Port | Started by default |
|---|---|---|---|
| `dns` | `services\dns_logger.py` | UDP 127.0.0.1:53 | yes |
| `cdn` | `services\recorder_server.py --rules config\rules_cdn.json` | TCP 127.0.0.1:8780 | yes |
| `sync` | `services\local_service\retr0_local_service.py` | TCP 127.0.0.1:8781 | only with `-WithSync` (and then `cdn` uses `rules_cdn_sync.json`) |

The control script:
- **`start`** starts each service hidden, records its PID, and waits until the port is really listening. It refuses a port that another program holds, and names that program.
- **`stop`** stops only what it started, including the child process the venv's Python launcher creates.
- **`status`** shows each service, a live HTTP check and the pack count.

## 5. How to run it

### 5.1 One-time setup (already done on this PC)

| Requirement | Notes |
|---|---|
| Hardware acceleration | Windows Hypervisor Platform enabled; `bcdedit` `hypervisorlaunchtype` = `Auto`. LDPlayer may switch it `Off`; then run `bcdedit /set hypervisorlaunchtype auto` as admin and restart |
| Android SDK + emulator 37.2.13 | `%LOCALAPPDATA%\Android\Sdk`; image `system-images;android-34;google_apis;x86_64` |
| AVD `RETR0_x86_64_34` | 10 GB RAM, 576 MB heap, 32 GB data, host GPU. The emulator caps a device at 6 cores |
| Frida | `frida` 17.27.0 + `frida-tools` in the project `.venv`; `frida-server` x86_64 at `TOOLS/FRIDA/17.27.0/` (pushed to `/data/local/tmp/frida-server`) |
| Classic zlib (only for building packs) | MSYS2 `C:\msys64\ucrt64\bin\zlib1.dll` (Python's zlib-ng gives different bytes) |
| APK install copy | `08_TESTING/runtime/out/apk/rr3_14.0.1_install_copy.apk` (SHA-256 `dcfe3788…1d5f`, same as the original) |

### 5.2 Normal session (game already installed and set up)

```
D:\RETR0_Server\retr0_server.cmd start -WithSync
emulator -avd RETR0_x86_64_34 -no-snapshot-load -no-boot-anim -gpu host -dns-server 127.0.0.1
bash 08_TESTING/runtime/avd_network_lock.sh lock --allow-dns
.venv\Scripts\python -I 08_TESTING\runtime\capture_run.py --mode redirect --minutes 60
...
D:\RETR0_Server\retr0_server.cmd stop
```

`capture_run.py` refuses to start unless the emulator is locked. It starts `frida-server` if needed, sets `adb reverse tcp:8780 tcp:8780`, launches the game under the hook, and saves `requests.jsonl`, `frida.log`, `logcat.txt` and a screenshot per minute under `08_TESTING/runtime/out/<time>_redirect/`. When the time runs out, Frida detaches and the redirect stops, **but the game keeps running**. Every request then fails with `Unable to resolve host "0037-connect.cloudcell.com"`, and online-gated screens lock: Grand Prix Special Events show "An internet connection is required to access this feature" (run 24). For research sessions `--minutes 0` keeps the hook attached until the game exits. **For playing, Frida is no longer needed:** the RETR0 client APK has the redirect built in (§9); start it with `D:\RETR0_Server\play.cmd`.

### 5.3 Fresh install (test from zero)

1. `adb uninstall com.ea.games.r3_row`, then `adb install 08_TESTING\runtime\out\apk\rr3_14.0.1_install_copy.apk`.
2. Launch the game once without the hook. It extracts `files/apk/` within seconds. Then stop it (`adb shell am force-stop com.ea.games.r3_row`).
3. Push the edited `res.zip`, and give it to the app's user id (shown by `dumpsys package com.ea.games.r3_row | grep appId`):
   `adb push D:\RETR0_Server\client\res.zip /sdcard/Android/data/com.ea.games.r3_row/files/apk/res.zip`, then as root `chown <appId>:1078 …/res.zip && restorecon …/res.zip`.
4. Add the RGB substitutes: `tools\apply_edited_lists.py apply --edited client --data <owner .depot> [--data <fallback .depot>]`.
5. Run a session as in 5.2. The game should request the edited base pack `a63159ce…` and download from 0%.

Pushing `res.zip` *before* the first launch doesn't work: the game wipes `files/apk/` while `checksum.md5` is missing.

### 5.4 Rebuilding the packs (after changing the source data)

```
.venv\Scripts\python -I SCRIPTS\asset_pack_build.py --apk 00_ORIGINAL\APK\real-racing-3-14-0-1.apk --list all ^
    --drop-unavailable --lists-out <out>\lists --data <owner .depot> [--data <fallback .depot>] --out <out>
.venv\Scripts\python -I 08_TESTING\runtime\make_edited_res_zip.py --apk 00_ORIGINAL\APK\real-racing-3-14-0-1.apk ^
    --lists <out>\lists --out <out>\res.zip
```

Then copy `<out>\rr3\live` to `D:\RETR0_Server\cdn\rr3\live` and the new `res.zip` and lists to `client\`. Building all lists takes about 15 minutes.

**Serving modified files:** add `--modified-data <folder>`, a folder holding your changed files at their `.depot`-relative paths (it can also be a full modified `.depot`). Every listed file found there that differs from the original replaces it in the pack, and the edited list gets that file's own MD5 and sizes, so the game's MD5 check passes. Compressed entries are re-packed as `FMASZ1` + zlib. Then rebuild `res.zip` and push it to the emulator: the game sees the changed list entries and downloads just those files again. Tested 2026-11-19 on a plain (`.nct`) and a compressed (`0.dat`) entry: only that list line changes, and the packed entry unpacks to the modified file.

### 5.5 Undo on the emulator

`apply_edited_lists.py restore` puts the original lists back from `/data/local/tmp/retr0_res_backup/`. Copy `/data/local/tmp/retr0_res_backup/res.zip` back to `files/apk/res.zip`. Or simply uninstall and reinstall the game.

## 6. Where to look when something goes wrong

| Symptom | Look at | Usual cause / fix |
|---|---|---|
| `start` says a port is in use | its message names the program | Stop that program, or `retr0_server.cmd stop` |
| Emulator very slow; `accel-check` exit 6 | `emulator -accel-check` | Hypervisor not running (§5.1) |
| Game asks for `asset_list_base/10a2829c…` (original) instead of `a63159ce…` | `runtime\recorder\requests.jsonl` | The original `res.zip` came back; redo §5.3 step 3 |
| Download stalls; `didn't match its MD5` in logcat | session `logcat.txt` | A file that isn't byte-exact is still listed: rebuild with `--drop-unavailable` |
| 404 for a pack | `runtime\recorder\requests.jsonl` | That list's pack is missing from `cdn\` |
| Redirect stopped mid-session | `frida.log` | The session's `--minutes` ran out: start a new session |
| App closes with `SIGTRAP` / "Render process … crash" | session `logcat.txt` | A WebView renderer crash (ads/consent pages offline), seen at 6 GB RAM; now 10 GB |
| Game shows **OFFLINE** | `runtime\sync.log`, requests to `CC_Sync.php` | Start the server with `-WithSync`; check `sync.log` for `bad request` lines |

Every hostname the game tried is in `runtime\dns_queries.jsonl`. Every redirected request (headers and bodies) is in `runtime\recorder\`.

## 7. Status and next steps

| Area | State |
|---|---|
| CDN asset download | **Working** from a fresh install, 0 download errors (runs 9, 11) |
| Request recording, DNS logging | Working |
| Server package, start/stop | Working (`D:\RETR0_Server`) |
| `/time` | **Working**: HTTP 200 + `X-Request-Start: <Unix seconds>` (recorder rule) |
| `CC_Sync.php` (`-WithSync`) | **Accepted**: the guest client's batches (legacy auth header) are parsed and answered; the game shows online. Most sub-syncs answered with empty parts |
| `assetManDownloadPackHash.php` (CloudCell download fallback) | Request format known (AD-09); reply format unknown |
| Serving modified files | Not yet (§5.4) |
| Glu, Firebase, Facebook and other SDK hosts | Not served; the game carries on without them |
| Username (Profile, race results) | **Working**: Enter Racing Code sets it; applies after a restart (§10) |
| Sync reply member header | **Fixed 2026-11-20** (§10); before, every non-empty sub-sync reply was misread |
| Game ↔ server connection without Frida | **Working** with the RETR0 client APK (§9, run 25) |
| Store BUY (currency packages + currency packs) | **Working** with the patched game (§8): grants through the game's own non-purchase award, survives a restart (runs 21-23) |

Next: decide which sub-syncs need real answers (career/progress saves, events, store), then the MD5-from-data mode for modified files.


## 8. Store preservation grants (patched game)

**What it does.** In the test build, BUY on a Store currency package or currency pack gives that product's contents straight away, as a free preservation grant. The amount and contents come from the game's own store catalogue and pack data (seed file 12), never from user input. No Google Play call, receipt, Nimble transaction or purchase record is made, and the pack-purchase analytics event is skipped.

**How.** Two instructions of `lib/arm64-v8a/libRealRacing3.so` are changed into branches to a 560-byte handler placed in unused zero padding (va `0x9876c8`):
- `NimbleMTX::PurchaseStoreProduct` (`0xb8d6e4`) for the currency packages;
- `PackManager`'s pack purchase (`0x13ef7e8`) for the packs. Its Google Play check is what showed "To access the Store please sign into a valid Google Play Store account".

For an allow-listed product id the handler:
1. looks the product up in the game's static store;
2. parses its catalogue metadata into a reward;
3. awards it with `MTXManager` (`0xb873c0`/`0xb879fc`) using the non-purchase flag, the same call the game's free offerwall-reward claim uses;
4. flags a save and logs `RETR0 preservation grant: store product N awarded=1 (no purchase)`.

Any other product id runs the original code unchanged. Source: `06_RECONSTRUCTION/APPLICATION/store_grant_patch/` in the project (`store_grant_patch.S`, `build_patch.py`, which builds from the original APK and never modifies it). Full findings: `07_DOCUMENTATION/STORE_PRESERVATION_GRANTS.md` (SP-12..SP-15).

| Product | Ids |
|---|---|
| Gold | 10051-10056 (16 / 42 / 87 / 183 / 476 / 1,019), 10057 (1,019) |
| R$ | 10045-10050 (50k / 140k / 300k / 700k / 2M / 5M) |
| M$ | 10461-10466 (45k / 115k / 250k / 520k / 1.35M / 3M) |
| Packs | Starter 10061, Booster 10062, Turbo 10063, Enhancer 10988, Charger 10989 |

**Using it.** The game must be the patched build; the server needs nothing extra (grants work offline too).

| Command | Effect |
|---|---|
| `store_grant.ps1 status` | Shows which APK the emulator runs (by SHA-256) |
| `store_grant.ps1 apply` | Stops the game; swaps the installed `base.apk` for `client\apk\rr3_14.0.1_store_grant_test.apk` in place, keeping owner, mode, SELinux label and timestamp. **Game data and downloads are kept** |
| `store_grant.ps1 restore` | The same with the original APK |
| `store_grant.ps1 install-fresh` | Uninstalls (deletes data, asks first) and installs the debug-signed patched APK; then follow §5.3 |

The in-place swap works because the game loads its libraries straight out of `base.apk` (`extractNativeLibs=false`), and Android does not re-check the APK signature at app start. The patched APK keeps the original's size and layout; only the library bytes and its zip CRC differ.

**Not yet verified:** that the swap survives an emulator reboot (Android could rescan the APK; if the game then fails to start, run `restore` or `apply` again); a real install of the debug-signed APK; and Gold 87-1,019, R$ 50k/300k-5M and M$ 45k/115k/520k-3M individually (the same code path as the tested ones).

**Server-side gift channel (not needed for BUY).** The sync service also answers sub-sync 10480 (FetchAdHocGifts) from a local-only admin queue (`POST http://127.0.0.1:8781/retr0/admin/gift?product=<id>`, catalogue currency ids only). The game stores such a gift as an unclaimed offerwall reward and credits it only after a UI claim. Two test gifts froze the game for unknown reasons, so both are held (`runtime\sync_data\state.json`, `gifts.held`); do not queue more until that is understood (SP-11, SP-12).


## 9. RETR0 client: everything from this server, no Frida (2026-11-19)

**Why.** Until now the game reached this server only while a Frida hook from the project repo (`capture_run.py --mode redirect`) was attached. When a timed session ended, the hook detached but the game kept running; every request then failed (`Unable to resolve host "0037-connect.cloudcell.com"`) and online screens locked. Grand Prix Special Events, for example, said "An internet connection is required to access this feature" (run 24).

**What.** `client\apk\rr3_14.0.1_retr0_client.apk` is the original 14.0.1 APK with:
1. the store preservation grants (§8, same native library bytes);
2. the redirect built into the Java class every CloudCell request goes through (`com.firemonkeys.cloudcellapi.HttpRequest.init`). Its first instruction calls `com.retr0.Redirect.rewrite(url)`: a URL on `*.cloudcell.com`, `*.exos.fm` or `firemonkeys.akamaized.net` becomes `http://127.0.0.1:8780<path+query>`. Before returning, it calls `Redirect.finish(this)`, which adds `X-RETR0-Host: <original host>` (the CDN rules route on it). Every other URL is unchanged. This is the same behaviour as the Frida hook's redirect mode, minus the logging.

`adb reverse tcp:8780 tcp:8780` carries 127.0.0.1:8780 on the emulator to this server. Source: `tools\local_server_redirect\` (`Redirect.smali`, `build_redirect_dex.py`) and `tools\store_grant_patch\build_patch.py` (copies of the project's `06_RECONSTRUCTION/APPLICATION/`).

| Command (in `D:\RETR0_Server`) | Effect |
|---|---|
| `retr0_server.cmd start -WithSync` | start the server (as before) |
| `play.cmd` (= `client.ps1 play`) | checks the emulator runs the RETR0 client, sets `adb reverse`, starts the game. It stays connected until you close it |
| `client.ps1 status` / `apply` / `restore` | which APK is installed / swap in the RETR0 client / swap the original back, in place, keeping data; then `cmd package compile -m verify` so Android recompiles the changed code |
| `client.ps1 install-fresh` | uninstall (asks first) and install `rr3_14.0.1_retr0_client_signed.apk` (debug-signed) |

`store_grant.ps1` still works and forwards to `client.ps1`.

**Tested (run 25):** the in-place swap, the launch with nothing attached, `/time` and `CC_Sync` `Succeeded=True`, and the server log showing the requests with `X-RETR0-Host`. The owner confirmed that Grand Prix Special Events open and Store BUY grants work under the client. **Not yet verified:** the signed APK install; the asset CDN download path through the built-in redirect on a fresh install; the emulator still needs its network lock and `adb reverse` after every emulator restart (`play.cmd` sets the reverse each time).


## 10. Username and the sync reply fix (2026-11-20)

**Username.** The game shows "Guest" as your name (Profile title, race results) because no Facebook/Google sign-in exists. The RETR0 client replaces it with a name of your choice:
1. Settings → **Enter Racing Code** → type the name (a leading `NAME ` is optional) → "code accepted".
2. Close the game and start it again (`play.cmd`). The name now shows wherever the game asks for your name.

The client writes the name to `files/doc/retr0_username.txt` on the device (next to the save, but a separate plain-text file; delete it to go back to "Guest"). It reads the file once per start. Codes the game already sent are refused ("already entered"); type the name with different capitals to reuse it. Because every racing code now means "set my name", this server hands out no racing-code rewards. Details: `07_DOCUMENTATION/SAVE_SYSTEM_ANALYSIS.md` SV-27.

**Sync reply fix.** Every sync reply needs a member header (member id, developer flag, device id and two more fields) between its first two fields and the sub-sync replies. The service did not send it, so the game read the first reply bytes as that header: harmless while replies were empty, but any real reply (the racing code, the gifts) arrived empty or garbled. The service now sends it. This is the likely cause of the earlier gift freezes (§8); gifts stay held until that is re-tested. Details: `NETWORKING_ANALYSIS.md` NW-93.
