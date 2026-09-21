# PR #508 — post-merge Test Plan, driven live (2026-09-21)

Items 13–18 of the two specs #508 shipped
(`implemented/specs/2026-09-20-dispatch-holder-identity-design.md` §6,
`implemented/specs/2026-09-20-unit-record-unification-design.md` §6), run against the
**installed** `fr 4.12.0` — not a worktree's `uv run fr` — on two harnesses, each driving one
throwaway one-phase `/fr-goal` (add a single scratch file). Neither run was pushed, delivered or
merged; both exist only to produce these records.

**Redaction, stated rather than hidden** (`.claude/rules/third-party-privacy.md`): agent and
session ids are cut to a six-character prefix, the home directory is `~`, and the OpenCode run's
model is written `<provider>/<model>`. Everything else is verbatim. Outputs are excerpts; `[…]`
marks a cut.

| item | harness | result |
|---|---|---|
| 13 — holder visible during a phase, pair after | Claude Code | PASS |
| 14 — the same record on a second harness | OpenCode | PASS, with caveat C1 |
| 15 — second `advance` refuses, naming the holder | both | PASS (OpenCode: see C1) |
| 16 — cost under each attempt, across abandon + re-dispatch | Claude Code | PASS |
| 17 — Stop hook: silent while held, blocks when idle, once per position | Claude Code | PASS |
| 18 — `review-phase` cannot be `done` without a review entry | both | PASS |
| `findings` gate (added by the #508 review) | both | PASS |

## Claude Code

Executor dispatched twice on purpose: a do-nothing dummy, abandoned, then the real one.

**13 / 15 — held, and the second `advance` refused (exit 2):**

```
implement: phase/1/implement-phase is ALREADY HELD by agent a63f02… (super-fr:fr-phase-executor, claude-code, claude-opus-5) (dispatched 2026-09-21T11:59:29+00:00) — not yet returned.
  Waiting on that agent — do NOT dispatch again.
  […]
```

`harness` was **detected**, not passed: the claim carried no `--harness`.

**13 / 16 — the cursor afterwards.** Two attempts on one unit, oldest first, each with its own
cost. Nothing was overwritten by the retry:

```yaml
      phase/1/implement-phase:
        state: done
        attempts:
        - dispatched: '2026-09-21T11:59:29+00:00'
          agent: a63f02…
          agent_type: super-fr:fr-phase-executor
          harness: claude-code
          model: claude-opus-5
          session: 145101…
          returned: '2026-09-21T11:59:53+00:00'
          outcome: abandoned
          estimate: {journal_entries: 1, journal_lines: 6, handoff_chars: 412, spec_bytes: 457, plan_bytes: 1284}
          measured: {input_tokens: 4, cache_creation_input_tokens: 33559, cache_read_input_tokens: 31950, output_tokens: 62}
        - dispatched: '2026-09-21T11:59:55+00:00'
          agent: af7cb1…
          […same type, harness, model, session…]
          returned: '2026-09-21T12:01:51+00:00'
          outcome: done
          estimate: {journal_entries: 1, journal_lines: 6, handoff_chars: 412, spec_bytes: 457, plan_bytes: 1284}
          measured: {input_tokens: 52, cache_creation_input_tokens: 69612, cache_read_input_tokens: 905879, output_tokens: 4778}
```

(The two `estimate`/`measured` maps are flowed onto one line here for width; the cursor writes
them as block mappings.) Worth reading twice: the **estimate** for the real attempt is ~500
tokens and the **measurement** is ~975,000. A do-nothing agent that replied with one word
billed ~65,000. That is the gap the spec said was "orders of magnitude and not comparable",
observed.

**17 — the Stop hook, three stops, from the harness's own event log:**

| when | run state | hook |
|---|---|---|
| 11:40:25 | parked at the `brainstorm` operator gate | silent |
| 12:00:20 | `phase/1/implement-phase` HELD by a working executor | silent |
| 12:02:33 | idle — `journal-check` advanceable, nobody working | **blocked** |
| 12:02:37 | same position, stopped again at once | silent (once per position) |

The block, verbatim:

```
fr run 2026-09-21-test-claude-holder-proof is idle — journal-check is advanceable and nobody is working on it (gh#518). Nothing is blocking it: run `fr run advance 2026-09-21-test-claude-holder-proof` now, in ~/.cache/fr/worktrees/super-fr/test__claude-holder-proof, and act on what it prints […]
```

**18 — no review entry (rc=2):**

```
phase/1/review-phase: refused — step 'review-phase' cannot be done without evidence (review).
  pass --evidence review=<journal-entry-id>, naming the `kind=review` plan-journal entry recorded for phase 1
  […]
```

**`findings` gate — review entry present, one finding deliberately left open (rc=2):**

```
phase/1/review-phase: refused — 1 finding(s) filed against phase 1 are still open: verification-dummy-finding.
  […]
  fr journal resolve --scope plan --slug 2026-09-21-claude-holder-proof --id verification-dummy-finding --state fixed --note "<what changed, and the test that pins it>"
```

The printed line was run as printed; the resolve then succeeded and the unit records
`evidence: {review: p1-review, findings: verification-dummy-finding}`.

## OpenCode

**14 — status from INSIDE the child, while it held the phase.** The child ran this as its
first act, because the orchestrator cannot: its task tool blocks until the child returns.

```
    phase/1/implement-phase: running
      HELD BY an unclaimed agent (opencode, <provider>/<model>) since 2026-09-21T11:35:28+00:00
```

After the return and the claim, and then the second `advance` (exit 2):

```
      HELD BY agent ses_f3… (opencode, <provider>/<model>) since 2026-09-21T11:35:28+00:00

implement: phase/1/implement-phase is ALREADY HELD by agent ses_f3… (super-fr:fr-phase-executor, opencode, <provider>/<model>) (dispatched 2026-09-21T11:35:28+00:00) — not yet returned.
```

The cursor's attempt carries the same keys as Claude Code's — `dispatched`, `agent`,
`agent_type`, `harness: opencode`, `model`, `returned`, `outcome`, `estimate` — and **no
`measured`** (no transcript reader exists for this harness; status says `not measured`, never
zero) and **no `session`**. `harness` was detected. `review-phase` recorded
`evidence: {review: feb138…, findings: none}`; a first resolve naming a nonexistent entry id
was refused and left the cursor untouched.

## Caveats and findings

**All five were fixed in #527** (4.13.1), each from a reproduced failure and a confirmed root
cause — trail in `docs/superpowers/journals/debug/2026-09-21-508-live-test-plan-defects.md`.
The text below is what was OBSERVED on 2026-09-21 and is left as written; each entry ends
with what became of it.

**C1 — on OpenCode the holder's ID is not knowable while the hold matters.** The orchestrator
reported learning the child session id "only when the task tool returned", from the return
value's task-id field. So during a phase, "who holds it" is answerable as *harness and model*
and never as *agent*; and the refusal of item 15 could only be exercised after the child had
already returned, where its "not yet returned" is true of the cursor and no longer of the
world. This is a property of a blocking dispatch tool, not a defect in fr, and the unclaimed
hold still refuses a second dispatch. The `parity.yaml` claim for this surface should say so.
*→ #527: it now does — its own row, `dispatch-holder-identity`; the skill and explainer no
longer describe the better case as the only one. The gap itself (a plugin-side claim on the
child's first tool call) is recorded there, not built.*

**C2 — `model` is derived, and reads as observed.** fr writes `model` from the tier binding
(`_resolved_model(repo, harness, tier)`); it does not observe what ran. For a dispatched
executor that is what was asked for. But OpenCode's `review-phase`, run inline by the
orchestrator, reads `the orchestrator (opencode, <provider>/<model>)` — the model the tier
WOULD dispatch. In this run the operator confirmed the orchestrator was on that same model,
so the value was true; the label is still stronger than the evidence behind it.
*→ #527: worse than a label. This repo's archived #508 cursor credits seven inline reviews to
a model that did not perform them. fr now derives a model only for work it dispatched.*

**C3 — a unit can be `done` with no attempt at all.** On the Claude Code run `review-phase`
was resolved without an `advance` ever briefing it, and fr accepted it: the unit has evidence
and no `attempts`, so no holder and no cost for the review. OpenCode's run advanced first and
has one. Not covered by any spec rule; recorded, not judged.
*→ #527: judged a defect. The flat path always refused an unbriefed step; the grouped path
now does too. The skill never said to `advance` before `review-phase` — which is how this
run came to do it — and now does.*

**C4 — `fr run start` cannot be fr-goal's first action from the base clone on Claude Code.**
With the pipeline sentinel live, `fr-isolation-guard.sh` allows only
`fr init|skills|--version` and `fr isolation …`, so `fr run start`, `fr run start --help` and
`fr models resolve` are all denied there. The skill calls `fr run start` "the first action"
that "enters isolation itself". The driving session had to `fr isolation up` first.
*→ #527: `fr run start`, and only it, is allowed. It had hidden because it bites only when the
repo already has some linked worktree; otherwise the orphan self-heal retires the sentinel
first — a separate open defect, recorded in the debug journal.*

**C5 — host and container share one `.venv`.** In the OpenCode run the child's `uv run fr`
(container, Linux) and the orchestrator's (host, macOS) each deleted and rebuilt the
worktree's `.venv` on every alternation — 31 packages, ~26 MB downloaded on the container
side. Unrelated to #508; observed because both sides ran in one transcript.
*→ #527: uv profiles now set a container-local, per-project environment. Proven live. Only
newly created containers pick it up; existing ones keep working as before and drain away as
their branches merge.*

## What this does not prove

One run per harness, one phase each, on one machine. Not exercised: picking a run up on
another host (`run-pickup-on-another-host`), OpenCode's `session.idle` continuation
(`run-idle-reprompt-opencode`), Hermes, or a multi-phase plan. Both of those rows stay
`not-implemented`.
