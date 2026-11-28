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
