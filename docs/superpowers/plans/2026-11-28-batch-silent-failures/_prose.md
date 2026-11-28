# Silent failures name their reason

Spec: `docs/superpowers/specs/2026-11-28-batch-silent-failures-design.md` (triage batch
`silent-failures`: #1682, #1668, #1592, #1689).

One agentic phase. The four asks are small, share one theme (a swallowed failure must
say why) and one review: each is a few dozen lines plus tests, about 550 lines in all.
A second phase would cost a whole executor and reviewer round trip for no review benefit.

Order inside the phase: the two shell scripts first (R1-R4), then the Python sites
(R5-R8), then docs, the change fragment and the acceptance rows. Each task is red, then
green, then a refactor step where the change leaves something to tidy.

Notes for the implementer:

- `fr.run` must not import `typer` or a console (`tests/unit/test_run_writes_layering.py`);
  the adopt warning reaches stderr through the `warn` callback the command layer passes.
- `fr.forge_body` is a leaf the forge adapters import: import `redact` inside the function.
- The bootstrap flake (#1668) was not reproduced locally (0 of 300 parallel runs). The fix
  makes any read failure loud and removes the `printf | grep -q` pipe, so a recurrence
  names its cause instead of dropping a tag.
- Run long test commands in the background as the brief's `long_commands` rule says.
