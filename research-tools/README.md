# research-tools/

Tools used while studying the game on the locked test emulator. They are not needed to play.

| File | What |
|---|---|
| `avd_network_lock.sh` | Locks the emulator's network: blocks everything except loopback, replies and DNS to the PC (`lock --allow-dns`, `unlock`, `status`) |
| `retr0_redirect_java.js` | Frida hook on `HttpRequest.init`: `log`, `record` (full requests) or `redirect` (to `127.0.0.1:8780`) |
| `retr0_redirect.js` | Earlier arm64-native variant (not usable on an x86_64 emulator, where ARM code is translated) |
| `capture_run.py` | Runs one session under the Frida hook and saves requests, logcat and screenshots (`--minutes 0` = until the game exits). Written for the project's folder layout |
| `recorder_rules.example.json` | Example rules for the recorder server |

Frida 17.27.0 with `frida-server` for x86_64 was used. See [docs/03-tools-and-environment.md](../docs/03-tools-and-environment.md).
