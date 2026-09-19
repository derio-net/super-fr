# Runbook — v2 demo recording (single arm, GitLab-backed)

Adapts the corrected `version-1/experiment/bc88/runbook.md` method. Two things
differ, and both matter:

- **One arm, not two.** This is a demo recording, not a comparison. The
  comparison evidence is reused as-is from `version-1/experiment/bc88/`. So
  there is no treatment to balance — but the clean room stays, because it is
  what makes the run reproducible and measurable.
- **GitLab, not GitHub.** Every auth, identity and host assumption from bc88
  has a GitLab counterpart, and they are not interchangeable.

## Identities are redacted — set them locally

Per `.claude/rules/third-party-privacy.md`, the employer's GitLab host, group,
project and username are third-party and never enter this repo. This runbook
carries the **shape**; the operator supplies the identity from a file that lives
**outside the repo**, alongside the recording assets:

```bash
# ~/.config/fr-demo.env  — NOT in this repo, never committed
export GITLAB_HOST=...          # self-hosted GitLab instance
export DEMO_NS=...              # the operator's own namespace on it
export DEMO_REPO=...            # the training project's name
export WORK_ROOT=...            # the path whose includeIf gives the WORK identity
export RUN_ROOT=$WORK_ROOT/runs/v2-demo
export BASE_IMAGE=...          # devcontainer base to pre-pull (see "the waits" below)
```

Source it before every command below. Nothing in this file should ever be
edited to contain a real value.

## Unblocked

[#486](https://github.com/derio-net/super-fr/issues/486) is fixed (PR #487) and
re-verified live on 2026-09-19: with `backend: gitlab` declared and no
`GITLAB_HOST` exported, the contents reads all pass and `file_exists` raises on
an unreachable host rather than reporting absence.

## The recording starts pristine — `fr-init` is IN it

The run is end-to-end from a repo with **no `.devcontainer`**, because that is
the state the listener's own repo is in. So two things that read like setup are
actually the opening beats, and must NOT be done beforehand:

- `fr-init` — the scan, the interview, the scaffold, and the container build.
- `fr init scaffold --backend gitlab` — which both installs a versioned `glab`
  in the container and records the key `detect_backend` reads. That key's
  absence is what made fr silently assume GitHub before #487, so the interview
  asking for it is the moment the GitLab story becomes visible.

**The waits get shown as waits.** A devcontainer build and a first Maven resolve
are minutes. Do not pre-build and cut to a warm container — that hides the
biggest cost of adoption. Do not play them in full either. Compress hard and
**label the compression on screen**. Pre-pulling *base image layers* is fine and
needs no label; we are not demonstrating a registry's bandwidth.

## Subject

| | |
|---|---|
| Repo | `$DEMO_REPO` — an internal Java training project, not product code |
| Remote | `origin` → the operator's own fork; `upstream` → the team's project, push `DISABLED` |
| Default branch | `master` (**not** `main`) |
| Stack | Java 17 + Maven |
| Invocation | `/fr-goal <text>` — brief passed inline, **no tracker issue** |
| Budget | 15–25 min, per the bc88 benchmark |

The brief is composed from two of its README exercises — fix three
deliberately-failing tests, and write unit tests for a class that has none.
Together they are bounded, touch more than one surface, and contain a
**built-in failure to recover from**, which is the beat the talk is built on.
The text itself names third-party classes, so it lives in the local env file,
not here.

`/fr-goal` produces a spec, a plan and a **merge request** — it does not create
or label tracker issues, which is the separate `fr apply --to <runner>` dispatch
path. So this run proves the MR half of GitLab live; the issue-tracking half was
already proven by #487's own live walk.

## Fixed since bc88 — the GitLab-specific additions

| bc88 (GitHub) | Here (GitLab) |
|---|---|
| `~/.config/gh` copied into each cfg dir | `~/.config/glab-cli` copied in, `glab auth status` **and** a real read asserted inside |
| — | `GITLAB_HOST` exported — `fr.glab._run_glab` passes no `--hostname`, so without it every call hits gitlab.com (#486) |
| — | `.devcontainer/fr-profiles.yaml` declares `backend: gitlab` — a self-hosted host otherwise resolves to `"github"` |
| `RUN_ROOT` under the personal path for the OSS identity | `RUN_ROOT` under `$WORK_ROOT` for the **work** identity |
| `git@github.com:` clone, dry-run push verified | ssh clone, dry-run push verified against the **fork** |

### The identity rule inverts here — do not copy bc88's fix blindly

bc88's bug was the *work* identity landing on a public open-source commit, fixed
by moving `RUN_ROOT` under the personal path. **Here the opposite is correct.**
These commits go to the employer's GitLab, so the work identity is the right
one, and `~/.gitconfig`'s `includeIf` for `$WORK_ROOT` supplies it. Putting
`RUN_ROOT` under the personal path would be the bug this time.

Assert it rather than trusting the path:

```bash
git -C "$CLONE" config user.email    # must be the work address
```

## Preflight — assert, never assume

Every line below failed silently in a previous run. That is why each is an
assertion and not a step.

```bash
source ~/.config/fr-demo.env
export CFG=$RUN_ROOT/cfg DATA=$RUN_ROOT/data
mkdir -p "$CFG" "$DATA"
CLONE=$RUN_ROOT/$DEMO_REPO

cp -R ~/.config/glab-cli "$CFG"/glab-cli          # glab reads $XDG_CONFIG_HOME

# 1. glab authenticated INSIDE the clean room, and able to actually read
XDG_CONFIG_HOME=$CFG glab auth status
XDG_CONFIG_HOME=$CFG glab api "projects/${DEMO_NS}%2F${DEMO_REPO}" >/dev/null

# 2. the fr skills really reached the config dir (a previous arm's copy silently didn't)
test -f "$CFG"/opencode/skills/fr-goal/SKILL.md || { echo "FAIL: fr-goal skill absent"; exit 1; }

# 3. identity is the WORK one
git -C "$CLONE" config user.email

# 4. push path is the fork, and upstream is closed
git -C "$CLONE" push --dry-run origin master
git -C "$CLONE" push --dry-run upstream master && \
  { echo "FAIL: upstream is pushable"; exit 1; }

# 5. the repo is PRISTINE — fr-init must have nothing to find
test ! -e "$CLONE/.devcontainer" || { echo "FAIL: .devcontainer exists; fr-init is in the recording"; exit 1; }
test -z "$(git -C "$CLONE" status --porcelain)" || { echo "FAIL: dirty tree"; exit 1; }

# 6. base image layers pre-pulled, so the build shows fr's work and not a download
docker image inspect "$BASE_IMAGE" >/dev/null 2>&1 || docker pull "$BASE_IMAGE"
```

## Record

```bash
XDG_CONFIG_HOME=$CFG XDG_DATA_HOME=$DATA GITLAB_HOST=$GITLAB_HOST \
  asciinema rec --idle-time-limit 2 --title "fr-goal demo" \
    -c "opencode --auto $CLONE" \
    $RUN_ROOT/demo.cast
```

**Harness: `opencode --auto`, `github-copilot/gpt-5.6-terra`, default effort**
— confirmed 2026-09-19, same as bc88. The audience's own tooling is
Copilot-based, and OpenCode's `/fr-goal` ran **0 subagents in 17 min** where
Claude ran 14 in 56 — decisive for the budget.

Two consequences of that choice, from `fr harness parity`:

- `subagent-dispatch / opencode: absent` — **the declaration is disputed
  ([#493](https://github.com/derio-net/super-fr/issues/493)); the shipped
  behaviour is not.** With 4.5.x, phases run inline, so phase executors and
  model tiers never appear on camera — and that is *why* the run fits the
  budget (bc88 arm G: 0 subagents, 17 min). OpenCode does in fact have a
  dispatch primitive: the #429 experiment's arm A, also `opencode --auto`,
  dispatched 13 `@general` subagents at $7.59 against ~$1 inline. If #493
  flips the default before recording, re-time the run before committing to it.
- `operator-gate / opencode: advisory` — no operator-question tool exists on
  OpenCode, so nothing mechanically enforces the batched-Q&A gate. It fired
  correctly in bc88's arm G, and failed to fire at all in the earlier arm A.
  **This is the highest-risk moment in the take.**

## Measure

```bash
sqlite3 -readonly "file:$DATA/opencode/opencode.db?mode=ro" "
SELECT COUNT(*) sessions, SUM(parent_id IS NOT NULL) subagents,
       ROUND(SUM(cost),2) cost, SUM(tokens_input) tin, SUM(tokens_output) tout,
       SUM(tokens_cache_read) cache FROM session;"
```

**Cast length is not runtime.** `--idle-time-limit` never engages against a TUI
that repaints roughly once a second, so the cast spans the whole session
regardless. True wall time comes from the db's session spans. Established the
hard way in v1; do not re-derive it from the cast.

## Annotation timings — capture during the run, not after

The deck pauses the player at each angle moment, so each needs an offset. Note
them live; recovering them afterwards means re-watching the whole cast.

| Moment | Angle |
|---|---|
| `fr-init` scans and interviews | the contract (1 of 2) |
| profile scaffolded, `backend: gitlab` declared | Security · Extensibility |
| container build (**compress, label it**) | — |
| `fr isolation up` → worktree + container | Security |
| batched Q&A asked, turn ends | the contract (2 of 2) |
| spec written | Continuity |
| acceptance rows presented | Quality |
| plan folder + `_meta.yaml` | Continuity |
| run cursor advances | Continuity |
| a check FAILS | **Quality — the beat the talk is built on** |
| journal finding recorded | Quality |
| MR opened | Continuity |

## Assets never enter this repo

`demo.cast`, any render and every still stay under `$RUN_ROOT`. super-fr is a
Skill cloned onto every consumer's machine, so a committed binary inflates every
install permanently and needs a history rewrite to remove. The deck resolves
them through a manifest of paths plus checksums and **fails loudly** when one is
missing, so a checkout without the private assets cannot render a silent
half-deck.

**The same applies to the cast's contents.** A terminal recording of a run
against a third-party GitLab shows its hostname, namespace and project in
prompts, git output and MR URLs. That is a further reason the rendered deck is
internal-only, and a reason the cast itself must never be committed even if the
binary-size argument were somehow answered.

## Take acceptance — run this BEFORE tearing anything down

Not a post-run curiosity: a take that fails any of these is discarded and
re-recorded. The evidence is perishable — it lives in the cast, the db and the
cursor — and the riskiest item (`operator-gate`) is advisory on this harness, so
it can silently not have happened.

```bash
# 1. a human answered the gate; the agent did not clear its own
grep -n 'answered_by' "$CLONE"/docs/superpowers/runs/*.yaml   # expect: operator

# 2. the artifacts the pipeline claims to produce actually exist
ls "$CLONE"/docs/superpowers/specs/ "$CLONE"/docs/superpowers/plans/

# 3. findings were resolved, not merely recorded
cd "$CLONE" && uv run fr journal check --scope plan --slug <slug>
```

By eye, from the cast itself:

- [ ] `fr-init` interviewed — gate 1 of 2 fired
- [ ] `/fr-goal` asked its batch and **ended the turn** — gate 2 of 2 fired
- [ ] a check genuinely **failed and was recovered** (this is why those two
      exercises were chosen; a clean run is a weaker take, not a luckier one)
- [ ] the merge request exists on the fork
- [ ] annotation offsets noted live, not reconstructed

This run is also the **first live exercise of the GitLab path end to end**, so
it doubles as verification for #486. Anything it surfaces gets an issue — with
identities redacted at capture time, the way #486 itself was written.
