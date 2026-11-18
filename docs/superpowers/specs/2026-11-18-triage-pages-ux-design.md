# Triage pages UX — one name per page, folds, links, filters, pages that stay current

**Date:** 2026-11-18
**Slug:** `2026-11-18-triage-pages-ux`
**Status:** design (fr-goal, batch `triage-pages`)
**Repo:** `derio-net/super-fr` (single-repo change)
**Issue:** derio-net/super-fr#1544

## 1. Goal

The triage engine writes five HTML pages into a scope's state directory. They have grown
long and flat. They do not link to each other or to the PRs they name. Some of them go
stale without saying so. This change gives each page one name. It makes the long sections
fold through one shared component, links every reference, adds the filters #1544 asks for,
and keeps every page current from the wave driver.

### Non-goals

- `facts.json`, `subsystems.yaml` and the judgement schema are unchanged. The one
  collection change is `origins collect` (R15): it also keeps the PRs merged in its window.
  `facts.json` does not hold merged PRs. `collect` reads them (`collect.py:753`) only to
  link PRs to issues, and keeps open, batch and judged PRs (`collect.py:888–910`).
- No new artifact kind and no artifact shape change. The pages, the snapshots and the
  fragment directories live in the triage state directory, which no registered kind covers.
- The authored fragments' content (`docs/triage/derio-net--super-fr/authored-src/`) is not
  rewritten. Only the history manifest moves the three 2026-10-02 fragments under a heading.

## 2. Background (read from the code on 2026-11-18)

- **The page registry** is `fr.triage.components.PAGES` (`components.py:55`): `backlog` →
  `triage.html`, `batches` → `board.html`, `origins`, `architecture`, `history`. The nav,
  `pages_present` and `refresh_navs` read it. The Backlog's fragment directory is `board/`
  (`triage_cmd.py:104`'s `BOARD_DIR`, used at `triage_cmd.py:1068`). The other pages name
  their own files and directories: `history.PAGE_FILE`/`HISTORY_DIR` (`history.py:36`),
  `origins.PAGE_FILE`/`ORIGINS_DIR` (`origins.py:53`) and `architecture.PAGE_FILE`/
  `ARCHITECTURE_DIR` (`architecture.py:48`). The `MOVED` maps call the Backlog "board"
  (`history.py:41`, `architecture.py:56`). History links finished-wave
  batches into the Backlog through a constant named `BOARD_FILE = "triage.html"`
  (`history.py:38`).
- **Commands:** `fr triage render` writes `triage.html` and stores a snapshot
  (`triage_cmd.py:1028–1106`). `fr triage board` writes `board.html`
  (`triage_kanban_cmd.py:615`). `fr triage origins render`, `fr triage architecture render`
  and `fr triage history render` write their own pages.
- **What the driver refreshes:** `fr triage batch drive` calls `_write_board` once per pass
  (`triage_batch_cmd.py:5415`), and that renders `board.html` only. It runs on a `--yes`
  pass that is not essential-only; a plan-mode, quiet or essential-only pass keeps the last
  board (`triage_batch_cmd.py:5354–5358`). The driver already sees a wave go from unfinished
  to finished within a drive: `self._unfinished` (`triage_batch_cmd.py:5306`), compared in
  `batch_drive.py:2050`. A snapshot cannot show that change, because `finished_waves`
  (`batch_drive.py:1225`) counts archived close-outs from judgements, and a snapshot stores
  only batch stages (`snapshot.py:63`). Nothing else is
  re-rendered, and the driver stores no snapshot. Snapshots are stored only by
  `fr triage render`, which keeps the latest `KEEP = 30` (`snapshot.py:34`).
- **Folds:** `components.collapsed()` (`components.py:380`) is a closed `<details
  class="fold">`. The Backlog uses it for most of its lists. Its decision sections (Since
  last report, Needs you now, Next up, Waves, Debt) are plain `<section>`s. History's
  timeline is a tab set with no fold. The board's columns are not folds: an empty column
  collapses to a strip through CSS alone (`kanban_render.py:104`, gh#1417).
- **Tabs:** `components.tabs()` with `TABS_SCRIPT` (`components.py:206`). The script reads
  no URL hash, so no link can open a given tab. Without the script every panel shows.
  `render_architecture` (`architecture.py:348`) includes no script at all, so the pipeline
  fragment's ten dated diagram panels (`authored-src/pipeline.py:196`) render stacked, one
  under another, instead of as one graph with dated tabs.
- **Links:** issue keys in rows link to `Issue.url`. Prose from judgements goes through
  `render.inline()` (`render.py:409`), which escapes the text and allows only `code` and
  **bold**, so a `#123` in a reason is plain text. Next up prints a batch id and its deps as
  text (`render.py:874`), and its wave appears only inside the reason string
  (`views.py:596`). The Origins PR leaderboards print the PR reference alone
  (`origins.py:631`), and `_pr_link` (`origins.py:537`) builds a `github.com` URL for any
  forge. The finished-wave table on History has no PR column.
- **Render time:** the Batches page states its render time (`kanban_render.py:445`). The
  other four state only `collected <facts time>`.
- **Origins "Every issue"** (`origins.py:684`) is one table with a category filter bar and
  no state filter.
- **Publish:** `triage_kanban_cmd.publish` hands the scope's publish command a copy named
  after the board file's basename (`triage_kanban_cmd.py:443`).

## Requirements

R1. Each triage page has one name that its nav title, its file, its command and, where it
has one, its fragment directory all use: Backlog (`backlog.html`, `fr triage backlog`,
`backlog/`), Issues (`issues.html`, `issues/`, written by `fr triage backlog`), Batches
(`batches.html`, `fr triage batches`; it reads no manifest, so it has no fragment
directory), Origins, Architecture and History (unchanged).
R2. `fr triage render` and `fr triage board` keep working as aliases of `fr triage backlog`
and `fr triage batches`. Each prints one line naming the new command.
R3. A render deletes its page's old-named file from the state directory (`triage.html`,
`board.html`), so no stale copy stays there. Where `backlog/` is absent and `board/` exists,
both the Backlog and the Issues page read `board/`, and each says so in a note on the page
and on stderr. A section the other page owns is then skipped with the existing "now on the
X page; skipped" note, so the operator's order and fragments carry over for both pages.
R4. The Backlog page holds the decisions: Since last report, Needs you now, Next up, Waves
and Batches. A new Issues page holds the lists: possible duplicates, backlog by tier, ranked
features, parked, awaiting live, closed but in progress, patterns, debt and PRs. Each page
has its own nav entry, goal sentence and manifest. A manifest that names a section the other
page owns gets the "now on the X page; skipped" note, naming the page by its registry title.
R5. Every page states when it was rendered, as `rendered YYYY-MM-DD HH:MM UTC`, beside the
time its facts were collected. The render command passes the moment in, so a render stays a
pure function of its inputs.
R6. While `fr triage batch drive` runs, every `--yes` pass that writes the board (one that
collected and is not essential-only) re-renders, after the board, every page whose inputs are
on disk: Backlog and Issues, History, Origins (when `origins-facts.json` exists) and
Architecture (when `subsystems.yaml` exists). Architecture re-measures line counts only on
the drive's first such pass and on a pass in which a wave finished, and it reuses the drive's
last measurement on the other passes. With no checkout of the scope's repo it renders with no
measurement, as the command does when git fails. A page that cannot be rendered is one
warning per distinct cause and never changes the pass, as the board's write is today. A
plan-mode, quiet or essential-only pass re-renders nothing.
R7. The driver stores a snapshot on the first pass of a drive that writes the pages, when it
differs from the latest stored one (a baseline per drive), and on every later such pass in
which a wave went from unfinished to finished. It uses the wave sets the driver already tracks
for dedupe (`self._unfinished`), not a comparison with a stored snapshot. It takes the
snapshot with the same function `fr triage backlog` uses. A driver re-render stores no other
snapshot. `fr triage backlog` run by hand keeps storing one whenever the board changed.
R8. One fold component in `components.py`, used by every section-level collapsible on every
page (a page section, an origin group, a fragment group). Small collapsibles inside a row or a
panel (a PR's issue list, a snapshot's stage list) stay plain `<details>`. A fold's summary
line shows the title and, when known, a count. It may start open or closed. With scripts off
it is a plain `<details>`. Opening a URL whose hash names an element inside a fold opens that
fold, and every enclosing `<details>`.
R9. Folds on the pages: the Backlog's sections (Since last report, Needs you now, Next up,
Waves, Batches) fold and start open. The Issues page's sections, Debt included, fold and start
closed. On History the snapshot timeline folds and starts closed, and the three 2026-10-02
fragments sit in one closed fold headed "Archived notes (2026-10-02)". On Origins each origin
group folds (R14).
R10. On the Batches page every column can be collapsed and expanded with a control in its
header. A column with no card starts collapsed, as today, and can be expanded. Whether each
column is collapsed is remembered in the viewer's browser, so the page's auto-refresh keeps
it. If browser storage is not available, the page still works and forgets on reload.
R11. Every reference to a PR or issue that a page renders links to the forge. A key the page's
inputs hold links to that item's own URL. In judgement prose (`inline()`), an `owner/repo#n`
reference links when that repo's URL base is known from the inputs, and a bare `#n` links
when the scope is a single repo. On a base whose host is `github.com` an unknown number links
to `/issues/<n>` (GitHub redirects a PR there). On any other forge only keys the inputs hold
link. Anything else stays text. The inputs are `facts.json` on Backlog, Issues, Batches,
History and Architecture, and `origins-facts.json` (its issues and, R15, its PRs) on Origins.
R12. A wave reference links to that wave on the page that holds it. An unfinished wave goes
to its tab on the Backlog, and a finished one to its tab on History. A batch reference goes
to its card. Next up shows each row's wave as its own linked field, and links its batch id and
dependencies the same way. `TABS_SCRIPT` selects the tab whose panel the URL hash names, or
that holds the element the hash names, on load and on every hash change.
R13. The Backlog's Waves section has a kind filter: one toggle per kind (defect, feature,
parked, unkinded), several on at once. A batch row stays shown while any of its issues has a
kind that is on. All kinds start on. The kind counts stay as they are.
R14. Origins: "Every issue" becomes a plain section with a state filter (open, closed, all;
default all) and one fold per origin group (each category in `CATEGORIES` order, then
unclassified), with the group's count on its summary. The filter applies to every group and
updates each group's shown count. The category buttons go, because the folds replace them.
R15. `fr triage origins collect` also keeps, in `origins-facts.json`, the PRs merged on or
after its `--since` date in each repo it reads (repo, number, title, url, merged date), with
one PR list read per repo. On Origins each PR in "Which PRs left work behind" shows its link,
its title and its merge date from those PRs, plus the issues of that group that name it, each
linked. A PR that `origins-facts.json` does not hold (merged before the window, or an older
file without PRs) shows its link and "not collected".
R16. History: each finished wave's table has a PR column showing each batch's PR with its
link, title and merge date, from the facts' batch PRs. A batch with no PR shows an em dash.
Its batch links point at the Backlog's `backlog.html`.
R17. Architecture: the pipeline fragment reads as one graph with dated tabs above it. Every
page includes the shared tab and fold CSS and scripts, so a fragment's tab set works on any
page. The tabs keep the fragment's chronological order.
R18. The Batches page has a wave cutoff toggle, on by default. While it is on, it hides the
cards of every wave whose batches are all terminal (merged, archived, cancelled or abandoned)
and none of which had an event in the 30 days before the render. A wave with any non-terminal
batch always shows, so a planned wave that has not started stays visible. Cards with no wave
always show. Turning the toggle off shows all waves. The choice is remembered like the column
state (R10).

## Design

### A. The registry and the names (R1–R3)

`PAGES` becomes, in nav order: `backlog` (`backlog.html`, "Backlog"), `issues`
(`issues.html`, "Issues"), `batches` (`batches.html`, "Batches"), `origins`,
`architecture`, `history`. Each `Page` gains `dir` (its fragment directory, or none for
Batches) and `legacy` (its old file name and old directory, or none). These constants become
reads of the registry: `triage_cmd.BOARD_DIR`, `triage_kanban_cmd.BOARD_FILE`,
`history.BOARD_FILE`, `history.PAGE_FILE`/`HISTORY_DIR`, `origins.PAGE_FILE`/`ORIGINS_DIR`,
`architecture.PAGE_FILE`/`ARCHITECTURE_DIR`, the `href="board.html"`/`href="history.html"`
literals in `render.py` and `triage.html#` in `origins.py`. The `MOVED` maps hold page keys
and their notes print the registry title. A new tripwire scans every module under
`fr/triage/` and every `fr/commands/triage_*_cmd.py`, docstrings and help text included, and
fails on a page file name (`*.html` of a registry page, old or new) outside `components.py`.
Docstrings and help text name pages by their command or title instead.

`fr triage backlog` is today's `render` command under its new name. It writes both
`backlog.html` and `issues.html`, because they share one input load and one snapshot. The
old names register as Typer commands, hidden from help, that print
`fr triage render is now fr triage backlog` and call the new ones. After writing, a render
removes `state_dir / page.legacy` when it exists. The fragment fallback (R3) is one helper,
`fragment_dir(state_dir, page)`, which returns the directory and an optional note. Both
Backlog and Issues use it.

`publish` hands over `batches.html`. Operators whose publish command names `board.html`
must update it. The release note says so.

### B. Backlog and Issues (R4)

`render.render()` splits into `render_backlog()` and `render_issues()`. Each takes the
builders it owns from today's `builders` map, its own `GENERATED` tuple and a `MOVED` map
naming the other page's sections. Both share the masthead, the skew banner and the CSS.
`FILTER_BAR` moves with `backlog` to Issues. Today's `render.FOLD_SCRIPT` is split: its stage
filter becomes `render.STAGE_FILTER_SCRIPT`, which stays with `batches` on the Backlog, and its
reveal half becomes the shared fold script (D).

### C. Render time and the driver (R5–R7)

Each `render_*` takes `rendered_at: datetime` and prints it with `components.when()`. Each
command's write is lifted into a function the driver can call: `write_backlog`,
`write_history`, `write_origins` and `write_architecture`. Each takes
`(scope, target, *, now, warn)`. `write_backlog` also takes what Needs you now reads today:
`loader`, `prefix` and `ci_none`, with the command's defaults (`read_sessions` with the host
loader, `local_ci_none(facts)`), so the cloud driver passes its own runner loader and its
pass's `ci_none`, as it does for `write_board`. `write_architecture` takes `checkout` and
`measured` (a prior measurement to reuse) and returns the measurement it used. `write_board`
keeps its signature and gains `now`.

The driver gets one method, `_write_pages(wave_finished: bool)`, called right after
`_write_board` on the same passes. It renders in registry order and keeps one failure set
per page, like `board_failures`. `wave_finished` is true when a wave in the previous pass's
`self._unfinished` is finished now. On the drive's first page-writing pass, `_write_pages`
stores a snapshot when it differs from `latest_snapshot`. On a later pass it stores one when
`wave_finished` is true. The snapshot is the same `take_snapshot` call `write_backlog` makes.
The acceptance rows come from the checkout the driver holds for a single-repo scope, else
`acceptance_rows(None)` (not tracked). Architecture measures with that checkout at its
`HEAD`, the command's default. The driver keeps the result in memory for the next passes.

### D. Folds (R8–R10)

`components.fold(id_, title, count, body, *, open_=False, heading=None)` replaces
`collapsed()`. All callers move to it, and `collapsed` is deleted. `heading` lets a section
keep its `<h2>` inside the summary, so the existing section ids (`since-last-report`,
`needs-you-now`, `next-up`, `waves`, `batches`, and `debt` on Issues) stay link targets.
`components.FOLD_SCRIPT` opens every ancestor `details` of the hash target on load and on
hash change, then scrolls to it. The board's column toggle is a `<button aria-expanded>` in
the column's `h2`. Its state is kept in `localStorage` under `fr-triage:<scope>:col:<key>`,
with every access wrapped in try/catch. An empty column's starting state is collapsed, and
the CSS rule that collapsed it becomes the style of the collapsed state.

### E. Links (R11, R12)

`components.Linker` is built once per render from the page's inputs (R11). It maps each
known issue and PR key to its URL and each repo to its URL base (the issue URL up to
`/issues/`, or the PR URL up to `/pull/`). It also knows whether the scope is a single repo.
`inline()` gains an optional `linker`: after escaping, and outside `code` spans, it rewrites
`owner/repo#n` and (for a single-repo scope) bare `#n` by R11's rules. Every href it writes
comes from a forge URL in the inputs or from a base plus a number, never from the prose.
Origins' `_pr_link` and `_related_pr` go through the Linker. `components.wave_href(key,
finished)` and `batch_href(id)` give the targets: `backlog.html#wave-panel-<k>`,
`history.html#history-wave-panel-<k>` and `backlog.html#batch-<id>`. `views.NextRow` gains
`wave: str | None`, rendered as its own linked tag. `TABS_SCRIPT` gains a `fromHash()` step:
find the element the hash names, walk up to its `tabpanel`, select that panel's tab, then let
the fold script open folds and scroll.

### F. Waves kind filter (R13)

The kind chips in "Closing order" become `<button aria-pressed>` toggles, one per kind,
in a `toolbar`. Each wave-table row carries `data-kinds` (the space-separated kinds of its
issues, `unkinded` for an issue with no kind). The script hides a row when none of its kinds
is pressed. A wave tab whose rows are all hidden shows "No batch of the selected kinds".

### G. Batches wave cutoff (R18)

Each card carries `data-wave`, `data-terminal` and `data-active` (the ISO date of its
batch's latest event, empty when it has none). A toolbar toggle, "last 30 days" (pressed by
default) or "all waves", hides the cards of a wave when every card of it is terminal and no
card's `data-active` falls in the 30 days before the render time (`data-rendered` on
`body`). Cards with no wave always show. Each column's count shows the cards shown. The toggle
state is remembered like the column state.

### H. Origins (R14, R15)

`OriginsFacts` gains `prs: list[MergedPr] = []` (repo, number, title, url, merged_at), filled
by `origins collect` from one merged-PR list read per repo, kept when `merged_at >= since`. It
is a state-directory cache, not an artifact kind. A file without the key reads as no PRs.
`_issue_table` groups the rows by category in `CATEGORIES` order, then unclassified, one
`fold` each, under a plain "Every issue" section heading that holds the state filter. The
rows carry `data-state`. `FILTER_SCRIPT` is replaced by a state filter that hides rows by
state and rewrites each fold's `.count`. `_leaderboards` renders each PR as a row with link,
title, merge date (`stamp_text` of `merged_at`) and a plain `<details>` listing its issues.

### I. History (R16, R9) and Architecture (R17)

`wave_table` gains an optional `prs` argument. History passes, for each finished batch, the
PR `fr.triage.batch.batch_pr` (`batch.py:310`) finds among the facts' batch PRs. History's
manifest gains one allowed entry kind, a fold group:
`{fold: "Archived notes (2026-10-02)", entries: [closing-order.html, …]}`.
`fragments.resolve_manifest` accepts it on every page, and the repo's
`docs/triage/derio-net--super-fr/history/manifest.yaml` uses it. Every page's CSS includes
`components.PAGE_CSS` (`TABS_CSS` plus the fold CSS), and every page's `<script>` ends with
`components.PAGE_SCRIPT` (`TABS_SCRIPT` plus `FOLD_SCRIPT`).

### J. Docs and skill

`docs/explainers/fr-triage.md`, `docs/explainers/fr-wave-driver.md`, `docs/triage/README.md`,
`AGENTS.md` (its `fr/triage` paragraph), `plugins/super-fr/skills/fr-triage/SKILL.md` (plus
both mirrors), `fr-audit`'s skill and the generated CLI tables name the new files and
commands. The change fragment is `minor`: new commands, a new page and new driver behaviour,
with the old commands kept.

## Verification

gate: developer
- triage-page-names: none — unit tests in CI pin the registry, the aliases, the legacy-file removal and the fallback
- triage-pages-rendered-stamp: none — unit tests in CI pin the stamp on every page; the visual checks at review and deliver see it
- triage-pages-driver-refresh: none — unit tests drive passes with a fake clock and assert the pages written and the snapshot stored at a wave's finish
- triage-pages-folds: none — CI unit tests plus fr-goal's browser checks at review and deliver, over pages rendered from a fixture state
- triage-pages-links: none — CI unit tests plus fr-goal's browser checks at review and deliver
- triage-backlog-issues-split: none — CI unit tests plus fr-goal's browser checks at review and deliver
- triage-batches-columns-cutoff: none — CI unit tests plus fr-goal's browser checks at review and deliver
- triage-origins-groups-prs: none — CI unit tests plus fr-goal's browser checks at review and deliver
- triage-history-pr-summary: none — CI unit tests plus fr-goal's browser checks at review and deliver
- triage-architecture-pipeline-tabs: none — CI unit tests plus fr-goal's browser checks at review and deliver

## Risks

- **Bookmarks and publish commands** that name `triage.html` or `board.html` break. Mitigation:
  R3 removes the stale copies, so a broken link fails visibly rather than showing old data,
  and the release note names both files.
- **Driver pass time.** Re-rendering four pages per pass is pure and reads only local files.
  Architecture's git reads run at most once per finished wave.
- **Browser storage** can be missing (private window). Every access is wrapped, and the
  default state is the one the page renders.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-18-triage-pages-ux | `derio-net/super-fr` | `2026-11-18-triage-pages-ux` | — |
