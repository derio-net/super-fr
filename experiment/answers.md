# Answer sheet — written BEFORE either run

Whichever run goes second would otherwise profit from what the operator learned
answering the first. So every design question is answered here, in advance,
identically for both runs. Read the answer out; do not improvise.

If a run asks something this sheet does not cover, answer as briefly as
possible, and log it in `corrections.md` — an unanticipated question is itself
a measurement.

| # | Question | Answer |
|---|---|---|
| 1 | New verbs, or make `add` upsert? | **New explicit verbs.** `fr journal update --id <id> --state open\|fixed\|refuted [--note ...]`; `fr acceptance set-status --id <id> --status <s> [--note ...]`; `fr acceptance add-level --id <id> --level <unit>=<repo>:<path>`. |
| 2 | What should a duplicate `--id` on `add` do? | **Error**, exit non-zero, naming the update verb. Silence is the bug. Call out any caller that relied on the old skip. |
| 3 | Are all status transitions allowed? | Yes, but moving **down** (`ci`/`scheduled` → `skipped`/`not-implemented`) or to `failing` **requires `--note`**. |
| 4 | Must the committed reports regenerate? | Yes — `set-status` and `add-level` regenerate all three, exactly as `add` does. Never leave them stale. |
| 5 | Journal state lives in two places | `update` must rewrite **both** the `<!-- fr:journal … state=… -->` marker and the `[open]` tag in the `### <id> · finding [open] · …` heading, or neither. |
| 6 | Artifact shape change? | **No.** No new required field, so no stamp bump and no migration. Version bump is **minor** (new subcommands). |
| 7 | Out of scope | Bulk edits, undo, GitHub sync, any new artifact kind. |
| 8 | Docs that must move with it | `plugins/super-fr/skills/fr-goal/SKILL.md` (§7/§8), `plugins/super-fr/agents/fr-phase-executor.md`, `.claude/rules/acceptance-matrix.md`, and the generated OpenCode/Hermes mirrors. |
