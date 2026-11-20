// Project RETR0 - Store preservation grant patch (arm64-v8a libRealRacing3.so, RR3 14.0.1)
// Independently written; see 07_DOCUMENTATION/STORE_PRESERVATION_GRANTS.md (SP-12).
//
// The entry of NimbleMTX::PurchaseStoreProduct (ELF 0xb8d6e4, "NimbleMTX:PurchaseStoreProduct(%d, %s)")
// is redirected here. For the store's currency packages only (Gold 10051-10057, R$ 10045-10050,
// M$ 10461-10466; ids from the store catalogue, seed file 12) the handler:
//   1. looks the product up in the game's own static store (vt call wrapper 0xb84354, as the original does),
//   2. parses the product's own catalogue metadata (product+0x98, e.g. "type:wrench, qty:16") into a
//      reward with the game's parser 0xcee2e0 (as NimbleMTX::AwardProduct 0xb8f7b8 does),
//   3. awards it with MTXManager 0xb873c0 / 0xb879fc exactly as the offerwall reward claim 0x12eda84
//      does (last argument 1 = the non-purchase path: no purchase record is written),
//   4. destroys the reward (0xa36fec), flags a save (0x13a14b8) and logs a grant line.
// It never starts a Nimble/Google Play transaction and never fabricates a receipt or verification.
// Every other product id runs the original function unchanged.

    .text
    .globl grant_entry
grant_entry:
    mov     w9, #10045              // R$ 10045-10050, Gold 10051-10057
    sub     w9, w1, w9
    cmp     w9, #12
    b.ls    grant
    mov     w9, #10461              // M$ 10461-10466
    sub     w9, w1, w9
    cmp     w9, #5
    b.ls    grant
    sub     sp, sp, #0x90           // displaced original instruction at 0xb8d6e4
    b       orig_continue           // 0xb8d6e8

// PackManager pack purchase (ELF 0x13ef7e8, src\Store\PackManager.cpp): x1 -> pack offer, product id at +8.
// The original first checks the Google Play store is available (0xb843d8) and otherwise shows
// "To access the Store please sign into a valid Google Play Store account". For the allow-listed
// currency packs the product goes to the same grant as above (the award routine hands pack types
// 5/6/0x21 to PackManager 0x13efb2c with the same non-purchase flag). Other packs are logged and run
// the original code unchanged.
    .globl pack_entry
pack_entry:
    ldr     w9, [x1, #8]
    adr     x10, pack_ids
    mov     x11, #(pack_ids_end - pack_ids) / 4
1:  cbz     x11, pack_other
    ldr     w12, [x10], #4
    cmp     w12, w9
    b.eq    pack_grant
    sub     x11, x11, #1
    b       1b
pack_grant:
    mov     w1, w9
    b       grant
pack_other:
    stp     x29, x30, [sp, #-0x40]!
    stp     x0, x1, [sp, #0x10]
    stp     x2, x3, [sp, #0x20]
    stp     x4, x5, [sp, #0x30]
    adr     x0, fmt_pack_other
    mov     w1, w9
    bl      game_log
    ldp     x4, x5, [sp, #0x30]
    ldp     x2, x3, [sp, #0x20]
    ldp     x0, x1, [sp, #0x10]
    ldp     x29, x30, [sp], #0x40
    str     d8, [sp, #-0x70]!       // displaced original instruction at 0x13ef7e8
    b       pack_continue           // 0x13ef7ec

pack_ids:                           // currency packs from the store catalogue (type:pack, consumable)
    .word   10061, 10062, 10063, 10988, 10989
pack_ids_end:

grant:
    sub     sp, sp, #0x240
    stp     x29, x30, [sp]
    mov     x29, sp
    stp     x19, x20, [sp, #0x10]
    str     x21, [sp, #0x20]
    mov     w19, w1                 // product id

    adrp    x8, got_store_mgr       // same load sequence as 0xb8d77c..0xb8d78c
    ldr     x8, [x8, :lo12:got_store_mgr]
    ldr     x0, [x8]
    mov     w1, w19
    mov     w2, #1
    bl      store_lookup            // 0xb84354
    cbz     x0, not_found
    mov     x20, x0                 // product

    add     x0, sp, #0x40           // reward object (0x200 bytes reserved)
    add     x1, x20, #0x98          // product catalogue metadata string
    add     x2, x20, #0x10
    ldr     w3, [x20, #8]
    bl      reward_parse            // 0xcee2e0

    add     x0, sp, #0x40
    mov     w1, wzr
    bl      mtx_can_award           // 0xb873c0
    mov     w21, w0
    tbz     w0, #0, after_award
    add     x0, sp, #0x40
    mov     w1, wzr
    mov     w2, #1                  // non-purchase award (offerwall-claim path)
    bl      mtx_award               // 0xb879fc
after_award:
    add     x0, sp, #0x40
    bl      reward_dtor             // 0xa36fec

    adrp    x8, got_save_mgr        // same load sequence as 0x12edecc..0x12eded4
    ldr     x8, [x8, :lo12:got_save_mgr]
    ldr     x0, [x8]
    bl      save_request            // 0x13a14b8

    adr     x0, fmt_grant
    mov     w1, w19
    and     w2, w21, #1
    bl      game_log                // 0x109fa18 (printf-style)
    b       out

not_found:
    adr     x0, fmt_missing
    mov     w1, w19
    bl      game_log

out:
    ldr     x21, [sp, #0x20]
    ldp     x19, x20, [sp, #0x10]
    ldp     x29, x30, [sp]
    add     sp, sp, #0x240
    ret

fmt_grant:
    .asciz  "RETR0 preservation grant: store product %d awarded=%d (no purchase)\n"
fmt_missing:
    .asciz  "RETR0 preservation grant: store product %d not in static store\n"
fmt_pack_other:
    .asciz  "RETR0 preservation grant: pack product %d not allow-listed, original store path\n"
    .balign 4

// =====================================================================================================
// RETR0 username (independently written; see 07_DOCUMENTATION/SAVE_SYSTEM_ANALYSIS.md SV-25..SV-27).
// The game's player-name function (ELF 0x135e944, used by the Profile title and the race results)
// asks the platform account and then CloudCell's MemberManager, which answers "Guest" without a
// sign-in. name_entry runs the original and then, if the name file holds a name, replaces the result
// with it. The file is read once per game start (so a new name applies after a restart):
//     /storage/emulated/0/Android/data/com.ea.games.r3_row/files/doc/retr0_username.txt
// promo_entry (racing-code submit, ELF 0x1516b1c, x1 = typed code): the typed code becomes the new
// name (a leading "NAME " in any case is dropped) and is written to that file; then the original code
// path runs unchanged (the local server, which hands out no promo rewards, answers "code accepted").
// Scratch state: 16 spare bytes inside a 24-byte static string that nothing reads (name_slot):
//     +0 = 1 once the file was tried, +8 = malloc'd name or 0.
// =====================================================================================================
    .globl name_entry
name_entry:
    stp     x29, x30, [sp, #-0x20]!
    stp     x19, x20, [sp, #0x10]
    mov     x29, sp
    mov     x19, x8                 // std::string* result: returned by value, so its address is in x8 (AAPCS64)
    bl      name_tramp              // original function, arguments untouched
    bl      name_load
    cbz     x0, 1f
    ldrb    w9, [x0]
    cbz     w9, 1f
    mov     x1, x0
    mov     x0, x19
    bl      str_assign              // 0x15da06c std::string::assign(const char*)
1:  ldp     x19, x20, [sp, #0x10]
    ldp     x29, x30, [sp], #0x20
    ret
name_tramp:
    sub     sp, sp, #0x1c0          // displaced original instruction at 0x135e944
    b       name_continue           // 0x135e948

name_load:                          // -> x0 = name or 0
    adrp    x8, name_slot
    add     x8, x8, :lo12:name_slot
    ldr     x9, [x8]
    cbnz    x9, 9f
    mov     x9, #1
    str     x9, [x8]
    stp     x29, x30, [sp, #-0x30]!
    mov     x29, sp
    stp     x19, x20, [sp, #0x10]
    str     x21, [sp, #0x20]
    adr     x0, name_path
    adr     x1, mode_r
    bl      fopen
    cbz     x0, 8f
    mov     x20, x0
    mov     x0, #0x48
    bl      malloc
    mov     x21, x0
    cbz     x0, 7f
    mov     w1, #0x40
    mov     x2, x20
    bl      fgets
    cbz     x0, 7f
    mov     x9, x21                 // cut at the first CR/LF
2:  ldrb    w10, [x9]
    cbz     w10, 4f
    cmp     w10, #10
    b.eq    3f
    cmp     w10, #13
    b.eq    3f
    add     x9, x9, #1
    b       2b
3:  strb    wzr, [x9]
4:  adrp    x8, name_slot
    add     x8, x8, :lo12:name_slot
    str     x21, [x8, #8]
    adr     x0, fmt_name_loaded
    mov     x1, x21
    bl      game_log
7:  mov     x0, x20
    bl      fclose
8:  ldr     x21, [sp, #0x20]
    ldp     x19, x20, [sp, #0x10]
    ldp     x29, x30, [sp], #0x30
    adrp    x8, name_slot
    add     x8, x8, :lo12:name_slot
9:  ldr     x0, [x8, #8]
    ret

    .globl promo_entry
promo_entry:
    cbz     x1, 5f
    mov     x9, x1                  // the new name = the whole code ...
    ldrb    w10, [x1]               // ... or what follows a leading "name " (any case)
    orr     w10, w10, #0x20
    cmp     w10, #'n'
    b.ne    4f
    ldrb    w10, [x1, #1]
    orr     w10, w10, #0x20
    cmp     w10, #'a'
    b.ne    4f
    ldrb    w10, [x1, #2]
    orr     w10, w10, #0x20
    cmp     w10, #'m'
    b.ne    4f
    ldrb    w10, [x1, #3]
    orr     w10, w10, #0x20
    cmp     w10, #'e'
    b.ne    4f
    ldrb    w10, [x1, #4]
    cmp     w10, #' '
    b.ne    4f
    add     x9, x1, #5
4:  ldrb    w10, [x9]
    cbz     w10, 5f                 // empty name: leave everything to the original code
    stp     x29, x30, [sp, #-0x30]!
    mov     x29, sp
    stp     x0, x1, [sp, #0x10]
    stp     x19, x20, [sp, #0x20]
    mov     x19, x9                 // the new name
    adr     x0, name_path
    adr     x1, mode_w
    bl      fopen
    cbz     x0, 6f
    mov     x20, x0
    mov     x0, x19
    mov     x1, x20
    bl      fputs
    mov     x0, x20
    bl      fclose
    adr     x0, fmt_name_saved
    mov     x1, x19
    bl      game_log
6:  ldp     x19, x20, [sp, #0x20]
    ldp     x0, x1, [sp, #0x10]
    ldp     x29, x30, [sp], #0x30
5:  sub     sp, sp, #0x170          // displaced original instruction at 0x1516b1c
    b       promo_continue          // 0x1516b20

name_path:
    .asciz  "/storage/emulated/0/Android/data/com.ea.games.r3_row/files/doc/retr0_username.txt"
mode_r:
    .asciz  "r"
mode_w:
    .asciz  "w"
fmt_name_loaded:
    .asciz  "RETR0 username loaded: %s\n"
fmt_name_saved:
    .asciz  "RETR0 username saved: %s (applies after a restart)\n"
    .balign 4
