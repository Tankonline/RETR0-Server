# 12 · Known issues and roadmap

## Known issues and limits

| Item | Detail |
|---|---|
| Most sub-syncs get empty answers | The game accepts that for everything tested so far, but features that need data (leaderboards, race teams, events data, sales) have none |
| Gifts are not per player | One queue for every connected game; cars and other reward types not investigated yet ([features/gifts.md](features/gifts.md)) |
| Racing codes give no rewards | Every racing code is treated as a name change |
| Name applies after a restart | The name file is read once per game start |
| Re-using a name | The game refuses a code it already sent; change the capitals |
| Edited asset lists | A fresh install lacks the files that could not be supplied byte-exactly (some limited-time GUI art, low-detail track variants) |
| arm64 only | The native patch targets the arm64-v8a library of 14.0.1; armv7 devices are not patched |
| Emulator-focused | Paths and `adb reverse` assume the emulator; a real phone would need a reachable server address in the redirect |
| In-place swap after a reboot | **It does not survive** an emulator reboot or a crash-restart of Android's system process (seen in run 34): at boot Android re-checks signatures and removes the swapped APK's code (data is kept). Run `client.ps1 fix-reboot` (or the control panel's "Fix after emulator restart"). A permanent install needs a signed APK, which today means a fresh install |
| Missing UI images show no error | If cards lack their frame or badge, the device is missing UI image files; compare it with your PC copy of the game data (the game logs nothing) |
| Store package sizes | Some Gold/R$/M$ package sizes were not individually tested (same code path as the tested ones); the 7-Day Gold Card (10196) is not covered |

## Roadmap

1. Per-player gifts with list/remove/history; investigate car rewards (the kind-0 community gift accepts any store reward type).
2. Give real answers to the sub-syncs that features need: career/progress, events data, store sales, leaderboards
   (local), race teams.
3. Make the server address in the redirect configurable (for a real phone on the same network).
4. A data-preserving way to install the signed client, and a standalone patcher (no NDK or SDK tools).
5. Answer `assetManDownloadPackHash.php` (reply format still unknown).
6. Keep documenting subsystems: front end, audio, the rest of the vehicle data.
