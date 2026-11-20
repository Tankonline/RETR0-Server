"""Tests for SCRIPTS/seed_data_decode.py on synthetic archives (no game data in the repo)."""
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "services"))
import seed_data_decode as sd  # noqa: E402


def build(entries):
    """entries: list of (type, name, payload_or_None)."""
    directory = b""
    data = b""
    for etype, name, payload in entries:
        n = name.encode()
        directory += struct.pack("<II", etype, len(n)) + n
        if etype == 0:
            directory += struct.pack("<I", len(payload))
            data += payload
    return sd.MAGIC + struct.pack("<I", len(directory)) + directory + data


def test_parse_files_and_offsets():
    blob = build([(0, "1", b"abc"), (0, "x.png", b"\x89PNG"), (0, "12", b"")])
    entries = sd.parse(blob)
    assert [(e["name"], e["size"]) for e in entries] == [("1", 3), ("x.png", 4), ("12", 0)]
    first = entries[0]
    assert blob[first["offset"]:first["offset"] + 3] == b"abc"
    assert entries[1]["offset"] == first["offset"] + 3


def test_directory_records_have_no_size():
    entries = sd.parse(build([(1, "sub", None), (0, "sub/a.txt", b"hi")]))
    assert entries[0] == {"type": "dir", "name": "sub", "raw_type": 1}
    assert entries[1]["size"] == 2


@pytest.mark.parametrize("bad", [
    b"NotNomNom" + b"\x00" * 8,                                  # wrong magic
    build([(0, "a", b"xyz")])[:-1],                              # data truncated
    build([(0, "a", b"xyz")]) + b"!",                            # trailing bytes
])
def test_rejects_inconsistent_files(bad):
    with pytest.raises(ValueError):
        sd.parse(bad)


def test_extract_refuses_path_escape(tmp_path):
    blob = build([(0, "../evil.txt", b"x")])
    with pytest.raises(ValueError):
        sd.extract(blob, sd.parse(blob), tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_extract_writes_files(tmp_path):
    blob = build([(0, "a.txt", b"one"), (0, "b.bin", b"\x00\x01")])
    sd.extract(blob, sd.parse(blob), tmp_path / "out")
    assert (tmp_path / "out" / "a.txt").read_bytes() == b"one"
    assert (tmp_path / "out" / "b.bin").read_bytes() == b"\x00\x01"


def _game_config_blob(values, game_id=15710):
    body = struct.pack("<5I", 0x1234, 17, 0, game_id, 1) + struct.pack("<I", len(values))
    for cid, v in values.items():
        b = v.encode()
        body += struct.pack("<II", cid, len(b)) + b
    return body + struct.pack("<I", 0)


def test_parse_game_config_synthetic():
    gc = sd.parse_game_config(_game_config_blob({1: "https://example.invalid/a", 87: "abc"}))
    assert gc["game_id"] == 15710 and gc["trailer"] == 0
    assert gc["values"] == {1: "https://example.invalid/a", 87: "abc"}
    with pytest.raises(ValueError):
        sd.parse_game_config(_game_config_blob({1: "x"}) + b"\x00")


def test_seed_archive_to_service_game_config(tmp_path):
    """Synthetic seed archive -> decoder -> local service reply for sub-sync 10631/5245."""
    sys.path.insert(0, str(ROOT / "server" / "services" / "cloudcell_codec"))
    sys.path.insert(0, str(ROOT / "server" / "services" / "local_service"))
    import cloudcell_codec as cc
    import retr0_local_service as svc
    blob = cc.box(cc.box(_game_config_blob({2: "12345", 5: "hello"}), cc.ZLIB), cc.XOR)
    seed = tmp_path / "CC_SeedData.bin"
    seed.write_bytes(build([(0, "1", blob), (0, "x.png", b"png")]))
    defaults = svc.load_seed_game_config(str(seed))
    assert defaults == {2: "12345", 5: "hello"}
    service = svc.Service(svc.Store(tmp_path / "data"), "http://127.0.0.1:8780", defaults)
    service.store.state["game_config"] = {"5": "override"}
    reply = service.handlers[cc.SUBSYNC_GAME_CONFIG](1000001, b"")
    assert cc.parse_game_config_response(reply) == {2: "12345", 5: "override"}


def test_store_catalogue_roundtrip_synthetic():
    products = [
        {"product_id": 83, "name": "Test Pack", "title": "", "price_string": "$1.00", "price": 1.0,
         "flags": [0, 0, 1, 0, 0], "metadata": "type:pack id:3", "sku_na": "SKU_NA", "sku_row": "SKU_ROW",
         "amazon_na": "pkg.na.1", "amazon_row": "pkg.row.1"},
        {"product_id": 10097, "name": "Empty", "title": "Title", "price_string": "???", "price": 0.0,
         "metadata": "type:adhoc"},
    ]
    blob = sd.build_store_catalogue(products)
    cat = sd.parse_store_catalogue(blob)
    assert cat["version"] == 10 and len(cat["products"]) == 2
    p0, p1 = cat["products"]
    assert (p0["product_id"], p0["name"], p0["price_string"], p0["flags"], p0["sku_row"], p0["amazon_na"]) == \
        (83, "Test Pack", "$1.00", [0, 0, 1, 0, 0], "SKU_ROW", "pkg.na.1")
    assert (p1["title"], p1["metadata"], p1["store_id_g"]) == ("Title", "type:adhoc", "")
    assert sd.build_store_catalogue(cat["products"]) == blob
    with pytest.raises(ValueError):
        sd.parse_store_catalogue(blob + b"\x00")
    with pytest.raises(ValueError):
        sd.parse_store_catalogue(b"\x00" * 12)
