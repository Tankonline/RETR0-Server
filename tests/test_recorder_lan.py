"""Tests for the recorder (cdn) service's LAN mode: which client addresses it serves, and the discovery reply."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "services"))
import recorder_server as rs  # noqa: E402


def test_only_loopback_and_private_clients_are_served():
    for ok in ("127.0.0.1", "192.168.0.224", "10.1.2.3", "172.16.5.4", "172.31.255.1", "169.254.10.10",
               "::1", "::ffff:192.168.0.5", "fe80::1%12"):
        assert rs.client_allowed(ok), ok
    for bad in ("8.8.8.8", "26.10.20.30", "172.32.0.1", "100.64.1.1", "2001:db8::1", "::ffff:8.8.8.8", "nonsense", ""):
        assert not rs.client_allowed(bad), bad


def test_discovery_answers_only_the_exact_request_from_allowed_addresses():
    assert rs.discovery_reply(b"RETR0?", "192.168.0.224", 8780) == b"RETR0 8780"
    assert rs.discovery_reply(b"RETR0?\n", "10.0.0.2", 8780) == b"RETR0 8780"
    assert rs.discovery_reply(b"RETR0?", "8.8.8.8", 8780) is None
    assert rs.discovery_reply(b"HELLO", "192.168.0.224", 8780) is None


def _flaky_target():
    """A TCP server that resets the first connection (RST) and answers later ones with 200 'ok'."""
    import socket, struct, threading
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(8)
    seen = {"n": 0}

    def loop():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            seen["n"] += 1
            req = b""
            while b"\r\n\r\n" not in req:                     # read the whole request: headers, then the body
                chunk = c.recv(65536)
                if not chunk:
                    break
                req += chunk
            head, _, body = req.partition(b"\r\n\r\n")
            length = next((int(l.split(b":")[1]) for l in head.split(b"\r\n") if l.lower().startswith(b"content-length:")), 0)
            while len(body) < length:
                chunk = c.recv(65536)
                if not chunk:
                    break
                body += chunk
            if seen["n"] == 1:
                c.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))   # close with RST
            else:
                c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            c.close()
    threading.Thread(target=loop, daemon=True).start()
    return srv, seen


def _recorder(tmp_path, target_port):
    import threading
    from http.server import ThreadingHTTPServer
    out = tmp_path / "rec"; (out / "bodies").mkdir(parents=True)
    rules = [{"path": "^/", "proxy": f"http://127.0.0.1:{target_port}"}]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), rs.make_handler(rules, out))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _retry_scenario(tmp_path, method):
    """One run: returns (client status or None, statuses the recorder logged, attempts the upstream saw)."""
    import json, urllib.request, urllib.error
    target, seen = _flaky_target()
    httpd = _recorder(tmp_path, target.getsockname()[1])
    url = f"http://127.0.0.1:{httpd.server_address[1]}/retr0/cloudsave/0/k"
    try:
        code = urllib.request.urlopen(urllib.request.Request(url, data=b"x", method=method), timeout=10).status
    except urllib.error.HTTPError as e:
        code = e.code
    except OSError:                                   # reset / timeout on the client socket
        code = None
    httpd.shutdown(); target.close()
    logged = [json.loads(l)["status"] for l in (tmp_path / "rec" / "requests.jsonl").read_text().splitlines()]
    return code, logged, seen["n"]


def test_put_is_retried_once_after_a_reset_but_post_is_not(tmp_path):
    """PUT: the reset first attempt is retried (2 upstream attempts) and the client gets 200.
    POST: never replayed (1 attempt) and the client gets 502.
    On the development PC, plain stdlib HTTP over loopback loses about 1 exchange in 10 to a reset or timeout even
    with no RETR0 code involved (control test, run 35; likely the endpoint-protection network filter), so each
    scenario gets up to 3 tries and must pass strictly once."""
    for method, expect, attempts in (("PUT", 200, 2), ("POST", 502, 1)):
        runs = []
        for i in range(3):
            run = _retry_scenario(tmp_path / f"{method}{i}", method)
            runs.append(run)
            if run == (expect, [expect], attempts):
                break
        else:
            raise AssertionError((method, runs))
