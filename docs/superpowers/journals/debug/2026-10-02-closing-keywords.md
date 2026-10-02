# Journal: 2026-10-02-closing-keywords

<!-- fr:journal kind=repro scope=debug id=59068e6f8a61 created=2026-10-02T16:42:18+00:00 -->
### 59068e6f8a61 · repro · deliver's PR gate never inspects closing references

_deliver_pr_gate (run_cmd.py) reads the live PR body via the forge adapter and checks only missing_sections (record/pr_body.py). A body 'Closes #a and #b' passes; on merge GitHub closes only #a (#544 stayed open this way).

<!-- fr:journal kind=hypothesis scope=debug id=0a057bbc2537 created=2026-10-02T16:42:19+00:00 -->
### 0a057bbc2537 · hypothesis · #821 and #822 are two root causes, not one

#821 is a grammar defect: no check that each closing reference has its own keyword. Local, needs only the body. #822 is a closing POLICY that needs data fr does not have: Row (acceptance/model.py) has no issue field, and issues appear only in free-text notes (50 'gh#N' mentions). Its other two prongs (harness+model on live evidence; awaiting-live marker kept out of the triage rank) touch fr acceptance set-status and fr triage, not deliver. They share a gate location, not a cause. Also: _deliver_pr_gate runs only on an fr run cursor's deliver step, so fr-debugging PRs (no cursor), this batch's included, are never checked.
