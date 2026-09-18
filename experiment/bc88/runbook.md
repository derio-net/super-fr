# Runbook — blog-craft #88, two arms

| | Arm P — plain + plan | Arm G — /fr-goal |
|---|---|---|
| Treatment | `prompt-planned.md` | `prompt-frgoal.md` (typed as `/fr-goal …`) |
| Config | `cfg-P` — no skills, no commands | `cfg-G` — the nine `fr-*` skills + commands, nothing else |
| Clone | `planned/` on `experiment/bc88-planned` | `frgoal/` on `main`; fr-goal cuts its own workspace |
| Base | `2874f35c3755` | same |
| Model | `github-copilot/gpt-5.6-terra`, default effort | same |

blog-craft's own `.opencode/` (11 blog-craft skills + commands, empty
instructions, **no plugins**) reaches both arms from the clone, so fr is the
only difference between them. Nothing repo-level is removed — unlike the
super-fr experiment, there is no fr wiring in the repo to strip, so no setup
commit and no polluted diff.

## Fixed since the last experiment

| Last time | Now |
|---|---|
| `gh` unauthenticated in every arm — no PR could be opened | `~/.config/gh` copied into both cfg dirs; `gh auth status` and `gh issue view` verified inside each |
| Clone outside `~/Docs/projects` → commits authored as the work identity | `RUN_ROOT` under `~/Docs/projects`; identity asserted per clone |
| `https` remote → the keychain credential for `clawdia-ai-assistant` | `git@github.com:` clone; dry-run push verified |
| `cfg-A`'s skill copy silently didn't take, so the arm ran on repo mirrors | `fr-goal/SKILL.md` and `commands/fr-goal.md` asserted present |
| An MCP server in one arm only | neither config declares one |
| Setup deletions risked polluting the measured diff | nothing is deleted |

## Run

```bash
export RUN_ROOT=~/Docs/projects/experiment-bc88

# Arm P first — so fr-goal's framing cannot leak into the corrections given to it
XDG_CONFIG_HOME=$RUN_ROOT/cfg-P XDG_DATA_HOME=$RUN_ROOT/data-P \
  asciinema rec --idle-time-limit 2 --title "planned bc88" \
    -c "opencode --auto $RUN_ROOT/planned" $RUN_ROOT/planned.cast

# Arm G
XDG_CONFIG_HOME=$RUN_ROOT/cfg-G XDG_DATA_HOME=$RUN_ROOT/data-G \
  asciinema rec --idle-time-limit 2 --title "fr-goal bc88" \
    -c "opencode --auto $RUN_ROOT/frgoal" $RUN_ROOT/frgoal.cast
```

Neither arm uses `--pure`: blog-craft ships no OpenCode plugins, so there is
nothing to disable and one fewer difference between the arms.

## Measuring

Each arm writes its own `opencode.db` under its `XDG_DATA_HOME`. The `session`
table carries `parent_id`, `agent`, `cost`, `tokens_*` and timestamps, so
subagent cost and wall time are attributable and included in an arm total.

```bash
DB=$RUN_ROOT/data-<P|G>/opencode/opencode.db
sqlite3 -readonly "file:$DB?mode=ro" "
SELECT COUNT(*) sessions, SUM(parent_id IS NOT NULL) subagents,
       ROUND(SUM(cost),2) cost, SUM(tokens_input) tin, SUM(tokens_output) tout,
       SUM(tokens_cache_read) cache FROM session;"
```

Cast length is the **sum of interval deltas** — asciinema v3 stores deltas, not
absolute timestamps. True wall time comes from the db's session spans.

## Scoring

`acceptance.md` is withheld from both runs and scored from the delivered PR
alone. `answers.md` is read out only when a run asks, and every utterance is
logged in `corrections.md` — which is the only record of what was actually
said to a run.
