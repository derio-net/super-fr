# Plan: deliver tests= gate matches a log under a dot-directory (gh#606)

A single agentic phase. `_writes` in `fr.run.telemetry` suffix-matched relative
redirect targets after `str.lstrip("./")`, which removes characters rather than a
prefix. The fix compares path segments instead (spec §2). The phase also ignores
`.fr-deliver/`, where this change's own deliver writes its suite log, and bumps
the patch version, because `packages/*/src/**` changed.

There is no walking skeleton. The change is internal to one function the
existing suite already exercises; the skeleton override is recorded at spec
scope. The live proof is this run's `deliver`, which names
`.fr-deliver/tests.log`.
