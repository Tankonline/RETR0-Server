# Feature · Server-side gifts (parked)

**What it would do:** let the server send in-game gifts (currency from the store catalogue) to the player.
**Status:** implemented in the server, **held**. Evidence:
[reference/STORE_PRESERVATION_GRANTS.md](../reference/STORE_PRESERVATION_GRANTS.md) SP-08..SP-12.

## How gifts work in the client

1. `cc::GiftManager` sends sub-sync **10480** (FetchAdHocGifts). The reply is `u32 count`, then per gift `u32, u32`
   and three length-prefixed strings.
2. `0x12ed440` stores each new gift as an **unclaimed offerwall reward** (keyed by id, duplicates skipped), logs
   "Offerwall Rewards Synced" and requests a save. With a game listener present the client sends no 10481 ack.
3. The player claims it later: `BuyCarBar` shows a notification, and the `CLAIM_OFFERWALL_REWARD` action
   (`0x12eda84`) parses the reward (type 3 only) and awards it through the non-purchase path.

## Server side

- The sync service answers 10480 from a queue and marks gifts delivered on 10481.
- Gifts are queued through a local-only endpoint: `POST http://127.0.0.1:8781/retr0/admin/gift?product=<id>`
  (catalogue currency ids only).

## Why it is parked

Two test gifts froze the game 35–60 s after delivery (GLThread, ~250k–800k `UnpackData` assertion messages). This
happened on the unpatched game too. Both gifts are held in the server state (`gifts.held`). The store feature was
then built a different way ([store-grants.md](https://github.com/Tankonline/RETR0-Client/blob/main/docs/features/store-grants.md)).

The likely cause was found later: the server's sync replies lacked the member header, so a long gift reply was
misread ([sync-reply-header-fix.md](sync-reply-header-fix.md)). **Next step:** re-test one gift with the fixed server.
