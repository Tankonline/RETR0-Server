"""Project RETR0 - local recorder server for the test emulator. Independently operated; binds to 127.0.0.1 only.

retr0_redirect_java.js (mode 'redirect') sends the game's CloudCell and asset-CDN requests here through
`adb reverse tcp:8780 tcp:8780`, adding header X-RETR0-Host with the host the game originally asked for.
Every request is recorded; the answer comes from the first matching rule, so responses can be built up step by
step while watching how the client reacts. No rule matched -> 404 with an empty body.

Rules file (JSON list, first match wins; every key except the action is optional):
  {"host": "regex on X-RETR0-Host", "method": "POST", "path": "regex on the path (no query)",
   one action of:
     "status": 200, "body": "text", "content_type": "text/plain"     fixed answer
         (+ optional "headers": {"Name": "value"}; "{unix_time}" in a value becomes the current Unix time in
          seconds with milliseconds, e.g. for /time: {"X-Request-Start": "{unix_time}"})
     "proxy": "http://127.0.0.1:8781"                                 forward unchanged (e.g. retr0_local_service.py)
     "dir": "folder"   (+ optional "strip": "regex removed from the path first")
                                                                      serve files, honouring Range (206)
  }
Example: 08_TESTING/runtime/recorder_rules.example.json

Records under --out (default 08_TESTING/runtime/out/recorder_<time>/, gitignored):
  requests.jsonl  {n, time, method, host, path, query, headers, body_len, rule, status, resp_len}
  bodies/<n>.bin  request bodies

Usage: python -I 08_TESTING/runtime/recorder_server.py [--rules rules.json] [--port 8780] [--out folder]
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_BODY = 64 * 1024 * 1024
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")
HOST_PREFIX_RE = re.compile(r"^/_retr0host/([A-Za-z0-9.-]{1,253})(/.*)?$")


def load_rules(path: str | None) -> list[dict]:
    if not path:
        return []
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    for r in rules:
        if sum(k in r for k in ("status", "proxy", "dir")) != 1:
            raise SystemExit(f"rule needs exactly one of status/proxy/dir: {r}")
        for k in ("host", "path"):
            if k in r:
                re.compile(r[k])
    return rules


def make_handler(rules: list[dict], out: Path):
    lock = threading.Lock()
    counter = {"n": 0}
    reqlog = open(out / "requests.jsonl", "a", encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "RETR0-recorder"

        def log_message(self, fmt, *args):   # quiet default access log; we keep our own
            pass

        def _handle(self):
            n_len = int(self.headers.get("Content-Length", "0") or 0)
            if n_len > MAX_BODY:
                self.close_connection = True
                return self._reply(413, b"", "too large", {}, None)
            body = self.rfile.read(n_len) if n_len else b""
            host = self.headers.get("X-RETR0-Host", "")
            # The native RETR0 client redirect can't add headers, so it puts the original host in the path:
            #   /_retr0host/<host>/<original path>   (e.g. /_retr0host/0037-connect.cloudcell.com/CC_Sync.php)
            m = HOST_PREFIX_RE.match(self.path)
            if m:
                host = host or m.group(1)
                self.path = m.group(2) or "/"
            path, _, query = self.path.partition("?")
            with lock:
                counter["n"] += 1
                n = counter["n"]
            if body:
                (out / "bodies" / f"{n:06d}.bin").write_bytes(body)
            rec = {"n": n, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "method": self.command, "host": host,
                   "path": path, "query": query, "headers": dict(self.headers.items()), "body_len": len(body)}
            rule = next((r for r in rules
                         if re.search(r.get("host", ""), host) and re.search(r.get("path", ""), path)
                         and r.get("method", self.command) == self.command), None)
            rec["rule"] = rules.index(rule) if rule else None
            try:
                if rule is None:
                    status, data, ctype, extra = 404, b"", "text/plain", {}
                elif "status" in rule:
                    status, data = rule["status"], rule.get("body", "").encode("utf-8")
                    now = f"{time.time():.3f}"
                    ctype = rule.get("content_type", "text/plain")
                    extra = {k: str(v).replace("{unix_time}", now) for k, v in rule.get("headers", {}).items()}
                    if extra:
                        rec["resp_headers"] = extra
                elif "proxy" in rule:
                    status, data, ctype, extra = self._proxy(rule["proxy"], body)
                else:
                    status, data, ctype, extra = self._file(rule, path)
            except Exception as e:   # record the failure, never crash the server
                status, data, ctype, extra = 502, b"", "text/plain", {}
                rec["error"] = repr(e)
            self._reply(status, data, ctype, extra, rec)
            with lock:
                reqlog.write(json.dumps(rec) + "\n"); reqlog.flush()
            print(f"{n:6} {self.command:4} {host or '-':32} {path[:70]:70} -> {status} {len(data)}B", flush=True)

        def _proxy(self, base: str, body: bytes):
            hdrs = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "x-retr0-host")}
            req = urllib.request.Request(base.rstrip("/") + self.path, data=body if body else None,
                                         method=self.command, headers=hdrs)
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.status, r.read(), r.headers.get("Content-Type", "application/octet-stream"), {}
            except urllib.error.HTTPError as e:
                return e.code, e.read(), e.headers.get("Content-Type", "text/plain"), {}

        def _file(self, rule: dict, path: str):
            rel = re.sub(rule["strip"], "", path) if "strip" in rule else path
            base = Path(rule["dir"]).resolve()
            f = (base / rel.lstrip("/")).resolve()
            if base not in f.parents and f != base or not f.is_file():
                return 404, b"", "text/plain", {}
            size = f.stat().st_size
            m = RANGE_RE.match(self.headers.get("Range", "").strip())
            if not m:
                return 200, f.read_bytes(), "application/octet-stream", {"Accept-Ranges": "bytes"}
            a, b = m.group(1), m.group(2)
            start = int(a) if a else max(0, size - int(b))
            end = min(int(b), size - 1) if (a and b) else size - 1
            if start >= size or start > end:
                return 416, b"", "text/plain", {"Content-Range": f"bytes */{size}"}
            with open(f, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start + 1)
            return 206, data, "application/octet-stream", {"Content-Range": f"bytes {start}-{end}/{size}",
                                                           "Accept-Ranges": "bytes"}

        def _reply(self, status, data, ctype, extra, rec):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in extra.items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
            if rec is not None:
                rec["status"], rec["resp_len"] = status, len(data)

        do_GET = do_POST = do_PUT = do_HEAD = do_DELETE = _handle

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        if isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return   # client closed a kept-alive connection; normal
        super().handle_error(request, client_address)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--rules")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("refusing to listen on a non-loopback address")
    rules = load_rules(a.rules)
    out = Path(a.out) if a.out else HERE / "out" / f"recorder_{time.strftime('%Y%m%d_%H%M%S')}"
    (out / "bodies").mkdir(parents=True, exist_ok=True)
    httpd = _Server((a.host, a.port), make_handler(rules, out))
    print(f"recorder on http://{a.host}:{a.port}  rules={len(rules)}  out={out}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
