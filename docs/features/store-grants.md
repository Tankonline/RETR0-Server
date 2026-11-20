# Feature · Store preservation grants

**What it does:** pressing **BUY** on a Store currency package (Gold, R$, M$) or a currency pack gives its contents
immediately, as a free preservation grant. There is no purchase: no Google Play call, no receipt, no purchase record.
Evidence: [reference/STORE_PRESERVATION_GRANTS.md](../reference/STORE_PRESERVATION_GRANTS.md) (SP-01..SP-15).

## Why

Real purchases are impossible now (EA's store backends are gone), so pressing BUY showed an error such as
*"To access the Store please sign into a valid Google Play Store account"*. The goal was that BUY under, say, the
16-Gold package gives exactly 16 Gold.

## Investigation

1. **Catalogue:** the store catalogue (seed file 12, 556 products) was decoded. Each product carries its own
   metadata, e.g. `type:wrench, qty:16`. Amounts therefore come from the game's data, never from user input.
2. **Server-side gifts first:** the game can receive gifts through sub-sync 10480 and credits them as unclaimed
   offerwall rewards. Implemented, but two test gifts froze the game, so this path was parked
   ([gifts.md](gifts.md)).
3. **The non-purchase award:** the offerwall claim (`0x12eda84`) awards a reward with
   `MTXManager` `0xb873c0(reward, 0)` then `0xb879fc(reward, 0, 1)`. With the last argument 1, currency is added with a
   non-purchase source code and the purchase-record branch is skipped (SP-13). That is exactly what a free grant
   needs.

## How it was built

Two hooks in the native patch ([10-retr0-client.md](../10-retr0-client.md)):

| Hook | Original behaviour | Handler |
|---|---|---|
| `NimbleMTX::PurchaseStoreProduct` `0xb8d6e4` | Starts a Nimble/Google Play purchase | For allow-listed currency packages: grant |
| `PackManager` pack purchase `0x13ef7e8` | Checks Google Play, then starts a purchase | For allow-listed currency packs: grant |

The grant routine:

1. looks the product up in the game's static store (`0xb84354`);
2. parses the product's catalogue metadata into a reward (`0xcee2e0`, as `NimbleMTX::AwardProduct` does);
3. awards it with `0xb873c0` / `0xb879fc(reward, 0, 1)` (the non-purchase path);
4. destroys the reward, requests a save (`0x13a14b8`), and logs
   `RETR0 preservation grant: store product N awarded=1 (no purchase)`.

Any other product id runs the original code unchanged.

| Product | Ids |
|---|---|
| Gold | 10051-10057 |
| R$ | 10045-10050 |
| M$ | 10461-10466 |
| Packs | Starter 10061, Booster 10062, Turbo 10063, Enhancer 10988, Charger 10989 |

## Verified (runs 21–23)

Gold 16 and 42, R$ 140k, M$ 250k and all five packs were granted with no error popup; balances persisted after a
force-stop and relaunch. Other sizes use the same code path but were not individually tested.
