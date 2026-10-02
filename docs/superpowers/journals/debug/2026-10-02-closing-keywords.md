# Journal: 2026-10-02-closing-keywords

<!-- fr:journal kind=repro scope=debug id=59068e6f8a61 created=2026-10-02T16:42:18+00:00 -->
### 59068e6f8a61 · repro · deliver's PR gate never inspects closing references

_deliver_pr_gate (run_cmd.py) reads the live PR body via the forge adapter and checks only missing_sections (record/pr_body.py). A body 'Closes #a and #b' passes; on merge GitHub closes only #a (#544 stayed open this way).
