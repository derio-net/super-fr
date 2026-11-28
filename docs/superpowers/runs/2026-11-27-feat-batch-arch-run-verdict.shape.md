```
packages/fr/src/fr/commands/run_cmd.py   ~ 8878 -> 4093 lines: typer verbs, _say, _settle and
                                           _refusals() (RunRefusal -> print + typer.Exit at the call site)
packages/fr/src/fr/run/
  verdict.py         + Say, Warn, RunRefusal, Verdict[T] (the typed refusal every engine module returns)
  unobserved.py      + unobserved-step helpers
  steps.py           + lookup cluster (step, unit, record lookups)          slice 2
  deliver.py         + deliver gates (deliver_pr_gate, shape, leftovers)    slice 3
  brief.py           ~ + dispatch-brief assembly moved from run_cmd          slice 4
  evidence/          + derived, lenses, emitted, target, journals, review,  slice 5
                       walk, suite, ci, owed: the resolve-time verifiers
  provenance.py      + operator-gate provenance, _GATE_DECISIONS,           slice 6
                       clears_gate, derive_gate_answer
packages/fr/src/fr/record/apply.py, run/adopt.py, run/ci_evidence.py, commands/pickup_cmd.py,
archive.py, settle/read.py, verification/baseline.py
                                         ~ import lines re-pointed; pickup's _say prints unhighlighted
tests/fixtures/run_verdict/{derived,steps,deliver,brief,evidence,provenance}/
                                         + stderr bytes + exit codes captured from the code BEFORE each move
tests/unit/test_run_verdict*.py          + each moved refusal path compared byte for byte with its capture
tests/unit/test_run_writes_layering.py   ~ the layering rule now covers all of fr/run
tests/unit/test_tripwire_module_budget.py ~ run_cmd.py budget 8895 -> 4115
tests/unit/test_run_*.py, test_deliver_*.py, …  ~ monkeypatches follow each name to its new home
AGENTS.md                                ~ fr/run paragraph names the engine modules and the no-typer rule
docs/reference/*.md, docs/explainers/*.md, docs/verification-strategies.md
                                         ~ reviewed: still true, names moved only
docs/acceptance/features/2026-11-27-run-verdict.yaml  + 3 rows, all ci
.changes/feat-batch-arch-run-verdict.yaml + bump: patch
```

```
import direction (layering rule, pinned by test_run_writes_layering.py):

fr.commands.run_cmd  ->  fr.run.{verdict, steps, deliver, brief, evidence.*, provenance}
fr.run.*             -x  typer, rich (rich.markup only), fr.commands
                         (sole allowance: fr.run.workspace -> fr.commands.isolation_cmd)

refusal flow:
  engine fn  --raises RunRefusal / returns Verdict-->  run_cmd._refusals() / _settle()
             --> err_console.print(text, style)  +  typer.Exit(code)   (bytes unchanged)
```
