# Open-issue triage — derio-net/super-fr

**Date:** 2026-07-24
**Scope:** all 8 open GitHub issues, cross-checked against repo state at
`main` (v3.14.0 in this worktree; v3.15.0 installed per #399), the implemented
specs/plans archive (`docs/superpowers/implemented/`), and the two live plans
(`multi-backend-git-host-adapters`, `hermes-agent-compat`).

Method: for each issue, read the body + comments, then verified the claim
against current code and the specs/plans archive rather than trusting the
issue's own framing. Findings and the exact evidence are below.

## Status update — 2026-07-26

The 2026-07-24 triage below is kept verbatim as the original record. This
section reports what has since happened and triages the issues filed after it.
`main` has moved **3.14.0 → 3.18.1** in the interim.

### Outcome of the 2026-07-24 triage: 4 of 8 closed

| # | Now | How |
|---|---|---|
| 379 | **CLOSED** | Closed at triage time — already resolved by the merged 2026-07-14 migrate spec/code. |
| 399 | **CLOSED** | **PR #402 merged.** `down` now takes `branch: str \| None = None` and resolves the single active workspace ("multiple isolation workspaces — specify --branch" when ambiguous). Verified on `main`. |
| 387 | **CLOSED** | **PR #401 merged.** `branch_changes_present` gained per-added-line containment (`_branch_change_present_in_file`), replacing the whole-file compare. Verified on `main`. |
| 289 | **CLOSED** | **PR #409 merged.** Scoped as recommended: umbrella closed in favour of per-harness compat, spawning #410 (harness playbook) and #411 (shared `harness_sync` helper). |

The four remaining are unchanged and none is hand-closeable:

- **#276** — the fix exists as **PR #408**, deliberately a **draft**: its body
  carries an operator merge precondition (a week of clean bridge logs). It is
  also `CONFLICTING`/`DIRTY` and has not been touched since 2026-07-24 while
  `main` advanced, so it needs a rebase whenever the gate clears. Closes
  automatically on merge — do not close by hand.
- **#333** — still infra-blocked (Omni/cluster); PR #314 still draft +
  conflicting, untouched since 2026-06-21. Phase 5 is operator-owned.
- **#311** — still `deferred`; the pod-measurement gate is still unmet.
- **#363** — bot-managed digest; auto-closes at zero debt. Leave alone.

### New issues filed 2026-07-26

Both were filed from one live `/fr-goal` run in `derio-net/blog-craft` against
super-fr 3.18.1, and both are **real, root-caused, and load-bearing for
fr-goal's subagent design**. Their central claims were re-verified against
current code (see evidence below) rather than taken on trust.

| # | Verdict | Action |
|---|---|---|
| 420 | fr-phase-executor deadlocks under `isolation: "worktree"` | **Schedule first** — highest severity |
| 421 | Pipeline guard makes a second repo unreachable (blocks fr-goal §3) | Schedule — sibling of #420 |

**#420 — poisoned dispatch, nothing refuses it.** Dispatching
`super-fr:fr-phase-executor` *with* `isolation: "worktree"` triple-deadlocks:
the agent wakes in a separate locked worktree cut from `main` (so the spec/plan
on the feature branch are invisible and `fr pickup` is unsatisfiable), every
Bash command is denied by `fr-isolation-guard.sh`, and every Write/Edit is
denied by `fr-isolation-required.sh` (no `.fr-isolation` marker in a fresh
checkout, fail-closed). The dispatch *succeeds*, so fr-goal looks healthy —
this is the exact mirror of the bug `ensure-phase-executor-allowlist.sh`
already fixed, where the failure was silent degradation to inline execution.

The issue's follow-up comment settles the delivery question and should drive
the fix: `scripts/install.sh:501` already mutates
`~/.claude/hooks/agent-worktree-required.sh` on every install, so a **hook
backstop is universally deliverable**, whereas `agent-worktree-default.md` —
the doc actively instructing the harmful flag — is operator-owned, unversioned,
and has **no canonical copy in any repo** (confirmed: it is absent on this pod
too). Fixing the prose is structurally impossible; the hook is the primary fix,
and the SKILL/`description:` wording is belt, not braces.

**#421 — the guard's two escapes are mutually exclusive.** Verified in
`plugins/super-fr/hooks/fr-isolation-guard.sh` on `main`: the `cd` allowance
(line 58) defaults to `$HOME/.cache/fr/worktrees:/tmp:$TMPDIR` — another repo
is never an allowed target — and the `fr isolation` allowance (line 84) is
start-anchored `^[[:space:]]*fr[[:space:]]+isolation`, so a command that must
lead with `cd <other-repo>` can never match it. Since the harness reports the
*session* cwd regardless of any inline `cd`, a pipeline session in repo A
cannot start isolation in repo B — including via `fr isolation up`, the very
command the deny message recommends. This blocks **fr-goal §3** (cross-repo
specs), i.e. the multi-repo story is unreachable from the flow that defines it.
The issue also records a working circumvention (`cd /tmp && cd <other-repo> &&
…`), which should be deliberately closed or blessed rather than left to be
rediscovered under pressure.

**Not merge candidates.** #420 and #421 are siblings from one session and both
gate fr-goal, but they are distinct root causes in different hooks
(`agent-worktree-required.sh` dispatch-flag ordering vs
`fr-isolation-guard.sh` cd/anchor scoping). Fix them separately; #420 first,
since subagent dispatch is central to the current fr-goal design.

### Revised scheduling order

1. **#420** — hook backstop (universally deliverable) + SKILL §6 / `description:` wording + tripwire test.
2. **#421** — scope the deny by *target* repo, not just cwd; un-anchor or post-`cd` evaluate the `fr isolation` allowance.
3. **#410 / #411** — follow-ups from the #289 close-out.
4. **#276** — rebase + merge PR #408 once the bridge-log gate clears.
5. **#333 / #311 / #363** — external preconditions; nothing to do.

---

## Verdict table

| # | Title (short) | Label | Verdict | Action |
|---|---|---|---|---|
| 399 | isolation: bare `down` errors on hardcoded `vk-iso/work` | — | **Real bug, unscheduled** | Schedule — small, root-caused |
| 387 | verify-merge false negative on concurrent same-file merge | — | **Real bug, unscheduled** | Schedule — needs per-hunk fix |
| 379 | fr migrate v1-to-v2: spec-table / staging / UX gaps | — | **Resolved (shipped)** | **Close** |
| 363 | Acceptance debt | — | Bot-managed living digest | Leave — do not touch |
| 333 | Resume PR #314 (Infisical) once Omni/cluster back | blocked | Still blocked; note stale | Keep; refresh drift note |
| 311 | rtk incorporation into fr isolation | deferred | Gates unmet | Keep as-is |
| 289 | multi-agent support | needs-scoping | Partly overtaken by reality | Re-scope against OpenCode+Hermes |
| 276 | remove vk-spelling fallbacks | deferred | Actionable, code still present | Keep; ready pending one log check |

No two issues are true duplicates; no merge of issues is warranted (see
"Merge candidates" below).

---

## Close now

### #379 — fr migrate v1-to-v2 gaps — **RESOLVED, close**

All four items (create `## Implementation Plans` table; loud 3/5-column parse
warning; git-stage created/removed files; `--include-in-progress` skip hint)
were designed, planned, and merged as
`docs/superpowers/implemented/specs/2026-07-14-migrate-v1-to-v2-spec-table-bugs-design.md`
+ its plan folder — the spec's front-matter cites `Issue: derio-net/super-fr#379`
and its plan `03.yaml` / `_prose.md` reference the number too. The fixes are in
shipped code, not just the archive:

- `packages/fr/src/fr/migrate.py` — `_resolve_spec_file` (~L715) and the
  append-Implementation-Plans-row path (~L770) create the table when absent
  (Bug 1); staging of created/removed files (Bug 3).
- `packages/fr/src/fr/spec.py:131` — emits a warning naming the column count
  instead of silently dropping the row (Bug 2).
- `--include-in-progress` hint present in the migrate skip path (UX gap).

The archive convention (plans move to `implemented/` only after merge) plus the
in-code presence confirm this landed. **Recommend: close with a comment linking
the implemented spec.**

---

## Keep open — real work, needs scheduling

### #387 — verify-merge false negative on concurrent same-file merge

Confirmed still real against current code. The decider is
`branch_changes_present` at `packages/fr/src/fr/isolation/local.py:119-145`,
which uses **whole-file** comparison:

```
git diff --name-only <branch> <base_ref> -- <changed-files>
```

Any file listed as differing is reported "missing", so a concurrent PR that
touches the same file *after* the branch's own merge produces a false
`NOT verified`. The docstring (`local.py:128-130`) acknowledges this as an
intentional safety trade ("never a false 'verified'"), but the impact is real:
fr-goal step 9 treats a failed verify-merge as STOP-and-recover, which would
have produced a duplicate re-landing PR (the reporter worked around it by hand).
No implemented or planned spec addresses this — the nearest,
`implemented/specs/2026-06-20-fr-goal-merge-race-guard-design.md`, *establishes*
the whole-file approach rather than fixing it. **Recommend: schedule a fix —
per-hunk / per-added-line containment (re-apply branch hunks against origin/main
with fuzz, or assert each added line present) instead of whole-file equality.**

### #399 — bare `fr isolation down` errors on hardcoded `vk-iso/work`

Root cause is nailed down in the issue's own comment (the stale-registry-row
hypothesis was disproven): `packages/fr/src/fr/commands/isolation_cmd.py`
defines `DEFAULT_BRANCH = "vk-iso/work"`, and bare `down` falls back to that
constant instead of resolving the cwd worktree's branch — the fix `exec`
already received (see the ~L180 comment "resolve the active workspace instead of
a hardcoded vk-iso/work default"). Filed today, non-blocking (`down --branch`
works; `up` auto-reconciles). Bundles three asks: (1) bare `down` resolves from
cwd worktree, `--branch` stays the explicit override; (2) `fr isolation status`
should handle an absent worktrees dir instead of raising `FileNotFoundError`;
(3) the Bash-gate sentinel should clear at zero workspaces. **Recommend:
schedule — small, well-scoped, mirrors the existing `exec` fix.**

### #276 — remove vk-spelling dual-read fallbacks

Every fallback the issue lists **still exists** in code (verified):

- `vk-profiles.yaml` fallback — `packages/fr/src/fr/isolation/types.py:170-175`
- `.git/vk/isolation` legacy state dir — `types.py:78-79`, used in
  `delete_state`/`load_state`/`list_states` (`:97,:103-107,:113-117`)
- legacy `/.config/vk/secrets/` mount-follow warning —
  `packages/fr/src/fr/isolation/local.py:1024-1025`
- `VK_BRIDGE_*` env fallback — `packages/fr-vk/src/fr_vk/config.py:124-138`
- `_warn_legacy` call sites — `types.py:106,117,174`, `local.py:1025`

The version window is wide open (target was 3.2.0; `main` is now 3.14.0), and
the 2026-06-11 comment already cleared willikins#235. The one remaining gate is
operator-side: "zero `[fr] WARNING: legacy` lines in a week of bridge logs"
(the pod-log read in the comment). **Recommend: keep deferred, but it is
otherwise ready — one operator log-check unblocks a straightforward removal PR.
The `Keep forever` list in the issue (VibeKanban-product env names) still holds.**

---

## Keep open — correctly parked

### #333 — Resume PR #314 (Infisical secret provider) — **blocked**

PR #314 is still OPEN + draft; the blocker (frank-omni dead, no `kubectl`) is
infra, unchanged. One note in the body is now stale: it says `main` advanced to
3.5.0 with the branch ~9 behind/11 ahead — `main` is now **3.14.0**, so the
rebase-and-re-bump will be larger. The cross-conflict it flags (#330,
"enforce invariants over prose") **did merge** (2026-06-21), so that rework is
now on `main` and the "confirm #314 still composes with the hook" step is live,
not hypothetical. **Recommend: keep (blocked); refresh the version-drift line so
the pickup checklist isn't misleading when the cluster returns.**

### #311 — rtk incorporation into fr isolation — **deferred**

Seed spec `docs/superpowers/specs/2026-06-14-rtk-isolation-incorporation-design.md`
is present (planned, not implemented). All three decision gates (measure the
pod; allowlist scope; go/no-go) are still unmet — it explicitly is "not
scheduled" pending pod measurement. Nothing in the repo has changed the calculus.
**Recommend: keep as-is.**

---

## Re-scope

### #289 — multi-agent support — **needs-scoping, partly overtaken**

Filed 2026-06-09 proposing a *separate* project ("multi-fr?") to convert
harness-specific setups into a common `AGENTS.md` format. Since then reality
moved *inside* super-fr, not into a new repo:

- OpenCode adaptation shipped (`implemented/specs/2026-07-08-opencode-adaptation-design.md`
  + command support) — skills/rules now mirror to `.opencode/`.
- Hermes Agent (Nous Research) harness support merged (#393) with a live plan
  `docs/superpowers/plans/2026-07-23-hermes-agent-compat/`.
- super-fr already generates/consumes an `AGENTS.md` (this repo's own).

So the *goal* (harness-neutral skills) is being met incrementally in-repo; the
issue's *proposed shape* (a new multi-fr project + Clief-Notes folder concept)
is not what's happening. The one comment (`abkzkg-oss`, "Mnemo") is vendor
promotion, not signal. **Recommend: re-scope the issue to "harness-neutral
skill/rule story" and reconcile it against the OpenCode + Hermes work already
landed — or close it in favor of per-harness compat issues if the umbrella no
longer adds value. Needs an operator decision, not an autonomous close.**

---

## Leave untouched

### #363 — Acceptance debt

Auto-generated and upserted by the `acceptance-report` GitHub Actions workflow
(`_generated by fr acceptance digest`); it self-updates weekly and auto-closes
at zero debt. It mirrors the SessionStart nag. It is not a hand-triageable
issue — **do not close or edit manually.** The 13 skipped rows behind it are
tracked by the acceptance matrix, not by re-triage here.

---

## Merge candidates

None recommended. The two isolation bugs (#399 bare `down`, #387 verify-merge)
touch different files (`isolation_cmd.py` / registry resolution vs
`local.py::branch_changes_present`) and are independent fixes; bundling them
buys nothing and couples unrelated risk. #399 already internally bundles its
three closely-related sub-asks, which is the right granularity.

## Suggested scheduling order

1. **#399** — smallest, root-caused, mirrors an existing fix; low risk.
2. **#387** — real correctness bug in the fr-goal safety path; slightly larger
   (needs a containment heuristic + tests).
3. **#276** — mechanical removal, but hold for the one-week bridge-log gate.
4. **#333** — unblock only when Omni/cluster returns (external).
5. **#289 / #311** — operator scoping decisions, not implementation-ready.
