"""Build classes2.dex with the RETR0 local-server redirect built into HttpRequest.init (RR3 14.0.1).

Never touches 00_ORIGINAL: apktool decodes the original APK's code (resources left encoded) into
08_TESTING/runtime/out/apk/smali_work/, two lines are inserted into HttpRequest.init, Redirect.smali is added,
apktool rebuilds, and classes2.dex is copied out to 08_TESTING/runtime/out/apk/classes2_redirect.dex.
store_grant_patch/build_patch.py then puts that dex into the patched APK.

    init(...):  p3 (url) = com.retr0.Redirect.rewrite(p3)      first instruction
                com.retr0.Redirect.finish(this)                  just before return (adds X-RETR0-Host)
"""
import hashlib, shutil, subprocess, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC_APK = ROOT / "00_ORIGINAL/APK/real-racing-3-14-0-1.apk"
WORK = ROOT / "08_TESTING/runtime/out/apk/smali_work"
OUT_DEX = ROOT / "08_TESTING/runtime/out/apk/classes2_redirect.dex"
APKTOOL = Path(r"C:\tools\APKTool\apktool_3.0.3.jar")
EXPECT_SHA = "dcfe3788004444bd69e2fb839c18a973b488e94f46f1b818b6c005afdcad1d5f"

SIG = ".method public init(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;[BIJZDZZI)V\n    .locals 12\n"
TAIL = ("    iput-object v11, v10, Lcom/firemonkeys/cloudcellapi/HttpRequest;->m_thread:Lcom/firemonkeys/cloudcellapi/HttpThread;\n"
        "\n    return-void\n.end method")
REWRITE = ("\n    # RETR0: send CloudCell/CDN requests to the local server\n"
           "    invoke-static {p3}, Lcom/retr0/Redirect;->rewrite(Ljava/lang/String;)Ljava/lang/String;\n\n"
           "    move-result-object p3\n")
FINISH = "\n    invoke-static {p0}, Lcom/retr0/Redirect;->finish(Lcom/firemonkeys/cloudcellapi/HttpRequest;)V\n"


def main() -> int:
    assert hashlib.sha256(SRC_APK.read_bytes()).hexdigest() == EXPECT_SHA, "original APK hash mismatch"
    dec = WORK / "dec"
    if dec.exists():
        shutil.rmtree(dec)
    WORK.mkdir(parents=True, exist_ok=True)
    OUT_DEX.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["java", "-jar", str(APKTOOL), "d", "-r", "-f", "-o", str(dec), str(SRC_APK)], check=True)

    hr = dec / "smali_classes2/com/firemonkeys/cloudcellapi/HttpRequest.smali"
    s = hr.read_text(encoding="utf-8")
    assert s.count(SIG) == 1, "HttpRequest.init signature not found"
    s = s.replace(SIG, SIG + REWRITE, 1)
    assert s.count(TAIL) == 1, "HttpRequest.init tail not found"
    s = s.replace(TAIL, TAIL.replace("\n    return-void", FINISH + "\n    return-void"), 1)
    hr.write_text(s, encoding="utf-8", newline="\n")
    dst = dec / "smali_classes2/com/retr0/Redirect.smali"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "Redirect.smali", dst)

    built = WORK / "rebuilt.apk"
    subprocess.run(["java", "-jar", str(APKTOOL), "b", "-f", "-o", str(built), str(dec)], check=True)
    OUT_DEX.write_bytes(zipfile.ZipFile(built).read("classes2.dex"))
    print(f"classes2.dex {OUT_DEX} sha256 {hashlib.sha256(OUT_DEX.read_bytes()).hexdigest()}")
    return 0


def configure(argv: list[str]) -> None:
    """Optional overrides for use outside the project layout (defaults: the project's paths)."""
    import argparse
    global SRC_APK, WORK, OUT_DEX, APKTOOL
    ap = argparse.ArgumentParser(description="Build classes2.dex with the built-in RETR0 redirect.")
    ap.add_argument("--apk", type=Path, help="your original real-racing-3-14-0-1.apk (SHA-256 checked)")
    ap.add_argument("--out", type=Path, help="output folder: classes2_redirect.dex and the smali_work folder")
    ap.add_argument("--apktool", type=Path, help="apktool jar (3.0.3 was used)")
    a = ap.parse_args(argv)
    SRC_APK = a.apk or SRC_APK
    if a.out:
        WORK, OUT_DEX = a.out / "smali_work", a.out / "classes2_redirect.dex"
    APKTOOL = a.apktool or APKTOOL


if __name__ == "__main__":
    configure(sys.argv[1:])
    sys.exit(main())
