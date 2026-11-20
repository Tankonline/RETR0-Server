# Feature · Player name (replacing "Guest")

**What it does:** you choose the name the game shows for you, on the Profile screen and in race results, instead of
"Guest".

**How to use:** Settings → **Enter Racing Code** → type the name → "code accepted" → restart the game. The name is
kept in `files/doc/retr0_username.txt` on the device; delete it to go back to "Guest".
Evidence: [reference/SAVE_SYSTEM_ANALYSIS.md](../reference/SAVE_SYSTEM_ANALYSIS.md) SV-25..SV-27.

## Investigation

1. **Not in the save.** The field names of every save file were listed (structure only): there is no player-name
   field (SV-25). In RR3 your name was the online account's name (Facebook, Google, Game Center).
2. **Not the text table.** A diagnostic build logged every text lookup returning "Guest" during a race: none
   (run 26).
3. **Not a static string.** A diagnostic build changed a built-in "Guest" string to "Hello": the screen still said
   Guest (run 27).
4. **The Profile screen** (`ProfileMenu`, layout `ProfileScreen.xml`) sets its title from `0x135e944`. That function
   asks the platform-account object first (empty on phones), then CloudCell's `MemberManager` for the member's
   display name, which is "Guest" when no social account is linked. The race results use the same function.
5. **Setting a name:** the game's own name prompt belongs to the dead Facebook sign-in, so a different input was
   needed. The **racing-code** box was a natural fit: its submit function `0x1516b1c(this, const char* code)` receives
   the typed text as a plain C string.

## How it was built

Two hooks in the native patch ([10-retr0-client.md](../10-retr0-client.md)):

- **`promo_entry`** at `0x1516b1c` (racing-code submit): takes the typed code (dropping a leading `NAME `, any case),
  writes it to `files/doc/retr0_username.txt` with `fopen`/`fputs`/`fclose`, logs
  `RETR0 username saved: …`, then lets the original code continue. The server answers the code with "accepted" and no
  rewards (sub-sync 10632, NW-94).
- **`name_entry`** at `0x135e944` (player name): runs the original function, then, if the name file holds a name,
  assigns it to the returned `std::string` with the game's own string assign (`0x15da06c`). The file is read once per
  game start (state kept in 16 spare bytes) and logged as `RETR0 username loaded: …`.

## Two bugs found on the way

- **"Connection error" after entering a code.** The server's sync reply had always lacked a 20-byte member header,
  so the game read the reply's first bytes as that header and the racing-code reply arrived empty. Fixed in the
  server. → [sync-reply-header-fix.md](sync-reply-header-fix.md)
- **Name saved and loaded, but still "Guest".** `0x135e944` returns its `std::string` **by value**, so the result's
  address arrives in register **`x8`**, not `x0`. Ghidra's pseudocode hides that. The first build wrote into `x0`
  (an unrelated object in memory). Fixed by saving `x8`. The save files were checked afterwards: all intact.

## Verified (run 29)

The owner confirmed the chosen name shows on Profile and in race results.
