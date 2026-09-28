# Journal: 2026-09-28-closeout-always

<!-- fr:journal kind=decision scope=plan id=p0-phase-shape created=2026-09-28T19:40:54+00:00 -->
### p0-phase-shape · decision · Six phases, skeleton first, sweep last

P1 skeleton (branch_changed_paths + branch_artifacts + fragment), P2 `fr archive --branch` (hard tier: ref resolution, per-kind held lines), P3 owed_artifacts + status + archive --all + archive_twin, P4 brief split / `fr pickup --branch`, P5 skill relays + both mirror generators + tripwire + explainer check, P6 the one-time sweep checked against `fr status`'s owed set. No manual phase: the post-merge Test Plan walk is operator-driven at close-out. #733 is no phase's tracking_issue.

<!-- fr:journal kind=discovery scope=plan id=p1-scope-dir-reuse created=2026-09-28T19:48:54+00:00 phase=1 -->
### p1-scope-dir-reuse · discovery · branch_artifacts reuses fr.journal.model._SCOPE_DIR (private) rather than a new literal (phase 1)

§A says to reuse fr.journal.model's scope constants rather than new
string literals. `_SCOPE_DIR` (scope -> dir name, e.g. "spec" ->
"specs") is the only such mapping and it is module-private (leading
underscore) with no `__all__` boundary in that module. `fr.closeout`
imports it directly and inverts it once (dir name -> scope) rather
than hand-writing {"specs": "spec", "plans": "plan", "debug": "debug"}
a second time. ruff's selected rule set (E,F,I,N,W,UP) does not include
SLF001, so this does not trip lint; flagged here in case a later phase
wants `_SCOPE_DIR` promoted to a public name instead.

<!-- fr:journal kind=discovery scope=plan id=p1-owner-scope-for-run-usage created=2026-09-28T19:48:54+00:00 phase=1 -->
### p1-owner-scope-for-run-usage · discovery · BranchArtifact.owner is None for spec/run/usage in this phase — §B/§C derive it from cursor content, not path (phase 1)

The spec's BranchArtifact docstring reads "plan dir name / spec slug
for followers; journal scope for journals". P1.T2's Test Plan item
only exercises plan-dir collapsing and journal scope ownership, so
this phase leaves owner=None for spec, run and usage artifacts:
a run/usage's owning plan is `emitted.plan` inside the cursor file,
which §B/§C (fr archive --branch, owed_artifacts) read once they
exist — deriving it from the path alone would be guessing ahead of
that data. Left open for phase 2/3 to either confirm this shape or
extend BranchArtifact once the real owner-resolution need is in view.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-28T19:48:54+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

GREEN already lands the shared shape: branch_changed_paths and branch_changes_present both call the new _branch_fork_and_changes helper, so there is exactly one merge-base/fork computation path and nothing left to extract.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-28T19:48:54+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

branch_artifacts is one flat classification function over constants imported from their owning modules; its only smell (the private _SCOPE_DIR import) is left to review as discovery p1-scope-dir-reuse rather than widened here.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-28T19:55:45+00:00 phase=1 -->
### p1-review · review · Phase 1 review: 2 minor findings (1 fixed, 1 refuted) (phase 1)

Independent reviewer (general-purpose, sonnet) over d37afdba..527cc106 with spec §A and plan 01.yaml. Verdict: ready, no critical/important issues. It confirmed the branch_changes_present lift is byte-for-byte behaviour-preserving (86 hardened tests re-run green). Findings: p1-r1 (private _SCOPE_DIR import, in scope) fixed; p1-r2 (spec owner None, in scope) refuted. Declined to judge: owner semantics for plan/spec journals (§B/§C), list ordering (no caller yet), duplicate-path defence (§B unions first), §B–§G behaviour (later phases).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-28T19:55:45+00:00 phase=1 state=fixed review_scope=in -->
### p1-r1 · finding [fixed] (reviewer: in scope) · fr.closeout imported the module-private fr.journal.model._SCOPE_DIR (phase 1)

closeout.py:21 coupled to a private name nothing lints. Fixed by promoting it to public `SCOPE_DIRS` (its only other users are journal_path/archived_journal_path in the same module), plus test_every_journal_scope_is_classified, which pins that every scope in SCOPE_DIRS is classified with no edit to fr.closeout. Phase 3's archive_twin journal pairs will read the same public map.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-28T19:55:45+00:00 phase=1 state=refuted review_scope=in -->
### p1-r2 · finding [refuted] (reviewer: in scope) · BranchArtifact.owner is None for a spec artifact (phase 1)

Refuted: spec §A defines `owner` as "plan dir name / spec slug for followers", and a spec is an owner, not a follower (followers are its spec journal, plus runs/usage for plans). Run/usage owners come from the cursor's `emitted.plan`, which phase 2 (§B) reads. That is planned work in a later phase, not a defect here.

<!-- fr:journal kind=discovery scope=plan id=p2-branch-refs-lift created=2026-09-28T20:07:16+00:00 phase=2 -->
### p2-branch-refs-lift · discovery · verify-merge's ref resolution lifted to fr.isolation.local.resolve_branch_refs (phase 2) (phase 2)

`_branch_refs` was bound to the workspace ops object (it used
`self._run_network`, whose env came from `self._network_env`). It is
now a module-level `resolve_branch_refs(run, repo_root, branch, remote)`
returning `(refs, branch_fetched)` with an EMPTY list when neither ref
resolves; `network_env`/`run_network` moved beside it. The method keeps
its IsolationError on no refs, so verify-merge's behaviour is unchanged
(234 isolation tests green). `fr archive --branch` calls the helper with
`subprocess_runner` and ignores `branch_fetched`: the §B.3 content check
over every resolving ref is its guard, and the brief still runs
verify-merge (PR state included) first.

<!-- fr:journal kind=decision scope=plan id=p2-sweep-report-shape created=2026-09-28T20:07:16+00:00 phase=2 -->
### p2-sweep-report-shape · decision · --branch prints every sweep move but only the branch's own specs' notes, as held lines (phase 2) (phase 2)

§B.4 says "report only its moves" and "a branch spec that stays live
prints held: <spec> — <note>". Every move the sweep makes is staged, so
hiding one would leave an unexplained rename in the operator's commit:
all moves print as `archived:`. The sweep's notes for specs the branch
did NOT touch are dropped (that is the "only"); a branch spec left live
takes its note by `<spec-name>: ` prefix, else the fallback "not every
Implementation Plans row is archived yet" (an active local row yields
no note). The sweep runs when the branch touched a spec or a plan moved,
matching single-plan archive's "sweep after a move".

<!-- fr:journal kind=discovery scope=plan id=p2-emitted-plan-and-private-journal-mover created=2026-09-28T20:07:16+00:00 phase=2 -->
### p2-emitted-plan-and-private-journal-mover · discovery · New public fr.archive.emitted_plan; archive_cmd imports the private _archive_journal the spec names (phase 2) (phase 2)

A held run/usage names its plan from the cursor's `emitted.plan`
(p1-owner-scope-for-run-usage's open question): `emitted_plan(cursor)`
is the reverse of `find_run_for_plan`, reading any cursor version via
`_read_any_version`; usage finds its cursor live, else archived.
BranchArtifact's shape is left as phase 1 made it — the owner is read
at the point of use, no extension needed. `archive_cmd` imports
`fr.archive._archive_journal` because §B.4 names it for debug journals;
it is the same private-import smell review p1-r1 fixed for
`_SCOPE_DIR`, left as is here since promoting it renames six call
sites. Phase 3 (§C's --all debug/orphan journals) will call it too and
may want the public name.

<!-- fr:journal kind=discovery scope=plan id=p2-run-held-even-when-plan-archived created=2026-09-28T20:07:16+00:00 phase=2 -->
### p2-run-held-even-when-plan-archived · discovery · A branch run/usage whose plan is already archived is held, not moved, by --branch (phase 2) (phase 2)

§B.4 says an unmoved run/usage is held naming its plan, with no orphan
exception (unlike plan/spec journals, which follow an already-archived
owner). Implemented literally, with a reason true in both cases:
"follows plan <p>, which did not move in this run". §C's orphan rule (`fr archive --all`, phase 3) is what
clears such a cursor; phase 3 may want --branch to share it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-09-28T20:07:16+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

GREEN was itself the extraction: verify-merge's bound _branch_refs/_network_env/_run_network became module-level resolve_branch_refs/network_env/run_network with the methods delegating, so there is one ref-resolution path and nothing left to clean; the one duplication T1 introduced (IsolationError -> exit 2) was folded into _refuse_on_isolation_error in P2.T2.S3.

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-09-28T20:17:44+00:00 phase=2 -->
### p2-review · review · Phase 2 review: 6 findings (2 important, 4 minor), all fixed (phase 2)

Independent reviewer (general-purpose, opus) over d9fd9723..8567e3c2 against spec §B and plan 02.yaml, with three probe tests run outside the checkout. It confirmed that the resolve_branch_refs extraction preserves verify-merge's argv, env and timeouts exactly, and that refusal order puts every refusal before the first git mv. Verdict: with fixes. All 6 in-scope findings are fixed (f348acca..ae5cd3f5). The orchestrator re-verified: 994 passed across archive/isolation/closeout/verify_merge, and ruff and mypy are clean. Declined to judge: the repo-wide spec-sweep printing (intended by §B.4), merge_evidence's fetch-failure tolerance (pre-existing), the PR-state check (verify-merge's job), and §C/§D/§F (later phases).

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-09-28T20:17:44+00:00 phase=2 state=fixed review_scope=in -->
### p2-r1 · finding [fixed] (reviewer: in scope) · (Important) --branch discarded branch_fetched, verifying stale refs verify-merge would refuse (phase 2)

Fixed in f348acca: exit 2 when the branch fetch failed and ls-remote did not confirm deletion; test with origin repointed at a missing repo.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-09-28T20:17:44+00:00 phase=2 state=fixed review_scope=in -->
### p2-r2 · finding [fixed] (reviewer: in scope) · (Important) run/usage held with a false 'did not move' reason when its plan was already archived (phase 2)

Fixed in ea75aa73: an orphan run+usage whose plan is archived is moved via the new public archive_run_cursor (the §C orphan rule); held lines now say 'still live' / 'neither live nor archived' / 'destination already exists'. Supersedes implement discovery p2-run-held-even-when-plan-archived.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-09-28T20:17:44+00:00 phase=2 state=fixed review_scope=in -->
### p2-r3 · finding [fixed] (reviewer: in scope) · (Minor) ArchiveError from a journal git mv escaped as a traceback (phase 2)

Fixed in 51e5cf1f: returned as the held reason; test patches _git_mv to raise.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-09-28T20:17:44+00:00 phase=2 state=fixed review_scope=in -->
### p2-r4 · finding [fixed] (reviewer: in scope) · (Minor) dirty followers were moved as RM instead of held (phase 2)

Fixed in 51e5cf1f: dirty journal/run/usage held with the plans' 'commit or stash first' reason; test with an edited debug journal.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-09-28T20:17:44+00:00 phase=2 state=fixed review_scope=in -->
### p2-r5 · finding [fixed] (reviewer: in scope) · (Minor) archive_cmd imported the private fr.archive._archive_journal (phase 2)

Fixed in 07164493: public archive_journal in __all__, _archive_journal kept as alias.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-09-28T20:17:44+00:00 phase=2 state=fixed review_scope=in -->
### p2-r6 · finding [fixed] (reviewer: in scope) · (Minor) test gaps: dirty plan held, usage carried with plan, repair once (phase 2)

Fixed in ae5cd3f5: three tests, each shown to fail when the guarded behaviour is removed.

<!-- fr:journal kind=decision scope=plan id=p3-plan-sweep-moved-to-closeout created=2026-09-28T20:50:23+00:00 phase=3 -->
### p3-plan-sweep-moved-to-closeout · decision · status_cmd's PlanSweep/_merged/_sweep_lists moved into fr.closeout; status_cmd imports it back (phase 3)

`fr.closeout.PlanSweep` + `plan_sweep(repo_root, evidence)` (pure given
`evidence` — it never fetches) replace status_cmd's private `_Sweep` /
`_merged` / `_sweep_lists`. `status_cmd._sweep_lists` is now a thin
wrapper: one `merge_evidence(fetch=True)` (unchanged: still exactly one
fetch per `fr status` invocation, per #544) then a call into
`fr.closeout.plan_sweep`. `owed_artifacts`'s "plan" entries
(`_owed_plans`) call the same `plan_sweep`, so `fr status`'s "merged but
not archived" block and `owed_artifacts`'s plan bucket can never
disagree — one predicate, two readers, exactly as §C asks.

<!-- fr:journal kind=decision scope=plan id=p3-held-spec-is-every-blocking-note created=2026-09-28T20:50:23+00:00 phase=3 -->
### p3-held-spec-is-every-blocking-note · decision · held (spec) = any not-yet-implemented spec with a note, not just pending/cross-repo (phase 3)

§C names two held examples (a pending slice; an unresolved cross-repo
row without the forge). `_owed_specs` treats the held set as EVERY spec
`_spec_fully_implemented` returns a note for (excluding the "no
Implementation Plans rows" case) — including a spec whose row is simply
still active under a live `plans/` dir. This is the same filter
`spec_archive_sweep` already applies to its own notes, so it introduces
no second classification of "not implemented yet, and why". The
alternative (limiting `held` to only the two named note shapes) would
leave an ordinary in-progress spec neither owed nor held — silent,
which is exactly what R5 forbids. Flagging this because the spec table
names only two examples, not a closed set: if the orchestrator or a
reviewer intended a narrower `held` list, this is the line to revisit.

<!-- fr:journal kind=discovery scope=plan id=p3-owed-block-omits-plan-kind-in-status-text created=2026-09-28T20:50:23+00:00 phase=3 -->
### p3-owed-block-omits-plan-kind-in-status-text · discovery · fr status's text 'owed' block filters out kind=plan; --format json does not (phase 3)

`owed_artifacts` always includes plan entries (kind `plan`) so
`fr archive --all` and any other consumer see the complete predicate.
`fr status`'s TEXT rendering (`_owed_block`) drops `plan` entries
because they would just repeat the existing "merged but not archived"
block's own per-plan `fr archive <dir>` line — printing the same plan
twice, once under each heading, would read as two different findings.
The `--format json` `owed` array is NOT filtered: a machine reader gets
every kind `owed_artifacts` returns, `plan` included, with no
text-only-special-case to reconstruct.

<!-- fr:journal kind=discovery scope=plan id=p3-journal-scope-and-slug-extracted created=2026-09-28T20:50:23+00:00 phase=3 -->
### p3-journal-scope-and-slug-extracted · discovery · fr.closeout.journal_scope_and_slug extracted for branch_artifacts and owed_artifacts/archive --all to share (phase 3)

`branch_artifacts` inlined "journals/<scope-dir>/<slug>.md ->
(scope, slug)" parsing. `owed_artifacts`'s orphan-journal check and
`fr archive --all`'s new clearing loop need the identical derivation
(to look up an owner and, for `--all`, to call `archive_journal(repo,
scope, slug)`), so it is now the public `journal_scope_and_slug(path)`,
and `branch_artifacts` calls it too — one classifier, not two.

<!-- fr:journal kind=discovery scope=plan id=p3-deliver-done-added-to-archive created=2026-09-28T20:50:23+00:00 phase=3 -->
### p3-deliver-done-added-to-archive · discovery · fr.archive.deliver_done(cursor) added, reading any cursor version like emitted_plan (phase 3)

The orphan-run rule's no-named-plan branch (§C) needs "this cursor's
`deliver` step is done" — no existing public helper answered that
without reaching into the private `_read_any_version`. Added
`deliver_done(cursor) -> bool` beside `emitted_plan` in `fr.archive`,
same shape (any version, `False` — never a raise — on anything
unreadable or not a cursor), and exported it in `__all__` alongside
`emitted_plan` (which had been usable but was missing from `__all__`
since its own introduction in phase 2).

<!-- fr:journal kind=discovery scope=plan id=p3-orphan-journal-no-ref-check created=2026-09-28T20:50:23+00:00 phase=3 -->
### p3-orphan-journal-no-ref-check · discovery · orphan plan/spec journal owed status never consults the default ref (phase 3)

Per the §C table, only the debug-journal rule and the orphan-run rule's
no-named-plan branch consult `evidence.ref`. An orphan plan/spec
journal is owed purely because its owner directory is already under
`implemented/` — no ref check, matching the table literally (and
`_archive_branch_journal`'s existing per-branch equivalent, which also
treats "owner archived" as sufficient with no ref condition for
plan/spec scope). Noted explicitly in case a reviewer expected the same
ref gate debug journals get.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-09-28T20:50:23+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

covered by the refactor field above.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-09-28T20:50:23+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

covered by the refactor field above.

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-09-28T21:08:16+00:00 phase=3 -->
### p3-review · review · Phase 3 review: 4 findings (1 critical, 2 important, 1 minor), all fixed (phase 3)

Independent reviewer (general-purpose, sonnet) over 9f17e751..f809f1d8 against spec §C/§F, including a live `fr status` on this repo's artifacts, which exposed p3-r1. It confirmed the single shared predicate, one merge-evidence read, JSON back-compat, and the archive_twin pairs. Verdict: with fixes. All 4 in-scope findings were fixed in 72f0cd1c. The orchestrator re-verified: 611 passed; ruff and mypy clean; `fr status` exit 0 with owed (36) debug journals, no held block, and this PR's plan only under 'in progress'. Declined to judge: §B internals (phase 2), skill prose (phase 5), fragment/explainers, pre-existing acceptance-check warnings, estimate overrun (the deliver proportionality gate reports it).

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-09-28T21:08:16+00:00 phase=3 state=fixed review_scope=in -->
### p3-r1 · finding [fixed] (reviewer: in scope) · (Critical) held (spec) swallowed every noted spec, incl. the ordinary 'still active under plans/' state and this PR's own unmerged spec (phase 3)

Fixed in 72f0cd1c: a spec is owed/held only if the spec itself is on the default ref; held only for the pending-slice or cross-repo-unresolved notes; an active-plan row is silent (its plan is reported by the plan blocks). Verified live: fr status shows no held block and does not list this PR's spec.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-09-28T21:08:16+00:00 phase=3 state=fixed review_scope=in -->
### p3-r2 · finding [fixed] (reviewer: in scope) · (Important) owner-archived checks for specs, orphan journals and named-plan runs read the working tree, not the default ref (phase 3)

Fixed in 72f0cd1c: artifact and owner both gated on the ref via _spec_rows_on_ref / _dir_on_ref; a --force archive on an unmerged branch no longer makes anything owed.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-09-28T21:08:16+00:00 phase=3 state=fixed review_scope=in -->
### p3-r3 · finding [fixed] (reviewer: in scope) · (Important) one git ls-tree subprocess per artifact (36+ per fr status) instead of one bulk read (phase 3)

Fixed in 72f0cd1c: _ref_tree does one ls-tree -r of docs/superpowers per owed_artifacts call, reused as a frozenset by every check (the _plans_on_ref pattern); an unreadable ref fails closed.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-09-28T21:08:16+00:00 phase=3 state=fixed review_scope=in -->
### p3-r4 · finding [fixed] (reviewer: in scope) · (Minor) no negative tests with the owner or artifact only on the branch (phase 3)

Fixed in 72f0cd1c: 7 unit cases plus CLI-level equivalents, all written after _publish. This also fixed fixtures whose empty owner dirs were invisible to git.

<!-- fr:journal kind=decision scope=plan id=p4-branch-mode-intro-line-diverges-from-run-mode created=2026-09-28T21:21:22+00:00 phase=4 -->
### p4-branch-mode-intro-line-diverges-from-run-mode · decision · branch mode's "Run this from" line drops the run-file/reaped-workspace language run mode keeps (phase 4)

§D's template shows one generic "Run this from <primary checkout> — the
base clone, after the branch's PR has merged." line, but the existing
run-mode text (p4-r3, kept verbatim per the table's "everything else …
is unchanged") also says "on the default branch" and "(the run file
lives there; the feature workspace this run happened in may already be
reaped)" — true only because a run FILE exists to be reaped away from.
`branch_closeout_brief` prints that fuller sentence only when
`run_extras is not None`; a plain `--branch` brief (no run cursor at
all) gets the shorter generic sentence instead, since there is no run
file for "lives there" to refer to.

<!-- fr:journal kind=discovery scope=plan id=p4-pickup-branch-check-is-its-own-no-fetch-helper created=2026-09-28T21:21:22+00:00 phase=4 -->
### p4-pickup-branch-check-is-its-own-no-fetch-helper · discovery · fr pickup --branch's unresolvable-branch check does not call fr.isolation.local.resolve_branch_refs (phase 4)

§D says the check is "the same resolution as §B.2, without the fetch".
`resolve_branch_refs` always fetches (it IS §B.2's fetch-then-verify),
so reusing it and discarding the network step was not an option without
also discarding its purpose. `pickup_cmd._refuse_unresolvable_branch`
instead composes the two primitives `resolve_branch_refs` itself is
built on — `fr.git.ref_exists` and `fr.git.remote_name` — checking the
local `<branch>` ref and, when a single remote is configured, the
already-fetched `<remote>/<branch>` tracking ref. `--branch` only
decides whether to print a brief, never whether to move anything, so a
round trip to the network buys it nothing (unlike `fr archive --branch`,
which mutates and must not act on a stale ref).

<!-- fr:journal kind=discovery scope=plan id=p4-branch-closeout-brief-is-the-one-builder created=2026-09-28T21:21:22+00:00 phase=4 -->
### p4-branch-closeout-brief-is-the-one-builder · discovery · branch_closeout_brief(repo_root, branch, *, run_extras=None) is the only place a close-out command string is built (phase 4)

`closeout.py` now has one `RunExtras` dataclass (run id, pr, spec/plan
paths, has_test_plan, out_of_scope lines) carrying everything run mode
adds on top of the branch core. `closeout_brief(repo_root, state)` kept
its done-`deliver` refusal, reads the run's emitted values and its
spec's Test Plan marker and out-of-scope journal lines, packs them into
a `RunExtras`, and delegates entirely to `branch_closeout_brief`. Every
command line (`fr isolation verify-merge`, `fr status`, `fr isolation
up`, `fr archive --branch <b>`, the commit/push line, the housekeeping
PR line, `fr isolation down`) is built exactly once, in
`branch_closeout_brief`, for both modes — confirmed by grep: no other
module constructs an `fr archive --branch` / `chore: archive` /
`chore: close out` string.

<!-- fr:journal kind=review scope=plan id=p4-review created=2026-09-28T21:32:15+00:00 phase=4 -->
### p4-review · review · Phase 4 review: 2 minor findings (1 fixed, 1 refuted) (phase 4)

Independent reviewer (general-purpose, sonnet) over 6706d8a2..59bb80a5 against spec §D. It confirmed every row of the run-mode table, that the brief has a single builder (grep), that no assertion was weakened, and that the brief is self-contained from the base clone (live `fr pickup --branch` runs). The 12 skips are test_skill_validation's fr-execute-only parametrisation and hide no coverage of this change. Verdict: with (optional) fixes. Declined to judge: matrix status flips (phase 6), §E skill prose (phase 5), §B internals, primary_checkout (unchanged), and `--branch main` (no requirement).

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-09-28T21:32:15+00:00 phase=4 state=fixed review_scope=in -->
### p4-r1 · finding [fixed] (reviewer: in scope) · (Minor) _refuse_unresolvable_branch swallowed remote_name's GitRefusal/None and claimed it checked origin/<b> (phase 4)

Fixed in 26d185bd: the local ref is checked first. A GitRefusal (ambiguous remotes) or None (no remote) is refused with its reason instead of a made-up origin label. Test test_pickup_branch_names_the_remote_ambiguity_instead_of_claiming_origin failed first (RED), then passed; 61 passed on -k 'closeout or pickup'; ruff and mypy clean.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-09-28T21:32:15+00:00 phase=4 state=refuted review_scope=in -->
### p4-r2 · finding [refuted] (reviewer: in scope) · (Minor) plan 04.yaml files: names tests/unit/test_closeout_brief.py, but the touched file is test_run_closeout.py (phase 4)

Refuted as a code defect. The plan's `files:` is a planning estimate that deliver's `fr plan proportionality` compares against the real diff. The mismatch is reported there, where the PR body shows it, and the plan's own metadata is not something this phase's code gets wrong. There is nothing to fix in the change itself.

<!-- fr:journal kind=discovery scope=plan id=p5-explainer-names-no-literal-archive-command created=2026-09-28T21:44:39+00:00 phase=5 -->
### p5-explainer-names-no-literal-archive-command · discovery · docs/explainers/01-fr-goal.md never named `fr archive <plan-dir>` as the close-out (phase 5)

Grepped `docs/explainers/*.md` and `*.html` for `fr archive` /
close-out prose (spec "Change fragment and explainers", §E). The only
hit is `01-fr-goal.md`'s "Post-merge close-out" section (§9), and it
describes the step only descriptively — "the exact commands to archive
the plan, its journal, and its run record through a housekeeping PR" —
never spelling out `fr archive <plan-dir>` literally. `index.html` and
`fr-isolation.html` (hand-authored, no `.md` source per
explainers-currency.md's known gap 1) have no `fr archive` mention
either. Per the spec's own fallback, no explainer edit or re-render was
needed; this replaces the PR-body note the spec asks for.

<!-- fr:journal kind=discovery scope=plan id=p5-skill-line-budget-forced-relay-prose-into-existing-bullets created=2026-09-28T21:44:39+00:00 phase=5 -->
### p5-skill-line-budget-forced-relay-prose-into-existing-bullets · discovery · The 120-line skill cap (test_skill_validation.py) meant the new relay sentences had to be folded into existing lines, not appended as new ones (phase 5)

fr-debugging, fr-execute and fr-isolation were each already at or near
the 120-line `SKILL.md` ceiling `TestSkillValidation.test_under_120_lines`
enforces. A naive addition of the close-out relay sentence as new
lines pushed all three over (123/125/124 lines) on the first pass.
Fixed by merging the new prose into the existing Deliver/step-5/Cleanup
sentences (fr-debugging), tightening the step-5 caveat paragraph
(fr-execute), and folding the new bullet into the existing `down`
bullet in fr-isolation's Cleanup contract, rather than adding a
standalone bullet. No content was dropped, only re-wrapped — worth
flagging because a line-wrap edit like this can silently break a
substring a tripwire greps for (which happened once here: a mid-phrase
wrap split `fr pickup` across two lines in fr-execute and failed
`test_tripwire_closeout_relay.py` on the mirrors until re-wrapped).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-09-28T21:44:39+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

covered by the refactor field above.

<!-- fr:journal kind=review scope=plan id=p5-review created=2026-09-28T21:53:35+00:00 phase=5 -->
### p5-review · review · Phase 5 review: 2 minor findings, both fixed (phase 5)

Independent reviewer (general-purpose, sonnet) over 1f262be2..17312fd1 against §E/R6/R8. It confirmed: both mirror generators report in sync; the fr-execute relay is confined to the standalone flow; fr-goal's post-merge section matches branch_closeout_brief; harness neutrality and parity tripwires pass; the relay tripwire is robust (it caught a real wrap during implementation); the explainer names no literal `fr archive <plan-dir>`, so no page is stale; fr-dispatch/fr-progress mentions of `fr archive <plan-dir>` are legitimate per-plan usage. Verdict: yes. Declined to judge: matrix flips (batched into phase 6), phase 2/4 internals, and other PR-opening surfaces beyond R8's named targets.

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-09-28T21:53:35+00:00 phase=5 state=fixed review_scope=in -->
### p5-r1 · finding [fixed] (reviewer: in scope) · (Minor) fr-isolation's folded cleanup bullet: 'not a substitute' had no clear referent (phase 5)

Fixed in 0cd998c8: reworded to '… ending in `down`, the immediate lever — never run alone in its place: it verifies …'. Mirrors regenerated by both sync scripts; 659 passed on -k 'tripwire or skill'.

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-09-28T21:53:35+00:00 phase=5 state=fixed review_scope=in -->
### p5-r2 · finding [fixed] (reviewer: in scope) · (Minor) the new bullet opened with a rhetorical question, unlike its bolded-declarative siblings (phase 5)

Fixed in 0cd998c8: the bullet now opens with the bolded declarative '**Post-merge cleanup is `fr pickup --branch <b>`'s brief**'.

<!-- fr:journal kind=discovery scope=plan id=p6-sweep-owed-set-matched-exactly created=2026-09-28T22:04:26+00:00 phase=6 -->
### p6-sweep-owed-set-matched-exactly · discovery · fr status's owed set and fr archive --all's moves matched exactly: 36 debug journals, no extra move (phase 6)

Ran `uv run fr status` first and recorded its 36-line owed set (all
`docs/superpowers/journals/debug/*.md`, each with `fr archive --all`
as the clearing command). Ran `uv run fr archive --all` and it moved
exactly those 36 files to `docs/superpowers/implemented/journals/debug/`
and nothing else — the merged-but-manual-phase plan
(`2026-07-09-multi-backend-git-host-adapters`, phase 9 incomplete) and
this run's own plan/spec (phase 6 still undispatched, not yet on
`origin/main`) were both correctly skipped with printed reasons. No
move fell outside the recorded owed set, so no finding was needed for
this step.

<!-- fr:journal kind=discovery scope=plan id=p6-four-prose-mentions-were-exactly-four created=2026-09-28T22:04:26+00:00 phase=6 -->
### p6-four-prose-mentions-were-exactly-four · discovery · Repo-wide grep confirmed exactly the four named prose mentions of the moved marketplace-config-clobber journal, plus only allowed exceptions (phase 6)

Grepped the whole tree (excluding
`docs/superpowers/implemented/`) for every one of the 36 moved
journals' `journals/debug/<name>` path. The
2026-07-23-marketplace-config-clobber.md hits were exactly the four
named files (AGENTS.md, scripts/install.sh, the two test docstrings) —
all four now point at `docs/superpowers/implemented/journals/debug/`.
Every other hit across the 36 files was a matrix-ref
(`docs/acceptance/matrix.yaml` + its three generated reports, which
`fr acceptance check` resolves through `archive_twin` and which the
brief says must NOT be rewritten) or the `tests/fixtures/triage/`
fixture / triage anchor code, both explicitly out of scope. No
unexpected fifth mention turned up.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-09-28T22:04:26+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

a one-time sweep of owed artifacts (journal moves + four prose path updates + acceptance flips); there is no new code path to refactor, only data/doc moves and matrix status flips

<!-- fr:journal kind=review scope=plan id=p6-review created=2026-09-28T22:10:10+00:00 phase=6 -->
### p6-review · review · Phase 6 review: no findings (phase 6)

Independent reviewer (general-purpose, sonnet) checked 3bfeae6b..40482e35 against §G/§F/R7. Findings: all 36 moves are 100%-similarity renames; the moves match the owed set exactly; `fr status` now reports nothing owed; `fr acceptance check`, `fr validate artifacts` and `fr acceptance report --check` pass, with matrix refs resolving through archive_twin; the 4 prose repoints are correct; each of the 6 flipped rows cites real tests verifying its statement (9 files, 107 passed); this run's own artifacts and every open PR's files are untouched. Declined to judge: test-file organisation (earlier phases), the flips beyond 06.yaml's declared row (required by the acceptance-matrix rule, so correct), a full-suite re-run (the executor's run was green; deliver re-runs it), and frozen evidence/fixture snapshots that quote old paths.
