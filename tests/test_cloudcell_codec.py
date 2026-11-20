"""Tests for the clean-room CloudCell codec (06_RECONSTRUCTION/BACKEND/cloudcell_codec).

These check internal consistency and the documented arithmetic only. Wire compatibility with the
original client/server is UNVERIFIED (no captured traffic available).
"""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "services" / "cloudcell_codec"))
import cloudcell_codec as cc  # noqa: E402


def test_checksum_documented_arithmetic():
    # group (2, 3, 4, 2) -> 2*3*4/2 = 12 ; partial group (5, 6) -> 30
    assert cc.checksum(bytes([2, 3, 4, 2, 5, 6])) == 42


def test_checksum_signed_bytes_and_truncation():
    # (-1, 7, 1, 2): -7 / 2 truncates toward zero -> -3 (wraps to 0xFFFFFFFD)
    assert cc.checksum(bytes([0xFF, 7, 1, 2])) == (-3) & 0xFFFFFFFF


def test_checksum_zero_divisor_ignored():
    assert cc.checksum(bytes([2, 3, 4, 0])) == 24


@pytest.mark.parametrize("box_type", [cc.PLAIN, cc.ZLIB, cc.XOR])
def test_box_roundtrip(box_type):
    data = bytes(range(256)) * 3
    assert cc.unbox(cc.box(data, box_type, seed=0x5A)) == data


def test_box_header_layout():
    blob = cc.box(b"abc", cc.PLAIN)
    stored, box_type = struct.unpack_from("<II", blob)
    assert box_type == cc.PLAIN and blob[8:] == b"abc"
    assert stored == cc.checksum(blob[8:])


def test_xor_rolling_key():
    blob = cc.box(bytes(4), cc.XOR, seed=250)
    assert blob[8] == 250
    assert blob[9:] == bytes([250, 253, 0, 3])          # seed, seed+3, seed+6 (mod 256), ...


def test_request_wrap_unwrap():
    body = struct.pack("<II", 0x22, 7) + b"\x05\x00\x00\x00hello"
    assert cc.unwrap(cc.wrap_request(body, seed=17)) == body


def test_subsync_record_layout():
    rec = cc.pack_subsync(10768, 0, b"")
    assert rec == struct.pack("<IIII", 10768, 0, 0, 0)


def test_subsync_batch_roundtrip():
    recs = [(10452, 6, b"\x01\x02"), (10768, 0, b""), (10448, 5440, b"x" * 300)]
    data = b"".join(cc.pack_subsync(*r) for r in recs)
    assert cc.parse_subsyncs(data) == recs


def test_subsync_malformed_rejected():
    bad = struct.pack("<IIII", 1, 2, 7, 0)          # reserved field must be 0
    with pytest.raises(ValueError):
        cc.parse_subsyncs(bad)


def test_response_parts_layout():
    assert cc.pack_response_parts([b"ab", b""]) == b"\x02\x00\x00\x00ab\x00\x00\x00\x00"


def test_player_rank_payloads():
    assert cc.player_rank_request(42) == struct.pack("<I", 42)
    assert cc.player_rank_response(17) == struct.pack("<I", 17)


def test_pvp_servers_count_is_twice_entries():
    data = cc.pvp_servers_response([("127.0.0.1", 7777), ("localhost", 7778)])
    assert struct.unpack_from("<I", data)[0] == 4
    assert cc.parse_pvp_servers_response(data) == [("127.0.0.1", 7777), ("localhost", 7778)]


def test_garage_response_layout():
    data = cc.garage_response("hdr", [(123, 7, b"BLOB")])
    assert data == (struct.pack("<I", 3) + b"hdr" + struct.pack("<I", 1)
                    + struct.pack("<II", 123, 7) + struct.pack("<I", 4) + b"BLOB")


def test_upload_vehicles_request_parse():
    data = (struct.pack("<II", 1, 1) + struct.pack("<I", 42) + struct.pack("<I", 3) + b"XYZ"
            + struct.pack("<II", 0, 1))
    assert cc.parse_upload_vehicles_request(data) == (1, [(42, b"XYZ", 0, 1)])
    with pytest.raises(ValueError):
        cc.parse_upload_vehicles_request(data + b"\x00")


def test_upload_vehicles_response():
    assert cc.upload_vehicles_response(None) == struct.pack("<I", 0)
    assert cc.upload_vehicles_response([5, 6]) == struct.pack("<IIII", 1, 2, 5, 6)


def test_customisation_info_payloads():
    assert cc.customisation_info_request([(1, 2)]) == struct.pack("<III", 1, 1, 2)
    data = cc.customisation_info_response([(1, 2, True, 3, 4, 5, False, "ab", 6)])
    assert data == (struct.pack("<I", 1) + struct.pack("<IIIIIII", 1, 2, 1, 3, 4, 5, 0)
                    + struct.pack("<I", 2) + b"ab" + struct.pack("<I", 6))


def test_leaderboard_request_layout():
    assert cc.leaderboard_request(7, [1, 2], 0, 10, 20, 0) == struct.pack("<8I", 7, 2, 1, 2, 0, 10, 20, 0)


def test_leaderboard_core_and_entries():
    core = cc.lb_core("A", 5, "", "x", b"\x01\x02", "")
    assert core == (struct.pack("<I", 1) + b"A" + struct.pack("<II", 5, 0) + struct.pack("<I", 1) + b"x"
                    + struct.pack("<I", 2) + b"\x01\x02" + struct.pack("<I", 0))
    e = cc.leaderboard_entry_main(core, "", 1, 1.5, "", 2, 3, [9], 4)
    assert e == core + struct.pack("<II", 0, 1) + struct.pack("<f", 1.5) + struct.pack("<IIIIII", 0, 2, 3, 1, 9, 4)
    r = cc.leaderboard_response(0, 0, 0, [e])
    assert r[:16] == struct.pack("<IIII", 0, 0, 0, 1) and r[16:] == e
    assert cc.leaderboard_entry_short(core, 1, 2, 3) == core + struct.pack("<III", 1, 2, 3)


def test_leaderboard_group_and_validate():
    assert cc.leaderboard_group_response(1, 2, [("g", 3, 4, 5)]) == (
        struct.pack("<III", 1, 2, 1) + struct.pack("<I", 1) + b"g" + struct.pack("<III", 3, 4, 5))
    assert cc.leaderboard_validate_response(True, 7) == struct.pack("<III", 1, 7, 0)


def test_sales_and_member_status():
    assert cc.sales_request() == b""
    assert cc.mp_member_status_request(9, 0x101) == struct.pack("<II", 9, 1)


def test_mp_start_match_response():
    data = cc.mp_start_match_response(1, 2, (3, 4, 5, 6), 7, 8, [(100, 5, b"CC", 0), (101, 6, b"", 0)])
    head = struct.pack("<11I", 1, 2, 3, 4, 5, 6, 7, 8, 2, 100, 5)
    assert data == head + struct.pack("<I", 2) + b"CC" + struct.pack("<I", 0) + struct.pack("<III", 101, 6, 0)


def test_saved_game_payloads():
    assert cc.download_saved_game_request(50) == struct.pack("<I", 50)
    data = cc.saved_game_list_response([(7, 0, "d", "http://localhost/s7")])
    assert data == (struct.pack("<III", 1, 7, 0) + struct.pack("<I", 1) + b"d"
                    + struct.pack("<I", 19) + b"http://localhost/s7")


def test_cloud_save_payloads():
    assert cc.gsm_upload_request(0x101, "a", "") == struct.pack("<II", 1, 1) + b"a" + struct.pack("<I", 0)
    assert cc.gsm_upload_response("k", "u") == struct.pack("<II", 0, 1) + b"k" + struct.pack("<I", 1) + b"u"
    assert cc.gsm_download_response(True, b"SAVE") == struct.pack("<II", 1, 4) + b"SAVE"
    assert cc.gsm_validate_response(False) == struct.pack("<I", 0)


def test_sync_response_body_and_data_request():
    body = cc.sync_response_body([b"\x01\x00\x00\x00", b""], value=5, trailing_ids=[9])
    assert body == (struct.pack("<II", 1, 5) + struct.pack("<IIIII", 0, 0, 0, 0, 0)
                    + cc.pack_response_parts([b"\x01\x00\x00\x00", b""]) + struct.pack("<II", 1, 9))
    # member header (LegacyManager 0x1cfb784): member id, developer, device id, u_b, flag
    hdr = cc.sync_response_body([], member_id=42, device_id=7)
    assert hdr == struct.pack("<II", 1, 0) + struct.pack("<IIIII", 42, 0, 7, 0, 0)
    assert cc.sync_response_body([], ok=False) == struct.pack("<I", 0)
    assert cc.unwrap(cc.wrap_request(body, seed=3)) == body
    assert cc.data_request_request(0) == struct.pack("<I", 0)
    assert cc.data_request_request(2, 7) == struct.pack("<II", 2, 7)
    assert cc.data_request_response(True, 1, 2) == struct.pack("<III", 1, 1, 2)


def test_direct_subsync_table_consistent_with_decoded():
    import subsync_table as t
    assert len(t.DIRECT_SUBSYNCS) == 80
    for key in (cc.SUBSYNC_GSM_LIST, cc.SUBSYNC_GSM_DOWNLOAD, cc.SUBSYNC_GSM_UPLOAD_REQUEST,
                cc.SUBSYNC_GSM_UPLOAD_INLINE, cc.SUBSYNC_GSM_VALIDATE):
        assert key in t.DIRECT_SUBSYNCS
    assert t.DIRECT_SUBSYNCS[cc.SUBSYNC_GSM_UPLOAD_REQUEST]["request"] == "u32 lp lp"   # matches manual decode
    assert (1, 1) not in t.DIRECT_SUBSYNCS                                            # false positive removed


def test_tamper_detected():
    blob = bytearray(cc.wrap_request(b"payload", seed=1))
    blob[-1] ^= 0xFF
    with pytest.raises(ValueError):
        cc.unwrap(bytes(blob))


def test_subsync_features_cover_table_and_use_valid_labels():
    import subsync_features as f
    import subsync_table as t
    assert set(f.SUBSYNC_FEATURES) == set(t.DIRECT_SUBSYNCS)
    labels = {"CONFIRMED", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}
    for key, v in f.SUBSYNC_FEATURES.items():
        assert v["confidence"] in labels, key
        assert v["owner"] and v["feature"], key
    # every Race Teams request whose layout starts with two u32s carries the shared header
    for key in f.RACE_TEAMS_PREFIX_TYPES:
        req = {**f.SUBSYNC_FEATURES, **f.RACE_TEAMS_HELPER_SUBSYNCS}[key].get("request")
        if req:
            assert req[0] == "u32 my_rt_member_id", key


def test_server_variables_roundtrip():
    body = cc.server_variables_response({"Rookie_Enable": "0", "RRTV_Enabled": "1"})
    assert body[:4] == struct.pack("<I", 2)
    assert cc.parse_server_variables_response(body) == [("Rookie_Enable", "0"), ("RRTV_Enabled", "1")]
    assert cc.parse_server_variables_response(cc.server_variables_response([])) == []


def test_report_abuse_and_record_transaction():
    assert cc.report_abuse_request(7, 42) == struct.pack("<II", 7, 42)
    body = (cc.lp_string("GPA.1") + cc.lp_string("tok") + cc.lp_string("sku.gold") + struct.pack("<I", 1700000000)
            + cc.lp_string(""))
    assert cc.parse_record_transaction_request(body) == {
        "transaction_id": "GPA.1", "receipt": "tok", "item_sku": "sku.gold", "timestamp": 1700000000, "extra": ""}


def test_race_teams_header():
    req = struct.pack("<III", 99, 5, 1234)
    assert cc.race_teams_parse_header(req) == (99, 5, 8)
    assert cc.race_teams_reply_prefix(100) == struct.pack("<I", 100)


def test_race_teams_create_join_edit():
    import subsync_features as f
    assert len(f.RACE_TEAMS_HELPER_SUBSYNCS) == 7
    assert not set(f.RACE_TEAMS_HELPER_SUBSYNCS) & set(f.SUBSYNC_FEATURES)
    assert f.RT_STATUS[0] == "success" and f.RT_STATUS[9] == "locked"
    req = (struct.pack("<III", 77, 5, 0) + cc.lp_string("Speed Demons") + cc.lp_string("SPD")
           + cc.lp_string("go fast") + cc.lp_string("we race") + struct.pack("<IIi", 1, 3, -5))
    p = cc.parse_rt_create_request(req)
    assert (p["my_rt_member_id"], p["name"], p["tag"], p["is_private"], p["utc_offset_hours"]) == (77, "Speed Demons", "SPD", True, -5)
    team = {"team_id": 12, "name": "Speed Demons", "tag": "SPD", "motto": "m", "description": "d",
            "leader_member_id": 3, "is_private": False}
    create = cc.rt_team_reply(77, 0, team)
    join = cc.rt_team_reply(77, 0, team, join=True)
    assert len(join) == len(create) + 4
    assert cc.rt_team_reply(77, cc.RT_CREATE_TAG_TAKEN) == struct.pack("<iI", 77, 2)
    edit = struct.pack("<IIi", 77, 5, 12) + cc.lp_string("d") + cc.lp_string("m") + struct.pack("<I", 0)
    assert cc.parse_rt_edit_team_request(edit) == {"my_rt_member_id": 77, "rt_local": 5, "team_id": 12,
                                                  "description": "d", "motto": "m", "is_private": False}


def test_sync_request_legacy_extension():
    """kind 0 (cc::auth::LegacyManager 0x1cfb554): u32 0, u32 n, n x (u32 index, 4 x lp), u32 value, then sub-syncs.
    Synthetic body with the shape seen on a fresh install (run 12); no recorded data is embedded."""
    head = struct.pack("<IIII", cc.PROTOCOL_VERSION, 37, 7469, 0) + cc.lp_string("com.example.pkg")
    head += struct.pack("<I", 2) + struct.pack("<I", 0) + cc.lp_string("x") + struct.pack("<I", 1) + cc.lp_string("y")
    head += cc.lp_string("Android") + cc.lp_string("model") + cc.lp_string("14")
    ext = struct.pack("<II", 0, 2)
    for idx in (0, 12):
        ext += struct.pack("<I", idx) + b"".join(cc.lp_string("") for _ in range(4))
    ext += struct.pack("<I", 0xFFFFFFFF)
    subs = cc.pack_subsync(13, 448, b"abc") + cc.pack_subsync(10631, 5245, b"")
    req = cc.parse_sync_request(head + ext + subs)
    assert req["auth_kind"] == 0 and req["member_id"] == 0 and req["token"] == ""
    assert [i for i, _ in req["legacy_slots"]] == [0, 12] and req["legacy_value"] == 0xFFFFFFFF
    assert req["subsyncs"] == [(13, 448, b"abc"), (10631, 5245, b"")]
    # kind 3 still works and unknown kinds are still rejected
    assert cc.parse_sync_request(cc.build_sync_request([(2, 4559, b"z")], 5, "tok"))["member_id"] == 5
    bad = head + struct.pack("<I", 9)
    with pytest.raises(ValueError):
        cc.parse_sync_request(bad)
