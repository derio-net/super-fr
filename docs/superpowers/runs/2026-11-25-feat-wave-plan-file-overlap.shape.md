```diff
  packages/fr/src/fr/triage/
+   plan_overlap.py              # read plan `files:` at a batch branch, the overlap rule, checked_report, the fix wording
    kanban.py                    # Card gains `overlaps`; build_board takes `overlaps=` (batch id → sentences)
    kanban_render.py             # one <p class="overlap"> in a card's detail
  packages/fr/src/fr/commands/
    triage_cmd.py                # `fr triage check`: the `plan overlap` set (text, --json `plan_overlap`)
    triage_kanban_cmd.py         # write_board(checkouts=): the report, card lines and unread page notes
    triage_batch_cmd.py          # the driver's _write_board passes checkouts=self.checkout_paths
  tests/unit/
+   test_triage_plan_overlap.py  # reader, rule, after-chains, ignore globs, clone rule, fix text
    test_triage_check.py         # check text/JSON, exit 0 when unread or when the read raises
    test_triage_kanban*.py       # card field, render paragraph, write_board notes and checkouts
  docs/explainers/fr-triage.md   # the plan overlap set of `check`
```

```text
checked_report → plan_overlap_report(judgements, facts, source_for_clones(cwd, checkouts)):
  per batch in dispatched|pr-open with a dispatch branch:
    repo = batch_repo(...)                     → None: "repo of batch unknown"
    source = source_for(repo)                  → str: "no clone (of <repo>) here"
    read_plan_paths(source, branch)            → origin/<branch>: cursor naming it → steps.*.emitted.plan → NN.yaml phase.files
  overlaps(compared, ignore = generated + version.files)
    skip pairs in one after-chain; literal∩literal ∪ glob(A)∋literal(B) ∪ glob(B)∋literal(A); globs = `*` or `?`
```
