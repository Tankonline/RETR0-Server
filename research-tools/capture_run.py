"""Project RETR0 - one recorded test session of Real Racing 3 on the locked test emulator.

Starts the game under retr0_redirect_java.js (Frida, Java level) for a fixed time and stores, in a new folder
under 08_TESTING/runtime/out/ (gitignored, because recordings contain the emulator's generated device ids):
    requests.jsonl   one JSON object per HTTP request the game started (full URL, headers, body length; record /
                     redirect modes only)
    bodies/<id>.bin  request bodies
    frida.log        everything else the hook printed
    logcat.txt       the whole Android log for the session
    screen_<n>m.png  a screenshot every minute
    summary.txt      request counts per method + host + path
Use only under RUNTIME_TEST_PLAN.md (owner approval, locked emulator, no real saves or accounts).

Safety checks before anything starts: exactly one emulator device; RETR0_LOCK active (avd_network_lock.sh);
frida-server running (started from /data/local/tmp if not). In redirect mode it also sets
`adb reverse tcp:<port> tcp:<port>` so redirected requests reach recorder_server.py on this PC.

Usage:
    python -I 08_TESTING/runtime/capture_run.py --mode record   --minutes 6
    python -I 08_TESTING/runtime/capture_run.py --mode redirect --minutes 6 --port 8780   (start recorder first)
    python -I 08_TESTING/runtime/capture_run.py --mode redirect --minutes 0   (play: no time limit, no screenshots)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PKG = "com.ea.games.r3_row"
ADB = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
FRIDA = ROOT / ".venv" / "Scripts" / "frida.exe"
HOOK = HERE / "retr0_redirect_java.js"


def adb(*args: str, check: bool = True, timeout: int = 60) -> str:
    r = subprocess.run([str(ADB), *args], capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    if check and r.returncode != 0:
        raise SystemExit(f"adb {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def preflight(mode: str, port: int) -> None:
    devices = [l.split()[0] for l in adb("devices").splitlines()[1:] if l.strip().endswith("device")]
    if len(devices) != 1 or not devices[0].startswith("emulator-"):
        raise SystemExit(f"need exactly one emulator device, found {devices}")
    if adb("shell", "id -u") != "0":
        adb("root"); time.sleep(2); adb("wait-for-device")
    if adb("shell", "iptables -w -C OUTPUT -j RETR0_LOCK >/dev/null 2>&1 && echo yes", check=False) != "yes":
        raise SystemExit("network is not locked: run  bash 08_TESTING/runtime/avd_network_lock.sh lock --allow-dns")
    if not adb("shell", "pidof frida-server", check=False):
        adb("shell", "(/data/local/tmp/frida-server -D >/dev/null 2>&1 &)")
        time.sleep(3)
        if not adb("shell", "pidof frida-server", check=False):
            raise SystemExit("frida-server is not running and could not be started")
    if mode == "redirect":
        adb("reverse", f"tcp:{port}", f"tcp:{port}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["log", "record", "redirect"], default="record")
    ap.add_argument("--minutes", type=float, default=6.0)
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--out", help="output folder (default: out/<time>_<mode>)")
    a = ap.parse_args()

    preflight(a.mode, a.port)
    out = Path(a.out) if a.out else HERE / "out" / f"{time.strftime('%Y%m%d_%H%M%S')}_{a.mode}"
    (out / "bodies").mkdir(parents=True, exist_ok=True)

    # Hook copy with the mode written in (the frida CLI has no script-parameter global).
    src = HOOK.read_text(encoding="utf-8")
    params = json.dumps({"mode": a.mode, "port": a.port})
    patched, n = re.subn(r"/\*RETR0_PARAMS\*/.*?/\*END\*/", lambda _m: params, src, count=1)
    if n != 1:
        raise SystemExit("PARAMS marker not found in the hook")
    tmpdir = Path(tempfile.mkdtemp(prefix="retr0_hook_"))
    hook = tmpdir / "hook.js"
    hook.write_text(patched, encoding="utf-8")

    adb("logcat", "-c", check=False)
    logcat_f = open(out / "logcat.txt", "w", encoding="utf-8", errors="replace")
    logcat = subprocess.Popen([str(ADB), "logcat", "-v", "threadtime"], stdout=logcat_f, stderr=subprocess.STDOUT)

    # --minutes 0 = play session: the hook stays attached until the game process ends. When a timed
    # session ends, frida detaches and the still-running game loses the redirect (every request then
    # fails with "Unable to resolve host", and online-gated screens such as Special Events lock).
    seconds = int(a.minutes * 60) if a.minutes > 0 else 30 * 24 * 3600
    print(f"[capture] mode={a.mode} minutes={a.minutes or 'until the game exits'} out={out}", flush=True)
    frida = subprocess.Popen([str(FRIDA), "-U", "-f", PKG, "-l", str(hook), "-q", "-t", str(seconds)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                             errors="replace", bufsize=1)

    def shots() -> None:
        for i in range(1, int(a.minutes) + 1):
            time.sleep(60)
            if frida.poll() is not None:
                return
            with open(out / f"screen_{i}m.png", "wb") as f:
                subprocess.run([str(ADB), "exec-out", "screencap", "-p"], stdout=f, timeout=30)
    if a.minutes > 0:
        threading.Thread(target=shots, daemon=True).start()

    summary: Counter[str] = Counter()
    with open(out / "requests.jsonl", "w", encoding="utf-8") as reqs, \
         open(out / "frida.log", "w", encoding="utf-8") as flog:
        assert frida.stdout is not None
        for line in frida.stdout:
            if line.startswith("RETR0JSON "):
                rec = json.loads(line[len("RETR0JSON "):])
                body = rec.pop("body_b64", "")
                if body:
                    (out / "bodies" / f"{rec['id']:05d}.bin").write_bytes(base64.b64decode(body))
                reqs.write(json.dumps(rec) + "\n"); reqs.flush()
                m = re.match(r"https?://([^/:?]+)(?::\d+)?([^?]*)", rec["url"])
                summary[f"{rec['method']} {m.group(1) if m else '?'} {m.group(2) if m else rec['url']}"] += 1
            else:
                flog.write(line); flog.flush()
                if "[RETR0]" in line and "[cc-http]" not in line and "[java-" not in line:
                    print(line.rstrip(), flush=True)
    frida.wait()
    logcat.terminate(); logcat_f.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    lines = [f"{c:6}  {k}" for k, c in summary.most_common()]
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[capture] done: {sum(summary.values())} requests recorded -> {out}", flush=True)
    print("\n".join(lines[:30]), flush=True)


if __name__ == "__main__":
    sys.exit(main())
