/*
 * Project RETR0 - Frida hook (Java level) for Real Racing 3 14.0.1: log, record, or redirect its CloudCell traffic.
 *
 * Use only under RUNTIME_TEST_PLAN.md §4d/§9 (locked test emulator, test identity, owner approval).
 *
 * Why Java: on an x86_64 emulator the game's ARM libraries run through Android's ARM translator, which Frida
 * cannot hook (see retr0_redirect.js, arm64-only). CloudCell's native layer performs its HTTP through this Java
 * class (NETWORKING_ANALYSIS NW-01), so sync, asset-manager and CDN requests all pass through it:
 *     com.firemonkeys.cloudcellapi.HttpRequest.init(String userAgent, String method, String url, byte[] body,
 *         int readCapacity, long callbackPtr, boolean failOnErrorStatus, double serverTime, boolean sslCheck,
 *         boolean addDefaultHeaders, int timeoutSeconds)
 *     HttpRequest.addHeader(String, String)   HttpRequest.post()  (starts the request thread)
 *
 * MODE (default 'log'; capture_run.py --mode/--port writes the PARAMS line in a temporary copy of this file):
 *   'log'      changes nothing; prints method, host, path and body size of every request (no query, headers or
 *              body, which can carry identity data).
 *   'record'   changes nothing; emits one machine-readable line per request
 *                  RETR0JSON {"id","t","method","url","headers":{..},"body_b64",...}
 *              with the FULL url, headers and body (bodies over 512 KiB are truncated and flagged). Use only on
 *              the test emulator; capture_run.py stores these lines under 08_TESTING/runtime/out/ (gitignored).
 *   'redirect' as 'record', and every request to a CloudCell host (*.cloudcell.com, *.exos.fm) or the asset CDN
 *              (firemonkeys.akamaized.net) is rewritten to http://127.0.0.1:<port><original path+query>, with
 *              header X-RETR0-Host: <original host>. Reaches the host PC through `adb reverse tcp:8780 tcp:8780`;
 *              plain HTTP to 127.0.0.1 is allowed by the app's network_security_config.xml. Other hosts untouched
 *              (and blocked by avd_network_lock.sh).
 * Discovery hooks (all modes, never modify anything): java.net.URL.openConnection and InetAddress lookups, each
 *              distinct value logged once. Lookups from native/translated code are caught by dns_logger.py.
 *
 * Guards: refuses unless the package is com.ea.games.r3_row version 14.0.1 and init() has exactly the
 * 11-parameter signature above.
 *
 * Usage:  python -I 08_TESTING/runtime/capture_run.py --mode record      (preferred: keeps the session alive)
 *   or    frida -U -f com.ea.games.r3_row -l 08_TESTING/runtime/retr0_redirect_java.js
 * (The frida CLI provides the Java bridge on Frida 17.)
 */
'use strict';

const PARAMS = /*RETR0_PARAMS*/{}/*END*/;        // capture_run.py writes {"mode":..,"port":..} here in a temp copy
const MODE = PARAMS.mode || 'log';                 // 'log' | 'record' | 'redirect'
const LOCAL_HOST = '127.0.0.1';
const LOCAL_PORT = PARAMS.port || 8780;
const PACKAGE = 'com.ea.games.r3_row';
const EXPECTED_VERSION = '14.0.1';
const REDIRECT_HOSTS = /(^|\.)cloudcell\.com$|(^|\.)exos\.fm$|^firemonkeys\.akamaized\.net$/i;
const BODY_LIMIT = 512 * 1024;
const INIT_SIG = ['java.lang.String', 'java.lang.String', 'java.lang.String', '[B', 'int', 'long', 'boolean',
                  'double', 'boolean', 'boolean', 'int'];

// Split an absolute http(s) URL without java.net.URL so a malformed value cannot throw inside the hook.
function splitUrl(u) {
  const m = /^(https?):\/\/([^/:?#]+)(?::(\d+))?([^?#]*)(\?[^#]*)?/i.exec(u || '');
  if (!m) return null;
  return { scheme: m[1].toLowerCase(), host: m[2], port: m[3] ? parseInt(m[3], 10) : null,
           path: m[4] || '/', query: m[5] || '' };
}

function packageVersion() {
  const app = Java.use('android.app.ActivityThread').currentApplication();
  if (app === null) return null;
  const ctx = app.getApplicationContext();
  if (String(ctx.getPackageName()) !== PACKAGE) return 'wrong package ' + ctx.getPackageName();
  const pm = ctx.getPackageManager();
  return String(pm.getPackageInfo.overload('java.lang.String', 'int').call(pm, PACKAGE, 0).versionName.value);
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
function b64(bytes) {
  let out = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i] & 255, b = i + 1 < bytes.length ? bytes[i + 1] & 255 : 0, c = i + 2 < bytes.length ? bytes[i + 2] & 255 : 0;
    const n = (a << 16) | (b << 8) | c;
    out += B64[(n >> 18) & 63] + B64[(n >> 12) & 63] + (i + 1 < bytes.length ? B64[(n >> 6) & 63] : '=') +
           (i + 2 < bytes.length ? B64[n & 63] : '=');
  }
  return out;
}

Java.perform(function () {
  let HttpRequest, init;
  try {
    HttpRequest = Java.use('com.firemonkeys.cloudcellapi.HttpRequest');
    init = HttpRequest.init.overload.apply(HttpRequest.init, INIT_SIG);
  } catch (e) {
    console.log('[RETR0] REFUSING: HttpRequest.init(11 args) not found - not the analysed build. ' + e);
    return;
  }
  const System = Java.use('java.lang.System');
  const pending = {};          // identityHashCode(HttpRequest) -> record being built
  let nextId = 1, versionChecked = false, versionOk = false;

  function key(obj) { return System.identityHashCode(obj); }

  init.implementation = function (ua, method, url, body, cap, cb, failOnErr, serverTime, sslCheck, addHdrs, timeout) {
    if (!versionChecked) {
      versionChecked = true;
      const v = packageVersion();
      versionOk = (v === EXPECTED_VERSION);
      console.log('[RETR0] package version ' + v + (versionOk ? ' - OK, mode ' + MODE : ' - REFUSING, hook inactive'));
    }
    const original = String(url);
    const p = splitUrl(original);
    let outUrl = url, redirectedFrom = null;
    if (versionOk && p) {
      console.log('[RETR0][cc-http] ' + method + ' ' + p.scheme + '://' + p.host + (p.port ? ':' + p.port : '') + p.path +
                  (p.query ? ' (query ' + (p.query.length - 1) + ' chars)' : '') +
                  ' body=' + (body === null ? 0 : body.length) + 'B');
      if (MODE === 'redirect' && REDIRECT_HOSTS.test(p.host)) {
        outUrl = 'http://' + LOCAL_HOST + ':' + LOCAL_PORT + p.path + p.query;
        redirectedFrom = p.host;
      }
    }
    const ret = init.call(this, ua, method, outUrl, body, cap, cb, failOnErr, serverTime, sslCheck, addHdrs, timeout);
    if (versionOk && (MODE === 'record' || MODE === 'redirect')) {
      const n = body === null ? 0 : body.length;
      const rec = { id: nextId++, t: Date.now(), method: String(method), url: original, sent_to: String(outUrl),
                    user_agent: String(ua), read_capacity: cap, fail_on_error: failOnErr, ssl_check: sslCheck,
                    default_headers: addHdrs, timeout_s: timeout, server_time: serverTime, headers: {},
                    body_len: n, body_truncated: n > BODY_LIMIT, body_b64: '' };
      if (n > 0) {
        const m = Math.min(n, BODY_LIMIT), bytes = new Array(m);
        for (let i = 0; i < m; i++) bytes[i] = body[i];
        rec.body_b64 = b64(bytes);
      }
      pending[key(this)] = rec;
      if (redirectedFrom !== null) {
        try { this.addHeader('X-RETR0-Host', redirectedFrom); } catch (e) { /* thread not created */ }
      }
    }
    return ret;
  };

  HttpRequest.addHeader.implementation = function (k, v) {
    const rec = pending[key(this)];
    if (rec && String(k) !== 'X-RETR0-Host') rec.headers[String(k)] = String(v);
    return this.addHeader(k, v);
  };

  HttpRequest.post.implementation = function () {
    const k = key(this), rec = pending[k];
    if (rec) {
      delete pending[k];
      console.log('RETR0JSON ' + JSON.stringify(rec));
    }
    return this.post();
  };
  console.log('[RETR0] hooked HttpRequest.init/addHeader/post (mode ' + MODE + ', port ' + LOCAL_PORT + ')');

  // Discovery only (never modifies anything): other Java networking in the process (EA Nimble/Synergy, Firebase,
  // ad and analytics SDKs). Logs scheme://host:port/path and looked-up hostnames once each.
  const seen = {};
  function once(tag, s) { if (!seen[tag + s]) { seen[tag + s] = true; console.log('[RETR0][' + tag + '] ' + s); } }
  try {
    const URL = Java.use('java.net.URL');
    URL.openConnection.overloads.forEach(function (ov) {
      ov.implementation = function () {
        try {
          const port = this.getPort();
          once('java-url', this.getProtocol() + '://' + this.getHost() + (port > 0 ? ':' + port : '') + this.getPath());
        } catch (e) { /* never break the app for logging */ }
        return ov.apply(this, arguments);
      };
    });
    const Inet = Java.use('java.net.InetAddress');
    ['getAllByName', 'getByName'].forEach(function (m) {
      Inet[m].overloads.forEach(function (ov) {
        ov.implementation = function (host) {
          if (host !== null) once('java-dns', String(host));
          return ov.apply(this, arguments);
        };
      });
    });
    console.log('[RETR0] discovery hooks on java.net.URL.openConnection and InetAddress lookups');
  } catch (e) {
    console.log('[RETR0] discovery hooks not installed: ' + e);
  }
});
