# Journal: 2026-09-25-fr-goal-closeout-defects

<!-- fr:journal kind=decision scope=spec id=fa46618d8b0c created=2026-09-25T09:56:21 -->
### fa46618d8b0c · decision · fr commits its own record writes

Q&A 1 (operator: 'fr commits its records (Recommended)'): every fr run cursor write and fr-authored plan/_meta write is followed by a path-scoped chore(fr) commit on a feature branch, reusing commit_migration's generic machinery; never on the default branch, never sweeping other staged files. Guards (repair/archive/down) stay strict.

<!-- fr:journal kind=decision scope=spec id=bda709e18ca8 created=2026-09-25T09:56:22 -->
### bda709e18ca8 · decision · No closeout step; deliver hands off an exact fr pickup command

Q&A 2 (operator, verbatim): 'no closeout, this is too much handholding for little benefit. Just tell the user to do the closeout in a new session with fr pickup, give the exact command. The closeout cost can be recorded in the new session'. So: no workflow-shape change, no closeout agent. fr pickup gains a way to print the post-merge closeout brief from the run file, and deliver's handoff names that exact command.

<!-- fr:journal kind=decision scope=spec id=7af74f9f2cfb created=2026-09-25T09:56:22 -->
### 7af74f9f2cfb · decision · Defect 2 (container port publishing) dropped

Q&A 3 (operator, verbatim): 'drop the feature, this is very narrow scope, we don't need it that much to incorporate to the plugin'. No ports/publish/port-helper work in this change; the issue's acceptance item 2 is explicitly not delivered.

<!-- fr:journal kind=decision scope=spec id=0736967ba3dd created=2026-09-25T09:56:23 -->
### 0736967ba3dd · decision · Tier models: haiku/sonnet/opus on claude-code

Q&A 4 (operator: 'haiku/sonnet/opus (Recommended)'): fr models set --harness claude-code mechanical=claude-haiku-4-5-20251001, standard=claude-sonnet-5, hard=claude-opus-5-5 (replacing prior all-opus bindings).

<!-- fr:journal kind=decision scope=spec id=a7323cb1b1e2 created=2026-09-25T09:56:23 -->
### a7323cb1b1e2 · decision · Defaults stated in the Q&A preamble (not objected to)

Defect 1: --default-branch optional; unset resolves via the existing _resolve_default_branch(); live path catches IsolationError -> clean exit 2; closes #469. Defect 3: fr plan create installs+stages the validator wrapper when it creates the plans dir; harness-neutral fr init validator-wrapper replaces the Claude-path REPAIR_COMMAND; the 'in the working tree' wording is corrected. Scope: all remaining defects in one spec and one PR.
