# Journal: 2026-10-06-verification-strategies

<!-- fr:journal kind=decision scope=plan id=p1-shared-shipped-walk created=2026-10-06T11:28:03+00:00 phase=1 -->
### p1-shared-shipped-walk · decision · shared shipped-dir walk lives in fr/_shipped.py; workflow keeps its own packaged_shipped_workflows_dir (phase 1)

fr/_shipped.py holds packaged_dir(dirname), shipped_dirs, lookup_candidates, listing and MARKETPLACE_ROOT (re-exported from workflow.resolve). workflow.resolve keeps a thin packaged_shipped_workflows_dir wrapper because tests monkeypatch it by that name. The packaged-dir cache moved from two module globals to a per-dirname dict.

<!-- fr:journal kind=decision scope=plan id=p1-strategy-template-shape created=2026-10-06T11:28:03+00:00 phase=1 -->
### p1-strategy-template-shape · decision · install/scenario accept a string (shell-split) or a list, stored as tuple; check_workflow takes optional repo_root (phase 1)

StrategyManifest.install/scenario normalise to tuple[str,...] | None. check_workflow(manifest, repo_root=None) resolves `verification:` against shipped sources only when repo_root is None; the CLI passes the repo root. resolve_strategy accepts repo_root=None for the same reason. effective_strategy(row_verify, row_id, section, shape_default) and is_post_merge(strategy, repo_root) take plain strings per the plan; is_post_merge raises StrategyError on an unresolvable name. spec_section ignores prose and fenced code, and errors only on a bullet or strategy: line that breaks the grammar; the reason is optional in the grammar (self-review owns 'reason owed').

<!-- fr:journal kind=discovery scope=plan id=p1-no-change-fragment created=2026-10-06T11:28:03+00:00 phase=1 -->
### p1-no-change-fragment · discovery · no .changes fragment added in phase 1 (phase 1)

This phase touches packages/*/src and plugins/*/workflows, so the PR needs a .changes/<branch-slug>.yaml fragment; none was in this phase's steps. It is owed before delivery.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-06T11:28:03+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the task's GREEN step is itself the refactor (the four-place walk factored into fr/_shipped.py, workflow/resolve.py re-pointed, behaviour pinned by the unchanged workflow tests); nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-06T11:28:03+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

data-only task: four manifests plus a byte copy; no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-06T11:28:03+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

thin CLI mirroring workflow_cmd.py and one optional field; nothing duplicated worth extracting

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-06T11:28:03+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

two small pure functions written once against their tests; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-06T11:34:51+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · check_workflow callers omit repo_root, so a repo-authored strategy is refused outside `fr workflow check` (phase 1)

run_cmd.py:917/4138/4170, artifacts/validate.py:144 and plan_ops.py:1638 called
check_workflow(manifest) with no root; resolve_strategy then searched only shipped places,
so a shape naming a repo-authored strategy (R1/R4/R5) passed `fr workflow check` but was
refused by `fr run start`, `fr validate artifacts` and `fr plan self-review`.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-10-06T11:34:51+00:00 phase=1 -->
### p1-review · review · Phase 1 independent code review — 1 finding (p1-r1, in scope, fixed) (phase 1)

Independent reviewer (separate context) reviewed cd689f2ce..a919a060d against spec §A/§B and
01.yaml. Raised p1-r1 only. Verified sound: the resolve.py refactor keeps order, errors and
exports; wheel packaging ships fr/verifications; the tripwire compares bytes both ways; the
group is not migration-exempt; the parser's separators, fences and duplicates; R7 precedence.
Received: p1-r1 verified against the five call sites and fixed structurally — repo_root is now
a required argument (no default), every caller passes its root, tests pass None explicitly;
a regression test fails without the validate.py fix and passes with it.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-06T11:34:51+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: check_workflow callers omit repo_root, so a repo-authored strategy is refused outside `fr workflow check` (phase 1)

check_workflow(manifest, repo_root) now requires the root; all five callers pass theirs; regression test test_every_shape_check_sees_a_repo_authored_strategy.

<!-- fr:journal kind=decision scope=plan id=p2-live-row-refuses-v3-spelling created=2026-10-06T12:16:40+00:00 phase=2 -->
### p2-live-row-refuses-v3-spelling · decision · the live Row/AcceptanceItem refuse `verify: post-merge`; resolution is checked where the repo is known (phase 2)

`verify` is a StrictStr, but the live models refuse the v3 spelling by name (pointing at
`fr migrate artifacts --yes`), so a body still carrying it is visibly not v4 — which is
what makes the 3 -> 4 crash-window check sound. Whether a name RESOLVES needs a repo
root, so it is checked in `fr validate artifacts` (structure.validate_matrix), in
apply_record (record.apply.strategy_error) and up front in `--verify`/`--strategy`.

<!-- fr:journal kind=decision scope=plan id=p2-record-migration-rewrites-post-merge created=2026-10-06T12:16:40+00:00 phase=2 -->
### p2-record-migration-rewrites-post-merge · decision · record 7 -> 8 rewrites a v7 acceptance entry's `verify: post-merge` to `live` instead of refusing it (phase 2)

The spec calls the record hop stamp-only because "every v7 record is a valid v8 record".
That is false for exactly one shape: an acceptance entry saying `verify: post-merge`,
which the v8 model refuses. Rather than strand such an in-flight record, the hop gives
it what the matrix row gets (R7): read through the frozen RecordV7, build in memory,
validate as v8, write once atomically; a body already v8 is left for the runner to
stamp. Every other v7 record is stamp-only, as specified. The 6 -> 7 hop's
"already v7?" check now asks RecordV7 rather than the live (now v8) model.

<!-- fr:journal kind=decision scope=plan id=p2-one-forge-command-table created=2026-10-06T12:16:40+00:00 phase=2 -->
### p2-one-forge-command-table · decision · hostclient.FORGE_COMMANDS holds PR and issue ops; PR_COMMANDS / ISSUE_COMMANDS are views (phase 2)

One per-backend table, so a backend cannot gain a PR verb and lack an issue verb.
issue_command(repo_root, op, ref=owner/repo#n, comment=, label=) adds `--repo owner/repo`
(gh -R/--repo, glab -R/--repo, tea --repo) because a row's issue may live in another
repo than the checkout; comment/label are shell-quoted. tea's unlabel is the spec's
one-line manual instruction, written as a `#` line so pasting it runs nothing.

<!-- fr:journal kind=decision scope=plan id=p2-spec-verification-seam created=2026-10-06T12:16:40+00:00 phase=2 -->
### p2-spec-verification-seam · decision · fr.verification.rows.SpecVerification binds a spec's section + shape default for every consumer (phase 2)

pr_body, run/visual, plan self-review and acceptance/walks all get a row's effective
strategy through SpecVerification (which calls effective_strategy / is_post_merge);
none compares a string. Shape default: the run's workflow (pr_body) or the plan's
(visual, self-review). Outside a run (walks.holds_open) no shape is known, so the
default does not apply, and an unreadable section/strategy holds the issue open
(a premature close is the worse error). visual treats an unresolvable strategy as
owing evidence (fail closed).

<!-- fr:journal kind=discovery scope=plan id=p2-set-status-scenario created=2026-10-06T12:16:40+00:00 phase=2 -->
### p2-set-status-scenario · discovery · set-status also takes --scenario (phase 7 P7.T1 sets scenarios through `fr acceptance`) (phase 2)

§E lists only --issue and --walk for set-status, but phase 7 says "use the scenario
field through `fr acceptance` once P2 added it" and self-review now tells the operator
to set one; `add` alone could not reach existing rows. Omitting it keeps the row's value.

<!-- fr:journal kind=discovery scope=plan id=p2-self-review-scenarios-owed created=2026-10-06T12:16:40+00:00 phase=2 -->
### p2-self-review-scenarios-owed · discovery · self-review of this plan now errors on six candidate rows with no scenario — owed by phase 7 (phase 2)

With the Verification checks live, `fr plan self-review` on this plan reports
verification-strategy-resolution, shipped-verification-strategies,
spec-verification-section, walk-recording-prints-close, prerelease-command-shape and
awaiting-live-triage (strategy candidate, agent pre-merge) as naming no `scenario`.
Phase 7 P7.T1 adds the scenario scripts and sets the field. No gate re-runs self-review
before then (only the plan-review step, already passed), so nothing is blocked.

<!-- fr:journal kind=discovery scope=plan id=p2-stray-r1-records-dir created=2026-10-06T12:16:40+00:00 phase=2 -->
### p2-stray-r1-records-dir · discovery · an empty untracked docs/superpowers/runs/r1.records/ sits in the worktree, created before this phase (phase 2)

Timestamped 13:25, before phase 2 began; empty and untracked, so git does not see it.
Some test appears to create it against the repo rather than tmp_path; not traced.

<!-- fr:journal kind=finding scope=plan id=p2-tea-remove-labels created=2026-10-06T12:16:40+00:00 phase=2 state=open review_scope=out -->
### p2-tea-remove-labels · finding [open] (reviewer: out of scope) · the spec says tea has no unlabel command, but the installed tea's `issues edit` has --remove-labels (phase 2)

`tea issues edit --help` (homebrew tea on the operator host) lists `--add-labels` and
`--remove-labels`. The implementation follows the spec (a manual line for tea's
unlabel; `--add-labels` for issue-label) and its test pins that; if the spec is
corrected, ISSUE_COMMANDS["gitea"]["issue-unlabel"] becomes
`tea issues edit {number} --repo {repo} --remove-labels {label}`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-06T12:16:40+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

a new frozen module plus a one-import re-point of guard_matrix; nothing duplicated to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-06T12:16:40+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the migration is one function written against its tests; the two row checks were shared (check_verify, check_issue_refs) as they were written, so AcceptanceItem reuses them

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-06T12:16:40+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

RecordV7 reuses the frozen v6 classes that did not change instead of copying them; the apply-path union helper was extracted while writing it

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-06T12:16:40+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

the four consumers were routed through one new seam (fr.verification.rows.SpecVerification) as they were changed; no leftover string compares remain

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-10-06T12:16:40+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

the forge table was widened in place with PR/issue views derived from it rather than a second table; the flag plumbing mirrors the existing set-status/add idiom

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t6 created=2026-10-06T12:16:40+00:00 phase=2 -->
### no-refactor-p2-t6 · discovery · no-refactor-because P2.T6 (phase 2)

one self-contained check function beside the acceptance-link check, using the same seam; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-06T12:23:33+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · tea gets a manual unlabel line though `tea issues edit --remove-labels` exists (phase 2)

hostclient.py:71-73 printed "# tea has no unlabel command …" and issue_command carried a
`startswith("#")` no-quote branch for it. The spec's premise was wrong: the installed tea's
`issues edit --help` lists --remove-labels (and --repo), the subcommand issue-label already uses.

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-10-06T12:23:33+00:00 phase=2 -->
### p2-review · review · Phase 2 independent code review — 1 finding (p2-r1, in scope, fixed) (phase 2)

Independent reviewer reviewed 4e4b49d88..HEAD against spec §B/§E, 02.yaml and the
artifact-versioning rule. Judged the recorded departures: (a) record 7→8 rewriting
verify post-merge→live is correct and necessary (a stamp-only hop leaves an unreadable v8);
(b) set-status --scenario justified by self-review's R10 refusal; (c) --repo on issue commands
correct; (d) tea → p2-r1. Verified sound: MatrixV3 inlines its vocabularies and is hash-pinned;
every matrix hop reads through it; 3→4 is one atomic write, byte-identical on refusal, chain
[2,3,4] asserted; registry at matrix 4 / record 8; no string compare of post-merge left outside
legacy/migration modules; walk_verified and issues_now_closable match R14/R16.
Received: p2-r1 verified on the installed tea (`tea issues edit --help`), fixed with a red-first
test; the spec's §E tea sentence corrected to match.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-06T12:23:33+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: tea gets a manual unlabel line though `tea issues edit --remove-labels` exists (phase 2)

tea unlabel is `tea issues edit {number} --repo {repo} --remove-labels {label}`; the manual-line branch and comment are gone; test pin updated (red first); spec §E corrected.

<!-- fr:journal kind=finding scope=plan id=p2-tea-remove-labels-resolved created=2026-10-06T12:23:33+00:00 phase=2 state=open resolves=p2-tea-remove-labels out_of_scope=true -->
### p2-tea-remove-labels-resolved · finding [out-of-scope] · resolves p2-tea-remove-labels: the spec says tea has no unlabel command, but the installed tea's `issues edit` has --remove-labels (phase 2)

Same fact as p2-r1, which carries the fix in scope; this executor-filed duplicate is closed without its own fix.

<!-- fr:journal kind=decision scope=plan id=p3-walk-log-header-is-the-proof created=2026-10-06T12:43:43+00:00 phase=3 -->
### p3-walk-log-header-is-the-proof · decision · a walk log is trusted by its fr-walk header, code tree and steps, not by who ran it (phase 3)

The log is `---`-fenced YAML (fr-walk: 1, run, strategy, code_tree, harness, model, steps)
followed by each step's output. deliver refuses a log with no header ("not a walk log"), a
code_tree != HEAD's, a failing step, a missing smoke (install, smoke:version, smoke:status),
an owed row with no `row:<id>` step, and uncommitted code paths. It does NOT tie the log to
the command that wrote it (tests does, via the transcript); a header forged by hand passes.
Recorded as a known limit rather than inventing a signature scheme the spec does not ask for.

<!-- fr:journal kind=decision scope=plan id=p3-walk-strategy-and-gates created=2026-10-06T12:43:43+00:00 phase=3 -->
### p3-walk-strategy-and-gates · decision · walk covers rows whose effective strategy is the run's (or --strategy); refuses dirty code, post-merge and prerelease sources (phase 3)

`--strategy` defaults to the spec section's `strategy:` else the shape default. The walk
refuses (exit 2): a post-merge strategy, an uncommitted code path (the log records HEAD's
tree, so a dirty tree would be false evidence), a `source: prerelease` strategy (walk does
not build an rc; install it and use --client), a row with no scenario, an unknown --row.
A failing step exits 1; the operator's fr changing exits 2 AFTER the log is written. The child
env drops FR_HARNESS_FR so the candidate is not judged against the operator's identity pin.
deliver owes ONE log covering every agent pre-merge row, so a run mixing two agent
strategies cannot satisfy it with one walk; not supported.

<!-- fr:journal kind=decision scope=plan id=p3-premature-closes-signature created=2026-10-06T12:43:43+00:00 phase=3 -->
### p3-premature-closes-signature · decision · premature_closes takes a holds_open callable as a fourth argument (phase 3)

The spec names premature_closes(live_body, matrix, identity). Whether a row holds an issue
open needs the run's section and shape default, so the predicate is injected
(pr_body.holds_open_for_run builds it; rows of other specs fall back to
acceptance.walks.holds_open). The gate (run_cmd._refuse_premature_closes) is inert when no
matrix row cites an issue, so repos without a remote or identity are unaffected.

<!-- fr:journal kind=discovery scope=plan id=p3-deliver-evidence-order created=2026-10-06T12:43:43+00:00 phase=3 -->
### p3-deliver-evidence-order · discovery · the walk-owed predicate sits before rule 2 in _verified_evidence, and an unreadable section/matrix/strategy fails closed (phase 3)

The old run_cmd.py:1773-1776 rule-2 block is now the `missing` list; `walk` is excluded
from it only when _walk_obligation says not owed. A malformed ## Verification section or an
unresolvable strategy refuses deliver (fr cannot decide whether a walk is owed). R10 (owed
row with no scenario) is refused by id inside the same obligation check. Both shapes' deliver
evidence (plugin + wheel copies) gained `walk`; three tripwire tests pinning the old lists and
REQUIRED_SECTIONS were updated.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-06T12:43:43+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

a new module (verification/walk.py) and one subcommand; the only shared piece (shape_default) was moved into verification/rows.py as written

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-06T12:43:43+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

one verifier branch beside the tests branch; nothing duplicated to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-06T12:43:43+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

shared_closing_keywords was refactored onto the _closing_lines generator that closing_refs shares, as part of the change

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · walk evidence trusts the log's self-declared header (forgeable) (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · check_walk_log never binds log.strategy or log.run to what is owed (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · gh#683 guard raised after writing an all-pass log deliver accepts (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · premature_closes misses closes GitHub honours (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · pre-merge-owed section printed a walk command prerelease rows always refuse (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · prose ## Verification in older specs made every deliver refuse (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · walk= ~ path never expanded (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · walk's throwaway prefix never removed (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-10-06T13:13:10+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · git failure in walk_cmd gave a traceback (phase 3)

Raised by the independent phase-3 reviewer with file:line evidence (see review p3-review).

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-10-06T13:13:10+00:00 phase=3 -->
### p3-review · review · Phase 3 independent code review — 9 findings, all in scope, all fixed (phase 3)

Independent reviewer checked 6fa8c9f50 against spec §C/§D and 03.yaml, and confirmed or refuted three background security flags: forgeable walk evidence (confirmed, p3-r1), gate field mismatch (partly, p3-r2), and parser differential (partly, p3-r4; the keyword-adjacency case is refuted because shared_closing_keywords already refuses it). It also raised p3-r3 and p3-r5 through p3-r9. All fixes were made test-first by a separate fixer context. Three further background security flags on the new observed.py predicate (a parser differential, an incomplete denylist, an allowlist semantic escape) drove the switch to the structural allowlist plus binding to the manifest sha, all red-tested. The residual trust boundary, a background writer during the window, equals the tests witness's and is documented beside the predicate. Full suite after the fixes: 9254 passed, 105 skipped.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: walk evidence trusts the log's self-declared header (forgeable) (phase 3)

Log must sit under walk_log_dir(run) as a regular non-symlink file; its mtime must lie inside the window of THIS session's command that is exactly `[cd <p> &&] fr|uv run fr verification walk … --run <run>` (allowlist: no env prefix, custom binary, uv flags, redirects, substitution, extra segments, background, duplicate --run), opened after deliver; unreadable transcript → unobserved=walk; the log records the strategy manifest's source+sha256 and deliver refuses a mismatch. Commits 7c81292b4, 17556fac0, aedbfc3fc, 275c5b736.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: check_walk_log never binds log.strategy or log.run to what is owed (phase 3)

check_walk_log(..., run=) refuses another run's or another strategy's log; WalkOwed.strategy carries the owed one. 83644164e.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: gh#683 guard raised after writing an all-pass log deliver accepts (phase 3)

Fingerprint checked right after INSTALL and at the end; a change is a failing operator-fr-unchanged step in the log. 316e293f7.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: premature_closes misses closes GitHub honours (phase 3)

Reads the whole body incl. fr's render; accepts GH-<n>; owner/repo compared case-insensitively; shared_closing_keywords unchanged. 7dab954fa.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: pre-merge-owed section printed a walk command prerelease rows always refuse (phase 3)

Prerelease rows print the prerelease command plus an executable install-and-run line, tested by running it. 4c18cb2f4.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: prose ## Verification in older specs made every deliver refuse (phase 3)

A section with no grammar line is no section; one grammar line keeps the strict parse. 2530e95d0.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: walk= ~ path never expanded (phase 3)

expanduser before is_absolute. 0b6517280.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: walk's throwaway prefix never removed (phase 3)

rmtree in finally after log + fingerprint. 316e293f7.

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-10-06T13:13:10+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: git failure in walk_cmd gave a traceback (phase 3)

GitUnavailableError refused with exit 2. 3e22530c8.

<!-- fr:journal kind=decision scope=plan id=p4-batch-awaits-live created=2026-10-06T13:29:40+00:00 phase=4 -->
### p4-batch-awaits-live · decision · a batch whose open members all await live is no next_up row and holds no wave open (phase 4)

Spec names next_up and preselected_wave as excluding awaiting-live issues but
those read batches and features. views.awaits_live(batch, facts) is true when a
batch has open members and all carry fr:awaiting-live; such a batch is skipped in
both next_up passes and in preselected_wave, and feature rows drop awaiting
members. A merged batch is unaffected (its stage already says merged).

<!-- fr:journal kind=decision scope=plan id=p4-refs-line-reader created=2026-10-06T13:29:40+00:00 phase=4 -->
### p4-refs-line-reader · decision · Refs lines are read with the closing-keyword scanner, keyword swapped (phase 4)

pr_body.referenced_refs reuses _closing_lines (code/fence/render-marker skipping,
GH-n spellings) with a Refs keyword, and closeout.awaiting_live_lines normalizes
through normalize_issue_ref. The label command comes from issue_command(issue-label);
an unreadable PR or matrix is said in the brief, tracking none prints nothing.

<!-- fr:journal kind=discovery scope=plan id=p4-awaiting-live-label-single-source created=2026-10-06T13:29:40+00:00 phase=4 -->
### p4-awaiting-live-label-single-source · discovery · walks.AWAITING_LIVE_LABEL now derives from labels.FR_AWAITING_LIVE (phase 4)

Phase 3 had hard-coded the string in acceptance/walks.py; it now reads the
registered LabelDef so the unlabel command and the label command cannot drift.

<!-- fr:journal kind=discovery scope=plan id=p4-install-atomic-flaky-under-load created=2026-10-06T13:29:40+00:00 phase=4 -->
### p4-install-atomic-flaky-under-load · discovery · test_install_atomic::test_fr_stays_runnable_throughout_a_reinstall failed once in a loaded full run (phase 4)

Failed in one -n auto run, passed alone (8/8) and in the immediately following
full run (9270 passed). Unrelated to this phase; not investigated further.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-10-06T13:29:40+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

closing-keyword scanning was generalised in place (_closing_lines takes the keyword) rather than copied for Refs; nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-10-06T13:29:40+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

one is_awaiting_live predicate in check.py serves check, views and render; no second label test exists

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-10-06T13:50:03+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · awaiting-live issue with leftover fr:in-progress also flagged stale dispatch and in needs-you (phase 4)

Raised by the independent phase-4 reviewer with file:line evidence (see p4-review).

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-10-06T13:50:03+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · next_up hid awaiting batches the driver still dispatched (phase 4)

Raised by the independent phase-4 reviewer with file:line evidence (see p4-review).

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-10-06T13:50:03+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · Refs-merged batch derived partial and blocked dependents (phase 4)

Raised by the independent phase-4 reviewer with file:line evidence (see p4-review).

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-10-06T13:50:03+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · close-out label command fails when the label does not exist (phase 4)

Raised by the independent phase-4 reviewer with file:line evidence (see p4-review).

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-10-06T13:50:03+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · parked/duplicate awaiting-live issues rendered twice (phase 4)

Raised by the independent phase-4 reviewer with file:line evidence (see p4-review).

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-10-06T13:50:03+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · no_severity still asked to rank awaiting-live issues (phase 4)

Raised by the independent phase-4 reviewer with file:line evidence (see p4-review).

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-10-06T13:50:03+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · referenced_refs read fr's render and matched prose 'ref' (phase 4)

Raised by the independent phase-4 reviewer with file:line evidence (see p4-review).

<!-- fr:journal kind=review scope=plan id=p4-review created=2026-10-06T13:50:03+00:00 phase=4 -->
### p4-review · review · Phase 4 independent code review — 7 findings, all in scope, all fixed (phase 4)

Reviewer checked labels/closeout/pr_body/triage check, views and render against §F (R17, R18). It confirmed: one label definition, closed issues excluded, a single PR-body read, nothing under tracking none, pure views, facts schema unchanged. It judged the test_install_atomic single failure an unrelated timing flake, since this phase does not touch install. Fixes were made test-first by a separate fixer. The orchestrator decided one shared rule for the board and the driver (p4-r2) and that awaiting-live members count as closed for the batch stage (p4-r3). Suite: 9285 passed, 105 skipped.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-10-06T13:50:03+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: awaiting-live issue with leftover fr:in-progress also flagged stale dispatch and in needs-you (phase 4)

stale_dispatches excludes awaiting-live. 11bccb9a0.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-10-06T13:50:03+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: next_up hid awaiting batches the driver still dispatched (phase 4)

One rule: check.batch_awaits_live; drive_pass emits held (AWAITING_LIVE_HOLD, not pending); next_up reads the held action; kanban card says why. 9f5a3cf49.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-10-06T13:50:03+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: Refs-merged batch derived partial and blocked dependents (phase 4)

Awaiting-live members count as closed in derive_batch_stage; the preselected_wave workaround removed (a proposed, wholly-awaiting batch still holds no wave open). 599e191aa.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-10-06T13:50:03+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: close-out label command fails when the label does not exist (phase 4)

LABEL_COMMANDS label-create per backend (flags checked against glab/tea --help); the brief prints one create line per repo before its add lines. 6749e766d.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-10-06T13:50:03+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: parked/duplicate awaiting-live issues rendered twice (phase 4)

_parked excludes awaiting-live. 73dee0e47.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-10-06T13:50:03+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: no_severity still asked to rank awaiting-live issues (phase 4)

Excluded; check.py docstring lists every excluded set. 224165148.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-10-06T13:50:03+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: referenced_refs read fr's render and matched prose 'ref' (phase 4)

as_github=False, plural-only refs keyword, docstring corrected (GH-n Refs no longer labelled — accepted narrow loss). d31f8b2a8.

<!-- fr:journal kind=decision scope=plan id=p5-conflict-checkout-is-the-clone created=2026-10-06T14:11:23+00:00 phase=5 -->
### p5-conflict-checkout-is-the-clone · decision · a fresh conflict session's checkout is the repo clone, as a close-out's is (phase 5)

§G says "the batch worktree as checkout". The driver has no batch worktree of its
own: dispatch_batch passes the repo clone (`--checkout` map) as payload.checkout,
and the batch session makes its own fr-isolation workspace for the branch. The
conflict item does the same as the close-out (`self.checkout(repo).path`), and
its brief names the branch, so `fr isolation up --branch <branch>` resumes the
batch's workspace. The merge scratch worktree is not used: it is driver-owned and
removed after a merge.

<!-- fr:journal kind=decision scope=plan id=p5-conflict-delivery-rules created=2026-10-06T14:11:23+00:00 phase=5 -->
### p5-conflict-delivery-rules · decision · session delivery needs both SessionInspector and SessionMessenger; `unknown` waits like working (phase 5)

A runner that can message but cannot report status gets the fresh path: messaging
a session of unknown state could answer a permission prompt. A status of `unknown`
sends nothing and records nothing, like `working`/`blocked`; only `absent`/`done`
start a fresh session. A failed status read or send is one line, no event, retried
next pass. A fresh item already live in the runner (a pass killed between dispatch
and its event) is recorded, not restarted. The message target is the latest fresh
conflict item since the latest dispatch (else the dispatch item); the fresh item
number counts every fresh event, so ids never repeat across re-dispatches.

<!-- fr:journal kind=decision scope=plan id=p5-conflict-keeps-exit-1 created=2026-10-06T14:11:23+00:00 phase=5 -->
### p5-conflict-keeps-exit-1 · decision · a conflict still sets failed_write, so `--once` exits 1 even when handed back (phase 5)

The merge was refused, exactly as before this phase; the hand-back is reported on
the same `stopped:` line (suffixed with what was done) and counts as acted. Skipped
repeats keep the `stopped again at` line.

<!-- fr:journal kind=discovery scope=plan id=p5-mirrors-in-facts-without-facts-bump created=2026-10-06T14:11:23+00:00 phase=5 -->
### p5-mirrors-in-facts-without-facts-bump · discovery · TriageConfig.mirrors lands in facts.json without a FACTS_SCHEMA bump (phase 5)

Facts.to_json dumps defaults, so every new facts.json carries `mirrors: []` per
configured repo and an older fr reading it refuses "invalid facts" (re-collect
fixes it). This follows the precedent of `export` (pages-goal), which also added a
TriageConfig key under facts schema 4; gh#885's reasoning would argue for a bump.
Judgements moved 4 -> 5 as planned; docs/triage's schema-4 file still loads.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-10-06T14:11:23+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

an exception subclass and one event model on the SCHEMA_3_EVENTS pattern; nothing duplicated to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-10-06T14:11:23+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

one pure function written once against its tests; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t3 created=2026-10-06T14:11:23+00:00 phase=5 -->
### no-refactor-p5-t3 · discovery · no-refactor-because P5.T3 (phase 5)

a one-method protocol and a one-call herdr method; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t4 created=2026-10-06T14:11:23+00:00 phase=5 -->
### no-refactor-p5-t4 · discovery · no-refactor-because P5.T4 (phase 5)

the refactor was done in GREEN: the stop-line reporting moved out of _merge_batch into _stopped_line so the conflict path reuses it, and _fresh_conflict takes the launch and branch _hand_back already resolved instead of re-resolving them

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-10-06T14:28:18+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · fresh conflict session starts in the driver's clone with no way onto the batch branch (phase 5)

Raised by the independent phase-5 reviewer with file:line evidence (see p5-review).

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-10-06T14:28:18+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · mirrors changes facts.json without a facts schema bump (phase 5)

Raised by the independent phase-5 reviewer with file:line evidence (see p5-review).

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-10-06T14:28:18+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · missing tests: committed schema-4 judgements load; wait-behind batch retried after its blocker merges (phase 5)

Raised by the independent phase-5 reviewer with file:line evidence (see p5-review).

<!-- fr:journal kind=review scope=plan id=p5-review created=2026-10-06T14:28:18+00:00 phase=5 -->
### p5-review · review · Phase 5 independent code review — 3 findings, all in scope, all fixed (phase 5)

Reviewer verified §G rule by rule: MergeConflictError, ConflictEvent and the schema gate, the pure conflict_decision order, idle-only delivery, SessionMessenger outside CAPABILITIES, needs-you merge-conflict and its clearing, restart safety through persisted events, and a stable unique conflict-<id>-<n>. On the implementer's decisions: (a) the clone checkout was wrong as shipped (p5-r1); (b) unknown waits like working is defensible, a follow-up could surface a long-lasting unknown; (c) --once exit 1 on a conflict is consistent; (d) needed a facts bump (p5-r2). Fixes were made test-first by a separate fixer. Suite: 9326 passed, 105 skipped.

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-10-06T14:28:18+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: fresh conflict session starts in the driver's clone with no way onto the batch branch (phase 5)

The brief's first step is `fr isolation up --branch <branch>` (resumes the batch workspace; harmless for a live session); no git checkout/switch in the brief; spec R20/§G updated to six steps. 33cd0243e.

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-10-06T14:28:18+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: mirrors changes facts.json without a facts schema bump (phase 5)

FACTS_SCHEMA 5, FACTS_READS (3,4,5); gh#885 comment names mirrors and notes export; schema pins updated. 7e26e4eec.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-10-06T14:28:18+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: missing tests: committed schema-4 judgements load; wait-behind batch retried after its blocker merges (phase 5)

Both tests added (behaviour already correct, so green on first run). 9d82b6ac7.

<!-- fr:journal kind=decision scope=plan id=p6-prerelease-source-line created=2026-10-06T14:54:15+00:00 phase=6 -->
### p6-prerelease-source-line · decision · the command prints the install source as a bare line `git+<remote>@<tag>`; PR-body route needed no change (phase 6)

pr_body.prerelease_route says the command prints the rc's `<source>`, which feeds `.fr/candidate-install {prefix} {source}`. The command prints that exact form (remote = `git remote get-url`, tag `rc/<slug>/<sha12>`, sha = the branch head, remote-tracking ref first) on a line of its own, pinned by a test. Same tag shape as prerelease.yml (slug `/`->`-`, sha12 of HEAD).

<!-- fr:journal kind=discovery scope=plan id=p6-workflow-permissions created=2026-10-06T14:54:15+00:00 phase=6 -->
### p6-workflow-permissions · discovery · prerelease.yml needs pull-requests: read beside contents: write (phase 6)

The release notes name the PR via `gh pr list --head`, which needs pull-requests: read. The structure test asserts contents: write and every other permission read-only. checkout is pinned by SHA (test_tripwire_actions_pinned). The workflow was never run (only parsed).

<!-- fr:journal kind=discovery scope=plan id=p6-install-atomic-flaky-again created=2026-10-06T14:54:15+00:00 phase=6 -->
### p6-install-atomic-flaky-again · discovery · test_install_atomic::test_fr_stays_runnable_throughout_a_reinstall failed in two loaded full runs, passes alone and in the final run (phase 6)

Same load-sensitive flake as p4-install-atomic-flaky-under-load; the final suite log is green.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-10-06T14:54:15+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

one new GhClient method and one thin subcommand; the argv builder (workflow_run_args) was written once and shared by the real client and --dry-run, nothing to clean

<!-- fr:journal kind=finding scope=plan id=p6-r1 created=2026-10-06T15:05:20+00:00 phase=6 state=open review_scope=in -->
### p6-r1 · finding [open] (reviewer: in scope) · prerelease SHA could come from a local-only or stale ref (phase 6)

Raised by the independent phase-6 reviewer with file:line evidence (see p6-review).

<!-- fr:journal kind=finding scope=plan id=p6-r2 created=2026-10-06T15:05:20+00:00 phase=6 state=open review_scope=in -->
### p6-r2 · finding [open] (reviewer: in scope) · workflow checked out any ref as 'branch' (phase 6)

Raised by the independent phase-6 reviewer with file:line evidence (see p6-review).

<!-- fr:journal kind=finding scope=plan id=p6-r3 created=2026-10-06T15:05:20+00:00 phase=6 state=open review_scope=in -->
### p6-r3 · finding [open] (reviewer: in scope) · workflow tests did not assert the security properties (phase 6)

Raised by the independent phase-6 reviewer with file:line evidence (see p6-review).

<!-- fr:journal kind=finding scope=plan id=p6-r4 created=2026-10-06T15:05:20+00:00 phase=6 state=open review_scope=in -->
### p6-r4 · finding [open] (reviewer: in scope) · --dry-run succeeded on glab/tea (phase 6)

Raised by the independent phase-6 reviewer with file:line evidence (see p6-review).

<!-- fr:journal kind=review scope=plan id=p6-review created=2026-10-06T15:05:20+00:00 phase=6 -->
### p6-review · review · Phase 6 independent code review — 4 findings, all in scope, all fixed (phase 6)

Reviewer confirmed no script injection (branch only via env, always quoted), tags stay under rc/, no overwrite, only the tag pushed, minimal permissions (pull-requests: read needed for the PR link), SHA-pinned checkout, ci-budget watch list, and that the Python slug, bash slug and PR-body route agree. Raised p6-r1..r4 plus three sub-bar nits; all were fixed test-first by a separate fixer, the nits too (SSH remote → git+ssh:// source, one remote for SHA/URL/dispatch, GitRefusal keeps its reason; 2c9f37f03). Suite: 9355 passed, 105 skipped.

<!-- fr:journal kind=finding scope=plan id=p6-r1-resolved created=2026-10-06T15:05:20+00:00 phase=6 state=fixed resolves=p6-r1 -->
### p6-r1-resolved · finding [fixed] · resolves p6-r1: prerelease SHA could come from a local-only or stale ref (phase 6)

SHA from `git ls-remote <remote> refs/heads/<branch>`; absent on remote → exit 2; workflow takes a required `sha` input and refuses a moved head. ad246f2d2.

<!-- fr:journal kind=finding scope=plan id=p6-r2-resolved created=2026-10-06T15:05:20+00:00 phase=6 state=fixed resolves=p6-r2 -->
### p6-r2-resolved · finding [fixed] · resolves p6-r2: workflow checked out any ref as 'branch' (phase 6)

Checkout refs/heads/<branch>; ls-remote --exit-code --heads check; BRANCH and SHA via env only. f376a5c96.

<!-- fr:journal kind=finding scope=plan id=p6-r3-resolved created=2026-10-06T15:05:20+00:00 phase=6 state=fixed resolves=p6-r3 -->
### p6-r3-resolved · finding [fixed] · resolves p6-r3: workflow tests did not assert the security properties (phase 6)

Assert no ${{ in run:, inputs via env, every uses: SHA-pinned, bash slug line equals rc_tag (proven to fail when changed). bb450c0cc.

<!-- fr:journal kind=finding scope=plan id=p6-r4-resolved created=2026-10-06T15:05:20+00:00 phase=6 state=fixed resolves=p6-r4 -->
### p6-r4-resolved · finding [fixed] · resolves p6-r4: --dry-run succeeded on glab/tea (phase 6)

Backend decided before dry-run; non-GitHub exits 2 UnsupportedForgeOperation; dry-run cases tested. d0079c899.
