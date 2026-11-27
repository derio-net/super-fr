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
  unit lookup, step drift, rebind. `_unit_key` (`:413`) refuses in five places, and
  `_resolve_manifest_for_read` (`:643`) prints the drift warning (`:656`) and goes on.
- **C provenance** — `_gate_degradation_notice` (`:875`) to `_refuse_missing_emits`
  (`:1303`), with `_GATE_DECISIONS` (`:1032`). `_queue_gate_decision` writes a journal
  entry, so its module joins the writer list in `tests/unit/test_journal_stamp_offset.py:31`.
  `fr/run/provenance.py` exists already (it reads gate provenance for `fr run check` and
  `fr run gates`).
- **D evidence** — `_parse_emitted` (`:1331`) to `_debt_phrase` (`:3744-3751`), about 2,400
  lines and 60 `raise typer.Exit`, two of them exit 75 (`ci_evidence.CI_PENDING_EXIT`,
  `:1903`, `:1910`). `_verified_evidence` (`:1732`) evaluates every derived witness through
  a local `derive` that catches `typer.Exit` (`:1923-1927`), so every derived refusal is
  printed before the resolve is refused (gh#768).
- **E briefs** — `_template_context` (`:3752`) to `_print_member_dispatch` (`:4940`). The
  binding guard `_guard_dispatch_binding` (`:4140`), with `_run_journal`, `_restore_bytes`,
  `_NotAppliedError` and `_substitution_id` (`:4101-4139`), writes a journal decision and a
  binding and restores both on failure. It stays.
- **H deliver gates** — `_repo_relative` (`:6804`) to `_answered_by_or_exit` (`:7579-7593`).
  `_resolve_body` (`:7594`) calls them in a fixed order and stays.

Every refusal in these clusters prints to `err_console`. Their prints differ per line in
`markup` and in `soft_wrap` (`_unit_key`'s last refusal, `:470-473`, passes no
`soft_wrap`), so at a fixed terminal width both matter to byte identity.

Importers outside `run_cmd.py`: `fr/record/apply.py:208` and `:1673`,
`fr/verification/baseline.py:178`, `commands/pickup_cmd.py:290`
(`_resolve_manifest_for_read`), `commands/push_cmd.py:125` and `commands/lenses_cmd.py:84`
(`_runs_on_this_branch`, which stays), and `fr/run/adopt.py:850` (`derive_run_id`). Tests:
49 files name `run_cmd`, and 49 lines patch or reach into a private `run_cmd` name.

`fr/run/writes.py` is held free of `typer`, `rich` and `fr.commands` by
`tests/unit/test_run_writes_layering.py`. Two other `fr/run` modules import from
`fr.commands`: `adopt.py:850` (`derive_run_id`, which moves here) and `workspace.py:48`
(`fr.commands.isolation_cmd._target`, which this spec does not touch).

## Requirements

R1. A new module `packages/fr/src/fr/run/verdict.py` defines four things. `Say(text, markup=False, soft_wrap=True)` is one frozen line as a command prints it. `Verdict(witness, refusal=(), exit_code=2, unobserved=(), warnings=())` is frozen: `refusal` and `warnings` are tuples of `Say` in print order, and `unobserved` is a tuple of the gate names `_note_unobserved` records today. `RunRefusal(lines, exit_code=2)` is an exception carrying a tuple of `Say`. `Warn` is the type of a `Callable[[Say], None]`.
R2. `run_cmd.py` has one adapter that settles a `Verdict`. It prints the warnings to `err_console`, in order, then records each unobserved gate through `_note_unobserved`. With a refusal it prints the refusal lines and raises `typer.Exit(exit_code)`; otherwise it returns the witness. A `RunRefusal` raised below a command is caught at that command's entry point (`resolve_in_process` included), and its lines are printed to `err_console` before `typer.Exit(exit_code)` is raised. `_UNOBSERVED` and `_note_unobserved` stay in `run_cmd.py`.
R3. Lookup (B) moves to a new `fr/run/steps.py`. `_unit_key`'s refusals are raised as `RunRefusal` with exit 2. `_resolve_manifest_for_read` takes a `warn` callable and sends the drift warning to it; `pickup_cmd.py` passes one. `fr/run/adopt.py` imports `derive_run_id` from `fr.run.steps`.
R4. The deliver gates (H) move to a new `fr/run/deliver.py`. `_resolve_body` stays in `run_cmd.py` and calls them in the order it calls them today. `_RECORD_ROWS` keeps its hand-off from `resolve_in_process`.
R5. The briefs (E) move to a new `fr/run/brief.py`: templates, `_build_brief`, `_build_member_brief`, the tier and binding-notice helpers, the dispatch open, close and claim record helpers, and the refusal texts. `_guard_dispatch_binding` and its four helpers stay in `run_cmd.py`, and so does `_print_member_dispatch`, which prints a brief to stdout.
R6. The evidence verifiers (D) move to a new package `fr/run/evidence/`, split by concern so that no module in it exceeds 800 lines. Each verifier `_verified_evidence` calls returns a `Verdict`. A helper below a verifier may raise `RunRefusal`, and the verifier turns it into its verdict's refusal, keeping the warnings collected so far. `_verified_evidence` stays in `run_cmd.py` and settles each verdict through R2's adapter, so every derived refusal is still printed before the resolve is refused, with the summary line for more than one refusal. Exit 75 for a pending CI gate is kept.
R7. Provenance (C) moves into `fr/run/provenance.py` with `_GATE_DECISIONS`. That module replaces `commands/run_cmd.py` in `test_journal_stamp_offset.py`'s writer list, unless `run_cmd.py` still stamps a journal entry itself; then both are listed.
R8. Behaviour does not change. Every refusal keeps its wording, markup, soft-wrap, line order and exit code, byte for byte. Warnings print in the same order relative to the refusal. The existing tests that assert refusal text pass unchanged. Each verifier and each moved refusing helper has a test that compares its stderr and exit code on every refusal path against a copy captured from the code before the move.
R9. Every module under `packages/fr/src/fr/run/`, subpackages included, imports no `typer` and no `rich` module other than `rich.markup`, at any nesting level. None imports `fr.commands` either, except `workspace.py`'s existing `fr.commands.isolation_cmd`, which the test names as the one allowance. `tests/unit/test_run_writes_layering.py` becomes that test for the whole package, with its planted-source cases kept.
R10. The moved names are public in their new modules. `run_cmd.py` imports only the names its own body uses, under `_`-prefixed spellings, with no re-export kept only for compatibility. `record/apply.py`, `verification/baseline.py`, `pickup_cmd.py` and the tests import from or patch the new module.
R11. Each slice lowers the `run_cmd.py` line budget to the module's new length plus at most 20 lines.
R12. The `fr/run` paragraph of `AGENTS.md` names `verdict.py`, `steps.py`, `deliver.py`, `brief.py` and `evidence/`, and the rule that `fr/run` imports no `typer` and no console.

## Design

### The types (R1, R2)

```python
@dataclass(frozen=True)
class Say:
    text: str
    markup: bool = False
    soft_wrap: bool = True

@dataclass(frozen=True)
class Verdict:
    witness: str | None
    refusal: tuple[Say, ...] = ()
    exit_code: int = 2
    unobserved: tuple[str, ...] = ()
    warnings: tuple[Say, ...] = ()

class RunRefusal(Exception):
    def __init__(self, lines: tuple[Say, ...], exit_code: int = 2) -> None: ...

Warn = Callable[[Say], None]
```

Design 6.1 put one `markup` flag on the verdict. It moves to each line here, with
`soft_wrap` beside it, because the prints being replaced differ in both from line to line
(`_unit_key`'s refusals: four with `soft_wrap=True` or none, one with a `[red]` first line
and a plain indented second line). A multi-line print such as `:448-455` stays one `Say`
whose text holds the `\n`, so the bytes do not move.

The adapter in `run_cmd.py`:

```python
def _say(line: Say) -> None:
    err_console.print(line.text, markup=line.markup, soft_wrap=line.soft_wrap)

def _settle(verdict: Verdict) -> str:
    for w in verdict.warnings: _say(w)
    for gate in verdict.unobserved: _note_unobserved(gate)
    if verdict.refusal:
        for line in verdict.refusal: _say(line)
        raise typer.Exit(verdict.exit_code)
    return verdict.witness
```

`RunRefusal` is caught by a decorator or a `try` at each `@run_app.command` entry point and
in `resolve_in_process`. It prints the lines with `_say` and raises `typer.Exit`. A refusal
that used `raise ... from e` keeps its cause on the `RunRefusal`.

### Order of the slices

The issue's order, one plan phase each, because each later slice uses the types and the
earlier ones shrink the file the later ones edit:

1. `verdict.py`, the adapter, the layering test (R9), and the first two verifiers,
   `_proportionality_witness` and `_docs_witness` with `_witness_base` and
   `_derived_refusal`, into `fr/run/evidence/derived.py`.
2. B into `steps.py`.
3. H into `deliver.py`.
4. E into `brief.py`.
5. The rest of D into `fr/run/evidence/`.
6. C into `provenance.py`.

### Preservation (R8)

In each slice, the red step captures every refusal path of each function that is about
to move: its stderr bytes at the CLI runner's fixed width, and its exit code. The capture
is taken from the code before the move and committed as a fixture. The green step moves
the code, and the test then drives the same inputs through the new module and the adapter
and compares. Tests that monkeypatch a moved name patch it where it now lives (R10),
because patching a re-export would no longer reach the caller.

## Design shape

```
packages/fr/src/fr/
  run/
+   verdict.py           Say, Verdict, RunRefusal, Warn
+   steps.py             B: derive_run_id … complete_step; unit_key raises RunRefusal;
+                        resolve_manifest_for_read(…, warn)
+   deliver.py           H: deliver gates, called by run_cmd._resolve_body in today's order
+   brief.py             E: templates, build_brief, build_member_brief, tiers, dispatch records
+   evidence/            D: one module per concern, each ≤ 800 lines
+     derived.py         proportionality, docs, witness base   (slice 1)
+     …                  tests logs / CI / reuse, reviewer & findings, lenses, walk,
+                        emitted, owed — every verifier returns a Verdict
~   provenance.py        + C: gate notice, round checks, queued gate decisions, _GATE_DECISIONS
~   adopt.py             derive_run_id from fr.run.steps
  commands/
~   run_cmd.py           adapter _settle / _say; RunRefusal caught at each entry point;
=                        keeps _verified_evidence, _resolve_body, _guard_dispatch_binding,
=                        _print_member_dispatch, _UNOBSERVED, F/G/I/J clusters
~   pickup_cmd.py        resolve_manifest_for_read from fr.run.steps, passes a warn
  record/apply.py      ~ imports from fr.run.*
  verification/baseline.py ~ imports from fr.run.*
tests/unit/
~ test_run_writes_layering.py      whole fr/run package: no typer, no rich but rich.markup,
~                                  no fr.commands (one named allowance)
+ test_run_verdict*.py             adapter; captured refusal bytes per moved function
~ test_tripwire_module_budget.py   run_cmd.py budget lowered each slice
~ test_journal_stamp_offset.py     writer list names fr/run/provenance.py
~ tests patching run_cmd._x       patch fr.run.<module>.x
```

## Verification

strategy: none
gate: developer

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
