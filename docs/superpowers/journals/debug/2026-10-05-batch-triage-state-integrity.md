# Journal: 2026-10-05-batch-triage-state-integrity

<!-- fr:journal kind=repro scope=debug id=repro-six created=2026-10-05T21:02:42+00:00 -->
### repro-six · repro · Six independent triage-state defects confirmed on origin/main 109349659

Batch triage-state-integrity (#886 #954 #885 #888 #882 #889) was batched as one root cause. Investigation finds six: (886) _load_state never compares facts.kind to scope.kind; (954) issue_key drops the owner, so same-named repos in a group scope share keys; (885) FACTS_SCHEMA=4 stamped on every scope though only groups changed shape; (888) origins collect reads one newest-first 1000-row page and only warns; (882) closeout_state's fallback looks for a MERGED PR in facts.prs, which holds only open PRs; (889) gitseam show() decodes UTF-8 silently. Operator chose (2026-10-05): one PR, six fixes; 885 write schema 3 for repo/org; 888 refuse a truncated window; 954 owner-qualified keys + judgements schema bump + migration + collision refusal.

<!-- fr:journal kind=ruled-out scope=debug id=h-954-live-collision created=2026-10-05T21:03:51+00:00 -->
### h-954-live-collision · ruled-out · #954: same-named-repo key collision is not reachable through the CLI

Hypothesis: owner-blind keys let two same-named repos in a group share judgements. Ruled out as a live bug: commands/triage_cmd.py _group_scope refuses (exit 2) a group whose repos share a name, and every triage/batch/origins command builds its scope through triage_cmd._scope; group facts.json is only written by collect behind that refusal. The only bypass is --dir onto another scope's facts, which is #886. What remains of #954 is a capability limit (a group cannot hold same-named repos), not a collision.

<!-- fr:journal kind=ruled-out scope=debug id=h-885-shape-unchanged created=2026-10-05T21:08:14+00:00 -->
### h-885-shape-unchanged · ruled-out · #885: repo/org facts shape DID move after schema 3; stamping 3 would break the old reader worse

Hypothesis (from the issue): only groups changed shape, so repo/org could keep writing schema 3. Ruled out empirically: a current repo-scope facts.json restamped schema 3 and validated with v5.1.1's Facts (the last schema-3-only reader, extra=forbid) fails with 9 errors — prs[].checks/mergeable/merge_state (now nullable, written null), prs[].author/cross_repo (#939), config[*].post_merge (#876), config[*].pr_authors (#939), judged_prs (#906), viewer (#939). to_json dumps every field on every scope. Stamp 4 is the honest marker: it makes v5.1.1 refuse with 'unsupported schema 4; re-run collect' instead of 'invalid facts'.

<!-- fr:journal kind=root-cause scope=debug id=rc-886 created=2026-10-05T21:10:32+00:00 -->
### rc-886 · root-cause · #886: _load_state and batch list never compare facts.scope/kind to the requested scope

commands/triage_cmd.py _load_state and triage_batch_cmd.py batch list load facts.json from state_dir(scope, --dir) and use it unchecked. _previous_facts in the same module already has the right predicate (facts.scope == scope.name and facts.kind == scope.kind); the two command loaders never got it. batch list also calls load_facts bare, so a bad file is a traceback, not exit 2. The origins loader has the same hole (OriginsFacts.scope vs scope.target).

<!-- fr:journal kind=root-cause scope=debug id=rc-954 created=2026-10-05T21:10:33+00:00 -->
### rc-954 · root-cause · #954: closes through #886 — the only way two same-named repos' judgements meet is --dir onto another scope's state

See ruled-out h-954-live-collision. _group_scope already refuses same-named repos; pin that every verb (collect, check, batch, origins) refuses it, and #886's scope check closes the --dir bypass. Lifting the limit (owner-qualified keys) is a feature, deferred by operator decision.

<!-- fr:journal kind=root-cause scope=debug id=rc-885 created=2026-10-05T21:10:34+00:00 -->
### rc-885 · root-cause · #885: schema 4 is correct on every scope; the FACTS_SCHEMA comment understates why

See ruled-out h-885-shape-unchanged. The comment says 4 'added the group scope kind' only; #876/#906/#939 added fields on every scope under 4. Fix: correct the comment and pin with a test that a repo-scope facts.json carries keys the schema-3 shape lacks, so nobody re-stamps 3.

<!-- fr:journal kind=root-cause scope=debug id=rc-888 created=2026-10-05T21:10:35+00:00 -->
### rc-888 · root-cause · #888: origins collect treats 'count == limit' as the truncation signal; for a newest-first list the signal is 'oldest row read is still inside the window'

triage/origins.py collect_origins warns when len(raw) == limit. gh lists issues and PRs newest-first, so a capped list covers [since, now] iff its oldest createdAt predates since. When it does, the warning is spurious; when it does not, rows inside the window are missing and counts are silently partial. Fix (operator decision): refuse (TriageError, exit 2, nothing written) naming a --since that the rows read do cover; drop the warning when the window is covered.

<!-- fr:journal kind=root-cause scope=debug id=rc-882 created=2026-10-05T21:10:36+00:00 -->
### rc-882 · root-cause · #882: the driver records 'archived' only for archive PRs it merged itself or close-outs it adopted; closeout_state's facts fallback is dead (facts.prs is open-only)

batch_drive.py step 3 sees a started close-out whose attributed archive PR is MERGED (is_finished) and just continues: nothing is written, so batch list reads the event, finds archived None, and falls back to a MERGED chore/closeout-* PR in facts.prs, which collect fills with open PRs only. Fix: the pass records it once, as the adopt path already does (append a closeout event with archived=<pr>), and the dead facts.prs fallback goes; batch list then reads one source, the event, like the driver.

<!-- fr:journal kind=root-cause scope=debug id=rc-889 created=2026-10-05T21:10:37+00:00 -->
### rc-889 · root-cause · #889: gitseam show() decodes through subprocess text mode — locale encoding, universal newlines, UnicodeDecodeError on binary — and snapshot_paths uses it to copy whole trees

Checkout.show/Worktree.show call git() (text=True): the decode is the locale's, not UTF-8; CRLF becomes LF; a binary blob raises UnicodeDecodeError, which is not a TriageError, so it escapes as a traceback. Every caller wants text (version manifests, .fr/triage.yaml) except Checkout.snapshot_paths, which copies SERVICE_PATHS trees byte-for-byte in intent. Fix: show_bytes() for raw content (snapshot_paths uses it with write_bytes); show() decodes those bytes as UTF-8 explicitly and refuses a non-UTF-8 blob with a GitError naming file and ref; contract documented.

<!-- fr:journal kind=finding scope=debug id=fx-886 created=2026-10-05T21:57:12+00:00 state=fixed -->
### fx-886 · finding [fixed] · #886 fixed: facts and origins facts of another scope are refused

Facts.matches + load_scope_facts (model.py) in _load_state, batch list, _previous_facts; load_scope_origins_facts in origins and architecture render. Pinned by tests/unit/test_triage_state_integrity.py (state-directory, kind, origins, architecture tests). Commits 85e3ac01b, 25545b911.

<!-- fr:journal kind=finding scope=debug id=fx-954 created=2026-10-05T21:57:13+00:00 state=fixed -->
### fx-954 · finding [fixed] · #954 closed: same-name refusal pinned on every verb; its --dir bypass closed by #886

test_every_verb_refuses_a_group_of_two_repos_sharing_a_name (collect, check, render, batch list, batch drive, origins collect/check). Owner-qualified keys deferred as a feature by operator decision.

<!-- fr:journal kind=finding scope=debug id=fx-885 created=2026-10-05T21:57:14+00:00 state=fixed -->
### fx-885 · finding [fixed] · #885 closed as decided: schema 4 stays on every scope

FACTS_SCHEMA comment states why; test_repo_and_org_facts_are_stamped_schema_4_because_their_shape_moved pins it.

<!-- fr:journal kind=finding scope=debug id=fx-888 created=2026-10-05T21:57:15+00:00 state=fixed -->
### fx-888 · finding [fixed] · #888 fixed: origins collect refuses a window one page does not cover

_short_of + refusal in collect_origins naming a covered --since and the --issue-limit/--pr-limit flags (new); no future or drifting since. Tests in test_triage_state_integrity.py; test_triage_origins.py warn test rewritten as a refusal test. fr-origins skill + mirrors. Commits 53f1cc387, 25545b911.
