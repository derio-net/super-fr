# install.sh fails intermittently at the fr-CLI step (retry succeeds)

## Symptom & reproduction

`./scripts/install.sh` failed twice in a row at step 10 ("Installing fr CLI
globally"), then succeeded on the third run with **no manual intervention**:

- **Run 1** — `uv tool install --force` completed ("Installed 1 executable:
  fr"), but the immediate smoke check aborted:
  `ERROR: fr CLI installed but does not run` → exit 1.
- **Run 2** — `uv tool install --force` itself failed:
  `error: failed to remove directory .../uv/tools/fr/lib: Directory not empty
  (os error 66)` → exit 2.
- **Run 3** — clean success.

Two *different* symptoms, both at the same step, both self-healing.

## Evidence

- `os error 66` = `ENOTEMPTY`. It fires when `uv tool install --force` removes
  the existing tool env in place and the `rmdir` of `.../fr/lib` finds the
  directory non-empty at that instant.
- The third run succeeding with no cleanup is the decisive fact: the condition
  is **transient**, not a persistent corruption (a stray file or bad state
  would have failed Run 3 too).
- Three deterministic reproduction attempts on the host all **failed** to
  trigger ENOTEMPTY — uv 0.11.18 absorbed each:
  1. a concurrent process holding the tool env open (CWD inside `lib/`),
  2. stray untracked files (`.DS_Store`, `__stray__.pyc`) left inside `lib/`,
  3. two `uv tool install --force` racing (uv takes a tool-dir lock).
  So the trigger is a genuinely timing-dependent filesystem race, not an
  on-demand condition.
- This host runs `fr` out-of-band constantly (the Claude Code SessionStart hook
  runs `fr acceptance status --brief`; `fr isolation up/down` spawns a detached
  gc `fr`), which supplies the momentary perturbation — but the exact interior
  race in uv/APFS was not the thing worth pinning: the fix is the same for any
  transient trigger.

## Root cause

`scripts/install.sh` step 10 is **non-idempotent and has zero resilience to a
transient failure**. It runs `uv tool install --force` exactly once and the
`fr --version` smoke check exactly once. `--force` removes the tool env in
place — on macOS that removal intermittently fails with ENOTEMPTY — and a
freshly built env can momentarily fail its first `--version` before it
quiesces. A single one-shot install + one-shot smoke check turns either
momentary hiccup into a hard abort, forcing the operator to re-run by hand.
This is systematic-debugging's "truly timing-dependent / environmental"
terminal case: the correct handling is **retry + hard-reset fallback**.

A secondary factor made Run 2 fatal specifically: under `set -euo pipefail`
the bare `uv tool install … | sed` pipeline, on `uv` failure, tripped
`errexit` and aborted the whole script (exit 2) — there was no place to catch
and retry.

## Fix

Step 10 now retries up to 3 times. The install pipeline lives in an `if`
condition so a `uv` failure (propagated by `pipefail` through `sed`) is caught
instead of tripping `set -e`; between attempts it runs `uv tool uninstall fr`
+ `rm -rf .../fr` to clear a stuck tool dir before retrying. The smoke check
likewise retries a few times before failing. Retry backoff is
`FR_INSTALL_RETRY_SLEEP` (default 2s; tests set 0). A persistent failure still
fails loud after the bounded attempts — retry is bounded, never an infinite
loop or a silent pass.

Failing tests first (`tests/integration/test_install_sh.py::
TestFrCliInstallResilience`), driven by a stateful `uv` stub that fails its
first install with the real ENOTEMPTY message and/or fails its first
`--version`:

- `test_retries_transient_enotempty_then_succeeds` — one ENOTEMPTY is retried,
  install ends rc 0.
- `test_retries_flaky_smoke_check` — a first failing `fr --version` is retried,
  not reported as "does not run".
- `test_gives_up_loudly_after_max_install_attempts` — a persistent failure
  still exits non-zero after retrying (bounded, surfaces the ENOTEMPTY).

## Rejected hypotheses

- **A concurrent `fr` process holding the env open** — plausible perturbation
  source, but the CWD-holder repro did not reproduce ENOTEMPTY; not the
  deterministic mechanism.
- **Stray untracked files (`__pycache__`, `.DS_Store`) blocking `rmdir`** —
  disproven: uv does a recursive remove and cleared them fine; also would not
  self-heal on Run 3.
- **Racing `uv` invocations** — disproven: uv serializes on a tool-dir lock.
