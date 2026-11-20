# Feature · Built-in server redirect

**What it does:** makes the game send all its CloudCell and asset-CDN traffic to the RETR0 server on your PC, with
no Frida and no time limit. Every other host is left alone.

## Background

The game hard-codes its servers (`0037-connect.cloudcell.com`, `firemonkeys.akamaized.net`, …) and always uses HTTPS
on port 443 (NW-85, NW-86). Two facts made a local server possible:

- All CloudCell HTTP, including asset downloads, goes through **one Java class**,
  `com.firemonkeys.cloudcellapi.HttpRequest`, via `init(userAgent, method, url, body, …)` (NW-01).
- The app's `network_security_config` allows plain HTTP **only to `127.0.0.1`**.

During research a **Frida** hook on `HttpRequest.init` rewrote those URLs to `http://127.0.0.1:8780` and added a
header `X-RETR0-Host: <original host>` ([research-tools/retr0_redirect_java.js](../../research-tools/retr0_redirect_java.js)).
That worked, but only while a Frida session was attached. When a timed session ended, the game silently lost the
server, and online screens locked (see [special-events.md](special-events.md)).

## How it was built

The same logic was moved into the APK as smali (the assembly form of Android bytecode):

```
HttpRequest.init(…, String url, …):
    url = com.retr0.Redirect.rewrite(url)      ← inserted as the first instruction
    … original body …
    com.retr0.Redirect.finish(this)            ← inserted just before return
```

[`Redirect.smali`](../../client-patches/local_server_redirect/Redirect.smali):

- `rewrite(url)` parses `scheme://host[:port]path?query`. If the host matches `*.cloudcell.com`, `*.exos.fm` or
  `firemonkeys.akamaized.net`, it returns `http://127.0.0.1:8780<path?query>` and remembers the original host in a
  thread-local. Anything else is returned unchanged.
- `finish(request)` adds `X-RETR0-Host: <original host>` (the server's CDN rules route on it) and clears the
  thread-local.

[`build_redirect_dex.py`](../../client-patches/local_server_redirect/build_redirect_dex.py) decodes your APK with
APKTool 3.0.3, checks that `init`'s signature and its last instructions are exactly as expected, inserts the two
calls, adds `Redirect.smali`, rebuilds and extracts `classes2.dex`. `build_patch.py` then swaps that dex into the
client APK ([10-retr0-client.md](../10-retr0-client.md)).

On the emulator, `adb reverse tcp:8780 tcp:8780` connects the device's `127.0.0.1:8780` to the PC; `play.cmd` sets it
every time.

## Verified (run 25)

With no Frida process attached: `POST /time` and `CC_Sync.php` succeed, and the server's request log shows each
request with `X-RETR0-Host: 0037-connect.cloudcell.com`. The owner confirmed that Special Events open and the
store grants work.
