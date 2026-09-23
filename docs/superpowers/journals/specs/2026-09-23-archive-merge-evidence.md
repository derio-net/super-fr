# Journal: 2026-09-23-archive-merge-evidence

<!-- fr:journal kind=decision scope=spec id=d1-scope created=2026-09-23T16:51:45 -->
### d1-scope · decision · Fold #544 in: fr archive refuses a plan not complete on the default branch

Operator answer (batched Q&A, AskUserQuestion): 'Also fix #544'. Recommended option was status-only; operator chose to fix the mutating half too.

<!-- fr:journal kind=decision scope=spec id=d2-suggestion created=2026-09-23T16:51:45 -->
### d2-suggestion · decision · The sweep always suggests per-plan fr archive commands, never --all

Operator answer: 'Always per-plan' (recommended option was per-plan with --all only when safe).

<!-- fr:journal kind=decision scope=spec id=d3-evidence created=2026-09-23T16:51:46 -->
### d3-evidence · decision · Merge evidence is gathered with a git fetch first, then read from origin/<default>

Operator answer: 'git fetch first' (recommended was the offline local ref). fr status gains a remote-tracking-ref side effect; a fetch failure must degrade to the local ref, stated, never to silence.

<!-- fr:journal kind=decision scope=spec id=d4-json created=2026-09-23T16:51:46 -->
### d4-json · decision · JSON: archivable narrows to merged-only; add complete_unmerged and default_ref

Operator answer: recommended option. in_progress unchanged.

<!-- fr:journal kind=discovery scope=spec id=o1-bind created=2026-09-23T16:51:55 -->
### o1-bind · discovery · P7.T1.S3 first half PASS: fr run start bound the session

fr isolation status right after fr run start (global fr 4.17.2): fix/526-status-archivable-merged ... sessions=23343080-96cd-4d63-a694-ddef4d6fb103. Also noted: the worktree was cut from d736cecb while local main was f6a26033 (stale origin/main ref at up time; fast-forwarded after fetch); FR_ISOLATION_TARGET=worktree was ignored by fr run start (profile=dev container=running).

<!-- fr:journal kind=review scope=spec id=r1-spec-review created=2026-09-23T16:57:34 -->
### r1-spec-review · review · Spec review (dispatched reviewer, 10 findings): all folded into the spec

1 important: a trailing manual phase ships unticked, so full-completeness-on-ref would make fr archive refuse every fr-goal plan on main forever and break the close-out -> merge evidence is agentic phases only; manual phases stay judged locally; a fourth sweep bucket 'merged, manual phases still open'. 2 important: _remote_name is private and can return GitRefusal -> extract public fr.git.remote_default_ref/remote_name; refusal -> ref=None with ref_error. 3 important: dispatched plans vs the offline sweep -> limit stated, completed_unarchived_plans docstring corrected. 4 important: fetch for status <plan>/apply nudges and archive_ready -> all fetch=True, archive_ready uses same landed. 5 important: test seam -> module-level _fetch monkeypatchable, timeout test. 6 minor: tripwire explicit skip when ref None. 7 minor: landed_phases needs per-phase parse; phase identity by number noted in Risks. 8 minor: unparsed_on_ref surfaced. 9 minor: fr-progress has two --all lines, both change. 10 minor: no-remote risk + refusal text.
