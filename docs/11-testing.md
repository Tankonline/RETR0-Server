# 11 · Testing

## Unit tests

```powershell
python -m pip install pytest
python -m pytest -q tests
```

| File | Covers |
|---|---|
| [`tests/test_cloudcell_codec.py`](../tests/test_cloudcell_codec.py) | Boxing and checksums, sub-sync records, every decoded sub-sync payload, the sync reply with its member header |
| [`tests/test_local_service.py`](../tests/test_local_service.py) | The sync service end to end over HTTP: auth, dispatch, reply part order, cloud-save upload/download |
| [`tests/test_seed_data.py`](../tests/test_seed_data.py) | The seed archive reader and the store catalogue reader/builder (synthetic data) |

The tests use synthetic data only; no game files are needed.

## Runtime tests

Every feature was tested on the network-locked emulator, each run approved by the project owner first. The full log
with setup, evidence and outcome is [reference/RUNTIME_TEST_PLAN.md](reference/RUNTIME_TEST_PLAN.md) §9.

| Runs | What | Outcome |
|---|---|---|
| 1, 3, 4 | Startup and first-run behaviour, request recording | Download flow and every endpoint identified |
| 5–9 | Serving the CDN from the owner's data | Full download, 0 errors |
| 12–13 | `/time` and `CC_Sync.php` | Game no longer OFFLINE |
| 14–15 | Serving modified files | Works; reverted |
| 16–23 | Store grants | All tested packages and packs granted; survive a restart |
| 24 | Special events | Cause found (timed hook); events open |
| 25 | RETR0 client without Frida | Sync works; events and store confirmed |
| 26–29 | Username | Works on Profile and race results; server header bug fixed |

## How a change is verified

1. Static: read the code path and the disassembly; check every address and expected instruction in the build script
   (the build fails if any byte differs from what it expects).
2. Unit tests for anything in the server or codec.
3. On the emulator: logcat lines from the game and from our `RETR0 …` log messages, the server's own logs, and the
   owner checking the screen.
4. After anything that could touch saves: pull the save files byte-exactly (`adb exec-out`) and check their
   container (magic, size, checksum). This was done after the username bug in run 29: all files intact.
