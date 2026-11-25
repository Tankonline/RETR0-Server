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
| 32-bit devices: partial | The RETR0 link (Java) connects any CPU type, but the native additions (store grants, player name) exist only for arm64-v8a |
| Real devices: manual install | LAN mode works ([features/lan-mode.md](features/lan-mode.md)), but `client.ps1` assumes the emulator's `su`; devices rooted through `adb root` are swapped by hand |
| Loopback resets on some PCs | On the development PC even plain Python HTTP over loopback loses about 1 exchange in 10 (likely the antivirus network filter); the CDN service retries GET/HEAD/PUT once, the game retries syncs |
| In-place swap after a reboot | **It does not survive** an emulator reboot or a crash-restart of Android's system process (seen in run 34): at boot Android re-checks signatures and removes the swapped APK's code (data is kept). Run `client.ps1 fix-reboot` (or the control panel's "Fix after emulator restart"). A permanent install needs a signed APK, which today means a fresh install |
| Missing UI images show no error | If cards lack their frame or badge, the device is missing UI image files; compare it with your PC copy of the game data (the game logs nothing) |
| Store package sizes | Some Gold/R$/M$ package sizes were not individually tested (same code path as the tested ones); the 7-Day Gold Card (10196) is not covered |

## Roadmap

1. Per-player gifts with list/remove/history; investigate car rewards (the kind-0 community gift accepts any store reward type).
2. **Weekly time trials**: leaderboards (codec already written), ghost upload/download, and a locally run weekly
   schedule.
3. **Multiplayer**: match start/finish sub-syncs are decoded; the race itself uses the game's own UDP protocol
   (fmRUDP), not yet analysed. First check whether the client's built-in LAN code path can be used.
4. Give real answers to the other sub-syncs features need: career/progress, events data, store sales, race teams.
5. Device tooling: `client.ps1` and the control panel for real devices, with a device picker.
6. A data-preserving way to install the signed client, and a standalone patcher (no NDK or SDK tools).
7. Answer `assetManDownloadPackHash.php` (reply format still unknown).
8. Keep documenting subsystems: front end, audio, the rest of the vehicle data.
