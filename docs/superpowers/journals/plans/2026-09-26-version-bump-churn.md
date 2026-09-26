# Journal: 2026-09-26-version-bump-churn

<!-- fr:journal kind=decision scope=plan id=plan-phase-shape created=2026-09-26T08:15:24 -->
### plan-phase-shape · decision · Six phases - skeleton surface list, PR gate, release workflow, acceptance, docs/config, manual live release

Acceptance (P4) depends only on the skeleton so it is independent of the release machinery.
The live first release is back-loaded as a [manual] phase; the PR ships it unimplemented.
Invariant for every phase: no version value changes (spec §4) - this PR's own gate proves rule 2.

<!-- fr:journal kind=decision scope=plan id=p1-surface-locators created=2026-09-26T08:24:56 phase=1 -->
### p1-surface-locators · decision · Surface locators are project.version, version, plugins[i].version, package[<name>].version (phase 1)

scripts/version_surfaces.py returns frozen Surface(file, locator, value); file is repo-relative POSIX.
uv.lock members are [[package]] blocks whose source has an editable or virtual key (6 here, incl.
super-fr-workspace via editable "."); fr-opencode-plugin is not a uv member, so it has no lock line.
Optional surfaces (marketplace.json, opencode package.json, uv.lock) are skipped when absent so the
module works on tmp repos; the root pyproject is required. write_version rewrites uv.lock textually
per [[package]] block (member version line only) and preserves JSON indent (2 for package.json, 4 else).

<!-- fr:journal kind=discovery scope=plan id=p1-write-version-byte-stable created=2026-09-26T08:24:56 phase=1 -->
### p1-write-version-byte-stable · discovery · write_version is byte-stable at the current version and moves exactly 17 lines on a bump (phase 1)

Checked in a scratch git copy of the tracked manifests + uv.lock: writing 4.23.0 left the tree clean;
writing 9.9.9 changed 11 files / 17 lines (6 uv.lock member lines), no registry package touched.
bump-version.py --check now lists 17 surfaces (was 11) and stays green.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T08:24:56 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

tests only; the one cleanup (a tuple-assert ruff flagged F631 and a hand-rolled frozen check) was folded into pytest.raises(FrozenInstanceError) before commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-26T08:24:56 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the glob helpers and per-file writers moved wholesale into scripts/version_surfaces.py, so nothing duplicated remained in bump-version.py; the label formatting was collapsed to one regex in P1.T3.S2

<!-- fr:journal kind=review scope=plan id=rp1-review created=2026-09-26T08:37:34 phase=1 -->
### rp1-review · review · Independent code review of phase 1: 3 findings (1 HIGH in, 1 MEDIUM in, 1 LOW out) (phase 1)

Dispatched reviewer (separate context, not the implementer) over dff6586e against spec §3.B/§7.9
and plan 01.yaml. Extraction sound; uv.lock rewrite byte-stable; no version value changed.
Raised: silent skip of missing single-instance surfaces (HIGH), tautological glob-derived test
expectations (MEDIUM), table-unaware first-match TOML regex (LOW, pre-existing).

<!-- fr:journal kind=finding scope=plan id=rp1-f1 created=2026-09-26T08:37:34 phase=1 state=open review_scope=in -->
### rp1-f1 · finding [open] (reviewer: in scope) · HIGH: version_surfaces() silently skips a missing marketplace.json / opencode package.json, weakening --check (phase 1)

scripts/version_surfaces.py guarded both with `.exists()`, so a lost manifest dropped out of
--check and write_version and still printed "ok". The old bump-version.py read both unconditionally.

<!-- fr:journal kind=finding scope=plan id=rp1-f2 created=2026-09-26T08:37:34 phase=1 state=open review_scope=in -->
### rp1-f2 · finding [open] (reviewer: in scope) · MEDIUM: tests re-derive expectations with the module's own globs and member predicate (phase 1)

tests/unit/test_version_surfaces.py rebuilt `expected` with the same globs and duplicated
`_is_member`, so a shared bug would pass silently.

<!-- fr:journal kind=finding scope=plan id=rp1-f3 created=2026-09-26T08:37:34 phase=1 state=open review_scope=out -->
### rp1-f3 · finding [open] (reviewer: out of scope) · LOW: write_version's TOML rewrite uses a table-unaware first-match regex (phase 1)

scripts/version_surfaces.py `_TOML_VERSION_RE` matches the first `version =` line in any table.
Identical to the pre-existing bump-version.py VERSION_RE/write_toml, relocated verbatim.

<!-- fr:journal kind=finding scope=plan id=rp1-f1-resolved created=2026-09-26T08:37:34 phase=1 state=fixed resolves=rp1-f1 -->
### rp1-f1-resolved · finding [fixed] · resolves rp1-f1: HIGH: version_surfaces() silently skips a missing marketplace.json / opencode package.json, weakening --check (phase 1)

`_required()` now fails loudly (SystemExit "version surface <path> is missing") for marketplace.json,
the OpenCode package.json and uv.lock; the temp-repo fixture writes them; a parametrized test pins
each missing file failing.

<!-- fr:journal kind=finding scope=plan id=rp1-f2-resolved created=2026-09-26T08:37:34 phase=1 state=fixed resolves=rp1-f2 -->
### rp1-f2-resolved · finding [fixed] · resolves rp1-f2: MEDIUM: tests re-derive expectations with the module's own globs and member predicate (phase 1)

The coverage test and the uv member set are hand-enumerated (11 files; 6 members), with a comment
saying why; the loud-failure and registry-exclusion tests still exercise the real parser.

<!-- fr:journal kind=finding scope=plan id=rp1-f3-resolved created=2026-09-26T08:37:34 phase=1 state=open resolves=rp1-f3 out_of_scope=true -->
### rp1-f3-resolved · finding [out-of-scope] · resolves rp1-f3: LOW: write_version's TOML rewrite uses a table-unaware first-match regex (phase 1)

Not caused by this change: the same regex and count=1 substitution lived in bump-version.py before
phase 1 moved it. Every current pyproject has [project].version before any other table.

<!-- fr:journal kind=decision scope=plan id=p2-surfaces-at-ref created=2026-09-26T08:48:12 phase=2 -->
### p2-surfaces-at-ref · decision · The gate reads version_surfaces at a git ref by materialising candidate files into a temp dir (phase 2) (phase 2)

`surfaces_at(repo, ref)` lists the tree at the ref, writes every file whose basename is one
of pyproject.toml, package.json, plugin.json, marketplace.json, uv.lock into a temp dir via
`git show`, and calls `version_surfaces(tmp)`. The basename set is only a superset filter;
which files are surfaces stays version_surfaces' decision, so there is still one list and
version_surfaces.py was not changed. A (file, locator) key present at HEAD but not at base
is an added surface and passes only at the base version.

<!-- fr:journal kind=decision scope=plan id=p2-merge-base-and-git-content created=2026-09-26T08:48:12 phase=2 -->
### p2-merge-base-and-git-content · decision · Every rule compares the merge base with HEAD and reads content from git, never the working tree (phase 2) (phase 2)

Rule 2 compares version values at `git merge-base <base> HEAD`, not the base tip, so a
release on main after the branch point is not reported as this PR's version edit (pinned by
test_version_is_compared_at_the_merge_base_not_the_base_tip). One `Diff` reader
(merge base + name-status, `before()`/`after()` via `git show`) feeds rule 1, rule 2 and the
floor rule, so an uncommitted fragment cannot make a red branch look green.

<!-- fr:journal kind=decision scope=plan id=p2-floor-scope created=2026-09-26T08:48:12 phase=2 -->
### p2-floor-scope · decision · Floors are found by tokenize in Python string tokens only; new floors are a per-file multiset of lower bounds (phase 2) (phase 2)

scripts/floors.py scans only `packages/<pkg>/src/**.py`, and only STRING / FSTRING_MIDDLE
tokens (comments excluded; a regex over quoted text is the fallback for untokenizable
source). A floor must not be preceded by an identifier char, so "demo>=1.0.0,<2.0.0" is not
one. The gate compares lower bounds per changed file as a multiset (base vs HEAD), so
reformatting a historical floor or moving its upper bound introduces nothing new; a new
lower bound above base must equal base + the highest bump among ADDED fragments.

<!-- fr:journal kind=discovery scope=plan id=p2-fragment-yaml-subset created=2026-09-26T08:48:12 phase=2 -->
### p2-fragment-yaml-subset · discovery · Fragments are parsed as a flat key-scalar YAML subset with the stdlib; richer YAML is refused (phase 2) (phase 2)

The gate and release script run under plain `python` / `uv run --no-project`, so no PyYAML.
changes.parse_text accepts `key: value` lines (plain or quoted, ` #` comments on plain
values, as YAML does) and refuses block scalars, continuation lines, duplicate and unknown
keys, each naming the file and field. A plain summary containing ` #` loses the tail, exactly
as real YAML would; quote it to keep it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-09-26T08:48:12 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

tests only; written table-driven from the start (one CASES list and shared edit builders), so nothing duplicated remained to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-09-26T08:48:12 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the cleanup owed here is the one P2.T3.S2 names (a single diff reader shared by the three rules) and was done there, not twice

<!-- fr:journal kind=review scope=plan id=rp2-review created=2026-09-26T09:03:31 phase=2 -->
### rp2-review · review · Independent code review of phase 2: 0 findings at the reviewer's bar; 2 sub-bar observations, verified here into 1 in-scope and 1 out-of-scope finding (phase 2)

Dispatched reviewer (separate context) over 88ab970c against spec §3.A/§3.B/§3.E/§5/§7 2,3,5.
Traced merge-base vs base tip against pull_request checkout semantics (refs/pull/N/merge, append-only
main): no evasion of rule 1 or 2. Floor scan, fragment subset parser, hand-bump refusal on every
surface type, fix lines, PR-only job, and the purge of the old script name all checked clean.
Two observations under its confidence bar were verified by the orchestrator: the quoted-summary
comment case reproduced (rp2-f1); the bare `python` CI call predates this change (rp2-f2).

<!-- fr:journal kind=finding scope=plan id=rp2-f1 created=2026-09-26T09:03:31 phase=2 state=open review_scope=in -->
### rp2-f1 · finding [open] (reviewer: in scope) · MEDIUM: a quoted fragment value followed by a ` #` comment keeps its literal quotes (phase 2)

scripts/changes.py `_scalar` only unquoted when the WHOLE value started and ended with a quote, so
`summary: "quoted text" # note` parsed to '"quoted text"' (reproduced) and would reach the release
notes verbatim; `bump: 'minor' # why` errored as an unknown bump.

<!-- fr:journal kind=finding scope=plan id=rp2-f2 created=2026-09-26T09:03:31 phase=2 state=open review_scope=out -->
### rp2-f2 · finding [open] (reviewer: out of scope) · LOW: the change-fragment CI step runs bare `python`, not uv-managed Python (phase 2)

.github/workflows/ci.yml:102. Works on ubuntu-latest (python-is-python3, 3.12 has tomllib).

<!-- fr:journal kind=finding scope=plan id=rp2-f1-resolved created=2026-09-26T09:03:31 phase=2 state=fixed resolves=rp2-f1 -->
### rp2-f1-resolved · finding [fixed] · resolves rp2-f1: MEDIUM: a quoted fragment value followed by a ` #` comment keeps its literal quotes (phase 2)

`_quoted()` scans to the real closing quote (honouring '' and \" escapes), allows only a ` #` comment
after it, and refuses any other trailing text with the field named. Two tests, red first: a quoted
value plus comment unquotes (bump and summary), and trailing non-comment text is refused.

<!-- fr:journal kind=finding scope=plan id=rp2-f2-resolved created=2026-09-26T09:03:31 phase=2 state=open resolves=rp2-f2 out_of_scope=true -->
### rp2-f2-resolved · finding [out-of-scope] · resolves rp2-f2: LOW: the change-fragment CI step runs bare `python`, not uv-managed Python (phase 2)

Not caused by this change: the replaced version-bump-required job invoked
`python scripts/check-version-bump-needed.py` the same way; phase 2 only swapped the script name.

<!-- fr:journal kind=decision scope=plan id=p3-release-computes-the-number created=2026-09-26T09:15:50 phase=3 -->
### p3-release-computes-the-number · decision · release.py computes X.Y.Z itself and calls bump-version.py with the explicit number (phase 3) (phase 3)

The bump is aggregated (or overridden) in release.py, then walked past any pre-existing
`v` tag with the same bump kind, and only then handed to `bump-version.py X.Y.Z`. So the
manual-tag rule (§5) and the override rule live in one place, and bump-version.py stays a
dumb writer. An override whose tag exists is refused rather than walked.

<!-- fr:journal kind=decision scope=plan id=p3-staged-diff-check created=2026-09-26T09:15:50 phase=3 -->
### p3-staged-diff-check · decision · The staged-diff check is per file - line count equals that file's surface count, and every removed line with old->new substituted equals the added line (phase 3) (phase 3)

`verify_staged` allows a consumed fragment only as a deletion and a surface file only as a
modification whose -U0 hunks are exactly N version lines (N = that file's
version_surfaces() entries) differing only by old->new. Anything else, including a stray
untracked file swept in by `git add -A`, refuses naming the path. sync_to_tip therefore
deliberately does NOT `git clean`: a stray file is refused, never deleted.

<!-- fr:journal kind=decision scope=plan id=p3-notes-from-the-commit created=2026-09-26T09:15:50 phase=3 -->
### p3-notes-from-the-commit · decision · Release notes always come from the release commit body, first run and rerun alike (phase 3) (phase 3)

`release_notes` reads `git log -1 -S<version> -- pyproject.toml`; if that commit's subject
is `release: vX.Y.Z` its body (summaries grouped Major/Minor/Patch) is `--notes`, else
(hand-bumped history, or an override with no fragments) `--generate-notes` alone. One path
serves the first run and a rerun after a crash between push and tag.

<!-- fr:journal kind=decision scope=plan id=p3-exit-codes-and-tags created=2026-09-26T09:15:50 phase=3 -->
### p3-exit-codes-and-tags · decision · Exit codes 1 refusal, 2 lost race x3, 3 floor mismatch after tagging; tags are read after fetch --prune-tags (phase 3) (phase 3)

EXIT_FLOOR (3) is distinct so the job fails visibly after the tag and Release exist. Tag
existence is checked on local refs after `fetch --prune --prune-tags --tags`, so a tag
deleted on origin is gone locally too (a rerun after a deleted tag re-tags). The floor check
compares `git describe --match v[0-9]*` (previous tag) with HEAD using floors.new_floors /
lower_bound_ok, so historical floors and upper-bound moves never trip it. The dispatch
`version` input reaches the script through env, never spliced into the shell.

<!-- fr:journal kind=discovery scope=plan id=p3-agents-md-auto-tag-mention created=2026-09-26T09:15:50 phase=3 -->
### p3-agents-md-auto-tag-mention · discovery · AGENTS.md still names auto-tag.yml as the tagger; left for the docs phase (phase 3) (phase 3)

AGENTS.md "Release / version bumping" says `.github/workflows/auto-tag.yml` tags on merge and
that branch protection blocks direct commits. Both are phase-5 (§3.G) rewrites and outside
this phase's file list, so they were not touched here; auto-tag.yml itself is deleted.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-09-26T09:15:50 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

tests only; one World fixture (bare origin, release clone, a second clone for other people's pushes, injected bump/lock/gh) was built first and every case reuses it, so nothing duplicated remained

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-09-26T09:15:50 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

the cleanup owed here is the one P3.T3.S2 names (push/retry loop and tag/release as separate functions); it was written that way in green and checked in P3.T3.S2, not done twice
