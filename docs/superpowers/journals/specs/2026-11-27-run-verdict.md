<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-run-verdict

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T15:14:04+00:00 input=true -->
### operator-brief · discovery · Batch arch-run-verdict: derio-net/super-fr#1519 as dispatched (issue title and body)

# run_cmd.py refuses through a typed verdict, then its lookup, deliver, brief, evidence and provenance clusters move to fr/run

Costly-part design (a) from the #1318 review (section 6.1). P3 refactor; no behaviour change.

The evidence cluster of `packages/fr/src/fr/commands/run_cmd.py` ([`packages/fr/src/fr/commands/run_cmd.py:1541-3922`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L1541-L3922), 2,382 lines) holds 55 `raise typer.Exit`; each decision is welded to its refusal print. Before it can move to `fr/run/evidence/`, each verifier returns a frozen `Verdict(witness, refusal lines, markup, exit_code, unobserved, warnings)`, and one adapter in the command module prints the warnings, then the refusal, records the unobserved note and raises `typer.Exit`. Verifiers import no typer and no console.

**First two to convert:** `_proportionality_witness` ([`packages/fr/src/fr/commands/run_cmd.py:2372`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L2372)) and `_docs_witness` ([`packages/fr/src/fr/commands/run_cmd.py:2414`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L2414)). `_proportionality_witness` prints two red-markup refusals ([`packages/fr/src/fr/commands/run_cmd.py:2387`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L2387), [`packages/fr/src/fr/commands/run_cmd.py:2396`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L2396)) and one plain one ([`packages/fr/src/fr/commands/run_cmd.py:2405`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L2405)); the verdict carries the markup flag for that.

**Preservation contract:** refusal wording, markup, line order and exit code are byte-identical, and warnings print in the same order relative to the refusal. Shown by the CLI tests that assert refusal text, unchanged, plus one test per converted verifier comparing the adapter's output on every refusal path with a copy captured before the change. `_UNOBSERVED` ([`packages/fr/src/fr/commands/run_cmd.py:298`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L298)) stays the channel until every verifier returns a verdict.

**Beyond verifiers.** Lookup (B, [`packages/fr/src/fr/commands/run_cmd.py:544-1084`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L544-L1084)), provenance (C, [`packages/fr/src/fr/commands/run_cmd.py:1085-1540`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L1085-L1540)), briefs (E, [`packages/fr/src/fr/commands/run_cmd.py:3923-5114`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L3923-L5114)) and deliver gates (H, [`packages/fr/src/fr/commands/run_cmd.py:6856-7576`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L6856-L7576)) refuse several calls deep (5, 9, 7 and 17 `raise typer.Exit`). For those, `fr/run/` raises `RunRefusal(lines, markup, exit_code)`, caught at the command's entry points, and sends a warning that does not stop the command (for example the drift warning at [`packages/fr/src/fr/commands/run_cmd.py:866`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L866)) to a `warn` callable the command passes in. Rule from the first converted verifier on, enforced by a new test: modules under `fr/run/` import neither `typer` nor a console.

**Slices this issue carries, in order** (the write ledger is #1515 and goes first): (1) the types and the two verifiers above (M); (2) B to a new `fr/run/steps.py` (M), preserving `_unit_key`'s refusal and exit 2; (3) H to a new `fr/run/deliver.py` (M), preserving the fixed call order in `_resolve_body` and the `_RECORD_ROWS` hand-off; (4) E to a new `fr/run/brief.py` (M), leaving `_guard_dispatch_binding`; (5) the remaining verifiers of D to `fr/run/evidence/` (L); (6) C to `fr/run/provenance.py` (M), adding its module to `tests/unit/test_journal_stamp_offset.py:31`'s writer list.

**Callers to migrate:** `_verified_evidence` ([`packages/fr/src/fr/commands/run_cmd.py:1937`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L1937)) and the resolve path; tests that patch `_verify_tests_log` and other verifiers by name.

**Guard:** an AST check that `fr/run/evidence/` imports neither `typer` nor a console; lower the line budget as verifiers move.

**Shared with other open work:** the `run_cmd.py` slices issue (do slices 1-3 first) and the cursor-race issue.

---

Came out of the architecture review for #1318 (section 6.1 of `docs/superpowers/audits/2026-11-16-architecture-review.md`, which lands with that PR: https://github.com/derio-net/super-fr/blob/main/docs/superpowers/audits/2026-11-16-architecture-review.md).

<!-- fr:journal kind=decision scope=spec id=scope-all-six-slices created=2026-11-27T15:14:04+00:00 decided_by=operator -->
### scope-all-six-slices · decision · The PR carries all six slices of #1519 and closes it

Operator answered round 1 question 1: all six slices (types plus the proportionality and docs verifiers; B lookup to steps.py; H deliver gates to deliver.py; E briefs to brief.py; the rest of D to fr/run/evidence/; C to provenance.py), one plan phase each, in the issue's order. The PR says Closes #1519.

<!-- fr:journal kind=decision scope=spec id=verification-none-developer created=2026-11-27T15:14:04+00:00 decided_by=operator -->
### verification-none-developer · decision · Verification strategy none, gate developer

Operator answered round 1 question 2: `strategy: none`, `gate: developer`. The CI suite is the evidence (existing refusal-text tests unchanged, captured byte-identical refusal tests, the AST layering guard). Nothing holds the close-out. No Test Plan: no post-merge row exists.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-27T15:14:04+00:00 lens=errors step=brainstorm -->
### lens-errors-1 · lens · Every refusal moves from typer.Exit to Verdict/RunRefusal and must keep its text, markup, soft-wrap, order and exit code

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · RunRefusal gets past the three places that catch typer.Exit today, starting in slice 1

R2 catches RunRefusal only at entry points; derive (:1926), _advance_once (:6268) and resolve_in_process (:8042-8045) catch typer.Exit below them, so a RunRefusal would skip gh#768 accumulation, the refused stop and the held-stdout ordering. _derived_refusal's callers at :2058, :2117, :2615, :2798 stay in run_cmd until slice 5.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · Say cannot express style="red", and its defaults are the opposite of rich's

Refusals at :1072, :1218, :1324, :6838, :6851 pass style="red"; Say had no style and defaulted markup=False, soft_wrap=True, against Console.print's markup on, soft_wrap off.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · Verdict(witness str|None) cannot carry what most verifiers return, and verifiers call other verifiers

LensSet, WalkOwed, dict, tuple and None returns; _settle typed -> str; no merge rule for _verify_lens_reviewers -> _verify_reviewer.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · E and H call fr.commands.common.resolve_repo_root, which R9 forbids in fr/run

Brief builders (:3832-3836, :3918, :3978, :4645, :4651, :4723) and _repo_relative (:6807) call resolve_repo_root(); the layering test resolves relative imports against a fixed package and lacks the `from rich import markup` spelling.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · Module-level helpers the moved clusters use, and C's warnings and unobserved note, have no home

_RECORD_ROWS, _why_unobservable, _why_tests_unobservable, _TEMPLATE_RE, _return_unobserved, and C's two warnings plus _note_unobserved had no destination legal under R9.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · R8's "existing tests pass unchanged" contradicts R10, starting in slice 1

test_run_settle_witness.py:241-257 patches _proportionality_witness with a print-and-exit fake; test_run_evidence_walk.py:70 patches _verify_tests_log with a string lambda.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · Merged acceptance rows name a test file and a function this spec changes

run-write-ledger-cli-free cites two test functions of test_run_writes_layering.py; harness-gate-degrades-loudly's note names run_cmd._gate_degradation_notice.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · Four docs pages cover these paths, and the spec plans no page update, AGENTS.md entry or change fragment

workflow-shapes.md, cli.md, fr-brainstorming-and-plan.md, verification-strategies.md; AGENTS.md; .changes fragment.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · Several line references and counts in the Background are wrong

Exit 75 is at :3233/:3240; the multi-line print is :458-465; the last two _unit_key prints are :467-470 and :474-485; D holds 56 exits.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · R7's writer-list conditional is already settled; both modules must be listed

_guard_dispatch_binding stamps with journal_now() (:4256-4260) and stays.

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-27T15:23:41+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · The slice boundaries split helpers away from their callers

_proportionality_base is called only by _witness_base; _lens_set_or_exit sits in E's range but serves evidence.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-27T15:23:41+00:00 -->
### spec-review-1 · review · independent spec review: 11 findings

Findings raised: s-r1 to s-r11, all in scope. The two operator decisions hold (scope-all-six-slices, verification-none-developer). R6's 800-line limit is feasible; D splits along natural seams. All eleven fixed in the spec; the three rows' origins re-pointed to the renumbered requirements.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-27T15:23:41+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · The capture-before-move fixtures and the re-pointed monkeypatches are the only evidence that no behaviour changed

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: RunRefusal gets past the three places that catch typer.Exit today, starting in slice 1

R2 now turns a RunRefusal back into typer.Exit at the fr.commands/fr.record call into fr/run (`_refusals()`), so all three catch sites see what they see today; Design 'Where a refusal turns back into an exit' and slice 1's note on _derived_refusal's remaining callers.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: Say cannot express style="red", and its defaults are the opposite of rich's

Say gains `style`, and defaults to markup=True, soft_wrap=False (R1, Design types); the capture uses a colour console so a lost style shows.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: Verdict(witness str|None) cannot carry what most verifiers return, and verifiers call other verifiers

Verdict is generic; R7 narrows Verdict[str] to the str witnesses, every other refusing function raises RunRefusal with a warn callable, and states the merge rule for a verifier calling a raising function or another verifier.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: E and H call fr.commands.common.resolve_repo_root, which R9 forbids in fr/run

R6 makes each moved function take repo_root; R10 resolves relative imports per file's package and allows rich.markup in both spellings with a planted case.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: Module-level helpers the moved clusters use, and C's warnings and unobserved note, have no home

R3 moves the unobserved channel to fr/run/unobserved.py; R5 moves _RECORD_ROWS to deliver.py; R6 moves _TEMPLATE_RE to brief.py; R8 gives _gate_provenance a warn callable and the unobserved module.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: R8's "existing tests pass unchanged" contradicts R10, starting in slice 1

R9 now says CLI tests asserting refusal text by running a command pass unchanged, and tests patching a moved name are re-pointed with a fake of the new shape.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: Merged acceptance rows name a test file and a function this spec changes

R10 keeps both test function names; R8 amends the harness row's note.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: Four docs pages cover these paths, and the spec plans no page update, AGENTS.md entry or change fragment

Background lists the four pages; R13 and the Design shape add the stamps, AGENTS.md and the patch fragment.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: Several line references and counts in the Background are wrong

Corrected in Background and Design.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: R7's writer-list conditional is already settled; both modules must be listed

R8 states it directly: add fr/run/provenance.py, run_cmd.py stays listed.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-27T15:23:41+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: The slice boundaries split helpers away from their callers

Slice 1 lists _proportionality_base; R6 and slice 4 put _lens_set_or_exit in fr/run/evidence/lenses.py.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T15:23:43+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  run-cmd-clusters-in-fr-run: none
  run-engine-cli-free: none
  run-verdict-refusals-preserved: none
row_kinds:
  run-cmd-clusters-in-fr-run: none
  run-engine-cli-free: none
  run-verdict-refusals-preserved: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-run-verdict-p2 created=2026-11-27T15:27:36+00:00 -->
### phase-split-2026-11-27-run-verdict-p2 · decision · ask: slice 2, lookup B to fr/run/steps.py (R4), the issue's own slice

Each slice of #1519 is independently reviewable and the operator chose one phase per slice.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-run-verdict-p3 created=2026-11-27T15:27:39+00:00 -->
### phase-split-2026-11-27-run-verdict-p3 · decision · ask: slice 3, deliver gates H to fr/run/deliver.py (R5)

One phase per slice, operator decision scope-all-six-slices.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-run-verdict-p4 created=2026-11-27T15:27:42+00:00 -->
### phase-split-2026-11-27-run-verdict-p4 · decision · ask: slice 4, briefs E to fr/run/brief.py (R6)

One phase per slice, operator decision scope-all-six-slices.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-run-verdict-p5 created=2026-11-27T15:27:44+00:00 -->
### phase-split-2026-11-27-run-verdict-p5 · decision · ask: slice 5, the remaining evidence verifiers D to fr/run/evidence/ (R7)

One phase per slice; also review-size: about 2,400 lines.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-run-verdict-p6 created=2026-11-27T15:27:47+00:00 -->
### phase-split-2026-11-27-run-verdict-p6 · decision · ask: slice 6, provenance C to fr/run/provenance.py (R8)

One phase per slice, operator decision scope-all-six-slices.

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-27-run-verdict-p1 created=2026-11-27T15:27:49+00:00 -->
### tier-2026-11-27-run-verdict-p1 · decision · hard: phase 1 sets the refusal contract (Verdict, RunRefusal, _refusals) every later phase and the resolve gate path rely on

A wrong adapter changes refusal bytes or exit codes on every run command.

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-27-run-verdict-p5 created=2026-11-27T15:27:52+00:00 -->
### tier-2026-11-27-run-verdict-p5 · decision · hard: phase 5 converts about 56 refusals of the evidence gate path, with the verifier merge rule and the gh#768 accumulation

The evidence verifiers are the resolve gate every run step passes.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-run-verdict-p2-1 created=2026-11-27T15:28:07+00:00 -->
### phase-split-2026-11-27-run-verdict-p2-1 · decision · review-size: slice 2 of #1519 moves its own cluster (1,200-5,600 lines); one review per cluster keeps each diff reviewable

The rows span all slices, so the asks overlap; the split is by cluster, as the audit's slices and the operator's scope-all-six-slices decision lay out.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-run-verdict-p3-1 created=2026-11-27T15:28:09+00:00 -->
### phase-split-2026-11-27-run-verdict-p3-1 · decision · review-size: slice 3 of #1519 moves its own cluster (1,200-5,600 lines); one review per cluster keeps each diff reviewable

The rows span all slices, so the asks overlap; the split is by cluster, as the audit's slices and the operator's scope-all-six-slices decision lay out.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-run-verdict-p4-1 created=2026-11-27T15:28:12+00:00 -->
### phase-split-2026-11-27-run-verdict-p4-1 · decision · review-size: slice 4 of #1519 moves its own cluster (1,200-5,600 lines); one review per cluster keeps each diff reviewable

The rows span all slices, so the asks overlap; the split is by cluster, as the audit's slices and the operator's scope-all-six-slices decision lay out.
