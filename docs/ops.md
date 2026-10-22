# fr ops — manual operations you can check and run

A plan's manual operations used to be prose: "create the deploy key", "rotate the
token after merge". Nothing checked them, nothing ran them, and at delivery someone
worked out by hand which were done and in what order the rest should run. `fr ops`
turns each one into a typed record with a probe that says whether it is done, an
apply that does it, and evidence that survives the session. A run whose plan carries
any op is held by the `devops` gate, and its **DevOps stage** (`fr ops gate`) applies
the ops, merges the PR and closes it out. (Spec:
`docs/superpowers/specs/2026-10-22-fr-ops-design.md`.)

Everything below that names a tool (an encryption tool, a cluster CLI, a forge) is an
example only. fr itself knows none of them.

## Authoring an op

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
| `undo` | A command, or `none: <reason>`. Shown when a mutating op is confirmed or fails. |
| `mutating` | Default `false`. A mutating op's confirmation names its side effects and undo, and needs `--yes-mutating` as well as `--yes` without a terminal. |
| `interactive` | Default `false`. `true` runs the apply with your terminal attached (an authorisation prompt). |
| `side_effects` | Prose list, shown at confirmation. |
| `identities` | Names from `.fr/ops.yaml`; the check and the apply run once per identity. |
| `ready` | Post-merge only: a probe of something only the merged revision produces. Apply refuses the op until it passes. |
| `disables` | The consequence when this optional dependency is missing; such an op is never N/A. |
| `escalate` | A probe: while the op is not done, a passing `escalate` means the thing the op guards against is already happening (ESCALATE). |
| `vacuous_if` | Prose: what the check would look like if it proved nothing (`fr ops status --explain`). |
| `commands`, `verify` | Human prose, kept for the reader. |

An unknown key is refused, naming the key and its file and line.

### Two carriers

`ops.yaml` in the plan folder is canonical. A plan may also carry ops the older way: a
fenced YAML block, inside a step's text, whose first line is `# manual-operation`. fr
reads those through a lenient legacy model: the older convention's keys
(`layer`, `app`, `plan`, `when`, `why_manual`, a `status:` such as `done`) are
accepted, and a key fr does not know is kept as prose with a warning, not refused. An
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

Each `from:` is run live when a check needs it, once per invocation, and its value is
never inlined, logged or recorded. Every identity an op names must pass for DONE, and
the report names the one that failed. A reason line never echoes a response body:
identity and passthrough values are masked (raw, base64 and URL-encoded), and a line
that looks like a body (JSON, or over 200 characters) is replaced by `exit N`.

Every probe runs with stdin closed, a timeout (`timeout_seconds`, a timeout reads
CANNOT-VERIFY), and a minimal environment: `PATH`, `HOME`, `LANG`, `LC_ALL`, `TERM`,
`TMPDIR`, `USER`, the `env_passthrough` variables and, for `check`/`apply` only, the
identity's variables.

## Trust

Probes are code the repository wrote, so none runs until you trust the exact op set:

```bash
fr ops trust --plan docs/superpowers/plans/<plan>
```

It shows every probe and command, the files a probe names by path, and on re-trust what
changed since your last grant; at a terminal it records the grant in YOUR store, outside
the repo (`$XDG_STATE_HOME/fr/ops-trust`, `FR_OPS_TRUST_DIR` overrides). The grant
covers the ops, the probe settings of `.fr/ops.yaml` and the repo's whole committed tree
minus fr's own evidence files, so any other commit invalidates it. Probes refuse to run
while a covered path has uncommitted changes. An ops profile's container sees the store
read-only: it can use your grants, never write one.

## Running ops

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

`status` writes nothing; it exits 0 when everything is DONE or N/A, 1 when anything is
OPEN, UNVERIFIABLE or CANNOT-VERIFY, 3 on an ESCALATE, and 2 on a refusal. `--ready`
runs only the `ready:` probes and exits 0 once every one passes.

`apply` runs in `needs` order, checks each op first (a DONE or N/A op is skipped and its
closure recorded once), confirms each one, stops at the first failure naming the op and
its undo, and re-checks after applying. A second run over a done phase writes nothing.
`attest` closes an UNVERIFIABLE op at a terminal; an op that has a check cannot be
attested. `apply`, `attest` and `seal` run only in an ops profile.

### Evidence

Every apply result, recorded check, proof and attestation is an `op` entry in the plan's
journal: `key: value` lines (`op`, `result`, `identity`, `reason`, `phase`,
`attested_by`), never secret material. The latest entry per op wins. `deliver` renders
a `## Manual operations` PR-body section from the recorded evidence (no live probe) and
never refuses on an OPEN op: the DevOps stage owns them.

## The helpers

Four generic subcommands for the safety bugs hand-written op scripts keep having:

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

`seal` substitutes `{in}` (a 0600 plaintext temp file outside the repo, filled from
stdin), `{out}` (an empty 0600 temp file beside the target) and `{target}` (the target's
name). It replaces the target only when the command exits 0 and `{out}` is non-empty;
otherwise the target is byte-identical to before. Both temp files are removed on every
exit path, signals included.

## The ops profile

Ops need credentials the delivering agent does not have, so they run in an **ops
profile**: a devcontainer profile declared `ops: true`.

```bash
fr init scaffold --ops               # a new ops profile (FR_PROFILE set, trust store mounted read-only)
fr init scaffold --ops --force       # an existing profile gains the key; then fr isolation rebuild
```

`apply`, `attest` and `seal` refuse outside one and print the route:
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

It runs on the harness host at a terminal and refuses a non-interactive context (no
terminal, or `CI` set), which is how a delivering agent is kept out. Run it from a
checkout that holds the run's cursor: before the merge, that is the feature workspace
(`fr isolation status` names it); after the merge, the base clone on the default branch
holds it too. The skill `fr-devops-gate` holds the judgement it needs from you.

| Stage | |
|---|---|
| 1 | Refuse, before anything comes up, a PR that changes the ops profile itself (`.devcontainer/<ops>/**` or `.devcontainer/fr-profiles.yaml` differs from the default branch): that change must merge in its own PR first. Bring up or reuse the ops workspace `chore/ops-<slug>`, cut from exactly the PR head, on the ops profile; grant trust on the host if the op set changed; pre-merge status, then each open op, confirmed on the host terminal and run as `fr isolation exec --branch chore/ops-<slug> -- fr ops apply <id> --yes [--yes-mutating]`. Records the head it cut from. |
| 2 | Merge through the forge, only with no open pre-merge op, the PR's required checks green on that head, the head unchanged since stage 1, and a terminal confirmation naming the PR, its head and the pre-merge state (asked even under `--yes`). A forge fr cannot merge through stops the stage naming the manual merge. |
| 3 | `fr isolation verify-merge`, then rebase the ops branch onto the default branch (it then carries only its own evidence commits), then every `ready:`. |
| 4 | Post-merge status and apply. |
| 5 | Each Test Plan step whose effective gate is `devops`, recorded with `fr closeout outcome` (`ran`, `na`, or `owed`, which stage 6 then refuses; see below). |
| 6 | `fr gate pass --gate devops --run <id>` from the ops workspace: it folds only recorded evidence. |
| 7 | Steps whose gate is `tester` are listed in the gate-pass comment, and `gate:tester` stays. |
| 8 | `fr archive --branch <feature>` (filing the run's out-of-scope findings with `--issues`, as the close-out brief would, or `--no-issues` under `tracking: none`), then open the ops branch as the housekeeping PR. |

### What the stage trusts

The ops workspace is cut from the PR, so anything it carries is written by the PR's
author. The stage therefore keeps its own progress elsewhere and never lets the PR
close anything:

- **Its state** (each stage's completion, and the PR head stage 1 cut from) lives
  host-side, per operator, outside every checkout:
  `$XDG_STATE_HOME/fr/ops-gate/<repo-key>/<run-id>.json`, by default
  `~/.local/state/fr/ops-gate/` (`FR_OPS_GATE_DIR` overrides). A `gate-stage-<n>`
  decision is still committed to the plan journal, as an audit trail no one reads back.
- **An op** closes only by its live status row (DONE or N/A). A closure that comes from
  the journal (an attestation, a proof, a recorded N/A) counts only when its entry was
  added on the ops branch after the recorded head, never one the PR already carries.
- **A Test Plan outcome** counts the same way: one the PR carries is asked for again.

Each stage is committed and pushed to the ops branch (fr owns it, so the push is forced
after the stage-3 rebase), and only then marked done; a failed push leaves the stage to
retry. A rerun resumes at the first stage the host state does not record, and a PR the
forge reports MERGED counts as stage 2 done. Stage 2 merges only the recorded head, and
stage 3 checks the merged PR's head is that one. The first failure stops the run, naming
the stage (exit 1; a refusal such as a moved head, a changed ops profile or an untrusted
op set exits 2). Pre-merge evidence never lands on the PR head, so the reviewed head and
its checks stay valid.

### When a devops step is owed

An `owed` answer at stage 5 is recorded, but it does not close the step, so stage 6's
gate pass refuses and prints the command to close it. Walk the step, then record it in
the ops workspace and re-run the stage:

```bash
fr isolation exec --branch chore/ops-<slug> -- \
  fr closeout outcome --run <run-id> --step <n> --ran --evidence "<what it showed>"
fr ops gate --run <run-id> --yes
```

A later `ran` or `n/a` outcome supersedes the owed one (`fr closeout outcome` records
over an owed step without a flag; over any other it needs `--supersede`), and so does
resolving the owed entry `fixed` with `fr journal resolve`.

### Test Plan tags

A Test Plan step that starts with `[devops]` or `[tester]` belongs to that gate. An
untagged step belongs to `devops` when the run's gates include it, else to `tester`
when they include that.
