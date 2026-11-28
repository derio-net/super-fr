<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-batch-silent-failures

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-28T09:33:19+00:00 input=true -->
### brief · discovery · Operator brief: triage batch silent-failures (#1682, #1668, #1592, #1689)

/fr-goal batch silent-failures

Batch `silent-failures` of derio-net/super-fr: 4 issues, delivered as ONE pull request.
Batch title: Silent failures: errors that report success or lose their reason

- super-fr#1682: install.sh hides fr's refusals: `fr models apply ... || true` turns a named
  exit-2 into a missing model: line. Batches with #1668.
- super-fr#1668: Flaky test_the_refusal_lists_installable_tags_in_version_order drops a tag
  (bootstrap's installable_tags skips a failed git show silently). Batches with #1682.
- super-fr#1592: adopt.py and push_cmd.py swallow forge errors silently, so a login page is
  never named there. Fail-open stays, add a log or warning line.
- super-fr#1689: fr debt: an unsupported forge operation is reported as 'forge error', and
  the reason never reaches the CI log.

Delivery rules: branch feat/batch-silent-failures; draft PR as soon as the spec is
committed, with one `Closes derio-net/super-fr#<n>` line per member; no member issue as a
phase tracking_issue; the wave driver owns mergeability and CI (no `fr pr settle` loop);
never add the `approved-fr` label.

<!-- fr:journal kind=decision scope=spec id=d1-install-warn created=2026-11-28T09:33:19+00:00 decided_by=operator -->
### d1-install-warn · decision · install.sh warns and continues when fr models apply fails, and repeats every warning at the end with the fr version

Q: When fr models apply exits non-zero, what should the install do?
A (operator): warn and keep going; "the warnings should be shown again at the bottom (as well
as the fr version), otherwise they might be missed by the user." Spec R1, R2.

<!-- fr:journal kind=decision scope=spec id=d2-bootstrap-refuse created=2026-11-28T09:33:19+00:00 decided_by=operator -->
### d2-bootstrap-refuse · decision · bootstrap refuses, naming the tag and git's message, when a tag's install.sh cannot be read

Q: When reading a tag's install.sh fails for a reason other than 'absent', what should
bootstrap do? A (operator): Refuse, naming it (recommended). Spec R3, R4.

<!-- fr:journal kind=decision scope=spec id=d3-every-swallowed-error created=2026-11-28T09:33:19+00:00 decided_by=operator -->
### d3-every-swallowed-error · decision · adopt and push warn on every swallowed forge error, not only login pages

Q: Which swallowed errors print a one-line warning? A (operator): every swallowed error
(recommended). Both sites stay fail-open. Spec R5, R6.

<!-- fr:journal kind=decision scope=spec id=d4-debt-stderr created=2026-11-28T09:33:19+00:00 decided_by=operator -->
### d4-debt-stderr · decision · fr debt issue prints each unavailable source's reason as a plain stderr line

Q: Where should fr debt issue print the detailed reason? A (operator): plain stderr line
(recommended), not a ::warning:: annotation. Spec R8.

<!-- fr:journal kind=decision scope=spec id=d5-verification created=2026-11-28T09:33:19+00:00 decided_by=operator -->
### d5-verification · decision · Verification: strategy candidate, rows none (CI tests), gate developer, no Test Plan

Q: How is this batch verified before it merges? A (operator): candidate, rows by CI
(recommended). Spec ## Verification.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-28T09:33:19+00:00 lens=errors step=brainstorm -->
### lens-errors-1 · lens · The batch is about error paths: every new warning and refusal must carry its real reason

<!-- fr:journal kind=finding scope=spec id=sr-r1 created=2026-11-28T09:39:56+00:00 state=open review_scope=in -->
### sr-r1 · finding [open] (reviewer: in scope) · R5's warn hook has no path from the adopt command: the command never calls default_pr_state, and migrate_cmd's adopt stays silent

adopt.py:963 is the only default_pr_state caller (inside adopt_run, adopt.py:880-894);
run_cmd.py:1640 adopt_cmd and migrate_cmd.py:328 call adopt_run without pr_state. The spec
must name the channel and cover both callers.

<!-- fr:journal kind=finding scope=spec id=sr-r2 created=2026-11-28T09:39:56+00:00 state=open review_scope=in -->
### sr-r2 · finding [open] (reviewer: in scope) · R1's 5-line stderr cap cuts the motivating refusal's remedy: the migration gate's refusal is 6-7 lines and its commands are last

fr.artifacts.trigger._will_not_act_here (trigger.py:957-965) prints fact, because, detail,
optional carry line, then preview/apply/bypass; a 5-line head drops the fix.

<!-- fr:journal kind=finding scope=spec id=sr-r3 created=2026-11-28T09:39:56+00:00 state=open review_scope=in -->
### sr-r3 · finding [open] (reviewer: in scope) · Design computes INSTALLABLE before any channel is chosen, so --version main now lists remote tags and can refuse on an unreadable tag

bootstrap.sh:155-156: main lists no tags today and is the refusal's own escape hatch
(bootstrap.sh:148). R3 and the Design disagreed.

<!-- fr:journal kind=finding scope=spec id=sr-r4 created=2026-11-28T09:39:56+00:00 state=open review_scope=in -->
### sr-r4 · finding [open] (reviewer: in scope) · 'No tag is ever dropped without a message' does not hold when channel_tags' ls-remote fails inside the process substitution

bootstrap.sh:118-121 channel_tags; bootstrap.sh:130 `done < <(channel_tags)` never sees its
status, so a failed ls-remote reads as "No installable versions exist yet".

<!-- fr:journal kind=finding scope=spec id=sr-r5 created=2026-11-28T09:39:56+00:00 state=open review_scope=in -->
### sr-r5 · finding [open] (reviewer: in scope) · R2 is unclear on a failing install: cleanup_tmps prints after every ERROR, and recorded warnings are never repeated on failure

install.sh:149-162 cleanup_tmps prints `install.sh failed (exit $rc)` after any error and
removes only .tmp sidecars on failure; the fr --version failure case was unspecified.

<!-- fr:journal kind=finding scope=spec id=sr-r6 created=2026-11-28T09:39:56+00:00 state=open review_scope=in -->
### sr-r6 · finding [open] (reviewer: in scope) · read_failure redacts but does not strip control characters, unlike R8's _clean, and putting it in fr.forge_body inverts layering

debt_cmd.py:238-242 _clean also strips control/bidi; forge_body.py is a leaf imported by
glab.py:38, real_glabclient.py:38, tea.py:46-47, so a module-level fr.debt.render import
pulls acceptance/settings into every adapter.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-28T09:39:56+00:00 -->
### spec-review-1 · review · independent spec review: 6 findings, all in scope, all fixed in the spec

Findings raised: sr-r1..sr-r6 (all in scope). Decisions d1-d5 honoured. The reviewer verified
every named file:line (install.sh:1116, 149-162; bootstrap.sh:33, 118-132, 143, 158, 161;
adopt.py:772-795, 880-894, 963; run_cmd.py:1640; push_cmd.py:150-170; forge_body.py:15,22;
debt/render.py:36,45-65; debt/engine.py:503,535-540; ghclient.py:18,42-58; debt_cmd.py:139-242;
test_run_writes_layering.py). Suggested lens: security.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-28T09:39:56+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · R5/R7/R8 echo forge-returned error text to terminals, CI logs and a published category: check redaction, control-char strip, fixed-shape tokens

<!-- fr:journal kind=finding scope=spec id=sr-r1-resolved created=2026-11-28T09:39:56+00:00 state=fixed resolves=sr-r1 -->
### sr-r1-resolved · finding [fixed] · resolves sr-r1: R5's warn hook has no path from the adopt command: the command never calls default_pr_state, and migrate_cmd's adopt stays silent

R5 now covers both adopt entry points; Design: adopt_run(warn=...) forwards to default_pr_state; run_cmd adopt_cmd and migrate_cmd's loop pass a stderr warn; Design shape lists migrate_cmd.py.

<!-- fr:journal kind=finding scope=spec id=sr-r2-resolved created=2026-11-28T09:39:56+00:00 state=fixed resolves=sr-r2 -->
### sr-r2-resolved · finding [fixed] · resolves sr-r2: R1's 5-line stderr cap cuts the motivating refusal's remedy: the migration gate's refusal is 6-7 lines and its commands are last

R1 and Design: cap raised to 12 lines with a '… N more lines' marker, so the 6-7 line migration refusal fits whole.

<!-- fr:journal kind=finding scope=spec id=sr-r3-resolved created=2026-11-28T09:39:56+00:00 state=fixed resolves=sr-r3 -->
### sr-r3-resolved · finding [fixed] · resolves sr-r3: Design computes INSTALLABLE before any channel is chosen, so --version main now lists remote tags and can refuse on an unreadable tag

R3 states --version main lists no tags, as today; Design computes INSTALLABLE only on non-main paths.

<!-- fr:journal kind=finding scope=spec id=sr-r4-resolved created=2026-11-28T09:39:56+00:00 state=fixed resolves=sr-r4 -->
### sr-r4-resolved · finding [fixed] · resolves sr-r4: 'No tag is ever dropped without a message' does not hold when channel_tags' ls-remote fails inside the process substitution

R3 adds the ls-remote failure ERROR ('could not list release tags'); Design captures channel_tags' output and status first.

<!-- fr:journal kind=finding scope=spec id=sr-r5-resolved created=2026-11-28T09:39:56+00:00 state=fixed resolves=sr-r5 -->
### sr-r5-resolved · finding [fixed] · resolves sr-r5: R2 is unclear on a failing install: cleanup_tmps prints after every ERROR, and recorded warnings are never repeated on failure

R2 specifies the failing install (warnings repeated, existing failure line stays last), the fr --version failure line, and temp-file removal on every exit; Design extends cleanup_tmps.

<!-- fr:journal kind=finding scope=spec id=sr-r6-resolved created=2026-11-28T09:39:56+00:00 state=fixed resolves=sr-r6 -->
### sr-r6-resolved · finding [fixed] · resolves sr-r6: read_failure redacts but does not strip control characters, unlike R8's _clean, and putting it in fr.forge_body inverts layering

R5 and Design: read_failure strips control and bidi characters like _clean and imports redact inside the function, never at module level.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-28T09:40:00+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  bootstrap-unreadable-tag-refuses: none
  debt-unsupported-forge-named: none
  forge-read-failure-named: none
  install-warns-on-fr-refusal: none
row_kinds:
  bootstrap-unreadable-tag-refuses: none
  debt-unsupported-forge-named: none
  forge-read-failure-named: none
  install-warns-on-fr-refusal: none
run_gate: developer
run_kind: candidate
```
