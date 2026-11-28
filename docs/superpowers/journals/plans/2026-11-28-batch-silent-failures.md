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

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-28T10:33:53+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · install.md said bootstrap names a tag on a listing failure and that it never drops a tag without a message, contradicted by the silent skips

docs/reference/install.md:88-91 vs scripts/bootstrap.sh channel_tags / installable_tags.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-28T10:33:53+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · install.md described the fr models apply warning as if every install ran it; it runs only in the OpenCode block, and the fr-not-on-PATH warning was not mentioned

docs/reference/install.md:37-38 vs scripts/install.sh OpenCode delivery block.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-28T10:33:53+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · adopt/push warned only on a raised error; every adapter's pr_status_by_url answers None on an ordinary forge error, so the common unread case stayed silent

real_ghclient.py:205-208, real_ghrestclient.py:939-944, real_glabclient.py:174-177, real_teaclient.py:131-136 fail soft; adopt.py `if not info: return None`, push_cmd.py `(status or {}).get`.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-28T10:33:53+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · install.sh ran fr --version with 2>/dev/null, discarding a failing fr's own reason, and recorded no warning, so it could close with No warnings.

scripts/install.sh closing block.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-28T10:33:53+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · a tag pushed after the fetch now aborted bootstrap with a raw 'Not a valid object name' and no remedy

scripts/bootstrap.sh: ls-remote lists the remote, ls-tree reads the local clone.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-28T10:33:53+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · render.py _TRACKER used Unicode \w/\d, so the published issue token was not strictly fixed-shape

packages/fr/src/fr/debt/render.py _TRACKER without re.ASCII admits fullwidth digits and homoglyphs.

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-28T10:33:53+00:00 state=open review_scope=out -->
### l-security-r2 · finding [open] (reviewer: out of scope) · CONTROL misses U+061C, zero-width U+200B-200D/U+2060/U+FEFF and U+2028/2029

packages/fr/src/fr/forge_body.py CONTROL, moved unchanged from debt_cmd.py; the class predates this change.

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-28T10:33:53+00:00 state=open review_scope=out -->
### l-security-r3 · finding [open] (reviewer: out of scope) · redact covers only GitHub/GitLab token shapes and URL credentials; Gitea tokens and Authorization header values pass through

packages/fr/src/fr/debt/render.py redact; predates this change, which routes more forge text through it.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-28T10:33:53+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy 2, errors 3, security 3 (1 in, 2 out); every in-scope finding fixed

One reviewer per lens over c4e69ecd0..HEAD with the shape file; shape found consistent with the diff by all three.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-28T10:33:53+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: install.md said bootstrap names a tag on a listing failure and that it never drops a tag without a message, contradicted by the silent skips

install.md: the listing failure shows git's message; a read failure shows the tag and git's message; never drops an unreadable tag; silent skips stated as such; the not-yet-fetched note added.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-28T10:33:53+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: install.md described the fr models apply warning as if every install ran it; it runs only in the OpenCode block, and the fr-not-on-PATH warning was not mentioned

install.md scopes the warning to OpenCode delivery and names the fr-not-on-PATH warning.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-28T10:33:53+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: adopt/push warned only on a raised error; every adapter's pr_status_by_url answers None on an ordinary forge error, so the common unread case stayed silent

adopt.py and push_cmd.py warn on a None answer with fr.forge_body.NO_STATE; spec R5 states both paths; tests test_default_pr_state_warns_when_the_adapter_answers_none and test_a_recorded_pr_the_adapter_answers_none_for_is_named_too.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-28T10:33:53+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: install.sh ran fr --version with 2>/dev/null, discarding a failing fr's own reason, and recorded no warning, so it could close with No warnings.

install.sh keeps fr --version's stderr and records a warning (and one for fr not on PATH); spec R2 says so; test_a_failing_fr_version_is_named_in_the_closing_block and test_fr_not_on_path_is_a_warning_repeated_in_the_summary extended.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-28T10:33:53+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: a tag pushed after the fetch now aborted bootstrap with a raw 'Not a valid object name' and no remedy

bootstrap.sh: a remote-listed tag missing locally is skipped with a note naming the rerun; spec R3 says so; test_a_tag_pushed_after_the_fetch_is_skipped_with_a_note.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-28T10:33:53+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: render.py _TRACKER used Unicode \w/\d, so the published issue token was not strictly fixed-shape

_TRACKER spelled as ASCII classes; fullwidth-digit and Cyrillic-homoglyph cases added to test_a_token_that_is_not_fixed_shape_never_reaches_the_category.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-28T10:33:53+00:00 state=open resolves=l-security-r2 out_of_scope=true -->
### l-security-r2-resolved · finding [out-of-scope] · resolves l-security-r2: CONTROL misses U+061C, zero-width U+200B-200D/U+2060/U+FEFF and U+2028/2029

The character class was moved verbatim from debt_cmd.py; widening it changes every existing echo site and is its own change. Filed as a follow-up.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-28T10:33:53+00:00 state=open resolves=l-security-r3 out_of_scope=true -->
### l-security-r3-resolved · finding [out-of-scope] · resolves l-security-r3: redact covers only GitHub/GitLab token shapes and URL credentials; Gitea tokens and Authorization header values pass through

redact's token shapes predate this change; adding Gitea and header shapes is a redaction change of its own across every caller. Filed as a follow-up.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved-2 created=2026-11-28T10:34:30+00:00 state=open resolves=l-security-r2 tracked_by=https://github.com/derio-net/super-fr/issues/1765 -->
### l-security-r2-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1765] · resolves l-security-r2: CONTROL misses U+061C, zero-width U+200B-200D/U+2060/U+FEFF and U+2028/2029

Filed at deliver as https://github.com/derio-net/super-fr/issues/1765.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved-2 created=2026-11-28T10:34:41+00:00 state=open resolves=l-security-r3 tracked_by=https://github.com/derio-net/super-fr/issues/1766 -->
### l-security-r3-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1766] · resolves l-security-r3: redact covers only GitHub/GitLab token shapes and URL credentials; Gitea tokens and Authorization header values pass through

Filed at deliver as https://github.com/derio-net/super-fr/issues/1766.
