# client-patches/

Sources and build scripts for the RETR0 client. They contain no EA code; every build reads **your own** original
RR3 14.0.1 APK (SHA-256 checked) and writes new files, never modifying the original.

| Folder | Builds | Docs |
|---|---|---|
| `local_server_redirect/` | `classes2_redirect.dex`: the built-in server redirect (smali, via APKTool 3.0.3) | [server-redirect](../docs/features/server-redirect.md) |
| `store_grant_patch/` | The native patch (store grants + username) and the final client APKs | [store-grants](../docs/features/store-grants.md), [username](../docs/features/username.md) |

Build order (redirect first, then the APK):

```powershell
python client-patches\local_server_redirect\build_redirect_dex.py --apk <apk> --out build\apk --apktool <apktool_3.0.3.jar>
python client-patches\store_grant_patch\build_patch.py --apk <apk> --out build\apk --ndk-bin <ndk llvm bin> --build-tools <build-tools 36>
```

How the patching works: [docs/10-retr0-client.md](../docs/10-retr0-client.md).
