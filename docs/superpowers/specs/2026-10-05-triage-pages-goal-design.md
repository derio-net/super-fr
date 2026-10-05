# Triage pages: one goal per page, one home per fact, authored sections everywhere, driver exports the state

**Date:** 2026-10-05
**Issues:** derio-net/super-fr#970 (folds in #968 and #887)
**Supersedes:** wave-driver spec R20's "the three pages keep everything they show today"
(`docs/superpowers/implemented/specs/2026-10-02-wave-driver-design.md`). The section
order R20 set for the board still applies to its first screen.

## Background

`fr triage` renders three pages from the state directory `~/.cache/fr/triage/<scope>/`:

- the board, `triage.html`, written by `fr triage render` (`fr/triage/render.py`);
- the defect-origins page, `origins.html`, written by `fr triage origins render`
  (`fr/triage/origins.py`);
- the architecture page, `architecture.html`, written by `fr triage architecture render`
  (`fr/triage/architecture.py`).

None of them says what it is for, so facts end up on more than one page:

| Fact | Board | Architecture | Origins |
|---|---|---|---|
| Waves (tabs) | `_waves_section` | `_waves` | — |
| Needs you now | `_needs_section` | `_operator_actions` | — |
| Kind counts | closing-order chips | summary "defects" | — |
| Filings per day | — | `filings_chart` | `_chart` |
| Where the issues came from | — | `origin_counts` | `_counts` |

The architecture page also carries the snapshot timeline and four authored fragments, three
of them dated history. On 2026-10-05 it was 740 KB.

Only the architecture page can hold authored fragments, through `resolve_manifest` and
`validate_fragment` (`architecture.py:214`, `:237`). Hand-written analysis for the board or
the origins page has nowhere to live, and the next render loses it (#968). Even on the
architecture page, `render_architecture` (`:623`) puts every fragment after every generated
section, whatever the manifest says.

The data has gaps:

- Severity exists only for issues classified in `origins.yaml` (`Origin.severity`).
  `Judgement` has no severity.
- A duplicate is only a category value in `origins.yaml`, and nothing in `judgements.yaml`
  records one.
- The wave tables leave out each batch's tier (#887). Next up shows it, as
  `views._tier` (`views.py:254`).

The durable state is kept in the repo by hand. PR #969 adds `docs/triage/<scope>/` and
`docs/triage/sync.sh export|import`. `fr triage batch drive` writes `judgements.yaml` on
every pass, so the cache drifts ahead of the repo copy without anyone noticing. The driver
can merge PRs (`GhClient.pr_merge`), but it cannot open one: `GhClient`
(`fr/ghclient.py`) has no create. Archive PRs today are opened by a dispatched
close-out agent session.

## Requirements

R1. Every page the triage engine writes opens with one sentence stating the question the page answers. It also carries a navigation bar that links the four pages by their file names in the state directory: `triage.html`, `origins.html`, `architecture.html`, `history.html`.

R2. The board (`triage.html`) answers "What do I do next?". Its order is: the masthead, then Since last report, Needs you now, Next up, and Waves (unfinished waves only). Below those come collapsed sections: Backlog by tier (each tier its own collapsed section, Unranked included), Ranked features, Parked, Patterns, PRs and Batches. A collapsed section is closed by default, and its summary line shows its title and item count.

R3. Since last report is a table of transitions, one row per change. Its columns are: what changed (merged or closed, filed, batch stage, acceptance row, figure), the item, the value before and the value after. A batch in that table links to its card.

R4. Every wave table, on the board and on the history page, has a Tier column. It holds the lowest tier number among the batch's issue judgements (the value Next up shows), or `—` when none of them has a judgement.

R5. On the board every batch card is collapsed by default. The Batches section has a multi-select stage filter: one toggle for each derived batch stage present, all on at first. A card whose stage is toggled off is hidden. A link to a batch card anywhere on the board opens that card and the sections around it, then scrolls to it. Without JavaScript the cards stay closed but open on click, and the filter is not shown.

R6. The architecture page (`architecture.html`) answers "What is the system, and where does it hurt?". It shows, in order: a summary, the subsystem cards, the size table, then authored fragments. The summary gives source lines then and now across all subsystems, and the three subsystems with the most open defects, each linked to its card. The page no longer shows waves, operator actions, filings per day, where the issues came from, or the snapshot timeline. A manifest entry naming one of those sections is skipped with a note naming the page that now owns it, and is not reported as a missing fragment.

R7. The origins page (`origins.html`) answers "Where do defects come from, and what process change stops them?". It shows, in order: where the issues came from, the conclusion (each cause linked to the batches that address it), filings per day, median hours to fix, the PR leaderboards, then the issue table as a collapsed section.

R8. A new verb, `fr triage history render`, writes `history.html`, which answers "How did we get here?". It shows the snapshot timeline, then the finished waves as tabs (same table as the board), then authored fragments. A wave is finished when every batch in it is terminal. A batch is terminal when it is cancelled, has a close-out event with `archived` set, or has the derived stage `abandoned` (its PR closed without a merge). Finished waves appear on the history page and not on the board. The board preselects a wave only among the unfinished ones. The history page preselects the highest finished wave. Batch links on the history page point to `triage.html#batch-<id>`.

R9. All four pages take authored fragments from `<state dir>/<page>/manifest.yaml` and the fragment files beside it, where `<page>` is `board`, `origins`, `architecture` or `history`. One shared implementation serves all four. It keeps today's manifest rules (names, the generated-section names a page has, missing generated names appended) and today's `validate_fragment` refusals. A fragment is placed exactly at its manifest position, between generated sections if that is where it is listed. A manifest entry can also be a mapping, `{fragment: <file>, title: <text>, collapsed: true}`, which renders the fragment as a closed section titled `<text>`. A fragment listed in a manifest survives every render of its page.

R10. `origins.yaml` schema 2 adds three optional fields per entry:
- `duplicate_of`: an issue key, allowed only with `category: duplicate`;
- `fixed_by`: a PR reference;
- `introduced_in`: a PR reference, refused on a regression, whose `pr` already names the PR that broke it.

Schema 1 files still load. `fr triage origins check` reports a new set, "duplicate target outside the window": entries whose `duplicate_of` is not an issue in the collected origins facts. The origins issue table links a duplicate to its original and shows `fixed_by` and `introduced_in`.

R11. A judgement in `judgements.yaml` gains two optional fields, `severity` (`low`, `med` or `high`) and `duplicate_of` (an issue key). Both load on every schema, as `kind` does. `fr triage check` reports two new sets:
- "no severity": open, judged issues without a severity;
- "duplicate target unknown": `duplicate_of` names an issue that the forge would not show.

`fr triage collect` views every `duplicate_of` target in a collected repo, as it already views every judged key, so a closed original is known and is not reported. The board shows each backlog row's severity, and each Next up row shows the most severe severity among its issues. An issue with `duplicate_of` leaves Backlog by tier and is listed only under Parked, as "duplicate of <link>". It counts as placed for the unplaced set. The link goes to the original's URL from the facts. When the facts do not hold the original, the key is shown as plain text.

R12. `fr triage state export --to <dir>` copies a scope's durable state from the state directory to `<dir>/<scope>/`. `fr triage state import --from <dir> [--force]` copies it back. The durable state is: `judgements.yaml`, `origins.yaml`, `subsystems.yaml`, each page's manifest directory (manifest and fragment files), `snapshots/` and `authored-src/`. Facts files and rendered pages never travel. Import skips a state-directory file that is newer than the repo copy unless `--force` is given. Both verbs print every file they copied and every file they skipped.

R13. `.fr/triage.yaml` accepts an optional `export: {path: <repo-relative dir>}`. With it set, the driver acts on a single-repo scope once a wave of that repo is finished (R8) and `judgements.yaml` records no export for that wave. `fr triage batch drive --yes` then:
- exports the state (R12) into a worktree of `origin/<default>` under `<path>`;
- commits only `<path>/<scope>/`;
- pushes `chore/triage-state-wave-<N>`;
- opens a ready (non-draft) PR as the collecting login, which `pr_authors` therefore trusts;
- records `{wave, repo, pr}` under a new top-level `exports:` list in `judgements.yaml` (judgements schema 4).

If the export changes nothing, the driver records the export with no PR and opens nothing. A trusted open PR already on `chore/triage-state-wave-<N>` with no recorded export means a pass died between opening and recording. The driver records that PR (adopts it) and does not push again, but only when every file the PR changes lies under `<path>/<scope>/`. The export branch belongs to the driver, so a re-export force-pushes it.

On a later pass the driver merges the export PR under the same gate as an archive PR. The PR must be trusted, open, not a draft, with required checks green. Two conditions are added, because the driver auto-merges content into the default branch:
- The live head must equal the head SHA recorded in the export: the commit the driver pushed, or the head it adopted. `pr_merge` is called with that recorded SHA.
- Every file the PR changes must lie under `<path>/<scope>/`.

A commit pushed to the branch by anyone else therefore blocks the merge, with a warning, rather than riding into the default branch. The driver then records the merge. Other PR states each get a warning on every pass, and change nothing else:
- open with checks pending: the driver waits;
- open with checks failing, or untrusted: counted as blocked;
- closed without a merge.

An export that is recorded but not yet merged keeps `drive` running, the same way a close-out does. Without `--yes`, the pass prints the actions it would take. Without `export:` in the config, no export action exists. A `group` or `org` scope never exports. A repo of such a scope that opts in gets one warning per pass naming `--repo`.

R14. The `fr-triage`, `fr-origins` and `fr-audit` skills document the four page goals and the four fragment manifests. They state that hand-written analysis lives in fragments and never in a page edited after it is rendered. They also document `severity` and `duplicate_of` on judgements, the origins schema-2 fields, `fr triage history render`, `fr triage state export|import` and the `export:` config key.

R15. In this repo, `docs/triage/README.md` names the `fr triage state` verbs and `docs/triage/sync.sh` is deleted. This repo's `docs/triage/derio-net--super-fr/` manifests move the dated fragments (the 2026-10-02 closing order, the 2026-10-02 origins analysis and the history to 2026-10-02) from the architecture manifest to `history/manifest.yaml`. That manifest lists `timeline` and `finished-waves` first, then the three fragments, so R8's order holds under R9's placement rule. They also drop the architecture manifest's entries for sections the page no longer has. `.fr/triage.yaml` opts in with `export: {path: docs/triage}`.

## Design

### A. Page goals and shared chrome (R1)

`components.py` gains:
- `PAGES`: an ordered tuple of `(key, file, title, goal)` for board, origins, architecture
  and history;
- `page_header(current_key) -> str`: the nav bar, with the current page marked
  `aria-current="page"`, plus the goal sentence.

Each renderer calls it right after its masthead. All four pages share it, so one goal per
page is a fact in one place. `components.py` also gains `collapsed(id, title, count, body)`,
a `<details id=… class="fold"><summary>title <span class="count">n</span></summary>…</details>`
helper. R2, R7, R9 and the history page use it, so every collapsed section looks the same.

### B. The board (R2–R5, R11)

`render.render()` keeps its inputs. Its body becomes:

1. Masthead and `page_header("board")`.
2. Since last report, as a table (R3). `SnapshotDiff` (`snapshot.py:69`) holds
   pre-formatted strings today (`"bid: old -> stage"`, `"key closed"`), so it gains a
   structured field. `transitions: list[Transition]`, where
   `Transition(change, item, before, after, batch: str | None)`, is built by `diff_snapshots`
   beside the strings, from the same comparisons:
   - `change` is one of `merged-or-closed`, `filed`, `batch-stage`, `acceptance` or `figure`;
   - `acceptance` rows come from what `acceptance_moved` compares, never from
     `acceptance_note`, which stays the "not tracked" notice.

   The string fields stay, because the history timeline's panels render them. A new
   `_since_table(since)` draws the transitions. A row with `batch` set links to
   `#batch-<id>`, and "filed" and "merged or closed" rows leave before or after empty. With
   no transitions it shows one line, "Nothing changed since the last report."
3. Needs you now and Next up, unchanged except for a severity pill on Next up rows (R11).
   Their severity is the maximum over member judgements, ordered `high > med > low`.
4. Waves: the closing-order kind chips (`kind_counts`) still head the section. Below them
   come tabs over `views.waves(judgements)`, minus the finished waves (`finished_waves`, §D).
   `preselected_wave` gains an `among` parameter, and the board passes the unfinished keys,
   so the preselected key is always a tab (R8). `_wave_table` gains `Tier` after `Batch`
   (R4). It is computed by the existing `views._tier`, renamed to the public
   `views.batch_tier` because two modules now call it. If every wave is finished, the
   section reads "Every wave is finished: see the history page." and links there.
5. Collapsed sections, each through `collapsed(...)`: Backlog by tier (one nested collapsed
   section per tier, and Unranked), Ranked features, Parked, Patterns, PRs, Batches.
   The existing backlog `FILTER_BAR` (search, sort, chips) moves inside Backlog by tier, at
   its top, beside the rows it filters. Backlog rows gain a severity pill, or `—`.
6. Batches. A stage filter of checkboxes, one per `BatchStage` present, is rendered `hidden`
   and unhidden by script, the same no-JS rule `tabs()` uses. Each `_batch_card` becomes a
   `<details id="batch-<id>" data-stage="<stage>">`. A small `FOLD_SCRIPT` does two things:
   - it toggles `hidden` on cards by `data-stage`;
   - on `hashchange` and on load, it opens the target `<details>` and every ancestor
     `<details>`, then scrolls the target into view.

   The merge-order list stays in the Batches section.

Parked (R11): issues with `kind: parked`, plus open issues whose judgement has
`duplicate_of`. Those issues are left out of the tier sections. A duplicate row reads
"duplicate of <link>". The link uses the original's `url` from the facts, or plain text when
the facts do not hold it. `collect` adds every `duplicate_of` target in a collected repo to
the keys it views, beside the judged keys (`collect.py`). The unplaced set in `check.py`
treats an issue with `duplicate_of` as placed.

### C. Fragments: one shared module (R9)

A new `fr/triage/fragments.py` moves `validate_fragment`, `_Checker` and `resolve_manifest`
out of `architecture.py` and generalises them:

```python
@dataclass(frozen=True)
class Entry:
    name: str             # a generated-section name or a fragment file name
    title: str | None     # mapping entries only
    collapsed: bool       # mapping entries only

@dataclass(frozen=True)
class Resolved:
    order: list[Entry]
    fragments: dict[str, str]
    missing: list[str]
    appended: list[str]
    moved: dict[str, str]      # manifest entries naming a section another page now owns

def resolve_manifest(page_dir: Path, generated: Sequence[str],
                     moved: Mapping[str, str] = {}) -> Resolved: ...
def splice(resolved: Resolved, generated: Mapping[str, Callable[[], str]]) -> list[str]: ...
```

- `resolve_manifest` reads `<page_dir>/manifest.yaml`. Entries are a string, or a mapping
  with `fragment` and optional `title` and `collapsed`. Unknown keys are refused, and a
  mapping naming a generated section is refused. With no manifest, the order is `generated`.
- A name in `moved` (R6) is recorded there, not in `missing`. The command prints
  "manifest names `<x>`, which is now on the `<page>` page" and adds it to the page's notes.
- `splice` walks `order` once. A generated entry becomes its builder's HTML. A fragment
  entry becomes `<section class="fragment" data-fragment=…><div class="scroll">…</div></section>`,
  wrapped in `collapsed(...)` when the entry asks for it. Fragments therefore interleave
  (R9).
- Nothing outside `fr/triage` imports these. `architecture.py` keeps no aliases, and the
  manifest and fragment tests in `test_triage_architecture.py` move to a new
  `test_triage_fragments.py`, rewritten for `Entry` and the interleaved order.

Each page declares its `GENERATED` tuple:
- board: `since`, `needs`, `next-up`, `waves`, `backlog`, `features`, `parked`, `patterns`,
  `prs`, `batches`;
- origins: `origin-counts`, `conclusion`, `filings-per-day`, `time-to-fix`, `leaderboards`,
  `issues`;
- architecture: `summary`, `subsystems`, `size-table`;
- history: `timeline`, `finished-waves`.

The architecture page's `MOVED` map is:
- `waves`, `operator-actions`: board;
- `filings-per-day`, `origin-counts`: origins;
- `timeline`: history.

The masthead and `page_header` sit outside the manifest, always first. The board's
`FILTER_BAR` belongs to the `backlog` section, and its stage filter to `batches`.

A manifest that lists fragments but omits a page's generated names gets those names
appended after its entries, as today. A manifest that wants generated sections first must
therefore name them. R15's history manifest does this.

### D. Finished waves, one predicate (R8, R13)

`batch_drive.finished_waves(batches, stages) -> frozenset[str]` sits beside
`closeout_event` (`batch_drive.py:338`). It returns the wave keys whose every batch is
terminal: derived stage `cancelled` or `abandoned`, or a `closeout_event(batch)` whose
`archived is not None`. `stages` maps batch id to `derive_batch_stage(batch, facts)`, which
the driver `Snapshot` already carries (`Snapshot.stages`). `views` re-exports the function
and calls it with stages derived the same way, so the board, the history page and
`drive_pass` share one predicate. `views` already imports `batch_drive`, so the predicate
lives there, not in `views`, to keep imports one-way. Unwaved batches never make a finished
wave.

`preselected_wave(judgements, among=None)` restricts its pick to `among` when it is given.
The board passes the unfinished keys, and the history page the finished ones. Among those,
it picks the highest wave with a batch neither merged nor cancelled, else the highest. For
history, that is always the highest finished wave.

### E. Architecture and origins (R6, R7, R10)

**Architecture.** Its `GENERATED` shrinks to `summary`, `subsystems` and `size-table`. The
`_timeline`, `_waves` and `_operator_actions` sections leave the module: the timeline moves
to `history.py`, and the other two are already the board's. `_summary` is rewritten:
- the first figure is lines then and now, summed over `measured`;
- then a "Where it hurts" list: the three subsystems with the most open issues of
  `kind: defect` (ties broken by total open issues, then by name), each linked to
  its card, which gains an anchor `id="subsystem-<slug>"` (cards carry none today);
- with no measurement, the line figures read `—`.

`render_architecture` loses its `origins_facts` and `origins` parameters, and the command
stops loading them.

**Origins.** `render_origins` builds its body through `splice` with the origins `GENERATED`
order (R7), wrapping the issue table in `collapsed(...)`. Schema 2 (R10):
- `SCHEMA` (`origins.py:53`) stamps both `origins-facts.json` and `origins.yaml` today. It
  splits into two constants:
  - `FACTS_SCHEMA = 1`, used by `write_facts` and `load_origins_facts`, which are unchanged;
  - `CLASSIFICATION_SCHEMA = 2`, with `load_origins` accepting 1 or 2.
- `Origin` gains `duplicate_of: str | None`, `fixed_by: str | None` and
  `introduced_in: str | None`. Validators refuse `duplicate_of` without
  `category: duplicate`, and refuse `introduced_in` on a regression. `duplicate_of` is
  normalised with `normalize_key`.
- `OriginsCheck` gains `duplicate_outside: list[str]`, and `check` prints it as its third
  set.
- The issue table's "Related PR" cell adds `introduced in …` and `fixed by …` lines when
  they are set. The Category cell for a duplicate links its original: to its table row
  (each row gains `id="origin-<key>"`; rows carry none today) when the original is in the window. When it is outside the window but in
  the same repo, the link is the duplicate's own `url` with its number replaced. Otherwise
  the key is plain text.

### F. History page (R8)

`fr/triage/history.py`'s `render_history(facts, judgements, *, snapshots, resolved, notes)`
builds:
- the snapshot timeline, moved from `architecture.py` unchanged;
- `finished-waves`: `tabs("history-wave", …)` over the finished waves, each a `_wave_table`
  with batch links absolute to `triage.html#batch-<id>`;
- the history manifest's fragments.

`commands/triage_history_cmd.py` adds `fr triage history render [--repo|--org|--dir] [--open]`,
registered beside `origins` and `architecture` in `triage_cmd.py`. It reads facts,
judgements, `stored_snapshots` and `history/manifest.yaml`, and writes
`<state>/history.html`. `triage` is already in `READ_ONLY_COMMANDS`, so the new verb needs
no exemption change.

### G. Judgements fields and schema 4 (R11, R13)

- `Judgement.severity: Severity | None = None` and `Judgement.duplicate_of: str | None = None`
  load on every schema, the precedent `kind` set. `duplicate_of` is normalised like issue
  keys, and a judgement naming its own key is refused.
- `JUDGEMENTS_SCHEMA` becomes 4. `JUDGEMENTS_READS` (`model.py:46`) and
  `Judgements.schema_` both gain 4.
- Schema 4 adds a top-level `exports: list[Export]`, where
  `Export(wave: str, repo: str, at: AwareDatetime, pr: int | None = None, head: str | None = None, merged: bool = False)`,
  where `head` is the SHA the merge is pinned to (R13).
  `at` is when the export was recorded, typed like the batch events' timestamps. The
  validator that ties schema-3 events to schema 3 gains the same rule: `exports` requires
  schema 4.
- The one writer (`batch.py`) writes `schema: 4`, as it writes 3 today. `save_batches`
  rewrites only the `schema:` line and the `batches:` section, so a sibling
  `save_exports(path, exports)` replaces the top-level `exports:` section. It uses the same
  `_replace_top_level` and the same refuse-or-restore discipline. `_Driver` appends an
  export through a `_record_export` helper beside `_append` (`triage_batch_cmd.py:2140`).
- `check.classify` gains `no_severity` and `duplicate_unknown`. `check` prints them as
  sets; it still always exits 0.

`judgements.yaml` lives in the triage state directory, not in a registered artifact kind
(`fr.artifacts.registry`), so the artifact-versioning rule's migration obligations do not
apply. The schema field is the file's own reader contract, as with schemas 2 and 3.

### H. State export and import (R12)

`fr/triage/state_sync.py`:

```python
DURABLE_FILES = ("judgements.yaml", "origins.yaml", "subsystems.yaml")
DURABLE_DIRS = ("board", "origins", "architecture", "history", "snapshots", "authored-src")

def export_state(state_dir: Path, dest_root: Path) -> SyncReport: ...
def import_state(src_root: Path, state_dir: Path, *, force: bool) -> SyncReport: ...
```

- Copies use `shutil.copy2` (mtime preserved), skip `__pycache__`, and never delete a
  destination file.
- A page directory travels whole, so fragments built by `authored-src/build.py` travel too.
  That is harmless: they are rebuilt from their sources before a render.
- `SyncReport(copied, skipped)`. Import skips a destination file whose mtime is newer than
  the source unless `force`.
- The CLI is `fr triage state export --to <dir>` and `fr triage state import --from <dir>
  [--force]`, with the usual `--repo|--org|--dir` scope options. `<dir>/<scope>/` is the
  repo-side root.

### I. The driver exports a finished wave (R13)

**Config.** `TriageConfig.export: ExportConfig | None = None`, where `ExportConfig(path: str)`.
The path must be relative, with no `..` and no leading `/`, else it is refused at load.

**Decision (pure).** `Snapshot` gains:
- `export_path: dict[str, str]`: repo to path, from config, for single-repo scopes only;
- `exports: list[Export]`;
- `export_prs: dict[tuple[str, str], LivePr]`, keyed `(repo, wave)`. It holds the live PR of
  each recorded, unmerged export. For a finished wave with no recorded export, it holds the
  open PR on `chore/triage-state-wave-<N>`, if any (`list_prs_by_head`). `LivePr` carries
  `trusted`, the checks and the head, as for archive PRs.
- `finished: frozenset[str]`: `finished_waves(batches, stages)`, computed once.

`drive_pass` adds a step after archive (step 3b). For each repo with `export_path` and each
finished wave that has no merged export:

| Recorded export | Live PR | Action |
|---|---|---|
| none | none | `export` |
| none | open, trusted, files only under `<path>/<scope>/` | `export-adopt` (record it and its head, no push) |
| none | open, trusted, a file outside `<path>/<scope>/` | `warn`, counted blocked |
| none | open, untrusted | `warn`, counted blocked |
| PR, merged | — | nothing |
| PR | open, trusted, not a draft, required checks green, head = recorded `head`, files only under `<path>/<scope>/` | `export-merge` |
| PR | open, head differs from the recorded `head`, or a file outside `<path>/<scope>/` | `warn`, counted blocked |
| PR | open, checks pending | nothing; counted closing |
| PR | open, checks failing, or untrusted, or a draft | `warn`, counted blocked |
| PR | closed, not merged | `warn` on every pass, counted blocked |
| `pr: None` | — | nothing (the export changed nothing) |

`ActionKind` gains `export`, `export-adopt` and `export-merge`. `Action` gains an optional
`wave: str | None`, and `action_line` prints `export wave <N> <repo>` for those kinds.
`Summary` counts each `export`, `export-adopt`, `export-merge` and pending export as
`closing`, and each warned export as `blocked`. So `summary.done` stays false while an
export is still owed. A loop then keeps passing until the merge, or exits 3 waiting on the
operator.

A `group` or `org` scope whose repo opts in gets one `warn` per pass: "export is per repo
scope; run drive with `--repo`". Export never copies a multi-repo scope's state into one
repo.

**Execution.** `_Driver._export(action)` runs these steps:
1. `checkout.fetch()`, then `add_worktree(<state>/export/<wave>, origin/<default>)`.
2. `export_state(state_dir, worktree/<path>)`.
3. `Worktree.commit_paths([<path>/<scope>], message)`, a new method that stages exactly
   those paths, including untracked files (`commit_all` stages only tracked ones), and
   returns `None` when nothing changed.
4. If nothing changed, append `Export(pr=None)` and stop.
5. Otherwise `Worktree.push("chore/triage-state-wave-<N>", force=True)`, then
   `GhClient.pr_create(repo, head, base, title, body) -> int`. `force` is a new keyword: the
   branch belongs to the driver, and a pass that died after pushing leaves it behind
   `origin/<default>`'s new commit. `pr_create` is a new adapter method: GitHub only, ready
   not draft. GitLab and Gitea raise `UnsupportedForgeOperation`, as the other write verbs
   do.
6. Append `Export(pr=<n>)` through `_record_export`, then remove the worktree.

A crash after step 5's push and before step 6 leaves an open PR with no record. The next
pass sees it on the head and adopts it (`export-adopt` records it and pushes nothing). So
no pass ever opens a second PR for one wave.

`_export_merge` calls `pr_merge(repo, pr, head_sha=<recorded head>, method=ctx.method)`, then
sets `merged: true`. Unlike `_archive`, it never merges the live head: an export PR's content
is machine-written, nobody reviews it, and a commit someone else pushed to its branch must not
reach the default branch (security review, p4-sec-unpinned-merge). The PR's changed files come
from git, never from the forge: after `fetch`, `Checkout.changed_paths(origin/<default>, <head>)`
(`git diff --name-only --no-renames ref...head`) at the head being judged, the recorded one for a
merge and the live one for an adoption. `--no-renames` lists a rename as a deletion plus an
addition, so a rename's source path is checked too, and git does not truncate the list as the
forge's `files` field does at 100 entries (p4-sec-file-list). A head git cannot read gives an
unknown file list, which is never "all inside": the row warns and counts as blocked.

The export branch prefix `chore/triage-state-` is not in `ARCHIVE_PREFIXES`, so archive
attribution can never claim an export PR. Without `--yes`, both actions print as
`action_line`s. A forge write failure exits 1, as the other writes do.

The PR is opened by the collecting login (`Facts.viewer`), so `allowed_authors` trusts it.
A repo whose `pr_authors` leaves that login out sees its own export PR as untrusted. The
table above refuses to merge it, with a `warn` that says why.

## Non-goals

- Per-wave cost on the board. Not chosen in the question round.
- Publishing pages. That stays outside fr (wave-driver R12).
- Exporting an org scope's state.
- Rewriting `authored-src/build.py`. It keeps writing fragment files. Only the manifest
  that places them changes (R15).

## Test Plan

Unit (CI):
- **Fragments:** a fragment interleaved between two generated sections renders there. A
  mapping entry renders collapsed with its title. Today's refusals are unchanged (the
  existing architecture tests, now pointed at `fragments.py`). A moved name is a note, not
  a missing fragment. A board or origins fragment survives a re-render.
- **Board:** the section order (R2); the transitions table rows and the batch link (R3);
  the Tier column on wave tables (R4); cards render as `details` with `data-stage`; the
  filter is `hidden` in the HTML; finished waves leave the board; severity pills; a
  duplicate is listed in Parked and is not unplaced.
- **Architecture:** none of the moved sections renders; the summary's lines and its "where
  it hurts" ordering.
- **Origins:** schema 1 and 2 both load; `duplicate_of` without `duplicate` is refused;
  `introduced_in` on a regression is refused; `check`'s duplicate-outside set; the
  section order; links on the issue table.
- **History:** the timeline and finished waves render; batch links are absolute.
- **`finished_waves`:** cancelled, archived, unarchived and unwaved cases.
- **Judgements:** severity and duplicate_of load on schemas 1–3; `exports` requires
  schema 4; the writer writes 4; `check`'s two new sets.
- **State sync:** export and import file sets; facts and pages never copied; import
  skipping newer files and `--force`.
- **`finished_waves` and preselection:** an `abandoned` batch is terminal; the board never
  preselects a finished wave (the case that used to raise `ValueError`); history preselects
  the highest finished wave.
- **Since table:** `SnapshotDiff.transitions` matches the string groups, change for change;
  acceptance rows come from the moved rows.
- **Origins schema split:** `origins-facts.json` stays schema 1, and `origins.yaml` loads 1
  and 2.
- **Driver (pure):** the step-3b table, row by row, including adopt, untrusted, pending,
  failing and closed; the group-scope and org-scope warnings; no action without config;
  `Summary.done` false while an export is owed.
- **Driver (command):** `_export` against a temporary git repo with a fake `GhClient`:
  committed paths, branch name, the force push over a stale branch, the `pr: None` path, the
  recorded `Export`. `_export_merge` records `merged: true`, and a forge failure exits 1. A
  drive loop does not return `done` while an export PR is open.
- **Writer:** `save_exports` replaces only `exports:` and restores the file on refusal.
- **Forge adapter:** `pr_create` opens a ready PR through `gh`; GitLab and Gitea raise
  `UnsupportedForgeOperation`.
- **Worktree:** `commit_paths` stages untracked files under the path and nothing else, and
  `push(force=True)` overwrites the remote branch.
- **CLI end to end:** `fr triage history render`, `fr triage state export` and
  `fr triage state import` against a temporary state directory, including the printed
  copied and skipped lists. Each render command prints the moved-name note.
- **Collect:** a `duplicate_of` target in a collected repo is viewed.

Every unit line above backs one of the eleven acceptance rows added at brainstorm. The plan
links each row to its tests, and each row moves to `ci` as they land.

Browser (visual evidence, phase and deliver): the board with the stage filter on and off,
a batch link opening a collapsed card, collapsed sections, and the four pages' nav and
goal lines, at desktop width and at phone width in light and dark themes.

Post-merge, operator-driven:
1. `uv run fr triage state import --from docs/triage --repo derio-net/super-fr`. Then run
   the four renders and open each page: one goal line, no section on two pages, and the
   2026-10-02 fragments on the history page.
2. On the next finished wave, the driver opens `chore/triage-state-wave-<N>` and merges it
   once green. The files on main then equal the cache as of the export commit (`git show`
   of that commit against a copy taken when it was made), except for the `exports:` entry.
   The driver records that entry after the commit, so it is never in the exported copy.

## Dependencies

#969 (`chore/triage-state`) adds `docs/triage/`. R15 edits files it adds, so #969 merges
first and this branch rebases onto it before the R15 work.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-05-triage-pages-goal | `derio-net/super-fr` | `2026-10-05-triage-pages-goal` | — |
