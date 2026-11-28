---
name: fr-debugging
description: >
  Debug a bug, test failure, or unexpected behavior INSIDE an isolated
  workspace and deliver a reviewed fix-PR. Wraps superpowers:systematic-debugging
  — enters fr-isolation first (reusing an active workspace, else a fresh fix
  branch), runs the four phases via the exec-bridge, autonomous to a PR with
  hard stops only at the genuine human checkpoints. Use in an fr-enabled repo
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

- **Already inside an active fr isolation workspace?** (e.g. a bug found mid-fr-goal implementation) — **reuse it.** The failing test + fix land on that feature's branch; a bug found while building a feature must not spawn a competing PR. Confirm with `fr isolation status`, then look for a cursor on the branch, `grep -l '^branch: <that branch>$' docs/superpowers/runs/*.yaml`: a branch that already has a run (a feature's fr-goal run) keeps it — start none (this check is yours: `fr run start` refuses only a second run of the same workflow) and let the host run's own steps carry the work; a branch with no run gets `fr run start fr-debugging --branch <that branch>`, and the run-step resolves of §3–§4 apply.
- **Cold start** (standalone bug, no active workspace): start the run, which ensures the workspace itself: `fr run start fr-debugging --branch fix/<slug>`. Name the branch for the bug now; the worktree, run, PR, and cleanup key off it. The run is the shipped `fr-debugging` shape — `debug`, `review`, `deliver` — so the PR's head carries a cursor whose `deliver` a batch driver can read. For a devcontainer profile, or to debug on the current branch by intent, bring the workspace up first (`fr isolation up --branch fix/<slug> [--profile <name>] [--base HEAD]`), then start the run on it. A cold-start `fix/<slug>` is cut from freshly-fetched `origin/<default>` (#322), so the fix is clean of whatever the base checkout is parked on. **No devcontainer profile → HARD STOP** — offer the fr-init interview; there is no unisolated fallback. (Under fr-goal: treat as a blocker — pause, fr-init, resume.)
- **Stealth (`mode=stealth <tracking-repo>@<branch>`, or from the tracking repo `mode=stealth target=<path>`):** add `--stealth <tracking-repo>@<branch>` (or `--target <path>`) to that `fr run start` (and to `fr isolation up`, if you bring the workspace up first). The debug journal and every fr artifact then live in the tracking repo, never in the target; push with `fr push`, open the one draft PR with `fr pr create` (a plain-summary body), and never write the target's forge (no label, comment or issue). Under stealth every code push asks: stealth forces `git.push: ask` and `git.pr: ask`, so push nothing before `deliver`, then `fr push` and `fr pr create` each ask for the operator's approval (a settle-fix push asks again). On a harness whose transcript fr cannot read, a stealth session cannot push or open its PR through fr: it stops at `deliver`'s open, and you report it there. **Where the files go (quiet and stealth).** Under the default `repo` placement fr's artifacts live in the checkout, at the `docs/superpowers/…` paths named here. Under quiet or stealth they do not: run `fr settings paths --shell` in the workspace and use its answers — `FR_SPECS_DIR`, `FR_PLANS_DIR`, `FR_PLAN_JOURNALS_DIR`, `FR_DEBUG_JOURNALS_DIR` and the rest — for every path a skill names below `docs/superpowers/`. They point into the repo's `fr` worktree (quiet) or the tracking clone (stealth), the two places outside the workspace where the edit gate lets you write. A file you write by hand there (the spec) is committed in that checkout, never in the product worktree, where `fr push` refuses it. fr's own commands (`fr plan create`, `fr journal add`, `fr run …`) already follow the placement.

From here on follow fr-isolation's exec-bridge discipline: read/edit files in
the worktree, run every command through `fr isolation exec -- …`. **Devcontainer mode:** `fr run` and `fr usage` run on the harness host — `fr isolation exec` refuses them and prints the host-side command; run that. A broken
environment is repaired with `fr isolation restart`, then `rebuild` (worktree, cursor and
uncommitted work kept), never `down --force`; a forced down preserves the run record, but the workspace and its uncommitted fix are gone.

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
(`journals/debug/<YYYY-MM-DD-slug>.md`) via `fr journal add --scope debug`, appended
**as you go** — not written up at the end. Continuous flush is the point: the
rejected-hypotheses trail is the most compaction-vulnerable artifact here, so
persist each verdict the moment you reach it. Each `fr journal add` is a one-entry
step record (the engine `fr run resolve --record` uses): validated, one commit, one line
back — so flushing costs one call per verdict. New debug journals live under
`journals/debug/`; pre-existing `debugging/*.md` prose stays put (no migration). A bug
fix does NOT enter the spec → plan pipeline, but the journal is durable and
searchable:

- `--kind repro` — the failing behavior + exact repro steps, on reproduce.
- `--kind hypothesis` / `ruled-out` — each hypothesis and its verdict as tested
  (the trail future debuggers would otherwise re-walk).
- `--kind root-cause` — the single confirmed cause ("X because Y").
- `--kind finding --state fixed` — the source change + the failing test pinning
  it.

**The run's steps (a run this skill started).** `fr run advance <run-id>` briefs `debug`: resolve it with a step record once the cause is confirmed, whose `emitted: {debug: <the journal's path>}` names the debug journal (the file must exist) — that path is how every later reader finds it — plus the entries not yet flushed. Then review: dispatch ONE reviewer (`superpowers:requesting-code-review`) over the fix, briefed to end with a fenced `review-findings` block of ids `d-r<k>` (`in` scope: this fix is wrong or incomplete; `out`: true but not caused by it), and receive it (`superpowers:receiving-code-review`): fix each in-scope finding with a test or refute it with reasoning, never drop it. Resolve `review` with its step record, the only route for the review entry: a `journal:` item of `kind: review` (the reviewer's entry), the findings, their resolutions and `evidence: {review: <that entry's id>, reviewer: <the reviewer's dispatch id>}`; it is refused while a `d-r<k>` finding is open.

## 4. Deliver

Verify first (`superpowers:verification-before-completion`: failing test now passes, no others broken). In a repo with `.fr/docs.yaml`, run `fr docs check` before opening the PR (`deliver` derives it too): a page covering a path the fix changed needs an edit, or its `reviewed` stamp updated when it is still true.
Open ONE PR via `superpowers:finishing-a-development-branch`, pushing with `fr push` and opening the draft with `fr pr create --title <t> --body-file <f>` — never `git push` or the forge CLI: they apply the repo's git policy (`git.*` in `fr settings show --json`; under `push`/`pr: ask` each refuses once, printing a request id and the `fr journal add --scope debug … --answered-by operator` line for this session's debug journal (the one journal the branch added): ask the operator with your question tool, the request id in the question text and the exact option `Approve <request-id>` (plus a decline) offered, record the line once they approve, then run the command again). The provisional body is derived from
`fr journal render --scope debug` (root cause + fix + the failing-test-first narrative).
Record the review through `review`'s step record (§3) alone — a `kind: review` journal item naming the findings raised or that none were; never `fr journal add --kind review`, which the gate refuses as evidence when added before the step opens; the cursor refuses `review` without a dispatched reviewer's entry or while a finding is open, and offers `deliver` only after it resolves.
Then `fr push` (`uv run fr push` in a worktree; on the host, never through `exec`) and confirm `git rev-list --count @{u}..HEAD` prints `0`. Every `fr journal add` is a local commit that nothing pushes, and the review record is written after the PR opened: left unpushed, the PR merges without it and the close-out's `verify-merge` refuses, when recovery already takes a second PR (#871). Then `fr pr settle --wait <s>`: exit 4 → fix by merging `origin/<base>` for a conflict, never rebase or force-push, or an ordinary commit for a red check, else what the printed line says, `fr push`, re-run; exit 75 → re-run; exit 2 → fix what it names and re-run, not a fix round; after three fix rounds stop and report. To relax a concern, add a debug-journal decision `settle-conflicts` or `settle-ci` (title the mode, body the reason), then `fr push` it.
Your last step is resolving `deliver` with a step record: `emitted: {pr: <the PR's url>}`, `evidence: {tests: <the log of the full suite you ran yourself after the resolve that opened `deliver`, or ci>}`; `docs` (`fr docs check`) and `settle` are derived, never passed, and a refusal names what to fix. It renders the PR body from the debug journal (in-scope and out-of-scope findings) to `docs/superpowers/runs/<run-id>.records/pr-body.md` and refuses until the live PR carries it, printing the command; an out-of-scope finding is refused until `fr journal file` defers it. No plan, so no `proportionality`. Then `fr push` the cursor commits and confirm `git rev-list --count @{u}..HEAD` prints `0`.
Once the PR is open, relay `closeout: fr pickup --branch <branch>` to the operator verbatim, as the last line of your final message with nothing after it — after merge, a NEW session runs it from the base clone (for a triage batch, the batch's driver, `fr triage batch drive`, starts that session through the batch's runner). The PR stays a draft: review approval and the ready transition are the operator's.
Stop — the operator merges. Cleanup: that close-out brief is the route, ending in `fr isolation down` — immediate teardown when this skill brought the
workspace up cold, otherwise `fr isolation gc` reaps the merged workspace automatically (fired on any up/down), so a missed `down` no longer leaks it.

## Scope notes

- Owns WHERE debugging happens and the autonomy contract — NOT the method.
  systematic-debugging's craft (Iron Law, four phases, red flags, supporting
  techniques) is delegated unchanged; restating it would duplicate a skill
  that evolves independently.
- When reusing a feature's workspace, the fix joins that branch/PR — do not
  open a second PR.
