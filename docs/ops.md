---
title: "fr ops: manual operations you can check and run"
tldr: |
  A plan's manual operations become typed records with a probe that says whether each is done, an apply that does it, and evidence that survives the session.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/ops/**
  - packages/fr/src/fr/commands/ops_cmd.py
reviewed: 2026-11-13 placement emitted paths fix, run/ops/pickup/verification readers now resolve a run's emitted spec and plan below the artifact root; nothing this page describes changed
---

# fr ops — manual operations you can check and run

A plan's manual operations used to be prose: "create the deploy key", "rotate the
token after merge". Nothing checked them and nothing ran them. At delivery, someone
found out by hand which ones were done, and in what order the others should run.

`fr ops` turns each one into a typed record. The record has a probe that says whether
the operation is done, an apply that does it, and evidence that survives the session.
The `devops` gate holds a run whose plan carries any op. The run's **DevOps stage**
(`fr ops gate`) applies the ops, merges the PR and closes it out. (Spec:
`docs/superpowers/specs/2026-10-22-fr-ops-design.md`.)

Everything below that names a tool (an encryption tool, a cluster CLI, a forge) is an
example only. fr itself knows none of them.

## Write an op

### The fields

```yaml
# docs/superpowers/plans/<plan>/ops.yaml
schema_version: 1
ops:
  - id: deploy-key                      # required
    summary: Create the deploy key the CI job pulls with   # required
    phase: pre-merge                    # required: pre-merge | post-merge
    check: 'forge-cli api repos/acme/app/keys --jq ".[].title" | grep -qx ci-deploy'
    apply: './scripts/make-deploy-key.sh'
    identities: [admin]
    mutating: true
    side_effects: [adds a deploy key to acme/app]
    undo: 'forge-cli api -X DELETE repos/acme/app/keys/$(…)'
  - id: rollout-ready
    summary: Restart the worker on the new image
    phase: post-merge
    needs: [deploy-key]
    ready: 'cluster-cli get deploy/worker -o jsonpath="{.spec.template.spec.containers[0].image}" | grep -q ":v2"'
    check: 'cluster-cli rollout status deploy/worker --timeout=5s'
    apply: 'cluster-cli rollout restart deploy/worker'
```

| Field | Meaning |
|---|---|
| `id`, `summary`, `phase` | Required. `phase` is `pre-merge` or `post-merge`. |
| `needs` | Op ids that must be done first. A cycle or an unknown id is refused before anything runs. |
| `check` | A probe: exit 0 is DONE; any other exit is OPEN, its last stdout line the reason. The reserved value `proof` means "done only once a recorded proof says so". |
| `na_if` | A probe: exit 0 means the op does not apply here (N/A). |
| `apply` | Idempotent automation. Absent for an op only a human can do in a UI. |
| `undo` | A command, or the mapping `{none: <reason>}`. Shown when a mutating op is confirmed or fails. |
| `mutating` | Default `false`. A mutating op's confirmation names its side effects and undo, and needs `--yes-mutating` as well as `--yes` without a terminal. |
| `interactive` | Default `false`. `true` runs the apply with your terminal attached (an authorisation prompt). |
| `side_effects` | Prose list, shown at confirmation. |
| `identities` | Names from `.fr/ops.yaml`; the check and the apply run once per identity. |
| `ready` | Post-merge only: a probe of something only the merged revision produces. Apply refuses the op until it passes. |
| `disables` | The consequence when this optional dependency is missing; such an op is never N/A. |
| `escalate` | A probe: while the op is not done, a passing `escalate` means the thing the op guards against is already happening (ESCALATE). |
| `vacuous_if` | Prose: what the check would look like if it proved nothing (`fr ops status --explain`). |
| `commands`, `verify` | Human prose, kept for the reader. |

An unknown key is not accepted. The error names the key and its file and line.

### Two carriers

`ops.yaml` in the plan folder is canonical. A plan may also carry ops the older way: a
fenced YAML block, inside a step's text, whose first line is `# manual-operation`. A
lenient legacy model reads those. It accepts the keys of the older convention
(`layer`, `app`, `plan`, `when`, `why_manual`, a `status:` such as `done`). It keeps a
key that fr does not know as prose, with a warning, and does not reject it. An
op id defined in both carriers is an error.

### The repo runbook

`.fr/ops.yaml` may name a repo-wide runbook (`runbook: <path>`) in the same legacy
shape. Its ops are read only into an explicit selection (`--runbook`, or an id a plan
op names in `needs`), never into a plan's default set.

## Identities and the probe environment

```yaml
# .fr/ops.yaml
identities:
  admin:
    env:
      FORGE_TOKEN: {from: 'secret-manager read forge/admin-token'}
env_passthrough: [KUBECONFIG]
timeout_seconds: 60
```

Each `from:` runs live when a check needs it, once per invocation. Its value is
never inlined, logged or recorded. Every identity that an op names must pass for DONE, and
the report names the one that failed. A reason line never echoes a response body.
Identity and passthrough values are masked (raw, base64 and URL-encoded). A line
that looks like a body (JSON, or over 200 characters) is replaced by `exit N`.

Every probe runs with stdin closed and with a timeout (`timeout_seconds`; a timeout reads
CANNOT-VERIFY). It also runs with a minimal environment:

- `PATH`, `HOME`, `LANG`, `LC_ALL`, `TERM`, `TMPDIR`, `USER`;
- the `env_passthrough` variables;
- for `check`/`apply` only, the identity's variables.

## Trust

Probes are code that the repository wrote. So no probe runs until you trust the exact op set:

```bash
fr ops trust --plan docs/superpowers/plans/<plan>
```

It shows every probe and command, and the files that a probe names by path. On re-trust,
it also shows what changed since your last grant. At a terminal, it records the grant in
YOUR store, outside the repo (`$XDG_STATE_HOME/fr/ops-trust`, `FR_OPS_TRUST_DIR` overrides).

The grant covers the ops, the probe settings of `.fr/ops.yaml` and the repo's whole
committed tree, except fr's own evidence files. So any other commit makes it invalid. Probes
do not run while a covered path has uncommitted changes. An ops profile's container sees
the store read-only: it can use your grants, never write one.

## Run ops

```bash
fr ops status [--plan <dir>] [--phase pre-merge|post-merge] [<op>] [--json] [--explain] [--ready]
fr ops apply <op> | --phase pre-merge|post-merge [--yes] [--yes-mutating]
fr ops attest <op> --note "<what you did and saw>"
```

| Status | Meaning |
|---|---|
| DONE (checked) / (attested) / (legacy) / (proof) | Closed, and how. Attested is always shown apart from checked. |
| OPEN | The check failed; its reason follows. |
| N/A | `na_if` passed. |
| UNVERIFIABLE | No check, and not closed. |
| CANNOT-VERIFY | The check could not run (exit 127, an unreadable credential, a timeout). |
| ESCALATE | Not done, and its `escalate` probe passed. |

`status` writes nothing. It exits 0 when everything is DONE or N/A, and 1 when anything is
OPEN, UNVERIFIABLE or CANNOT-VERIFY. It exits 3 on an ESCALATE, and 2 on a refusal. `--ready`
runs only the `ready:` probes and exits 0 once every one passes.

`apply` runs in `needs` order and checks each op first. It skips a DONE or N/A op, and
records its closure once. It confirms each op. It stops at the first failure, and names the
op and its undo. It checks again after the apply. A second run over a done phase writes nothing.

`attest` closes an UNVERIFIABLE op at a terminal. An op that has a check cannot be
attested. `apply`, `attest` and `seal` run only in an ops profile.

### Evidence

Every apply result, recorded check, proof and attestation is an `op` entry in the plan's
journal. The entry has `key: value` lines (`op`, `result`, `identity`, `reason`, `phase`,
`attested_by`), never secret material. The latest entry per op wins. `deliver` renders
a `## Manual operations` PR-body section from the recorded evidence (no live probe). It
never stops on an OPEN op, because the DevOps stage owns them.

## The helpers

Four generic subcommands for the safety bugs that hand-written op scripts often have:

```bash
# Encrypt stdin into a file without ever leaving plaintext behind
printf '%s' "$VALUE" | fr ops seal --target secrets/app.enc.yaml \
  --encrypt 'encryption-tool --encrypt --filename-override {target} {in} > {out}'
# Pass a secret to a command on stdin, never to stdout or argv
fr ops secret --from 'secret-manager read app/token' -- cluster-cli create secret generic app --from-file=token=/dev/stdin
# Put a value on the clipboard (pbcopy, wl-copy, xclip or clip.exe)
fr ops clip --from 'secret-manager read app/token'
# Run a command, then its cleanup on success, failure, Ctrl-C or SIGTERM
fr ops scratch --cleanup 'forge-cli repo delete acme/scratch --yes' -- ./scripts/try-scratch.sh
```

`seal` substitutes these values:

- `{in}`: a 0600 plaintext temp file outside the repo, filled from stdin;
- `{out}`: an empty 0600 temp file beside the target;
- `{target}`: the target's full path.

Each substitution is shell-quoted. It replaces the target only when the command exits
0 and `{out}` is non-empty. Otherwise the target is byte-identical to before. Both temp files are removed on every
exit path, signals included.

## The ops profile

Ops need credentials that the agent who delivers the work does not have. So they run in
an **ops profile**: a devcontainer profile declared `ops: true`.

```bash
fr init scaffold --profile <name> --purpose "<line>" --ops           # a new ops profile (FR_PROFILE set, trust store mounted read-only)
fr init scaffold --profile <name> --purpose "<line>" --ops --force   # an existing profile gains the key; then fr isolation rebuild
```

`apply`, `attest` and `seal` do not run outside one, and they print the route:
`fr isolation up --profile <ops> --branch chore/ops-<slug> --base <ref>`, then
`fr isolation exec --branch chore/ops-<slug> -- fr ops …`.

## The DevOps stage

A run whose plan carries any op (or whose spec declares `gate: devops`) is held by
`gate:devops` before merge as well as after it. `fr pickup --run <id>` prints a DevOps
brief for it, and its one command is:

```bash
fr ops gate --run <run-id>          # preview the 8 stages
fr ops gate --run <run-id> --yes    # act
fr ops gate --run <run-id> --yes --profile <ops-profile> --method squash
```

`--profile` names the ops profile when the repo declares more than one (`ops: true`);
`--method` picks the merge method (`merge`, `squash` or `rebase`; default: the repo's).

It runs on the harness host at a terminal. It does not run in a non-interactive context (no
terminal, or `CI` set). That keeps out the agent that delivered the work. Run it from a
checkout that holds the run's cursor. Before the merge, that is the feature workspace
(`fr isolation status` names it). After the merge, the base clone on the default branch
holds it too.

The skill `fr-devops-gate` holds the judgement it needs from you.

| Stage | |
|---|---|
| 1 | Before anything comes up, stop on a PR that changes the ops profile itself. That is a PR whose own diff, from the merge base, touches `.devcontainer/<ops>/**` or `.devcontainer/fr-profiles.yaml`. That change must merge in its own PR first. Bring up or reuse the ops workspace `chore/ops-<slug>` on the ops profile. Cut it from exactly the PR head, or from the default branch's tip once the PR has merged (a merged head can never be rebased). Stop on a cut whose profile is not the same as the default branch's, because the workspace runs the cut's copy with the ops credentials. Rebase an open PR onto the default branch; a merged PR's stale workspace is cut again. Grant trust on the host if the op set changed. Then show the pre-merge status, then each open op. Each op is confirmed on the host terminal and run as `fr isolation exec --branch chore/ops-<slug> -- fr ops apply <id> --yes [--yes-mutating]`. Records the head it cut from. |
| 2 | Merge through the forge, only when all of these are true: no pre-merge op is open, and the PR's required checks are green on that head. The head is unchanged since stage 1. A terminal confirmation names the PR, its head and the pre-merge state (asked even under `--yes`). If fr cannot merge through the forge, the stage stops and names the manual merge. |
| 3 | `fr isolation verify-merge`. Then rebase the ops branch onto the default branch (it then carries only its own evidence commits). Then every `ready:`. |
| 4 | Post-merge status and apply. |
| 5 | Each Test Plan step whose effective gate is `devops`. A pointed step's probe runs (see Test Plan probes), and the stage asks about the others. Each answer is recorded with `fr closeout outcome`: `ran`, `na`, or `owed` (stage 6 then stops on it; see below). |
| 6 | `fr gate pass --gate devops --run <id>` from the ops workspace. It folds only recorded evidence. |
| 7 | Steps whose gate is `tester` are listed in the gate-pass comment, and `gate:tester` stays. |
| 8 | `fr archive --branch <feature>`, with `--issues` to file the run's out-of-scope findings, as the close-out brief would. Under `tracking: none`, use `--no-issues`. Then open the ops branch as the housekeeping PR. |

### What the stage trusts

The ops workspace is cut from the PR, so the PR's author wrote anything that it carries.
So the stage keeps its own progress in a different place, and never lets the PR
close anything:

- **Its state** (each stage's completion, and the PR head stage 1 cut from) is
  host-side, per operator, outside every checkout. The path is
  `$XDG_STATE_HOME/fr/ops-gate/<repo-key>/<run-id>.json`, by default
  `~/.local/state/fr/ops-gate/` (`FR_OPS_GATE_DIR` overrides). A `gate-stage-<n>`
  decision is still committed to the plan journal, as an audit trail no one reads back.
- **An op** closes only by its live status row (DONE or N/A). A closure can come from
  the journal (an attestation, a proof, a recorded N/A). It counts only when its entry was
  added on the ops branch after the recorded head. A closure that the PR already carries
  never counts.
- **A Test Plan outcome** counts the same way: one the PR carries is asked for again.

- **The default branch** comes from the forge's repo metadata, never from the PR's base ref.
  The stage cross-checks it with the base clone's `origin/HEAD`, and stops when they disagree.
  It stops on a PR based on any other branch. It also stops on one that adds or changes files
  under `docs/superpowers/implemented/journals/`.
- **A PR-carried journal that cannot be parsed** is a refusal, never an empty exclusion.

Before the merge, each stage commits on the ops branch LOCALLY only. Until stage 3
rebases it onto the default branch, the branch holds the unmerged PR head. That head must
never reach a branch of the base repo (an `on: push` workflow there would run it with the
repo's secrets). From stage 3 on, each stage is committed and pushed, and only then marked
done. A failed push leaves the stage to retry.

The first push makes the branch, and stops if the branch already exists. Every later push
is leased on the sha that fr last pushed (`--force-with-lease`), recorded in the host state.
A rerun resumes at the first stage that the host state does not record. A PR that the forge
reports MERGED counts as stage 2 done. Stage 2 merges only the recorded head, and stage 3
checks that the merged PR's head is that one.

The first failure stops the run, and names the stage (exit 1). This includes an op set that
is not trusted when the stage asks. A refusal such as a moved head or a changed ops profile
exits 2. Pre-merge evidence never lands on the PR head, so the reviewed head and its checks
stay valid.

### When a devops step is owed

An `owed` answer at stage 5 is recorded, but it does not close the step. So stage 6's
gate pass stops, and prints the command to close it. Walk the step, then record it in
the ops workspace and re-run the stage:

```bash
fr isolation exec --branch chore/ops-<slug> -- \
  fr closeout outcome --run <run-id> --step <n> --ran --evidence "<what it showed>" --supersede
fr ops gate --run <run-id> --yes
```

A later `ran` or `n/a` outcome supersedes the owed one. So does a `fixed` resolution of the
owed entry with `fr journal resolve`. `fr closeout outcome` records over an outcome that is
already there, owed included, only with `--supersede`. An owed step may already be filed as an
`fr:owed` issue, so it is never overwritten silently. Stage 6 prints the command with the
flag already on it.

### Test Plan probes

A devops-gated run's Test Plan steps that run commands should be ops. Then stage 5 can
run their checks, and does not have to ask.

- **The pointer.** A step may lead its text with `(op: <id>)`, after the optional gate
  tag: `- [devops] (op: guest-verify) Run the verify playbook`. `fr plan self-review`
  errors when the id names no op of the plan.
- **The gap.** A run has an ops gap when all of these are true: its gates include `devops`,
  and its plan declares no op and no `none:`. Also, its devops steps carry commands. These are
  fenced lines, or inline spans that look like an operations command. This test is a
  heuristic, so a prose span can be a false positive. `fr plan self-review` and the spec
  review warn about the gap.

  `fr ops gate` stage 1 stops on it (exit 2, nothing brought up
  or recorded). The stage reads the PR head, or the default branch's tip once merged. Fix the
  gap on the PR branch while the PR is open. After it has merged, land the fix on the
  default branch through a follow-up PR (stage 1 then reads the default branch's tip).
- **`fr ops stub [--plan <dir>] [--yes]`.** For each devops command step without a
  pointer, it proposes the op `step-<n>` and the `(op: step-<n>)` pointer. The op has
  `phase: post-merge`, `apply:` the step's commands joined with ` && `, and `mutating: true`.
  Without `--yes` it prints both and writes nothing. With `--yes` it writes `ops.yaml`
  (stamped `schema_version: 2`) and the spec.

  It stops, and writes nothing, on a declared id, a
  `none:` file or a plan with no spec. Each stub's `check:` is the sentinel `TODO`.
  `fr ops status` reports it UNVERIFIABLE ("write a real probe"), and self-review shows an
  error on it until you replace it.
- **`none: <reason>`.** When the steps have no ops on purpose, say so in `ops.yaml`
  (`schema_version: 2`, `none: <reason>`, no `ops:`). It is not accepted beside `ops:` or a
  `# manual-operation` step block. A `none:` plan does not promote the run to the
  `devops` gate.
- **Stage 5.** For a pointed step it runs `fr ops status <id> --json` in the ops workspace
  (after the trust check). A check that passes records `ran` with `<op id>: check passed` and
  the evidence lines, with no question. An OPEN, UNVERIFIABLE, CANNOT-VERIFY or ESCALATE
  op shows its reason and asks `retry`, `na <reason>` or `owed <why>`. An N/A op, or a
  DONE that ran no check, asks the usual `ran | na | owed`.

  Answers take an optional `:`
  or `-` separator (`ran: x`). If an answer does not match, the stage asks again. Three
  such answers in a row fail the stage.
- **Evidence bound.** The screen shows the last 40 lines of a probe that passes (each at most
  200 characters). Only the last three **status lines**, 300 characters in all, are
  recorded. The rule fails closed:
  - a status line holds only letters, digits, spaces and `, . ; ( ) / % + # _ * -`
    (no colon, quote, `=` or angle bracket);
  - a line that starts with `- ` or `* ` (a list item) is dropped;
  - a line with a word of 20 or more characters is dropped;
  - a line with a word of 12 or more that mixes letters and digits (token-shaped) is dropped;
  - output with a `{`, `}`, `[` or `]` anywhere records none of its lines.

  So a JSON or YAML body, an env assignment, a URL, a JWT or a key is never committed. The
  evidence reads `no output` instead. The mask hides known secret values only. It does not
  filter hostnames, IPs or other text that identifies a system. So end a probe
  with a plain one-line summary (`converged 3 of 3`) and keep it free of them.

### Test Plan tags

A Test Plan step that starts with `[devops]` or `[tester]` belongs to that gate. An
untagged step belongs to `devops` when the run's gates include it, else to `tester`
when they include that.
