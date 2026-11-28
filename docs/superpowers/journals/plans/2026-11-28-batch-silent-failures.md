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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-28T10:24:24+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · install.sh captured fr models apply's stderr to a file and showed it only on a non-zero exit, so a notice on a successful run was lost (phase 1)

scripts/install.sh `fr models apply --harness opencode 2>"$FR_INSTALL_STDERR"`: the file was read only when apply_rc != 0.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-28T10:24:24+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · debt/render.py token shape checks used match with $, accepting a trailing newline into the published category (phase 1)

packages/fr/src/fr/debt/render.py _BACKEND/_TRACKER/_UNSUPPORTED: re.match with `$` accepts `gitea\n`, `gh#611\n`; `[^)]+` admits a newline.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-28T10:24:24+00:00 phase=1 -->
### review-p1 · review · phase 1 review: 2 findings, both in scope, both fixed with a test (phase 1)

Independent reviewer read spec, plan and the diff c4e69ecd0..HEAD. R1-R8 met; no dropped-tag path,
no `--version main` tag read, no fr.run layering breach, no temp-file leak.
Findings: p1-r1 (in, fixed), p1-r2 (in, fixed). Suggested a `bash-portability` concern (macOS bash 3.2);
not a defined lens in this repo, so not added; the changed constructs (`${arr[@]+…}`, `< <()`, here-strings,
`local`) all predate 4.x and are already used in both scripts.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-28T10:24:24+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: install.sh captured fr models apply's stderr to a file and showed it only on a non-zero exit, so a notice on a successful run was lost (phase 1)

install.sh: on exit 0 a non-empty captured stderr is passed through to stderr; test_a_notice_from_a_successful_fr_models_apply_still_reaches_stderr.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-28T10:24:24+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: debt/render.py token shape checks used match with $, accepting a trailing newline into the published category (phase 1)

render.py: fullmatch for all three patterns, and _UNSUPPORTED is DOTALL so a newline-carrying token matches and is refused as not fixed-shape; two newline cases added to test_a_token_that_is_not_fixed_shape_never_reaches_the_category.
