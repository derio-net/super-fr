# Journal: 2026-10-10-herdr-opencode-uptake

<!-- fr:journal kind=repro scope=debug id=live-startup-stall created=2026-10-10T01:54:29+00:00 -->
### live-startup-stall · repro · Authorized live walk stalled before first OpenCode prompt uptake

Final candidate b348f8b2 launched real OpenCode with selected model at stable base and Herdr reported ready, but two dispatched initial prompts returned agent_prompt_stalled after five seconds and captured screen remained empty home prompt. Owned fixture processes/workspaces were closed, source transcripts retained; no passing live verdict. Reuse feat/1089 and draft1115, no new PR; investigate startup/render versus submission before fixing.
