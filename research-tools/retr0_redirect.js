/*
 * Project RETR0 - Frida hook: point Real Racing 3 14.0.1's CloudCell sync at the local RETR0 service.
 *
 * STATUS: written for review. NOT RUN. Use only under the approved RUNTIME_TEST_PLAN.md (option A).
 *
 * What it does, and nothing else:
 *   The game builds every HTTP request through FUN 0x1c754a0 (arm64 libRealRacing3.so):
 *       build(out, const string& method, const string& host, const string& path, int port, bool tls, bool f)
 *   (confirmed from the sync sender 0x1d03520: x1 "POST", x2 SyncManager+0x90 = SyncDomain,
 *    x3 "CC_Sync.php", w4 = .rodata constant 443). The URL is later assembled by 0x1c756d8 as
 *       (port == 443 ? "https://" : "http://") + host + ":" + port + "/" + path
 *   For calls whose path is exactly "CC_Sync.php" and whose host is a CloudCell host, MODE "redirect"
 *   replaces host with "127.0.0.1" and port with LOCAL_PORT. Port != 443 means plain HTTP, which the
 *   game's network security config allows to 127.0.0.1 only. MODE "log" changes nothing and prints
 *   method/host/path/port of every request (no bodies, no identity data).
 *
 * Safety guards: refuses to run unless the process is arm64 and the first 16 bytes of the target match
 * the analysed build (SHA-256 of libRealRacing3.so 57edb631...5aa73051). It never touches other hosts,
 * other paths, files, or request bodies.
 *
 * Usage (after approval):  adb reverse tcp:8780 tcp:8780
 *                          frida -U -f com.ea.games.r3_row -l retr0_redirect.js
 */
'use strict';

const MODE = 'log';            // 'log' first; switch to 'redirect' only after the log-only run
const LOCAL_HOST = '127.0.0.1';
const LOCAL_PORT = 8780;
const LIB = 'libRealRacing3.so';
const BUILD_REQUEST_OFFSET = 0x1c754a0;           // ELF vaddr == offset from load base
const EXPECTED_PROLOGUE = 'fc6fbaa9fa6701a9f85f02a9f65703a9';
const CLOUDCELL_HOST = /(^|\.)cloudcell\.com$|(^|\.)exos\.fm$/;

function hex(buf) {
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

// libc++ std::string: short form = byte0 (len << 1), chars at +1; long form = byte0 bit0 set,
// size at +8, data pointer at +16.
function readStdString(p) {
  if (p.isNull()) return null;
  const b0 = p.readU8();
  let len, data;
  if ((b0 & 1) === 0) {
    len = b0 >> 1;
    data = p.add(1);
  } else {
    len = p.add(8).readU64().toNumber();
    data = p.add(16).readPointer();
  }
  if (len > 512) return null;
  return data.readUtf8String(len);
}

function makeShortStdString(s) {
  if (s.length > 22) throw new Error('short-string form only');
  const m = Memory.alloc(24);
  m.writeU8(s.length << 1);
  m.add(1).writeUtf8String(s);
  return m;
}

const LOCAL_HOST_STR = makeShortStdString(LOCAL_HOST);   // kept alive for the whole session

function install(base) {
  if (Process.arch !== 'arm64') {
    console.log(`[retr0] refusing: process arch is ${Process.arch}, script only supports arm64`);
    return;
  }
  const target = base.add(BUILD_REQUEST_OFFSET);
  const prologue = hex(target.readByteArray(16));
  if (prologue !== EXPECTED_PROLOGUE) {
    console.log(`[retr0] refusing: unexpected bytes at target (${prologue}); different build?`);
    return;
  }
  Interceptor.attach(target, {
    onEnter(args) {
      const method = readStdString(args[1]);
      const host = readStdString(args[2]);
      const path = readStdString(args[3]);
      const port = args[4].toInt32();
      console.log(`[retr0] request ${method} host=${host} path=${path} port=${port}`);
      if (MODE !== 'redirect' || path !== 'CC_Sync.php' || host === null || !CLOUDCELL_HOST.test(host)) return;
      args[2] = LOCAL_HOST_STR;
      args[4] = ptr(LOCAL_PORT);
      console.log(`[retr0]   -> redirected to http://${LOCAL_HOST}:${LOCAL_PORT}/${path}`);
    }
  });
  console.log(`[retr0] hook installed at ${target} (mode ${MODE})`);
}

// The library is loaded by the Java layer after start-up; wait for it.
const timer = setInterval(() => {
  const m = Process.findModuleByName(LIB);
  if (m === null) return;
  clearInterval(timer);
  install(m.base);
}, 50);
