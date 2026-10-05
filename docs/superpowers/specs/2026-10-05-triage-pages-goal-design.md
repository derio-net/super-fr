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

R8. A new verb, `fr triage history render`, writes `history.html`, which answers "How did we get here?". It shows the snapshot timeline, then the finished waves as tabs (same table as the board), then authored fragments. A wave is finished when every batch in it is cancelled or has a close-out event with `archived` set. Finished waves appear on the history page and not on the board. Batch links on the history page point to `triage.html#batch-<id>`.

R9. All four pages take authored fragments from `<state dir>/<page>/manifest.yaml` and the fragment files beside it, where `<page>` is `board`, `origins`, `architecture` or `history`. One shared implementation serves all four. It keeps today's manifest rules (names, the generated-section names a page has, missing generated names appended) and today's `validate_fragment` refusals. A fragment is placed exactly at its manifest position, between generated sections if that is where it is listed. A manifest entry can also be a mapping, `{fragment: <file>, title: <text>, collapsed: true}`, which renders the fragment as a closed section titled `<text>`. A fragment listed in a manifest survives every render of its page.

R10. `origins.yaml` schema 2 adds three optional fields per entry:
- `duplicate_of`: an issue key, allowed only with `category: duplicate`;
- `fixed_by`: a PR reference;
- `introduced_in`: a PR reference, refused on a regression, whose `pr` already names the PR that broke it.

Schema 1 files still load. `fr triage origins check` reports a new set, "duplicate target outside the window": entries whose `duplicate_of` is not an issue in the collected origins facts. The origins issue table links a duplicate to its original and shows `fixed_by` and `introduced_in`.

R11. A judgement in `judgements.yaml` gains two optional fields, `severity` (`low`, `med` or `high`) and `duplicate_of` (an issue key). Both load on every schema, as `kind` does. `fr triage check` reports two new sets:
- "no severity": open, judged issues without a severity;
- "duplicate target unknown": `duplicate_of` names an issue that collect did not read.

The board shows each backlog row's severity, and each Next up row shows the most severe severity among its issues. An issue with `duplicate_of` is listed under Parked as "duplicate of <link>", and counts as placed for the unplaced set.

R12. `fr triage state export --to <dir>` copies a scope's durable state from the state directory to `<dir>/<scope>/`. `fr triage state import --from <dir> [--force]` copies it back. The durable state is: `judgements.yaml`, `origins.yaml`, `subsystems.yaml`, each page's manifest directory (manifest and fragment files), `snapshots/` and `authored-src/`. Facts files and rendered pages never travel. Import skips a state-directory file that is newer than the repo copy unless `--force` is given. Both verbs print every file they copied and every file they skipped.

R13. `.fr/triage.yaml` accepts an optional `export: {path: <repo-relative dir>}`. With it set, the driver acts on a single-repo scope once a wave of that repo is finished (R8) and `judgements.yaml` records no export for that wave. `fr triage batch drive --yes` then:
- exports the state (R12) into a worktree of `origin/<default>` under `<path>`;
- commits only `<path>/<scope>/`;
- pushes `chore/triage-state-wave-<N>`;
- opens a ready (non-draft) PR as the collecting login, which `pr_authors` therefore trusts;
- records `{wave, repo, pr}` under a new top-level `exports:` list in `judgements.yaml` (judgements schema 4).

If the export changes nothing, the driver records the export with no PR and opens nothing. On a later pass the driver merges the export PR under the same gate as an archive PR: open, not a draft, required checks green, and head unchanged. It then records the merge. An export PR closed without a merge is reported as a warning on every pass. Without `--yes`, the pass prints the export and merge actions it would take. Without `export:` in the config, no export action exists.

R14. The `fr-triage`, `fr-origins` and `fr-audit` skills document the four page goals and the four fragment manifests. They state that hand-written analysis lives in fragments and never in a page edited after it is rendered. They also document `severity` and `duplicate_of` on judgements, the origins schema-2 fields, `fr triage history render`, `fr triage state export|import` and the `export:` config key.

R15. In this repo, `docs/triage/README.md` names the `fr triage state` verbs and `docs/triage/sync.sh` is deleted. This repo's `docs/triage/derio-net--super-fr/` manifests move the dated fragments (the 2026-10-02 closing order, the 2026-10-02 origins analysis and the history to 2026-10-02) from the architecture manifest to `history/manifest.yaml`. They also drop the architecture manifest's entries for sections the page no longer has. `.fr/triage.yaml` opts in with `export: {path: docs/triage}`.

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
2. Since last report, as a table (R3). `diff_snapshots` already yields typed groups. A new
   `_since_table(since)` flattens them into rows `(change, item_html, before, after)`.
   "Filed" and "merged or closed" rows have an empty before or after. Acceptance moves come
   from the existing `acceptance_note` data. Batches link to `#batch-<id>`. With no changes,
   it shows one line, "Nothing changed since the last report."
3. Needs you now and Next up, unchanged except for a severity pill on Next up rows (R11).
   Their severity is the maximum over member judgements, ordered `high > med > low`.
4. Waves: tabs over `views.waves(judgements)`, minus the finished waves
   (`views.finished_waves`, §D). `_wave_table` gains `Tier` after `Batch` (R4), computed by
   the existing `views._tier`, renamed to the public `views.batch_tier` because two modules
   now call it. If every wave is finished, the section reads "Every wave is finished: see
   the history page." and links there.
5. Collapsed sections, each through `collapsed(...)`: Backlog by tier (one nested collapsed
   section per tier, and Unranked), Ranked features, Parked, Patterns, PRs, Batches.
   Backlog rows gain a severity pill, or `—`.
6. Batches. A stage filter of checkboxes, one per `BatchStage` present, is rendered `hidden`
   and unhidden by script, the same no-JS rule `tabs()` uses. Each `_batch_card` becomes a
   `<details id="batch-<id>" data-stage="<stage>">`. A small `FOLD_SCRIPT` does two things:
   - it toggles `hidden` on cards by `data-stage`;
   - on `hashchange` and on load, it opens the target `<details>` and every ancestor
     `<details>`, then scrolls the target into view.

   The merge-order list stays in the Batches section.

Parked (R11): issues with `kind: parked`, plus open issues whose judgement has
`duplicate_of`. A duplicate row reads "duplicate of <link>". The link points to the issue's
row on the board when it is open there, and to its forge URL otherwise. The unplaced set in
`check.py` treats an issue with `duplicate_of` as placed.

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
- `architecture.py` re-exports `validate_fragment` and `resolve_manifest` for one release,
  as thin aliases bound to the architecture page's generated names. That keeps
  `test_triage_architecture.py` and any caller of the old import path working.

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

The masthead, `page_header` and the board's filter bar sit outside the manifest, always
first.

### D. Finished waves, one predicate (R8, R13)

`views.finished_waves(judgements) -> set[str]` returns the wave keys where every batch is
cancelled, or has a `closeout_event(batch)` whose `archived is not None`. The board, the
history page and `batch_drive.drive_pass` all call it. It reads judgements only: the driver
writes `archived` when it merges an archive PR (`_Driver._archive`) or adopts a hand
archive, so judgements already record what "finished" needs. Unwaved batches never make a
finished wave.

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
- `SCHEMA` becomes 2, and `load_origins` accepts 1 or 2.
- `Origin` gains `duplicate_of: str | None`, `fixed_by: str | None` and
  `introduced_in: str | None`. Validators refuse `duplicate_of` without
  `category: duplicate`, and refuse `introduced_in` on a regression. `duplicate_of` is
  normalised with `normalize_key`.
- `OriginsCheck` gains `duplicate_outside: list[str]`, and `check` prints it as its third
  set.
- The issue table's "Related PR" cell adds `introduced in …` and `fixed by …` lines when
  they are set. The Category cell for a duplicate links its original: to its table row
  (each row gains `id="origin-<key>"`; rows carry none today) when the original is in the window, else to the forge URL built from
  the key.

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
- `JUDGEMENTS_SCHEMA` becomes 4, and `Judgements.schema_` accepts `1 | 2 | 3 | 4`.
- Schema 4 adds a top-level `exports: list[Export]`, where
  `Export(wave: str, repo: str, pr: int | None, merged: bool = False, at: str)`. The
  validator that ties schema-3 events to schema 3 gains the same rule: `exports` requires
  schema 4.
- The one writer (`batch.py`) writes `schema: 4`, as it writes 3 today.
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
- `export_prs: dict[(repo, wave), PrState]`: the live state of each recorded open export PR.

`drive_pass` adds a step after archive (step 3b). For each repo with `export_path` and each
`finished_waves` key that has no merged export:

| Recorded export | Live PR state | Action |
|---|---|---|
| none | — | `export` |
| PR, merged | — | nothing |
| PR | open, not a draft, required checks green | `export-merge` |
| PR | closed, not merged | `warn` (on every pass) |
| `pr: None` | — | nothing (nothing changed when exported) |

`ActionKind` gains `export` and `export-merge`.

For an org scope, a repo that opts in gets one `warn` per pass, "export is per repo scope;
run drive with `--repo`". Export never copies an org scope's state into one repo.

**Execution.** `_Driver._export(action)` runs these steps:
1. `checkout.fetch()`, then `add_worktree(<state>/export/<wave>, origin/<default>)`.
2. `export_state(state_dir, worktree/<path>)`.
3. `Worktree.commit_paths([<path>/<scope>], message)`, a new method that stages exactly
   those paths, including untracked files (`commit_all` stages only tracked ones), and
   returns `None` when nothing changed.
4. If nothing changed, append `Export(pr=None)` and stop.
5. Otherwise `Worktree.push("chore/triage-state-wave-<N>")`, then
   `GhClient.pr_create(repo, head, base, title, body)`. That is a new adapter method: GitHub
   only, ready not draft. GitLab and Gitea raise `UnsupportedForgeOperation`, as the other
   write verbs do.
6. Append `Export(pr=<n>)`, then remove the worktree.

`_export_merge` calls `pr_merge(repo, pr, head_sha=…, method=ctx.method)`, the archive
path, and sets `merged: true`.

The export branch prefix `chore/triage-state-` is not in `ARCHIVE_PREFIXES`, so archive
attribution can never claim an export PR. Without `--yes`, both actions print as
`action_line`s. A forge write failure exits 1, as the other writes do.

The PR is opened by the collecting login (`Facts.viewer`), so `allowed_authors` trusts it.
A repo whose `pr_authors` leaves that login out sees its own export PR as untrusted, and
the driver refuses to merge it with a `warn` that says so.

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
- **Driver (pure):** the step-3b table, row by row; the org-scope warning; no action
  without config.
- **Driver (command):** `_export` against a temporary git repo with a fake `GhClient`:
  committed paths, branch name, the `pr: None` path, the recorded `Export`.
- **Worktree:** `commit_paths` stages untracked files under the path and nothing else.

Browser (visual evidence, phase and deliver): the board with the stage filter on and off,
a batch link opening a collapsed card, collapsed sections, and the four pages' nav and
goal lines, at desktop width and at phone width in light and dark themes.

Post-merge, operator-driven:
1. `uv run fr triage state import --from docs/triage --repo derio-net/super-fr`. Then run
   the four renders and open each page: one goal line, no section on two pages, and the
   2026-10-02 fragments on the history page.
2. On the next finished wave, the driver opens `chore/triage-state-wave-<N>` and merges it
   once green. Then `docs/triage/derio-net--super-fr/judgements.yaml` on main matches the
   cache copy.

## Dependencies

#969 (`chore/triage-state`) adds `docs/triage/`. R15 edits files it adds, so #969 merges
first and this branch rebases onto it before the R15 work.
