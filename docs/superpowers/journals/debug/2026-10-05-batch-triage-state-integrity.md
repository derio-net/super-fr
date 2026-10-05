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
