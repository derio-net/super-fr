# Export drift: refuse a repo-side edit; targeted import

One agentic phase implements spec `2026-11-27-export-drift` (issue #1667): the export writes a
committed record of what it wrote (`exported-files`), refuses before any write when the repo-side
copy drifted from it (hand `--force` overrides; the driver records an `export-drift:<repo>` stop
that shows as a Needs-you-now row), and `fr triage state import --only` takes in named paths only,
removing a named path the repo deleted. Docs, skill mirrors and a minor change fragment close it.

The asks share one module (`fr/triage/state_sync.py`) and one test surface, so splitting them would
add a review round trip without a reviewable boundary.
