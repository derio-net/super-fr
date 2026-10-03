# Journal: 2026-10-03-triage-prs-as-issues

<!-- fr:journal kind=repro scope=debug id=75e205eb6f63 created=2026-10-03T21:03:48+00:00 -->
### 75e205eb6f63 · repro · Open PRs land in facts.issues and show as unplaced issues

super-fr#902. After `fr triage collect --repo derio-net/super-fr`, open PRs #314, #474, #476, #852 sit in facts.json `issues` with /pull/ URLs; `fr triage check` lists them as unplaced, the board shows 'Unplaced issue super-fr#…', and the architecture page files them under Other. Each of those PRs has a judgement in judgements.yaml (PR judgements are intended: the skill ranks open PRs under the same OWNER/REPO#N key).
