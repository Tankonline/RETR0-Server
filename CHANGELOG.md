# Changelog

All notable changes to the RETR0 Server. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

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

[0.1.0]: https://github.com/Tankonline/RETR0-Server/releases/tag/v0.1.0
