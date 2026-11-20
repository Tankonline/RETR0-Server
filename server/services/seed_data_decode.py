"""Project RETR0 - clean-room reader for CloudCell seed data (CC_SeedData.bin, "NomNomNom" archive).

Format, from the loader cc FileManager init (arm64 libRealRacing3.so 0x1c70a80, "CC: Filemanager initializing..."):
    char[9]  "NomNomNom"
    u32      dir_bytes                      directory length in bytes
    repeat until dir_bytes are consumed:
        u32  type                           0 = file, otherwise a directory
        u32  name_len
        char name[name_len]                 consumed += 8 + name_len
        if type == 0:  u32 size             consumed += 4
    file data, back to back, starting at 13 + dir_bytes, in directory order
A directory record creates that directory (FileManager vtable +0x68); following names are relative to it
([likely]: the record order is depth-first, so the current directory is the last directory record).
All integers are little-endian.

Usage:
    python -I SCRIPTS/seed_data_decode.py <CC_SeedData.bin>                 list entries
    python -I SCRIPTS/seed_data_decode.py <CC_SeedData.bin> --extract <dir>  extract to a new directory
    python -I SCRIPTS/seed_data_decode.py <CC_SeedData.bin> --game-config [--values]
                                     game-config ids and value lengths (values only with --values)
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

MAGIC = b"NomNomNom"


def parse(data: bytes) -> list[dict]:
    if not data.startswith(MAGIC):
        raise ValueError("not a NomNomNom seed archive")
    off = len(MAGIC)
    (dir_bytes,) = struct.unpack_from("<I", data, off)
    off += 4
    data_off = off + dir_bytes
    if data_off > len(data):
        raise ValueError("directory runs past end of file")
    consumed, entries, pos = 0, [], data_off
    while consumed < dir_bytes:
        etype, nlen = struct.unpack_from("<II", data, off)
        name = data[off + 8: off + 8 + nlen].decode("utf-8")
        off += 8 + nlen
        consumed += 8 + nlen
        if etype == 0:
            (size,) = struct.unpack_from("<I", data, off)
            off += 4
            consumed += 4
            entries.append({"type": "file", "name": name, "offset": pos, "size": size})
            pos += size
        else:
            entries.append({"type": "dir", "name": name, "raw_type": etype})
    if consumed != dir_bytes:
        raise ValueError(f"directory length mismatch: consumed {consumed}, header {dir_bytes}")
    if pos != len(data):
        raise ValueError(f"file data ends at {pos}, file is {len(data)} bytes")
    return entries


def seed_blob(data: bytes, entries: list[dict], name: str) -> bytes:
    """Contents of a numeric seed file, unboxed twice (XOR outside, zlib inside) with the clean-room codec."""
    here = Path(__file__).resolve()
    for p in (here.parent / "cloudcell_codec",                                   # standalone server package
              here.parents[1] / "06_RECONSTRUCTION" / "BACKEND" / "cloudcell_codec"):   # project layout
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import cloudcell_codec as cc
    e = next(x for x in entries if x["type"] == "file" and x["name"] == name)
    return cc.unbox(cc.unbox(data[e["offset"]: e["offset"] + e["size"]]))


def parse_game_config(blob: bytes) -> dict:
    """Seed file "1" (GameConfigManager defaults), unboxed.

    Layout: u32 h0, u32 h1, u32 h2, u32 game_id, u32 h4, then the value list read by GameConfigManager
    (0x1cee574 / sync reply handler 0x1cee984):  u32 n, n x (u32 config_id, u32 len, bytes), then u32 trailer.
    h0, h1, h2, h4 and the trailer are UNKNOWN (observed: 0x870d, 17, 0, 1 and 0).
    """
    h = struct.unpack_from("<5I", blob, 0)
    off = 20
    (n,) = struct.unpack_from("<I", blob, off)
    off += 4
    values = {}
    for _ in range(n):
        cid, ln = struct.unpack_from("<II", blob, off)
        off += 8
        if off + ln > len(blob):
            raise ValueError("value runs past end of blob")
        values[cid] = blob[off: off + ln].decode("utf-8", "replace")
        off += ln
    if len(blob) - off != 4:
        raise ValueError(f"unexpected tail: {len(blob) - off} bytes after the value list")
    (trailer,) = struct.unpack_from("<I", blob, off)
    return {"header": h, "game_id": h[3], "values": values, "trailer": trailer}


STORE_MAGIC = 654321

# Field names come from content and from the labels of the debug panels 0xa7f5c8 ("Name, IsValid, Telemetry
# Price, Store Price, Consumable, String 0, Product Id ROW/NA") and 0xb89804 (iTunes/Google/Amazon NA/ROW SKUs).
# The binary reader itself was not located, so names other than id/name/price are MEDIUM (see NW-91).
STORE_ID_FIELDS = ["store_id_a", "store_id_b", "amazon_na", "amazon_row", "store_id_e", "store_id_f", "store_id_g"]


def parse_store_catalogue(blob: bytes) -> dict:
    """Seed file "12" (store product catalogue), unboxed. Must consume the blob exactly.

    u32 magic (654321), u32 version (10), u32 count, then count x:
      u32 product_id, lp name, lp title, lp price_string, f32 price, u32 x5 (third: 0/1, [likely] consumable),
      lp metadata ("type:pack id:N"), lp unk_string_1, lp sku_na, lp sku_row, lp unk_string_2, 7 x lp store ids
    """
    off = 0

    def u32():
        nonlocal off
        (v,) = struct.unpack_from("<I", blob, off)
        off += 4
        return v

    def lp():
        nonlocal off
        n = u32()
        if n > len(blob) - off:
            raise ValueError("string runs past end of blob")
        v = blob[off: off + n].decode("utf-8", "replace")
        off += n
        return v

    magic, version, count = u32(), u32(), u32()
    if magic != STORE_MAGIC:
        raise ValueError(f"unexpected catalogue magic {magic}")
    products = []
    for _ in range(count):
        p = {"product_id": u32(), "name": lp(), "title": lp(), "price_string": lp()}
        (p["price"],) = struct.unpack_from("<f", blob, off)
        off += 4
        p["flags"] = [u32() for _ in range(5)]
        p["metadata"] = lp()
        p["unk_string_1"] = lp()
        p["sku_na"], p["sku_row"] = lp(), lp()
        p["unk_string_2"] = lp()
        for f in STORE_ID_FIELDS:
            p[f] = lp()
        products.append(p)
    if off != len(blob):
        raise ValueError(f"{len(blob) - off} unread bytes after {count} products")
    return {"magic": magic, "version": version, "products": products}


def build_store_catalogue(products: list[dict], version: int = 10) -> bytes:
    """Inverse of parse_store_catalogue (for tests and a replacement service)."""
    def lp(s):
        b = s.encode()
        return struct.pack("<I", len(b)) + b
    out = struct.pack("<3I", STORE_MAGIC, version, len(products))
    for p in products:
        out += struct.pack("<I", p["product_id"]) + lp(p["name"]) + lp(p.get("title", "")) + lp(p["price_string"])
        out += struct.pack("<f", p["price"]) + struct.pack("<5I", *p.get("flags", [0, 0, 0, 0, 0]))
        out += lp(p.get("metadata", "")) + lp(p.get("unk_string_1", "")) + lp(p.get("sku_na", "")) + lp(p.get("sku_row", ""))
        out += lp(p.get("unk_string_2", "")) + b"".join(lp(p.get(f, "")) for f in STORE_ID_FIELDS)
    return out


def extract(data: bytes, entries: list[dict], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    base = out.resolve()
    for e in entries:
        if e["type"] != "file":
            continue
        target = (out / e["name"]).resolve()
        if base not in target.parents:
            raise ValueError(f"unsafe entry name {e['name']!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data[e["offset"]: e["offset"] + e["size"]])


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    data = Path(argv[0]).read_bytes()
    entries = parse(data)
    if len(argv) >= 2 and argv[1] == "--store":
        cat = parse_store_catalogue(seed_blob(data, entries, "12"))
        prods = cat["products"]
        kinds = {}
        for p in prods:
            k = p["metadata"].split(" ")[0] if p["metadata"] else "(none)"
            kinds[k] = kinds.get(k, 0) + 1
        print(f"store catalogue v{cat['version']}: {len(prods)} products; metadata types {kinds}")
        if "--list" in argv:
            for p in prods:
                print(f"  {p['product_id']:6d}  {p['price_string']:>8}  {p['name']}  [{p['metadata']}]")
        return 0
    if len(argv) >= 2 and argv[1] == "--game-config":
        gc = parse_game_config(seed_blob(data, entries, "1"))
        show = "--values" in argv
        print(f"game id {gc['game_id']}, {len(gc['values'])} config values (header {gc['header']}, trailer {gc['trailer']})")
        for cid, v in sorted(gc["values"].items()):
            print(f"  {cid:5d}  len {len(v):4d}" + (f"  {v}" if show else ""))
        return 0
    for e in entries:
        if e["type"] == "file":
            print(f"file  {e['size']:8d}  @0x{e['offset']:06x}  {e['name']}")
        else:
            print(f"dir   type={e['raw_type']}  {e['name']}")
    files = [e for e in entries if e["type"] == "file"]
    print(f"{len(files)} files, {len(entries) - len(files)} directories, "
          f"{sum(e['size'] for e in files)} data bytes; layout consistent with file size")
    if len(argv) >= 3 and argv[1] == "--extract":
        extract(data, entries, Path(argv[2]))
        print("extracted to", argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
