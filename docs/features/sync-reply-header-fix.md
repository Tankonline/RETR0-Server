# Fix · The sync reply member header

**What it fixed:** before 2026-11-20 the RETR0 server's sync replies were missing a header, so the game misread
**every non-empty sub-sync reply**. Evidence: [reference/NETWORKING_ANALYSIS.md](../reference/NETWORKING_ANALYSIS.md)
NW-93.

## How it showed up

Entering a racing code gave *"Connection error. Please check your connection settings and try again."*, although
the server had answered. The client's log in that moment said:

```
CC: Member changed [Member Id: 13]
CC: Device Id: 1920230770
CC: SubSync Received: 10632
```

`13` was exactly the length of the server's 13-byte racing-code reply, and the "device id" was the next four bytes
of that reply read as a number.

## Cause

After `u32 ok` and `u32 value`, the client hands the reply to the active auth manager (`cc::auth::LegacyManager`,
`0x1cfb784`), which reads a **member header** before any sub-sync parts:

```
u32 member_id · bool32 is_developer · u32 device_id · u32 u_b · bool32 flag
```

The server sent the parts straight after `value`. With empty parts this went unnoticed: the lengths read as zeros
("member 0, not a developer"). Any real reply, however, was eaten by the header and its callback received an empty
blob, which the racing-code handler reports as a connection error.

## Fix

The codec's `sync_response_body()` writes the header, and the sync service fills it with **the member id the client
sent**, so the game never sees a member change. Tests check the header and the part offsets.

## Likely also explains the gift freezes

The two test gifts (sub-sync 10480) froze the game 35–60 s after delivery, with hundreds of thousands of
`UnpackData` assertion messages from the BinaryBlob reader. A long gift reply misread the same way would send the
reader past the end of the data. This link is **MEDIUM** confidence until gifts are re-tested
([gifts.md](gifts.md)).
