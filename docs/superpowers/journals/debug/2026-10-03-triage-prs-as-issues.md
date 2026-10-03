# Journal: 2026-10-03-triage-prs-as-issues

<!-- fr:journal kind=repro scope=debug id=75e205eb6f63 created=2026-10-03T21:03:48+00:00 -->
### 75e205eb6f63 · repro · Open PRs land in facts.issues and show as unplaced issues

super-fr#902. After `fr triage collect --repo derio-net/super-fr`, open PRs #314, #474, #476, #852 sit in facts.json `issues` with /pull/ URLs; `fr triage check` lists them as unplaced, the board shows 'Unplaced issue super-fr#…', and the architecture page files them under Other. Each of those PRs has a judgement in judgements.yaml (PR judgements are intended: the skill ranks open PRs under the same OWNER/REPO#N key).

<!-- fr:journal kind=root-cause scope=debug id=1f7d1eb5e18a created=2026-10-03T21:03:48+00:00 -->
### 1f7d1eb5e18a · root-cause · collect re-views judged PR keys with gh issue view, which returns PRs

`collect_facts` takes every judged key absent from the open-issue list (`gh issue list`, which excludes PRs) and re-fetches it with `forge.view_issue` (`_judged_elsewhere`), to settle closed issues. `gh issue view N` resolves a PR number too (verified live: `gh issue view 852` returns url .../pull/852, state OPEN). So every judged PR is appended to `issues` as an open issue, and every issue-reading view (check unplaced/unranked/settled, needs_you, architecture) counts it.

<!-- fr:journal kind=finding scope=debug id=47d208bf686b created=2026-10-03T21:25:39+00:00 state=fixed -->
### 47d208bf686b · finding [fixed] · collect keeps judged PRs out of issues; check reports them as found or settled

Fix: `collect_facts` builds a key→PR map from both PR lists and never views a judged key it names; a viewed record with a /pull/ URL is Unviewed (PR past the limit, --pr-limit hint); closed/merged judged PRs no other list carries go to the new defaulted `Facts.judged_prs`. `classify` treats a judged key naming any known PR as found, and returns non-open judged PRs as `settled_prs` (CLI, JSON, masthead and snapshot settled counts). Tests first: test_triage_collect.py (3 gh#902 tests) and test_triage_check.py (2). Live: collect+check+render on derio-net/super-fr in a scratch dir: 0 PRs unplaced, 14 judged PRs settled, 0 unreachable/orphaned.
