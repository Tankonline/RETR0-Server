"""Project RETR0 — clean-room CloudCell BinaryBlob codec.

INDEPENDENT IMPLEMENTATION written from the behaviour documented in
07_DOCUMENTATION/NETWORKING_ANALYSIS.md §8 (arm64 functions BinaryBlob::BoxData 0x1cbd66c,
BinaryBlob::UnboxData 0x1cbd8f0, checksum 0x1cb9734, PackBlobHeader 0x1d00f38). It contains no
EA code. It has only been checked for internal consistency (round trips, documented arithmetic):
NO captured client/server traffic was available, so wire compatibility is UNVERIFIED.

Box layout (all integers little-endian, as written by the ARM client):
    u32 checksum      checksum(bytes[8:])
    u32 box_type      0 = plain, 1 = zlib, 2 = rolling XOR
    payload
        type 0: data
        type 1: u32 uncompressed_length + zlib.compress(data, level 9)
        type 2: u8 seed + data[i] XOR ((seed + 3*i) & 0xFF)

The client boxes request bodies as Box(Box(body, 1), 2) and unboxes responses twice.
"""
from __future__ import annotations

import random
import struct
import zlib

PLAIN, ZLIB, XOR = 0, 1, 2


def _s8(b: int) -> int:
    return b - 256 if b > 127 else b


def _trunc_div(a: int, b: int) -> int:
    """C-style integer division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def checksum(data: bytes) -> int:
    """Checksum over signed bytes in groups of four (a, b, c, d): sum += a*b*c / d.

    Partial final groups use the bytes present; division happens only when d exists and is non-zero.
    The result wraps like a 32-bit int and is returned as an unsigned 32-bit value.
    """
    total = 0
    n = len(data)
    for i in range(0, n, 4):
        v = _s8(data[i])
        if i + 1 < n:
            v *= _s8(data[i + 1])
        if i + 2 < n:
            v *= _s8(data[i + 2])
        if i + 3 < n and data[i + 3] != 0:
            v = _trunc_div(v, _s8(data[i + 3]))
        total = (total + v) & 0xFFFFFFFF
    return total


def box(data: bytes, box_type: int, seed: int | None = None) -> bytes:
    if box_type == PLAIN:
        payload = data
    elif box_type == ZLIB:
        payload = struct.pack("<I", len(data)) + zlib.compress(data, 9)
    elif box_type == XOR:
        s = random.randrange(256) if seed is None else seed & 0xFF
        payload = bytes([s]) + bytes(b ^ ((s + 3 * i) & 0xFF) for i, b in enumerate(data))
    else:
        raise ValueError(f"unknown box type {box_type}")
    body = struct.pack("<I", box_type) + payload
    return struct.pack("<I", checksum(body[4:])) + body


def unbox(blob: bytes) -> bytes:
    if len(blob) <= 8:
        raise ValueError("blob too short")
    stored, box_type = struct.unpack_from("<II", blob)
    if stored != checksum(blob[8:]):
        raise ValueError("checksum mismatch")
    payload = blob[8:]
    if box_type == PLAIN:
        return payload
    if box_type == ZLIB:
        (length,) = struct.unpack_from("<I", payload)
        out = zlib.decompress(payload[4:])
        if len(out) != length:
            raise ValueError("length mismatch after inflate")
        return out
    if box_type == XOR:
        s = payload[0]
        return bytes(b ^ ((s + 3 * i) & 0xFF) for i, b in enumerate(payload[1:]))
    raise ValueError(f"unknown box type {box_type}")


def pack_subsync(sub_type: int, param: int, payload: bytes) -> bytes:
    """One sub-sync record inside a request batch (SubSync pack, arm64 0x1d05af4):
    u32 type, u32 param, u32 reserved (0), u32 length, payload."""
    return struct.pack("<IIII", sub_type, param, 0, len(payload)) + payload


def parse_subsyncs(data: bytes, offset: int = 0) -> list[tuple[int, int, bytes]]:
    """Parse consecutive sub-sync records from `offset` to the end (no count field has been observed)."""
    out = []
    while offset < len(data):
        sub_type, param, reserved, n = struct.unpack_from("<IIII", data, offset)
        offset += 16
        if reserved != 0 or offset + n > len(data):
            raise ValueError(f"malformed sub-sync record at {offset - 16}")
        out.append((sub_type, param, data[offset:offset + n]))
        offset += n
    return out


def pack_response_parts(parts: list[bytes]) -> bytes:
    """Per-sub-sync response parts, in request order: u32 length + bytes each (SubSync receive, 0x1d05bb0).
    The leading response status field(s) are NOT included here (semantics only partly known)."""
    return b"".join(struct.pack("<I", len(p)) + p for p in parts)


# ---- individual sub-sync payloads (NETWORKING_ANALYSIS §8.9) -------------------------------------------

SUBSYNC_PLAYER_RANK = (10452, 6)
SUBSYNC_GET_PLAYER_GARAGE = (10607, 3491)
SUBSYNC_GET_PVP_SERVERS = (10768, 0)


def lp_string(s: str | bytes) -> bytes:
    """Length-prefixed string: u32 length + bytes (BinaryBlob string writer)."""
    b = s.encode("utf-8") if isinstance(s, str) else s
    return struct.pack("<I", len(b)) + b


def player_rank_request(member_id: int) -> bytes:
    """PlayerRankSync request payload: one u32 (object field +0x50, [likely] member id)."""
    return struct.pack("<I", member_id)


def player_rank_response(rank: int) -> bytes:
    """PlayerRankSync response part: one u32 rank. (An empty part makes the client use rank 500.)"""
    return struct.pack("<I", rank)


def garage_request(member_id: int) -> bytes:
    """GetPlayerGarageSync request payload: one u32 (object field +0x50, [likely] member id)."""
    return struct.pack("<I", member_id)


def garage_response(header: str | bytes, cars: list[tuple[int, int, bytes]]) -> bytes:
    """GetPlayerGarageSync response part: lp_string(header), u32 count, then per car
    (u32 a [likely car id], u32 b, lp-blob). Each blob is a complete `.cc_cust` file in the user-data
    container format (XOR stream + header + key dictionary; see SAVE_SYSTEM_ANALYSIS §2b), which the
    client writes to .depot/customisation/random_temp.2.cc_cust and loads with its save loader.
    Field meanings of `header`, `a`, `b` are not yet confirmed."""
    out = [lp_string(header), struct.pack("<I", len(cars))]
    for a, b, blob in cars:
        out.append(struct.pack("<II", a, b) + struct.pack("<I", len(blob)) + blob)
    return b"".join(out)


SUBSYNC_UPLOAD_VEHICLES = (10545, 2387)
SUBSYNC_GET_CUSTOMISATION_INFO = (10630, 2322)


def parse_upload_vehicles_request(data: bytes) -> tuple[int, list[tuple[int, bytes, int, int]]]:
    """UploadVehiclesSync request (slot 2, arm64 0xcec53c): u32 flag (object byte +0x68), u32 count,
    then per car: u32 id ([likely] car id), lp-blob (a complete `.cc_cust` file read back from
    .depot/customisation/NNN.2.cc_cust), u32 (always 0), u32 bit (car field +0x170 & 1).
    Returns (flag, [(id, cc_cust_bytes, zero, bit), ...])."""
    off = 0
    flag, n = struct.unpack_from("<II", data, off)
    off += 8
    cars = []
    for _ in range(n):
        car_id, ln = struct.unpack_from("<II", data, off)
        off += 8
        blob = data[off:off + ln]
        off += ln
        zero, bit = struct.unpack_from("<II", data, off)
        off += 8
        cars.append((car_id, blob, zero, bit))
    if off != len(data):
        raise ValueError("trailing bytes in UploadVehicles request")
    return flag, cars


def upload_vehicles_response(ids: list[int] | None) -> bytes:
    """UploadVehiclesSync response part (slot 3, 0xcecb78): u32 status; if non-zero, u32 count + u32 ids.
    `None` produces status 0, which the client reports as a failed upload (empty callback)."""
    if ids is None:
        return struct.pack("<I", 0)
    return struct.pack("<II", 1, len(ids)) + b"".join(struct.pack("<I", i) for i in ids)


def customisation_info_request(pairs: list[tuple[int, int]]) -> bytes:
    """GetCustomisationInfoSync request (slot 2, 0xced408): u32 count, then (u32 cc_member_id, u32 car_id)
    per garage car whose customisation was authored on the current CloudCell server (builder 0xef9f8c area;
    cars from another server are skipped and logged). HIGH confidence."""
    return struct.pack("<I", len(pairs)) + b"".join(struct.pack("<II", a, b) for a, b in pairs)


# ResultInfo record (0x40 bytes in memory), names from the consumers YourGarageList 0xefa444 and
# YourGarageScreen 0xefa8f8 (NETWORKING_ANALYSIS NW-34). unk_* fields are not read by those consumers.
CUSTOMISATION_INFO_FIELDS = ("cc_member_id", "car_id", "unk_c", "unk_d", "flag_bit0", "unk_f",
                             "name_valid", "member_name", "flag_bit1")


def customisation_info_response(results: list[tuple]) -> bytes:
    """GetCustomisationInfoSync response part (slot 3, 0xced508): u32 count, then per ResultInfo
    (see CUSTOMISATION_INFO_FIELDS): u32 cc_member_id, u32 car_id, bool32 unk_c, u32 unk_d,
    u32 flag_bit0 (non-zero sets car flags bit 0), u32 unk_f, bool32 name_valid, lp-string member_name,
    u32 flag_bit1 (non-zero sets car flags bit 1). bool32 values must be 0 or 1."""
    out = [struct.pack("<I", len(results))]
    for a, b, c, d, e, f, g, s, h in results:
        out.append(struct.pack("<IIIIIII", a, b, int(bool(c)), d, e, f, int(bool(g))) + lp_string(s)
                   + struct.pack("<I", h))
    return b"".join(out)


# ---- leaderboards (NETWORKING_ANALYSIS §8.11). Field names are neutral where meaning is UNKNOWN. -----------

SUBSYNC_LEADERBOARD = (10477, 3573)
SUBSYNC_LEADERBOARD_GROUP = (10484, 3574)
SUBSYNC_LEADERBOARD_FRIENDS = (10486, 5040)
SUBSYNC_LEADERBOARD_ENTRY = (10514, 1468)
SUBSYNC_LEADERBOARD_CCMEMBERID = (10516, 1900)
SUBSYNC_LEADERBOARD_VALIDATE = (10788, 5338)


def lb_key(board: int, keys: list[int]) -> bytes:
    """Common request prefix of LeaderBoard/Group/Friends/Entry/CCMemberId: u32 board (+0x50),
    u32 n, n x u32 (+0x58 vector)."""
    return struct.pack("<II", board, len(keys)) + b"".join(struct.pack("<I", k) for k in keys)


def leaderboard_request(board: int, keys: list[int], p70: int, p74: int, p78: int, p7c: int) -> bytes:
    """LeaderBoardSync request (0xce0310): key prefix + u32 x4 (object +0x70, +0x74, +0x78, +0x7c).
    +0x70 and +0x78 are echoed into the parsed result ([likely] range parameters)."""
    return lb_key(board, keys) + struct.pack("<IIII", p70, p74, p78, p7c)


def _f32_bits(x: float) -> bytes:
    return struct.pack("<f", x)


def lb_core(name: str, u18: int, s20: str, s38: str, blob: bytes, s50: str) -> bytes:
    """Common start of every leaderboard entry record: lp-string name (+0x00), u32 (+0x18),
    lp-string (+0x20), lp-string (+0x38), lp-blob (read and SKIPPED by the client), lp-string (+0x50)."""
    return (lp_string(name) + struct.pack("<I", u18) + lp_string(s20) + lp_string(s38)
            + struct.pack("<I", len(blob)) + blob + lp_string(s50))


def leaderboard_entry_main(core: bytes, s68: str, u8c: int, f90: float, s98: str, u84: int, u88: int,
                           vb0: list[int], u80: int) -> bytes:
    """LeaderBoardSync entry (0xce06a8): core + lp-string (+0x68), u32 (+0x8c), f32 (+0x90; the client
    adds 0.01 when > 0), lp-string (+0x98), u32 (+0x84), u32 (+0x88), u32 n + n x u32 (+0xb0), u32 (+0x80)."""
    return (core + lp_string(s68) + struct.pack("<I", u8c) + _f32_bits(f90) + lp_string(s98)
            + struct.pack("<III", u84, u88, len(vb0)) + b"".join(struct.pack("<I", v) for v in vb0)
            + struct.pack("<I", u80))


def leaderboard_response(own_index: int, h1: int, h2: int, entries: list[bytes]) -> bytes:
    """LeaderBoardSync response: u32 own_index ([likely] the local player's row; other rows may be shown as
    GAMETEXT_ANONYMOUS_RACER), u32 h1, u32 h2, u32 count, entries (leaderboard_entry_main)."""
    return struct.pack("<IIII", own_index, h1, h2, len(entries)) + b"".join(entries)


def leaderboard_entry_friends(core: bytes, u84: int, u88: int, u8c: int, f90: float, s98: str, u80: int,
                              s68: str) -> bytes:
    """LeaderBoardFriendsSync entry (0xce2510): core + u32 (+0x84), u32 (+0x88), u32 (+0x8c), f32 (+0x90),
    lp-string (+0x98), u32 (+0x80), lp-string (+0x68). Response = u32 count + entries."""
    return (core + struct.pack("<III", u84, u88, u8c) + _f32_bits(f90) + lp_string(s98)
            + struct.pack("<I", u80) + lp_string(s68))


def leaderboard_entry_short(core: bytes, u84: int, u88: int, u8c: int) -> bytes:
    """LeaderBoardCCMemberIdSync entry (0xce4808; response = u32 count + entries) and the single record of
    LeaderBoardEntrySync (0xce3ad4; response = one record, no count): core + u32 x3 (+0x84, +0x88, +0x8c)."""
    return core + struct.pack("<III", u84, u88, u8c)


def leaderboard_group_response(h0: int, h1: int, rows: list[tuple[str, int, int, int]]) -> bytes:
    """LeaderBoardGroupSync response (0xce1e08): u32, u32, u32 count, then per row lp-string, u32 x3."""
    out = [struct.pack("<III", h0, h1, len(rows))]
    for s, a, b, c in rows:
        out.append(lp_string(s) + struct.pack("<III", a, b, c))
    return b"".join(out)


def leaderboard_validate_response(valid: bool, value: int, extra: int = 0) -> bytes:
    """LeaderBoardValidateSync response (0xce1558): bool32 valid, u32 value, u32 (read, then discarded).
    An empty part gives the callback (received=0, valid=true, value=-1)."""
    return struct.pack("<III", int(bool(valid)), value, extra)


# ---- sales and online multiplayer (NETWORKING_ANALYSIS §8.13). Neutral names where meaning is UNKNOWN. ----

SUBSYNC_SALES = (10448, 5440)
SUBSYNC_MP_FINISHED_OR_DISCONNECT = (10532, 5431)
SUBSYNC_MP_MEMBER_STATUS = (10548, 1731)
SUBSYNC_MP_START_MATCH = (10626, 2218)
MP_MAGIC = 0x1D2D   # first u32 of start/finish/disconnect requests (constant 7469)


def sales_request() -> bytes:
    """SyncSales request (0xcf13b0): empty. The response part is handed unparsed to the callback (0xcf1420)."""
    return b""


def mp_member_status_request(match_value: int, flag: int) -> bytes:
    """OnlineMultiplayerMemberStatusSync request (0xce9eb8): u32 (match object +0x120), u32 (byte +0x14).
    Response (0xcea000): content ignored; non-empty part -> callback(1), empty -> callback(0)."""
    return struct.pack("<II", match_value, flag & 0xFF)


def mp_start_match_response(h0: int, h1: int, h2_5: tuple[int, int, int, int], h6: int, h7: int,
                            players: list[tuple[int, int, bytes, int]]) -> bytes:
    """OnlineMultiplayerStartMatchSync response (0xce76a8): u32 h0, u32 h1 (stored as a protected value),
    u32 x4, u32 h6 (protected value), u32 h7, u32 count, then per player: u32 member_id, u32 value,
    u32 blob_len, and if blob_len > 0: blob (an opponent `.cc_cust` file, written to
    .depot/customisation/omp/<member>_<NNN>.2.cc_cust for players other than the local one) + u32 index."""
    out = [struct.pack("<II", h0, h1), struct.pack("<4I", *h2_5), struct.pack("<III", h6, h7, len(players))]
    for member_id, value, blob, index in players:
        out.append(struct.pack("<III", member_id, value, len(blob)))
        if blob:
            out.append(blob + struct.pack("<I", index))
    return b"".join(out)


# ---- saved-game download (NETWORKING_ANALYSIS §8.14) ----------------------------------------------------

SUBSYNC_DOWNLOAD_SAVED_GAME = (10469, 3496)   # shared by DownloadSavedGameSync and ...RandomProgressSaveGameSync


def download_saved_game_request(max_count: int) -> bytes:
    """DownloadSavedGameSync request (0xcdd284): u32 (object +0x14, the maximum number of saves wanted).
    DownloadRandomProgressSaveGameSync (0xcddda4) sends the constant 50."""
    return struct.pack("<I", max_count)


def saved_game_list_response(saves: list[tuple[int, int, str, str]]) -> bytes:
    """Response (0xcdd30c / 0xcdde2c): u32 count (0 <= count <= requested, otherwise the client EXITS),
    then per save: u32 id (file name "<id>.bin"), u32 (meaning UNKNOWN), lp-string description,
    lp-string URL. The client then fetches each URL with HTTP GET; the body is one BinaryBlob box
    (unboxed once, see unbox()). An empty part is logged as an invalid blob size."""
    out = [struct.pack("<I", len(saves))]
    for sid, b, desc, url in saves:
        out.append(struct.pack("<II", sid, b) + lp_string(desc) + lp_string(url))
    return b"".join(out)


# ---- cloud save, cc::GameSaveManager (NETWORKING_ANALYSIS §8.15) -----------------------------------------

SUBSYNC_GSM_LIST = (47, 7277)           # QueueDownloadList: payload u32 1
SUBSYNC_GSM_DOWNLOAD = (48, 809)        # QueueDownloadSync: payload u32 save_id, u32 0
SUBSYNC_GSM_UPLOAD_REQUEST = (10660, 5638)   # normal upload: ask for an upload URL
SUBSYNC_GSM_UPLOAD_INLINE = (22, 2816)       # alternate upload carrying the save inline
SUBSYNC_GSM_VALIDATE = (10555, 5757)    # QueueValidate: payload lp-string


def gsm_upload_request(flag: int, s1: str, s2: str) -> bytes:
    """Normal upload request (0x1ce887c): u32 flag (byte +8), lp-string (+0x28), lp-string (+0x40)."""
    return struct.pack("<I", flag & 0xFF) + lp_string(s1) + lp_string(s2)


def gsm_upload_response(key: str, put_url: str) -> bytes:
    """Upload reply (0x1ce8d88): u32 status (0 = OK; anything else = failure), lp-string (kept in the upload
    record), lp-string URL. The client then sends the boxed save to that URL with HTTP PUT."""
    return struct.pack("<I", 0) + lp_string(key) + lp_string(put_url)


def gsm_download_response(ok: bool, save_blob: bytes) -> bytes:
    """Download-sync reply (0x1ce994c): bool32, lp-blob (the boxed save)."""
    return struct.pack("<I", int(bool(ok))) + struct.pack("<I", len(save_blob)) + save_blob


def gsm_validate_response(ok: bool) -> bytes:
    """Validate reply (0x1ceab68): bool32."""
    return struct.pack("<I", int(bool(ok)))


# ---- whole sync response body and the last two sub-syncs (NETWORKING_ANALYSIS §8.16) ---------------------

def sync_response_body(parts: list[bytes], value: int = 0, ok: bool = True,
                       trailing_ids: list[int] | None = None, member_id: int = 0, developer: bool = False,
                       device_id: int = 0, u_b: int = 0, flag: bool = False) -> bytes:
    """Plain body of a CC_Sync.php reply, before boxing (handler arm64 0x1d03ca0):
    u32 ok (0 = failure: every queued sub-sync completes with an EMPTY part), u32 value (handed to a
    CloudCell sub-object, meaning UNKNOWN), then the member header read by the active auth manager
    (cc::auth::LegacyManager 0x1cfb784): u32 member_id ("Member changed" when it differs from the
    client's), bool32 is_developer, u32 device_id ("CC: Device Id"), u32 u_b (vt+0x140 -> +0xe0), bool32 flag;
    then one `u32 len + bytes` part per queued sub-sync in queue order, then OPTIONALLY u32 n + n x u32 (inserted into a set kept by the SyncManager; meaning UNKNOWN).
    The client unboxes the reply twice, so send box(box(body, ZLIB), XOR) like a request (wrap_request)."""
    if not ok:
        return struct.pack("<I", 0)
    out = (struct.pack("<II", 1, value)
           + struct.pack("<IIIII", member_id, int(developer), device_id, u_b, int(flag))
           + pack_response_parts(parts))
    if trailing_ids is not None:
        out += struct.pack("<I", len(trailing_ids)) + b"".join(struct.pack("<I", i) for i in trailing_ids)
    return out


SUBSYNC_SYNC_USER_PN = (10455, 4240)


def data_request_request(kind: int, extra: int = 0) -> bytes:
    """FrontEnd2::DataRequestSubSync request (0xab3644; type/param supplied at run time): u32 kind (+0x14),
    and only when kind != 0, u32 (+0x18). Used by DataRequestPopup."""
    return struct.pack("<I", kind) + (struct.pack("<I", extra) if kind else b"")


def data_request_response(ok: bool, a: int, b: int) -> bytes:
    """DataRequestSubSync reply (0xab36f8): bool32, u32, u32 (stored as the popup's pending result)."""
    return struct.pack("<III", int(bool(ok)), a, b)


def pvp_servers_response(servers: list[tuple[str, int]]) -> bytes:
    """PingTestGetServersSync response part: u32 n (= 2 x entries), then per entry lp_string(host), u32 port."""
    out = [struct.pack("<I", 2 * len(servers))]
    for host, port in servers:
        out.append(lp_string(host) + struct.pack("<I", port))
    return b"".join(out)


def parse_pvp_servers_response(data: bytes) -> list[tuple[str, int]]:
    (n,) = struct.unpack_from("<I", data)
    off, out = 4, []
    for _ in range(n // 2):
        (ln,) = struct.unpack_from("<I", data, off)
        host = data[off + 4: off + 4 + ln].decode("utf-8")
        off += 4 + ln
        (port,) = struct.unpack_from("<I", data, off)
        off += 4
        out.append((host, port))
    return out


# ---- Direct sub-syncs with named fields (NETWORKING_ANALYSIS.md 8.18; subsync_features.py) ---------------
SUBSYNC_SERVER_VARIABLES = (10712, 4373)
SUBSYNC_REPORT_ABUSE = (10565, 2016)
SUBSYNC_RECORD_TRANSACTION = (10704, 5986)
SUBSYNC_RT_SYNC = (10673, 3645)


def server_variables_response(variables: dict[str, str] | list[tuple[str, str]]) -> bytes:
    """ServerVariableService reply (0x13c20f4): u32 count, then count x (lp key, lp value)."""
    items = list(variables.items()) if isinstance(variables, dict) else list(variables)
    return struct.pack("<I", len(items)) + b"".join(lp_string(k) + lp_string(v) for k, v in items)


def parse_server_variables_response(data: bytes) -> list[tuple[str, str]]:
    (n,) = struct.unpack_from("<I", data)
    off, out = 4, []
    for _ in range(n):
        pair = []
        for _ in range(2):
            (ln,) = struct.unpack_from("<I", data, off)
            pair.append(data[off + 4: off + 4 + ln].decode("utf-8"))
            off += 4 + ln
        out.append((pair[0], pair[1]))
    return out


def report_abuse_request(reportee_member_id: int, reportee_car_id: int) -> bytes:
    """Report Abuse / Inappropriate Customisation (0xceceac): u32 reportee member id, u32 reportee car id
    (the same two values are logged as telemetry 'Reportee CC Member Id' / 'Reportee Car Id')."""
    return struct.pack("<II", reportee_member_id, reportee_car_id)


def parse_record_transaction_request(data: bytes) -> dict:
    """NimbleMTX record-transaction request (0x1c78da4): lp transaction_id, lp receipt, lp item_sku,
    u32 timestamp, lp extra (meaning unknown)."""
    out, off = {}, 0
    for name in ("transaction_id", "receipt", "item_sku", "timestamp", "extra"):
        (v,) = struct.unpack_from("<I", data, off)
        off += 4
        if name == "timestamp":
            out[name] = v
            continue
        out[name] = data[off: off + v].decode("utf-8", "replace")
        off += v
    return out


def race_teams_parse_header(data: bytes) -> tuple[int, int, int]:
    """Every Race Teams request begins with u32 my_rt_member_id (global +0x1608), u32 rt_local (0xcd6c00,
    meaning unknown). Returns (my_rt_member_id, rt_local, offset_after_header)."""
    me, local = struct.unpack_from("<II", data)
    return me, local, 8


def race_teams_reply_prefix(my_rt_member_id: int) -> bytes:
    """Every Race Teams reply starts with u32 my_rt_member_id; the client stores it (global +0x1608) and sends
    it as the first field of its next Race Teams request. -1 means 'no Race Teams identity yet'."""
    return struct.pack("<i", my_rt_member_id)


SUBSYNC_RT_CREATE = (10670, 3607)
SUBSYNC_RT_JOIN = (10671, 3609)
SUBSYNC_RT_EDIT_TEAM = (10682, 2822)      # queued via helper 0xfb2cc4 (not in the direct catalogue)

RT_CREATE_OK, RT_CREATE_NAME_TAKEN, RT_CREATE_TAG_TAKEN, RT_CREATE_GENERIC, RT_CREATE_PROFANITY = range(5)


def _read_lp(data: bytes, off: int) -> tuple[str, int]:
    (n,) = struct.unpack_from("<I", data, off)
    return data[off + 4: off + 4 + n].decode("utf-8", "replace"), off + 4 + n


def parse_rt_create_request(data: bytes) -> dict:
    """10670 (0xfb3650): header, u32 0, lp name, lp tag, lp s3, lp s4 (motto and description; their order is
    not verified), bool32 is_private, u32 g710_4, u32 utc_offset_hours (signed)."""
    me, local, off = race_teams_parse_header(data)
    (zero,) = struct.unpack_from("<I", data, off)
    off += 4
    out = {"my_rt_member_id": me, "rt_local": local, "zero": zero}
    for k in ("name", "tag", "s3", "s4"):
        out[k], off = _read_lp(data, off)
    priv, g710, utc = struct.unpack_from("<IIi", data, off)
    out.update(is_private=bool(priv), g710_4=g710, utc_offset_hours=utc)
    return out


def rt_team_reply(my_rt_member_id: int, status: int, team: dict | None = None, *, join: bool = False) -> bytes:
    """Create (0xfb3a80) / join (0xfb5434) reply. status 0 is followed by the team: u32 team_id, u32 u1554,
    lp name, lp tag, lp motto, lp description, [join only: u32 leader_member_id], bool32 is_private.
    On create the client sets the leader to my_rt_member_id itself."""
    out = race_teams_reply_prefix(my_rt_member_id) + struct.pack("<I", status)
    if status != 0:
        return out
    t = team or {}
    out += struct.pack("<iI", t.get("team_id", 0), t.get("u1554", 0))
    out += b"".join(lp_string(t.get(k, "")) for k in ("name", "tag", "motto", "description"))
    if join:
        out += struct.pack("<i", t.get("leader_member_id", -1))
    return out + struct.pack("<I", int(bool(t.get("is_private", False))))


def parse_rt_edit_team_request(data: bytes) -> dict:
    """10682 (0xfb2aec, info tab edits): header, u32 team_id, lp description, lp motto, bool32 is_private."""
    me, local, off = race_teams_parse_header(data)
    (team_id,) = struct.unpack_from("<i", data, off)
    desc, off = _read_lp(data, off + 4)
    motto, off = _read_lp(data, off)
    (priv,) = struct.unpack_from("<I", data, off)
    return {"my_rt_member_id": me, "rt_local": local, "team_id": team_id, "description": desc,
            "motto": motto, "is_private": bool(priv)}


# ---- request headers and authentication (NETWORKING_ANALYSIS §8.21) ------------------------------------
#
# Every CC_Sync.php POST starts with a header written by the client. Two shapes exist:
#   * batched sync (SyncManagerV34 PackBlobHeader 0x1d04438):
#       u32 0x22, u32 id_a, u32 id_b, u32 id_c, lp s0,
#       u32 n, n x (u32 tag, lp value)          [tags seen: 0, 1, 3, 6, 4, 5]
#       lp s1, lp s2, lp s3,
#       then the auth extension written by the active auth manager (federated manager slot 3, 0x1d0095c):
#       u32 3, u32 member_id, lp token
#     followed by sub-sync records to the end of the body.
#   * authentication (FederatedManager 0x1d00364, header 0x1d00f38):
#       u32 0x22, u32 id_a, u32 id_b, u32 id_c, 7 x lp,
#       u32 auth_state, u32 member_id, u32 n, n x (u32 index, 4 x lp), u32 flag
# Field meanings beyond those named are UNKNOWN; identity strings may contain platform account data and
# must not be logged or stored by a replacement service.

PROTOCOL_VERSION = 0x22
AUTH_STATES = ["LEGACY", "INITIATE", "AUTHENTICATE_SUCCESS", "AUTHENTICATED", "REAUTHENTICATE",
               "MEMBER_CONFLICT", "DEVICE_CONFLICT", "SOCIAL_AUTH_CHANGED", "REAUTHENTICATE_STRICT"]


class _Reader:
    def __init__(self, data: bytes, off: int = 0):
        self.d, self.o = data, off

    def u32(self) -> int:
        if self.o + 4 > len(self.d):
            raise ValueError("truncated u32")
        (v,) = struct.unpack_from("<I", self.d, self.o)
        self.o += 4
        return v

    def lp(self) -> bytes:
        n = self.u32()
        if n > len(self.d) - self.o:
            raise ValueError("truncated string")
        v = self.d[self.o:self.o + n]
        self.o += n
        return v


def parse_sync_request(body: bytes, known_types: set[int] | None = None) -> dict:
    """Parse an unwrapped batched sync request. Raises ValueError if it is not one."""
    r = _Reader(body)
    if r.u32() != PROTOCOL_VERSION:
        raise ValueError("not protocol 0x22")
    ids = (r.u32(), r.u32(), r.u32())
    s0 = r.lp()
    n = r.u32()
    if n > 64:
        raise ValueError("implausible tag count")
    tags = [(r.u32(), r.lp()) for _ in range(n)]
    tail = (r.lp(), r.lp(), r.lp())
    kind = r.u32()
    legacy_slots, legacy_value = [], None
    if kind == 3:
        # cc::auth federated manager (0x1d0095c): u32 3, u32 member_id, lp token
        member_id = r.u32()
        token = r.lp()
    elif kind == 0:
        # cc::auth::LegacyManager slot 3 (0x1cfb554), used before the client has authenticated:
        # u32 0, u32 n, n x (u32 index, 4 x lp), u32 value (LegacyManager +0x580).
        # Verified on 10/10 recorded requests of a fresh install (RUNTIME_TEST_PLAN §9 run 12): five empty slots
        # (indices 0, 12, 6, 3, 13) and value 0xffffffff. Field meanings UNKNOWN.
        n_slots = r.u32()
        if n_slots > 64:
            raise ValueError("implausible legacy slot count")
        legacy_slots = [(r.u32(), [r.lp() for _ in range(4)]) for _ in range(n_slots)]
        legacy_value = r.u32()
        member_id, token = 0, b""
    else:
        raise ValueError(f"unexpected auth extension kind {kind}")
    subs = parse_subsyncs(body, r.o)
    if known_types is not None and any(t not in known_types for t, _, _ in subs):
        raise ValueError("unknown sub-sync type in batch")
    return {"ids": ids, "s0": s0, "tags": tags, "tail": tail, "auth_kind": kind,
            "member_id": member_id, "token": token.decode("utf-8", "replace"), "subsyncs": subs,
            "legacy_slots": legacy_slots, "legacy_value": legacy_value}


def build_sync_request(subsyncs: list[tuple[int, int, bytes]], member_id: int, token: str,
                       ids=(0, 0, 0), s0: str = "", tags=((0, ""),), tail=("", "", "")) -> bytes:
    """Inverse of parse_sync_request (unwrapped). For tests and tooling."""
    out = struct.pack("<IIII", PROTOCOL_VERSION, *ids) + lp_string(s0) + struct.pack("<I", len(tags))
    out += b"".join(struct.pack("<I", k) + lp_string(v) for k, v in tags)
    out += b"".join(lp_string(s) for s in tail)
    out += struct.pack("<II", 3, member_id) + lp_string(token)
    return out + b"".join(pack_subsync(t, p, d) for t, p, d in subsyncs)


def parse_auth_request(body: bytes) -> dict:
    """Parse an unwrapped authentication request; it must consume the whole body."""
    r = _Reader(body)
    if r.u32() != PROTOCOL_VERSION:
        raise ValueError("not protocol 0x22")
    ids = (r.u32(), r.u32(), r.u32())
    strings = [r.lp() for _ in range(7)]
    state = r.u32()
    member_id = r.u32()
    n = r.u32()
    if n > 64:
        raise ValueError("implausible identity count")
    identities = [(r.u32(), [r.lp() for _ in range(4)]) for _ in range(n)]
    flag = r.u32()
    if r.o != len(body):
        raise ValueError("trailing bytes after auth request")
    return {"ids": ids, "strings": strings, "state": state, "member_id": member_id,
            "identities": identities, "flag": flag}


def build_auth_request(state: int, member_id: int, ids=(0, 0, 0), strings=("",) * 7,
                       identities=(), flag: int = 0) -> bytes:
    """Inverse of parse_auth_request (unwrapped). For tests and tooling."""
    out = struct.pack("<IIII", PROTOCOL_VERSION, *ids) + b"".join(lp_string(s) for s in strings)
    out += struct.pack("<III", state, member_id, len(identities))
    for idx, four in identities:
        out += struct.pack("<I", idx) + b"".join(lp_string(s) for s in four)
    return out + struct.pack("<I", flag)


def auth_success_reply(member_id: int, token: str, token_timeout_s: int, value: int = 0,
                       developer: bool = False, u_a: int = 0, u_b: int = 0, flag_c: bool = False) -> bytes:
    """Authentication reply, success path (FederatedManager::AuthenticationCallback 0x1d0131c), before boxing:
    u32 ok (1), u32 value (to the same sub-object as the sync reply value; [likely] server time),
    u32 new_state (2 = AUTHENTICATE_SUCCESS), u32 member_id, bool32 is_developer,
    u32 u_a (Cloudcell vt+0x150 -> +0x18), u32 u_b (vt+0x140 -> +0xe0), bool32 flag_c, lp token,
    u32 token timeout in seconds (expiry = now + timeout). The client then moves to AUTHENTICATED (3).
    u_a, u_b and flag_c are UNKNOWN; 0 is a guess, not verified."""
    return (struct.pack("<IIIII", 1, value, 2, member_id, int(developer))
            + struct.pack("<III", u_a, u_b, int(flag_c)) + lp_string(token)
            + struct.pack("<I", token_timeout_s))


def auth_failure_reply() -> bytes:
    """u32 0: the client clears its pending request and sets REAUTHENTICATE_STRICT (8)."""
    return struct.pack("<I", 0)


SUBSYNC_FILE_MANAGER = (13, 448)


def parse_file_manager_request(data: bytes) -> list[tuple[str, int]]:
    """cc::FileManager sync request (0x1c73bf8): no count; for every file the client knows,
    lp name, u32 version (file record +0x20)."""
    off, out = 0, []
    while off < len(data):
        name, off = _read_lp(data, off)
        (ver,) = struct.unpack_from("<I", data, off)
        off += 4
        out.append((name, ver))
    return out


def file_manager_request(files: list[tuple[str, int]]) -> bytes:
    return b"".join(lp_string(n) + struct.pack("<I", v) for n, v in files)


def file_manager_response(updates: list[tuple[bool, str, int, bytes]], deletes: list[str] = ()) -> bytes:
    """cc::FileManager sync reply (0x1c73da0). An empty part means "no change".
    u32 n, n x (bool32 is_directory, lp name, u32 version, [only for files: u32 size, bytes]) -- each written
    through the FileManager file API and logged "new: <name>"; then u32 m, m x lp name -- deleted ("del: <name>")."""
    out = struct.pack("<I", len(updates))
    for is_dir, name, ver, payload in updates:
        out += struct.pack("<I", int(bool(is_dir))) + lp_string(name) + struct.pack("<I", ver)
        if not is_dir:
            out += struct.pack("<I", len(payload)) + payload
    out += struct.pack("<I", len(deletes)) + b"".join(lp_string(n) for n in deletes)
    return out


def parse_file_manager_response(data: bytes) -> tuple[list[tuple[bool, str, int, bytes]], list[str]]:
    (n,) = struct.unpack_from("<I", data)
    off, ups = 4, []
    for _ in range(n):
        (is_dir,) = struct.unpack_from("<I", data, off)
        name, off = _read_lp(data, off + 4)
        (ver,) = struct.unpack_from("<I", data, off)
        off += 4
        payload = b""
        if not is_dir:
            (sz,) = struct.unpack_from("<I", data, off)
            payload = data[off + 4: off + 4 + sz]
            off += 4 + sz
        ups.append((bool(is_dir), name, ver, payload))
    (m,) = struct.unpack_from("<I", data, off)
    off += 4
    dels = []
    for _ in range(m):
        name, off = _read_lp(data, off)
        dels.append(name)
    return ups, dels


SUBSYNC_GAME_CONFIG = (10631, 5245)


def game_config_response(values: dict[int, str]) -> bytes:
    """GameConfigManager sync reply (handler 0x1cee7c8 -> 0x1cee984): u32 n, n x (u32 config_id, lp value).
    Each pair is stored through the manager's setter ("CC: Updated GameConfig '%d' -> %s")."""
    items = sorted(values.items())
    return struct.pack("<I", len(items)) + b"".join(struct.pack("<I", k) + lp_string(v) for k, v in items)


def parse_game_config_response(data: bytes) -> dict[int, str]:
    (n,) = struct.unpack_from("<I", data)
    off, out = 4, {}
    for _ in range(n):
        (cid,) = struct.unpack_from("<I", data, off)
        out[cid], off = _read_lp(data, off + 4)
    return out


def wrap_request(body: bytes, seed: int | None = None) -> bytes:
    """What the client sends: Box(Box(body, ZLIB), XOR)."""
    return box(box(body, ZLIB), XOR, seed)


def unwrap(blob: bytes) -> bytes:
    """Inverse of wrap_request (the client applies UnboxData twice)."""
    return unbox(unbox(blob))
