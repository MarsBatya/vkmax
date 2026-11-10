# AGENTS.md

## Overview & Architecture

Async Python (>=3.10) user-client library for the MAX messenger (OneMe), speaking a
seq-matched JSON-RPC protocol over WebSocket (`wss://ws-api.oneme.ru/websocket`).

- `vkmax/raw_client.py` — base `MaxClient`: connection lifecycle, `invoke_method` RPC,
  auth, keepalive. Owns all pending-future/task state.
- `vkmax/client.py` — public `MaxClient`, composed from method mixins in `vkmax/functions/`
  (`UploadMethods` subclasses the raw client; `MessageMethods` subclasses `UploadMethods`).
  Import path for users is `vkmax.client.MaxClient`.
- `vkmax/types/`, `vkmax/utils/` — TypedDicts/enums and formatting helpers.
- `vkmax/routing.py`, `vkmax/packet.py` — experimental, not wired into dispatch; don't
  build on them without an explicit decision.
- `tests/` — pytest suite; `tests/conftest.py` provides `FakeWebSocket` + `make_client`.
- `docs/protocol.md`, `docs/opcodes.md` — protocol reference; verify wire constants here
  or against the live API before changing them.
- `examples/`, `example.py` — runnable userbots; covered by import/smoke tests.

## Essential Commands

```sh
uv sync --extra dev          # install (uv.lock is authoritative; pip: python -m pip install -e ".[dev]")
uv run pytest -q             # full suite (CI gate)
uv run pytest tests/test_lifecycle.py -q   # focused file; ::test_name for a single test
uv run ruff check vkmax      # lint (CI gate, config in pyproject.toml)
```

CI (`.github/workflows/tests.yml`) runs import smoke + `ruff check vkmax` + `pytest -q`
on Python 3.10–3.13. Verify on 3.10 (the floor) as well as the local interpreter when
touching runtime code; no 3.11+ APIs (e.g. `asyncio.timeout`).

Formatting: new/changed code must also pass the maintainer's stricter config
`/home/mars/python/.vscode/ruff.toml` (88 columns, A/C/B/Q/N/S/COM/C4/RET rules):
`uv run ruff format --config /home/mars/python/.vscode/ruff.toml <files>` and
`uv run ruff check --config /home/mars/python/.vscode/ruff.toml <files>`.
Fix only violations in code you touch; the rest of the repo has a known baseline.

## Testing Conventions

- Unit tests never touch the network: an autouse fixture blocks `socket.connect`.
  Use `make_client` / `FakeWebSocket` (scripted responses, `auto_reply=False` for
  silence, `push_packet`/`push_raw`/`close_from_server` for server-side events).
- `asyncio_mode = "auto"`: async tests need no decorator/markers.
- `ResourceWarning` is an error — consume/close every aiohttp response and stream.
- Every behavioral fix ships with a regression test that fails before the fix and
  passes after. One focused change per commit; no drive-by refactors.

## Lifecycle Invariants (raw_client)

- No caller may await forever: `invoke_method` bounds waits with `request_timeout`
  and removes/cancels its future on every failure path.
- Disconnect and recv-loop death fail all pending futures (`_pending`,
  `_video_pending`, `_file_pending`) with `ConnectionError` and clear the dicts.
- `disconnect()` is idempotent, awaits cancelled tasks, resets session state.
- The recv loop must survive malformed packets; guard future resolution with
  `not future.done()`; spawn callback tasks via `_spawn_callback` (tracked, exceptions
  logged) — never bare `asyncio.create_task` for callbacks.

## Safety & Boundaries

- Never commit session/token files (e.g. `max_session.txt`, `login_token.txt`) or
  log/commit tokens, SMS codes, or phone numbers; they are live credentials/PII.
- `build/`, `vkmax.egg-info/`, `.venv/`, `.tmp/` are untracked local artifacts/notes —
  never edit or import from `build/` (stale duplicate package). Don't hand-edit `uv.lock`.
- Protocol constants (permission codes, operation names, opcodes) must be confirmed
  against `docs/` or the live API before merging changes.
- Publishing, force-pushing, and other destructive/shared-state actions require
  explicit user confirmation.