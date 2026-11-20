# RETR0 preservation toolkit: audit and stage tracker

Scope (owner request, 2026-11-20): server gifts, save/profile inspection and backup, an in-game debug menu opened by
four taps on a screen corner, and later a desktop admin tool. This file is the Stage 1 audit and the tracker for the
stages after it. Evidence lives in the referenced documents; nothing here is new reverse engineering unless marked.

## Stage tracker

| Stage | Status |
|---|---|
| 1 Audit | DONE (this file, 2026-11-20) |
| 2 Gift re-test (16 Gold, product 10051) | **DONE, works** (run 32, STORE_PRESERVATION_GRANTS.md SP-16): server fix = gift kind 2 |
| 3 Gift expansion (R$, M$, other reward types, cars) | R$/M$ **DONE, work** as kind-0 gifts (run 33, SP-17); cars and other reward types NOT STARTED |
| 4 Save/profile investigation | PARTLY DONE earlier (format fully known, SV-01..SV-27); currency editing BLOCKED on an owner decision (D1) |
| 5 Save backup/restore | NOT STARTED (game has its own local backup cheat, see below) |
| 6 Corner-tap gesture | NOT STARTED |
| 7-11 Debug menu and features | NOT STARTED; approach depends on D2 |
| 12 Docs | ongoing |
| Desktop admin app | DEFERRED until 2-6 are verified (owner instruction) |

## 1. Current implementation

**Server gifts (`06_RECONSTRUCTION/BACKEND/local_service/retr0_local_service.py`):**
- `Store.queue_gift / pending_gifts / claim_gifts` (lines ~126-156): one **global** queue in
  `runtime/sync_data/state.json` (`gifts.pending`, `gifts.claimed`, `gifts.held`, `next_id`). Not per player.
- `Service._fetch_gifts` answers sub-sync **10480/5610** with `u32 count`, then per gift `u32 gift_id, u32 product_id`
  and the catalogue metadata string three times (which string the client reads is not established).
- `Service._claim_gifts` handles **10481** (ack) and moves gifts to `claimed`. SP-12: with a game listener present the
  client never sends 10481, so pending gifts are re-offered every session; the client skips gift ids it already holds.
- `Service.grant(product_id)`: allow-list = currency packages from the owner's store catalogue (seed file 12) of type
  `type:wrench` (Gold), `type:money` (R$), `type:mdollars` (M$). Amounts come only from the catalogue.
- Admin endpoint `POST /retr0/admin/gift?product=<id>` on 127.0.0.1:8781: rejects non-loopback callers, no token.
  The emulator cannot reach it: the CDN service forwards only `CC_Sync.php` and `/retr0/cloudsave/`
  (`config/rules_cdn_sync.json`). No list/remove/history endpoints.
- State now: `pending` empty, two **held** gifts (ids 1 and 2, both 10051 = 16 Gold) from the stalled tests;
  `devices`/`tokens` empty (the game uses guest/legacy auth and sends its own member id).
- The game asks for gifts (10480) **twice per session** (`runtime/sync.log`, two batches), matching the duplicate
  delivery noted in SP-11.

**Client gift handling (STORE_PRESERVATION_GRANTS.md SP-08..SP-12):** 10480 reply handler `0x1d1ad0c` builds
`cc::AdHocGift` objects (`0x1d1b448`); `0x12ed440` stores new gifts as unclaimed offerwall rewards and saves;
`BuyCarBar` (`0xd4d6a0`) shows the gift notification; `CLAIM_OFFERWALL_REWARD` (`0xd4f56c`) calls `0x12eda84`, which
parses the string with the store parser and awards **reward type 3 only** through `MTXManager` `0xb879fc(reward, 0, 1)`
(the non-purchase path also used by the working store grants, SP-13..SP-15).

**Products (SP-06, from the owner's seed data):** Gold `type:wrench` 10051-10056 = 16/42/87/183/476/1019 (smallest:
**10051 = 16 Gold**); R$ `type:money` 10045-10050 = 50k/140k/300k/700k/2M/5M; M$ `type:mdollars` 10461-10466 =
45k/115k/250k/520k/1.35M/3M. 33 catalogue products are `type:adhoc`. Car products: not yet identified.

**Player identification:** every sync request carries the client's own member id; the server echoes it in the reply
header (NW-93). That is the only per-player identifier available. One emulator = one member today.

**Save system (SAVE_SYSTEM_ANALYSIS.md SV-01..SV-27):** files in `files/doc/*.2.dat` (+ `.bak` in `.depot`), fixed
64-byte XOR obfuscation, big-endian header, typed name -> id -> value tables; a clean-room codec re-serialises all 9
real files byte-identically (SV-24). Currency and reward values are stored as protected `[EHV]`/`[H]` pairs (SV-22).
Local save does not depend on the cloud (SV-17). Tools: `SCRIPTS/save_format_check.py`, `save_decode.py` (structure).

**Built-in developer tools (new, 2026-11-20, from strings of arm64 libRealRacing3.so):**
- `FrontEnd2::MainMenuCheatScreen` (`MainMenuCheatScreen.cpp`, `MainMenuCheats.cpp`) with **303** named cheats in
  categories, e.g. Character (24: "Give gold:", "Give money:", "Give XP", "Own All Cars", "Unlock All Tracks",
  "Save game", "Validate user data", "Clear local save"), Car (22: "Repair Car", "Upgrade all cars", "Remove Car"),
  Career (8: "Win tapped event", "Bypass Locked Series"), Customisation (19), Cloudcell (23), Store, Sales, Time.
- A numeric/text cheat input dialog in Java (`MainActivity.showCheatInput` -> native `onCheatInputDone`).
- `FrontEnd2::CheatIntercept`, `GuiCheatProtector`, pause-menu tweak/cheat buttons (NW-49), CamTweaks, Dear ImGui
  debug windows, debug layouts (`DebugInfoScreen.gui`, `DebugRaceSelectScreen.gui`, `CarDebugViewer.gui`, ...),
  "Backup Current Save Locally" / "Restore Previous Local Backup" (SV-04).
- How the cheat screen is opened and gated: UNKNOWN (next investigation for D2).

## 2-3. Relevant files and functions
Server: `retr0_local_service.py` (above), `cloudcell_codec.py` (`sync_response_body`, member header),
`recorder_server.py`, `D:\RETR0_Server\config\rules_cdn_sync.json`, `client.ps1`.
Client: `store_grant_patch.S` / `retr0_redirect.c` (code cave, 79 bytes free), addresses above.

## 4. Known bugs and open problems
- Gift stall (SP-11/SP-12): runs 16 and 20 froze 35-60 s after a gift (~250k-800k `UnpackData` asserts). Likely cause:
  the missing sync member header (fixed in NW-93), **not re-tested**. The gift string layout is also unverified.
- Gifts are not per player and are re-offered every session (no 10481 from the game).
- Code cave nearly full (2,281 / 2,360 bytes): new native features need another cave or a larger design.
- In-place client install does not survive an emulator reboot (run 30).

## 5. Existing tests
`08_TESTING/test_local_service.py` (auth, sync layout, cloud save, file manager, HTTPS, end-to-end): **no gift or
grant tests**. 59 tests pass.

## 6. Blockers and owner decisions
- **D1 - local currency editing conflicts with standing rules.** The owner's earlier constraints say: do not decode the
  protected `[EHV]`/`[H]` currency values, and no client-only balance edits (amounts decided by the server). Editing
  Gold/R$/M$ in the save, or through a debug-menu currency editor, contradicts both. Options: (a) keep the rules:
  currency only through server gifts/grants; (b) allow the game's **own** cheats ("Give gold:", "Give money:"), which
  credit through the game's code without us decoding anything, in a clearly marked debug build; (c) lift the rule.
- **D2 - debug menu approach.** Reusing the built-in `MainMenuCheatScreen` (already has currency, car, career, save
  and validation tools, uses the game's own UI) versus building a new RETR0 overlay. Reuse is far smaller and safer;
  the corner-tap gesture would then just open it.

**Decision (owner, 2026-11-20): D1 = option (b), D2 = reuse.** Currency changes in the debug menu use the game's
own cheats ("Give gold:", "Give money:" and similar), in a clearly marked RETR0 debug build. The protected save values
stay undecoded, and the save editor stays read-only for currency. Server gifts remain the preservation path.

## 7. Recommended order
1. Stage 2: re-test one 16 Gold gift (back up saves + server state first; one gift; watch logcat with a large buffer).
2. Make gifts per member and add list/remove/history endpoints with tests (needs no client change).
3. Find how `MainMenuCheatScreen` is opened and gated (D2), then decide the gesture/patch.
4. R$/M$ gifts, then car reward types (claim path accepts type 3 only: cars likely need more than a gift).
5. Save backup/restore tooling around the existing codec (copies only, never the original).
6. Desktop admin app last.
