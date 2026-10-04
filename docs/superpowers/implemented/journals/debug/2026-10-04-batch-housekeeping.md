# Journal: 2026-10-04-batch-housekeeping

<!-- fr:journal kind=ruled-out scope=debug id=single-root-cause created=2026-10-04T04:52:51+00:00 -->
### single-root-cause · ruled-out · Batch is not one root cause

Batch premise 'ONE root cause' ruled out on investigation. Members touch six unrelated subsystems with independent causes: #746 PATH/zsh fr-binary identity (design ask); #455 fr-worktree-create.sh agent-* mimic skips .worktreeinclude; #456 plugins/super-fr/scripts/fr-statusline-segment.sh latency (unmeasured); #619 scripts/install-validator-wrapper.sh retirement (deletion); #805/#806 isolation/scaffold.py:697 safe_dump drops comments + #794 nits; #648/#646 triage collect join_open defaults + live_reservations scope; #691 explainer 01-fr-goal.md L583-587 still says provenance is typed, default agent. Per batch rule, stopping to ask before fixing.

<!-- fr:journal kind=decision scope=debug id=scope-decision created=2026-10-04T05:07:32+00:00 -->
### scope-decision · decision · Operator scope decision

Operator chose: one PR fixing the eight mechanical members (#455 #456 #619 #805 #806 #648 #646 #691), each journalled per cause with its own failing test; #746 is a design ask, excluded from Closes, routed to its own fr-goal run.

<!-- fr:journal kind=root-cause scope=debug id=rc-805 created=2026-10-04T05:12:12+00:00 -->
### rc-805 · root-cause · #805: scaffold round-trips fr-profiles.yaml

_update_profiles_yaml (fr/isolation/scaffold.py) rebuilt the file with yaml.safe_load + safe_dump, which carry no comments, so every scaffold dropped operator comments.

<!-- fr:journal kind=finding scope=debug id=fix-805 created=2026-10-04T05:12:14+00:00 state=fixed -->
### fix-805 · finding [fixed] · #805 fixed by line surgery

New _edit_profiles_text replaces/appends only the profile entry and the default: line, drops service/legacy keys by line, and verifies the result re-reads to the intended data, else falls back to the old dump. Tests: test_init_scaffold.py::test_adding_a_profile_keeps_every_comment, ::test_rescaffolding_a_profile_replaces_only_its_entry (red first).

<!-- fr:journal kind=finding scope=debug id=fix-806 created=2026-10-04T05:12:18+00:00 state=fixed -->
### fix-806 · finding [fixed] · #806 three #794 nits fixed

registry.split_lines (re.split on newline only) replaces str.splitlines(keepends=True) in the stamp writer, journal stamp reader and the services migration (test_line_surgery_separators.py, red first). local.py uncommitted-profile hint now names --force and --tracking none (test_isolation.py::test_up_uncommitted_profile_raises_actionable_error). test_migration_trigger docstring corrected.

<!-- fr:journal kind=finding scope=debug id=fix-648 created=2026-10-04T05:15:40+00:00 state=fixed -->
### fix-648 · finding [fixed] · #648: linked non-open PRs carried default checks/merge state

Root cause: PullRequest defaulted checks to zero counts and mergeable/merge_state to UNKNOWN; parse_prs filled them with those defaults for list_prs(state=all) records that carry none, and only join_open overwrote them for open PRs. Fix: fields are Optional (None), parse_prs fills only when the record carries the key; consumers (render, views, snapshot, triage_batch_cmd) read None as no checks. Tests: test_triage_open_prs.py::test_a_linked_non_open_pr_carries_no_invented_checks_or_merge_state (red first); test_triage_facts_schema3 old-defaults test updated to the new contract.

<!-- fr:journal kind=finding scope=debug id=fix-646 created=2026-10-04T05:15:41+00:00 state=fixed -->
### fix-646 · finding [fixed] · #646: brief overstated the reserved version

Root cause: live_reservations walks only the dispatching scope batches, yet the brief said reserved for this batch; do not pick another number. batch_merge already recomputes slots from main, so only the wording misled. Fix (cheapest cut named in triage): the brief calls the number provisional and says merge renumbers. Test: test_triage_batch_dispatch.py::test_the_reserved_version_is_called_provisional_until_merge (red first).

<!-- fr:journal kind=finding scope=debug id=fix-619 created=2026-10-04T05:17:11+00:00 state=fixed -->
### fix-619 · finding [fixed] · #619: retired installer deleted

Root cause: the script outlived its caller (install.sh dropped it; fr init validator-wrapper replaced it) and stayed shipped as a hand-copied WRAPPER_TEXT duplicate. Pure deletion: script, tests/integration/test_install_validator_wrapper.py, test_closeout_run_clean byte-pin test, check-change-fragment VERSION_REQUIRED_EXACT entry, AGENTS.md/HERMES.md mentions. No red-first test: a deletion has no behaviour to pin; test_install_sh.py already pins install.sh not naming it. Historical comments naming it as retired (plan_validator_wrapper.py, test_init_cmd.py) kept.

<!-- fr:journal kind=finding scope=debug id=fix-455 created=2026-10-04T05:19:10+00:00 state=fixed -->
### fix-455 · finding [fixed] · #455: agent-* mimic copies .worktreeinclude matches

Root cause: mimic_default in plugins/super-fr/hooks/fr-worktree-create.sh ran only git worktree add, never the .worktreeinclude step spec 2026-09-04 §5.B.3 asks for. Fix: copy_worktreeinclude pipes git ls-files -o -i --exclude-from=.worktreeinclude through git check-ignore --stdin (ignored AND included), copying each best effort. Tests: test_hooks_worktree.py::TestWorktreeCreate::test_agent_worktree_copies_worktreeinclude_matches (red first), ::test_agent_worktree_without_worktreeinclude_copies_nothing.

<!-- fr:journal kind=finding scope=debug id=sec-455-symlink created=2026-10-04T05:21:32+00:00 state=fixed -->
### sec-455-symlink · finding [fixed] · Security: #455 include copy followed symlinks

Background commit security review flagged symlink-following writes in copy_worktreeinclude. Reproduced red first: a committed cfg -> outside symlink with a real cfg/ in the base checkout made the copy write cfg/.env outside the worktree. Fix: no_link_under refuses any destination with a symlink component or an existing file; cp -P copies source symlinks as links. Test: test_hooks_worktree.py::TestWorktreeCreate::test_agent_worktree_include_copy_never_writes_through_a_symlink.

<!-- fr:journal kind=finding scope=debug id=fix-456 created=2026-10-04T05:22:50+00:00 state=fixed -->
### fix-456 · finding [fixed] · #456: statusline within the 60 ms budget

Re-measured first (the script was rewritten after #456: one rev-parse, no worktree list). Component profile on the operator Mac: bash 16 ms, jq stdin 15, git rev-parse 16, jq over 13 state files 16, and 13 (cd && pwd -P) subshells ~34 ms on top: the remaining over-budget cost. Fix: [ "$wt" -ef "$toplevel" ] (builtin inode compare). Interleaved warm medians: base clone 47-59 -> 31-37 ms; fr worktree 40-49 -> 30-33 ms (machine load is noisy; a first unloaded-vs-loaded read showed 85-113 ms before). Neither of the issue's heavier options (cache, pure-bash git walk) is needed. Guard: test_statusline_segment.py::test_a_state_file_naming_the_worktree_through_a_symlink_still_matches pins the physical-path semantics; CI timing guard stays 0.5 s.

<!-- fr:journal kind=finding scope=debug id=fix-691 created=2026-10-04T05:23:44+00:00 state=fixed -->
### fix-691 · finding [fixed] · #691: explainer gate provenance rewritten

Root cause: 01-fr-goal.md paragraph predated the transcript-observed provenance in run_cmd._gate_provenance (operator observed; refusal unless --no-questions --reason -> agent + journal; typed claim only where unobservable, marked unverified). Rewrote the paragraph; re-rendered .html with the blog-craft renderer from / with --isolated after confirming the unmodified render was byte-identical to the committed page; page diff is exactly that paragraph. No test (prose); test_tripwire_explainers_fresh covers heading/title survival.

<!-- fr:journal kind=finding scope=debug id=review-r1-crlf created=2026-10-04T05:40:52+00:00 state=fixed review_scope=in -->
### review-r1-crlf · finding [fixed] (reviewer: in scope) · Review: scaffold surgery normalised CRLF

read_text converted CRLF to LF before _edit_profiles_text. Fixed: read_verbatim + write newline="", BOM preserved. Test: test_init_scaffold.py::test_a_crlf_profiles_file_stays_crlf_and_keeps_its_comments (red first).

<!-- fr:journal kind=finding scope=debug id=review-r2-dupkey created=2026-10-04T05:40:53+00:00 state=fixed review_scope=in -->
### review-r2-dupkey · finding [fixed] (reviewer: in scope) · Review: verification could not see duplicate keys

safe_load keeps the last duplicate, so an entry appended beside a quoted "dev": passed verification. Fixed: re-read with fr.artifacts.structure._StrictLoader; BOM split off by read_verbatim. Test: test_init_scaffold.py::test_a_quoted_profile_key_never_ends_up_duplicated (red first).

<!-- fr:journal kind=review scope=debug id=review created=2026-10-04T05:40:54+00:00 -->
### review · review · Milestone review

Independent code review of the branch diff (feature-dev code-reviewer, read-only). Raised two findings, both in scope and fixed: review-r1-crlf, review-r2-dupkey. Checked clean: hook set -eu/pipeline/newline handling, PullRequest None consumers, statusline -ef, deleted-script references. Separately, a background commit security review raised symlink-following writes in the #455 hook (sec-455-symlink, fixed).

<!-- fr:journal kind=finding scope=debug id=ci-py311-read-text created=2026-10-04T06:24:50+00:00 state=fixed -->
### ci-py311-read-text · finding [fixed] · CI: 3.13-only read_text(newline=) in a test

CI (Python 3.12; floor 3.11) failed test_line_surgery_separators.py: Path.read_text(newline=) is 3.13+. Replaced with open(path, encoding='utf-8', newline='').read(). Scanned the branch diff for other 3.13+ APIs: none (write_text(newline=) is 3.10+). Verified: uv run --python 3.11 pytest tests/unit/test_line_surgery_separators.py -> 2 passed; every test file the branch touches under 3.11 -> 500 passed.

<!-- fr:journal kind=decision scope=debug id=merge-main-939 created=2026-10-04T07:41:02+00:00 -->
### merge-main-939 · decision · Merged origin/main (#939 conflict)

Conflicts with #939 resolved keeping both: views.needs_you keeps #939's foreign-PR skip (gh#936) and this branch's None-safe pr.checks or {}; test_triage_open_prs keeps both sides' new tests (#939's author/cross_repo parsing follows the same absence-stays-unknown convention as #648). Remote branch had three 'update from main' merges not made in this session; merged them in rather than force-pushing. Merged explainer re-rendered byte-identical to its committed html. Verified on the merged tree: requested triage subset 58 passed; full suite 8333 passed, 105 skipped; mypy/ruff/acceptance/change-fragment/validate-artifacts green; later main commits were journal archive renames only (artifact gates re-run green).
