# `run_cmd.py` refuses through a typed verdict; its clusters move to `fr/run`

Issue: derio-net/super-fr#1519 (slices 2-7 of the #1318 `run_cmd.py` decomposition, section
5.1 and design 6.1 of `docs/superpowers/audits/2026-11-16-architecture-review.md`). P3
refactor: no behaviour change. Slice 1, the write ledger (#1515), has merged as
`fr/run/writes.py`.

## Background

`packages/fr/src/fr/commands/run_cmd.py` is 8,878 lines at `65414cf8a` (budget 8,895 in
`tests/unit/test_tripwire_module_budget.py:22`) and holds 188 `raise typer.Exit`. Its
decision code cannot leave the command module because each decision is welded to its
refusal print: `err_console.print(...)` and then `raise typer.Exit(...)`. Design 6.1 gives
`fr/run` a way to refuse and warn without typer or a console. This spec builds it and moves
five clusters with it. Line numbers below are at `65414cf8a`.

The clusters (the audit's letters):

- **B lookup** — `derive_run_id` (`:334`) to `_complete_step` (`:797-874`): manifest and
  unit lookup, step drift, rebind. `_unit_key` (`:413`) refuses at `:437`, `:444`, `:466`,
  `:471` and `:485`; its multi-line print is `:458-465`, and its last two prints
  (`:467-470`, `:474-485`) pass no `soft_wrap`. `_resolve_manifest_for_read` (`:643`) prints
  the drift warning (`:656`) and goes on.
- **C provenance** — `_gate_degradation_notice` (`:875`) to `_refuse_missing_emits`
  (`:1303`), with `_GATE_DECISIONS` (`:1032`). `_gate_provenance` prints two yellow
  warnings (`:1241-1245`, `:1276-1281`) and calls `_note_unobserved("operator-gate")`
  (`:1264`). `_queue_gate_decision` builds a journal entry with `journal_now()`
  (`:1081-1086`), so its module joins the writer list of
  `tests/unit/test_journal_stamp_offset.py:33`. `fr/run/provenance.py` exists already (it
  reads gate provenance for `fr run check` and `fr run gates`).
- **D evidence** — `_parse_emitted` (`:1331`) to `_debt_phrase` (`:3744-3751`), about 2,400
  lines and 56 `raise typer.Exit`. Two exit 75 (`ci_evidence.CI_PENDING_EXIT`, `:3233` and
  `:3240`, in `_ci_tests_witness`). `_verified_evidence` (`:1732`) evaluates every derived
  witness through a local `derive` that catches `typer.Exit` (`:1923-1927`), so every
  derived refusal is printed before the resolve is refused, with a summary line when more
  than one fails (`:2002-2007`, gh#768). Its callees return different things: a `str`
  witness (`_proportionality_witness`, `_docs_witness`, `_verify_tests_log`, …), a
  `LensSet` (`_lens_set_or_exit`, `:4728`, inside E's range), a `WalkOwed`
  (`_walk_obligation`, `:2823`), a `dict` (`_verify_lens_reviewers`, `:2565`), a tuple
  (`_review_journal_entries`, `:1687`) or nothing (`_verify_reviewer`, `:2331`;
  `_verify_review_entry`, `:3505`; `_verify_historical_bound`, `:2037`). Some call others:
  `_verify_lens_reviewers` calls `_verify_reviewer` (`:2619`). `_derived_refusal` (`:2322`)
  is called from outside the derived witnesses too (`:2058`, `:2117`, `:2615`, `:2798`).
- **E briefs** — `_template_context` (`:3752`) to `_print_member_dispatch` (`:4940`). The
  binding guard `_guard_dispatch_binding` (`:4140`), with `_run_journal`, `_restore_bytes`,
  `_NotAppliedError` and `_substitution_id` (`:4101-4139`), writes a journal decision
  (`journal_now()`, `:4256-4260`) and a binding and restores both on failure. It stays. The
  brief builders call `fr.commands.common.resolve_repo_root()` themselves (`:3832-3836`,
  `:3918`, `:3978`, `:4645`, `:4651`, `:4723`).
- **H deliver gates** — `_repo_relative` (`:6804`, which also calls `resolve_repo_root()`,
  `:6807`) to `_answered_by_or_exit` (`:7579-7593`). `_resolve_body` (`:7594`) calls them
  in a fixed order and stays. Two H refusals print with `style="red"` (`:6838`, `:6851`),
  as do two in C (`:1072`, `:1218`) and one more at `:1324`.

Every refusal in these clusters prints to `err_console`. Their prints differ in `markup`,
`soft_wrap` and `style`, and many use rich's defaults (markup on, `soft_wrap` off).

Three places in `run_cmd.py` catch `typer.Exit` below a command's entry point: `derive`
(`:1926`), `_advance_once` (`:6268`, which turns a refusal into a `refused` stop that
`_advance_chain` commits after), and `resolve_in_process` (`:8042-8045`, which writes the
held stdout to stderr after the refusal printed, then re-raises).

Module-level names the moving code reads: `_RECORD_ROWS` (`:174`, set by
`resolve_in_process`, read in H at `:7369`), `_UNOBSERVED` and `_note_unobserved`
(`:189`, `:192`), `_why_unobservable` (`:201`), `_why_tests_unobservable` (`:218`),
`_take_unobserved` (`:233`) and `_TEMPLATE_RE` (`:158`). `_return_unobserved`
(`:2776-2783`) notes an unobserved gate and prints a warning.

Importers outside `run_cmd.py`: `fr/record/apply.py:208` and `:1673`,
`fr/verification/baseline.py:178`, `commands/pickup_cmd.py:290`
(`_resolve_manifest_for_read`), `commands/push_cmd.py:125` and `commands/lenses_cmd.py:84`
(`_runs_on_this_branch`, which stays), and `fr/run/adopt.py:850` (`derive_run_id`). Tests:
49 files name `run_cmd`. Some patch a moved name with a fake that prints and raises
`typer.Exit` (`tests/unit/test_run_settle_witness.py:241-257` patches
`_proportionality_witness`) or returns a plain value (`tests/unit/test_run_evidence_walk.py:70`
patches `_verify_tests_log`).

`fr/run/writes.py` is held free of `typer`, `rich` and `fr.commands` by
`tests/unit/test_run_writes_layering.py`, whose two tests are level refs of the merged row
`run-write-ledger-cli-free`. Two other `fr/run` modules import from `fr.commands`:
`adopt.py:850` (`derive_run_id`, which moves here) and `workspace.py:48`
(`fr.commands.isolation_cmd._target`, which this spec does not touch). The merged row
`harness-gate-degrades-loudly` (`docs/acceptance/features/2026-09-18-harness-parity-matrix.yaml`)
names `fr.commands.run_cmd._gate_degradation_notice` in its notes.

Four pages cover the touched paths, so `fr docs check` owes each an edit or a `reviewed`
stamp: `docs/reference/workflow-shapes.md` (`fr/run/**`, `run_cmd.py`),
`docs/reference/cli.md` (`commands/*.py`), `docs/explainers/fr-brainstorming-and-plan.md`
(`commands/pickup_cmd.py`) and `docs/verification-strategies.md` (`verification/**`).

## Requirements

R1. A new module `packages/fr/src/fr/run/verdict.py` defines four things. `Say(text, markup=True, soft_wrap=False, style=None)` is one frozen line as a command prints it, with `rich.Console.print`'s own defaults. `Verdict[T](witness, refusal=(), exit_code=2, warnings=())` is a frozen generic: `witness` is a `T | None`, and `refusal` and `warnings` are tuples of `Say` in print order. `RunRefusal(lines, exit_code=2)` is an exception carrying a tuple of `Say`. `Warn` is the type of a `Callable[[Say], None]`.
R2. `run_cmd.py` prints a `Say` to `err_console` with its `markup`, `soft_wrap` and `style`. It settles a `Verdict` through one adapter: the warnings first, in order, then, with a refusal, the refusal lines and `typer.Exit(exit_code)`; otherwise the witness is returned. A `RunRefusal` never travels past the `fr.commands` or `fr.record` function that called into `fr/run`. It is turned back into its printed lines and `typer.Exit(exit_code)` at that call, keeping the original exception's cause. So `derive`, `_advance_once` and `resolve_in_process` keep catching `typer.Exit`, and they see each refusal where and when they see it today.
R3. The unobserved-gate channel moves to a new `fr/run/unobserved.py`: `_UNOBSERVED`, `_note_unobserved`, `_why_unobservable`, `TESTS_PROVENANCE_SURFACE`, `_why_tests_unobservable` and `_take_unobserved`. It keeps the same context variable and the same notes. `run_cmd.py` imports what it uses from there.
R4. Lookup (B) moves to a new `fr/run/steps.py`. `_unit_key`'s refusals are raised as `RunRefusal` with exit 2. `_resolve_manifest_for_read` takes a `warn` callable and sends the drift warning to it; `pickup_cmd.py` passes one. `fr/run/adopt.py` imports `derive_run_id` from `fr.run.steps`.
R5. The deliver gates (H) move to a new `fr/run/deliver.py` with `_RECORD_ROWS`. `_resolve_body` stays in `run_cmd.py` and calls them in the order it calls them today. `resolve_in_process` sets `_RECORD_ROWS` as it does today.
R6. The briefs (E) move to a new `fr/run/brief.py` with `_TEMPLATE_RE`: templates, `_build_brief`, `_build_member_brief`, the tier and binding-notice helpers, the dispatch open, close and claim record helpers, and the refusal texts. Each moved function that called `resolve_repo_root()` takes `repo_root` as a parameter instead, and its caller passes the root it already resolved. `_guard_dispatch_binding` and its four helpers stay in `run_cmd.py`, and so does `_print_member_dispatch`, which prints a brief to stdout. `_lens_set_or_exit` moves in this slice to `fr/run/evidence/lenses.py`, not to `brief.py`.
R7. The evidence code (D) moves to a new package `fr/run/evidence/`, split by concern so that no module in it exceeds 800 lines. Each witness verifier whose result `_verified_evidence` stores as a `str` returns a `Verdict[str]`. Every other moved function that refuses raises `RunRefusal` and takes a `warn` callable when it warns. A verifier that calls a function that raises catches the `RunRefusal` and returns it as its refusal, with the warnings it gathered before it. A verifier that calls another verifier appends the callee's warnings to its own, in order, and returns the callee's refusal as its own. `_verified_evidence` stays in `run_cmd.py`, and its `derive` settles each derived verdict inside its `try`. Every derived refusal is still printed before the resolve is refused, with the summary line when more than one fails. Exit 75 for a pending CI gate is kept.
R8. Provenance (C) moves into `fr/run/provenance.py` with `_GATE_DECISIONS`. `_gate_provenance` takes a `warn` callable for its two warnings and notes its unobserved gate through `fr/run/unobserved.py`. `tests/unit/test_journal_stamp_offset.py`'s writer list adds `fr/run/provenance.py`, and `commands/run_cmd.py` stays listed because `_guard_dispatch_binding` still stamps an entry. The note of the merged row `harness-gate-degrades-loudly` is amended to name the function's new module.
R9. Behaviour does not change. Every refusal keeps its wording, markup, style, soft-wrap, line order, stream and exit code, byte for byte. Warnings print in the same order relative to the refusal. The CLI tests that assert refusal text by running a command pass unchanged. A test that patches a moved name patches it in its new module, with a fake of the new shape: one that returns a `Verdict` or raises `RunRefusal` where the real function now does. Each moved function that refuses has a test that compares its stderr and exit code on every refusal path against a copy captured from the code before the move.
R10. Every module under `packages/fr/src/fr/run/`, subpackages included, imports no `typer` and no `rich` module other than `rich.markup`, in any spelling (`from rich import markup` included), at any nesting level. None imports `fr.commands` either, except `workspace.py`'s existing `fr.commands.isolation_cmd`, which the test names as the one allowance. The test resolves each file's relative imports against that file's own package. `tests/unit/test_run_writes_layering.py` holds this test, and keeps its two existing test functions under their names, now applied to every module.
R11. The moved names are public in their new modules. `run_cmd.py` imports only the names its own body uses, under `_`-prefixed spellings, with no re-export kept only for compatibility. `record/apply.py`, `verification/baseline.py`, `pickup_cmd.py` and the tests import from or patch the new module.
R12. Each slice lowers the `run_cmd.py` line budget to the module's new length plus at most 20 lines.
R13. The `fr/run` paragraph of `AGENTS.md` names `verdict.py`, `unobserved.py`, `steps.py`, `deliver.py`, `brief.py` and `evidence/`, and the rule that `fr/run` imports no `typer` and no console. The four pages the Background names get an edit or a `reviewed` stamp, and a `patch` change fragment is added.

## Design

### The types (R1, R2)

```python
@dataclass(frozen=True)
class Say:
    text: str
    markup: bool = True          # rich.Console.print's defaults, so Say(text) == print(text)
    soft_wrap: bool = False
    style: str | None = None

@dataclass(frozen=True)
class Verdict[T]:
    witness: T | None
    refusal: tuple[Say, ...] = ()
    exit_code: int = 2
    warnings: tuple[Say, ...] = ()

class RunRefusal(Exception):
    def __init__(self, lines: tuple[Say, ...], exit_code: int = 2) -> None: ...

Warn = Callable[[Say], None]
```

Design 6.1 put one `markup` flag and an `unobserved` note on the verdict. Both change:

- `markup` moves to each line, with `soft_wrap` and `style` beside it, because the prints
  being replaced differ in all three from line to line. A multi-line print such as
  `:458-465` stays one `Say` whose text holds the `\n`, so the bytes do not move.
- `unobserved` is dropped. The context variable that collects unobserved gates holds no
  console, so it moves into `fr/run/unobserved.py` (R3), and moved code notes a gate there
  directly, as it does today. One channel, not two.

`Verdict` is generic (PEP 695, which the 3.14 floor allows) only so mypy can check
`_settle`'s return. Slice 5 uses `Verdict[str]` alone, because only `str` witnesses pass
through `derive`.

The adapter in `run_cmd.py`:

```python
def _say(line: Say) -> None:
    err_console.print(line.text, markup=line.markup, soft_wrap=line.soft_wrap, style=line.style)

def _settle[T](verdict: Verdict[T]) -> T | None:
    for w in verdict.warnings: _say(w)
    if verdict.refusal:
        for line in verdict.refusal: _say(line)
        raise typer.Exit(verdict.exit_code)
    return verdict.witness

@contextmanager
def _refusals() -> Iterator[None]:
    try:
        yield
    except RunRefusal as r:
        for line in r.lines: _say(line)
        raise typer.Exit(r.exit_code) from r.__cause__
```

A caller that passes `rich.markup.escape` output into a `Say` keeps doing so.
`fr/run` may import `rich.markup` for that, and nothing else from rich (R10).

### Where a refusal turns back into an exit (R2)

`_refusals()` wraps each call from `run_cmd.py` (or `record/apply.py`, `pickup_cmd.py`)
into a moved function that can raise `RunRefusal`. The refusal therefore prints and becomes
`typer.Exit` at the same frame the old function raised it from. `derive`'s gathering,
`_advance_once`'s `refused` stop, and `resolve_in_process`'s held-stdout flush after the
refusal all see what they see today. The entry points need no catch of their own.

`warn` is `_say` itself, passed down by the caller.

### Order of the slices

The issue's order, one plan phase each, because each later slice uses the types and the
earlier ones shrink the file the later ones edit:

1. `verdict.py`, `unobserved.py`, the adapter, the layering test (R10), and the first two
   verifiers, `_proportionality_witness` and `_docs_witness`, with `_witness_base`,
   `_proportionality_base` and `_derived_refusal`, into `fr/run/evidence/derived.py`.
   `_derived_refusal` becomes a builder of refusal lines. Its callers still in
   `run_cmd.py` (`:2058`, `:2117`, `:2615`, `:2798`) print and exit through
   `_refusals()` until slice 5 moves them.
2. B into `steps.py`.
3. H into `deliver.py`, with `_RECORD_ROWS`.
4. E into `brief.py`, with `_TEMPLATE_RE`; `_lens_set_or_exit` into
   `fr/run/evidence/lenses.py`.
5. The rest of D into `fr/run/evidence/`.
6. C into `provenance.py`, with `_GATE_DECISIONS`.

### Preservation (R9)

In each slice, the red step captures every refusal path of each function that is about
to move: its stderr bytes at a fixed console width (the CLI runner's, or a recording
`Console` with colour on, so a lost `style` shows), and its exit code. The capture is
taken from the code before the move and committed as a fixture. The green step moves the
code, and the test then drives the same inputs through the new module and the adapter and
compares.

## Design shape

```
packages/fr/src/fr/
  run/
+   verdict.py           Say(markup=True, soft_wrap=False, style=None), Verdict[T], RunRefusal, Warn
+   unobserved.py        _UNOBSERVED channel, note / take / why_unobservable (from run_cmd)
+   steps.py             B: derive_run_id … complete_step; unit_key raises RunRefusal;
+                        resolve_manifest_for_read(…, warn)
+   deliver.py           H + RECORD_ROWS; called by run_cmd._resolve_body in today's order
+   brief.py             E + TEMPLATE_RE; builders take repo_root instead of resolve_repo_root()
+   evidence/            D: one module per concern, each ≤ 800 lines
+     derived.py         proportionality, docs, witness base, proportionality base   (slice 1)
+     lenses.py          lens_set_or_exit (slice 4), lens reviewers and returns (slice 5)
+     …                  tests logs / CI / reuse, reviewer & findings, walk, emitted, owed
~   provenance.py        + C, GATE_DECISIONS; gate_provenance(…, warn)
~   adopt.py             derive_run_id from fr.run.steps
  commands/
~   run_cmd.py           _say / _settle / _refusals(); keeps _verified_evidence (derive settles
=                        inside its try), _resolve_body, _guard_dispatch_binding,
=                        _print_member_dispatch, F/G/I/J clusters
~   pickup_cmd.py        resolve_manifest_for_read from fr.run.steps, passes a warn
  record/apply.py      ~ imports from fr.run.*, calls through run_cmd._refusals()
  verification/baseline.py ~ imports from fr.run.*
tests/unit/
~ test_run_writes_layering.py      every fr/run module; both test names kept; per-file package;
~                                  rich.markup allowed in both spellings; one fr.commands allowance
+ test_run_verdict*.py             adapter, _refusals(); captured refusal bytes per moved function
~ test_tripwire_module_budget.py   run_cmd.py budget lowered each slice
~ test_journal_stamp_offset.py     + fr/run/provenance.py (run_cmd.py stays)
~ tests patching run_cmd._x       patch fr.run.<module>.x with a Verdict / RunRefusal fake
docs/
~ reference/workflow-shapes.md, reference/cli.md, explainers/fr-brainstorming-and-plan.md,
~ verification-strategies.md        reviewed stamps (pages stay true)
~ acceptance/features/2026-09-18-harness-parity-matrix.yaml   amendment: row note names provenance.py
~ AGENTS.md                         fr/run paragraph (R13)
+ .changes/feat-batch-arch-run-verdict.yaml   bump: patch
```

## Verification

strategy: none
gate: developer
settle.conflicts: report — batch arch-run-verdict: the wave driver owns this PR's mergeability
settle.ci: report — batch arch-run-verdict: the wave driver owns this PR's CI

- run-verdict-refusals-preserved: none — CI unit tests compare each moved function's refusal bytes and exit code with captures taken before the move, and the existing refusal-text CLI tests run unchanged
- run-engine-cli-free: none — a CI unit test reads every `fr/run` module's syntax tree, with planted-source cases
- run-cmd-clusters-in-fr-run: none — CI tests: the module budget tripwire and the import tests of each new module

## Out of scope

- Clusters F, G, I and J (advance, start/reshape/adopt/status/cost, resolve, claim/check/gates),
  which the audit keeps in `run_cmd.py`.
- Moving lens-return parsing to `fr/lenses/review.py` or the walk to `fr/verification`, which
  the audit suggests. Both move to `fr/run/evidence/` here, inside the layering rule, and can
  move again later.
- `fr/run/workspace.py`'s import of `fr.commands.isolation_cmd`.
- Any change to what a refusal says or when it fires.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-run-verdict | `derio-net/super-fr` | `2026-11-27-run-verdict` | — |
