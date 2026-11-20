# Project RETR0 documentation

Start here. The guide chapters are written to be read in order; the feature pages and the reference set can be
read on their own.

## Guide

| # | Chapter | What it covers |
|---|---|---|
| 01 | [Project overview](01-project-overview.md) | Why the project exists, goals, ground rules, what was achieved |
| 02 | [Timeline](02-timeline.md) | Every phase and step the project took, in order, with dates |
| 03 | [Tools and environment](03-tools-and-environment.md) | Every tool used, versions, the test emulator |
| 04 | [How the game was decompiled](04-decompilation-method.md) | APK unpacking, Java decompilation, Ghidra, function recovery, naming and evidence rules |
| 05 | [Client architecture](05-client-architecture.md) | What we learned about the game: Java layer, native engine, CloudCell, saves, assets, physics |
| 06 | [Network protocol](06-network-protocol.md) | CloudCell sync: message boxing, batches, sub-syncs, auth, the reply member header |
| 07 | [The server](07-server.md) | Server architecture, services, ports, config, state |
| 08 | [Setup guide](08-setup-guide.md) | From zero to playing: emulator, server, assets, client |
| 09 | [Asset CDN](09-asset-cdn.md) | How the game downloads content and how the packs are rebuilt from your own data |
| 10 | [The RETR0 client](10-retr0-client.md) | How the game is patched: native code cave, smali, build pipeline, installing |
| 11 | [Testing](11-testing.md) | Unit tests, runtime test runs, what was verified |
| 12 | [Known issues and roadmap](12-known-issues-and-roadmap.md) | What is open, what is next |
| 13 | [Legal and ethics](13-legal-and-ethics.md) | The project's rules and why they exist |

## Features (how each one was added)

| Feature | Page |
|---|---|
| Built-in server redirect (no Frida) | [features/server-redirect.md](features/server-redirect.md) |
| Special events unlocked | [features/special-events.md](features/special-events.md) |
| Store preservation grants | [features/store-grants.md](features/store-grants.md) |
| Player name (Username) | [features/username.md](features/username.md) |
| Sync reply member header fix | [features/sync-reply-header-fix.md](features/sync-reply-header-fix.md) |
| Gifts (parked) | [features/gifts.md](features/gifts.md) |

## Reference set

[`reference/`](reference/) holds the project's detailed working documents: every finding with its ID, evidence,
addresses and confidence label (e.g. `NW-93`, `SV-27`, `SP-14`). The guide chapters link into them. Start with
[reference/README.md](reference/README.md).

## Conventions

- **Addresses** are ELF virtual addresses in the arm64-v8a `libRealRacing3.so` of RR3 14.0.1 unless stated otherwise.
  (In Ghidra the project used an image base of `0x100000`, so Ghidra labels are ELF + `0x100000`, e.g. `FUN_00c879fc`
  is ELF `0xb879fc`.)
- **Confidence labels:** CONFIRMED (direct, preferably multiple evidence), HIGH, MEDIUM, LOW, UNKNOWN.
- **Function names** stay neutral (`FUN_…` or the address) unless evidence supports a name, such as an original
  source-file path or log string embedded in the binary.
- **Pseudocode is not source.** Decompiler output is the project's reconstruction aid, not EA's code, and is not
  published.
