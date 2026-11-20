# Feature · Special events unlocked

**What it does:** Grand Prix / Special Events open and can be played again.

## The symptom

Tapping a Special Event card (for example *Formula 1 Honda Japanese Grand Prix 2022*) showed a popup titled with
the event name: *"An internet connection is required to access this feature. Make sure your device is online and
flight mode is turned off."*

## How it was investigated (run 24)

1. Static search for the text and for the game's connectivity checks (`IsConnectedToInternet`-style helpers at
   `0xcd80c0` / `0xcd906c`, the `LtsSyncScreen`, the championship card handlers). None matched a popup titled with
   the event name.
2. A **diagnostic build** hooked the two popup functions (`0x150cf80`, `0x150d564`) to log each popup's title, body
   and caller.
3. The game was relaunched under a fresh redirect session; the owner tapped the event, and it **opened** (team
   selection screen), with no popup logged.
4. The logcat from the failing session showed why: every CloudCell request was failing with
   `Unable to resolve host "0037-connect.cloudcell.com"`. The research launcher had attached the Frida redirect
   hook with a time limit; when it ran out the hook detached, but the game kept running, now with no server.

## The fix

- Research launcher: `capture_run.py --minutes 0` keeps the hook attached until the game exits.
- For playing: the redirect was built into the client, so the connection no longer depends on Frida at all
  ([server-redirect.md](server-redirect.md)).

No change to the game's event logic was needed: with a working connection, the events gate passes by itself.
