"""Tests for the RETR0 local service and the request/auth parsers it relies on.

These check internal consistency against the documented formats (NETWORKING_ANALYSIS §8.21). They do not
prove the real client accepts the replies: that needs the approved runtime test.
"""
import struct
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "services" / "cloudcell_codec"))
sys.path.insert(0, str(ROOT / "server" / "services" / "local_service"))
import cloudcell_codec as cc  # noqa: E402
import retr0_local_service as svc  # noqa: E402


def _auth_body(state=1, member=0, identity="device-abc"):
    return cc.build_auth_request(state, member, ids=(7, 8, 9),
                                 strings=(identity, "a", "b", "c", "d", "e", "f"),
                                 identities=[(0, ["prov", "uid", "secret-token", "name"])], flag=0)


def _read_auth_reply(body):
    ok, value, state, member, dev, ua, ub, fc = struct.unpack_from("<8I", body)
    (n,) = struct.unpack_from("<I", body, 32)
    token = body[36:36 + n].decode()
    (timeout,) = struct.unpack_from("<I", body, 36 + n)
    assert 40 + n == len(body)
    return ok, state, member, dev, token, timeout


def test_sync_request_roundtrip():
    subs = [cc.pack_subsync(*cc.SUBSYNC_SERVER_VARIABLES, b"\x05\x00\x00\x00")]
    body = cc.build_sync_request([(10712, 4373, b"\x05\x00\x00\x00"), (47, 7277, b"\x01\x00\x00\x00")],
                                 member_id=1000001, token="tok", s0="x",
                                 tags=[(0, "a"), (1, "b"), (3, "c"), (6, "d"), (4, "e"), (5, "f")])
    req = cc.parse_sync_request(body)
    assert req["member_id"] == 1000001 and req["token"] == "tok" and req["auth_kind"] == 3
    assert [(t, p) for t, p, _ in req["subsyncs"]] == [(10712, 4373), (47, 7277)]
    assert [k for k, _ in req["tags"]] == [0, 1, 3, 6, 4, 5]
    assert subs  # helper consistency


def test_auth_request_roundtrip_and_strictness():
    body = _auth_body()
    req = cc.parse_auth_request(body)
    assert req["state"] == 1 and req["member_id"] == 0 and len(req["strings"]) == 7
    with pytest.raises(ValueError):
        cc.parse_auth_request(body + b"\x00")          # must consume the whole body
    with pytest.raises(ValueError):
        cc.parse_sync_request(body)                    # an auth body is not a sync body


def test_auth_success_reply_layout():
    r = cc.auth_success_reply(1000001, "abcd", 3600, value=42)
    ok, state, member, dev, token, timeout = _read_auth_reply(r)
    assert (ok, state, member, dev, token, timeout) == (1, 2, 1000001, 0, "abcd", 3600)
    assert cc.auth_failure_reply() == b"\x00\x00\x00\x00"


@pytest.fixture
def service(tmp_path):
    store = svc.Store(tmp_path / "data")
    return svc.Service(store, "http://127.0.0.1:8780")


def test_auth_issues_stable_member_and_fresh_tokens(service):
    r1 = _read_auth_reply(cc.unwrap(service.handle_post(cc.wrap_request(_auth_body()))))
    r2 = _read_auth_reply(cc.unwrap(service.handle_post(cc.wrap_request(_auth_body(state=4, member=r1[2])))))
    other = _read_auth_reply(cc.unwrap(service.handle_post(cc.wrap_request(_auth_body(identity="other")))))
    assert r1[0] == 1 and r1[1] == 2
    assert r1[2] == r2[2] != other[2]
    assert r1[4] != r2[4]


def test_identity_strings_are_not_stored(service, tmp_path):
    service.handle_post(cc.wrap_request(_auth_body(identity="device-abc")))
    state_text = (tmp_path / "data" / "state.json").read_text()
    for secret in ("device-abc", "secret-token", "uid"):
        assert secret not in state_text


def test_sync_reply_has_one_part_per_subsync_in_order(service):
    auth = _read_auth_reply(cc.unwrap(service.handle_post(cc.wrap_request(_auth_body()))))
    service.store.state["server_variables"] = {"RRTV_Enabled": "0"}
    body = cc.build_sync_request([(10712, 4373, b"\x05\x00\x00\x00"),
                                  (12345, 1, b"unknown"),
                                  (10660, 5638, cc.gsm_upload_request(1, "a", "b"))],
                                 member_id=auth[2], token=auth[4])
    reply = cc.unwrap(service.handle_post(cc.wrap_request(body)))
    ok, value = struct.unpack_from("<II", reply)
    assert ok == 1
    member, dev, device, u_b, flag = struct.unpack_from("<IIIII", reply, 8)   # LegacyManager header
    assert member == auth[2] and (dev, device, u_b, flag) == (0, 0, 0, 0)
    off, parts = 28, []
    for _ in range(3):
        (n,) = struct.unpack_from("<I", reply, off)
        parts.append(reply[off + 4: off + 4 + n])
        off += 4 + n
    assert off == len(reply)
    assert cc.parse_server_variables_response(parts[0]) == [("RRTV_Enabled", "0")]
    assert parts[1] == b""                                   # no handler -> empty part
    status, = struct.unpack_from("<I", parts[2])
    assert status == 0 and b"http://127.0.0.1:8780/retr0/cloudsave/" in parts[2]


def test_garbage_is_rejected(service):
    with pytest.raises(ValueError):
        service.handle_post(cc.wrap_request(b"\x01\x02\x03\x04"))


def test_cloudsave_paths_cannot_escape(service):
    for member, key in (("..", "x"), ("1", "../x"), ("1", "a/b"), ("x1", "k")):
        with pytest.raises(ValueError):
            service.store.cloudsave_path(member, key)


def test_https_with_self_signed_certificate(tmp_path):
    """The client syncs over HTTPS; check the service serves it with a locally generated certificate.
    Needs the openssl command line tool (shipped with Git for Windows); fails loudly if it is missing."""
    import http.client
    import shutil
    import ssl
    import subprocess
    openssl = shutil.which("openssl")
    assert openssl, "openssl CLI not found on PATH (needed to generate a test certificate)"
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=retr0-local-test", "-addext", "subjectAltName=IP:127.0.0.1",
                    "-keyout", str(key), "-out", str(cert)],
                   check=True, capture_output=True)
    httpd = svc.serve("127.0.0.1", 0, str(tmp_path / "data"), str(cert), str(key))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    # Verify against the generated certificate (the game itself would accept any certificate, K-16).
    ctx = ssl.create_default_context(cafile=str(cert))
    conn = http.client.HTTPSConnection("127.0.0.1", httpd.server_address[1], timeout=10, context=ctx)
    try:
        conn.request("POST", "/CC_Sync.php", body=cc.wrap_request(_auth_body()))
        r = conn.getresponse()
        assert r.status == 200
        assert _read_auth_reply(cc.unwrap(r.read()))[1] == 2
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()


def test_http_end_to_end(tmp_path):
    """Over real loopback HTTP, with a keep-alive client (as Android's HttpURLConnection behaves)."""
    import http.client
    httpd = svc.serve("127.0.0.1", 0, str(tmp_path / "data"))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        def call(method, path, body=None):
            conn.request(method, path, body=body)
            r = conn.getresponse()
            return r.status, r.read()

        status, raw = call("POST", "/CC_Sync.php", cc.wrap_request(_auth_body()))
        assert status == 200
        auth = _read_auth_reply(cc.unwrap(raw))
        status, raw = call("POST", "/CC_Sync.php", cc.wrap_request(cc.build_sync_request(
            [(10660, 5638, cc.gsm_upload_request(1, "a", "b"))], member_id=auth[2], token=auth[4])))
        assert status == 200
        reply = cc.unwrap(raw)
        (n,) = struct.unpack_from("<I", reply, 28)          # after ok, value and the 20-byte member header
        part = reply[32:32 + n]
        (klen,) = struct.unpack_from("<I", part, 4)
        (ulen,) = struct.unpack_from("<I", part, 8 + klen)
        url = part[12 + klen: 12 + klen + ulen].decode()
        assert url.startswith(base + "/retr0/cloudsave/")
        path = url[len(base):]
        assert call("PUT", path, b"SAVE-BYTES")[0] == 200
        assert call("GET", path) == (200, b"SAVE-BYTES")
        assert call("POST", "/CC_Sync.php", b"junk")[0] == 400
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()


def test_file_manager_codec_roundtrip():
    req = cc.file_manager_request([("1", 5), ("12", 7)])
    assert cc.parse_file_manager_request(req) == [("1", 5), ("12", 7)]
    rep = cc.file_manager_response([(False, "12", 8, b"DATA"), (True, "dir", 1, b"")], ["old"])
    assert cc.parse_file_manager_response(rep) == ([(False, "12", 8, b"DATA"), (True, "dir", 1, b"")], ["old"])


def test_file_manager_pushes_only_changed_published_files(service):
    assert service.handlers[cc.SUBSYNC_FILE_MANAGER](1, cc.file_manager_request([("1", 3)])) == b""  # nothing published
    v12 = service.store.publish_file("12", b"catalogue-v1")
    v99 = service.store.publish_file("99", b"new-file")
    # client already has 12 at the published version, does not know 99
    rep = service.handlers[cc.SUBSYNC_FILE_MANAGER](1, cc.file_manager_request([("12", v12), ("1", 3)]))
    ups, dels = cc.parse_file_manager_response(rep)
    assert ups == [(False, "99", v99, b"new-file")] and dels == []
    # republishing bumps the version and the client gets it again
    v12b = service.store.publish_file("12", b"catalogue-v2")
    assert v12b == v12 + 1
    ups, _ = cc.parse_file_manager_response(
        service.handlers[cc.SUBSYNC_FILE_MANAGER](1, cc.file_manager_request([("12", v12), ("99", v99)])))
    assert ups == [(False, "12", v12b, b"catalogue-v2")]


def test_file_manager_rejects_unsafe_names(service):
    for bad in ("../x", "a/b", "a\\b", "", "..", "a\x08", "a:b", "\u00fc", "a b"):
        with pytest.raises(ValueError):
            service.store.publish_file(bad, b"x")


def test_publish_from_seed_copies_boxed_bytes(tmp_path):
    sys.path.insert(0, str(ROOT / "server" / "services"))
    import seed_data_decode as sd
    boxed = cc.box(cc.box(b"payload", cc.ZLIB), cc.XOR)
    seed = tmp_path / "seed.bin"
    d = b"12".decode()
    directory = struct.pack("<II", 0, 2) + d.encode() + struct.pack("<I", len(boxed))
    seed.write_bytes(sd.MAGIC + struct.pack("<I", len(directory)) + directory + boxed)
    store = svc.Store(tmp_path / "data")
    svc.publish_files(store, [], ["12"], str(seed))
    assert store.file_payload("12") == boxed and store.published_files() == {"12": 1}
    assert cc.unbox(cc.unbox(store.file_payload("12"))) == b"payload"


def test_gift_reply_uses_offerwall_kind_and_first_string(service):
    """SP-16: the client's gift listener (0xcd3cfc) switches on the second u32 (kind 2 = claimable offerwall gift,
    any value other than 0/2 is dropped) and stores only the first string. Amounts come from the catalogue."""
    meta = "type:wrench, qty:16, displayImage:store_image_coins_02.png"
    service.grant_packages = {10051: meta}
    with pytest.raises(ValueError):
        service.grant(99999, source="test")              # not an allowed currency package
    gid = service.grant(10051, source="test")
    body = service._fetch_gifts(1, b"")
    count, got_id, kind = struct.unpack_from("<III", body)
    assert (count, got_id, kind) == (1, gid, svc.OFFERWALL_GIFT_KIND) and kind == 2
    o = 12
    strings = []
    for _ in range(3):
        (n,) = struct.unpack_from("<I", body, o)
        strings.append(body[o + 4:o + 4 + n].decode())
        o += 4 + n
    assert strings == [meta, "", ""] and o == len(body)
    # acknowledged gifts (10481: u32 count, per gift u32 id, lp string, u32 flag) are not offered again
    ack = struct.pack("<II", 1, gid) + cc.lp_string(meta) + struct.pack("<I", 1)
    service._claim_gifts(1, ack)
    assert struct.unpack_from("<I", service._fetch_gifts(1, b""))[0] == 0


def test_claim_parses_the_clients_two_gift_receipt(service):
    """Byte-exact 10481 payload the client sent for gifts 4 and 5 (run 32)."""
    m1 = "type:money, qty:50000, displayImage:store_image_r_dollars_01.png"
    m2 = "type:mdollars, qty:45000, displayImage:store_image_m_dollar_02.png"
    payload = (struct.pack("<II", 2, 4) + cc.lp_string(m1) + struct.pack("<II", 1, 5) + cc.lp_string(m2)
               + struct.pack("<I", 1))
    assert len(payload) == 158
    for i in range(5):
        service.store.queue_gift(10051, "type:wrench, qty:16", "test")
    service._claim_gifts(1, payload)
    assert sorted(g["id"] for g in service.store.pending_gifts()) == [1, 2, 3]


def test_rs_and_ms_go_as_community_gifts_offered_once(service):
    """SP-17: Gold = kind 2 (claimable); R$/M$ = kind 0 (credited at once, popup title/message in strings 2/3).
    Kind 0 has no client-side duplicate check and the client asks twice per session, so it is offered once."""
    service.grant_packages = {10051: "type:wrench, qty:16", 10045: "type:money, qty:50000",
                              10461: "type:mdollars, qty:45000"}
    g_gold = service.grant(10051, source="test")
    g_rs = service.grant(10045, source="test")

    def offered(body):
        (n,), o, out = struct.unpack_from("<I", body), 4, []
        for _ in range(n):
            gid, kind = struct.unpack_from("<II", body, o); o += 8
            s = []
            for _ in range(3):
                (k,) = struct.unpack_from("<I", body, o); s.append(body[o + 4:o + 4 + k].decode()); o += 4 + k
            out.append((gid, kind, s))
        assert o == len(body)
        return out

    first = offered(service._fetch_gifts(1, b""))
    assert first == [(g_gold, 2, ["type:wrench, qty:16", "", ""]),
                     (g_rs, 0, ["type:money, qty:50000", "RETR0", "Preservation grant: 50,000 R$"])]
    second = offered(service._fetch_gifts(1, b""))          # same session, before the client acknowledges
    assert [x[0] for x in second] == [g_gold]               # kind 0 is not offered twice
