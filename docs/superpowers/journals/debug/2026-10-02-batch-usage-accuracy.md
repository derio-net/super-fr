# Journal: 2026-10-02-batch-usage-accuracy

<!-- fr:journal kind=repro scope=debug id=repro-637 created=2026-10-02T16:45:26+00:00 -->
### repro-637 · repro · #637: the cursor names models that did not run

Run 2026-09-26-fix-624-set-status-drop-level (archived cursor). phase/1..3/implement-phase attempts record model claude-haiku-4-5-20251001 / claude-sonnet-5 / claude-sonnet-5, but the three subagent transcripts (session d798e182…/subagents/agent-{a3c281b4…,aa1d78a9…,af67e457…}.jsonl) name only claude-opus-5-5 (13/31/42 messages). The usage file's one-model reading (opus) is CORRECT. The agent-*.meta.json files carry no model key on this host (checked 4 recent ones), so the transcript messages are the only observable source.

<!-- fr:journal kind=root-cause scope=debug id=rc-637 created=2026-10-02T16:45:26+00:00 -->
### rc-637 · root-cause · _open_dispatch records the tier binding as a dispatched attempt's model, and nothing replaces it with what ran

run_cmd.py _open_dispatch: model=_resolved_model(repo_root, harness, tier) when agent_type is not None. That's a prediction made at advance, before anything runs; the dispatch went out without a model argument, so the harness ran the executors on the orchestrator's model. _close_on_resolve / _claimed_identity only overwrite model with an agent-REPORTED --model; no path observes the subagent transcript, though attribute_dispatches already pairs agent id → transcript. Contrast: orchestrator-run attempts already record the OBSERVED orchestrator_model (debug journal C3).

<!-- fr:journal kind=repro scope=debug id=repro-756 created=2026-10-02T16:45:27+00:00 -->
### repro-756 · repro · #756: the closeout capture ran BEFORE the delivering session exited, not after

The issue premise ('moved unchanged') is wrong: the archived usage file gained at=closeout, a second session (the closeout's) and fresh tokens for adff62ba (output 33439→34479), so capture ran and re-read the transcript. It found no cost-state. Timeline (UTC, 2026-09-26) from the closeout session transcript 12cefec0 and adff62ba's mtime: 10:54:39 adff62ba's last message; 10:57:25 grep shows 0 cost-state; 11:02:52–59 fr journal resolve ×2 + fr archive (captured_at 11:02:59); 11:02:59 adff62ba.jsonl last write = cost-state ×2 + exit trailer (session exited); 11:03:27 fr usage report reads $4.27 exact. Claude Code writes cost-state only at session exit, so the read raced the exit by under a second.

<!-- fr:journal kind=root-cause scope=debug id=rc-756 created=2026-10-02T16:45:28+00:00 -->
### rc-756 · root-cause · Nothing orders the closeout capture after the delivering session's exit, and nothing re-captures later

Claude Code's dollars (cost-state) exist only once a session exits. Every capture point (resolve:*, deliver, closeout) can run while the delivering session is still open — in the batch flow the operator's session merges and closes out while the herdr-run session idles. fr archive then moves the file to implemented/usage/, which no later capture or backfill rewrites (backfill only CREATES archive files). Devcontainer mode was not the cause: the run's host-side capture read the transcript fine. Side finding: the closeout capture relabelled mode devcontainer→host-worktree because isolation_mode() reads the workspace record, which gc had reaped at 11:02:44.

<!-- fr:journal kind=finding scope=debug id=fix-637 created=2026-10-02T17:22:21+00:00 state=fixed -->
### fix-637 · finding [fixed] · resolve records the model the subagent transcript names, warning when it differs from the binding

New fr.run.telemetry.subagent_model(env, session, agent_id): the last real message.model of the subagent transcript paired by exact tool_use id (witness_transcript). run_cmd._close_on_resolve now passes the closing attempt through _observed_model: a dispatched attempt (agent_type set) with a known agent id takes the observed model, over both the binding and a reported --model, and a differing non-null prediction prints a yellow warning naming both. Unobservable leaves the attempt untouched. Pinned by tests/unit/test_run_observed_executor_model.py (resolve --agent; claim then bare resolve; matching model silent; unobservable kept). Ruled out: usage/file.py _role labelling the folded record main — the record IS the main session, and its subagent models already appear as their own rows in its models table; not a defect.

<!-- fr:journal kind=finding scope=debug id=fix-756 created=2026-10-02T17:30:48+00:00 state=fixed -->
### fix-756 · finding [fixed] · closeout names unpriced sessions and keeps the recorded mode; fr usage backfill prices them after exit

Operator chose warn + refresh (not a PR Cost-table edit). capture.unpriced_sessions(capture): tokens, no dollars. archive._archive_usage prints the session ids and 'run fr usage backfill' after the closeout capture. capture.isolation_mode takes the host's previous mode, used when the workspace record is gone (gc reaped it). usage/backfill.refreshed_file: for an archived file, re-reads only THIS host's unpriced sessions and replaces an entry only with a priced reading, appending at: backfill (existing closed vocabulary — no artifact shape change, no migration). Pinned by tests/unit/test_usage_refresh_after_exit.py, which re-stages the race by stripping/restoring the fixture's cost-state lines. Full suite: 7600 passed, 97 skipped.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-10-02T17:39:36+00:00 -->
### review-1 · review · Independent review (fresh-context code reviewer): no high-severity defects; two lower-confidence findings, both fixed

Confirmed sound: refreshed_file touches only this host's capture, never trades a reading for an absence, no at duplication, no-op re-run; isolation_mode fallback order; _note_unpriced cannot fail an archive; no artifact shape change; subagent_model pairs by exact tool_use id. Finding r1 (verified against real transcripts: haiku is recorded dated, claude-haiku-4-5-20251001 ×800, while the shipped mechanical binding is undated claude-haiku-4-5): a dispatch honouring the binding would warn — FIXED, compare via _model_family (drops date and [ctx] suffix), record the precise observed id; pinned by test_a_dated_id_of_the_bound_model_is_a_match_not_a_mismatch, which failed first. Finding r2: test_a_matching_binding_is_kept_silently passed without the feature, and the warning mislabelled a reported --model as 'the tier's binding' — FIXED (test replaced by the dated-id test; warning wording neutral). Full suite after fixes: 7600 passed, 97 skipped.
