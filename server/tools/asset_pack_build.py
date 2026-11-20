"""Project RETR0 - build an asset-CDN pack for one asset list from the owner's own game data. READ-ONLY on inputs.

Format (07_DOCUMENTATION/ASSET_DOWNLOAD_PROTOCOL.md):
    pack name   <md5 of the list file>.bin, served at  rr3/live/<list name>/<that name>     (AD-02)
    pack body   for every list line, in list order:  u32 key, u32 length, <stored bytes>     (AD-03, AD-05)
    key         djb2(path) % 0x106d643d (signed bytes, 32-bit)                               (AD-06)
    stored      the file itself when stored size == uncompressed size; otherwise
                b"FMASZ1" + zlib.compress(file) with CLASSIC zlib default settings           (AD-08)
Every stored blob is checked against the list MD5 (the client does the same check, AD-07). An entry whose file is
missing, or whose rebuilt bytes do not match, keeps its slot (offsets must not move) filled with zeros after a
correct header; the client will reject that one file and retry, and it is listed in the report.

Classic zlib is required for byte-identical output (Python 3.14 bundles zlib-ng, which compresses differently):
the script loads zlib1.dll from MSYS2 (--zlib-dll) through ctypes.

Usage:
  python -I SCRIPTS/asset_pack_build.py --apk 00_ORIGINAL/APK/real-racing-3-14-0-1.apk --list asset_list_base
         --data 00_ORIGINAL/GAME_DATA/com.ea.games.r3_row/files/.depot --out 03_ASSET_EXTRACTION/CDN
Output (gitignored, proprietary content): <out>/rr3/live/<list>/<md5>.bin and <out>/<list>.report.tsv
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import os
import struct
import zipfile
from pathlib import Path

RES_ZIP_IN_APK = "res/xR.zip"          # the APK's (obfuscated) name for the game's res.zip


def djb2_key(path: str) -> int:
    h = 0x1505
    if not path:
        return h
    for b in path.encode("utf-8"):
        h = (h * 0x21 + (b - 256 if b > 127 else b)) & 0xFFFFFFFF
    return h % 0x106D643D


class ClassicZlib:
    def __init__(self, dll: str):
        os.add_dll_directory(str(Path(dll).parent))
        self.z = ctypes.CDLL(dll)
        self.z.compressBound.restype = ctypes.c_ulong
        self.z.zlibVersion.restype = ctypes.c_char_p
        self.version = self.z.zlibVersion().decode()

    def compress(self, data: bytes) -> bytes:
        cap = self.z.compressBound(ctypes.c_ulong(len(data)))
        out = ctypes.create_string_buffer(cap)
        n = ctypes.c_ulong(cap)
        rc = self.z.compress2(out, ctypes.byref(n), data, ctypes.c_ulong(len(data)), -1)   # -1 = Z_DEFAULT (6)
        if rc != 0:
            raise RuntimeError(f"compress2 failed: {rc}")
        return out.raw[:n.value]


def read_list(apk: str, name: str) -> bytes:
    with zipfile.ZipFile(apk) as a:
        inner = a.read(RES_ZIP_IN_APK)
    with zipfile.ZipFile(io.BytesIO(inner)) as r:
        return r.read(f"res/{name}.txt")


def all_lists(apk: str) -> list[str]:
    with zipfile.ZipFile(apk) as a:
        inner = a.read(RES_ZIP_IN_APK)
    with zipfile.ZipFile(io.BytesIO(inner)) as r:
        return sorted(n[len("res/"):-len(".txt")] for n in r.namelist()
                      if n.startswith("res/asset_list_") and n.endswith(".txt"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True)
    ap.add_argument("--list", default="asset_list_base", help="list name, or 'all' for every asset_list_*.txt")
    ap.add_argument("--data", required=True, action="append",
                    help="a .depot folder (unpacked files); repeat to add fallback copies, tried in order")
    ap.add_argument("--out", required=True)
    ap.add_argument("--zlib-dll", default=r"C:\msys64\ucrt64\bin\zlib1.dll")
    ap.add_argument("--skip-existing", action="store_true", help="with --list all: skip lists whose pack exists")
    ap.add_argument("--drop-unavailable", action="store_true",
                    help="TEST DEVICES ONLY: leave out entries that cannot be supplied byte-exact and write edited "
                         "lists to --lists-out (the device must then use those lists)")
    ap.add_argument("--lists-out", help="folder for edited lists (with --drop-unavailable)")
    ap.add_argument("--modified-data",
                    help="TEST DEVICES ONLY: folder with owner-modified files at their .depot-relative paths; each one "
                         "that differs replaces the original and the edited list carries its MD5 and sizes "
                         "(implies --drop-unavailable)")
    a = ap.parse_args()
    if a.modified_data:
        if not Path(a.modified_data).is_dir():
            raise SystemExit(f"--modified-data folder not found: {a.modified_data}")
        a.drop_unavailable = True
    if a.drop_unavailable and not a.lists_out:
        raise SystemExit("--drop-unavailable needs --lists-out")
    if a.drop_unavailable and a.skip_existing:
        raise SystemExit("--skip-existing cannot be combined with --drop-unavailable (pack names change)")

    z = ClassicZlib(a.zlib_dll)
    if a.list == "all":
        names = all_lists(a.apk)
        print(f"{len(names)} lists in {RES_ZIP_IN_APK}", flush=True)
        summary = []
        for i, name in enumerate(names, 1):
            raw = read_list(a.apk, name)
            if a.skip_existing and (Path(a.out) / "rr3" / "live" / name / f"{hashlib.md5(raw).hexdigest()}.bin").exists():
                continue
            counts = build(a, z, name, raw)
            summary.append(f"{name}\t" + "\t".join(f"{k}={v}" for k, v in counts.items()))
            print(f"[{i}/{len(names)}] {name} {counts}", flush=True)
        Path(a.out, "ALL_LISTS.summary.tsv").write_text("\n".join(summary) + "\n", encoding="utf-8")
        return
    raw = read_list(a.apk, a.list)
    build(a, z, a.list, raw)


def build(a, z: "ClassicZlib", list_name: str, raw: bytes) -> dict:
    """Build one pack. With --drop-unavailable, entries that cannot be supplied byte-exact are left OUT of both
    the pack and an edited copy of the list (written to --lists-out); the pack is then named by the MD5 of the
    edited list, which is the list the test device must use. Without it, missing entries keep a zero-filled slot."""
    a = argparse.Namespace(**{**vars(a), "list": list_name})
    drop = getattr(a, "drop_unavailable", False)
    lines = [l for l in raw.decode("utf-8").split("\n") if l.strip()]
    sources = [Path(d) for d in a.data]          # tried in order; first byte-exact match wins
    modified = Path(a.modified_data) if getattr(a, "modified_data", None) else None
    live = Path(a.out) / "rr3" / "live" / a.list
    live.mkdir(parents=True, exist_ok=True)
    dest = live / ("building.tmp" if drop else f"{hashlib.md5(raw).hexdigest()}.bin")
    report, kept = [], []
    counts = {"ok_plain": 0, "ok_fmasz": 0, "modified": 0, "missing": 0, "md5_mismatch": 0}
    offset = 0
    with open(dest, "wb") as pack:
        for line in lines:
            path, md5, stored_s, size_s = line.rstrip("\r").split("\t")[:4]
            stored, size = int(stored_s), int(size_s)
            # Owner-modified file: it replaces the original, and the edited list gets ITS md5 and sizes, so the
            # client's MD5 check (AD-07) passes for the new content. Compressed entries stay FMASZ1 + zlib.
            if modified is not None and (modified / path.lstrip("/")).is_file():
                content = (modified / path.lstrip("/")).read_bytes()
                blob = content if stored == size else b"FMASZ1" + z.compress(content)
                new_md5 = hashlib.md5(blob).hexdigest()
                if new_md5 == md5:
                    # the owner's copy IS the listed original: use it (other sources may hold a changed version)
                    pack.write(struct.pack("<II", djb2_key(path), stored))
                    pack.write(blob)
                    kept.append(line.rstrip("\r"))
                    counts["ok_plain" if stored == size else "ok_fmasz"] += 1
                    offset += stored + 8
                    continue
                else:
                    pack.write(struct.pack("<II", djb2_key(path), len(blob)))
                    pack.write(blob)
                    kept.append(f"{path}\t{new_md5}\t{len(blob)}\t{len(content)}")
                    report.append(f"modified\t{path}\t{offset}\t{len(blob) + 8}")
                    counts["modified"] += 1
                    offset += len(blob) + 8
                    continue
            header = struct.pack("<II", djb2_key(path), stored)
            if not drop:
                pack.write(header)
            status, blob = "missing", None
            for src in sources:
                f = src / path.lstrip("/")
                if not f.is_file():
                    continue
                content = f.read_bytes()
                cand = content if stored == size else b"FMASZ1" + z.compress(content)
                if len(cand) == stored and hashlib.md5(cand).hexdigest() == md5:
                    status, blob = ("ok_plain" if stored == size else "ok_fmasz"), cand
                    break
                status = "md5_mismatch"
            counts[status] += 1
            if status not in ("ok_plain", "ok_fmasz"):
                report.append(f"{status}\t{path}\t{offset}\t{stored + 8}")
                if drop:
                    continue                      # entry removed from the edited list; offsets do not advance
            if drop:
                pack.write(header)
                kept.append(line.rstrip("\r"))
            pack.write(blob if blob is not None else b"\0" * stored)
            offset += stored + 8
    if drop:
        edited = ("\n".join(kept) + "\n").encode("utf-8") if kept else b""
        pack_md5 = hashlib.md5(edited).hexdigest()
        lists_out = Path(a.lists_out)
        lists_out.mkdir(parents=True, exist_ok=True)
        (lists_out / f"{a.list}.txt").write_bytes(edited)
        final = live / f"{pack_md5}.bin"
        if final.exists():
            final.unlink()
        dest.rename(final)
        dest = final
    else:
        pack_md5 = hashlib.md5(raw).hexdigest()
    (Path(a.out) / f"{a.list}.report.tsv").write_text("status\tpath\toffset\tslot_bytes\n" + "\n".join(report) + "\n",
                                                      encoding="utf-8")
    print(f"zlib {z.version}; list {a.list}: {len(lines)} entries ({len(kept) if drop else len(lines)} in pack), "
          f"md5 {pack_md5}; pack {offset} bytes -> {dest}", flush=True)
    return counts


if __name__ == "__main__":
    main()
