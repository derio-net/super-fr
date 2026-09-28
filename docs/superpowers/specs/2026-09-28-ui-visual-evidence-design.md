# UI evidence is visual: screenshots actually opened, every named interaction exercised

**Status:** design · **Date:** 2026-09-28 · **Closes:** super-fr#779
**Builds on:** `docs/superpowers/implemented/specs/2026-09-28-requirements-traceability-design.md`
(acceptance rows seeded from requirements, `verify: post-merge`, derived
evidence on `deliver`), the `tests=` provenance gate (debug journal 2026-09-21
C5, `packages/fr/src/fr/commands/run_cmd.py:2133`)

## Background

In take 9 of the super-fr-3 feature-C recording (fr 4.29.2), the brief asked for
a browser check of basket mode. The executor wrote a Playwright script and ran
it four times. The orchestrator ran it again after the review fixes, and the
closeout ran it once more. **No screenshot was ever opened.** The only attempt to
read one used the wrong directory and was not retried. The script never used
the − control, the slider drag, the 20 cap or the range labels. The scorer then
found four defects, each visible in one screenshot or one drag. The plain
comparison arm, given the same brief, opened six screenshots before delivering.

fr has nothing that asks for visual evidence. The skills have no browser-check
step (`grep -i "browser\|screenshot" plugins/super-fr/skills/*/SKILL.md` finds
nothing). No gate can tell a UI requirement from any other. Nothing reads
whether an image was ever looked at. A script's exit code satisfies everyone.

fr already reads the harness's session transcript to verify evidence. The
`tests=` gate ties a suite log to an orchestrator shell call
(`fr.run.telemetry.orchestrator_wrote_since`, `packages/fr/src/fr/run/telemetry.py:799`).
The `reviewer=` gate ties a review to a subagent this session dispatched
(`subagent_dispatch_since`, `:595`). Dispatched subagents' transcripts are
attributed file to file (`attribute_dispatches`, `:281`). The same machinery can
answer "was this image opened, and by whom".

## Decisions (operator, 2026-09-28)

| id | decision |
|---|---|
| d1-visual-row-flag | A user-visible UI requirement is marked on its **acceptance row** (a `visual` field beside `verify: post-merge`), not in the spec's Requirements grammar and not left to agent judgement. Plan phases already link rows (`acceptance: [ids]`), so fr knows which phases and which delivery owe visual evidence. |
| d2-transcript-verified | fr verifies from the transcript that each named screenshot was opened (an image read of the file) since the unit opened, in the transcript of the agent that owes it. Where no transcript is readable it is recorded as unobserved with a warning, as `tests=` is. |
| d3-reviewer-drives | At `review-phase` the dispatched reviewer drives the UI itself (or re-runs the capture script), opens its own screenshots and uses the named controls at their limits; reading the executor's screenshots is not enough. |
| d4-interactions-on-row | The visual row lists its named states and interactions (limits included, e.g. `20 cap`). The step record maps each to a screenshot taken after it; fr refuses a name with no screenshot. fr checks coverage, not what the image shows. |
| d5-fresh-at-deliver | `deliver` takes fresh screenshots of the delivered branch (review fixes land after the phase screenshots); phase evidence does not carry over. |

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | A user-visible UI requirement is identified structurally by its acceptance row, which names the states and interactions visual evidence must cover. | input "When a requirement or acceptance row is user-visible UI"<br>decision d1-visual-row-flag |
| R2 | Visual evidence names the screenshots the agent actually opened, one or more per named state, and fr verifies the opening from the transcript. A script's pass/fail alone does not count. | input "screenshots the agent actually opened (an image read of the file, observable in the transcript), for each state the requirement names"<br>input "rather than a script's pass/fail alone."<br>decision d2-transcript-verified |
| R3 | Every interaction the row names is exercised, limits included, and each has a screenshot showing its result. | input "the interactions the requirements name (each control used at least once, including its limits)"<br>decision d4-interactions-on-row |
| R4 | Visual evidence is owed at `implement-phase`, `review-phase` and `deliver`. At `review-phase` it is the reviewer's own: the reviewer drives the UI (or re-runs the capture) and opens its own screenshots, rather than reading the executor's. At `deliver` the screenshots are taken fresh, of the delivered branch. | input "evidence at implement/review/deliver names the screenshots the agent opened (observable in the transcript) and the controls it used at their limits."<br>decision d3-reviewer-drives<br>decision d5-fresh-at-deliver |
| R5 | When a script can capture the screenshots reliably, a capture script is preferred to agent-driven browsing, so each later stage re-runs it and opens its output. | input "if a script can be written to reliably retrieve the screenshots mechanically instead of driving via the agent, it should be preferred."<br>input "That way the token cost is only paid once and each rerun only costs a script invocation (and viewing the images of course)." |
| R6 | fr-execute and fr-goal carry a browser-check step that says all of this. | input "fr-execute / fr-goal say so in the browser-check step." |

## Design

### A. The `visual` acceptance row (R1)

`Row` (`packages/fr/src/fr/acceptance/model.py:55`) gains an optional field:

```yaml
- id: basket-mode-visual
  capability: ...
  acceptance: ...
  status: not-implemented
  visual:
    states: [accepted, not accepted, staff check, single article]
    interactions: ["− at 1", slider drag, 20 cap, range labels]
```

`Visual` is a closed model with two string tuples, `states` and `interactions`.
At least one is non-empty, and no name appears twice across both lists (a name
is what a screenshot's `shows` points at, so it must be unambiguous). `verify:
post-merge` and `visual` may coexist. Such a row owes its visual evidence after
merge, so the gates below skip it, as `requirement-rows` does.

Writers: `fr acceptance add --visual-state <s> --visual-interaction <i>`
(repeatable), and `AcceptanceItem.visual` in a step record
(`packages/fr/src/fr/record/model.py:142`). `fr acceptance set-status` leaves the
field alone. The three reports render unchanged.

Brainstorm writes `visual` on every row whose requirement is user-visible UI.
Its states and interactions are the ones the input and the answered questions
name, limits included. When the input names a control but not its limits, the
limits are a round question under fr-brainstorming's "always ask" rule.

### B. The `visual` record section (R2, R3, R5)

`StepRecord` (`packages/fr/src/fr/record/model.py:188`) gains an optional
`visual` section. It sits in the `evidence` section group of `_SECTION_FIELDS`,
so any step that may carry evidence may carry it:

```yaml
visual:
  - row: basket-mode-visual
    script: src/test/browser/basket-shots.cjs   # optional, see §D
    shots:
      - {path: /tmp/shots/accepted.png, shows: [accepted]}
      - {path: /tmp/shots/qty-at-20.png, shows: [20 cap, range labels]}
```

`shows` may name several of the row's states/interactions. A shot path may be
absolute or repo-relative, and it must have an image suffix (`.png`, `.jpg`,
`.jpeg`, `.webp`, `.gif`).

**Where shots live.** `fr run resolve` runs on the harness host
(`require_harness_host`, `packages/fr/src/fr/isolation/where.py:119`), and so
does the agent that opens the image. A shot must therefore be at a path the host
sees. A shot inside the repo must be git-ignored, so that screenshots can never
be committed (the gh#638 class). A shot inside `<run>.records/` is refused
outright, as `tests=` refuses a log there. In devcontainer mode a capture run
inside the container writes into a git-ignored directory of the bind-mounted
worktree, which both sides see. The container's `/tmp` is invisible to the
host, and that is where take 9's screenshots were lost. Elsewhere, a scratch
directory outside the repo (`$TMPDIR`) is simplest.

### C. The `visual` derived evidence (R2, R3, R4)

A new derived evidence name, `visual`, joins `_VERIFIABLE_EVIDENCE` and
`_DERIVED_EVIDENCE` (`packages/fr/src/fr/commands/run_cmd.py:1386-1406`). The
shipped `fr-goal.yaml` declares it on `implement-phase`, `review-phase` and
`deliver`. Adding an evidence name is not step drift (`_check_step_drift`,
`:756`, compares step ids only), so runs in flight keep advancing. No row carries
`visual` today, so they derive `none`.

**Owed rows**, computed when the unit resolves `done`:

- `implement-phase` / `review-phase` of phase N: the rows in phase N's header
  `acceptance:` (`PhaseHeader.acceptance`, `packages/fr/src/fr/types.py:111`)
  that carry `visual` and no `verify: post-merge`;
- `deliver`: the rows citing the run's spec (`rows_citing`,
  `packages/fr/src/fr/requirements.py:331`) that carry `visual` and no
  `verify: post-merge`.

No owed row → witness `none`, and nothing is asked of the record.

**Checks, per owed row, in order.** Each refusal exits 2 and names the row and
the fix:

1. The record's `visual` section has an entry for the row.
2. Every state and interaction of the row is named by at least one shot's
   `shows`, and `shows` names nothing the row does not declare (a typo would
   otherwise count as coverage of nothing).
3. Every shot file exists, is non-empty, has an image suffix, and sits where
   §B allows: not in `<run>.records/`, and git-ignored if inside the repo. At
   `review-phase` and `deliver` the file must also have been modified at or after
   the unit opened, with one second of slack as in `tests=`. That is how d3's
   "its own screenshots" and d5's "fresh at deliver" become mechanical. At
   `implement-phase` the executor's shots may predate the unit, because d2
   constrains only when they are opened.
4. **Opened.** The *witness transcript* holds an image read of each shot path
   issued since the unit opened. The witness transcript is:
   - `implement-phase`: the claimed holder's subagent transcript
     (`attribute_dispatches`), or the orchestrator's own stream when the phase
     ran inline (no holder);
   - `review-phase`: the transcript of the agent named by this unit's
     `reviewer` evidence (d3), never the executor's;
   - `deliver`: the orchestrator's own stream.
5. If the entry names a `script`, the file exists, and the witness transcript
   holds a shell call naming it since the unit opened. The stage that claims the
   script re-ran it. fr does not require the script to be committed: the input
   asks for a script to be preferred, not versioned.

**The transcript predicates.** Two new functions in `fr.run.telemetry`,
alongside `subagent_dispatch_since` and with its three-valued contract (a value
when found, `False` when the transcript was read and holds none, `None` when it
could not be read):

- `read_file_since(transcript, path, since) -> datetime | False | None`. The
  first `tool_use` in `transcript`, at or after `since`, whose tool name
  normalises to `Read` (`fr.usage.classify`'s alias table, so `read_file` and
  `view` count too) and whose input `file_path` (or `path`) resolves to the same
  file as `path`. "An image read" is a read of an image-suffixed path; fr does
  not inspect the tool result.
- `shell_named_since(transcript, name, since) -> datetime | False | None`. The
  first `Bash` `tool_use` at or after `since` whose command names `name`
  (`_names`' matching, `:788`).

Both take a transcript *file*, not the session, so the same predicate reads the
orchestrator stream or one subagent's file. `witness_transcript(env, step, unit)`
picks the file: the orchestrator's session, or the `Dispatch.transcript` of the
holder or reviewer found through `attribute_dispatches` (`:281`).

Unobservable, when no transcript is readable (a Claude Code session file fr
cannot find; OpenCode, whose session store fr already reads for `tests=`
(`_opencode_wrote_since`, `:1002`) but whose reader does not yet recognise a
file read; Hermes, which has no reader): checks 1–3 still apply, checks 4–5 are
skipped with a yellow warning, and the witness is marked `unobserved`. This is
the same contract as `tests=` (`_note_unobserved`).

The recorded witness is one line per row:
`<row>:<n-shots>:<sha256[:12] over the shot bytes, in path order>[:unobserved]`.
It is joined with `,` into the evidence value, and `none` when nothing is owed.
Like the other derived names, `--evidence visual=` is refused. A flag-form
resolve that owes visual rows is refused with a pointer to `--record`.

### D. The capture script (R5)

The script is preferred, not required. The skills say: when the UI can be driven
reliably by a script (a headless browser run that performs each named
interaction and writes a screenshot after it), write that script once, keep it
where every later stage finds it (the worktree is the natural place), and name
it in the record's `script`. Whether it is committed is the implementer's call. Every later stage re-runs
it (the reviewer, the executor after fixes, `deliver`) and opens the fresh
output. The token cost of driving the UI is then paid once, and a rerun costs
one command plus viewing the images. Check 5 keeps a named script honest: the
stage that names it ran it. Check 4 keeps it from becoming the pass/fail the
input rejects: its screenshots are still opened. Drive the UI by hand only for
what the script cannot reach reliably, and list those shots without a script.

### E. Prose: the browser check (R4, R5, R6)

- **fr-execute** gains a *Browser check* step for a phase whose `acceptance:`
  links a `visual` row. The step:
  - captures every named state and every named interaction at its limits,
    preferring a capture script (§D);
  - opens every screenshot with an image read and looks at it;
  - fixes what it shows;
  - fills the record's `visual:` section.

  A script's exit code is never the evidence. `fr-phase-executor`'s agent file
  says the same in its return contract.
- **fr-goal** §5 names it in the executor brief. §6 briefs the reviewer (d3):
  re-run the script or drive the UI itself, open its own screenshots, try each
  named control at its limits, check that the script covers every name the row
  declares, and return shot paths for the review-phase record. §8 re-runs the
  capture on the delivered branch and opens it (d5).
- **fr-brainstorming** §3 and fr-goal §1: a row for user-visible UI declares
  `visual` (§A). **fr-plan**: the phase that builds the UI links the row.
- Harness clauses (the neutrality tripwire): on Claude Code an image read is the
  file-read tool on the image path, which the transcript records. On OpenCode
  and Hermes it is their read tool. It is recorded as unobserved until fr's
  readers recognise a read there.

Mirrors regenerate with `scripts/sync-opencode.py` and `scripts/sync-hermes.py`.

### F. Harness parity

A new `parity.yaml` row, `visual-evidence` (`kind: interaction`), is paired to
no hook script. It is an evidence gate, like `deliver-tests-provenance`
(`packages/fr/src/fr/harness/parity.yaml:261`), and it uses that row's
vocabulary:

- claude-code `enforced`, with per-mode entries (devcontainer enforced because
  `fr run` resolves on the host, where the transcript is);
- opencode `advisory`: the session store is read, but no file-read detection
  exists, so checks 4–5 record as unobserved;
- hermes `advisory`: no reader, so the same;
- codex and copilot-cli `unsupported`.

### G. Artifact versioning

- **matrix 2 → 3** for `Row.visual`: stamp-only (`fr.artifacts.matrix_visual`,
  modelled on `matrix_verify.py`), additive, so no frozen model.
- **record 3 → 4** for `AcceptanceItem.visual` and `StepRecord.visual`:
  stamp-only (`fr.artifacts.record_visual`).
- This PR runs `fr migrate artifacts --yes` and commits the result.

A released `fr` resolves its **own** wheel copy of `fr-goal.yaml` before the
marketplace clone, so an older `fr` never meets a `visual` name it cannot verify.

### H. Docs

Check `docs/explainers/01-fr-goal.md` for a description of the evidence gates.
If it names them, add `visual` and regenerate the `.html` per
`explainers-currency.md`. Add a change fragment, `bump: minor`.

## Non-goals

- Judging what an image shows. fr checks that it was taken, is fresh, covers a
  name and was opened. Whether the UI is right stays the agent's and the
  reviewer's judgement.
- A PR-body section listing screenshots.
- Recognising a file read in OpenCode's session store or in Hermes. Both are recorded as
  unobserved (§C); a follow-up issue is filed for OpenCode, whose store fr already reads.
- Reaching a devcontainer app from the host (the take-9 port was not
  published). The capture script can run inside the container through
  `fr isolation exec`. It writes into a git-ignored directory of the
  bind-mounted worktree (§B).

## Test Plan

1. Unit: `Visual` validation (both lists empty refused, one empty list
   accepted, duplicate names refused), `Row.visual` round-trip,
   `fr acceptance add --visual-*`, `fr acceptance set-status` preserving
   `visual`, record `AcceptanceItem.visual`.
2. Unit: matrix 2 → 3 and record 3 → 4 migrations are registered, reachable
   along the whole chain, and stamp-only. `fr validate artifacts` passes on this
   repo after `fr migrate artifacts --yes`.
3. Unit: `visual` derivation. No owed row → `none`. Each of these is refused:
   a missing row entry, an uncovered name, an unknown name in `shows`, a missing
   or zero-byte shot, a shot in `<run>.records/`, a shot inside the repo that
   is not git-ignored, a non-image suffix, and a stale shot at `review-phase`
   and `deliver`. A stale shot at `implement-phase` is accepted, and a
   post-merge row is skipped.
4. Unit, transcript fixtures (`read_file_since`, `shell_named_since`,
   `witness_transcript`). The witness is the orchestrator stream for an inline
   `implement-phase` and for `deliver`, the holder's subagent file for a
   dispatched `implement-phase`, and the reviewer's file at `review-phase`. An
   image read in the witness transcript passes, and a read through an aliased
   tool name passes. Each of these is refused: the same read only in the
   executor's transcript at `review-phase`, a read before the unit opened, a
   named script that does not exist, and a named script with no shell call
   naming it. An unreadable transcript records `unobserved` with a warning.
5. Unit: `--evidence visual=` refused; the flag-form resolve owing visual rows
   points at `--record`.
6. Tripwires: skill mirrors in sync, harness-parity row present,
   tool-neutrality scan clean.
7. Post-merge, operator-driven: an fr-goal run on a UI feature with a `visual`
   row. The transcript shows the executor, the reviewer and deliver each open
   their own fresh screenshots, and the cursor records the witness.

## Implementation Plans

(filled by fr-plan)
