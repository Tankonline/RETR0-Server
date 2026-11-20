# Contributing to RETR0 Server

Thanks for helping preserve Real Racing 3. This project runs on evidence, so contributions follow a few rules.

## Ground rules (non-negotiable)

- **Never commit game material:** no APKs, DEX/`.so` files, assets, seed data, saves, keys, or decompiler output.
  The `.gitignore` blocks the common file types; CI checks too.
- **Never contact EA infrastructure.** Everything listens on and talks to `127.0.0.1`.
- **No personal data** in code, docs, logs or screenshots (account ids, device ids, tokens, home paths).
- **Pseudocode is not source.** Describe behaviour and addresses; don't paste decompiler output.

## Ways to help

| You can… | How |
|---|---|
| Report a bug | Open a **Bug report** issue with logs from `server/runtime/` (scrub personal data) |
| Share a finding | Open a **Research finding** issue: what, where (address/string/log), evidence, confidence |
| Implement a sub-sync | Pick one from [docs/reference/NETWORKING_ANALYSIS.md](docs/reference/NETWORKING_ANALYSIS.md), add a handler + codec function + tests |
| Improve the docs | Fix, clarify, or add a diagram; keep the confidence labels honest |

## Findings: evidence and confidence

Every finding states its evidence and one label:

| Label | Meaning |
|---|---|
| **CONFIRMED** | Direct evidence, ideally from more than one source (code + runtime) |
| **HIGH** | Strong evidence, one detail unverified |
| **MEDIUM** | Plausible, partly supported |
| **LOW** | Tentative |
| **UNKNOWN** | Not enough evidence |

Addresses are ELF virtual addresses in the arm64-v8a `libRealRacing3.so` of RR3 14.0.1 unless stated otherwise.
Function names stay neutral (`FUN_…`/address) unless evidence (source path, log string, RTTI) names them.

## Code

- Python 3.12+, **standard library only** for anything under `server/`.
- New wire formats go into `server/services/cloudcell_codec/cloudcell_codec.py` with a docstring that cites the
  client function that reads or writes them, plus a unit test.
- Run the tests before opening a pull request:

  ```powershell
  python -m pip install pytest
  python -m pytest -q tests
  ```

## Pull requests

- One topic per pull request; describe what changed, why, and how it was verified.
- If a runtime test was involved, say what was run on the emulator and what the logs showed.
- Fill in the checklist in the pull request template.
