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
gate. The delivering agent's job ends at a PR plus the list of owed ops. Today the
gate vocabulary's post-merge gates (`fr/gates.py:16`, `POST_MERGE_GATES = {tester,
devops}`) hold only a merge's close-out (`gates.py:3-5`).

Today's surfaces this changes: `fr/record/pr_body.py` (`REQUIRED_SECTIONS`,
`render_pr_body`), `fr/verification/exit.py` (`run_exit`, `Exit`),
`fr/run/closeout.py` (`branch_closeout_brief`), `fr/commands/gate_cmd.py` (`fr gate
pass`), `fr/triage/batch_merge.py` (`_approved_and_ready`), `fr/spec.py`
(`test_plan_steps`), `fr/journal/model.py` (`JournalKind`), `fr/artifacts/registry.py`
(journal kind at 2, a new `ops` kind), `fr/isolation/scaffold.py`
(`_update_profiles_yaml`, `containerEnv`), `fr/commands/init_cmd.py` (`fr init
scaffold`), and the `.devcontainer/fr-profiles.yaml` profile entries read by
`fr/isolation/types.py` `profiles_config`.

## Requirements

R1. An op is a typed record. **Required:** `id`, `summary`, `phase: pre-merge|post-merge`. **Optional:** `needs: [<op-id>]`; `check:` (a read-only probe: exit 0 = done, any other exit = open, its last stdout line the reason; the reserved value `proof` means "done only once a recorded proof says so", R7); `na_if:` (a probe; exit 0 = not applicable here); `apply:` (idempotent automation; absent for UI-only ops); `undo:` (a command, or `none: <reason>`); `mutating: true|false` (default false); `interactive: true|false` (default false: apply needs a terminal for authorisations); `side_effects:` (prose list); `identities: [<name>]`; `ready:` (R11); `disables:` and `escalate:` (R9); `vacuous_if:` (prose naming what the probe would look like if it proved nothing, shown by `fr ops status --explain`); and the human prose `commands`/`verify`. Unknown keys are refused, naming the key and its file and line.
R2. A plan's ops come from two carriers: an optional `ops.yaml` in the plan folder (canonical) and `# manual-operation` fenced YAML blocks inside step text, dedented (back-compat). An op id defined in both carriers is an error. A legacy block is read through its own model. frank's fields `layer`/`app`/`plan`/`when`/`why_manual` are accepted; `summary` defaults to `why_manual`; `phase` defaults to `post-merge` unless the block sets it; a legacy `status:` reads `done` (or a `done …` prefix) as DONE (legacy), a closed state shown apart from checked and attested, `decommissioned`/`n/a` as N/A (legacy), and anything else as not closed; non-string `commands`/`verify` items are kept as prose. The block may also carry any R1 field; a key that is neither R1's nor frank's (frank's real runbook carries `note`, `notes`, `done_note`, `decommissioned`) is kept as prose with a warning, never refused, because the legacy carrier is a convention fr does not own. `Op` itself (`ops.yaml`) stays strict. Ops from a repo runbook (`.fr/ops.yaml` `runbook: <path>`, frank's `manual-operations.yaml` shape) are read through the same legacy model, but only into an explicit selection (`--runbook`, or an id a plan op names in `needs`). Never a plan's default selection or the R14 set.
R3. `fr ops status [--plan <dir>] [--runbook] [--phase pre-merge|post-merge] [<op-id>] [--json] [--explain]` reports each selected op as DONE (checked), DONE (attested), DONE (legacy), OPEN with the check's reason, N/A (`na_if` passed), UNVERIFIABLE (no `check:` and not closed), or CANNOT-VERIFY (the check could not run: exit 127, or an identity's credential reference could not be read; distinct from OPEN). It never mutates the target system and never writes. `--plan` defaults to the plan of the run whose `branch` is the current branch, and it refuses when there is none. It runs anywhere and warns when not inside an ops profile. Exit codes: 0 when everything is DONE or N/A, 1 when anything is OPEN, UNVERIFIABLE or CANNOT-VERIFY, 3 when anything ESCALATEs (R9; it outranks 1), 2 on refusal.
R4. `fr ops apply <op-id>` and `fr ops apply --phase pre-merge|post-merge` run in `needs` dependency order. A cycle or an unknown `needs` id is refused before anything runs. Each op is checked first, and a DONE or N/A op is skipped, reporting "already done, nothing written". Each op is confirmed on the terminal, and a `mutating: true` op's prompt names its side effects and its undo. Without a terminal, `--yes` confirms non-mutating ops, and mutating ops also need `--yes-mutating`. The run stops at the first failure, naming the op and its undo. After an apply it re-runs the check and records the result (R7). A second run over a done phase writes nothing and says so. `apply` refuses (exit 2) outside an ops profile (R6).
R5. A check runs once per declared identity. `identities:` names entries of `.fr/ops.yaml` `identities: {<name>: {env: {<VAR>: {from: '<cmd>'}}}}`. Each reference is read live at check time and never inlined, logged or recorded. Every identity must pass for DONE, and the report names the failing identity. One identity list drives both `check` and `apply` loops, so the two cannot drift. A reason line keeps a status code and never echoes a forge or API response body: every identity value is masked line by line and token by token, in its raw, base64 and URL-encoded forms; for a check run as an identity, a line that still looks like a response body (JSON, or over 200 characters) is dropped and only `exit N` is reported. Identity references are resolved once per invocation. Every probe (`check`, `na_if`, `escalate`, `ready`, an identity's `from:`) runs with stdin closed, a bounded timeout (a timeout reads CANNOT-VERIFY, "timed out"), and a minimal environment: `PATH`, `HOME`, `LANG`, `LC_ALL`, `TERM`, `TMPDIR`, `USER`, plus the variables named in `.fr/ops.yaml` `env_passthrough:` and, for `check`/`apply` only, the identity's variables. `na_if`/`escalate` never receive identity variables.
R6. An ops profile is a `fr-profiles.yaml` profile entry declaring `ops: true`. `fr init scaffold --ops` writes that key and gives the profile `containerEnv.FR_PROFILE=<name>`. Re-scaffolding preserves every existing entry key it does not own. An existing profile gains the key and `FR_PROFILE` by re-running `fr init scaffold --ops --force`, then `fr isolation rebuild`. `in_ops_profile()` holds when `FR_PROFILE` names a profile declared `ops: true` and container evidence is present (`/.dockerenv`, `/run/.containerenv`, or `$KUBERNETES_SERVICE_HOST`). `apply`, `attest` and `seal` refuse outside it, printing the ops-workspace route: `fr isolation up --profile <ops> --branch chore/ops-<slug> --base <ref>`, then `fr isolation exec --branch chore/ops-<slug> -- fr ops …`.
R7. Evidence is durable and shared. Every apply result, every check outcome recorded by `apply`, every proof and every attestation is a plan-journal entry of a new `op` kind. Its body holds `key: value` lines (`op`, `result: done|na|open|failed|attested|proof`, `identity`, `reason`, `phase`, `attested_by`) and never secret material. `fr ops status` folds the latest entry per op, and the latest entry wins. Status itself writes nothing; `apply` (and `fr ops gate`'s op stages) record the closure they observe: an op skipped as DONE or N/A whose latest recorded entry does not already close it gets one `done` or `na` entry, so a second run still writes nothing. A recorded `na` closes an op only while it carries `na_if`. An op whose `check:` is `proof` reads DONE only from a recorded `result: proof` entry. Evidence for a runbook op is written to the journal of the plan named by `--plan`, and a write with no plan is refused. `status` reads every live and archived plan journal for runbook ops.
R8. `fr ops attest <op-id> --note <text>` closes an UNVERIFIABLE op as DONE (attested). It needs a terminal, and records `attested_by: operator` and the note in the entry's body. Status and the PR body always show attested apart from checked. An op that has a `check:` cannot be attested.
R9. An op that only gates a requirement (an optional dependency whose absence silently disables behaviour) declares `disables: <consequence>`. When its check fails it reports OPEN with that consequence, and it is never N/A. `escalate:` is an optional probe: while the op is not DONE, a passing `escalate` turns its line into ESCALATE ("the condition this op guards against is already happening"), and `status` exits 3.
R10. Generic, tool-neutral safety helpers ship as fr subcommands, with no sops/kubectl/forge names in code. `fr ops seal --encrypt '<cmd>' --target <path>` substitutes `{in}` (a 0600 plaintext temp file outside the repo, filled from stdin), `{out}` (an empty 0600 temp file beside the target) and `{target}` (the target's path, as a name only, e.g. for `sops --filename-override`). The command must write ciphertext to `{out}`. fr then renames `{out}` over the target as bytes, but only when the command exited 0 and `{out}` is non-empty. Both temps are removed on every exit path, signals included. On failure the target is byte-identical to before, no plaintext exists in the repo, and the exit is non-zero. `fr ops secret --from '<cmd>' -- <command>` reads a value live and passes it to `<command>` on stdin, never to stdout. `fr ops clip --from '<cmd>'` puts a value on the clipboard. `fr ops scratch --cleanup '<cmd>' -- <command>` runs a command, then its cleanup on any exit.
R11. A post-merge op may declare `ready:`, a probe of a live artifact that only the merged revision produces. Post-merge `apply` refuses an op until its `ready:` passes, and a forge's merged state alone never satisfies it.
R12. Test Plan steps carry an effective gate. A Test Plan item whose text starts with exactly `[devops]` or `[tester]` takes that gate, and the tag is removed from the step text wherever it is shown. Any other leading bracket (a `[ ]`/`[x]` checkbox, a Markdown link) stays text. An untagged step takes `devops` when the run's effective gates (R13) include it, else `tester` when they include that, else it stays ungated, handled exactly as today.
R13. A run's effective gates are its spec's gates plus `devops` whenever its plan has any op, of either phase. That promotion lives in `run_exit`/`Exit`, so the PR labels, the triage ledger, `fr verification`, `deliver` and the baseline all agree; the ledger reads the plans it needs, and the driver never passes a gate by walked rows when ops promoted it (that pass belongs to `fr gate pass`), while a devops gate with no ops passes by rows as today. `devops` is added beside a declared gate; it never replaces it. `deliver` renders a new required `## Manual operations` PR-body section from the plan's ops and recorded evidence, with no live probes. The section lists each op's phase, its last recorded state (or "never checked") and its command, and says the DevOps stage owns them. `deliver` never refuses on OPEN ops.
R14. `devops` holds a PR before merge as well as at close-out. A pre-merge hold predicate (beside `POST_MERGE_GATES`, which keeps its label and pass rules) makes the triage driver's merge path refuse a PR carrying `gate:devops` without `gate:devops-passed`. `fr gate pass --gate devops --run <id>` finds the run (or matches `RunState.branch` to the PR's head ref) and folds only the recorded evidence in the current checkout, never probing live. It refuses while any plan op, or any Test Plan step whose effective gate is `devops`, is not DONE/N/A by recorded evidence or has no `ran`/`n/a` outcome (an `owed` outcome does not close a devops step). When no run resolves (none named, none matching, an unreadable cursor, an unresolvable repo root), a devops pass refuses and names `--run`; `--no-run-evidence` is the explicit escape for a row-only devops gate on a repo with no run, and the pass comment records that it was used. Archived runs are found too. A forge-UI merge is not blocked (labels never were).
R15. `fr ops gate --run <run-id>` is the DevOps stage's engine. It runs on the harness host, refuses in a non-interactive context (the artifact gate's `is_interactive`: no terminal on stdin and stdout, or `CI` set, which is how a delivering agent is kept out), previews by default and acts with `--yes`. Its stages run in order: (1) bring up or reuse the ops workspace `chore/ops-<slug>` on the ops profile, cut from the PR head, then pre-merge status and apply; (2) the merge, through the forge adapter, only after an explicit terminal confirmation naming the PR, its head sha and the pre-merge state, and only when no pre-merge op is open and the PR's required checks pass on that head; (3) `fr isolation verify-merge`, then rebase the ops workspace onto the default branch (it then carries only its own evidence commits), then every `ready:`; (4) post-merge apply and status; (5) each Test Plan step whose effective gate is `devops`, recorded with `fr closeout outcome`; (6) `fr gate pass --gate devops --run <id>` from the ops workspace; (7) when steps whose effective gate is `tester` remain, those steps are listed in the gate-pass comment and the `gate:tester` label is kept; (8) `fr archive --branch <feature>`, then commit, push and open the ops branch as the housekeeping PR. Pre-merge evidence never lands on the PR head. All stage evidence is committed on the ops branch, so the reviewed head stays untouched and the merge's checks stay valid. Each op's confirmation is taken on the host terminal, then the op runs through `fr isolation exec --branch chore/ops-<slug> -- fr ops apply <id> --yes [--yes-mutating]`. An `interactive: true` op runs with a terminal attached. Each stage's completion is a `gate-stage-<n>` decision in the plan journal. A rerun resumes at the first unrecorded stage, and it treats a forge-MERGED PR as stage 2 done even without that decision. It stops at the first failure, naming the stage.
R16. A thin `fr-devops-gate` skill (canonical, plus the OpenCode and Hermes mirrors and install.sh) drives `fr ops gate`. It holds only the judgement: reading OPEN reasons, choosing between attesting and writing a check, and confirming the merge. For a run whose effective gates include `devops`, `fr pickup --run` prints a DevOps brief instead of the close-out brief. That brief says it runs before or after merge, and drops the verify-merge/STOP and archive lines, because the stage owns them. Its one command is `fr ops gate --run <id>`.
R17. Artifact compliance. The journal kind moves 2 → 3 for the `op` entry kind, with a stamp-only migration; `fr journal check` ignores `op` entries. `op` entries are written only by `fr ops`, never through a step record: the record kind's `JournalItem.kind` refuses `op`, and the record kind is unchanged. `ops.yaml` is a new registered artifact kind `ops` (locator `docs/superpowers/plans/*/ops.yaml`, `schema_version` stamp, version 1, a structure validator). `fr plan self-review` refuses a plan carrying ops whose `fr_version` floor predates the release that ships `fr ops`, so an older fr refuses that plan rather than silently ignoring its ops. The profiles kind is unchanged, because per-profile keys are not validated by any reader (`services/legacy.py:31`, `structure.py:550`). The whole `ops` group, `status` included, is gated by the artifact trigger. What each verb writes: `status` nothing; `apply`/`attest` plan-journal entries; `seal` the named target; `gate` the ops branch, the forge merge, and labels and comments.
R18. Documentation: `docs/ops.md` (authoring ops, identities, helpers, the DevOps stage), the fr-goal skill's `deliver`/close-out prose, and any explainer that describes them. frank's adoption (replacing `scripts/ci-budget-ops.sh` with `check`/`apply` fields and carrying them through `/sync-runbook`) is a follow-up frank issue, not this change.
R19. Probes are repo-authored code and run only once trusted. `fr ops trust [--plan <dir>] [--runbook]` shows every probe and command text of the selected ops and, on a terminal confirmation, writes the trusted fingerprint to a per-operator store OUTSIDE the repo (`$XDG_STATE_HOME/fr/ops-trust/<repo-key>/<plan>.json`, default `~/.local/state/fr/ops-trust`, `FR_OPS_TRUST_DIR` overrides). Trust is never read from anything a checkout carries: a journal line records the grant for audit only and is never consulted. The fingerprint covers each op's fields, the `.fr/ops.yaml` settings that affect probes (`identities`, `env_passthrough`, `timeout_seconds`, `runbook`), and the repo's whole committed tree minus only the files fr itself writes as evidence (`docs/superpowers/journals/**/*.md`, `docs/superpowers/runs/**`, `docs/acceptance/matrix.yaml` and its generated reports), never a whole prefix, so any other change, including an indirect dependency no token names, invalidates trust; `trust` lists the files a probe names by path and, on re-trust, the code paths changed since the last grant. Probes refuse to run while any fingerprinted path has uncommitted changes, which no tree hash covers. A file a probe names by path is hashed even when it is one of the excluded evidence files. `fr init scaffold --ops` mounts the store read-only into the ops profile's container, so probes there see the operator's grants and cannot write one. `status`, `apply` and `fr ops gate` run no probe while the current op set's hash differs from the last trusted one: they refuse (exit 2), print what changed since the trusted set, and name `fr ops trust`. Without a terminal, trust cannot be granted. No help text calls a probe read-only; probes are non-mutating by the author's contract, which trust is the operator's acceptance of.

## Design

### A. The op model (`fr/ops/model.py`)

`Op` is a frozen pydantic model, `extra="forbid"`, with R1's fields. `LegacyOp` is the
R2 reader: it accepts frank's keys plus every R1 key, applies R2's defaults, and maps
`commands`/`verify` across. Probes are shell strings, run via `bash -euo pipefail -c`
with the repo root as cwd and the identity's environment.

### B. Carriers (`fr/ops/load.py`)

`load_ops(plan_dir, repo_root, *, runbook=False, ids=()) -> OpSet` reads `ops.yaml`
(`schema_version: 1`, `ops: [...]`), then each phase file's step text. In step text it
looks for fenced YAML code blocks whose first non-blank line is `# manual-operation`,
dedents them, and parses them with fence tracking. A step-text line that merely looks
like a fence mid-prose must not open one; this spec's own first draft hid its
`## Verification` that way. It reads the runbook only for an explicit selection
(R2). Errors name file and line.

### C. Status and apply (`fr/ops/engine.py`)

The engine is pure over an injected `Runner` (which runs a shell string with an env and
returns `(exit, last_line)`), an identity resolver and a journal port, so tests run
no subprocesses. `order(ops)` is a topological sort that refuses cycles and unknown
ids. `status` evaluates `na_if`, then `check` per identity, then `escalate`. `apply`
follows R4. The terminal prompt reads `/dev/tty`.

### D. Evidence (`op` journal kind)

`op` entries are appended through `fr journal`'s engine. Their title is `op <id>:
<result>` and their body is R7's key lines. Journal kind 3 adds `op` to `JournalKind`.
Migration `fr.artifacts.journal_op` is stamp-only, registered in `MIGRATIONS`, and
imported from `fr/artifacts/__init__.py`. `fr/record/model.py`'s `JournalItem.kind`
becomes `JournalKind` minus `op`, so a record can never carry one.

### E. Profiles

`ops: true` is a profile entry key. `fr init scaffold --ops` sets it and writes
`containerEnv.FR_PROFILE`. `_update_profiles_yaml` (`isolation/scaffold.py:704-721`)
merges into the existing entry instead of replacing it. Profiles without `--ops` keep
today's `containerEnv` behaviour (`scaffold.py:544-550`). `fr init` asks about an ops
profile when the repo has ops.

### F. Helpers (`fr/ops/helpers.py`)

`seal` follows R10. `{in}` lives under `$TMPDIR` (refused if that resolves inside the
repo), `{out}` sits beside the target so `os.replace` is atomic, and every
substitution is `shlex.quote`d. Cleanup runs in `finally` and in SIGINT/SIGTERM
handlers. `clip` picks `pbcopy`, `wl-copy`, `xclip` or `clip.exe`, and refuses with
that list when none exists. `docs/ops.md` shows sops (`--filename-override
{target}`), kubectl and forge probes as examples only.

### G. Test Plan gates (`fr/spec.py`)

`Step` gains `gate: Literal["devops","tester"] | None` from the literal tag (R12). The
effective gate is resolved against a run's `Exit` by `fr/ops/testplan.py`
`effective_step_gate`. Every current caller keeps reading `.text`.

### H. Gates, deliver, labels

`Exit` gains the R13 promotion inside `run_exit`. `fr.gates` gains
`PRE_MERGE_HOLD_GATES = frozenset({"devops"})`, used by `batch_merge._approved_and_ready`.
`POST_MERGE_GATES` and its pass and label rules stay as they are, and its docstring
says `devops` also holds pre-merge. `render_pr_body` inserts `## Manual operations`
after `## Post-merge verification owed`, and `REQUIRED_SECTIONS` gains it in that
position. A plan with no ops renders "None.". `fr gate pass` gains `--run` (R14).

### I. The DevOps stage (`fr ops gate`, `fr/ops/gate.py`)

A sequencer in the `batch_closeout` style: it decides the next stage and runs nothing
itself. A `gitseam.Worktree` seam runs git and `fr`, and the forge adapter merges
(`GhClient.pr_merge`; another forge raises `UnsupportedForgeOperation` naming the manual
merge). State is the ops workspace's plan journal plus the forge's PR state (R15).

### J. Candidate scenarios

`tests/scenarios/fr-ops-status-apply.sh`: a fixture plan with one op per state,
including a cycle refusal; `apply --phase` twice, where the second run writes nothing;
the profile refusal; an identity failure that names the identity.
`tests/scenarios/fr-ops-seal.sh`: a failing encrypt command leaves the target
byte-identical and no plaintext anywhere in the repo, and an interrupted seal cleans
up. `tests/scenarios/fr-ops-gate-stage.sh`: a fake forge and a fake ops profile carry
a run through stages 1–8, including a resume after an interrupted stage 4 and a
refusal at stage 6 while a `[devops]` step has no outcome.

## Verification

strategy: candidate
gate: developer
gate: fr-ops-live-first-run=devops
- fr-ops-deliver-section: none — the PR body is rendered by `deliver`, which no installed-CLI scenario runs; unit tests over `render_pr_body` and `deliver`'s required-section check pin it in CI, and this run's own `deliver` renders the section live.
- fr-ops-live-first-run: live — only a released fr inside a real ops profile, against real credentials, a live system and a real PR merge, can prove the DevOps stage end to end; the candidate scenarios (§J) use local, credential-free checks and a fake forge.

## Test Plan

- [devops] Post-merge — operator-driven: with the released fr, scaffold an ops profile (`fr init scaffold --ops`) in a disposable repo (or frank, once its follow-up issue lands), write a plan with one pre-merge and one post-merge op (`check`, `apply`, `ready`, one identity), deliver a PR, and run `fr ops gate --run <id>` through every stage: pre-merge apply, the confirmed merge, `ready`, post-merge apply, the `[devops]` step, the gate pass and the housekeeping PR. Confirm a second `fr ops gate` writes nothing, and that `fr ops status` from a fresh checkout of the merged housekeeping PR shows the recorded evidence. Record the walk for `fr-ops-live-first-run`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-22-fr-ops | `derio-net/super-fr` | `2026-10-22-fr-ops` | — |
