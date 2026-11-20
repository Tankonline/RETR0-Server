# Runtime Test Plan — original client against the RETR0 local service

Status: **PLAN, PARTLY APPROVED, NOT RUN.** Redirection option **A (Frida hook) chosen by the owner on 2026-11-15**. The remaining items in §8 must still be confirmed before anything runs on a device. Written 2026-11-15.

## 1. Goal

Find out, on a device the owner controls, whether the unmodified Real Racing 3 14.0.1 client accepts the independently operated local service (`06_RECONSTRUCTION/BACKEND/local_service/`):

| Level | Pass when | Evidence |
|---|---|---|
| L1 | The client's auth POST reaches the service and the client accepts the reply | Service log `auth: state=…`; logcat `CC: AUTH INFO [MemberId: …]` then state `AUTHENTICATED` |
| L2 | The first batched sync is answered and the client continues without a crash | Service log lists the sub-syncs; logcat `CC: [%d] Sync response received`; no crash |
| L3 | The front end stays usable for 10 minutes (menus, garage, starting an offline race) | Screen recording; no crash; logcat |
| L4 | A cloud-save upload arrives as an HTTP PUT | File under `<data-dir>/cloudsave/` |

Every failure is a result too: the service log and logcat show which sub-sync or field the client rejected, and that feeds the next handlers.

## 2. What the static analysis says (pre-flight, already done)

| Fact | Consequence | Ref |
|---|---|---|
| Sync and auth go to `https://<SyncDomain>/CC_Sync.php`. The port is the constant **443** in `.rodata` (`0x5ff3d4`), and the request object uses TLS exactly when the port is 443 (`0x1c754a0`) | The service must speak **HTTPS** on whatever the client connects to | NW-85 |
| The CloudCell Java TLS path accepts **any certificate and any hostname** | A self-signed certificate generated locally is enough. No CA install on the device | K-16 |
| The domain comes from a **fixed table** (`GetDefaultDomain` `0x1cf098c`): environment 0…6 → `0037-connect`, `-stage`, `connect-dev-ss`, `-lt`, `connect-sandbox`, `-be`, `stage-connect.rr3.exos.fm`. The debug "Save CC Server?" cheat only switches between these | The unmodified client **cannot be pointed at a custom host** from inside the game. Some redirection is required (§4) | NW-85 |
| `localhost`/`127.0.0.1` strings in the binary belong to libcurl, not to a game environment | No hidden local-development environment | NW-85 |
| Cleartext HTTP is allowed only to `127.0.0.1` | Irrelevant for sync (HTTPS), relevant if a hook changes the port | NW-08 |

## 3. Test environment

- **Device:** an emulator or phone owned by the project owner, used only for this test. The game data path (`<emulator data folder>`) suggests LDPlayer 9 [inferred from the folder name, not verified]. LDPlayer is x86_64 and runs the ARM libraries through binary translation, which matters for option A below.
- **APK:** install from a *copy* of `00_ORIGINAL/APK/real-racing-3-14-0-1.apk`. Verify the SHA-256 against `00_ORIGINAL/METADATA/CHECKSUMS.sha256` before and after. Never modify the original.
- **Saves:** fresh install, or **test copies** of saves. Back up `/data/data/com.ea.games.r3_row` and the `.depot` folder (e.g. `adb backup` or copying files out, if the device allows it) before the first run. The owner's real saves stay untouched.
- **Network:** the device must not reach EA infrastructure during the test. EA's services are shut down, but the test must not depend on that. Disable the emulator's internet access or block outbound traffic except to the host machine.
- **Host:** the service runs on the development PC with `--tls-cert/--tls-key`, logging to a file.

## 4. Redirection options (owner must choose one)

| | A. Runtime hook (Frida) | B. Hosts-file redirect | C. Patched private copy of the APK |
|---|---|---|---|
| How | Hook `GetDefaultDomain` (`0x1cf098c`) or the SyncDomain setter (`0x1d02804`) to return `127.0.0.1`, and the request port (`0x1c754a0` arg 5) to `8443`. `adb reverse tcp:8443 tcp:8443` forwards to the PC | On a rooted test device, add `<host-ip> 0037-connect.cloudcell.com` (and the environment actually in use) to `/system/etc/hosts`; service on port 443 | Replace the domain string in a copy of `libRealRacing3.so`, re-sign the copy, install it on the test device only |
| Files changed | None (in-memory, per session) | Device hosts file only | A modified copy of the app (never distributed) |
| Endpoint identity | Own endpoint (`127.0.0.1`), **no EA hostname used** | The client still asks for an **EA hostname** that resolves to the local service | Own endpoint |
| Needs | Root or `frida-server` on the device. **ARM code under LDPlayer's translation layer usually cannot be hooked**: needs a real ARM device or an ARM emulator image | Root (LDPlayer offers a root toggle); port 443 reachable (run the service as admin on 443, or forward) | Re-signing; string length limits; Play Integrity and anti-tamper may react (BanningManager/PiracyManager untested) |
| Project-rule fit | Best fit with "independently operated, own endpoints" | Conflicts with "do not impersonate EA services" unless the owner decides a private, offline test device is acceptable | Acceptable as an experiment on a copy (§3 of CLAUDE.md), but produces a modified binary |
| Recommendation | **Preferred**, if an ARM device is available | Only with an explicit owner decision | Fallback |

## 4b. Option A in detail (chosen)

Hook script: `08_TESTING/runtime/retr0_redirect.js` (reviewed statically, syntax-checked, **not run**).

- Target: `libRealRacing3.so` + `0x1c754a0`, the request builder `build(out, method, host, path, port, tls, flag)`. The argument order was confirmed at the sync sender `0x1d03520` (`x1` "POST", `x2` SyncManager `+0x90`, `x3` "CC_Sync.php", `w4` port). The URL is assembled by `0x1c756d8` as `(port == 443 ? "https://" : "http://") + host + ":" + port + "/" + path` (NW-86).
- In `redirect` mode, only calls with path `CC_Sync.php` and a CloudCell host are changed: host → `127.0.0.1`, port → `8780`. The game then posts to `http://127.0.0.1:8780/CC_Sync.php`; cleartext to `127.0.0.1` is allowed by its network config, so **no certificate is needed for option A**.
- In `log` mode (the default), nothing is changed: each request's method, host, path and port are printed.
- Guards: the script refuses to act unless the process is arm64 and the 16 bytes at the target equal `fc6fbaa9fa6701a9f85f02a9f65703a9` (the analysed build, library SHA-256 `57edb631…5aa73051`).
- **Device requirement:** an arm64 Android device or arm64 emulator image with `frida-server` (root). x86_64 emulators such as LDPlayer run ARM code through binary translation; the script detects a non-arm64 process and refuses.
- The armv7 build is not supported by this script (different addresses).

### 4c. Device attempts (2026-11-15)

| Device | Result |
|---|---|
| Samsung Galaxy S26 Ultra (owner's phone) | Not used: frida-server needs root, and rooting trips Knox permanently. A Frida-Gadget copy of the app would avoid root but means installing a re-signed copy on a daily phone; the owner chose an emulator instead |
| Android Emulator 37.2.13 + `system-images;android-27;google_apis;arm64-v8a` (r03, SHA-1 `54dd140e…d171`, downloaded from dl.google.com with approval; AVD `RETR0_arm64_27`) | **Does not start:** `FATAL | QEMU2 emulator does not support arm64 CPU architecture`. The current emulator cannot run arm64 images on an x86_64 Windows host at any API level |
| LDPlayer / x86_64 AVD (`Pixel_8`, API 37, 16 KB pages) | ARM code runs through translation; Frida cannot hook it (the script refuses on a non-arm64 process) |

**Consequence:** option A needs real arm64 hardware (a spare arm64 phone, or an arm64 machine). Without it, the remaining route is option C (patched private copy, works under translation) on a fresh emulator instance that holds no real game data.

### 4d. Emulator route (owner chose an emulator, 2026-11-18)

**Java-level variant of option A.** CloudCell HTTP is performed in Java (`com.firemonkeys.cloudcellapi.HttpRequest.init(url, …)`, NETWORKING_ANALYSIS NW-01/NW-06). On an x86_64 emulator the Java layer runs natively (only the ARM `.so` code is translated), so Frida can rewrite the URL in Java even though it cannot hook the native `GetDefaultDomain`. This keeps option A's "no files changed" property without arm64 hardware. The hook script for this variant is **not written yet**; the existing `runtime/retr0_redirect.js` (native, arm64-only) stays as is.

Setup done 2026-11-18 (owner approved the installs):

| Item | Detail |
|---|---|
| System image | `system-images;android-34;google_apis;x86_64` r14 (dl.google.com, 1.5 GB zip, 4.2 GB unpacked). Google APIs (not Play Store), so `adb root` works; 4 KB pages; Android 11+ x86_64 images translate ARM apps |
| AVD | `RETR0_x86_64_34` (pixel_6 profile): 6 GB RAM, 8 cores, 32 GB data partition (room for the ~10 GB `.depot`), host GPU. Original `config.ini` kept as `config.ini.orig` |
| Hypervisor | **Missing on this PC** (`emulator -accel-check` exit 6; Windows hypervisor not present). The Android Emulator hypervisor driver installer (AEHD 2.2) is downloaded to `%LOCALAPPDATA%\Android\Sdk\extras\google\Android_Emulator_Hypervisor_Driver`; **the owner must run `silent_install.bat` as administrator** (kernel driver). Alternative: enable the Windows feature "Windows Hypervisor Platform" (reboot) |
| Frida (host) | `frida` 17.27.0 and `frida-tools` 14.13.2 in the project `.venv` (PyPI) |
| frida-server | `TOOLS/FRIDA/17.27.0/frida-server-17.27.0-android-x86_64` from the official GitHub release; xz SHA-256 `499874336ec3e8bc7c83fea0577b68a49c99239133ebcc60a717e21bce92dd4e`, binary SHA-256 `613cd3d7d2d16ac78b597c067f7b7cbe472433ac2ed6a62f5d3c1bbce54d1697` (ELF64 x86-64) |

**Acceleration fixed 2026-11-18.** Root cause from the Windows logs: the hypervisor last started on 16 Nov 18:46 and was not launched on any boot from 19:04 that day (no failure events, so the boot setting `hypervisorlaunchtype` was off; an emulator such as LDPlayer is the likely cause, not proven). Enabling *Windows Hypervisor Platform* set it back to `Auto` at 20:57, after that boot's launch point, so one more restart was needed. After the 21:15 restart: `HypervisorPresent = True`, `emulator -accel-check` → "WHPX(10.0.26300) is installed and usable". If LDPlayer turns Hyper-V off again, run `bcdedit /set hypervisorlaunchtype auto` (admin) and restart.

**Boot test passed 2026-11-18:** `RETR0_x86_64_34` boots in about 25 s; `ro.product.cpu.abilist = x86_64,arm64-v8a`; `ro.dalvik.vm.native.bridge = libndk_translation.so` (present in `/system/lib64`); Android 14; page size 4096; `adb root` gives `uid=0 … context=u:r:su:s0`; `/data` 31 GB free. **The AVD still has normal emulator networking (`eth0` 10.0.2.15)**: cut it (e.g. iptables in the root shell, allowing only loopback and the `adb reverse` port) before the game is ever launched. Nothing has been installed on it yet; it was shut down after the test.

**Network lock and Java hook written and dry-run 2026-11-18 (no game involved):**

| File | What it does | Test result |
|---|---|---|
| `runtime/avd_network_lock.sh` `lock\|unlock\|status` | Host-side; via `adb root` adds chain `RETR0_LOCK` first in `OUTPUT` (IPv4 + IPv6): loopback allowed, replies to inbound connections allowed, everything else `REJECT`. Not persistent: run `lock` after every boot. Probes are TCP only (`1.1.1.1:443`, `8.8.8.8:53`, `dns.google:443`); ICMP is useless because the emulator's user-mode network never answers ping | Before: all 3 probes reachable. After `lock`: all 3 blocked (rc 1), `adb shell` still works, `frida -U` still works |
| `runtime/retr0_redirect_java.js` | Hooks `com.firemonkeys.cloudcellapi.HttpRequest.init` (11-arg overload). `log` mode prints method/host/path of CloudCell requests only (no query, headers or body); `redirect` mode rewrites only CloudCell `…/CC_Sync.php` to `http://127.0.0.1:8780/CC_Sync.php` + original query. Refuses unless package `com.ea.games.r3_row` reports version 14.0.1 | frida-server 17.27.0 (on-device SHA-256 matches) runs as root; loading the script into `com.android.settings` gives the expected clean refusal (class not found). URL parsing/matching checked offline in Node: real CloudCell sync URLs matched, `…cloudcell.com.evil.net` and non-sync paths not matched, malformed input ignored |

Order for the first real run: boot AVD → `avd_network_lock.sh lock` → start frida-server → install a hash-checked copy of the APK (no real saves) → start the local service → `adb reverse tcp:8780 tcp:8780` → `frida -U -f com.ea.games.r3_row -l runtime/retr0_redirect_java.js` in `log` mode first.

Still to do: then the remaining §8 confirmations (network isolation, saves on test copies only). The 3.9 GB arm64 API-27 image/AVD that cannot boot is still on disk, awaiting the owner's decision to delete it.

### 4e. Capture and replay tools (2026-11-18)

Purpose: record exactly what the client asks for, then answer it from a server we operate, one endpoint at a time.

| Tool | Role |
|---|---|
| `runtime/dns_logger.py` | Host DNS server for the emulator (`-dns-server 127.0.0.1`): logs every lookup from any code, answers NXDOMAIN (nothing resolves) |
| `runtime/avd_network_lock.sh lock --allow-dns` | Blocks all emulator traffic except loopback, replies and DNS to the emulator resolver |
| `runtime/retr0_redirect_java.js` | Java hook on `HttpRequest.init/addHeader/post`. Modes: `log` (method/host/path only), `record` (full URL, headers and body per request as `RETR0JSON` lines), `redirect` (record + send every CloudCell host and `firemonkeys.akamaized.net` to `http://127.0.0.1:8780` with header `X-RETR0-Host`) |
| `runtime/capture_run.py --mode record\|redirect --minutes N` | One session: checks the lock, frida-server and (redirect) `adb reverse`; spawns the game under the hook; writes `requests.jsonl`, `bodies/`, `frida.log`, `logcat.txt`, a screenshot per minute and `summary.txt` to `runtime/out/<time>_<mode>/` (gitignored) |
| `runtime/recorder_server.py --rules R.json` | 127.0.0.1-only HTTP server for redirect mode: records every request (`requests.jsonl`, `bodies/`) and answers by the first matching rule: fixed `status`/`body`, `proxy` to another local server (e.g. `retr0_local_service.py --port 8781` for `CC_Sync.php`), or `dir` (serves files with `Range`/206); unmatched → 404. Example rules: `runtime/recorder_rules.example.json` |

Self-test (2026-11-18, host only): fixed answer 200, `Range: bytes=3-7` → 206 `Content-Range: bytes 3-7/16`, full file 200, out-of-range 416, `../` path escapes (literal and in a sub-path) → 404, unmatched path → 404; request bodies stored.

Typical loop: `dns_logger.py` → emulator with `-dns-server 127.0.0.1` → `lock --allow-dns` → `recorder_server.py --rules …` → `capture_run.py --mode redirect` → read `requests.jsonl` and the game's log → add or change one rule → repeat.

## 5. Procedure (option A)

1. **Device:** arm64 test device with `frida-server` running; app installed from a copy of the original APK (hash checked).
2. **Service** (host, plain HTTP is enough for option A):
   `.venv\Scripts\python -I 06_RECONSTRUCTION\BACKEND\local_service\retr0_local_service.py --data-dir <test-data> --port 8780 --public-base http://127.0.0.1:8780 --log-file <test-data>\service.log -v`
   (Options B/C would need HTTPS: generate a certificate with `openssl req -x509 … -addext "subjectAltName=IP:127.0.0.1"` and add `--tls-cert/--tls-key`.)
3. **Port forward** (device → host): `adb reverse tcp:8780 tcp:8780`.
4. **Hook:** `frida -U -f com.ea.games.r3_row -l 08_TESTING/runtime/retr0_redirect.js` with `MODE = 'log'`.
5. **Observe first, then change:** the log-only run records which hosts and paths the client actually uses (and logcat `Active Environment`, `updating SyncDomain to`). Only then set `MODE = 'redirect'` and start again.
6. **Logs:** `adb logcat -v time "CC Info:I" "CC Trace:I" "CC Error:E" "AndroidRuntime:E" "*:S" > logcat.txt`.
7. **Run** L1 → L4. Stop at the first crash and keep all logs.
8. **Restore:** stop Frida, `adb reverse --remove tcp:8780`, restore the save backup, and re-check the original APK hash.

## 6. What to record

- The service log (contains member ids and sub-sync types only; no identity strings).
- logcat filtered as above, plus any tombstone/crash.
- The list of sub-sync types requested at startup, in order. This tells us which handlers to build next.
- For each failure: the last request and reply sizes and the client log line before it.

Findings go to `07_DOCUMENTATION/NETWORKING_ANALYSIS.md` as runtime evidence ("observed at runtime"), kept separate from static findings.

## 7. Known risks and unknowns

| Risk | Mitigation |
|---|---|
| Three auth-reply fields and the shared `value` are unknown; the service sends 0 / the current time | L1 shows directly whether the reply is accepted; adjust and repeat |
| Empty parts for unhandled sub-syncs may leave features waiting or show error popups | Record which ones; implement handlers in order of appearance |
| EA Nimble/Synergy identity and other SDK traffic is separate from CloudCell and may block start-up when offline | Observe; offline behaviour is part of the result (NW-15/16) |
| Anti-tamper reaction (option C) | Prefer A |
| Frida cannot hook translated ARM code on x86 emulators | Use an ARM device or ARM emulator for option A |
| Accidental contact with real EA hosts | Network isolation (§3); the hook/hosts entries cover only the sync domain, so other hosts simply fail |

## 8. Owner approval checklist

- [ ] Test device: which **arm64** device or arm64 emulator image (with root / `frida-server`), used only for testing
- [x] Redirection option: **A (Frida hook)**, chosen 2026-11-15
- [ ] Saves: fresh install or test copies; backup taken
- [ ] Network isolation from EA infrastructure confirmed
- [ ] Hook script `08_TESTING/runtime/retr0_redirect.js` reviewed by the owner before use
- [ ] Permission to run `adb` commands against that device

## 9. Run log

### Run 1 (2026-11-18 21:35, owner approved; log mode, no redirect)

Setup: AVD `RETR0_x86_64_34` started with `-dns-server 127.0.0.1`; `avd_network_lock.sh lock --allow-dns` (only DNS to the emulator resolver allowed; all three TCP probes blocked); host `dns_logger.py` answering NXDOMAIN to everything; APK copy SHA-256 `dcfe3788…1d5f` installed (versionName 14.0.1, `primaryCpuAbi=arm64-v8a`, translated); game data pushed **without** saves, profiles, `doc/CC_Data`, `.depot/CC_Data`, friends' liveries or web cache (44,300 files, count verified), owned by the app uid 10192:1078. Raw outputs: `08_TESTING/runtime/out/run1/` (gitignored; contains a generated emulator device id).

**Result: the game starts, unpacks assets, runs CloudCell sync attempts, then crashes after 31 s** with a null dereference on `GLThread` right after `Asset::LoadFile unable to load file: '18.dat'`. Cause: our exclusion list wrongly treated `0.dat`/`18.dat` as saves (corrected in ASSET_FORMAT_INVENTORY §3). The game data also comes from a "Project Resurrection" install (`PR_Installation_Methods.txt` in the data root) and lists cars up to 2026, newer than the original 14.0.1 content; compatibility with the original APK is not yet confirmed.

**Network endpoints observed (nothing reached any of them: every lookup got NXDOMAIN, every connection was blocked):**

| Endpoint | Seen by | Owner / role (from names and code, not verified) |
|---|---|---|
| `0037-connect.cloudcell.com:443` `POST /time` (empty body), `POST /CC_Sync.php` ×4 (204–1,745 B bodies) | Java `HttpRequest.init` + DNS | CloudCell sync (NW-01); the replacement service's main target |
| `0037-mp6.cloudcell.com` | **DNS only** (native code) | CloudCell, likely multiplayer (`fmRUDP`); not visible to the Java hooks |
| `ping1.tnt-ea.com` | Java URL + DNS | EA connectivity ping |
| `prd1.session.centech.glulive.com /v1/sessions/games/com.ea.r3/devices/…`, `prd1.revid…/revid/v1/games/com.ea.r3/players/…`, `prd1.personalization…/personalization/v2/games/com.ea.r3/tags`, `prod.geo.gluops.com /geoservice/v2/publishdetailed` | Java URL + DNS | Glu central services (session, revenue id, personalisation, geo) |
| `cognito-identity.us-east-1.amazonaws.com` | Java URL + DNS | AWS Cognito identity (SDK) |
| `firebaseinstallations.googleapis.com`, `firebase-settings.crashlytics.com`, `app-measurement.com` | Java URL / DNS | Google Firebase (installations, Crashlytics, Analytics) |
| `graph.facebook.com /v16.0/app[/mobile_sdk_gk]` | Java URL | Facebook SDK |
| `api.helpshift.com /events/v1/ea-production/websdk/` | Java URL + DNS | Helpshift customer support |

Android system lookups (`*.google.com`, `connectivitycheck.gstatic.com`, `time.android.com`, …) appear before the game starts and are background noise.

Next: run 2 with `0.dat`/`18.dat` added (needs the owner's OK, see the session), to get past start-up and see the full sync sequence; then a `redirect` run against the local service.

### Run 2 (not run)

Pushing `0.dat`/`18.dat` into the run-1 install was not done; the owner chose a fresh install instead (run 3).

### Run 3 (2026-11-18 22:07, owner approved; FRESH install, no game data pushed, log mode)

Setup as run 1, except: `adb uninstall` first (app data, `Android/data` and `obb` folders confirmed gone), then the same hash-checked APK copy installed (new appId 10193); nothing pushed. Raw outputs: `08_TESTING/runtime/out/run3_fresh/` (gitignored).

**Result: no crash; the game reaches its first-run download screen and stays up (100 s observed).** The screen says *"Real Racing 3 needs to download an additional 1025MB"* with a Wi-Fi warning (the emulator reports a T-Mobile cellular connection, `Connectivity::May use 3G? - true`) and DOWNLOAD / EXIT / SETTINGS. The downloader does **not** wait for that dialog: it starts in the background straight away.

**First-run download flow (from the game's own `CC Trace/Info` log lines):**

1. The APK's `assets` are unpacked to `files/apk/res.zip` + `res/` (1,550 files, 23 MB, with `checksum.md5`). `res.zip` holds the asset lists: `res/asset_list_base.txt` (2,827 entries), `asset_list_base_gui*.txt`, per-track / per-car / per-quest lists (`asset_list_track_*_high.txt`, `asset_list_vehicle_*.txt`, `asset_list_quest_*`, `asset_list_lts_*`) and `asset_packs.cfg`.
2. CloudCell `FileManager` is built (seed `CC_SeedData.bin`, documents `files/doc/`, cache `files/.depot/`); `CC_ASSET_MANAGER_ENABLE` and `CC_ENABLE_ASSET_MGR_SERVICE` are on.
3. `AssetManager` tries the **updates** list first (`asset_list_updates.txt`, "Assets Update sync failed" offline), then downloads the **base** list: `StartListDownload() : Downloading asset_list_base.txt … nTotalDownloadBytes = 128145261` for the first phase.
4. For each file: `POST https://0037-assets.cloudcell.com/assetman/assetManDownloadPackHash.php` (1,269 calls; asks the server for a pack hash), then HTTP **Range** GETs from the CDN `https://firemonkeys.akamaized.net/rr3/live/asset_list_base/10a2829c2abd31ec9a59da64ba0801d7.bin` (4,404 GETs, 285 distinct ranges, chunks of ~470 KB median, highest byte 250,716,298). Each file gets up to **8 attempts** (`Download attempt n of 8 from CDN has failed!`); 160 distinct files were attempted, `/0.dat` first (confirming it is shipped data).
5. The downloader starts about **2 minutes** after launch (first `assetman` POST 22:09:50). The Frida session had already ended (22:09:27, `-t` timeout), which is why the Java hooks did not log these calls; the DNS logger saw `firemonkeys.akamaized.net` and `0037-assets.cloudcell.com`. The service `AndroidAssetManagerService` runs in the main process and calls native `ProcessDownloadsJNI`; since CloudCell's native HTTP goes through Java `HttpRequest` (NW-01), these requests are **probably** visible to the Java hook in a longer session (to confirm).

**List format** (`res/asset_list_base.txt` and `.depot/asset_list_updates.txt`): one line per file, `/path<TAB>md5<TAB>stored size<TAB>uncompressed size` (e.g. `/0.dat … 397 1028`). Sum of stored sizes 290,483,840, uncompressed 297,201,577. The `.depot/asset_list_base.txtCache.txt` cache has a short binary header (`9d f3 f6 a4`, u32 4, count line) then `/path<TAB>md5` lines. `asset_list_updates.info` holds a timestamp (`20251230230637` in the owner's copy).

**Open:** the requested byte ranges do **not** line up with file boundaries if the pack is the list's files concatenated in list order or path order (0 of 285 match), so the pack's internal index comes from somewhere else: possibly the `assetManDownloadPackHash.php` reply or a header inside the `.bin` pack. Needed before a replacement CDN can serve these files; next step is the native `AssetManager` code (`CC_AssetManager_Class`, `StartListDownload`, `AssetDownloadError` strings).

**Endpoints added by run 3** (to the run-1 table): `0037-assets.cloudcell.com:443 POST //assetman/assetManDownloadPackHash.php` (CloudCell asset manager), `firemonkeys.akamaized.net:443 GET //rr3/live/asset_list_base/<md5>.bin` with `Range` (Akamai CDN, asset packs).

### Run 4 (2026-11-18 22:20, owner approved; fresh install, `capture_run.py --mode record --minutes 5`)

Fresh `adb uninstall` + install of the same APK copy; network locked with DNS to `dns_logger.py`. Raw outputs: `08_TESTING/runtime/out/run4_record_fresh/` (gitignored).

**11,357 requests recorded in 5 minutes, all through Java `HttpRequest`** (confirms the run-3 correction: the asset manager and CDN calls use the same Java path as sync, so they can be recorded and redirected):

| Count | Request |
|---|---|
| 8,813 | `GET https://firemonkeys.akamaized.net:443//rr3/live/asset_list_base/10a2829c2abd31ec9a59da64ba0801d7.bin` with headers `Range: bytes=a-b`, `Accept-Encoding: identity` |
| 2,530 | `POST https://0037-assets.cloudcell.com:443//assetman/assetManDownloadPackHash.php` |
| 10 | `POST https://0037-connect.cloudcell.com:443/time` (empty body) |
| 4 | `POST https://0037-connect.cloudcell.com:443/CC_Sync.php` (`Content-Type: application/octet-stream`, `cc::BinaryBlob` body, NW-18) |

All requests: `failOnErrorStatus=true`, `sslCheck=true`, default headers on, 60 s timeout; read capacity 65,536 (assets) or 4,096 (sync).

**`assetManDownloadPackHash.php` request body (decoded from 2,530 samples):** `u32 w0` (varies per request, e.g. `0x00024096`, `0xffff23ec`; not CRC-32/Adler-32 of the payload: meaning UNKNOWN), `u32 1`, `u32 inflated size`, then a zlib stream (inflated size matches in every sample) holding a list of entries, each `u32 len + path`, `u32 32 + md5 hex`, `u32 x`. The path/md5 pairs are the entries of `res/asset_list_base.txt` (e.g. `/0.dat 1cc716b7…`, 23 entries in the first request). `x` is constant per file across retries (e.g. `/0.dat` → `0x060344a0`); meaning UNKNOWN. Each request was retried up to 16 times.

**Interpretation (MEDIUM):** the client asks this endpoint *where* each listed file lives; the byte ranges it then requests from the CDN pack (which do not follow from the list, run 3) most likely come from this reply. Rebuilding that reply is the key to serving downloads: next, read the reply parser in the native `CC_AssetManager_Class` code (strings `assetManDownloadPackHash`, `REQUESTING PARTIAL RANGE`), then serve it from `recorder_server.py`.

### Runs 5–9 (2026-11-18 22:30–23:05, owner approved): serving the asset CDN from the owner's own data

Tools: `SCRIPTS/asset_pack_build.py` (packs per ASSET_DOWNLOAD_PROTOCOL.md, classic zlib via MSYS2 `zlib1.dll`), `recorder_server.py` with `recorder_rules.cdn.json` / `recorder_rules.cdn_edited.json`, `capture_run.py --mode redirect`. Packs and edited lists live only in `03_ASSET_EXTRACTION/CDN*/` (gitignored).

| Run | Change | Result |
|---|---|---|
| 5 | Fresh install; pack for `asset_list_base` only | 317 CDN ranges served (206) and accepted; reached **94 / 1025 MB**; stopped at `asset_list_base_gui*` (no pack yet → 404 → CloudCell fallback 404) |
| 6 | Packs for the two GUI lists; resume | Reached **254 MB**; then needed `asset_list_track_common_*`; 60 GUI ETC textures failed MD5 (zero-filled slots) |
| — | Packs for **all 1,236 lists** (5.8 GB; 34,472 entries byte-exact) | Gaps for this device: ~1,767 ETC textures that every copy on the PC holds only as `.rgb.pvr.z` (the owner's own install cache lists the ETC originals with the same MD5 as the APK lists, so they were later replaced, likely by a texture-conversion step), 1,382 limited-time GUI files, 2,777 low-LOD track files, 15 files changed by later updates; other GPU formats and 480×320 are never requested |
| 7 | Resume (40 min) | Reached **833 / 1025 MB (81.3 %)**; blocked by 198 ETC GUI textures + `carrepairs.repairs.nct` (blanked in the main copy) + `upgrade_discount_popups.dat.nct` (newer version) |
| — | Second source `Downloads\apktool#\…\.depot` (read-only) | Supplies byte-exact `carrepairs.repairs.nct` and `upgrade_discount_popups.dat.nct`; none of the 198 ETC textures (3 other copies checked) |
| 8 | **Edited lists** (owner chose this): `asset_pack_build.py --drop-unavailable` leaves out every entry we cannot supply byte-exact; packs named by the edited list's MD5; `apply_edited_lists.py apply` backs up the device's lists to `/data/local/tmp/retr0_res_backup/`, installs the edited lists and pushes 1,632 RGB substitutes + 11 owner versions | **Lists were restored by the game at launch**: `Platform.extractRes` re-extracts `files/apk/res.zip` on every start (rewriting differing files) and recopies `res.zip` from the APK only when its length differs from the APK resource |
| 9 | `make_edited_res_zip.py`: edited `res.zip` with the edited lists, padded to the **identical length** (12,069,666 bytes; zip test OK); original `res.zip` backed up on the device | Game kept it, extracted the edited lists and requested the edited base pack `a63159ce…`; first 265 CDN ranges served, **0 download errors, 0 missing packs, 0 CloudCell fallbacks** |

The APK and `00_ORIGINAL` are untouched. To undo on the device: `apply_edited_lists.py restore` and copy `/data/local/tmp/retr0_res_backup/res.zip` back to `files/apk/res.zip`. Consequence of the edit: the game will not have the dropped files (e.g. low-LOD track variants, some limited-time GUI art) and uses the RGB substitutes for the dropped ETC GUI textures, as the owner's own install did.

### Runs 12–13 (2026-11-18 23:48–23:57, owner approved): answering `/time` and `CC_Sync.php`

Server: package `D:\RETR0_Server` started with `-WithSync` (recorder forwards `CC_Sync.php` to `retr0_local_service.py` on 8781).

- **`/time` (CONFIRMED):** `cc::ServerTimeManager` reads the server time from the **`X-Request-Start` response header** with `strtod` (header callback `0x1cef8a4`; name stored inline as `"X-Reque"`+`"s"`+`"t-Start"`), unit **seconds** (Unix time). The recorder answers `POST /time` with HTTP 200, empty body, `X-Request-Start: <now>` (rule with `{unix_time}`). The client logged `Server time returned; server time: 1795045728.678000 server-local time diff: 2.660444`.
- **`CC_Sync.php`:** run 12: every request rejected by the service (`truncated string`). Cause: this client syncs as a **guest**. Its log says `CC_SYNC_MANAGER_AUTHENTICATION : DISABLED` and `Member is guest`, and it never sends an auth request. Each batch's header carries the **legacy auth extension** written by `cc::auth::LegacyManager` slot 3 (`0x1cfb554`): `u32 0`, `u32 n`, n × (`u32 index`, 4 × lp), `u32 value`. A fresh install sends 5 empty slots (indices 0, 12, 6, 3, 13) and value `0xffffffff`. The codec only knew kind 3 (federated). Fixed in `cloudcell_codec.parse_sync_request` (kinds 0 and 3; synthetic test added); 10/10 recorded bodies now parse to the end.
- Run 13: the service answers every batch (10 batches, ~37 sub-sync kinds; most get an empty part; 10631 game config 1,649 B from the owner's seed data, 10712 server variables, 10555 cloud-save validate). **The game no longer shows OFFLINE**: the M$ screen shows `REWARD 10,850` and the daily-max `RESETS IN` countdown instead of "OFFLINE. M$ rewards may be lost".
- Not yet known: whether each empty sub-sync answer is acceptable to every feature; which sub-syncs need real data next.


### Runs 14–15 (2026-11-19 00:20–00:45, owner approved): serving the owner's modified assets, then reverting

- **Owner's folder:** `<owner game data> only assets\com.ea.games.r3_row` (full copy, 44,966 files).
- **What differs:** a hash diff against `00_ORIGINAL/METADATA/GAME_DATA.sha256` finds 6 files: `eds/AndroidHigh|Mid|Low.plist` and `feats/AndroidHigh|Mid|Low.feats`. Their packed form matches the APK's `asset_list_startup` MD5s exactly. So the owner's folder holds the ORIGINAL profiles, and the earlier GAME_DATA copy held changed ones (that copy produced `Settings file loaded, but had an invalid ID: AndroidHigh.plist`).
- **Builder:**
  - `asset_pack_build.py --modified-data` was added: an owner file that differs from the list gets its own MD5/sizes in the edited list.
  - A bug was fixed: an owner file that EQUALS the listed original was ignored, and the entry fell through to the changed copy and was dropped.
  - The `--modified-data` rebuild also took the owner's (PR) versions of the splash atlas/sprites (2048x1536 and 960x640), `r3_symbols.ttf` and `data/upgrade_discount_popups.dat.nct` (7 `modified` entries).
- **Server:** the previous `cdn` + `client` were moved to `D:\RETR0_Server\backups\...`. The new packs and a new length-matched `res.zip` (MD5 `ef15c549…`, new base pack `450619ab…`, startup pack `bfe1e85a…`) were installed.
- **Run 14:** fresh reinstall (appId 10197). The game requested the new base pack (284 × 206) and logged `Loaded settings file: AndroidHigh.plist` with NO `invalid ID` error. At that point `asset_list_startup` had not been downloaded yet, so the profile came from the APK's own res. The owner then ended the experiment.
- **Revert (run 15):**
  - The experiment's `cdn` + `client` are kept in `D:\RETR0_Server\backups\20261119_0038_pr_only_assets_experiment\`.
  - The pre-experiment assets are back in `D:\RETR0_Server\cdn` and `client` (`res.zip` MD5 `d6b42658…`, base pack `a63159ce…`).
  - Fresh reinstall (appId 10198), restored `res.zip` + RGB substitutes. The game requests `a63159ce…` again (264 × 206 in the first minute).
- **To switch back to the experiment:** stop the server, swap the `cdn` + `client` folders with the experiment backup, then do a fresh reinstall procedure.


### Runs 16–23 (2026-11-19 16:41–18:35, owner approved): Store preservation grants

Findings: `07_DOCUMENTATION/STORE_PRESERVATION_GRANTS.md` SP-11..SP-15. Outputs: `08_TESTING/runtime/out/run16_gift_test` … `run23_persist` (gitignored).

- **Runs 16–18 (server gift channel):**
  - A local admin call queued gift 1 (product 10051, 16 Gold). The game requested 10480 only at the main menu, and got it twice.
  - The game then froze: GLThread, ~250k `UnpackData` asserts.
  - Gift 1 was held and the server restarted; the game was fine without it.
- **Run 19:** gift 2 (identical) arrived with a 16 MB log buffer and a streaming log. No freeze, no 10481 ack, no claim notification; Gold unchanged. Code reading showed the game only stores it as an unclaimed offerwall reward (SP-12).
- **Run 20:** first patched build (BUY hook only). The game froze ~35 s after gift 2 was delivered again. That's the same flood, on the GLThread, and it also happened on the unpatched game, so it isn't the patch. The host backtrace only shows `libndk_translation`.
- **Run 21:** BUY → `RETR0 preservation grant: store product 10051 awarded=1 (no purchase)`, then 10052, 10046, 10463. The owner confirmed the balances went up. Pack BUY still showed the Google Play error (it goes through `PackManager`, not the hooked function).
- **Run 22:** second build (+ `PackManager` hook). Gift 2 held first. Packs 10061, 10988, 10062, 10989 (×2) and 10063 granted, all `awarded=1`, with no error popup. The owner confirmed it all works.
- **Run 23 (persistence):** force-stop and relaunch.
  - M$ 750,500 → 750,500; Gold 586 → 586.
  - R$ 2,937,525 → 2,941,000 (the counter was probably still animating in the first screenshot).
- **Package:**
  - `D:\RETR0_Server\store_grant.ps1` `status` and the `restore` → `apply` round trip were tested on the emulator; `install-fresh` was not tested.
  - The debug-signed APK is built and `apksigner verify` passes, but it has not been installed.

### Run 24 (2026-11-19 20:10-20:50, owner approved): Grand Prix Special Events "internet connection required"

- **Symptom:** in the long session after run 23, tapping the Formula 1 Japanese GP 2022 Special Event showed "An internet connection is required to access this feature" (title = event name).
- **Cause (CONFIRMED):** that session's redirect hook had detached (`capture_run.py -t` limit). The game kept running, but every CloudCell request failed: logcat `CC: [52] POST complete [Succeeded=False]`, `Unable to resolve host "0037-connect.cloudcell.com"`. The game treated itself as offline.
- **Check:** a diagnostic build logged every call to the two popup functions (`0x150cf80`, `0x150d564`). It was relaunched under a fresh redirect session; the owner tapped the event, it opened (team selection screen), and no popup was logged. The diagnostic APK was then replaced by the normal patched APK (`store_grant.ps1 apply`).
- **Fix:** `capture_run.py --minutes 0` keeps the hook attached until the game exits (no screenshots); `D:\RETR0_Server\play.cmd` runs it. Started at 20:47; requests redirected. **Not yet verified:** a session longer than 30 minutes, and actually finishing a Special Event race offline.

### Run 25 (2026-11-19 21:08, owner approved): RETR0 client, no Frida

- Built `classes2_redirect.dex` (`06_RECONSTRUCTION/APPLICATION/local_server_redirect/`: apktool 3.0.3 decode/rebuild, two calls inserted in `HttpRequest.init`, new class `com.retr0.Redirect`) and `rr3_14.0.1_retr0_client.apk` (SHA-256 `248de210…28ad`; signed copy `1e3193a9…45f9`, `apksigner verify` OK). The store-grant APK rebuilt byte-identical (`ed1ef5ab…2163`).
- Frida session stopped. `client.ps1 apply` (in-place swap + `cmd package compile -f -m verify`: Success), then `play.cmd` (adb reverse + launcher intent).
- Logcat: `CC: [1] POST request [https://0037-connect.cloudcell.com:443/time]` then `Succeeded=True`; `CC_Sync.php` x2 `Succeeded=True`. Server `runtime\recorder\requests.jsonl` n=117/118 carry `X-RETR0-Host: 0037-connect.cloudcell.com`. Non-CloudCell hosts (Crashlytics, Cognito, Glu geo) still fail to resolve, as before.
- Owner check (21:20): under the RETR0 client with no Frida, Grand Prix Special Events open and Store BUY grants work.

### Runs 26-29 (2026-11-19 21:50 to 2026-11-20 00:45, owner approved): username

- **Run 26 (diagnostic):** a text-lookup hook (`0x10aa8c8`) logged any lookup returning "Guest": none during a race, so "Guest" is not from the text table.
- **Run 27 (diagnostic):** the static "Guest" string (`0x1f9c198`) changed to "Hello": Profile still said Guest, so not that string. Profile traced to `0x135e944` (SV-27).
- **Run 28:** first username build. The code "RETR0" (no prefix) gave "Connection error": the reply was misread because the sync reply lacked the member header (NW-93). Service and codec fixed, tests updated (59 pass). Next try: "incorrect" (prefix still required then); changed so that any code sets the name.
- **Run 29:** name saved and loaded (`RETR0 username saved/loaded: RETR0`) but still Guest: the hook wrote to x0, while the function returns its string through x8. Fixed. The stray in-memory write was checked: the device save files, pulled byte-exactly (`adb exec-out`), all pass `save_format_check.py` (magic, size, checksum). **Owner confirmed the name change works.**
- Client: `rr3_14.0.1_retr0_client.apk` SHA-256 `60fba100…c24c`; signed `7ad53b0b…3e7b`.

