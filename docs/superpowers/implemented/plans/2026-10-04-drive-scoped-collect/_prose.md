# Drive collects only what changed each pass — plan

Spec: `docs/superpowers/specs/2026-10-04-drive-scoped-collect-design.md` (gh#911).

One agentic phase. The whole change is a single reviewable ask: the driver's
per-pass collect stops re-viewing settled judged issues. It has three pieces:
an engine keyword, a command-layer flag, and the driver call site. Splitting
them would cost three review round trips for a diff of about 400 lines.

The tasks run in this order:

1. the engine (`collect_facts_counted`, `carried`, `CollectStats`);
2. `collect_into(carry=)`;
3. `recollect` and its `collect:` line;
4. the acceptance rows, the change fragment and the full suite.

The tests pin these invariants:

- A repo whose open-issue list was truncated carries nothing
  (spec-review `sr-truncated-issue-list`).
- The carried map is keyed by `(repo.lower(), number)`, so a group scope
  never carries an issue into the wrong repo.
- `viewed` counts `view_issue` calls, failures included.
- `collect_facts` and `fr triage collect` behave exactly as before.

No explainer describes the driver's collect, so none needs regenerating.
