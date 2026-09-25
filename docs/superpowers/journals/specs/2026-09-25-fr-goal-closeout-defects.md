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

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-25T10:05:58 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Tier-model decision not reflected in spec

Reviewer (high): decision 0736967ba3dd is neither a goal nor a non-goal in the spec.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-25T10:05:58 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · run_cmd.py:872 journal write not covered by §3.C

Reviewer (medium): fr run resolve --no-questions writes a spec-journal decision via append_journal_entry, bypassing journal_cmd; would stay uncommitted.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-25T10:05:59 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · SKILL §8 'commit plan + journals' not reconciled

Reviewer (low): spec should say how §8's manual commit line changes once fr auto-commits.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-25T10:06:20 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Tier-model decision not reflected in spec

Spec §2 non-goals now records the model bindings as an operator-environment action applied at brainstorm (fr models set), no code change.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-25T10:06:20 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: run_cmd.py:872 journal write not covered by §3.C

§3.C now covers run_cmd.py:872: fr run resolve commits cursor + spec journal together; each command commits every record path it wrote, once.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-25T10:06:21 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: SKILL §8 'commit plan + journals' not reconciled

§3.C now specifies SKILL §8: add push after deliver; 'commit plan + journals' becomes a clean-status check.

<!-- fr:journal kind=review scope=spec id=review-spec-1 created=2026-09-25T10:06:21 -->
### review-spec-1 · review · Spec review (fr-spec-reviewer)

Independent fr-spec-reviewer raised s1 (high, decision not reflected), s2 (medium, run_cmd.py:872 journal write uncovered), s3 (low, SKILL §8 commit line). All in scope, all fixed in the spec. 30 codebase claims verified by the reviewer.

<!-- fr:journal kind=decision scope=spec id=248a1091887d created=2026-09-25T12:15:07 -->
### 248a1091887d · decision · Record commits skip hooks, keep signing, restore the index on failure

Phase-3 review p3-r2: fr's record commits (run/plan/journal, not migrations) pass --no-verify — they are fr's own bookkeeping, frequent, and a fixer hook (end-of-file-fixer) would fail every tick. Commit signing is left as the repo configures it (fr never silently bypasses a signing policy). On a failed commit the index is restored to its prior state for those paths. Orchestrator's decision under the operator's 'fr commits its records' answer; surfaced in the PR body.
