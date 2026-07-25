# Acceptance report formats — local/linked HTML + linked Markdown

**Status:** design · **Date:** 2026-07-25 · **Slug:** acceptance-report-formats

## Goal

Extension of #403/#412. Operator finding on `derio-net/frank`: **GitHub does not
render committed `.html` at all** (it shows source), so a committed
`report.github.html` is not viewable on github.com — the whole point of a
"github-linked" report. Fix the format story:

1. **`report.html` reverts to ad-hoc, uncommitted** — as before this feature:
   `fr acceptance report` (no `--deterministic`) renders it git-stamped honoring
   `--link-mode` (github in CI, local when run locally). Gitignored again.
2. **The committed deterministic set becomes THREE files:**
   - `docs/acceptance/report_local.html` — local links, HTML (checkout-viewable).
   - `docs/acceptance/report_linked.html` — github links, HTML.
   - `docs/acceptance/report_linked.md` — the github-linked report rendered as
     **Markdown**, which GitHub *does* render inline.

## Current shape (post-#412)

- `report.py` — `render(matrix, links, stamp)` (HTML); `LinkBuilder` (github|local);
  `REPORT_SET: dict[str,str]` = `{report.html: local, report.github.html: github}`;
  `render_committed_set(matrix, root)` renders each deterministically; `render_deterministic`
  / `render_report` helpers.
- `acceptance_cmd.report_cmd` — `--deterministic`/`--check` operate on the set;
  `--out` single-file; ad-hoc git-stamped default.
- `check.check()` — existence-gated report-sync over `REPORT_SET`.
- `scaffold.init` — generates the set; `add_cmd` regenerates it.
- Committed on main: `report.html` (local) + `report.github.html` (github).
- `.gitattributes` pins both; tripwire checks both.

## Design

### D1 — Markdown renderer

New `render_markdown(matrix, links, stamp) -> str` in `report.py`, GitHub-flavored,
mirroring `render()`'s information (title, status counts, one table per capability
with Acceptance / Origin / Levels / Automation / Evidence, and the "sharp line"
sections for failing/skipped/not-implemented). Refs become `[repo:name](url)` via
the same `LinkBuilder`; cell text is escaped for `|`/newlines so the tables stay
valid. Deterministic like `render()` (matrix-derived stamp, `probe=False`).

### D2 — the committed set is now three files, keyed by (link_mode, format)

```python
REPORT_SET = {
    "docs/acceptance/report_local.html":  ("local",  "html"),
    "docs/acceptance/report_linked.html": ("github", "html"),
    "docs/acceptance/report_linked.md":   ("github", "md"),
}
```

`render_committed_set` dispatches `html → render(...)`, `md → render_markdown(...)`.
`report.html` and `report.github.html` leave the committed set entirely.

### D3 — `report.html` back to ad-hoc, uncommitted

- `fr acceptance report` (no `--deterministic`, no `--out`) → writes
  `docs/acceptance/report.html` git-stamped, honoring `--link-mode` (unchanged
  pre-#403 behavior; the CI "Build report" artifact step keeps using it).
- `report.html` is **gitignored** again (repo `.gitignore` + `scaffold.init`),
  and the previously-committed `report.html` + `report.github.html` are removed
  (`git rm`) — superseded by `report_local.html` / `report_linked.html`.

### D4 — CLI, check, init, add

- `report --deterministic` (no `--out`) → writes the 3-file set.
- `report --check` (no `--out`) → verifies the 3 files; exit 3 naming any
  drifted/missing.
- `--out X` → single explicit file, git-stamped or deterministic per flags,
  honoring `--link-mode` (HTML escape hatch; unchanged).
- `check.check()` — existence-gated report-sync over the NEW set (report.html is
  no longer in the set, so its ad-hoc presence/content never affects `check`).
- `init` — generates the 3-file set AND writes the `report.html` gitignore line.
- `add` — regenerates the 3-file set.
- **Stale-legacy cleanup on write:** the deterministic writers (`add`, `init`,
  `report --deterministic`) delete a stale `docs/acceptance/report.github.html`
  if present (it is never produced anymore, only renamed). `report.html` is left
  untouched — it is the ad-hoc file now, not a leftover. This is a filesystem
  concern in the *writers*, never in `render_committed_set` (which stays a pure
  matrix→{path:content} function) nor in `check` (no git-tracking queries).

### D5 — docs, gitattributes, tripwire, migration, version

- `.gitattributes` pins the 3 committed files to `eol=lf`; drop old entries.
- Tripwire checks the 3-file set.
- Rule text / `scaffold.RULE_TEMPLATE` / `.opencode` mirror describe the three
  committed reports + the ad-hoc `report.html`.
- **Migration:** super-fr `git rm`s `report.html` + `report.github.html`, adds
  the three new files, gitignores `report.html`. Consumer repos: documented
  one-liner — `git rm --cached docs/acceptance/report.html
  docs/acceptance/report.github.html && fr acceptance report --deterministic &&
  git add -A` (the `--deterministic` run writes the new set and deletes the stale
  `report.github.html`; `check` then enforces the new set).
- Version bump **minor** (3.17.0 → 3.18.0).

## Decisions (autonomous — non-interactive VK card; ratify at merge)

- **DEC-1 names** exactly as requested: `report_local.html`, `report_linked.html`,
  `report_linked.md`.
- **DEC-2 `report.html`** ad-hoc + gitignored; the committed copy is `git rm`'d.
- **DEC-3 `report.github.html`** removed — superseded by `report_linked.html`.
- **DEC-4 Markdown link mode = github** ("report_linked.md is report_linked.html
  rendered as markdown"); a local-links markdown twin is YAGNI.
- **DEC-5 no git logic in `check`.** `check` stays a filesystem/existence gate on
  the new set. Distinguishing a *committed* leftover `report.html` from the
  legitimate *ad-hoc* one needs git state, which would over-couple `check` — so
  instead the deterministic writers delete the stale `report.github.html` on
  regenerate, and the operator migration one-liner handles the `git rm --cached
  report.html`. A consumer that runs `fr acceptance add` / `report --deterministic`
  gets the new set (and the gate then enforces it); the old `report.html` simply
  becomes an ad-hoc gitignored file.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-07-25-acceptance-report-formats | `derio-net/super-fr` | `2026-07-25-acceptance-report-formats` | — |

## Test Plan

1. **Markdown render.** `render_markdown` yields GFM: a `#` title, a status-count
   table, one `##` section + table per capability, `[repo:name](https://github.com/...)`
   links (github mode), and the sharp-line sections; deterministic across runs. (unit)
2. **`report --deterministic` writes exactly the 3 committed files** (report_local.html,
   report_linked.html, report_linked.md) and NOT report.html. (unit)
3. **Ad-hoc `report`** (no flags) writes git-stamped `report.html` honoring
   `--link-mode`, and `report.html` is gitignored. (unit)
4. **`report --check`** passes when the 3 are in sync; exits 3 naming any
   drifted/missing one. (unit)
5. **`check` enforces the new set** (existence-gated); an out-of-sync/missing new
   file fails; a stale/ad-hoc `report.html` does not affect it. (unit)
6. **`init`** generates the 3 files and gitignores report.html; **`add`**
   regenerates the 3 and deletes a stale `report.github.html`. (unit)
7. **[post-merge] github.com render:** open `report_linked.md` on github.com and
   confirm it renders as a table with working links; run the consumer migration
   one-liner on a sibling repo and confirm `fr acceptance check` goes green.
