# Journal: 2026-10-02-batch-usage-accuracy

<!-- fr:journal kind=repro scope=debug id=repro-637 created=2026-10-02T16:45:26+00:00 -->
### repro-637 · repro · #637: the cursor names models that did not run

Run 2026-09-26-fix-624-set-status-drop-level (archived cursor). phase/1..3/implement-phase attempts record model claude-haiku-4-5-20251001 / claude-sonnet-5 / claude-sonnet-5, but the three subagent transcripts (session d798e182…/subagents/agent-{a3c281b4…,aa1d78a9…,af67e457…}.jsonl) name only claude-opus-5-5 (13/31/42 messages). The usage file's one-model reading (opus) is CORRECT. The agent-*.meta.json files carry no model key on this host (checked 4 recent ones), so the transcript messages are the only observable source.
