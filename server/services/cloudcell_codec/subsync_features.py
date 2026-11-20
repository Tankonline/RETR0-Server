"""Project RETR0 - feature attribution and field names for the directly queued CloudCell sub-syncs.

Companion to subsync_table.py (wire layouts). Evidence is static analysis of libRealRacing3.so 14.0.1
(arm64, function-recovered Ghidra working copy):
  * owner      : C++ class owning the sender, from RTTI vtables of the sender or its callers
                 (SCRIPTS/ghidra/RETR0_CallerContext.java -> direct_subsyncs/callers/callers.tsv),
                 or from assert source paths / log strings in the sender.
  * feature    : what the request is for, from caller strings (GAMETEXT ids, debug labels, telemetry
                 labels) and reply-handler strings. Wording is ours, not EA's.
  * confidence : CONFIRMED / HIGH / MEDIUM / LOW / UNKNOWN (project scale).
  * request / reply : field names aligned with the layout tokens. A name in [brackets] is an
                 inference; "?" means the value's meaning is unknown (source noted in NETWORKING_ANALYSIS.md
                 section 8.18). Fields not listed keep the token-only layout from subsync_table.py.

Race Teams (RaceTeamManager.cpp): see NETWORKING_ANALYSIS.md 8.19. Every request starts with
  u32 my_rt_member_id - global(0x1f6d5d8)->+0x1608. Every reply's FIRST u32 is stored back into this slot.
                   The client also uses the slot as "me" (decline-own-requests passes it as the member id;
                   the results tab compares list entries with it) and resets it to -1 on account change
                   (HIGH: local player's Race Teams member id).
  u32 rt_local   - 0xcd6c00(): global->+0x10500->+0x58->+0x58; only RaceTeamManager calls it (UNKNOWN).
  Some requests end with
  u32 g710_4     - *(global 0x1f6d710)+4 (UNKNOWN; also the only field of 10748)
  u32 utc_offset_hours - 0x14168bc(): (mktime(localtime) - mktime(gmtime)) / 3600 (CONFIRMED).
Team record kept by the client (global +0x1550..+0x15f8), filled by create/join/team-info replies:
  +0x1550 team_id, +0x1554 ? (0/1), +0x1558 leader_member_id [create sets it to my id; join takes it from
  the reply], +0x155c is_private, +0x1568 name, +0x1580 tag, +0x1598 motto, +0x15b0 description,
  +0x15f8 have_team (set to 1 by create and join).
"""

RT_HDR = ["u32 my_rt_member_id", "u32 rt_local"]

SUBSYNC_FEATURES = {
    # ---- CloudCell core managers ------------------------------------------------------------------------
    (2, 4559): {"owner": "cc::social::AchievementManager", "feature": "achievement list at Initialize", "confidence": "HIGH"},
    (20, 476): {"owner": "cc::social::AchievementManager", "feature": "achievement update/unlock batch", "confidence": "MEDIUM"},
    (10463, 10463): {"owner": "cc::social::AchievementManager", "feature": "empty-body achievement request", "confidence": "MEDIUM"},
    (11, 4494): {"owner": "cc::TextManager", "feature": "server text/strings at Initialize", "confidence": "HIGH"},
    (13, 448): {"owner": "cc::FileManager", "feature": "file list / file download", "confidence": "HIGH"},
    (68, 3281): {"owner": "cc::StatManager", "feature": "stat upload (session end / game session time)", "confidence": "HIGH"},
    (80, 1079): {"owner": "cc::PiracyManager", "feature": "piracy check (string)", "confidence": "HIGH"},
    (82, 1082): {"owner": "cc::PiracyManager", "feature": "piracy check follow-up", "confidence": "HIGH"},
    (10547, 4663): {"owner": "cc::BanningManager", "feature": "ban status", "confidence": "HIGH",
                    "reply": ["bool32 ?", "bool32 ?", "u32 ?", "u32 ?"]},
    (10631, 5245): {"owner": "cc::GameConfigManager", "feature": "game config fetch (empty body)", "confidence": "HIGH"},
    (10662, 5645): {"owner": "cc::CommunityEventManager", "feature": "community event query", "confidence": "HIGH"},
    (10663, 5646): {"owner": "cc::CommunityEventManager", "feature": "community event query", "confidence": "HIGH"},
    (10714, 6371): {"owner": "cc::auth::SimpleManager", "feature": "authentication finished report", "confidence": "HIGH"},
    (10716, 6255): {"owner": "cc::CustomerSupportManager", "feature": "customer-support records upload",
                    "confidence": "HIGH", "request": ["u32 count", "{ lp ?", "lp ?", "lp ? }"]},
    (10738, 6661): {"owner": "cc::social::MemberManager", "feature": "social sign-in (platform id / display name)", "confidence": "MEDIUM"},
    (10790, 7403): {"owner": "cc::VersionUpdateManager", "feature": "version update check", "confidence": "HIGH"},
    (10556, 4776): {"owner": "cc::social::SocialMedia", "feature": "friend list update (LoadFriendVectorCallback)", "confidence": "HIGH"},
    (10480, 5610): {"owner": "cc::GiftManager", "feature": "FetchAdHocGifts", "confidence": "CONFIRMED"},
    (10481, 1): {"owner": "cc::GiftManager", "feature": "gift claim/ack batch", "confidence": "MEDIUM"},
    (32, 2437): {"owner": "cc::social::twitter::TwitterManager", "feature": "LegacyMemberCheck", "confidence": "CONFIRMED"},
    (10444, 2437): {"owner": "cc::social::twitter::TwitterManager", "feature": "LegacyLogout", "confidence": "CONFIRMED"},
    (10445, 2437): {"owner": "cc::social::twitter::TwitterManager", "feature": "legacy Twitter request (string)", "confidence": "HIGH"},
    (10443, 4445): {"owner": "cc::social::twitter::TwitterManager", "feature": "Twitter sign-in (two strings)", "confidence": "HIGH"},
    # ---- GameSaveManager (decoded in NW-55..64) ---------------------------------------------------------
    (47, 7277): {"owner": "cc::GameSaveManager", "feature": "QueueDownloadList", "confidence": "CONFIRMED", "request": ["u32 1"]},
    (48, 809): {"owner": "cc::GameSaveManager", "feature": "QueueDownloadSync / QueueDirectDownload", "confidence": "CONFIRMED",
                "request": ["u32 save_id", "u32 0"]},
    (10555, 5757): {"owner": "cc::GameSaveManager", "feature": "QueueValidate", "confidence": "CONFIRMED"},
    (10660, 5638): {"owner": "cc::GameSaveManager", "feature": "upload: request PUT URL", "confidence": "CONFIRMED"},
    (22, 2816): {"owner": "cc::GameSaveManager", "feature": "upload: inline save", "confidence": "CONFIRMED"},
    (10661, 5639): {"owner": "cc::GameSaveManager", "feature": "upload follow-up (string, status<5)", "confidence": "HIGH"},
    # ---- Store / purchases ------------------------------------------------------------------------------
    (10704, 5986): {"owner": "NimbleMTX (CloudcellRecordTransaction)", "feature": "record a store transaction",
                    "confidence": "HIGH",
                    "request": ["lp transaction_id (GooglePlay: additionalInfo['orderId'])",
                                "lp receipt (GooglePlay: additionalInfo['token'])",
                                "lp item_sku", "u32 timestamp (int of NimbleMTXTransaction.getTimeStamp)", "lp ?"],
                    "reply": ["bool32 ?", "u32 ?"]},
    (10767, 7086): {"owner": "cc::NimbleStoreHandler", "feature": "VerifyNimblePurchaseDetails (purchaseData, receipt)",
                    "confidence": "HIGH"},
    (10632, 2369): {"owner": "FrontEnd2::SettingsMenu (promo entry)", "feature": "promo code redeem", "confidence": "HIGH",
                    "request": ["lp promo_code"]},
    (10609, 4901): {"owner": "TargetedSaleManager [by file order]", "feature": "targeted sales sync (debug 'Sync Sales')",
                    "confidence": "MEDIUM"},
    (10606, 4907): {"owner": "CC_Helpers (called from MainMenuManager)", "feature": "batch of (u32,u32,u8) items + flag", "confidence": "LOW"},
    # ---- Server variables / maintenance -----------------------------------------------------------------
    (10712, 4373): {"owner": "ServerVariableService", "feature": "server variables sync", "confidence": "HIGH",
                    "request": ["u32 ? (Cloudcell vtable +0x90 -> object vtable +0x1d8)"],
                    "reply": ["u32 count", "{ lp key", "lp value }"]},
    (10715, 3443): {"owner": "ServerMaintenanceService [likely]", "feature": "maintenance query", "confidence": "MEDIUM"},
    (10739, 4188): {"owner": "ServerMaintenanceService [likely]", "feature": "maintenance query (u32 list)", "confidence": "MEDIUM"},
    (10806, 7392): {"owner": "CloudcellService (Maintenance_KillSwitch path)", "feature": "maintenance / kill-switch status",
                    "confidence": "MEDIUM", "reply": ["u32 ?", "lp ?", "u32 ?"]},
    (10742, 6700): {"owner": "Cloudcell start-up (CC_SeedData path)", "feature": "start-up request (string)", "confidence": "MEDIUM"},
    (25, 519): {"owner": "app resume path (ndActivity RESUME SYSTEM)", "feature": "empty-body request on resume", "confidence": "MEDIUM"},
    # ---- Racing / results -------------------------------------------------------------------------------
    (10451, 4933): {"owner": "UploadResultTask", "feature": "race result upload (n x 17 u32 records)", "confidence": "HIGH"},
    (10694, 6061): {"owner": "UploadResultTask / TimeTrialMode", "feature": "time-trial ghost upload ('RR3 Time Trial Ghost')",
                    "confidence": "HIGH"},
    (10695, 5763): {"owner": "FileManager-area helper (time-trial ghost path)", "feature": "ghost file upload step", "confidence": "MEDIUM"},
    (10696, 5764): {"owner": "FileManager-area helper (time-trial ghost path)", "feature": "ghost file upload step", "confidence": "MEDIUM"},
    (10476, 5005): {"owner": "TimeTrialMode caller", "feature": "time-trial ghost download (reply carries bytes)", "confidence": "MEDIUM"},
    (10565, 2016): {"owner": "CC_Helpers (YourGarageScreen / race results BTN_REPORT)",
                    "feature": "Report Abuse: inappropriate customisation", "confidence": "HIGH",
                    "request": ["u32 reportee_member_id", "u32 reportee_car_id"]},
    (10785, 5070): {"owner": "OnlineMultiplayerSchedule", "feature": "online multiplayer schedule", "confidence": "HIGH"},
    # ---- RacerManager (friends / opponents) -------------------------------------------------------------
    (10472, 6146): {"owner": "RacerManager [by file order]", "feature": "friends list (friendsList.pld)", "confidence": "MEDIUM"},
    (10446, 2910): {"owner": "RacerManager::loadOpponents", "feature": "opponent list for a race", "confidence": "HIGH"},
    (10419, 3654): {"owner": "RacerManager / MainMenuCheatScreen", "feature": "opponent/save data fetch", "confidence": "LOW"},
    (10459, 1603): {"owner": "RacerManager [by file order]", "feature": "event-map friend data", "confidence": "MEDIUM"},
    (10458, 715): {"owner": "RacerManager [by file order]", "feature": "event result report (career event complete)", "confidence": "MEDIUM"},
    # ---- Front end / misc -------------------------------------------------------------------------------
    (10567, 6145): {"owner": "FrontEnd2::MainMenuCheatScreen", "feature": "debug: reconstruct save by CC id", "confidence": "HIGH"},
    (10733, 3792): {"owner": "FrontEnd2::MainMenuCheatScreen", "feature": "debug request", "confidence": "MEDIUM"},
    (10734, 3797): {"owner": "FrontEnd2::MainMenuCheatScreen", "feature": "debug request", "confidence": "MEDIUM"},
    (10735, 3977): {"owner": "SaveManager.cpp", "feature": "save-load step during loading", "confidence": "HIGH"},
    (10737, 4171): {"owner": "third-party ads area", "feature": "ads config (empty body)", "confidence": "LOW"},
    (10748, 5646): {"owner": "RealRacingTv2Banner (RRTV_Enabled)", "feature": "Real Racing TV query", "confidence": "MEDIUM",
                    "request": ["u32 g710_4"]},
    (10762, 4558): {"owner": "FrontEnd2::LtsSyncScreen", "feature": "limited-time-series sync", "confidence": "MEDIUM"},
    (10781, 5022): {"owner": "FrontEnd2::MainMenuManager", "feature": "usage-sharing opt-in", "confidence": "MEDIUM"},
    (10784, 5028): {"owner": "Load-from-cloud path", "feature": "missing-progress check (GAMETEXT_TTC_MISSING_PROGRESS)", "confidence": "MEDIUM"},
    (10796, 7625): {"owner": "FrontEnd2::RemoveAccountPopup", "feature": "account removal", "confidence": "HIGH", "reply": ["bool32 ok"]},
    (10797, 7092): {"owner": "FrontEnd2::MainMenuManager", "feature": "main-menu request (empty body)", "confidence": "LOW"},
    (10688, 2920): {"owner": "SettingsMenu-area code", "feature": "list of string pairs", "confidence": "LOW"},
    # ---- Race Teams (RaceTeamManager.cpp, BRACKETED-HIGH source attribution) ----------------------------
    (10669, 3616): {"owner": "RaceTeamManager", "feature": "team search (RaceTeamJoinPage)", "confidence": "HIGH",
                    "request": RT_HDR + ["u32 0", "u32 g710_4", "u32 utc_offset_hours", "lp search_text [likely]"],
                    "reply": ["u32 my_rt_member_id", "u32 count", "{ u32 ?", "lp lp lp lp ?", "bool32 ?", "u32 ?", "u32 ? }"]},
    (10670, 3607): {"owner": "RaceTeamManager", "feature": "create team (RaceTeamCreatePage)", "confidence": "HIGH",
                    "request": RT_HDR + ["u32 0", "lp name", "lp tag", "lp s3 (motto or description)", "lp s4 (the other one)",
                                         "bool32 is_private", "u32 g710_4", "u32 utc_offset_hours"],
                    "reply": ["u32 my_rt_member_id", "u32 status (0 ok, 1 name taken, 2 tag taken, 3 generic, 4 profanity)",
                              "if 0: u32 team_id", "u32 ? (+0x1554)", "lp name", "lp tag", "lp motto", "lp description",
                              "bool32 is_private"]},
    (10671, 3609): {"owner": "RaceTeamManager", "feature": "join team", "confidence": "HIGH",
                    "request": RT_HDR + ["u32 team_id", "bool32 ?"],
                    "reply": ["u32 my_rt_member_id", "u32 status (RT_STATUS)", "if 0: u32 team_id", "u32 ? (+0x1554)",
                              "lp name", "lp tag", "lp motto", "lp description", "u32 leader_member_id", "bool32 is_private"]},
    (10672, 2739): {"owner": "RaceTeamManager", "feature": "view a team (leaderboard team popup; 2 senders)", "confidence": "MEDIUM",
                    "request": RT_HDR + ["u32 ?", "u32 ?"]},
    (10673, 3645): {"owner": "RaceTeamManager", "feature": "Race Teams sync (hub)", "confidence": "HIGH", "request": RT_HDR,
                    "reply": ["u32 my_rt_member_id", "... (rest parsed by 0xfab7e0)"]},
    (10674, 2757): {"owner": "RaceTeamManager", "feature": "leave team (RaceTeamMembersTab)", "confidence": "HIGH",
                    "request": RT_HDR,
                    "reply": ["u32 my_rt_member_id", "u32 ?", "lp ?", "bool32 is_private", "u32 status (0 ok, 2 locked, else generic)"]},
    (10675, 4465): {"owner": "RaceTeamManager", "feature": "get team info (own team: -1, or a team id; 4 senders)", "confidence": "HIGH",
                    "request": RT_HDR + ["u32 team_id or -1"],
                    "reply": ["u32 my_rt_member_id", "... fills the team record (team_id, name, tag, motto, description, leader, is_private)"]},
    (10676, 6086): {"owner": "RaceTeamManager", "feature": "add contribution (score for team goal)", "confidence": "MEDIUM",
                    "request": RT_HDR + ["u32 ?"] * 12},
    (10678, 2804): {"owner": "RaceTeamManager", "feature": "team rewards (RaceTeamRewardsPage)", "confidence": "HIGH",
                    "request": RT_HDR + ["u32 team_id (+0x1550)", "u32 ? (+0x15cc)"]},
    (10680, 2820): {"owner": "RaceTeamManager", "feature": "request membership (-1, team id); variant (member id, -1)",
                    "confidence": "HIGH", "request": RT_HDR + ["u32 member_id or -1", "u32 team_id or -1", "bool32 ?"],
                    "reply": ["u32 my_rt_member_id", "u32 status (RT_STATUS)", "lp team_name ([szTeamName])"]},
    (10685, 2907): {"owner": "RaceTeamManager", "feature": "accept invite", "confidence": "HIGH", "request": RT_HDR},
    (10686, 3538): {"owner": "RaceTeamManager", "feature": "decline invite (header only) / cancel invite (2 more senders)",
                    "confidence": "HIGH", "request": RT_HDR + ["optional: u32 member_id or 0", "u32 0 or member_id", "u32 ?"]},
    (10687, 2919): {"owner": "RaceTeamManager", "feature": "team members / manage data (hub, manage tab)", "confidence": "MEDIUM",
                    "request": RT_HDR + ["u32 team_id (+0x1550)"]},
    (10690, 2924): {"owner": "RaceTeamManager", "feature": "team wall messages", "confidence": "HIGH",
                    "request": RT_HDR + ["u32 team_id (+0x1550)"]},
    (10725, 3511): {"owner": "RaceTeamManager", "feature": "create-page check of two strings [likely name/tag availability]",
                    "confidence": "MEDIUM"},
    (10766, 4589): {"owner": "RaceTeamManager", "feature": "restore contribution (RT_RestoreContributionClampEnabled)",
                    "confidence": "MEDIUM", "request": RT_HDR + ["u32 ?", "u32 ?", "u32 ?"]},
}

# Race Teams sub-syncs queued through helper 0xfb2cc4 instead of a direct SyncManager vtable call, so the
# catalogue scan missed them. Found by scanning RaceTeamManager code for type/param constants (NW-74).
RACE_TEAMS_HELPER_SUBSYNCS = {
    (10679, 2819): {"owner": "RaceTeamManager", "feature": "kick member (telemetry 'Race Teams | Kick Member', RTMemberId)",
                    "confidence": "HIGH", "request": RT_HDR + ["u32 member_id"],
                    "reply": ["u32 my_rt_member_id", "u32 status (2 locked, else generic error)"]},
    (10681, 2821): {"owner": "RaceTeamManager", "feature": "invite member (2 senders)", "confidence": "HIGH",
                    "request": RT_HDR + ["u32 member_id", "u32 team_id (+0x1550)"],
                    "reply": ["u32 my_rt_member_id", "u32 ?", "lp ?", "u32 status (RT_STATUS; 6 not authorised)"]},
    (10682, 2822): {"owner": "RaceTeamManager", "feature": "edit team info (info tab: motto / description / privacy)",
                    "confidence": "HIGH", "request": RT_HDR + ["u32 team_id", "lp description", "lp motto", "bool32 is_private"]},
    (10683, 2905): {"owner": "RaceTeamManager", "feature": "accept membership request (telemetry 'Accept Request')",
                    "confidence": "HIGH", "request": RT_HDR + ["u32 member_id"]},
    (10684, 2906): {"owner": "RaceTeamManager", "feature": "decline membership request (own requests: my id, -1)",
                    "confidence": "HIGH", "request": RT_HDR + ["u32 member_id", "u32 team_id or -1", "bool32 ?"]},
    (10689, 2923): {"owner": "RaceTeamManager", "feature": "post wall message (telemetry 'Post Wall Message')",
                    "confidence": "HIGH", "request": RT_HDR + ["u32 team_id (+0x1550)", "lp message"],
                    "reply": ["u32 my_rt_member_id", "u32 status (0 ok, 1 profanity, 2 connection error)"]},
    (10726, 3586): {"owner": "RaceTeamManager", "feature": "team request carrying a value from 0xfb8514", "confidence": "LOW",
                    "request": RT_HDR + ["u32 team_id (+0x1550)", "u32 ?"]},
}

# Status codes shared by Race Teams replies (join, request-membership and invite handlers; the request
# handler's jump table is at ELF 0x4f7c76). Create (1-4) and leave (2 = locked) use their own codes.
RT_STATUS = {0: "success", 1: "already on a team", 2: "too many members", 3: "too many requests",
             4: "already requested membership", 5: "blocked", 6: "not authorised", 8: "team is private",
             9: "locked"}

RACE_TEAMS_PREFIX_TYPES = frozenset(k for k, v in {**SUBSYNC_FEATURES, **RACE_TEAMS_HELPER_SUBSYNCS}.items()
                                    if v["owner"] == "RaceTeamManager")
