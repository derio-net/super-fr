# Journal: 2026-10-05-batch-triage-state-integrity

<!-- fr:journal kind=repro scope=debug id=repro-six created=2026-10-05T21:02:42+00:00 -->
### repro-six · repro · Six independent triage-state defects confirmed on origin/main 109349659

Batch triage-state-integrity (#886 #954 #885 #888 #882 #889) was batched as one root cause. Investigation finds six: (886) _load_state never compares facts.kind to scope.kind; (954) issue_key drops the owner, so same-named repos in a group scope share keys; (885) FACTS_SCHEMA=4 stamped on every scope though only groups changed shape; (888) origins collect reads one newest-first 1000-row page and only warns; (882) closeout_state's fallback looks for a MERGED PR in facts.prs, which holds only open PRs; (889) gitseam show() decodes UTF-8 silently. Operator chose (2026-10-05): one PR, six fixes; 885 write schema 3 for repo/org; 888 refuse a truncated window; 954 owner-qualified keys + judgements schema bump + migration + collision refusal.
