# Journal: 2026-10-02-closing-keywords

<!-- fr:journal kind=repro scope=debug id=59068e6f8a61 created=2026-10-02T16:42:18+00:00 -->
### 59068e6f8a61 · repro · deliver's PR gate never inspects closing references

_deliver_pr_gate (run_cmd.py) reads the live PR body via the forge adapter and checks only missing_sections (record/pr_body.py). A body 'Closes #a and #b' passes; on merge GitHub closes only #a (#544 stayed open this way).

<!-- fr:journal kind=hypothesis scope=debug id=0a057bbc2537 created=2026-10-02T16:42:19+00:00 -->
### 0a057bbc2537 · hypothesis · #821 and #822 are two root causes, not one

#821 is a grammar defect: no check that each closing reference has its own keyword. Local, needs only the body. #822 is a closing POLICY that needs data fr does not have: Row (acceptance/model.py) has no issue field, and issues appear only in free-text notes (50 'gh#N' mentions). Its other two prongs (harness+model on live evidence; awaiting-live marker kept out of the triage rank) touch fr acceptance set-status and fr triage, not deliver. They share a gate location, not a cause. Also: _deliver_pr_gate runs only on an fr run cursor's deliver step, so fr-debugging PRs (no cursor), this batch's included, are never checked.

<!-- fr:journal kind=root-cause scope=debug id=79a9a7870a68 created=2026-10-02T16:47:06+00:00 -->
### 79a9a7870a68 · root-cause · deliver's PR gate checks sections but not closing-keyword grammar (#821)

Root cause: _deliver_pr_gate validates only REQUIRED_SECTIONS. Nothing checks that each issue reference on a closing-keyword line has its own keyword, so 'Closes #a and #b' delivers and #b never closes. Operator decision (2026-10-02): this batch fixes #821 only; #822 is a separate closing-policy design (row→issue link is a matrix shape change) and is referenced, not closed.

<!-- fr:journal kind=finding scope=debug id=f-821 created=2026-10-02T17:01:52+00:00 state=fixed -->
### f-821 · finding [fixed] · deliver refuses a line sharing one closing keyword across several issues

fr.record.pr_body.shared_closing_keywords + a refusal in _deliver_pr_gate after the section check, printing the one-per-line fix. Failing test first: tests/unit/test_deliver_closing_keywords.py (17 cases, committed d2cc9339 before the fix ac093bbd). Full suite: 7606 passed, 97 skipped.
