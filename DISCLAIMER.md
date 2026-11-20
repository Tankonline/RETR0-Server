# Disclaimer and ground rules

Project RETR0 is a **preservation and interoperability** project for Real Racing 3, whose official online services were shut down by Electronic Arts on **20 March 2026**. It is not affiliated with, endorsed by or connected to Electronic Arts, Firemonkeys Studios or Glu Mobile.

## What this repository contains

- Independently written server code (Python), patch sources (ARM64 assembly, smali) and build scripts.
- Documentation written by the project: observations, addresses, data layouts and explanations.

## What it does not contain, and never will

- No EA code, decompiled source or pseudocode dumps. Addresses and short descriptions of behaviour are documented; decompiler output is **not** EA's original source and is not distributed.
- No game assets, APKs, seed data, save files or other game files.
- No encryption keys from the game (the docs say *where* a key is and *which* cipher is used, never the key bytes).
- No personal data, accounts, tokens or credentials.

## Rules the project follows

- **No EA infrastructure.** Nothing here contacts, probes, scans or authenticates to EA's original servers. The server listens on `127.0.0.1` only. The client patch sends CloudCell and CDN traffic to `127.0.0.1:8780` and leaves every other host untouched.
- **Your own copy.** Every build script starts from your own legitimately obtained, unmodified copy of the game (`real-racing-3-14-0-1.apk`, SHA-256 `dcfe3788…dcad1d5f`). Asset packs are built from your own game data.
- **No fake purchases.** The store feature gives in-game currency through the game's own *non-purchase* reward path. It does not fake receipts, does not call Google Play billing and does not record a purchase.
- **Test on a test device.** The project was developed on a dedicated, network-locked Android emulator. Back up your game data before trying any patched build.

## No warranty

The software is provided "as is", without warranty of any kind (see [LICENSE](LICENSE)). You are responsible for how you use it and for complying with the laws and agreements that apply to you.
