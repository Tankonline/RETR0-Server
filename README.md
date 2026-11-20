# RETR0 Server

**An independent, local replacement server for Real Racing 3 (Android 14.0.1), built by reverse engineering the game client after its official online services shut down on 20 March 2026.**

Project RETR0 is a preservation project. The game still works offline, but a fresh install can no longer download its ~1.5 GB of content, and every online-gated screen (special events, the store, sync) is locked. This repository contains:

- **the RETR0 server**: a small set of Python services that run on your own PC and answer the game's asset downloads and its CloudCell sync traffic;
- the **documentation**: how the game was decompiled and analysed, how its network protocol works, and every step the project took.

The **game side** (patch sources and build scripts that turn *your own* copy of the game into a client that talks to this server, plus the feature docs) lives in **[RETR0-Client](https://github.com/Tankonline/RETR0-Client)**.

> This repository contains **no EA code, no game assets, no APKs and no keys**. Everything here is independently written. To use it you need your own legitimately obtained copy of the game and its data. See [DISCLAIMER.md](DISCLAIMER.md).

## What works

| Feature | Status | Docs |
|---|---|---|
| Asset downloads for a fresh install (served from your own data) | Working | [Asset CDN](docs/09-asset-cdn.md) |
| CloudCell sync (`/time`, `CC_Sync.php`): the game shows online | Working (most sub-syncs get empty answers) | [Server](docs/07-server.md), [Protocol](docs/06-network-protocol.md) |
| Built-in server redirect (no Frida, no time limit) | Working | [Server redirect](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/server-redirect.md) |
| Grand Prix / Special Events open again | Working | [Special events](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/special-events.md) |
| Store BUY gives currency and currency packs (free preservation grant) | Working | [Store grants](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/store-grants.md) |
| Choose your player name (instead of "Guest") | Working | [Username](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/username.md) |
| Server-side gifts | Parked | [Gifts](docs/features/gifts.md) |
| Leaderboards, race teams, multiplayer | Not built | [Roadmap](docs/12-known-issues-and-roadmap.md) |

## Quick start

The full walkthrough is in **[docs/08-setup-guide.md](docs/08-setup-guide.md)**. In short, on Windows with an Android emulator:

```powershell
# 1. one-time: Python for the server, your seed data, your asset packs (see the guide)
py -3 -m venv server\python
# 2. build the RETR0 client from YOUR copy of the APK with the RETR0-Client repo (see its README),
#    then copy the built APKs into server\client\apk\
# 3. run
server\retr0_server.cmd start -WithSync
server\client.ps1 apply      # put the RETR0 client on the emulator (keeps your data)
server\play.cmd              # start the game connected to the server
```

## Repository layout

| Folder | Contents |
|---|---|
| [`server/`](server/) | Control scripts, services (DNS logger, CDN/recorder, CloudCell sync), config, pack-building tools |
| [`research-tools/`](research-tools/) | Emulator network lock, Frida hooks and the session runner used during the research |
| [`tests/`](tests/) | Unit tests for the codec and the sync service (`python -m pytest tests`) |
| [`docs/`](docs/) | The documentation, start at **[docs/README.md](docs/README.md)** |

## Licence

- Code: [MIT](LICENSE).
- Documentation (`docs/`): [CC BY 4.0](LICENSE-DOCS.md).

Real Racing 3 is a trademark of Electronic Arts Inc. This project is not affiliated with or endorsed by EA, Firemonkeys or Glu.
