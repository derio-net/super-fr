# Runbook — v2 demo recording (single arm, GitLab-backed)

Adapts the corrected `version-1/experiment/bc88/runbook.md` method. Two things
differ, and both matter:

- **One arm, not two.** This is a demo recording, not a comparison. The
  comparison evidence is reused as-is from `version-1/experiment/bc88/`. So
  there is no treatment to balance — but the clean room stays, because it is
  what makes the run reproducible and measurable.
- **GitLab, not GitHub.** Every auth, identity and host assumption from bc88
  has a GitLab counterpart, and they are not interchangeable.

## BLOCKED

Do not record until [#486](https://github.com/derio-net/super-fr/issues/486) is
fixed and live-verified. GitLab is the only forge at the audience's company; a
run that silently fell back to GitHub would demonstrate nothing to them.

## Subject

| | |
|---|---|
| Repo | `agentic-playground` (internal AI102 course material) |
| Remote | `origin` → operator's fork; `upstream` → team project, push `DISABLED` |
| Default branch | `master` (**not** `main`) |
| Stack | Java 17 + Maven |
| Issue | composed from README tasks 2 + 4 (optionally 3) |
| Budget | 15–25 min, per the bc88 benchmark |

## Fixed since bc88 — the GitLab-specific additions

| bc88 (GitHub) | Here (GitLab) |
|---|---|
| `~/.config/gh` copied into each cfg dir | `~/.config/glab-cli` copied in, `glab auth status` **and** a real read asserted inside |
| — | `GITLAB_HOST` exported — `fr.glab._run_glab` passes no `--hostname`, so without it every call hits gitlab.com (#486) |
| — | `.devcontainer/fr-profiles.yaml` declares `backend: gitlab` — a self-hosted host otherwise resolves to `"github"` |
| `RUN_ROOT` under `~/Docs/projects` for the OSS identity | `RUN_ROOT` under `~/gebit/**` for the **work** identity |
| `git@github.com:` clone, dry-run push verified | `git@gitlab.local...` clone, dry-run push verified against the **fork** |

### The identity rule inverts here — do not copy bc88's fix blindly

bc88's bug was the *work* identity landing on a public open-source commit,
fixed by moving `RUN_ROOT` under `~/Docs/projects`. **Here the opposite is
correct.** These commits go to the company's GitLab, so the work identity is
the right one, and `~/.gitconfig`'s `includeIf "gitdir:~/gebit/**"` supplies it.
Putting `RUN_ROOT` under `~/Docs/projects` would be the bug this time.

Assert it rather than trusting the path:

```bash
git -C "$CLONE" config user.email    # must be the gebit address
```

## Preflight — assert, never assume

Every line below failed silently in a previous run. That is why each is an
assertion and not a step.

```bash
export RUN_ROOT=~/gebit/runs/v2-demo
export GITLAB_HOST=gitlab.local.gebit.de
export CFG=$RUN_ROOT/cfg  DATA=$RUN_ROOT/data
mkdir -p "$CFG" "$DATA"

cp -R ~/.config/glab-cli "$CFG"/glab-cli          # glab reads $XDG_CONFIG_HOME

# 1. glab authenticated INSIDE the clean room, and able to actually read
XDG_CONFIG_HOME=$CFG glab auth status
XDG_CONFIG_HOME=$CFG glab api "projects/IDermitzakis%2Fagentic-playground" >/dev/null

# 2. the fr skills really reached the config dir (cfg-A's copy silently didn't)
test -f "$CFG"/opencode/skills/fr-goal/SKILL.md || { echo "FAIL: fr-goal skill absent"; exit 1; }

# 3. identity is the WORK one
git -C "$RUN_ROOT/agentic-playground" config user.email

# 4. push path is the fork, and upstream is closed
git -C "$RUN_ROOT/agentic-playground" push --dry-run origin master
git -C "$RUN_ROOT/agentic-playground" push --dry-run upstream master && \
  { echo "FAIL: upstream is pushable"; exit 1; }

# 5. backend resolves to gitlab, not the github default
cd "$RUN_ROOT/agentic-playground" && uv run python -c \
  "from fr._hosts import detect_backend; from pathlib import Path; \
   b=detect_backend(Path('.')); print(b); assert b=='gitlab', b"

# 6. maven cache warm — otherwise the recording measures the network
mvn -q -o dependency:resolve || echo "WARN: offline resolve failed, cache cold"
```

## Record

```bash
XDG_CONFIG_HOME=$CFG XDG_DATA_HOME=$DATA GITLAB_HOST=$GITLAB_HOST \
  asciinema rec --idle-time-limit 2 --title "fr-goal agentic-playground" \
    -c "opencode --auto $RUN_ROOT/agentic-playground" \
    $RUN_ROOT/demo.cast
```

**Harness is an open decision.** bc88 used `opencode --auto` with
`github-copilot/gpt-5.6-terra`. Two arguments to keep it: the audience's own
prerequisites name Copilot, and OpenCode's `/fr-goal` ran **0 subagents in
17 min** where Claude ran 14 subagents in 56 min — decisive for a 15–25 min
budget. Confirm with the operator before recording.

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
| `fr isolation up` → worktree + container | Security |
| batched Q&A asked, turn ends | the contract |
| spec written | Continuity |
| acceptance rows presented | Quality |
| plan folder + `_meta.yaml` | Continuity |
| run cursor advances | Continuity |
| phase executor dispatched | Extensibility |
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

## Post-run: harvest harness findings before tearing anything down

Carried forward from bc88, where this was a second deliverable rather than a
footnote. The evidence is perishable — it lives in the cast, the db and the
cursor.

```bash
# a human answered the gate; the agent did not clear its own
grep -n 'answered_by' "$RUN_ROOT"/agentic-playground/docs/superpowers/runs/*.yaml

# journal findings must be resolved, not merely present
cd "$RUN_ROOT/agentic-playground" && uv run fr journal check
```

This run is also the **first live exercise of the GitLab path end to end**, so
it doubles as verification for #486. Anything it surfaces gets an issue, the
same way #486 itself came out of a five-minute check.
