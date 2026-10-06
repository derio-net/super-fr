# Triage owns duplicates — design

Issue: derio-net/super-fr#971. Batch `triage-dedupe`, wave 4.

## 1. Goal

Nothing finds duplicate open issues today. Pipeline runs file their out-of-scope
findings straight to the forge, and #781 (check before filing) was closed as not
planned on purpose: a run must not search the backlog. So the search belongs to
an asynchronous sweep, and triage is that sweep. The fr-triage skill already says
"hunt duplicates", but only among the issues it is judging, and it records what it
finds as prose in `note`. Known duplicates went unnoticed for days: #594, #607 and
#631; #640 and #647; #724 and #725.

This change splits the job the way triage already splits work. The **engine**
proposes candidate groups from the facts, deterministically and with no model
call. The **skill** judges them. The verdict is **structural**: `duplicate_of` or
`distinct_from` in `judgements.yaml`. Forge actions stay printed commands for the
operator.

### Non-goals

- Searching the backlog from inside a pipeline run (#781 stays closed, and
  pipeline runs stay local).
- Any forge write. There is no `--yes` path: the sweep prints `gh` lines and
  never runs them.
- Duplicates in `origins.yaml` (#968, #970). Origins keeps its own prose
  `duplicate` category.
- Comparing against closed issues. Candidates are drawn from open issues only.
- A model in the engine. `no-claude-p-batch` holds: the judge is the agent
  session that is already running the triage loop.

## Requirements

R1. `fr triage check` reports a `duplicate candidates` set in its text output
and under `duplicate_candidates` in `--json`. Each candidate is a group of two or
more open issues in the scope, with every flagged pair inside it and that pair's
reasons.
R2. Candidate pairs come from four deterministic signals, and any one of them
flags a pair: close titles, shared rare code identifiers, a shared journal
finding id with a shared issue reference, or the same theme with fairly close
titles (thresholds in §3.B). Flagged pairs are joined into groups by
connectivity.
R3. A judgement may carry `duplicate_of: <key>` and `distinct_from: [<key>, ...]`
on every judgements schema. At load, fr refuses a malformed key, a self
reference, and an issue that names one key in both fields. A chain loads, and
`check` reports it in triage-pages-goal's `duplicate chained` set (§2.1).
R4. Candidates never include an issue judged `duplicate_of` anything, nor a pair
where either issue lists the other in `distinct_from`.
R5. `fr triage check` reports a `duplicates` set: every open issue judged a
duplicate, with its original's state (`open`, `closed` or `missing`, plus a
reason). For an open or closed original it prints the exact
`gh issue close <n> --repo <OWNER/REPO> --duplicate-of <original url>` command.
For a missing one it names the dangling key and prints no command. The set sits
beside triage-pages-goal's `duplicate target unknown`, which lists the same
missing keys without the reason or the command (§2.1).
R6. `fr triage collect` views every `duplicate_of` target that is not an open
issue, the same way it views a judged key, so a closed original reads `closed`,
not `missing`.
R7. A judged duplicate is never in the `unplaced` set.
R8. On the board, every judged duplicate leaves Backlog by tier and is listed under
Parked as "duplicate of <link>" (triage-pages-goal R11, §2.1). In addition, an
open original's row carries a `Duplicates` paragraph and a `+N duplicate(s)` tag
listing its judged duplicates: an open one with its close command, a closed one
with a `closed` tag and no command.
R9. The board has a "Possible duplicates" section listing the candidate groups
with each pair's reasons, and it says so when there are none.
R10. In loop mode, `fr triage batch drive` prints one `dedupe` line when it
observes a wave go from unfinished to finished while the candidate set is not
empty. Finished is main's one `finished_waves` predicate (§2.1). The line gives the count and the scope-qualified `fr triage check`
command. The driver never judges and never writes a duplicate to the forge.
R11. The fr-triage skill teaches the loop: read the candidates, judge each group
into `duplicate_of` or `distinct_from`, and leave the printed close commands to
the operator. The skill's prose-only "link duplicates in `note`" goes away.

## 2. Background (verified at f15bd482a)

- `fr.triage.model.Judgement` (`model.py:385`) is closed-world (`_Strict`,
  `extra="forbid"`). Its last additive field, `kind`, was added "optional on every
  schema" without a stamp bump (wave-driver R9, `model.py:394`), and so was
  `Judgements.features`. `judgements.yaml` is not an artifact kind: it lives under
  `$HOME/.cache/fr/triage/<scope>/`, and the artifact-versioning rule does not reach
  it.
- `fr.triage.check.classify` (`check.py:187`) is pure (facts and judgements in,
  sets out), and `check` always exits 0. `unplaced_issues` is `check.py:175`.
- `fr.triage.batch` already holds the reusable pieces: `theme_key` (`batch.py:505`,
  the shared case/whitespace normaliser from #724/#725) and `cited_paths`
  (`batch.py:594`). `suggest` (`batch.py:604`) is the precedent of an engine
  proposing groups that the agent accepts or ignores.
- `fr.commands.triage_cmd.collect_into` (`triage_cmd.py:178`) passes
  `judged=list(loaded.issues)` to `collect_facts_counted`, which views each judged
  key that is not open (`collect.py:335`, `_judged_elsewhere`). The driver
  re-collects through the same function on every pass.
- `fr.triage.render.render` (`render.py:754`) builds the tier sections from
  `judgements.issues`. `_row` (`render.py:338`) renders one `<details>` row with a
  detail block.
- `fr.triage.batch_drive.drive_pass` (`batch_drive.py:424`) is pure: a `Snapshot`
  in, ordered `Action`s out. `is_finished` (`batch_drive.py:354`) says a batch's
  archive PR has merged, and `archive` actions merge those PRs.
- `gh issue close --duplicate-of <number|url>` exists (gh 2.101.0, checked here). It
  sets GitHub's own duplicate state and links the issues.

### 2.1 Reconciled with triage-pages-goal (#976, merged mid-run)

#976 landed on main while this run was in review. Its R11 already ships part of
this design, so the two features are merged rather than layered (decision
`d-merge-976`):

- **One field.** `Judgement.duplicate_of` and `severity` come from #976. This
  change adds `distinct_from` beside them.
- **Chains** load. `check`'s `duplicate chained` set (#976) reports them. This
  spec's earlier load-time refusal is dropped, because it would have made that
  set dead and refused files #976 accepts.
- **Missing originals.** #976's `duplicate target unknown` set stays. This
  change's `duplicates` set adds the state, the reason and the close command.
- **Board.** #976 moves every duplicate off the tiers into Parked. This change
  keeps that and adds the `Duplicates` paragraph on an open original's row.
  "Possible duplicates" is a generated board section (`render.GENERATED`), so a
  board manifest can place it. One that omits it gets it appended.
- **Collect** viewing `duplicate_of` targets (R6) is the same rule in both. One
  implementation is kept.
- **Driver.** "Finished" is #976's `finished_waves(batches, stages)`, every
  batch terminal (cancelled, abandoned, or a close-out whose `archived` is set),
  read once into `Snapshot.finished`. This change's own predicate (§3.E as
  first written) is dropped, so the board, the history page and the driver
  cannot disagree. `unfinished_waves` is that set's complement over the state
  file's wave keys.

### Calibration (2026-10-06, this repo, 438 issues of which 61 open)

A throwaway prototype of §3.B's signals was run over every issue of
derio-net/super-fr. Over all 438 issues, it flagged #594–#607, #607–#631,
#640–#647 and #724–#725 directly, which is 4 of the 5 known pairs. The fifth
(#594–#631) joins its group through #607, so all three known groups are
recovered. Over the 61 open issues it flags 4 pairs (#454–#458, #601–#611,
#868–#869, #921–#991), each of which a judge can settle in a minute. Earlier,
looser variants flagged 46 open pairs. The rules that removed that noise are
§3.B's "not a file or module name" and "a finding id is not a word". The theme
signal added no pair here at 0.25. It stays because the issue asks for it and
it costs nothing.

## 3. Design

### A. Model (`fr/triage/model.py`)

```python
class Judgement(_Strict):
    ...
    duplicate_of: str | None = None     # a key; normalised
    distinct_from: list[str] = []       # keys; normalised, each once
```

Field validators apply `KEY_RE` and `normalize_key`, the same as `Pattern.ids`. A
`Judgements` model validator then refuses:

- a self reference in either field. The key is only known at the mapping level,
  so the check lives on `Judgements`;
- `duplicate_of: B` when `B` is judged and B's own `duplicate_of` is set. A
  chain has no single original to nest under, so it is refused at load rather
  than resolved at render;
- one key in both `duplicate_of` and `distinct_from`.

The fields are optional on every schema (1, 2 and 3), following `kind`. There is
no stamp bump, because no engine verb writes these fields (the agent does).
Decision `d-no-schema-bump`.

`Judgements.duplicate_targets() -> set[str]` returns every `duplicate_of` value.
`collect_into` adds these targets to the keys it views (R6), and the driver
inherits that through the same function.

### B. Candidates (`fr/triage/dedupe.py`, new, pure)

```python
@dataclass(frozen=True)
class Pair:
    a: str; b: str                      # keys, a < b
    reasons: tuple[str, ...]            # e.g. "title 0.62", "identifiers verify_tests_log"

@dataclass(frozen=True)
class CandidateGroup:
    keys: tuple[str, ...]               # sorted
    pairs: tuple[Pair, ...]             # sorted by (a, b)

def candidates(facts: Facts, judgements: Judgements) -> list[CandidateGroup]: ...
```

**Universe.** Open issues in `facts.issues` (PRs never), minus every key that
carries `duplicate_of` (R4). A pair is skipped when either side lists the other
in `distinct_from`. `distinct_from` is read symmetrically, so it only needs to
be written on one side.

**Text.** The title, plus the body as collected (at most 2,000 characters, the
same cap `collect` already applies).

**Signals.** A pair is flagged when any of these holds:

1. **title**: the Jaccard similarity of the two title word sets is ≥ 0.5. Words
   are lowercased `[a-z0-9_]+` runs, minus a short stop list. A word is kept when
   it is longer than two characters or is all digits, so the phase-tracking
   titles `…-0-agentic` and `…-1-agentic` differ (the rule the calibration ran).
2. **identifiers**: the two issues share at least 2 rare identifiers, or share 1
   rare identifier and have a title Jaccard ≥ 0.25. An identifier is the leaf of
   a code-shaped token, i.e. the last `::`, `/` or `.` segment with any `:<line>`
   suffix and `()` removed. A token is code-shaped when it is backticked (no
   spaces; contains `_ . / ( :` or camelCase) or is a bare snake_case word. The
   leaf must contain `_` and be at least 8 characters long. It is never a file
   name (a leaf with an extension) and never a module name. Module names are
   collected over the same text set (titles and bodies of the open issues in
   the universe) from every code-shaped token. For each token, every `::` or
   `/` segment except the last, cut at its first `.`, is a module name, and so
   is a file leaf's stem. A dotted leaf such as `fr.run.telemetry.x_y`
   contributes only `x_y`. Module names are excluded because they link issues
   that share a subsystem, not a defect. Rare means at most 3 open issues in
   the universe name it (sr-10).
3. **finding**: the two issues name the same journal finding id after the word
   `finding` (`finding r2-2`, ``finding `deliver-flaky-columns` ``), and both
   reference at least one same `#<n>`. A finding id contains a digit, or is
   backticked (``finding `deliver-flaky-columns` ``), so prose such as
   "finding out-of-scope" never matches (review p1-r2). Finding ids repeat across journals (`r2-2`), and
   the shared reference ties both issues to the same run.
4. **theme**: both are judged with the same non-empty `theme_key(theme)` and a
   title Jaccard ≥ 0.25.

The thresholds are module constants, named in one place. Reasons are written
deterministically: `title 0.62`, `identifiers a, b` (sorted, at most 3),
`finding r2-2 (#723)`, `theme isolation, title 0.27`.

**Groups.** Connected components over the flagged pairs, sorted by their
smallest key. The calibration in §2 is why components are used: #594 and #631
are joined only through #607.

The function reads no forge, no clock and no model, and it is quadratic in the
number of open issues (61 here, a few hundred for an org). Decision
`d-quadratic-ok`.

### C. `check` (`fr/triage/check.py`, `commands/triage_cmd.py`)

`CheckResult` gains two lists: `candidates: list[CandidateGroup]` and
`duplicates: list[Duplicate]`.

```python
@dataclass(frozen=True)
class Duplicate:
    key: str; title: str; url: str
    original: str                      # key
    state: Literal["open", "closed", "missing"]
    reason: str = ""                   # missing: why (unviewed reason / not in scope)
    command: str = ""                  # "" when missing
```

`duplicates` covers every open issue in the facts that carries `duplicate_of`.
The original is looked up through `facts.issues` (open, or closed after R6's
view). If it is not found, the state is `missing` and the reason is the first that
applies, checked in order (sr-7):
1. "a pull request, not an issue", when any PR list in the facts carries the
   key;
2. the `unviewed` reason;
3. the `skipped` reason;
4. "added since the last collect; run `fr triage collect` again", for a key in
   a collected repo;
5. "not in any collected repo".

`_unreachable_reason`'s "judged after…" wording is not reused, because a target
is not a judgement. The command is built from facts,
`gh issue close <n> --repo <OWNER/REPO> --duplicate-of <original url>`, so it
works across the repos of a group scope. A closed original gets the same
command: "close both" means the duplicate must close too.

`unplaced_issues` treats every judged duplicate as placed (R7).

Collect's view list becomes `judged ∪ duplicate_targets()`. `classify`'s
`unreachable` and `orphaned` sets still iterate judgement keys only, so an
unviewed target that is not judged never enters them. The stderr `unviewed`
report in `triage_cmd._report` and the `Unviewed` docstring are reworded from
"judged" to "judged or named by `duplicate_of`" (sr-8).

The text output adds two sections after `unplaced`. Under
**duplicate candidates**, each group prints its keys, then one indented line
per pair with its reasons. Under **duplicates**, each entry prints
`key → original (state)`, then the command or the reason. `--json` adds
`duplicate_candidates` and `duplicates`. `check` still always exits 0.

### D. Board (`fr/triage/render.py`)

- Every judged duplicate leaves the tier sections and is listed under Parked
  (#976, §2.1). An open original's row also gets a `Duplicates` paragraph:
  one line per duplicate, giving the key (linked) and the title. An open
  duplicate also gets its `gh` command in `<code>`, and a closed one gets a
  `closed` tag and no command (sr-6). The original's summary gets a
  `+N duplicate(s)` tag (R8).
- A new `Possible duplicates` section (`id="possible-duplicates"`, a generated
  section in `render.GENERATED`, collapsed like its neighbours) goes directly
  before "Backlog by tier". A group lists at most 10 pairs, then "+N more"; the
  `check` JSON keeps all of them (review p1-r8). It shows one block per group: the keys linked to
  their issues, then the pair reasons. With no candidates it reads "No candidate
  duplicates among the open issues." (R9).
- `render` stays deterministic: same inputs, same bytes. Snapshots
  (`fr/triage/snapshot.py`) are unchanged. The "Since last report" diff does not
  track candidates. Decision `d-no-snapshot`.

### E. Driver (`fr/triage/batch_drive.py`, `commands/triage_batch_cmd.py`)

The trigger is an **observed** transition, a wave going from unfinished to
finished. It is never inferred from a planned action: an `archive` action is a
plan, and its merge may still fail (spec review sr-2, sr-3).

- **Finished** is #976's `finished_waves(batches, stages)`, read once into
  `Snapshot.finished` (wave keys, `str(batch.wave)`), over every batch whatever
  the selection (§2.1). `unfinished_waves(snap)` is its complement over the
  state file's wave keys.
- **`Snapshot`** gains three fields:
  - `unfinished_waves: frozenset[str] | None = None` holds the waves that were
    unfinished on this process's previous pass, or `None` on its first pass.
  - `duplicate_groups: int = 0` is the candidate-group count.
  - `dedupe_command: str = ""` is the scope-qualified check command, for
    example `fr triage check --repo derio-net/super-fr`. The command builds it
    from its own scope args, because the pure pass has none (sr-5).
- **`drive_pass`**, as its last step, emits one action per wave `w` in
  `snap.finished & (snap.unfinished_waves or ∅)`, in numeric order,
  provided `duplicate_groups > 0`: `Action("dedupe", "", "<n> duplicate
  candidate group(s) after wave <w> finished; run `<dedupe_command>` to judge
  them")`. It uses a new `ActionKind` value, `dedupe`, which names no batch.
- **The command** carries forward to the next pass the waves this pass's
  snapshot found unfinished. `_act` handles `dedupe` before it resolves
  `action.batch`, returning the detail and acting on nothing (sr-1). In plan
  mode (no `--yes`), the line prints like any other action.

So loop mode reports each wave once, in the pass that first sees it finished.
When a pass finishes the drive (nothing left to do) while some wave that was
unfinished at its start is now finished, the loop runs one more observation
pass before it exits, so the last wave is reported too (review p1-r4).
A wave already finished when the process starts is never reported. `--once`
never reports, because every `--once` run is a first pass. This is stated
rather than worked around: `check` and the board always show the candidates.
Decision `d-driver-observed`.

### F. Skill (`plugins/super-fr/skills/fr-triage/SKILL.md`, and both mirrors)

- In the `check` list, add **duplicate candidates** (judge each group) and
  **duplicates** (report the printed close commands to the operator; fix a
  `missing` original's key).
- In the judging step: for each candidate group, re-read the issues and set
  `duplicate_of: <original>` on each duplicate, or `distinct_from: [<other>]`
  when they differ. The original is the issue with the fuller evidence, else the
  older one.
- In the `judgements.yaml` example, add both fields.
- Replace "link duplicates in `note`" with the structured fields.
- In "Forge actions are unrun commands", name `--duplicate-of`.
- Run `scripts/sync-opencode.py` and `scripts/sync-hermes.py`.

### G. Release

Change fragment `.changes/feat-batch-triage-dedupe.yaml`, `bump: minor`. This
adds a new check set, new judgement fields, a board section and a driver report.
No explainer describes triage (`docs/explainers/` has only fr-goal and
fr-isolation), so there is no explainer obligation.

## 4. Risks

- **Noise.** Signals that are too loose would turn the set into a chore. §2's
  calibration is the evidence that they are not loose here. `distinct_from`
  makes dismissing a pair a one-time cost.
- **Misses.** A duplicate described in completely different words is not found.
  That is accepted: the engine proposes, and the skill still compares each new
  issue against all judgements.
- **Older fr.** An older `fr` that reads a `judgements.yaml` carrying the new
  fields refuses it ("invalid judgements … extra inputs"). This is the same
  exposure `kind` accepted.

## 5. Test Plan

No deployment step. The release ships it. Post-merge, operator-driven:

1. `fr triage collect --repo derio-net/super-fr && fr triage check --repo
   derio-net/super-fr`: the `duplicate candidates` set lists the calibration
   pairs, or whatever the backlog holds by then, each with its reasons.
2. Judge one group `duplicate_of`, then re-run `check`. The duplicate leaves the
   candidates and appears under `duplicates` with a `gh issue close …
   --duplicate-of …` line. Nothing was written to the forge.
3. `fr triage render --repo derio-net/super-fr --open`: the duplicate is nested
   under its original, and "Possible duplicates" lists the rest.
4. Judge a duplicate of an issue that is already closed, then
   `fr triage collect` and `check`: the original reads `closed`, not `missing`
   (R6).

R3's load refusals and R10's driver line are covered at unit level only
(`drive_pass` is pure, and a live wave cannot be finished on demand). Their
rows say so.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-10-06-triage-dedupe | `derio-net/super-fr` | `2026-10-06-triage-dedupe` | — |

## 6. Acceptance rows

Born at brainstorm, presented at spec review: `triage-dedupe-candidates` (R1,
R2, R4), `triage-dedupe-judged` (R3, R5, R6, R7), `triage-dedupe-board` (R8,
R9), `triage-dedupe-driver` (R10) and `triage-dedupe-skill` (R11, added at
spec review, sr-12).
