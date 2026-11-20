"""Project RETR0 - TEST EMULATOR ONLY: switch the installed game to edited asset lists, or restore the originals.

Why: the CDN packs can only contain files we can reproduce byte-exact (ASSET_DOWNLOAD_PROTOCOL.md AD-07). The
owner's data lacks some originals (e.g. ETC GUI textures that were replaced by .rgb.pvr.z files), so
asset_pack_build.py --drop-unavailable writes edited lists without those entries. The game reads its lists from
the unpacked files/apk/res/ folder (Platform.extractRes only re-extracts res.zip when the APK's checksum resource
differs from files/apk/checksum.md5), so replacing the list files there is enough; the APK is not modified.

apply:   1. copy the device's original lists + checksum.md5 to /data/local/tmp/retr0_res_backup/ (if not there yet)
         2. push the edited lists over files/apk/res/asset_list_*.txt
         3. push substitutes into files/.depot/: for every dropped *.etc.dds.z, the owner's *.rgb.pvr.z of the same
            image (what the owner's own install used); for every dropped entry whose file exists but differs,
            the owner's version
         4. give everything to the app's uid (group ext_data_rw) and restore SELinux labels
restore: copy the backed-up lists back (substitute files are left in place).

Usage:  python -I 08_TESTING/runtime/apply_edited_lists.py apply   --edited 03_ASSET_EXTRACTION/CDN_edited
                 --data <.depot> [--data <fallback .depot>]
        python -I 08_TESTING/runtime/apply_edited_lists.py restore
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PKG = "com.ea.games.r3_row"
ADB = str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe")
DEV = f"/data/media/0/Android/data/{PKG}/files"
BACKUP = "/data/local/tmp/retr0_res_backup"
ENV = {**os.environ, "MSYS_NO_PATHCONV": "1"}


def adb(*args: str, timeout: int = 600) -> str:
    r = subprocess.run([ADB, *args], capture_output=True, text=True, timeout=timeout, env=ENV)
    if r.returncode != 0:
        raise SystemExit(f"adb {' '.join(args[:3])} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def preflight() -> str:
    devs = [l.split()[0] for l in adb("devices").splitlines()[1:] if l.strip().endswith("device")]
    if len(devs) != 1 or not devs[0].startswith("emulator-"):
        raise SystemExit(f"need exactly one emulator, found {devs}")
    if adb("shell", "id -u") != "0":
        adb("root")
        adb("wait-for-device")
    out = adb("shell", f"dumpsys package {PKG} | grep -m1 appId=")
    appid = out.split("appId=")[1].split()[0]
    adb("shell", f"am force-stop {PKG}")
    return appid


def fix_owner(appid: str, path: str) -> None:
    adb("shell", f"chown -R {appid}:1078 {path} && restorecon -R {path} >/dev/null 2>&1; true")


def apply(edited: Path, sources: list[Path], stage: Path) -> None:
    appid = preflight()
    if adb("shell", f"ls {BACKUP}/asset_list_base.txt >/dev/null 2>&1 && echo yes || echo no") != "yes":
        adb("shell", f"mkdir -p {BACKUP} && cp -p {DEV}/apk/res/asset_list_*.txt {DEV}/apk/checksum.md5 {BACKUP}/")
    print("backup:", adb("shell", f"ls {BACKUP} | wc -l"), "files in", BACKUP, flush=True)

    # substitutes, staged under the (gitignored) edited folder
    if stage.exists():
        shutil.rmtree(stage)
    (stage / ".depot").mkdir(parents=True)
    n_rgb = n_alt = 0
    for rep in sorted(edited.glob("*.report.tsv")):
        for line in rep.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status, path = parts[0], parts[1].lstrip("/")
            cands = []
            if path.endswith(".etc.dds.z"):
                cands.append((path[: -len(".etc.dds.z")] + ".rgb.pvr.z", "rgb"))
            if status == "md5_mismatch":
                cands.append((path, "alt"))
            for rel, kind in cands:
                src = next((s / rel for s in sources if (s / rel).is_file()), None)
                dst = stage / ".depot" / rel
                if src is not None and not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
                    if kind == "rgb":
                        n_rgb += 1
                    else:
                        n_alt += 1
                    break
    print(f"substitutes staged: {n_rgb} RGB textures for dropped ETC entries, {n_alt} owner versions of changed files",
          flush=True)

    adb("shell", "rm -rf /data/local/tmp/retr0_lists && mkdir -p /data/local/tmp/retr0_lists")
    adb("push", str(edited / "lists") + "/.", "/data/local/tmp/retr0_lists/")
    adb("shell", f"cp /data/local/tmp/retr0_lists/asset_list_*.txt {DEV}/apk/res/ && rm -rf /data/local/tmp/retr0_lists")
    print("edited lists installed:", adb("shell", f"ls {DEV}/apk/res | grep -c '^asset_list_'"), flush=True)
    if n_rgb + n_alt:
        adb("push", str(stage / ".depot") + "/.", f"{DEV}/.depot/")
    fix_owner(appid, f"/data/media/0/Android/data/{PKG}")
    print("done; checksum.md5 untouched:", adb("shell", f"cat {DEV}/apk/checksum.md5"), flush=True)


def restore() -> None:
    appid = preflight()
    adb("shell", f"cp -p {BACKUP}/asset_list_*.txt {DEV}/apk/res/")
    fix_owner(appid, f"{DEV}/apk")
    print("original lists restored from", BACKUP)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["apply", "restore"])
    ap.add_argument("--edited", default="03_ASSET_EXTRACTION/CDN_edited")
    ap.add_argument("--data", action="append", default=[])
    a = ap.parse_args()
    if a.action == "restore":
        return restore()
    if not a.data:
        raise SystemExit("apply needs --data")
    edited = Path(a.edited)
    apply(edited, [Path(d) for d in a.data], edited / "substitutes")


if __name__ == "__main__":
    sys.exit(main())
