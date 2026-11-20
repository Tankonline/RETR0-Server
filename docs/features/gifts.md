# Feature · Server-side gifts

**What it does:** the server sends currency to the player through the game's own gift system. The amounts come only
from the game's store catalogue (your seed data); there is no free-form amount.

| Currency | How it arrives | Tested |
|---|---|---|
| Gold (`type:wrench`) | Notifications → "FREE GOLD EARNED FROM OFFER!" → tap → "Congratulations! You have successfully received …" | Run 32: 16 Gold, 693 → 709 |
| R$ (`type:money`) | Credited at once, popup "RETR0 · Preservation grant: 50,000 R$" | Run 33: 3,571,000 → 3,621,000 |
| M$ (`type:mdollars`) | Credited at once, popup "RETR0 · Preservation grant: 45,000 M$" | Run 33: 778,600 → 823,600 |

All three survive a game restart and are never delivered twice.
Evidence: [reference/STORE_PRESERVATION_GRANTS.md](../reference/STORE_PRESERVATION_GRANTS.md) SP-08..SP-17.

## Sending a gift

From the PC running the server (the endpoint only answers `127.0.0.1`; the emulator cannot reach it):

```powershell
Invoke-WebRequest -Method Post "http://127.0.0.1:8781/retr0/admin/gift?product=10051"   # 16 Gold
```

Product ids (store catalogue, SP-06): Gold 10051–10056 (16 / 42 / 87 / 183 / 476 / 1,019), R$ 10045–10050
(50k / 140k / 300k / 700k / 2M / 5M), M$ 10461–10466 (45k / 115k / 250k / 520k / 1.35M / 3M). Anything else is
refused with HTTP 400. The game picks gifts up when it starts (main menu).

## How gifts work in the client

1. `cc::GiftManager` sends sub-sync **10480** (FetchAdHocGifts), twice per session. The reply is `u32 count`, then
   per gift `u32 id, u32 kind` and three length-prefixed strings.
2. The listener `CC_Helpers::Manager` (`0xcd3cfc`) switches on **kind**:
   - **kind 2, offer reward:** stored by id with string 1 as an unclaimed reward (`0x12ed440`), shown in
     Notifications; the claim (`0x12eda84`) parses string 1 with the store parser and credits **Gold only**.
   - **kind 0, "Community Management"** (`0xcd7844`): string 1 is a `;`-separated reward list; each entry is credited
     at once through the non-purchase award; if string 3 is set, a popup shows string 2 (title) and string 3.
   - any other kind: dropped ("Unsupported Adhoc Gift Type").
3. The client acknowledges with sub-sync **10481**: `u32 count`, per gift `u32 id, string, u32 flag`. The server then
   marks the gift delivered.

## Server side

- Gold is sent as kind 2; R$ and M$ as kind 0 (the kind-2 claim would silently drop them).
- A kind-0 gift is offered **once**: the client asks twice per session before it acknowledges, and kind 0 has no
  duplicate check in the client.
- State: `runtime/sync_data/state.json` → `gifts.pending`, `gifts.claimed`, `gifts.held` (test gifts that must not
  be re-sent). Gifts are not per player yet.

## History

The first tests (runs 16–20) froze the game: the server's sync replies lacked the member header
([sync-reply-header-fix.md](sync-reply-header-fix.md)). After that fix (run 32) the gift still vanished, because the
server put the product id where the client expects the gift kind. Fixing that made Gold work; R$/M$ then needed the
kind-0 path (run 33).
