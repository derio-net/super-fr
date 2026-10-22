# fr ops — checkable, runnable manual operations and the DevOps stage

## Context

A plan's manual operations are prose today. In consumer repos they are fenced YAML
blocks whose first line is `# manual-operation` (frank's convention:
`agents/rules/repo-manual-ops.md`, synced into a central runbook by `/sync-runbook`).
fr itself knows only `tag: manual` phases (`fr/types.py` `PhaseHeader.tag`) and the
agentic-purity lint over step text (`fr/plan_ops.py` `_MANUAL_VERB_RES`). Nothing
checks an op, nothing runs one, and at `deliver` and close-out the operator works out
by hand which ops are done and in what order the rest run.

gh#1220 records one run (frank#875) where an ad-hoc `status`/`apply` script's live
checks caught five defects that tests, three reviews and CI missed, and a close-out
round where seven of nine further defects were invisible to everything but a check
that ran as the real identity against the live system. The same script carried its
own safety bugs (plaintext left behind on a failed encryption, a scratch repo left
by Ctrl-C, a silent exit in a failing `$(…)` under `set -e`).

The operator settled two structural points beyond the issue. Ops need credentials
that the delivering agent does not have, so they run under an **ops profile**.
And the **DevOps gate stops being a post-merge label only**. It becomes an
interactive stage, run on the ops profile, that owns pre-merge ops, the merge
itself and post-merge ops, then hands the Test Plan's tester part to the Tester
gate. The delivering agent's job ends at a PR plus the list of owed ops. Today
`fr.gates.POST_MERGE_GATES` holds only the close-out.

Today's surfaces this changes: `fr/record/pr_body.py` (`REQUIRED_SECTIONS`,
`render_pr_body`), `fr/run/closeout.py` (`branch_closeout_brief`),
`fr/commands/gate_cmd.py` (`fr gate pass`), `fr/spec.py` (`test_plan_steps`),
`fr/journal/model.py` (`JournalKind`), `fr/artifacts/registry.py` (journal kind at 2),
`.devcontainer/fr-profiles.yaml` profile entries (`fr/isolation/types.py`
`discover_profiles`).

## Requirements

R1. An op is a typed record with `id`, `summary`, `phase: pre-merge|post-merge`, optional `needs: [<op-id>]`, `check:` (a read-only probe; exit 0 = done, otherwise open, its last stdout line the reason), `apply:` (idempotent automation; absent for UI-only ops), `undo:` (or an explicit `undo: none` with a reason), `mutating: true|false`, `side_effects:` (prose list), `identities: [<name>]` (the consumer identities the check runs as), `vacuous_if:` (what the probe would look like if it proved nothing), and human `commands`/`verify` prose. Unknown keys are refused, naming the key.
R2. Ops are read from two carriers in one plan: an optional `ops.yaml` in the plan folder (canonical) and `# manual-operation` fenced YAML blocks inside step text, dedented (back-compat, frank's existing blocks, whose own fields `layer`/`app`/`plan`/`when`/`why_manual`/`status` are accepted and ignored). An op id defined in both carriers is an error. Ops also come from a repo runbook named by `.fr/ops.yaml` `runbook: <path>` (frank's `manual-operations.yaml` shape), so ops from earlier plans are checkable.
R3. `fr ops status [--plan <dir>] [--phase pre-merge|post-merge] [<op-id>] [--json]` reports each op as DONE (checked), DONE (attested), OPEN (with the check's reason), N/A, UNVERIFIABLE (no `check:`, never attested), or CANNOT-VERIFY (the check could not run: missing tool or credential, distinct from OPEN). It never mutates the target system. It runs anywhere and warns when not inside an ops profile. Exit 0 iff nothing is OPEN, UNVERIFIABLE or CANNOT-VERIFY in the selection.
R4. `fr ops apply <op-id>` and `fr ops apply --phase pre-merge|post-merge` run in `needs` dependency order (a cycle or an unknown `needs` id is refused before anything runs). They check first and skip a DONE op, reporting "already done, nothing written". They confirm each op on the TTY, and a `mutating: true` op names its side effects and undo in the prompt. They stop at the first failure, naming the op and its undo. After an apply they re-run the check and record evidence. A second run over a done phase writes nothing and says so. `apply` refuses (exit 2) outside an ops profile.
R5. A check runs once per declared identity: `identities:` names entries of `.fr/ops.yaml` `identities: {<name>: {env: {...}}}`. The check runs with that identity's environment (a credential reference read live, never inlined), and every identity must pass for DONE. The report names the failing identity. A check's reason line keeps a status code and never echoes a forge or API response body.
R6. An op is "ops-profile"-bound: a profile entry in `fr-profiles.yaml` may declare `ops: true`, and `fr init scaffold` gives such a profile `FR_PROFILE=<name>` in its container env. `fr ops apply` (and `fr ops gate`'s op stages) pass only when `FR_PROFILE` names a profile declared `ops: true` and container evidence is present. Otherwise they refuse, naming the `fr isolation exec --profile <ops>` command.
R7. Evidence is durable and shared. Every apply result, every check outcome recorded by `apply`/`gate`, every one-off proof and every attestation is a plan-journal entry of a new `op` kind (`op: <id>`, `result`, `identity`, `at`, the check's reason; never secret material). `fr ops status` reads the latest entry per op across the plan's journal and, for runbook ops, every live and archived plan journal. A one-off proof (an op whose `check:` is `proof`) reads DONE only from a recorded entry.
R8. `fr ops attest <op-id> --note <text>` closes an UNVERIFIABLE op as DONE (attested) with `answered_by: operator`. Status and the PR body always show attested apart from checked. An op that has a `check:` cannot be attested.
R9. An op that only gates a requirement, an optional dependency whose absence silently disables behaviour, declares `disables: <consequence>`. When its check fails, it reports OPEN with that consequence and is never N/A. `escalate:` (an optional probe) turns status into an ESCALATE line when the condition a pending op protects against is already happening, and `fr ops status` exits 3 on any ESCALATE.
R10. Generic, tool-neutral safety helpers ship as fr subcommands, with no sops/kubectl/forge names in code. `fr ops seal --encrypt '<cmd with {in} and {target}>' --target <path>` takes plaintext from stdin into a 0600 temp file outside the repo, removed on every exit path including signals, and installs the target only after the encrypt command succeeds, atomically. On failure no plaintext exists in the repo or at the target, and the exit is non-zero. `fr ops secret --from '<cmd>'` reads a value live and passes it to a child via env or stdin, never to stdout. `fr ops clip --from '<cmd>'` puts a value on the clipboard. `fr ops scratch --cleanup '<cmd>' -- <command>` runs a command and its cleanup on any exit.
R11. A post-merge op may declare `ready:`, a probe of a live artifact that only the merged revision produces. Post-merge apply refuses until `ready:` passes, and a forge's merged state alone never satisfies it.
R12. The Test Plan splits by step tag. A Test Plan item may start `[devops]` or `[tester]`, and an untagged item takes the run's gate. `fr closeout`/`fr archive` outcome recording is unchanged. The tag is parsed, removed from the step text everywhere it is shown, and a tag outside the two names is an error naming the step.
R13. `deliver` renders a new required `## Manual operations` PR-body section from the plan's ops and recorded evidence, with no live probes. It lists each op's phase, last recorded state (or "never checked") and its `fr ops apply`/`attest` command, plus a Ready-checklist line saying the DevOps stage owns them. `deliver` does not refuse on OPEN ops. A plan with any pre-merge op gives the run gate `devops`, synced as the `gate:devops` label at deliver, whatever the spec's `## Verification` says.
R14. `gate: devops` holds a PR before merge as well as its close-out: a PR carrying `gate:devops` without `gate:devops-passed` is not mergeable by the triage driver, and `fr gate pass --gate devops` refuses while any op of the run's plan, or any `[devops]` Test Plan step, is OPEN, UNVERIFIABLE, CANNOT-VERIFY or without an outcome.
R15. `fr ops gate --run <run-id>` is the DevOps stage's engine. It is interactive, previews by default, `--yes` acts, and it is resumable from what it recorded. Its stages run in order: (1) pre-merge `status` then `apply --phase pre-merge`, inside an ops workspace `chore/ops-<slug>` cut from the PR head on the ops profile, with evidence pushed to the feature branch as `chore(fr):` commits; (2) the merge, executed by the session through the forge adapter only after an explicit operator confirmation, and only when pre-merge shows nothing OPEN and the PR's required checks pass; (3) `fr isolation verify-merge` and every `ready:`; (4) `apply --phase post-merge` then `status`; (5) the `[devops]` Test Plan steps, each recorded with `fr closeout outcome`; (6) `fr gate pass --gate devops`; (7) when `[tester]` steps remain, the `gate:tester` label with those steps listed in its comment. It stops at the first failure naming the stage and resumes there. The delivering agent never runs it.
R16. A thin `fr-devops-gate` skill (canonical plus the OpenCode and Hermes mirrors, and install.sh) drives `fr ops gate` and holds only the judgement: reading OPEN reasons, choosing attest vs. writing a check, confirming the merge. `fr pickup --run` for a devops-gated run prints `fr ops gate --run <id>` as its first close-out step instead of the generic Test Plan line. `fr ops status` follows it for runs with post-merge ops.
R17. `fr ops` is a CLI surface every harness drives identically. The `ops` group writes only plan-journal entries through `fr journal`'s engine, and the artifact gate treats it as a mutating command (not in `READ_ONLY_COMMANDS`), except `status`, which writes nothing. The journal kind moves 2 → 3 for the `op` entry kind with a stamp-only migration. The profiles kind is unchanged, because `ops: true` is a per-profile key the current reader already accepts. The `ops.yaml` file carries its own `schema_version: 1` and is validated by `fr validate artifacts` as part of the plan kind.
R18. Documentation: `docs/ops.md` (authoring ops, identities, helpers, the DevOps stage) and the fr-goal/explainer prose where `deliver` and the close-out are described. frank's adoption (replacing `scripts/ci-budget-ops.sh` with `check`/`apply` fields and carrying them through `/sync-runbook`) is a follow-up frank issue, not part of this change.

## Design

### A. The op model (`fr/ops/model.py`)

`Op` is a frozen pydantic model, `extra="forbid"`, with the R1 fields. `check`, `apply`,
`undo`, `ready` and `escalate` are shell strings run via `bash -euo pipefail -c` with the
repo root as cwd and the op's identity environment. `check: proof` is a reserved
value: the check is satisfied only by a recorded `op` journal entry with
`result: done` (R7). A legacy frank block is parsed through `LegacyBlock`, which
accepts frank's fields and maps `commands`/`verify` across, so the strict model never
sees frank-only keys. Its `status:` is ignored, because evidence lives in the journal.

### B. Carriers (`fr/ops/load.py`)

`load_ops(plan_dir, repo_root) -> OpSet` reads `ops.yaml` (`schema_version: 1`,
`ops: [...]`), then every phase file's step text. For each step it finds fenced YAML code
blocks whose first non-blank line is `# manual-operation`, dedents
them, and parses them (fence-aware, reusing `spec.py`'s fence regex). Then it reads
the runbook from `.fr/ops.yaml` when one is declared. A duplicate id across the plan
carriers is an error. A runbook op with a plan's id is shadowed by the plan's op,
with a warning. Errors name file and line.

### C. Status and apply (`fr/ops/engine.py`)

The engine is pure over an injected `Runner` (which runs a shell string with an env and
returns `(exit, last_line)`) and an injected journal reader/writer, so tests need no
subprocesses. `order(ops)` is a topological sort that refuses cycles and unknown ids.
`status` evaluates `check` once per identity. Identity env values are
`{from: '<cmd>'}` references resolved through the same live reader as `fr ops
secret`, and they never enter the report. A check that exits 127, or whose identity
reference cannot be read, is CANNOT-VERIFY. `apply` follows the R4 algorithm. The
confirmation prompt reads `/dev/tty`, and with no TTY `apply` refuses unless `--yes`
is passed. Even with `--yes`, a `mutating: true` op still needs `--yes-mutating`.

### D. Evidence (`op` journal kind)

An `op` entry is written through `fr journal`'s engine. Its body holds `key: value`
lines (`op`, `result: done|open|failed|attested|proof`, `identity`, `reason`,
`phase`), and its title is `op <id>: <result>`. Journal kind 3 adds `op` to
`JournalKind`. Migration `fr.artifacts.journal_op` is stamp-only and registered in
`MIGRATIONS`. `fr journal check` ignores `op` entries (they are never findings).
`fr ops status` folds the entries per op, and the last one wins.

### E. Profiles

`ops: true` is an optional key on a profile entry. `fr isolation scaffold` writes
`containerEnv.FR_PROFILE` for every profile it scaffolds (harmless for the rest) and
`fr init` asks about an ops profile only when the repo has ops. `in_ops_profile()`
checks `FR_PROFILE`, the declaration in `fr-profiles.yaml`, and container evidence
(`/.dockerenv`, `/run/.containerenv`, `$KUBERNETES_SERVICE_HOST`, as the edit gate
does). `status` warns and `apply` refuses when it fails.

### F. Helpers (`fr/ops/helpers.py`, `fr ops seal|secret|clip|scratch`)

`seal`: `tempfile.mkstemp(dir=<$TMPDIR outside repo>)` with mode 0600, an
`atomic` install via `fr.artifacts.atomic.write_text_atomic`'s rename discipline,
and cleanup in `finally` plus SIGINT/SIGTERM handlers. `{in}`/`{target}` are
substituted `shlex.quote`d. A target inside the repo whose encrypt command fails
leaves the pre-existing target byte-identical. `clip` picks `pbcopy`, `wl-copy`,
`xclip` or `clip.exe`, and refuses with the list when none exists. The docs
(`docs/ops.md`) show sops (`--filename-override {target}`), kubectl and forge
probes only as examples.

### G. Test Plan tags (`fr/spec.py`)

`test_plan_steps` returns `Step(n, text, gate)`, where `gate` is `devops`, `tester`
or `None`. `_ITEM_RE` keeps matching. A leading `[devops]`/`[tester]` is stripped
into `gate`, and any other leading `[word]` is an error naming the step. Every
current caller keeps reading `.text`.

### H. Deliver and gates

`render_pr_body` gains `## Manual operations`, inserted after `## Post-merge
verification owed` and added to `REQUIRED_SECTIONS` in that position. The section
reads "None." for a plan with no ops, so older runs re-render compliant. The run gate
promotion to `devops` (R13) happens in the existing label sync at deliver, through
`fr.verification.labels`. `fr gate pass --gate devops` (R14) loads the run's plan via
the PR's run file on the default branch and refuses with the open list. The triage
driver's merge step (`batch_merge`) treats an un-passed `gate:devops` as a hold.

### I. The DevOps stage (`fr ops gate`, `fr/ops/gate.py`)

A sequenced engine in the `batch_closeout` style: it decides and sequences, while a
`Worktree` seam runs git and `fr`, and the forge adapter merges (`GhClient`; another
forge's merge raises `UnsupportedForgeOperation` naming the manual step). Its
progress is the `op` entries plus `gate-stage` journal decisions, so a rerun resumes
at the first stage not recorded as done. The engine itself runs on the harness host,
like `fr run`. Op stages execute through `fr isolation exec --profile <ops>` in the
ops workspace (R15). The merge confirmation is a TTY prompt naming the PR, its head
sha and the pre-merge state, and `--yes` alone never merges without it.

## Verification

strategy: candidate
gate: developer
gate: fr-ops-live-first-run=devops
- fr-ops-live-first-run: live — only a released fr inside a real ops profile, against real credentials, a live system and a real PR merge, can prove the DevOps stage end to end; candidate scenarios use local, credential-free checks and a fake forge.

## Test Plan

- [devops] Post-merge — operator-driven: with the released fr, scaffold an ops profile in a disposable repo (or frank, once its follow-up issue lands), write a plan with one pre-merge and one post-merge op (`check`, `apply`, `ready`, one identity), deliver a PR, and run `fr ops gate --run <id>` through every stage: pre-merge apply, confirmed merge, `ready`, post-merge apply, the `[devops]` step, and the gate pass. Confirm a second `fr ops gate` writes nothing and that `fr ops status` from a fresh checkout shows the recorded evidence. Record the walk for `fr-ops-live-first-run`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
