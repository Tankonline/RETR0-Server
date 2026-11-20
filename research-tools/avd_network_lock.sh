#!/usr/bin/env bash
# Project RETR0 - cut the test emulator off from the network, except loopback (adb reverse / frida).
#
# Runs on the HOST and drives the emulator over adb (needs the Google APIs image, where `adb root` works).
# Rules live in their own chain RETR0_LOCK, inserted first in OUTPUT, for IPv4 and IPv6:
#     loopback -> allowed      (adb reverse tcp:8780 and frida's adb forward both arrive on lo)
#     replies to connections started from outside -> allowed (adb's own link)
#     anything else leaving the emulator -> REJECT
# The rules are NOT persistent: run `lock` again after every emulator boot, before starting the game.
#
# Usage:  bash 08_TESTING/runtime/avd_network_lock.sh lock|unlock|status [-s emulator-5554] [--allow-dns]
set -euo pipefail
export MSYS_NO_PATHCONV=1            # Git Bash on Windows: do not rewrite /system/... paths

ADB="${ADB:-$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe}"
ACTION="${1:-status}"
shift || true
SERIAL_ARGS=()
ALLOW_DNS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -s) SERIAL_ARGS=(-s "$2"); shift 2 ;;
    --allow-dns) ALLOW_DNS=1; shift ;;   # DNS to the emulator resolver 10.0.2.3 only; pair with -dns-server 127.0.0.1
    *) echo "unknown option $1"; exit 1 ;;
  esac
done
adbsh() { "$ADB" "${SERIAL_ARGS[@]}" shell "$@"; }

ensure_root() {
  if [[ "$(adbsh id -u | tr -d '\r')" != "0" ]]; then
    "$ADB" "${SERIAL_ARGS[@]}" root >/dev/null
    sleep 2
    "$ADB" "${SERIAL_ARGS[@]}" wait-for-device
  fi
  [[ "$(adbsh id -u | tr -d '\r')" == "0" ]] || { echo "adb root failed (Play Store image?)"; exit 1; }
}

tcp_probe() {
  # TCP connect test run on the device. A connection that opens stays idle until `timeout` kills it (rc 124)
  # or closes cleanly (rc 0): both mean REACHABLE. A REJECT or failed lookup ends at once with rc 1.
  # (ICMP is useless here: the emulator's user-mode network never answers ping, locked or not.)
  local rc
  rc=$(adbsh "timeout 6 toybox nc -w 4 $1 $2 </dev/null >/dev/null 2>&1; echo \$?" | tr -d '\r')
  if [[ "$rc" == "0" || "$rc" == "124" ]]; then echo "  tcp $1:$2  REACHABLE"; return 1; fi
  echo "  tcp $1:$2  blocked (rc $rc)"; return 0
}

probe() {
  # Outbound probes; each must be blocked while locked. Never contacts EA hosts.
  local ok=0
  tcp_probe 1.1.1.1 443 || ok=1        # direct IP
  tcp_probe 8.8.8.8 53 || ok=1         # DNS server over TCP
  tcp_probe dns.google 443 || ok=1     # needs a DNS lookup first
  return $ok
}

case "$ACTION" in
  lock)
    ensure_root
    for t in iptables ip6tables; do
      adbsh "$t -w -N RETR0_LOCK 2>/dev/null; $t -w -F RETR0_LOCK
             $t -w -A RETR0_LOCK -o lo -j RETURN
             $t -w -A RETR0_LOCK -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN"
      if [[ $ALLOW_DNS == 1 && $t == iptables ]]; then
        adbsh "$t -w -A RETR0_LOCK -d 10.0.2.3/32 -p udp --dport 53 -j RETURN
               $t -w -A RETR0_LOCK -d 10.0.2.3/32 -p tcp --dport 53 -j RETURN"
      fi
      adbsh "$t -w -A RETR0_LOCK -j REJECT
             $t -w -C OUTPUT -j RETR0_LOCK 2>/dev/null || $t -w -I OUTPUT 1 -j RETR0_LOCK"
    done
    echo "RETR0_LOCK installed. Probes:"
    if probe; then echo "LOCKED: no outbound route found."; else echo "WARNING: something is still reachable"; exit 2; fi
    ;;
  unlock)
    ensure_root
    for t in iptables ip6tables; do
      adbsh "while $t -w -D OUTPUT -j RETR0_LOCK 2>/dev/null; do :; done; $t -w -F RETR0_LOCK 2>/dev/null; $t -w -X RETR0_LOCK 2>/dev/null; true"
    done
    echo "RETR0_LOCK removed (emulator has normal networking again)."
    ;;
  status)
    ensure_root
    for t in iptables ip6tables; do
      if adbsh "$t -w -C OUTPUT -j RETR0_LOCK" >/dev/null 2>&1; then echo "$t: RETR0_LOCK active"; else echo "$t: not locked"; fi
    done
    probe && echo "no outbound route found" || echo "outbound traffic possible"
    ;;
  *) echo "usage: $0 lock|unlock|status [-s serial]"; exit 1 ;;
esac
