# Run pipeline failures at resolve and deliver; double phase claims

Batch `run-pipeline` (super-fr#1090, #1091, #1110), one PR. Spec:
`docs/superpowers/specs/2026-10-12-run-pipeline-failures-design.md`.

Three independent asks, one agentic phase each, serial in one workspace:

1. **CI-built reports (#1090, R1–R3).** One helper (`ci_built_reports` /
   `tracked_reports`) beside `REPORT_SET`; every report writer and both
   report checks use it. Skeleton phase: its first task is the smoke (change
   fragment + one targeted test + the draft PR's CI).
2. **Unrunnable strategies (#1091, R4–R6).** `install_problem` becomes the
   one install rule (`_contract` calls it); `effective_shape_default` filters
   the shape default at its three binding sites; `unrunnable_strategies` flags
   explicitly named ones at self-review (error) and the brainstorm resolve
   (warning); the malformed `strategy:` message shows the accepted form.
3. **First claim wins (#1110, R7–R8).** One merge function for claim,
   `--open-unit` and resolve's identity fields; a no-change re-claim writes
   nothing.

Testing discipline (overnight rule): targeted tests locally only; any full or
large suite goes through `bash ~/.cache/fr/coord/testslot.sh -- <command>`;
CI on the draft PR is preferred for the full suite (`tests: ci`). No member
issue is a phase `tracking_issue`.
