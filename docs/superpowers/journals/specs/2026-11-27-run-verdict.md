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
