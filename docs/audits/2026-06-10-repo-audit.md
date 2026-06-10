# super-fr — Repository Audit & Improvement Plan (2026-06-10)

Auditor: principal-level repository audit, performed on an isolated worktree of
`origin/main` (branch `audit/repo-audit-2026-06-10`). No code was modified; this
report is the only artifact. Every finding is grounded in `file:line` citations
against that commit. Verification commands (`ruff check`, `ruff format --check`,
`mypy` strict, `uv run pytest`) were executed in the worktree and their results
are reported as observed, not assumed.

---

## 1. Executive Summary

**Health grade: A−**

super-fr is production-quality internal tooling. The core architecture — a pure
render → observe → diff pipeline with a *single* mutation path (`apply.py`),
dry-run by default, failure accumulation instead of fail-fast, and a documented
exit-code contract — is the kind of design most internal CLIs never get. Static
gates are genuinely green: `ruff check`, `ruff format --check`, and `mypy
--strict` across all three packages pass clean; 842 of 844 tests pass with
87.87% coverage (threshold 75%). Inline documentation is exceptional — modules
routinely cite the GitHub Issue that motivated a behavior (`#133`, `#246`,
`#286`, `#290`, `#294`), which makes archaeology cheap.

The deductions are concentrated in three themes, none of them architectural:

1. **Operator-environment leakage.** The repo presents as an installable plugin
   suite, but operator-specific names are baked into the `fr-vk` package and
   scripts: `VK_DERIO_OPS_PROJECT_ID` env vars, `willikins_*` Prometheus metric
   names, `~/.willikins-agent/` state directories, a `willikins|frank|content-factory`
   repo allowlist in a validator, and a cluster-local Pushgateway default URL.
   Anyone else installing this hits silent misconfiguration.
2. **Test hermeticity.** The suite's outcome depends on the ambient environment:
   2 tests fail on this pod because `VK_DERIO_OPS_PROJECT_ID` is set in the
   environment and the autouse fixture only sets the legacy fallback variable.
3. **Stale internal docs.** `CLAUDE.md` references pre-monorepo paths (`src/**`)
   and a script (`scripts/validate-skills.sh`) that no longer exists.

Top 3 risks (one line each):

- **R1 — Non-hermetic tests:** suite result depends on ambient env vars; CI is
  green but a configured operator pod sees 2 failures (`tests/conftest.py:16-26`).
- **R2 — MCP client robustness:** the JSON-RPC client doesn't match response ids
  to request ids and never drains stderr — a chatty or out-of-order VK MCP server
  produces silent mis-association or deadlock (`packages/fr-vk/src/fr_vk/_mcp_client.py:51,79-84`).
- **R3 — Latent dispatch bug in dead code:** `recover_orphan_card` passes the
  workspace branch where the VK API requires the *base* branch — documented
  elsewhere in the same package as a guaranteed 400 (`packages/fr-vk/src/fr_vk/workspaces.py` vs `dispatch.py`).

Top 3 opportunities: extract operator config from code (theme 1 below), make the
test suite hermetic (one fixture line), refresh `CLAUDE.md` to match the monorepo
layout. All are small, low-risk, high-trust-restoring changes.

---

## 2. Repo Map

```
super-fr/                          uv workspace monorepo, version 3.1.7 (lockstep)
├── pyproject.toml                 workspace root; ruff/mypy-strict/pytest config,
│                                  cov-fail-under=75 (pyproject.toml:44)
├── packages/
│   ├── fr/                        the CLI: plan-as-folder engine
│   │   └── src/fr/
│   │       ├── cli.py             typer app; exit-code contract 0/1/2/4/5 in docstring
│   │       ├── plan_ops.py        all plan writers (931 lines) — core 20%
│   │       ├── render.py / observe.py / diff.py   pure functional pipeline
│   │       ├── apply.py           THE single mutation path (209 lines)
│   │       ├── gh.py              gh CLI subprocess wrappers, retry/classify
│   │       ├── real_ghclient.py   GhClient impl (GraphQL closingIssuesReferences)
│   │       ├── commands/          typer subcommand modules (apply_cmd.py = gate logic)
│   │       ├── isolation/         worktree + devcontainer lifecycle (local.py)
│   │       ├── migrate.py (878)   v1→v2 plan migration   ← lighter-reviewed
│   │       └── plan/parser.py     v1 markdown parser (428) ← lighter-reviewed
│   ├── fr-dispatch/               runner-agnostic dispatch protocol
│   │   └── src/fr_dispatch/
│   │       ├── __init__.py        discover_plans + tick (270 lines) — core 20%
│   │       ├── protocols.py       Runner Protocol seam
│   │       ├── registry.py        entry-point registry (`fr.runners` group)
│   │       ├── lifecycle.py       FR_LIFECYCLE_HOOK_SCRIPT (30s timeout, swallow)
│   │       └── metrics.py         Pushgateway pusher (cluster-local default URL)
│   └── fr-vk/                     VibeKanban adapter
│       └── src/fr_vk/
│           ├── _mcp_client.py     JSON-RPC over stdio (235 lines)
│           ├── dispatch.py        canonical dispatch chain; VK wire contract docs
│           ├── workspaces.py      workspace ops + orphan reaping (355 lines)
│           ├── bridge_cli.py      cron tick daemon (538 lines) — core 20%
│           ├── runner.py          VkRunner adapter (operator constants live here)
│           └── config/slots/dedup/pr_state/pr_observe.py   defensive parsers
├── plugins/
│   ├── super-fr/                  7 skills + isolation-guard/pipeline-sentinel hooks
│   └── super-fr-dispatch/         2 skills
├── scripts/                       bump-version.py, install.sh (399), validate-plans.sh
├── tests/                         842 passing, 32 skipped, 87.87% cov; FakeGhClient/FakeMcpClient
├── .github/workflows/             ci.yml (lint/typecheck/test/version-sync), auto-tag.yml
└── .devcontainer/                 dogfooded isolation profiles (dev = least-privileged)
```

Core 20% receiving extra depth: `plan_ops.py`, `apply.py`/`apply_cmd.py`,
`gh.py`/`real_ghclient.py`, `fr_dispatch/__init__.py`, `bridge_cli.py`,
`_mcp_client.py`/`dispatch.py`/`workspaces.py`, the two plugin hooks, and
`install.sh`. **Lighter-reviewed areas** (read for shape, not line-by-line):
`migrate.py` (878 lines), `plan/parser.py` (v1 legacy, 428), `render.py` (559),
`spec.py`, `repair.py`, `archive.py`, SKILL.md prose contents, and the middle
section of `install.sh`.

---

## 3. Audit Report

Severity scale: **High** (correctness/operational risk now), **Medium**
(latent risk, portability, or trust erosion), **Low** (hygiene).

### 3.1 Findings

#### Medium

**M1 — Operator-environment leakage across the `fr-vk` package and scripts.**
The repo claims to be an installable plugin suite, but:

- `packages/fr-vk/src/fr_vk/runner.py` hard-codes
  `METRICS_NAMESPACE = "willikins_vk_bridge"`, `METRICS_JOB = "vk_issue_bridge"`,
  `HEARTBEAT_METRIC = "willikins_heartbeat_last_success_timestamp"`, and
  `_env_project_id()` reads `VK_DERIO_OPS_PROJECT_ID` / `VK_DERIO_OPS_PROJECT` —
  the env var *name* encodes the operator's board ("derio ops").
- `packages/fr-vk/src/fr_vk/bridge_cli.py:66-69` persists bridge state in
  `~/.willikins-agent/_seen_plans.json` and `_done_closed.json` — inconsistent
  with the `~/.cache/fr/` convention used by isolation, and named after one
  operator's agent.
- `scripts/validate-plans.sh` (≈line 74) hard-codes a spec-ref allowlist:
  `[[ "$spec_ref" != willikins/* ]] && [[ "$spec_ref" != frank/* ]] && [[ "$spec_ref" != content-factory/* ]]`
  — any other operator's repos fail validation by construction.
- `packages/fr-dispatch/src/fr_dispatch/metrics.py` defaults the Pushgateway URL
  to `http://pushgateway.monitoring.svc.cluster.local:9091` — a cluster-local
  address that only resolves inside one specific Kubernetes cluster.

Individually each is small; together they mean a second installer silently
misconfigures. Fix is mechanical: a config module / env prefix (`FR_VK_PROJECT_ID`,
`FR_BRIDGE_STATE_DIR`, `FR_METRICS_*`) with the current names kept as deprecated
fallbacks (the `bridge_env()` dual-read pattern in `config.py` already shows how).

**M2 — Test suite is not hermetic.**
`tests/conftest.py:16-26` has an autouse fixture that sets the legacy
`VK_DERIO_OPS_PROJECT` but never `delenv`s the canonical
`VK_DERIO_OPS_PROJECT_ID`. On this pod (where the canonical var is set in the
ambient environment), 2 tests fail reproducibly:
`tests/integration/test_bridge_project_id.py::test_tick_passes_project_id_to_create_issue`
and `::test_tick_dedup_passes_project_id_to_list_issues` — `_env_project_id()`
prefers the canonical var, so the fixture's value never reaches the code under
test. CI happens to be green only because GitHub runners don't set the var.
One-line fix: `monkeypatch.delenv("VK_DERIO_OPS_PROJECT_ID", raising=False)`.

**M3 — `CLAUDE.md` is stale against the monorepo layout.**
`CLAUDE.md:19-22` references `src/**` (code now lives under `packages/*/src`)
and claims CI runs `mypy src/` (CI actually runs
`mypy packages/fr/src packages/fr-dispatch/src packages/fr-vk/src`);
`CLAUDE.md:114-115` references `scripts/validate-skills.sh`, which does not
exist anywhere in the tree. Since CLAUDE.md is the standing instruction file
for every agent that touches this repo, staleness here propagates errors into
future automated work.

**M4 — MCP JSON-RPC client robustness gaps** (`packages/fr-vk/src/fr_vk/_mcp_client.py`):

- `_recv` (lines 79-84, used at line 139) returns the *next* queued message
  without matching the response `id` to the request `id`. The current VK MCP
  server is strictly request/response, so this works today — but any server
  notification or out-of-order reply silently mis-associates responses with
  requests.
- Line 51: the child is spawned with `stderr=subprocess.PIPE` but stderr is
  never drained. A chatty server fills the OS pipe buffer and the child blocks
  on a stderr write while the client blocks reading stdout — classic deadlock.
  Either drain in a thread or pass `stderr=subprocess.DEVNULL` / a file.
- `close()` (lines 231-235) calls `wait(timeout=5)`, which raises
  `TimeoutExpired` with no `kill()` fallback — a hung server turns shutdown
  into an unhandled exception.

**M5 — Latent 400 in `recover_orphan_card` (currently dead code).**
`packages/fr-vk/src/fr_vk/workspaces.py` (`recover_orphan_card`, ≈line 772
region) passes `branch=f"vk/gh-{issue_num}"` to `start_workspace`.
`dispatch.py` documents the VK wire contract explicitly: `branch` must be the
*base* branch (`"main"`) — "passing the would-be workspace branch (`vk/gh-{N}`)
returns 400". Grep confirms `recover_orphan_card` has no production caller
(tests only) and is gated behind `FR_BRIDGE_RECOVER_ORPHAN_CARDS=1`, so nothing
breaks today — but the first operator to flip that flag gets a guaranteed 400.
Fix the argument or delete the function.

**M6 — Isolation `down()` deletes state even when teardown fails.**
`packages/fr/src/fr/isolation/local.py` (≈lines 143-155): `down()` ignores the
return codes of `docker stop` / `docker rm` and `git worktree remove --force`,
then unconditionally calls `delete_state`. A failed worktree removal (e.g. a
process holding the directory) orphans the worktree on disk while dropping the
state record that would let `fr isolation` find and clean it later. Teardown
should at minimum refuse to delete state when the worktree still exists.

**M7 — `list_linked_prs` fails soft with no signal.**
`packages/fr/src/fr/real_ghclient.py:93-97` catches `GhError` and returns `[]`
with no log line. The inline comment justifies fail-soft (a PR-query blip
shouldn't kill `fr apply --dry-run`) — the *direction* is right, but with zero
output, "PR observations missing because GitHub hiccuped" is indistinguishable
from "no PRs exist", and label transitions that depend on PR state (fr:pr-ready)
silently don't happen. One `warn` line to stderr restores observability.

#### Low

**L1 — `_stage()` swallows git failures.**
`packages/fr/src/fr/plan_ops.py:57-66`: `subprocess.run(..., check=False,
capture_output=True)` — a failed `git add` (e.g. `.gitignore` shadowing,
index.lock) is silently ignored; the plan file mutates on disk but never stages.

**L2 — `tick()` writes before re-validating.**
`plan_ops.py:388-392`: the phase YAML is written, then re-parsed; a failed
re-parse raises *after* the mutated file is on disk (unstaged). Validate the
new document object before writing, or write to a temp file and rename.

**L3 — `_has_cycle` DFS is potentially exponential.**
`plan_ops.py:922-931`: carries ancestor sets and revisits nodes; fine at plan
scale (≤ dozens of phases), pathological on adversarial graphs. Standard
three-color DFS is the same line count.

**L4 — `_append_spec_row` substring idempotence.**
`plan_ops.py:314`: presence check is `` f"`{file}`" in text `` — a plan filename
that is a substring of another's (`plan.md` / `my-plan.md`) false-positives and
skips the append.

**L5 — Parameter passing via `os.environ` mutation.**
`bridge_cli.py:431-432, 468-472`: `FR_REPOS_DIR` is communicated to
`discover_plans` by mutating the process environment around the call instead
of passing a parameter. Works single-threaded; surprising and un-typed.

**L6 — Hard-coded `origin/main` in bridge self-healing.**
`bridge_cli.py:216-217`: `reset --hard origin/main` / `checkout -f main` assume
the default branch is `main`. Documented as an assumption, but a
`git symbolic-ref refs/remotes/origin/HEAD` lookup removes it.

**L7 — Cross-module use of private `_run_gh`.**
`real_ghclient.py:34,79,154,195,207` call `fr.gh._run_gh` (underscore-private)
from another module, and `view_issue` duplicates a variant of `gh.view_issue`.
Promote `_run_gh` to public (`run_gh`) or add the missing public wrappers.

**L8 — CI gaps (acknowledged).** `.github/workflows/ci.yml` has no Python
version matrix (only one interpreter is exercised despite `requires-python
>=3.11`) and no "did you bump the version?" guard on PRs that touch packages —
the latter is explicitly acknowledged as a follow-up in `CLAUDE.md:123-128`.

**L9 — Sentinel reads an undocumented hook field.**
`plugins/super-fr/hooks/fr-pipeline-sentinel.sh` notes the Skill-hook field
name is "not formally documented" and probes three spellings. Fragile by
nature; worth a canary test that fails loudly when Claude Code renames it.

### 3.2 Strengths (preserve these)

- **Single mutation path.** All GitHub writes flow through `apply.py` (209
  lines); `render`/`observe`/`diff` are pure. `_UnhandledMutationError`
  subclasses `AssertionError` so an unknown mutation type is a crash, not a
  skip. Failure accumulation reports *all* failed mutations per run.
- **Dry-run by default + reachability gate.** `fr apply` defaults to dry-run;
  `--yes --to <runner>` additionally requires the plan and spec to be reachable
  on `origin/HEAD` (`commands/apply_cmd.py`, `_check_plan_reachable_on_origin_head`),
  and refuses archived plans (#246).
- **Label-safety discipline.** Only `MANAGED_LABEL_PREFIXES` (`fr:`, `runner:`,
  `spec:`, `plan:`, `phase:`) plus bare `manual` are ever touched — operator
  labels are structurally unreachable by the diff engine.
- **Documented exit-code contract** in `cli.py`'s module docstring (0/1/2/4/5),
  honored by the command modules.
- **Protocol seams + fake-first testing.** `GhClient` / `Runner` / MCP client
  are Protocol-typed with `FakeGhClient` / `FakeMcpClient`; 842 behavioral
  tests, 87.87% coverage, mypy `--strict` clean across all three packages.
- **Operational scar tissue is encoded, not just remembered.** Bridge-owned
  checkouts with self-healing (#286), `skip_issue_create=True` after the
  2026-05-18 incident, PR-state sweep with a per-tick close cap of 50
  (`pr_state.py`), terminal-Done reconciliation (#294), flock tick lock,
  per-phase failure isolation in `fr_dispatch.tick`.
- **Version lockstep machinery.** `scripts/bump-version.py` + `version-sync`
  CI job + `auto-tag.yml` keep 3 packages and 2 plugin manifests in lockstep
  (all at 3.1.7, verified).
- **Dogfooded isolation.** The repo ships its own `.devcontainer` profiles,
  with `dev` least-privileged (`secrets: []`).
- **Security posture is sound** for the threat model: no secrets in tree, all
  GitHub auth delegated to `gh`, per-profile host-side secrets, deny-guard
  hooks with a 48h GC and a cd-transition allowance (#279).

---

## 4. Improvement Strategy

Four themes, ordered by leverage. Each has a done-signal.

**T1 — De-operator-ify the installable surface.** Introduce `FR_`-prefixed env
vars and configurable constants for: VK project id, bridge state dir, metric
namespace/job/heartbeat names, Pushgateway URL, and the validate-plans repo
allowlist. Keep current names as deprecated fallbacks via the existing
`bridge_env()` dual-read pattern. *Done when:* `grep -ri "willikins\|derio"
packages/ scripts/` returns only deprecation-fallback lines and CHANGELOG
entries.

**T2 — Make the suite hermetic.** delenv ambient `VK_DERIO_OPS_PROJECT_ID` in
the autouse fixture; sweep for other ambient reads (`FR_REPOS_DIR`,
`FR_BRIDGE_*`) and isolate them the same way. *Done when:* the suite passes
identically on a bare runner and on a fully-configured operator pod.

**T3 — Truthful internal docs.** Update `CLAUDE.md` paths to the monorepo
layout, delete or recreate the `validate-skills.sh` reference, and add the
missed-bump CI guard it already promises. *Done when:* every path and command
in CLAUDE.md executes successfully from a fresh clone.

**T4 — Harden the I/O edges.** MCP client (id-matching, stderr drain, kill
fallback), `list_linked_prs` warn line, isolation `down()` state-deletion
guard, `_stage()` check=True, fix-or-delete `recover_orphan_card`. *Done
when:* every external-process interaction either propagates failure or logs it.

**Deliberate non-fixes:**

- `migrate.py` / `plan/parser.py` (v1 legacy) — read-mostly migration code on
  its way out; don't invest beyond keeping tests green.
- `prompt.build_prompt` being unused in the VK flow — documented as reserved;
  leave it.
- GraphQL batching in `RealGhClient` — the module docstring already places it
  correctly ("if we ever need bulk reads"); no evidence of rate pressure yet.
- Python version matrix in CI — nice-to-have; single-interpreter risk is low
  for a tool the operator runs on one pinned runtime.

---

## 5. Task Plan

### Milestones

| Milestone | Goal | Tasks |
|---|---|---|
| **M0 — Quick wins** (≤ 1 day) | Restore trust signals | Q1–Q4 |
| **M1 — Hermetic & truthful** | T2 + T3 complete | 1.1–1.3 |
| **M2 — Portable** | T1 complete | 2.1–2.4 |
| **M3 — Hardened edges** | T4 complete | 3.1–3.5 |

### Task table

| # | Task | Theme | Effort | Risk | Depends on |
|---|---|---|---|---|---|
| Q1 | `delenv("VK_DERIO_OPS_PROJECT_ID")` in autouse fixture (`tests/conftest.py:16-26`) | T2 | XS | none | — |
| Q2 | Fix `CLAUDE.md` paths + remove `validate-skills.sh` reference | T3 | XS | none | — |
| Q3 | Add warn log to `list_linked_prs` fail-soft branch (`real_ghclient.py:93-97`) | T4 | XS | none | — |
| Q4 | `_stage()` → `check=True` with a clear error (`plan_ops.py:57-66`) | T4 | XS | low | — |
| 1.1 | Sweep tests for other ambient env reads; isolate via fixtures | T2 | S | low | Q1 |
| 1.2 | Missed-bump CI guard (CLAUDE.md:123-128 promise) | T3 | S | low | — |
| 1.3 | Canary test for the Skill-hook field name (L9) | T3 | S | low | — |
| 2.1 | `FR_VK_PROJECT_ID` (+ deprecated dual-read of `VK_DERIO_OPS_*`) | T1 | S | low | — |
| 2.2 | `FR_BRIDGE_STATE_DIR` default `~/.cache/fr/bridge/` with migration of `~/.willikins-agent/` files | T1 | M | med | 2.1 |
| 2.3 | Configurable metric names + Pushgateway URL (no cluster-local default) | T1 | S | low | — |
| 2.4 | Replace validate-plans.sh repo allowlist with a config file or env list | T1 | S | low | — |
| 3.1 | MCP client: match response id to request id (`_mcp_client.py:79-84,139`) | T4 | S | med | — |
| 3.2 | MCP client: drain or DEVNULL stderr (`_mcp_client.py:51`); kill() fallback in `close()` | T4 | S | low | 3.1 |
| 3.3 | Fix or delete `recover_orphan_card` branch arg (M5) | T4 | S | low | — |
| 3.4 | `down()` refuses `delete_state` when worktree still exists (`isolation/local.py`) | T4 | S | med | — |
| 3.5 | `tick()` validate-before-write; `_append_spec_row` exact-cell match (L2, L4) | T4 | S | low | — |

Effort: XS ≤ 30 min, S ≤ half day, M ≤ 2 days.

### Top-3 implementation sketches

**Q1 (hermeticity):** in `tests/conftest.py` autouse fixture, add
`monkeypatch.delenv("VK_DERIO_OPS_PROJECT_ID", raising=False)` before setting
`VK_DERIO_OPS_PROJECT`. Verify by running the suite with
`VK_DERIO_OPS_PROJECT_ID=bogus uv run pytest tests/integration/test_bridge_project_id.py`
— both currently-failing tests must pass.

**2.2 (bridge state dir):** add `state_dir()` to `fr_vk/config.py` reading
`FR_BRIDGE_STATE_DIR`, defaulting to `~/.cache/fr/bridge/`. On first access, if
the new dir lacks `_seen_plans.json`/`_done_closed.json` but
`~/.willikins-agent/` has them, copy them over and log a one-time migration
line. Replace the two literals at `bridge_cli.py:66-69`. Tests: tmp_path-based,
no home-dir touch.

**3.1 (MCP id-matching):** give `_recv` a `want_id` parameter; loop reading
messages, buffering any whose `id != want_id` (and discarding/logging
notifications without `id`), returning only the matching response. `_request`
passes the id it just allocated. Behavior for the current well-behaved server
is unchanged; out-of-order replies become correct instead of corrupting state.

---

## 6. Open Questions

1. **Is `fr-vk` meant to be installable by anyone, or is it explicitly the
   operator's adapter?** If the latter, M1/T1 shrinks to renaming the state dir
   and documenting the assumption — the env-var names stop being a defect.
2. **Is `recover_orphan_card` wanted at all?** It has no production caller and
   contradicts the documented VK wire contract. Delete vs. fix is a product
   decision, not a code one.
3. **Should the bridge support non-`main` default branches?** L6 is trivial to
   fix but only matters if a dispatched repo will ever use `master`/`trunk`.
4. **v1 plan format end-of-life:** `migrate.py` + `plan/parser.py` are ~1,300
   lines of legacy surface. Is there a date after which v1 plans are refused
   and this code is deleted?
5. **Coverage floor:** actual coverage is 87.87% against a 75% gate — is the
   gate intentionally slack (room for hard-to-test modules), or should it
   ratchet to ~85% to prevent regression?
