# Changelog

All notable changes to the RETR0 Server. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-11-25

### Added
- **LAN mode** ([docs/features/lan-mode.md](docs/features/lan-mode.md)): `retr0_server.ps1 start -Lan` or the
  control panel's LAN toggle. The CDN service also listens on the PC's network addresses but answers only loopback
  and private home-network clients; UDP 8799 discovery (`RETR0?` -> `RETR0 <port>`) lets the RETR0 link client
  find the server. Tested on an NVIDIA SHIELD Tablet K1 over Wi-Fi (run 35).
- **Control panel 0.5**: LAN toggle, LAN in the status pill, the PC address to use, and the devices seen.
- **Control panel** `RETR0 Server.exe` (source in `server/tools/control_panel/`, built with Windows' own C# compiler):
  start/stop with live status lights, client commands, catalogue and custom gifts, file list, log view. It runs the
  existing scripts, so the Python services stay editable without a rebuild.
- **Control panel 0.4 redesign**: dark/light theme, navigation rail, Overview page (status, service tiles, recent gifts,
  activity feed), server status pill with uptime, "stopped unexpectedly" toast, gift filters, file filter, log
  highlighting, danger zone for Restore original / New install, collapsible output.
- **Custom gifts and cars**: `?money=&gold=&mdollars=&car=&message=` on the admin endpoint, validated and sent as an
  instant community gift (run 34: R$ +12,345, car 383 added to the garage).
- `client.cmd` wrapper and `client.ps1 fix-reboot`.

### Fixed
- **Cloud-save uploads** were handed out as `127.0.0.1:8781`, which no device can reach; the sync service now
  gets `--public-base http://127.0.0.1:8780`.
- The CDN service retries GET/HEAD/PUT once after a connection reset on its hop to the sync service (POST is never
  replayed) and passes the sync service's own error replies through unchanged.
- **Server gifts work** (runs 32–33): the gift reply now sends the gift *kind* the client expects (the product id
  was sent there, so every gift was dropped). Gold arrives as a claimable offer reward; R$ and M$ as community gifts,
  credited at once with a RETR0 popup and offered only once. The 10481 receipt is parsed with the client's real
  layout.
- One gift kind per reply: the client applies the first gift's kind to the whole list, so mixing a Gold offer gift
  with instant gifts lost the instant ones.

## [0.2.0] - 2026-11-20

### Added
- **CDN service** accepts the `/_retr0host/<host>/<path>` prefix used by the native redirect of RETR0 Client 0.2.0
  (the host is taken from the path; `X-RETR0-Host` still works).
- **`client.ps1 ui-text` / `ui-text-restore`** and `tools/retr0_gui_patch.py`: rename Settings › ENTER RACING CODE to
  "Change Username (Restart Required)" and its prompt, built from the player's own game files; originals kept.
- Docs: the emulator-reboot behaviour of in-place installs; the asset audit (run 31) and the missing-UI-image
  diagnosis.

## [0.1.0] - 2026-11-20

First public release.

### Added
- **CDN service** (`recorder_server.py`): rule-based router; serves asset packs with HTTP Range; answers `/time`
  with `X-Request-Start`; forwards `CC_Sync.php`; records every request.
- **CloudCell sync service** (`retr0_local_service.py`): boxed batch parsing, guest/legacy and federated auth,
  sub-sync dispatch with handlers for FileManager, game config, server variables, cloud save, PvP servers, gifts
  (parked) and racing codes.
- **Codec** (`cloudcell_codec`): boxing and checksums, sync request/reply, 80+ catalogued sub-syncs, decoded
  payloads.
- **DNS logger**: logs every lookup, answers none.
- **Control scripts**: `retr0_server.cmd` (start/stop/status/restart, `-WithSync`), `client.ps1` (apply/restore/
  install-fresh/status/play), `play.cmd`.
- **Asset tools**: pack builder from your own data, edited lists, length-matched `res.zip`.
- **Research tools**: emulator network lock, Frida hooks, session runner.
- **Documentation**: 13-chapter guide, feature pages, and the project's reference set.
- 59 unit tests and CI.

### Fixed
- Sync replies now include the auth manager's **member header** (member id, developer flag, device id, two more
  fields). Without it the client misread every non-empty reply ("Connection error"; likely the cause of the gift
  freezes).

[Unreleased]: https://github.com/Tankonline/RETR0-Server/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Tankonline/RETR0-Server/releases/tag/v0.3.0
[0.2.0]: https://github.com/Tankonline/RETR0-Server/releases/tag/v0.2.0
[0.1.0]: https://github.com/Tankonline/RETR0-Server/releases/tag/v0.1.0
