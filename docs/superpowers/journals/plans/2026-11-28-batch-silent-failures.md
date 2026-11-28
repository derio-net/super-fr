<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-batch-silent-failures

<!-- fr:journal kind=discovery scope=plan id=p1-d1 created=2026-11-28T10:17:26+00:00 phase=1 -->
### p1-d1 · discovery · install sandbox needs devcontainer and uv stubs to reach No warnings. (phase 1)

The install test sandbox always warns (no devcontainer or npm, uv stub exports no lock, no fr entry point), so the No warnings. case stubs devcontainer, a uv that names a tool dir with fr, and an export.

<!-- fr:journal kind=decision scope=plan id=p1-d2 created=2026-11-28T10:17:26+00:00 phase=1 -->
### p1-d2 · decision · read_failure sanitises the url as well as the reason (phase 1)

Per the coordinator's security note, the url (from the run cursor) is redacted, control/bidi-replaced and bounded like the reason.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-28T10:17:26+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

forge_body.read_failure and the shared CONTROL class were written once, with debt_cmd importing it; nothing duplicated to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-28T10:17:26+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the change is one anchored regex in source_category and one loop in issue_cmd; no duplication left.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-28T10:17:26+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs, fragment and acceptance rows only; no code to clean.
