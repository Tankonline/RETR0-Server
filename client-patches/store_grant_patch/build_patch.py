"""Build the RETR0 store-grant test APK (arm64 libRealRacing3.so patch) from the original 14.0.1 APK.

Never touches 00_ORIGINAL: reads it, writes a patched copy to 08_TESTING/runtime/out/apk/.
Steps: assemble store_grant_patch.S with the NDK clang, link it at the unused padding before .text
(va 0x9876c8, 0x938 bytes of zeros), check the bytes being replaced are what we expect, write the
handler + a branch at PurchaseStoreProduct's entry, then fix the zip entry CRC (local + central header).
The stored library keeps its size and offset, so the APK layout is otherwise unchanged.
If 08_TESTING/runtime/out/apk/classes2_redirect.dex exists, it also writes the RETR0 client APK
(that dex swapped in, zip-aligned) and a debug-signed copy (see build_client()).
"""
import hashlib, os, shutil, struct, subprocess, sys, tempfile, zlib, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_APK = ROOT / "00_ORIGINAL/APK/real-racing-3-14-0-1.apk"
OUT_DIR = ROOT / "08_TESTING/runtime/out/apk"
OUT_APK = OUT_DIR / "rr3_14.0.1_store_grant_test.apk"      # store grants only (kept for comparison)
# RETR0 client = store grants + the built-in local-server redirect (classes2.dex from
# ../local_server_redirect/build_redirect_dex.py), zip-aligned; plus a debug-signed copy for new installs.
REDIRECT_DEX = OUT_DIR / "classes2_redirect.dex"
CLIENT_APK = OUT_DIR / "rr3_14.0.1_retr0_client.apk"
CLIENT_SIGNED = OUT_DIR / "rr3_14.0.1_retr0_client_signed.apk"
BUILD_TOOLS = Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk/build-tools/36.0.0"
DEBUG_KEYSTORE = Path.home() / ".android/debug.keystore"
LIB = "lib/arm64-v8a/libRealRacing3.so"
NDK = Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin"
EXPECT_SHA = "dcfe3788004444bd69e2fb839c18a973b488e94f46f1b818b6c005afdcad1d5f"

CAVE, CAVE_LEN = 0x9876C8, 0x938          # zero padding between .eh_frame and .text (RX segment)
HOOK = 0xB8D6E4                           # NimbleMTX::PurchaseStoreProduct entry: sub sp, sp, #0x90
PACK_HOOK = 0x13EF7E8                     # PackManager pack purchase entry: str d8, [sp, #-0x70]!
SYMS = {
    "orig_continue": 0xB8D6E8, "pack_continue": 0x13EF7EC,"store_lookup": 0xB84354, "reward_parse": 0xCEE2E0,
    "mtx_can_award": 0xB873C0, "mtx_award": 0xB879FC, "reward_dtor": 0xA36FEC,
    "save_request": 0x13A14B8, "game_log": 0x109FA18,
    "got_store_mgr": 0x1F6DDF0, "got_save_mgr": 0x1F6D818,
    # RETR0 username (SV-27): player-name function, racing-code submit, libc PLT stubs, spare state bytes
    "name_continue": 0x135E948, "promo_continue": 0x1516B20, "str_assign": 0x15DA06C,
    "fopen": 0x1E17CE0, "fclose": 0x1E17CF0, "fgets": 0x1E18AD0, "fputs": 0x1E18AE0, "malloc": 0x1E18BA0,
    "name_slot": 0x1F9C1A0,
}
NAME_HOOK = 0x135E944                     # player-name function entry: sub sp, sp, #0x1c0
PROMO_HOOK = 0x1516B1C                    # racing-code submit entry: sub sp, sp, #0x170


def build_handler(tmp: Path) -> bytes:
    src = Path(__file__).with_name("store_grant_patch.S")
    obj, elf = tmp / "p.o", tmp / "p.elf"
    subprocess.run([str(NDK / "clang.exe"), "--target=aarch64-linux-android", "-c", str(src), "-o", str(obj)], check=True)
    ld = [str(NDK / "ld.lld.exe"), "-static", "-e", "grant_entry", f"-Ttext=0x{CAVE:x}", "-o", str(elf), str(obj)]
    ld += [f"--defsym={k}=0x{v:x}" for k, v in SYMS.items()]
    subprocess.run(ld, check=True)
    subprocess.run([str(NDK / "llvm-objcopy.exe"), "-O", "binary", "--only-section=.text", str(elf), str(tmp / "p.bin")], check=True)
    nm = subprocess.run([str(NDK / "llvm-nm.exe"), str(elf)], check=True, capture_output=True, text=True).stdout
    syms = {p[2]: int(p[0], 16) for p in (l.split() for l in nm.splitlines()) if len(p) == 3}
    return (tmp / "p.bin").read_bytes(), syms


def branch(src: int, dst: int) -> bytes:
    off = (dst - src) // 4
    assert -(1 << 25) <= off < (1 << 25)
    return struct.pack("<I", 0x14000000 | (off & 0x3FFFFFF))


def main() -> int:
    data = bytearray(SRC_APK.read_bytes())
    assert hashlib.sha256(data).hexdigest() == EXPECT_SHA, "original APK hash mismatch"
    z = zipfile.ZipFile(SRC_APK)
    info = z.getinfo(LIB)
    assert info.compress_type == zipfile.ZIP_STORED
    lh = info.header_offset
    name_len, extra_len = struct.unpack_from("<HH", data, lh + 26)
    lib_off = lh + 30 + name_len + extra_len
    lib = data[lib_off:lib_off + info.file_size]
    assert zlib.crc32(lib) & 0xFFFFFFFF == info.CRC

    with tempfile.TemporaryDirectory() as t:
        code, syms = build_handler(Path(t))
    assert len(code) <= CAVE_LEN, len(code)
    assert syms["grant_entry"] == CAVE
    assert lib[CAVE:CAVE + CAVE_LEN] == bytes(CAVE_LEN), "cave not empty"
    assert lib[HOOK:HOOK + 4] == bytes.fromhex("ff4302d1"), "unexpected instruction at hook"  # sub sp, sp, #0x90
    assert lib[PACK_HOOK:PACK_HOOK + 4] == bytes.fromhex("e80f19fc"), "unexpected instruction at pack hook"
    lib[CAVE:CAVE + len(code)] = code
    lib[HOOK:HOOK + 4] = branch(HOOK, CAVE)
    lib[PACK_HOOK:PACK_HOOK + 4] = branch(PACK_HOOK, syms["pack_entry"])
    assert lib[NAME_HOOK:NAME_HOOK + 4] == bytes.fromhex("ff0307d1"), "unexpected instruction at name hook"
    assert lib[PROMO_HOOK:PROMO_HOOK + 4] == bytes.fromhex("ffc305d1"), "unexpected instruction at promo hook"
    lib[NAME_HOOK:NAME_HOOK + 4] = branch(NAME_HOOK, syms["name_entry"])
    lib[PROMO_HOOK:PROMO_HOOK + 4] = branch(PROMO_HOOK, syms["promo_entry"])
    print(f"pack hook 0x{PACK_HOOK:x} -> pack_entry 0x{syms['pack_entry']:x}")

    data[lib_off:lib_off + len(lib)] = lib
    crc = zlib.crc32(lib) & 0xFFFFFFFF
    struct.pack_into("<I", data, lh + 14, crc)                       # local header CRC
    eocd = data.rfind(b"PK\x05\x06")
    cd_off = struct.unpack_from("<I", data, eocd + 16)[0]
    p, fixed = cd_off, False
    while data[p:p + 4] == b"PK\x01\x02":
        n, e, c = struct.unpack_from("<HHH", data, p + 28)
        if data[p + 46:p + 46 + n].decode() == LIB:
            struct.pack_into("<I", data, p + 16, crc); fixed = True
        p += 46 + n + e + c
    assert fixed
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_APK.write_bytes(data)
    zipfile.ZipFile(OUT_APK).testzip()
    print(f"handler {len(code)} bytes at 0x{CAVE:x}; hook 0x{HOOK:x} -> {branch(HOOK, CAVE).hex()}")
    print(f"lib sha256 {hashlib.sha256(lib).hexdigest()}")
    print(f"apk {OUT_APK} sha256 {hashlib.sha256(data).hexdigest()}")
    if REDIRECT_DEX.exists():
        build_client()
    else:
        print(f"no {REDIRECT_DEX.name}: run ../local_server_redirect/build_redirect_dex.py first for the RETR0 client APK")
    return 0


def build_client() -> None:
    """Copy the store-grant APK with classes2.dex replaced, then zipalign (4 KiB pages for the stored .so) and sign."""
    dex = REDIRECT_DEX.read_bytes()
    tmp = OUT_DIR / "retr0_client_unaligned.apk"
    with zipfile.ZipFile(OUT_APK) as zin, zipfile.ZipFile(tmp, "w") as zout:
        names = [i.filename for i in zin.infolist()]
        assert "classes2.dex" in names
        for info in zin.infolist():
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type, zi.external_attr = info.compress_type, info.external_attr
            zout.writestr(zi, dex if info.filename == "classes2.dex" else zin.read(info))
    subprocess.run([str(BUILD_TOOLS / "zipalign.exe"), "-P", "16", "-f", "4", str(tmp), str(CLIENT_APK)], check=True)
    tmp.unlink()
    subprocess.run([str(BUILD_TOOLS / "zipalign.exe"), "-c", "-P", "16", "4", str(CLIENT_APK)], check=True)
    subprocess.run(["cmd", "/c", str(BUILD_TOOLS / "apksigner.bat"), "sign", "--ks", str(DEBUG_KEYSTORE),
                    "--ks-key-alias", "androiddebugkey", "--ks-pass", "pass:android", "--key-pass", "pass:android",
                    "--out", str(CLIENT_SIGNED), str(CLIENT_APK)], check=True)
    subprocess.run(["cmd", "/c", str(BUILD_TOOLS / "apksigner.bat"), "verify", str(CLIENT_SIGNED)], check=True)
    for p in (CLIENT_APK, CLIENT_SIGNED):
        print(f"client {p} sha256 {hashlib.sha256(p.read_bytes()).hexdigest()}")


def configure(argv: list[str]) -> None:
    """Optional overrides for use outside the project layout (defaults: the project's paths)."""
    import argparse
    global SRC_APK, OUT_DIR, OUT_APK, REDIRECT_DEX, CLIENT_APK, CLIENT_SIGNED, NDK, BUILD_TOOLS, DEBUG_KEYSTORE
    ap = argparse.ArgumentParser(description="Build the RETR0 client APK from an original RR3 14.0.1 APK.")
    ap.add_argument("--apk", type=Path, help="your original real-racing-3-14-0-1.apk (SHA-256 checked)")
    ap.add_argument("--out", type=Path, help="output folder (classes2_redirect.dex is looked for here too)")
    ap.add_argument("--ndk-bin", type=Path, help="NDK llvm bin folder (clang, ld.lld, llvm-objcopy, llvm-nm)")
    ap.add_argument("--build-tools", type=Path, help="Android build-tools folder (zipalign, apksigner)")
    ap.add_argument("--keystore", type=Path, help="debug keystore (alias androiddebugkey, password android)")
    a = ap.parse_args(argv)
    SRC_APK = a.apk or SRC_APK
    if a.out:
        OUT_DIR = a.out
    OUT_APK = OUT_DIR / OUT_APK.name
    REDIRECT_DEX = OUT_DIR / REDIRECT_DEX.name
    CLIENT_APK = OUT_DIR / CLIENT_APK.name
    CLIENT_SIGNED = OUT_DIR / CLIENT_SIGNED.name
    NDK = a.ndk_bin or NDK
    BUILD_TOOLS = a.build_tools or BUILD_TOOLS
    DEBUG_KEYSTORE = a.keystore or DEBUG_KEYSTORE


if __name__ == "__main__":
    configure(sys.argv[1:])
    sys.exit(main())
