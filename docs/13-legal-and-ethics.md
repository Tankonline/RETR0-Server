# 13 · Legal and ethics

Project RETR0 exists to preserve a discontinued game for people who already own it. These are the rules it worked
by, and why.

| Rule | Why |
|---|---|
| The original APK and data are immutable evidence; work happens on copies | Results must be reproducible and traceable |
| Nothing contacts EA infrastructure; the server listens on `127.0.0.1` only | The project replaces discontinued services for a single player; it does not revive, probe or impersonate EA's systems |
| The test emulator is network-locked | Nothing the game does during research can reach any outside service |
| No EA code, assets, APKs, seed data or keys are published | They are EA's property. Discontinuation does not make them public domain |
| Decompiler output is never presented or published as EA's source | It is a reconstruction aid, not the original |
| Every build starts from the user's own original APK and data | Users bring their own legitimately obtained copy |
| No fake receipts, no billing calls, no purchase records | The store feature uses the game's own *non-purchase* reward path; it does not pretend money changed hands |
| Tamper-protected values (currency `[EHV]`/`[H]`) were not decoded | Not needed; editing currency directly in saves was never a goal |
| Player saves were only read, from copies | Users' progress must never be damaged by research |
| Findings carry evidence and confidence labels | So readers can tell what is known from what is inferred |

## Trademarks

Real Racing 3 is a trademark of Electronic Arts Inc. Firemonkeys, CloudCell, Nimble and other names belong to their
owners. This project is not affiliated with or endorsed by them.

## Your responsibility

Laws and agreements differ by country. Using this software is your decision and your responsibility; see
[DISCLAIMER.md](../DISCLAIMER.md).
