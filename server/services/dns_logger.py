"""Project RETR0 - discovery DNS server for the test emulator. Logs every hostname looked up; resolves NOTHING.

Every query is answered NXDOMAIN ("no such host"), so no lookup ever reaches a real DNS server and the game
never learns an address: nothing can contact EA or anyone else. It only records which names the client asks for
(from Java, native or translated ARM code alike, because Android resolves all of them through netd).

Run on the host, then start the emulator with  -dns-server 127.0.0.1  and lock it with
avd_network_lock.sh lock --allow-dns  (lets DNS reach the emulator's resolver 10.0.2.3, which forwards here).

Usage: python -I 08_TESTING/runtime/dns_logger.py [--bind 127.0.0.1] [--port 53] [--log dns_queries.jsonl]
Output: one JSON line per query {time, client, name, type}; a summary of distinct names on Ctrl+C.
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import time
from collections import Counter

QTYPES = {1: "A", 28: "AAAA", 5: "CNAME", 12: "PTR", 15: "MX", 16: "TXT", 33: "SRV", 65: "HTTPS", 64: "SVCB"}


def parse_question(pkt: bytes) -> tuple[str, int, int]:
    """Return (name, qtype, end offset of the question) for the first question. Raises on malformed input."""
    o, labels = 12, []
    while True:
        n = pkt[o]
        if n == 0:
            o += 1
            break
        if n & 0xC0:
            raise ValueError("compression pointer in question")
        labels.append(pkt[o + 1:o + 1 + n].decode("ascii", "replace"))
        o += 1 + n
        if o > len(pkt) or len(labels) > 64:
            raise ValueError("bad name")
    qtype, _qclass = struct.unpack_from(">HH", pkt, o)
    return ".".join(labels).lower(), qtype, o + 4


def nxdomain(pkt: bytes, q_end: int) -> bytes:
    tid, flags = struct.unpack_from(">HH", pkt, 0)
    rd = flags & 0x0100
    # QR=1, opcode copied, RD copied, RA=1, RCODE=3 (NXDOMAIN); one question, no answers
    out_flags = 0x8000 | (flags & 0x7800) | rd | 0x0080 | 3
    return struct.pack(">HHHHHH", tid, out_flags, 1, 0, 0, 0) + pkt[12:q_end]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=53)
    ap.add_argument("--log", default="dns_queries.jsonl")
    a = ap.parse_args()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((a.bind, a.port))
    seen: Counter[str] = Counter()
    print(f"dns_logger listening on {a.bind}:{a.port} (answers NXDOMAIN to everything); log -> {a.log}", flush=True)
    with open(a.log, "a", encoding="utf-8") as log:
        try:
            while True:
                pkt, addr = s.recvfrom(4096)
                try:
                    name, qtype, q_end = parse_question(pkt)
                except (ValueError, IndexError, struct.error):
                    continue
                t = QTYPES.get(qtype, str(qtype))
                rec = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "client": addr[0], "name": name, "type": t}
                log.write(json.dumps(rec) + "\n"); log.flush()
                if seen[name] == 0:
                    print(f"NEW  {t:5} {name}", flush=True)
                seen[name] += 1
                s.sendto(nxdomain(pkt, q_end), addr)
        except KeyboardInterrupt:
            pass
    print("\nDistinct names:", flush=True)
    for n, c in seen.most_common():
        print(f"{c:6}  {n}")


if __name__ == "__main__":
    main()
