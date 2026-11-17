<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-triage-intake

<!-- fr:journal kind=decision scope=plan id=p1-intake-admits-bot-logins created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-intake-admits-bot-logins · decision · Intake also admits the debt workflow's bot logins (BOT_LOGINS) (phase 1)

R2 names claim_trusted(config, viewer) only. check already trusts fr.debt.render.BOT_LOGINS as a debt-digest author, and collect now clears the body of an ineligible issue, so a bot-authored digest (whose association is not OWNER/MEMBER/COLLABORATOR) would lose the marker in its body and stop being read as a digest. intake_trusted() is claim_trusted | BOT_LOGINS, used by collect, issue_reason and the association-read gate. No second association list; only the login set widens, by the logins check already trusts.

<!-- fr:journal kind=decision scope=plan id=p1-create-edit-leave-unjudged-to-save created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-create-edit-leave-unjudged-to-save · decision · create/edit leave an uncollected AND unjudged member to the save's own refusal (phase 1)

rejected_members rejects an absent key as `not collected` (R6). For create and edit, _refuse_rejected passes the judgements and skips an uncollected member that is not judged either, so the existing `members [...] are not judged` refusal (exit 2, nothing written) still names the real cause. dispatch passes no judgements, so it rejects every uncollected member as R6 says.

<!-- fr:journal kind=decision scope=plan id=p1-acceptance-record-shape created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-acceptance-record-shape · decision · Acceptance moves use the AcceptanceItem shape, not {row, op} (phase 1)

The four intake rows are still pending on this branch (not merged on the default ref), so a record entry is a row move ({id, status, notes, levels}), not an amendment; the {row, op, ...} shape the brief gave is for merged rows. Levels are unit refs anchored on test names.

<!-- fr:journal kind=discovery scope=plan id=p1-circular-import-batch-intake created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-circular-import-batch-intake · discovery · fr.triage.batch cannot import fr.triage.intake at module level (phase 1)

intake -> claims -> batch is a cycle. suggest() imports untrusted_issues inside the function. check.py, collect.py, views.py and triage_batch_cmd.py import intake at module level without a cycle.

<!-- fr:journal kind=discovery scope=plan id=p1-rest-list-carries-association-outside-projection created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-rest-list-carries-association-outside-projection · discovery · REST list_issues returns authorAssociation outside the field projection (phase 1)

_project() raises on a field the record lacks and cuts to the requested fields, and `gh issue list --json` has no association field, so collect cannot ask for it. RealGhRestClient.list_issues adds authorAssociation to each projected record (empty string when absent); collect reads the key's presence to skip the extra read.

<!-- fr:journal kind=discovery scope=plan id=p1-fixture-churn-from-intake created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-fixture-churn-from-intake · discovery · Many fixtures built issues with no author; intake now treats them as untrusted (phase 1)

Fixtures gained author_association OWNER (the shared _issue helpers, triage_board_fixtures.issue, the scenario fixture generators, which were regenerated at schema 14), FakeForge.issue_associations answers OWNER for an unscripted repo, and the old `untrusted marker stays ranked` assertion in test_triage_debt_sets now says it is set apart. Facts schema asserts moved 13 -> 14.

<!-- fr:journal kind=discovery scope=plan id=p1-ready-fr-also-created-by-init-scaffold created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-ready-fr-also-created-by-init-scaffold · discovery · init scaffold and merge --yes create ready-fr too (phase 1)

They share ensure_approval_label, which now ensures both labels; their tests assert both. Each label is checked and created on its own, so one failure never hides the other.

<!-- fr:journal kind=discovery scope=plan id=p1-dispatch-repair-also-refuses created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-dispatch-repair-also-refuses · discovery · dispatch --repair is refused for a batch with a rejected member (phase 1)

R6 places the check in dispatch_batch after the repo is resolved and before the tracking gate, which `--repair` shares. A dispatched batch whose member is later edited by an outside author or closed with no association therefore needs ready-fr (or removing the member) before a repair, as the spec's rule reads.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-constant label and a fragment: nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the association read mirrors the existing optional-read helpers (_closed_in_progress, _gated_prs); no duplication to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

one small final step in collect (_withhold_untrusted_bodies); no earlier code was repeated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

is_set_apart gained one clause and CheckResult one field, matching the existing sets; nothing to simplify

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

one shared helper (_refuse_rejected) already serves create, edit and dispatch, and one builder (rejected_by_batch) serves both snapshots

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

render_brief changed in place around one helper (quote_untrusted); no duplicate remained

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t8 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t8 · discovery · no-refactor-because P1.T8 (phase 1)

ensure_approval_label now loops over its two labels; the loop is the cleanup
