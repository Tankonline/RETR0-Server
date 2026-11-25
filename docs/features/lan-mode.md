# LAN mode: play from another device on your home network

LAN mode lets an Android device on the same Wi-Fi as the server PC (for example a phone or tablet) use the RETR0
server, with no USB cable and no `adb reverse`. The device runs the **RETR0 link client** (RETR0-Client
`patches/retr0_link/`), which finds the server by itself.

Tested on an NVIDIA SHIELD Tablet K1 (LineageOS 15.1, Android 8.1, 32-bit ARM) with the server on a Windows PC over
Wi-Fi (run 35): the game found the server, synced, and reached Daily Rewards; after a restart it found the server
again.

## Turning it on

- Control panel: tick **LAN mode** (Overview or Server page) before Start. The status pill shows `LAN`.
- Command line: `retr0_server.ps1 start -WithSync -Lan`. `status` prints the PC address devices connect to.

## What changes on the server

| | Normal | LAN mode |
|---|---|---|
| CDN / recorder service (8780) | listens on `127.0.0.1` | listens on all of the PC's addresses, but **answers only loopback and private home-network clients** (10/8, 172.16/12, 192.168/16, link-local); anyone else gets 403 |
| Discovery | off | UDP 8799: answers the exact request `RETR0?` from a private address with `RETR0 <port>` |
| Sync service (8781) | `127.0.0.1` | unchanged: still `127.0.0.1` only, reached through the CDN service |
| DNS logger (53) | `127.0.0.1` | unchanged |

Every request is recorded with the device's address (`client` in `runtime/recorder/requests.jsonl`); the control
panel lists the devices it has seen.

## Windows firewall (one-time, done by you)

Windows blocks incoming connections by default. On the server PC, in an administrator PowerShell:

1. Make sure your home network's profile is **Private** (Settings → Network → your network → Private).
2. Allow the two ports from your home network only (adjust the subnet to yours):

```powershell
New-NetFirewallRule -DisplayName "RETR0 LAN (TCP 8780)" -Direction Inbound -Protocol TCP -LocalPort 8780 -RemoteAddress 192.168.0.0/24 -Profile Private -Action Allow
New-NetFirewallRule -DisplayName "RETR0 LAN discovery (UDP 8799)" -Direction Inbound -Protocol UDP -LocalPort 8799 -RemoteAddress 192.168.0.0/24 -Profile Private -Action Allow
```

3. If Windows once asked whether Python may use the network and you clicked *Cancel*, it created **Block** rules for
   `python.exe`; those win over Allow rules. Remove them (Windows Defender Firewall → Inbound rules → `python`).

Never forward these ports on your router: the server is for your own home network.

## On the device

Install the RETR0 link client (see RETR0-Client `docs/features/lan-link.md`). If discovery can't work on your
network (some routers block broadcasts), put the PC's address in
`/sdcard/Android/data/com.ea.games.r3_row/files/retr0_server.txt`, for example `192.168.0.39`.

## Also fixed with LAN mode

- **Cloud-save uploads** were handed to the game as `127.0.0.1:8781`, which a device (and the emulator) can never
  reach. The sync service now gets `--public-base http://127.0.0.1:8780`, so uploads go through the CDN service.
- **Retry on the internal hop**: a connection reset between the CDN and sync services is retried once for
  GET/HEAD/PUT. A POST (a sync batch) is never replayed; the game retries syncs itself. On the development PC even
  plain Python HTTP over loopback loses about 1 exchange in 10 to a reset or timeout, with no RETR0 code involved
  (control test, run 35; likely the antivirus network filter), so this is a workaround, not a fix of a server bug.
