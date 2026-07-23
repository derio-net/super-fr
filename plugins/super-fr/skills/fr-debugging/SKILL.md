---
name: fr-debugging
description: >
  Debug a bug, test failure, or unexpected behavior INSIDE an isolated
  workspace and deliver a reviewed fix-PR. Wraps superpowers:systematic-debugging
  — enters fr-isolation first (reusing an active workspace, else a fresh fix
  branch), runs the four phases via the exec-bridge, autonomous to a PR with
  hard stops only at the genuine human checkpoints. Use in a vk/fr-enabled repo
  (fr plans or devcontainer profiles present) whenever debugging starts — "this
  is broken", "the test fails", "find the root cause", "why is X happening" — or
  when fr-goal hits a bug mid-implementation.
---

# fr-debugging

`superpowers:systematic-debugging`, wrapped in isolation. The root-cause
investigation, the failing test, and the fix all happen in the isolation
workspace, so the base repo is never touched and the fix lands as a reviewed
PR — the debugging analogue of `fr-brainstorming` / `fr-goal`.

**Announce at start:** "I'm using fr-debugging to find the root cause in isolation."

This skill owns WHERE debugging happens (isolation) and the autonomy contract.
It delegates HOW — the Iron Law, the four phases, the supporting techniques —
to `superpowers:systematic-debugging`, invoked unchanged.

## 0. Isolation first — hard gate

Before ANY command — reproduction, evidence-gathering, instrumentation, reads
included; "just check X first" never reorders this:

- **Already inside an active fr isolation workspace?** (e.g. a bug found
  mid-fr-goal implementation) — **reuse it.** The failing test + fix land on
  that feature's branch and ride its existing PR; a bug found while building a
  feature must not spawn a competing PR. Confirm with `fr isolation status`.
- **Cold start** (standalone bug, no active workspace):
  ```bash
  fr isolation up --branch fix/<slug> [--profile <name>]
  ```
  Name the branch for the bug now (`fix/<slug>`); the worktree, PR, and
  cleanup key off it. A cold-start `fix/<slug>` is cut from freshly-fetched
  `origin/<default>` (#322), so the fix is clean of whatever the base checkout
  is parked on — to debug on the current branch by intent, add `--base HEAD`.
  **No devcontainer profile → HARD STOP** — offer the fr-init interview; there
  is no unisolated fallback. (Under fr-goal: treat as a blocker — pause,
  fr-init, resume.)

From here on follow fr-isolation's exec-bridge discipline: read/edit files in
the worktree, run every command through `fr isolation exec -- …`.

## 1. Debug

Run `superpowers:systematic-debugging` as written — the Iron Law (no fixes
without root cause), the four phases (root cause → pattern → hypothesis →
implementation), the red flags, and the supporting techniques
(`root-cause-tracing`, `defense-in-depth`, `condition-based-waiting`) all
apply unchanged. Phase 4's failing test uses
`superpowers:test-driven-development`.

## 2. Autonomy — autonomous, with two hard stops

Like fr-goal, run to a reviewed PR with no intermediate approval gates —
EXCEPT the two checkpoints systematic-debugging genuinely reserves for the
human. At each, stop, state what you found / tried, and ask (a wrong guess
shipped in a PR costs more than a paused run):

- **"I don't understand X" (Phase 3, step 4).** Investigation can't form a
  confident single hypothesis — non-reproducible, or genuinely ambiguous
  evidence. Pause and ask; don't guess.
- **3+ fixes failed → question the architecture (Phase 4, step 5).** Not a
  failed hypothesis but a wrong-architecture signal. After the 3rd failed fix,
  stop, present the pattern (each fix surfacing a new coupling/symptom), and
  ask before any 4th attempt.

Everything else — reading errors, reproduction, evidence instrumentation,
pattern analysis, single-hypothesis testing, the failing-test-then-fix, the
milestone review — runs autonomously.

## 3. Record — durable debug journal, flushed as you go

Record the investigation to the `debug`-scope journal
(`journals/<YYYY-MM-DD-slug>.md`) via `fr journal add --scope debug`, appended
**as you go** — not written up at the end. Continuous flush is the point: the
rejected-hypotheses trail is the most compaction-vulnerable artifact here, so
persist each verdict the moment you reach it. New debug journals live under
`journals/`; pre-existing `debugging/*.md` prose stays put (no migration). A bug
fix does NOT enter the spec → plan pipeline, but the journal is durable and
searchable:

- `--kind repro` — the failing behavior + exact repro steps, on reproduce.
- `--kind hypothesis` / `ruled-out` — each hypothesis and its verdict as tested
  (the trail future debuggers would otherwise re-walk).
- `--kind root-cause` — the single confirmed cause ("X because Y").
- `--kind finding --state fixed` — the source change + the failing test pinning
  it.

## 4. Deliver

Verify first (`superpowers:verification-before-completion`: failing test now
passes, no others broken). Open ONE PR via
`superpowers:finishing-a-development-branch`; the body is derived from
`fr journal render --scope debug` (root cause + fix + the failing-test-first
narrative). Stop — the operator merges. Cleanup: `fr isolation down` for immediate teardown when
this skill brought the workspace up cold — otherwise `fr isolation gc` reaps the
merged workspace automatically (fired on any up/down), so a missed `down` no
longer leaks it.

## Scope notes

- Owns WHERE debugging happens and the autonomy contract — NOT the method.
  systematic-debugging's craft (Iron Law, four phases, red flags, supporting
  techniques) is delegated unchanged; restating it would duplicate a skill
  that evolves independently.
- When reusing a feature's workspace, the fix joins that branch/PR — do not
  open a second PR.
