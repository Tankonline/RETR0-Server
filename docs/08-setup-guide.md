# 08 · Setup guide: from zero to playing

This is the procedure the project used, on Windows 11 with the Android emulator. Paths are examples; run commands
from the repository root unless stated. Commands are PowerShell.

> **Back up first.** If you use an existing install, copy its `Android/data/com.ea.games.r3_row/` folder somewhere
> safe before changing anything.

## 1. What you need

| Item | Notes |
|---|---|
| Your own RR3 **14.0.1** APK | `real-racing-3-14-0-1.apk`, SHA-256 `dcfe3788004444bd69e2fb839c18a973b488e94f46f1b818b6c005afdcad1d5f`. The build scripts refuse any other file |
| Your own game data | The `.depot` folder of an install that finished downloading (`Android/data/com.ea.games.r3_row/files/.depot`). It also contains `CC_SeedData.bin` |
| Python 3.12+ | For the server (standard library only) and the build scripts |
| Android SDK | Emulator, platform-tools (adb), **build-tools 36** (zipalign, apksigner), **NDK 28** (clang, ld.lld) |
| Java + APKTool 3.0.3 | For the client's Java patch |
| MSYS2 `ucrt64` zlib | Only for building asset packs (`C:\msys64\ucrt64\bin\zlib1.dll`); Python's own zlib gives different bytes |
| Windows Hypervisor Platform | For a fast x86_64 emulator |

## 2. The emulator

1. Create an AVD: Android 14 (API 34), **Google APIs, x86_64** image (it allows `adb root` / `su`), plenty of RAM
   (the project used 10 GB; 6 GB crashed the WebView now and then).
2. Start it with DNS pointed at your PC:

   ```powershell
   emulator -avd <your avd> -no-snapshot-load -gpu host -dns-server 127.0.0.1
   ```
3. Optional but recommended: lock its network so nothing can leave except DNS to your PC
   ([research-tools/avd_network_lock.sh](../research-tools/avd_network_lock.sh)):

   ```powershell
   bash research-tools/avd_network_lock.sh lock --allow-dns
   ```

## 3. The server

```powershell
py -3 -m venv server\python
mkdir server\data
copy <your .depot>\CC_SeedData.bin server\data\
```

## 4. Asset packs (for fresh installs)

A fresh install downloads ~1 GB from the CDN. The server serves it from packs built from **your** data.

```powershell
server\python\Scripts\python -I server\tools\asset_pack_build.py --apk <apk> --list all `
    --data <your .depot> [--data <a second copy, used as fallback>] `
    --drop-unavailable --lists-out build\lists --out build
server\python\Scripts\python -I server\tools\make_edited_res_zip.py --apk <apk> --lists build\lists --out build\res.zip
```

Then copy `build\rr3\live` to `server\cdn\rr3\live`, and `build\res.zip` plus `build\lists` to `server\client\`.
Building all 1,236 lists takes about 15 minutes. Why "edited" lists exist: [09-asset-cdn.md](09-asset-cdn.md).

If your install already has all its content, you can skip this step.

## 5. Build the RETR0 client

Use the **[RETR0-Client](https://github.com/Tankonline/RETR0-Client)** repository (clone it next to this one):

```powershell
python ..\RETR0-Client\patches\store_grant_patch\build_patch.py --apk <apk> --out build\apk `
    --ndk-bin <sdk>\ndk\28.2.13676358\toolchains\llvm\prebuilt\windows-x86_64\bin `
    --build-tools <sdk>\build-tools\36.0.0
```

Outputs in `build\apk\`:
- `rr3_14.0.1_retr0_client.apk`: for swapping into an existing install (keeps data);
- `rr3_14.0.1_retr0_client_signed.apk`: debug-signed, for a new install.

Copy both into `server\client\apk\`, together with your original APK renamed to `rr3_14.0.1_original.apk` (used by
`client.ps1 restore`). How the build works: [the RETR0 client](https://github.com/Tankonline/RETR0-Client/blob/main/docs/how-the-client-is-patched.md).

## 6. Put the client on the emulator

**Existing install (keeps your progress):**

```powershell
server\client.ps1 apply      # swaps base.apk in place as root, then lets Android recompile the code
server\client.ps1 status     # shows which APK is installed
```

**New install:**

```powershell
server\client.ps1 install-fresh                      # asks before uninstalling
# launch the game once, let it unpack files/apk/, then stop it:
adb shell am force-stop com.ea.games.r3_row
adb push server\client\res.zip /sdcard/Android/data/com.ea.games.r3_row/files/apk/res.zip
#   then, as root, give the file to the app's user id and restore its SELinux label
server\python\Scripts\python -I server\tools\apply_edited_lists.py apply --edited server\client --data <your .depot>
```

`apply_edited_lists.py` also adds the RGB substitutes for textures that the edited lists dropped. Pushing `res.zip`
*before* the first launch does not work: the game wipes `files/apk/` while its checksum file is missing.

> [!WARNING]
> An emulator **restart** removes an in-place swapped APK (Android re-checks signatures at boot); your data stays.
> Reinstall the original over it with `adb install -r server\client\apk\rr3_14.0.1_original.apk`, then
> `server\client.ps1 apply` again.

**Optional: button text.** `server\client.ps1 ui-text` renames Settings › ENTER RACING CODE to "Change Username
(Restart Required)" (it edits two of the game's UI files on the device and keeps the originals in
`server\backups\ui_text\`).

## 7. Play

```powershell
server\retr0_server.cmd start -WithSync
server\play.cmd
```

`play.cmd` checks that the emulator runs the RETR0 client, sets `adb reverse tcp:8780 tcp:8780` and starts the game.
It stays connected until you close the game. When you are done:

```powershell
server\retr0_server.cmd stop
```

## 8. Undo

| To undo | Do |
|---|---|
| The RETR0 client | `server\client.ps1 restore` (original APK back in place, data kept) |
| Edited lists on the device | `apply_edited_lists.py restore`, and copy back `/data/local/tmp/retr0_res_backup/res.zip` |
| The player name | delete `files/doc/retr0_username.txt` on the device |
| The button text | `server\client.ps1 ui-text-restore` |
| Everything | uninstall and reinstall the original APK |
