# server/

The RETR0 server: run `retr0_server.cmd start -WithSync`, then `play.cmd`.

| Path | What |
|---|---|
| `retr0_server.cmd` / `.ps1` | `start` · `stop` · `status` · `restart` (`-WithSync` adds the CloudCell sync service) |
| `client.ps1` / `play.cmd` | Put the RETR0 client on the emulator (`apply`, `restore`, `install-fresh`, `status`) and start the game (`play`) |
| `config/` | Request-routing rules for the CDN service |
| `services/` | `dns_logger.py`, `recorder_server.py` (CDN + router), `local_service/` (CloudCell sync), `cloudcell_codec/`, `seed_data_decode.py` |
| `tools/` | Asset-pack building from your own data |

You create these yourself (they are git-ignored): `python/` (a venv: `py -3 -m venv server\python`),
`data/CC_SeedData.bin` (from your game's `.depot`), `cdn/` (asset packs), `client/` (edited `res.zip`, lists, and your
built APKs in `client/apk/`), `runtime/` (created on start).

Docs: [../docs/07-server.md](../docs/07-server.md) and [../docs/08-setup-guide.md](../docs/08-setup-guide.md).
