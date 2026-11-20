"""Project RETR0 - independently operated local CloudCell-compatible service (clean-room, test use).

What it is: a small HTTP server that speaks the request/response format documented in
07_DOCUMENTATION/NETWORKING_ANALYSIS.md (section 8) using the clean-room codec. It has its own endpoints,
its own member ids and its own random tokens. It contains no EA code or data, never contacts EA
infrastructure, and accepts no EA credentials.

Scope (first slice):
  * POST .../CC_Sync.php
      - authentication requests  -> success reply with a locally issued member id and token
      - batched sync requests     -> one reply part per queued sub-sync, in order
  * PUT/GET /retr0/cloudsave/<member>/<key>  - local blob store for the cloud-save upload URL it hands out

Sub-sync handling: a few sub-syncs get real replies (server variables, cloud-save upload URL and validate,
PvP server list). Every other sub-sync gets an EMPTY part. The client already supports empty parts: a
failed sync (u32 ok = 0) completes every queued sub-sync with one. Whether each feature behaves well with
an empty part is UNVERIFIED until the runtime test.

Safety: binds 127.0.0.1 by default (the client's network config only allows cleartext to 127.0.0.1).
Identity strings from the client are never logged or stored; devices are keyed by a salted SHA-256.

Usage:
    .venv\\Scripts\\python -I 06_RECONSTRUCTION\\BACKEND\\local_service\\retr0_local_service.py --data-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import secrets
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloudcell_codec"))
import cloudcell_codec as cc  # noqa: E402

log = logging.getLogger("retr0.local_service")

TOKEN_TIMEOUT_S = 24 * 3600
CLOUDSAVE_PREFIX = "/retr0/cloudsave/"


class Store:
    """Persistent state in one JSON file plus cloud-save blobs. Thread-safe."""

    def __init__(self, data_dir: str | os.PathLike):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "state.json"
        self.lock = threading.Lock()
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.state = {"salt": secrets.token_hex(16), "next_member_id": 1000001,
                          "devices": {}, "tokens": {}, "server_variables": {}}
            self._save()

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def device_key(self, ids: tuple, strings: list[bytes]) -> str:
        h = hashlib.sha256(self.state["salt"].encode())
        for i in ids:
            h.update(i.to_bytes(4, "little"))
        for s in strings:
            h.update(len(s).to_bytes(4, "little") + s)
        return h.hexdigest()

    def authenticate(self, device: str) -> tuple[int, str]:
        with self.lock:
            rec = self.state["devices"].get(device)
            if rec is None:
                rec = {"member_id": self.state["next_member_id"]}
                self.state["next_member_id"] += 1
                self.state["devices"][device] = rec
            token = secrets.token_hex(16)
            self.state["tokens"][token] = rec["member_id"]
            self._save()
            return rec["member_id"], token

    def token_member(self, token: str) -> int | None:
        with self.lock:
            return self.state["tokens"].get(token)

    def server_variables(self) -> dict[str, str]:
        with self.lock:
            return dict(self.state.get("server_variables", {}))

    # ---- published FileManager files (served through sub-sync 13/448) -------------------------------
    @staticmethod
    def _check_file_name(name: str) -> str:
        # Allow-list: every seed file name uses only these characters (e.g. "12", "cc_webbrowser_logo@2x.png").
        if (not name or len(name) > 128 or name in (".", "..")
                or any(not (c.isascii() and (c.isalnum() or c in "._@-")) for c in name)):
            raise ValueError(f"unsafe FileManager file name {name!r}")
        return name

    def publish_file(self, name: str, payload: bytes) -> int:
        """Store a file to push to clients. Returns its new version (bumped on every publish)."""
        self._check_file_name(name)
        d = self.dir / "files"
        d.mkdir(exist_ok=True)
        with self.lock:
            files = self.state.setdefault("files", {})
            ver = int(files.get(name, {}).get("version", 0)) + 1
            (d / name).write_bytes(payload)
            files[name] = {"version": ver}
            self._save()
            return ver

    def published_files(self) -> dict[str, int]:
        with self.lock:
            return {n: int(v["version"]) for n, v in self.state.get("files", {}).items()}

    def file_payload(self, name: str) -> bytes:
        return (self.dir / "files" / self._check_file_name(name)).read_bytes()

    # ---- RETR0 preservation grants, delivered as CloudCell ad-hoc gifts (STORE_PRESERVATION_GRANTS.md) ----
    def queue_gift(self, product_id: int, metadata: str, source: str) -> int:
        """Queue one gift for delivery through sub-sync 10480. Returns its unique gift id (the client skips gift
        ids it already holds, SP-10)."""
        with self.lock:
            g = self.state.setdefault("gifts", {"next_id": 1, "pending": [], "claimed": []})
            gid = g["next_id"]
            g["next_id"] += 1
            g["pending"].append({"id": gid, "product_id": product_id, "metadata": metadata, "source": source,
                                 "queued": int(time.time())})
            self._save()
            return gid

    def pending_gifts(self) -> list[dict]:
        with self.lock:
            return [dict(x) for x in self.state.get("gifts", {}).get("pending", [])]

    def claim_gifts(self, ids: set[int]) -> list[int]:
        """Mark gifts the client acknowledged (sub-sync 10481) as delivered so they are never sent again."""
        with self.lock:
            g = self.state.get("gifts")
            if not g:
                return []
            done = [x for x in g["pending"] if x["id"] in ids]
            g["pending"] = [x for x in g["pending"] if x["id"] not in ids]
            now = int(time.time())
            for x in done:
                x["claimed"] = now
            g["claimed"].extend(done)
            self._save()
            return [x["id"] for x in done]

    def cloudsave_path(self, member: str, key: str) -> Path:
        if not (member.isdigit() and key.replace("-", "").isalnum()):
            raise ValueError("bad cloud-save path")
        p = (self.dir / "cloudsave" / member / key).resolve()
        if (self.dir / "cloudsave").resolve() not in p.parents:
            raise ValueError("path escapes data dir")
        return p


class Service:
    """Protocol logic, independent of HTTP so it can be tested directly."""

    def __init__(self, store: Store, base_url: str, game_config_defaults: dict[int, str] | None = None):
        self.store = store
        self.base_url = base_url.rstrip("/")
        # Defaults from the user's own CC_SeedData.bin (seed file "1"), loaded at start-up, never copied into
        # the repo. state.json "game_config" entries ({"id": "value"}) override them.
        self.game_config_defaults = dict(game_config_defaults or {})
        self.handlers = {
            cc.SUBSYNC_FILE_MANAGER: self._file_manager,
            cc.SUBSYNC_GAME_CONFIG: self._game_config,
            cc.SUBSYNC_SERVER_VARIABLES: self._server_variables,
            cc.SUBSYNC_GSM_UPLOAD_REQUEST: self._gsm_upload_request,
            cc.SUBSYNC_GSM_VALIDATE: lambda m, d: cc.gsm_validate_response(True),
            cc.SUBSYNC_GET_PVP_SERVERS: lambda m, d: cc.pvp_servers_response([]),
            (10480, 5610): self._fetch_gifts,      # cc::GiftManager FetchAdHocGifts (SP-08)
            (10481, 1): self._claim_gifts,         # cc::GiftManager acknowledge (SP-09)
            (10632, 2369): self._promo_code,       # racing code (NW catalogue; reply parsed by 0x15170e0)
        }
        # Currency packages allowed for preservation grants: product id -> catalogue metadata string, taken from
        # the owner's store catalogue (seed file 12). Set by serve() when --seed-data is given.
        self.grant_packages: dict[int, str] = {}

    def _fetch_gifts(self, member: int, payload: bytes) -> bytes:
        """Reply: u32 count, then per gift u32 gift_id, u32 product_id, lp, lp, lp (SP-08/SP-10). The reward
        string (catalogue metadata, e.g. "type:wrench, qty:16, ...") is put in all three strings because which
        one the client copies is not yet established; to be narrowed by testing."""
        gifts = self.store.pending_gifts()
        out = struct.pack("<I", len(gifts))
        for g in gifts:
            out += struct.pack("<II", g["id"], g["product_id"]) + b"".join(cc.lp_string(g["metadata"]) for _ in range(3))
        if gifts:
            log.info("gifts: offering %s", [(g["id"], g["product_id"]) for g in gifts])
        return out

    def _promo_code(self, member: int, payload: bytes) -> bytes:
        """Racing code. Request: lp code. Reply (0x15170e0): lp code (echoed; the client compares it), bool32 ok,
        and when ok an lp reward list. In the RETR0 client the racing code is the username setter: the patched
        client already wrote the typed code (minus a leading "NAME ") to doc/retr0_username.txt, so the server
        confirms every non-empty code with no rewards. This server hands out no promo rewards."""
        try:
            (n,) = struct.unpack_from("<I", payload, 0)
            code = payload[4:4 + n]
        except struct.error:
            log.warning("promo: malformed 10632 request (%d bytes)", len(payload))
            return b""
        name = code[5:] if code[:5].lower() == b"name " else code
        ok = len(name) > 0
        log.info("racing code from member %d: %s", member, "username change" if ok else "empty")
        out = cc.lp_string(code) + struct.pack("<I", int(ok))
        return out + cc.lp_string(b"") if ok else out

    def _claim_gifts(self, member: int, payload: bytes) -> bytes:
        """Request: u32 count, per gift u32, u32, lp, u32 flag (SP-09). Marks the listed gift ids delivered."""
        ids = set()
        try:
            (n,) = struct.unpack_from("<I", payload, 0)
            o = 4
            for _ in range(min(n, 1000)):
                a, b = struct.unpack_from("<II", payload, o)
                o += 8
                (sl,) = struct.unpack_from("<I", payload, o)
                o += 4 + sl + 4
                ids.add(a)
        except struct.error:
            log.warning("gifts: malformed 10481 request (%d bytes)", len(payload))
        claimed = self.store.claim_gifts(ids)
        log.info("gifts: client acknowledged %s; marked delivered %s", sorted(ids), claimed)
        return b""

    def grant(self, product_id: int, source: str) -> int:
        """Queue a preservation grant for an allowed currency package. The amount comes only from the catalogue."""
        meta = self.grant_packages.get(product_id)
        if meta is None:
            raise ValueError(f"product {product_id} is not an allowed currency package")
        gid = self.store.queue_gift(product_id, meta, source)
        log.info("grant queued: gift %d = product %d (%s) from %s", gid, product_id, meta, source)
        return gid

    @staticmethod
    def server_value() -> int:
        # The u32 both replies hand to the same CloudCell sub-object. [likely] server time; unverified.
        return int(time.time()) & 0xFFFFFFFF

    def handle_post(self, raw: bytes) -> bytes:
        body = cc.unwrap(raw)
        try:
            req = cc.parse_sync_request(body)
        except ValueError:
            req = None
        if req is not None:
            return cc.wrap_request(self._sync(req))
        try:
            auth = cc.parse_auth_request(body)
        except ValueError as e:
            raise ValueError(f"neither a sync nor an auth request: {e}") from None
        return cc.wrap_request(self._auth(auth))

    def _auth(self, req: dict) -> bytes:
        device = self.store.device_key(req["ids"], req["strings"])
        member_id, token = self.store.authenticate(device)
        log.info("auth: state=%s -> member %d", cc.AUTH_STATES[req["state"]] if req["state"] < 9 else req["state"],
                 member_id)
        return cc.auth_success_reply(member_id, token, TOKEN_TIMEOUT_S, value=self.server_value())

    def _sync(self, req: dict) -> bytes:
        member = self.store.token_member(req["token"])
        if member is None or member != req["member_id"]:
            log.warning("sync with unknown token or member mismatch (member %d); answering anyway",
                        req["member_id"])
            member = req["member_id"]
        parts = []
        for sub_type, param, payload in req["subsyncs"]:
            h = self.handlers.get((sub_type, param))
            part = h(member, payload) if h else b""
            log.info("sub-sync %d/%d: %d-byte request -> %s", sub_type, param, len(payload),
                     f"{len(part)}-byte reply" if h else "empty part (no handler)")
            parts.append(part)
        # Echo the member id the client sent, so the header never reports a member change (CloudCell
        # LegacyManager 0x1cfb784). Before 2026-11-19 the header was missing and the client read the first
        # reply parts as these fields (garbage member ids, empty sub-sync replies, UnpackData asserts).
        return cc.sync_response_body(parts, value=self.server_value(), member_id=req["member_id"])

    def _file_manager(self, member: int, payload: bytes) -> bytes:
        """Send published files whose version differs from what the client reports. The client already has
        the seed files from its own CC_SeedData.bin; only files published here are pushed. Files the client
        did not list are pushed too. Nothing is ever deleted."""
        try:
            client = dict(cc.parse_file_manager_request(payload))
        except (struct.error, ValueError):
            log.warning("unreadable FileManager request (%d bytes); sending no changes", len(payload))
            client = {}
        updates = []
        for name, ver in sorted(self.store.published_files().items()):
            if client.get(name) != ver:
                updates.append((False, name, ver, self.store.file_payload(name)))
                log.info("FileManager: pushing %s v%d (client has %s)", name, ver, client.get(name, "none"))
        return cc.file_manager_response(updates) if updates else b""

    def _game_config(self, member: int, payload: bytes) -> bytes:
        values = dict(self.game_config_defaults)
        with self.store.lock:
            values.update({int(k): str(v) for k, v in self.store.state.get("game_config", {}).items()})
        return cc.game_config_response(values)

    def _server_variables(self, member: int, payload: bytes) -> bytes:
        return cc.server_variables_response(self.store.server_variables())

    def _gsm_upload_request(self, member: int, payload: bytes) -> bytes:
        key = secrets.token_hex(8)
        return cc.gsm_upload_response(key, f"{self.base_url}{CLOUDSAVE_PREFIX}{member}/{key}")


def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RETR0-local/0.1"
        # HTTP/1.1 keep-alive: the client closes the connection, not the server. On the development
        # machine a server-initiated close on loopback was frequently delivered to the client as a
        # connection reset before it had read the response (reproduced with the stdlib server alone).
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # route through logging, without client identity data
            log.debug("http %s", fmt % args)

        def _send(self, code: int, data: bytes = b"", ctype="application/octet-stream"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> bytes:
            n = int(self.headers.get("Content-Length", "0"))
            if n > 64 * 1024 * 1024:
                raise ValueError("body too large")
            return self.rfile.read(n)

        def do_POST(self):
            try:
                body = self._body()          # always consume the body, so the connection stays usable
            except ValueError:
                self.close_connection = True
                return self._send(413)
            if self.path.split("?")[0] == "/retr0/admin/gift":
                # Operator-only: reachable on this service's own port from this PC. The emulator only reaches the
                # recorder (adb reverse 8780), which forwards CC_Sync.php and cloud saves, never this path.
                if self.client_address[0] not in ("127.0.0.1", "::1"):
                    return self._send(403)
                from urllib.parse import parse_qs, urlsplit
                q = parse_qs(urlsplit(self.path).query)
                try:
                    gid = service.grant(int(q.get("product", ["0"])[0]), source="admin")
                except ValueError as e:
                    return self._send(400, str(e).encode())
                return self._send(200, json.dumps({"gift_id": gid}).encode())
            if not self.path.split("?")[0].endswith("CC_Sync.php"):
                return self._send(404)
            try:
                self._send(200, service.handle_post(body))
            except ValueError as e:
                log.warning("bad request: %s", e)
                self._send(400)

        def _cloudsave(self):
            rest = self.path.split("?")[0][len(CLOUDSAVE_PREFIX):].split("/")
            if len(rest) != 2:
                raise ValueError("bad cloud-save path")
            return service.store.cloudsave_path(*rest)

        def do_PUT(self):
            try:
                body = self._body()
            except ValueError:
                self.close_connection = True
                return self._send(413)
            if not self.path.startswith(CLOUDSAVE_PREFIX):
                return self._send(404)
            try:
                p = self._cloudsave()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(body)
                self._send(200)
            except ValueError:
                self._send(400)

        def do_GET(self):
            if not self.path.startswith(CLOUDSAVE_PREFIX):
                return self._send(404)
            try:
                p = self._cloudsave()
            except ValueError:
                return self._send(400)
            if not p.exists():
                return self._send(404)
            self._send(200, p.read_bytes())

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # A client closing its keep-alive connection surfaces as a reset; that is not an error.
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


def _add_seed_decoder_path() -> None:
    """seed_data_decode.py lives in SCRIPTS/ in the project, or next to this service's folder in the server package."""
    here = Path(__file__).resolve()
    for p in (here.parents[1], here.parents[3] / "SCRIPTS"):
        if (p / "seed_data_decode.py").is_file() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


def load_currency_packages(seed_path: str) -> dict[int, str]:
    """Allowed preservation-grant packages: Gold (type:wrench), R$ (type:money) and M$ (type:mdollars) products
    of the owner's store catalogue (seed file 12, NW-91), product id -> metadata string."""
    _add_seed_decoder_path()
    import seed_data_decode as sd
    data = Path(seed_path).read_bytes()
    cat = sd.parse_store_catalogue(sd.seed_blob(data, sd.parse(data), "12"))
    prods = cat["products"] if isinstance(cat, dict) else cat
    out = {}
    for p in prods:
        meta = str(p.get("metadata", ""))
        kind = meta.split(",")[0].strip()
        if kind in ("type:wrench", "type:money", "type:mdollars") and "qty:" in meta:
            out[int(p["product_id"])] = meta
    return out


def load_seed_game_config(seed_path: str) -> dict[int, str]:
    """Game-config defaults from the user's CC_SeedData.bin (SCRIPTS/seed_data_decode.py)."""
    _add_seed_decoder_path()
    import seed_data_decode as sd
    data = Path(seed_path).read_bytes()
    return sd.parse_game_config(sd.seed_blob(data, sd.parse(data), "1"))["values"]


def publish_files(store: Store, pairs: list[str], seed_names: list[str], seed_path: str | None) -> None:
    for item in pairs:
        name, sep, path = item.partition("=")
        if not sep:
            raise SystemExit(f"--publish expects NAME=PATH, got {item!r}")
        log.info("published %s v%d", name, store.publish_file(name, Path(path).read_bytes()))
    if seed_names:
        if not seed_path:
            raise SystemExit("--publish-from-seed needs --seed-data")
        _add_seed_decoder_path()
        import seed_data_decode as sd
        data = Path(seed_path).read_bytes()
        entries = {e["name"]: e for e in sd.parse(data) if e["type"] == "file"}
        for name in seed_names:
            e = entries.get(name)
            if e is None:
                raise SystemExit(f"{name!r} is not in the seed archive")
            ver = store.publish_file(name, data[e["offset"]: e["offset"] + e["size"]])
            log.info("published seed file %s v%d", name, ver)


def serve(host: str, port: int, data_dir: str, tls_cert: str | None = None, tls_key: str | None = None,
          public_base: str | None = None, seed_data: str | None = None) -> ThreadingHTTPServer:
    """Create the server. With tls_cert/tls_key it speaks HTTPS: the client always syncs over HTTPS
    (port constant 443 in .rodata, NETWORKING_ANALYSIS NW-85) and its CloudCell TLS trust manager accepts
    any certificate (K-16), so a locally generated self-signed certificate is sufficient.
    public_base overrides the base URL handed out for cloud-save uploads (e.g. the address as the device
    sees it through a port forward)."""
    store = Store(data_dir)
    httpd = _Server((host, port), None)
    scheme = "http"
    if tls_cert:
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(tls_cert, tls_key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"
    defaults = load_seed_game_config(seed_data) if seed_data else None
    service = Service(store, public_base or f"{scheme}://{host}:{httpd.server_address[1]}", defaults)
    if seed_data:
        service.grant_packages = load_currency_packages(seed_data)
        log.info("preservation grants: %d currency packages from the store catalogue", len(service.grant_packages))
    httpd.RequestHandlerClass = make_handler(service)
    return httpd


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--tls-cert", help="PEM certificate: serve HTTPS (the client syncs over HTTPS)")
    ap.add_argument("--tls-key", help="PEM private key for --tls-cert")
    ap.add_argument("--public-base", help="base URL the device should use for cloud-save uploads")
    ap.add_argument("--log-file", help="also write the log to this file")
    ap.add_argument("--seed-data", help="your CC_SeedData.bin: serve its game-config defaults (sub-sync 10631)")
    ap.add_argument("--publish", action="append", default=[], metavar="NAME=PATH",
                    help="publish a FileManager file (pushed through sub-sync 13/448); bumps its version")
    ap.add_argument("--publish-from-seed", action="append", default=[], metavar="NAME",
                    help="publish a file exactly as stored in --seed-data (e.g. 12 = store catalogue)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    handlers = [logging.StreamHandler()]
    if a.log_file:
        handlers.append(logging.FileHandler(a.log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(message)s", handlers=handlers)
    if a.host not in ("127.0.0.1", "localhost", "::1"):
        log.warning("listening on %s, not loopback", a.host)
    publish_files(Store(a.data_dir), a.publish, a.publish_from_seed, a.seed_data)
    httpd = serve(a.host, a.port, a.data_dir, a.tls_cert, a.tls_key, a.public_base, a.seed_data)
    scheme = "https" if a.tls_cert else "http"
    log.info("RETR0 local service on %s://%s:%d (data: %s)", scheme, a.host, httpd.server_address[1], a.data_dir)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
