# Wave plan file overlap

One agentic phase delivers spec 2026-11-25-wave-plan-file-overlap. A new module,
`fr/triage/plan_overlap.py`, reads the plan `files:` of each unmerged batch at its branch head
through the local clone. It then applies the overlap rule: a glob counts only against a literal
path, generated and version files are ignored, and `after`-linked pairs are skipped. The result is
reported through `fr triage check` and the Batches page. The kanban and driver edits are kept to a
field, a keyword, a paragraph and one line, because the live merge-readiness batch edits the same
files.
