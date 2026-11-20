"""Project RETR0 - username UI text patch for RR3 14.0.1 (game data files, not the APK). Standard library only.

Builds edited copies of two UI layouts from the user's OWN game files:
  SettingsMenu.gui    button label GAMETEXT_ENTER_PROMO_CODE -> "Change Username (Restart Required)"
  TextEntryPopup.gui  the game sets LBL_HEADING to "Enter your code:" at run time, so that label is moved off-screen
                      and a fixed label "Enter your new username (restart required):" is added in its place
A GuiLabel whose text is not a GAMETEXT_ key is drawn as written (verified on the emulator, test run 31).

.gui files are RC4-encrypted (8-byte key, first 133 keystream bytes dropped; the same cipher as .nct). The key is
read at run time from the user's own arm64 libRealRacing3.so (ELF vaddr 0x49c8f8); it is never stored here.
The input files are only read; outputs go to --out. Copying them onto the device is up to the caller
(client.ps1 ui-text keeps the originals for ui-text-restore).

Usage: python -I retr0_gui_patch.py <original APK or arm64 libRealRacing3.so> <folder with the two .gui files> --out <dir>
"""
from __future__ import annotations

import argparse
import re
import struct
import zipfile
from pathlib import Path

KEY_VADDR, KEY_LEN, DROP = 0x49C8F8, 8, 0x85
LIB_IN_APK = "lib/arm64-v8a/libRealRacing3.so"
BUTTON_TEXT = "Change Username (Restart Required)"
HEADING_TEXT = "Enter your new username (restart required):"
NEW_LABEL_ID = "1375419001"


def load_lib(path: Path) -> bytes:
    data = path.read_bytes()
    if data[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(path) as z:
            data = z.read(LIB_IN_APK)
    return data


def read_key(elf: bytes) -> bytes:
    """Map the key's virtual address to a file offset through the PT_LOAD program headers (ELF64, little endian)."""
    if elf[:4] != b"\x7fELF" or elf[4] != 2 or elf[5] != 1:
        raise SystemExit("expected the arm64 (64-bit) libRealRacing3.so or the APK that contains it")
    phoff, = struct.unpack_from("<Q", elf, 0x20)
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x36)
    for i in range(phnum):
        p_type, _, p_offset, p_vaddr, _, p_filesz = struct.unpack_from("<IIQQQQ", elf, phoff + i * phentsize)
        if p_type == 1 and p_vaddr <= KEY_VADDR < p_vaddr + p_filesz:
            off = p_offset + KEY_VADDR - p_vaddr
            return elf[off:off + KEY_LEN]
    raise SystemExit("key address not in the library (not RR3 14.0.1 arm64?)")


def rc4_drop(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 0xFF
        s[i], s[j] = s[j], s[i]
    i = j = 0
    for _ in range(DROP):
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
    out = bytearray(len(data))
    for n, b in enumerate(data):
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out[n] = b ^ s[(s[i] + s[j]) & 0xFF]
    return bytes(out)


def patch_settings(xml: str) -> str:
    old = 'text="GAMETEXT_ENTER_PROMO_CODE"'
    if xml.count(old) != 1:
        raise SystemExit("SettingsMenu.gui: button label not found exactly once (already patched or another version?)")
    return xml.replace(old, f'text="{BUTTON_TEXT}"')


def patch_popup(xml: str) -> str:
    m = re.search(r'\t<GuiLabel type="11" id="1375410590" id_string="LBL_HEADING".*?</GuiLabel>\r?\n', xml, re.S)
    if not m or NEW_LABEL_ID in xml or 'x="0.188477"' not in m.group(0):
        raise SystemExit("TextEntryPopup.gui: heading label not as expected (already patched or another version?)")
    el = m.group(0)
    hidden = el.replace('x="0.188477"', 'x="5"', 1)
    label = el.replace(' id="1375410590" id_string="LBL_HEADING" text="GAMETEXT_ENTER_NAME"',
                       f' id="{NEW_LABEL_ID}" id_string="" text="{HEADING_TEXT}"', 1)
    if label == el:
        raise SystemExit("TextEntryPopup.gui: heading text not as expected")
    return xml.replace(el, hidden + label, 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the RETR0 username UI text patch from your own game files.")
    ap.add_argument("lib", type=Path, help="original RR3 14.0.1 APK, or its lib/arm64-v8a/libRealRacing3.so")
    ap.add_argument("gui_dir", type=Path, help="folder holding SettingsMenu.gui and TextEntryPopup.gui "
                                                "(e.g. files/.depot/gui/processed)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    key = read_key(load_lib(a.lib))
    a.out.mkdir(parents=True, exist_ok=True)
    for name, fn in (("SettingsMenu.gui", patch_settings), ("TextEntryPopup.gui", patch_popup)):
        src = a.gui_dir / name
        xml = rc4_drop(key, src.read_bytes()).decode("utf-8")
        if not xml.startswith("<?xml"):
            raise SystemExit(f"{name}: did not decode to XML (wrong library or game version?)")
        data = rc4_drop(key, fn(xml).encode("utf-8"))
        (a.out / name).write_bytes(data)
        print(f"{name}: {src.stat().st_size} -> {len(data)} bytes -> {a.out / name}")


if __name__ == "__main__":
    main()
