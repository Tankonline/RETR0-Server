# Changelog

All notable changes to the RETR0 Server. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- **Server gifts work** (runs 32–33): the gift reply now sends the gift *kind* the client expects (the product id
  was sent there, so every gift was dropped). Gold arrives as a claimable offer reward; R$ and M$ as community gifts,
  credited at once with a RETR0 popup and offered only once. The 10481 receipt is parsed with the client's real
  layout.

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

[0.2.0]: https://github.com/Tankonline/RETR0-Server/releases/tag/v0.2.0
[0.1.0]: https://github.com/Tankonline/RETR0-Server/releases/tag/v0.1.0
