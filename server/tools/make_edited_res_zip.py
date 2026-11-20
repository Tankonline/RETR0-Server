"""Project RETR0 - TEST EMULATOR ONLY: build an edited copy of the game's res.zip that carries edited asset lists.

Why: at every launch Platform.extractRes re-extracts files/apk/res.zip into files/apk/res/, so edited list files are
overwritten. It recopies res.zip from the APK only when the file's length differs from the APK's raw resource
(RUNTIME_TEST_PLAN §9, run 8), so an edited res.zip of IDENTICAL length is kept and extracted instead.

Build: every entry of the original res.zip (res/xR.zip inside the APK) is copied unchanged, except
res/asset_list_*.txt, which are replaced by the edited lists (asset_pack_build.py --drop-unavailable). The archive
is then padded to the original length with a stored entry res/retr0_padding.bin plus the zip comment.
Nothing is written into the APK or the original evidence.

Usage: python -I 08_TESTING/runtime/make_edited_res_zip.py --apk <apk> --lists 03_ASSET_EXTRACTION/CDN_edited/lists
                                                           --out 03_ASSET_EXTRACTION/CDN_edited/res.zip
"""
from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

RES_ZIP_IN_APK = "res/xR.zip"
PAD_NAME = "res/retr0_padding.bin"


def build(orig: bytes, lists: Path, pad: int) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(orig))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as dst:
        for info in src.infolist():
            data = src.read(info)
            name = info.filename
            if name.startswith("res/asset_list_") and name.endswith(".txt"):
                edited = lists / name[len("res/"):]
                if edited.is_file():
                    data = edited.read_bytes()
            new = zipfile.ZipInfo(name, date_time=info.date_time)
            new.external_attr = info.external_attr
            new.compress_type = zipfile.ZIP_DEFLATED if info.compress_type else zipfile.ZIP_STORED
            dst.writestr(new, data, compress_type=new.compress_type, compresslevel=9)
        if pad >= 0:
            p = zipfile.ZipInfo(PAD_NAME, date_time=(2026, 1, 1, 0, 0, 0))
            dst.writestr(p, b"\0" * pad, compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True)
    ap.add_argument("--lists", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with zipfile.ZipFile(a.apk) as apk:
        orig = apk.read(RES_ZIP_IN_APK)
    target = len(orig)
    lists = Path(a.lists)
    base = build(orig, lists, 0)                       # with an empty padding entry
    gap = target - len(base)
    if gap < 0:
        raise SystemExit(f"edited res.zip is {-gap} bytes LARGER than the original; cannot match its length")
    out = build(orig, lists, gap)                      # stored padding grows the file byte for byte
    if len(out) != target:
        raise SystemExit(f"length mismatch after padding: {len(out)} != {target}")
    z = zipfile.ZipFile(io.BytesIO(out))
    bad = z.testzip()
    if bad:
        raise SystemExit(f"zip test failed at {bad}")
    n_lists = sum(1 for n in z.namelist() if n.startswith("res/asset_list_"))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_bytes(out)
    print(f"original {target} bytes; edited {len(out)} bytes (padding {gap}); {len(z.namelist())} entries, "
          f"{n_lists} asset lists -> {a.out}")


if __name__ == "__main__":
    main()
