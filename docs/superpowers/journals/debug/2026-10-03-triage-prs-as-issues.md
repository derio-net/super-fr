# Journal: 2026-10-03-triage-prs-as-issues

<!-- fr:journal kind=repro scope=debug id=75e205eb6f63 created=2026-10-03T21:03:48+00:00 -->
### 75e205eb6f63 · repro · Open PRs land in facts.issues and show as unplaced issues

super-fr#902. After `fr triage collect --repo derio-net/super-fr`, open PRs #314, #474, #476, #852 sit in facts.json `issues` with /pull/ URLs; `fr triage check` lists them as unplaced, the board shows 'Unplaced issue super-fr#…', and the architecture page files them under Other. Each of those PRs has a judgement in judgements.yaml (PR judgements are intended: the skill ranks open PRs under the same OWNER/REPO#N key).

<!-- fr:journal kind=root-cause scope=debug id=1f7d1eb5e18a created=2026-10-03T21:03:48+00:00 -->
### 1f7d1eb5e18a · root-cause · collect re-views judged PR keys with gh issue view, which returns PRs

`collect_facts` takes every judged key absent from the open-issue list (`gh issue list`, which excludes PRs) and re-fetches it with `forge.view_issue` (`_judged_elsewhere`), to settle closed issues. `gh issue view N` resolves a PR number too (verified live: `gh issue view 852` returns url .../pull/852, state OPEN). So every judged PR is appended to `issues` as an open issue, and every issue-reading view (check unplaced/unranked/settled, needs_you, architecture) counts it.
