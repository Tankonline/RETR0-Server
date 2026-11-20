# RETR0 local service (first slice)

An independently operated, clean-room service that speaks the CloudCell request/response format documented in `07_DOCUMENTATION/NETWORKING_ANALYSIS.md` §8 (request headers and authentication: §8.21). It contains no EA code or data, issues its own member ids and random tokens, accepts no EA credentials, and never contacts EA infrastructure.

**Status: protocol-consistent, not yet tested against the real client.** Every reply is built from statically decoded formats and checked by `08_TESTING/test_local_service.py` (round trips, ordering, HTTP end to end). Whether the game accepts these replies is UNKNOWN until the runtime test below is approved and run.

## Run

```
.venv\Scripts\python -I 06_RECONSTRUCTION\BACKEND\local_service\retr0_local_service.py --data-dir <dir> [--port 8780] [-v]
```

- Listens on `127.0.0.1` by default. The client's network security config only allows cleartext HTTP to `127.0.0.1` (NW-08).
- `<dir>` holds `state.json` (member ids, tokens, server variables) and `cloudsave/`. Keep it outside the repo or in an ignored folder.
- Server variables: edit `"server_variables"` in `state.json` (string → string), e.g. `"Rookie_Enable": "0"`.

## What it answers

| Request | Reply |
|---|---|
| Authentication (`FederatedManager`, any state) | Success: new or existing member id for this device, fresh random token, 24 h timeout |
| Batched sync | `u32 ok=1`, `u32 value` (current Unix time; [likely] server time, unverified), one part per sub-sync in order |
| 13/448 FileManager | Files you **publish** (`--publish NAME=PATH`, or `--publish-from-seed NAME` with `--seed-data`) are pushed whenever the version the client reports differs. Nothing is pushed otherwise (empty part); nothing is ever deleted |
| 10631/5245 game config | values from your `CC_SeedData.bin` (`--seed-data`, seed file `1`), overridden by `"game_config"` in `state.json` |
| 10712/4373 server variables | count + key/value pairs from `state.json` |
| 10660/5638 cloud-save upload | status 0, random key, a PUT URL on this service |
| 10555/5757 cloud-save validate | `true` |
| 10768/0 PvP servers | empty list |
| Any other sub-sync | **empty part** (the client's own failure path completes sub-syncs with empty parts; per-feature behaviour unverified) |
| `PUT`/`GET /retr0/cloudsave/<member>/<key>` | Stores / returns the uploaded save blob |

## Privacy and safety

- Devices are keyed by a salted SHA-256 of the auth header ids and strings. The strings themselves (which may include platform account data) and the identity records are never stored or logged.
- Cloud-save paths are validated (numeric member, alphanumeric key) and confined to the data directory.
- Tokens are local random values, not credentials for any other service.

## Publishing changed game data

Seed files are FileManager files (NW-92). To change the store catalogue, for example: decode it with `SCRIPTS/seed_data_decode.py` (`parse_store_catalogue`), edit, rebuild with `build_store_catalogue`, box it with the codec (`cc.box(cc.box(data, cc.ZLIB), cc.XOR)`, the same boxing the seed uses), write it to a file and start the service with `--publish 12=<that file>`. Each publish bumps the version. Which version the client reports for its own seed files is unknown until the runtime test, so the service pushes on any difference.

## HTTPS

The client always syncs over HTTPS (port constant 443, NW-85) and accepts any certificate (K-16). Generate a local self-signed certificate and pass `--tls-cert`/`--tls-key`; `--public-base` sets the URL handed out for cloud-save uploads. See `08_TESTING/RUNTIME_TEST_PLAN.md`.

## Not done (next)

- Approved runtime test (`08_TESTING/RUNTIME_TEST_PLAN.md`). The in-game server switch only chooses between built-in EA hosts (NW-85), so a redirection method must be chosen by the project owner.
- Cloud-save list (47) and download (48) replies with real entries; sales catalogue; leaderboards; Race Teams; garage.
- The three unknown auth-reply fields (`u_a`, `u_b`, `flag_c`) and the meaning of the shared `value`.
