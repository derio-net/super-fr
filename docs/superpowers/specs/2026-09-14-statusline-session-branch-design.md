# Status line: session branch and fr-isolation worktree — design

Status: draft (fr-brainstorming, 2026-09-14)
Branch: `feat/statusline-session-branch`
Operator decisions recorded in §4 (d1–d5); journal
`docs/superpowers/journals/specs/2026-09-14-statusline-session-branch.md`.
Supersedes §5.E and decision d4 of
`2026-09-04-worktree-traceability-design.md`.

## 1. Goal

The status line must answer two questions at a glance:

1. **Which branch is this session working on?**
2. **Is this session inside an fr-isolation workspace, and where is it?**

After this ships, the Claude Code status line reads:

```
Opus 5 (1M context) | ctx:8% of 1M | 5h:12% 7d:30%
branch: feat/x | ~/Docs/projects/acme
worktree: /Users/me/.cache/fr/worktrees/acme/feat__x
```

or, for a session with no fr workspace:

```
branch: main | ~/Docs/projects/acme
no fr-isolation
```

The branch and worktree text is **green** when the session is in an fr
workspace and **purple** when it is not.

### Non-goals

- A status bar inside OpenCode. OpenCode has no status-line hook (§2.3).
- Writing a Hermes status-bar key that Hermes does not ship yet (§2.3).
- Liveness detection of sessions, or new binding transports.
- Editing the operator's personal `~/.claude/statusline.sh` in this PR. That
  file is not tracked; it is rewired on the host after merge (d1).

## 2. Background — what exists today (verified 2026-09-14)

### 2.1 The segment

`plugins/super-fr/scripts/fr-statusline-segment.sh` reads Claude Code
status-line JSON and prints two lines:

- `iso: <bound worktree>` when the session is bound elsewhere than the cwd;
  `iso: ? (feat/x, feat/y)` when the session is unbound and the repo has fr
  workspaces; else empty.
- `worktrees (N): branch:rel, …` — every other worktree of the repo.

The operator script puts the cwd's checked-out branch first on line 2 and the
gauge on line 3.

### 2.2 Why it fails the operator

Observed on the operator Mac, in a willikins base-clone session with no
binding:

```
main | ~/Docs/projects/DERIO_NET/willikins | iso: ? (feat/book-service-brainstorm)
worktrees (3): feat/book-service-brainstorm:~/.cache/fr/worktrees/…, +1 more
```

- The branch is the cwd's branch, even when the session is bound to a
  workspace on another branch.
- `iso: ?` lists workspaces that belong to *other* sessions. It reads as if
  this session were in isolation.
- The gauge lists worktrees unrelated to this session.

### 2.3 Harness support for a command-driven status line

super-fr supports three harnesses (`fr models resolve --harness`:
`claude-code | opencode | hermes`).

| Harness | Command-driven status line | Input to the command |
|---|---|---|
| Claude Code | `statusLine.command` in settings | JSON on stdin (`session_id`, `workspace.current_dir`, `cwd`, …) |
| OpenCode | **None.** Requested upstream: anomalyco/opencode#37464, #30295. `ocstatusline` (separate pane) has no command widget yet. | — |
| Hermes Agent | **Not shipped.** `display.status_bar.custom_command` is PR NousResearch/hermes-agent#109596, open. First line only, 40 chars, ~10 s TTL, runs in the session cwd. | cwd only; no documented session id |

### 2.4 Session binding data

`~/.cache/fr/sessions/<session_id>.json` (`FR_SESSIONS_DIR`) has keys
`session_id, harness, repo_root, branch, worktree, profile, attached_at`.
Workspace state lives in `<git-common-dir>/fr/isolation/<branch-slug>.json`
with keys `repo_root, branch, worktree, …`.

## 3. Principle — neutral core, thin harness wiring

One shell script decides **what** to show. Harness wiring decides **where**
to show it. The core reads files and runs one `git` call; it never runs the
`fr` CLI (4 s) and never breaks the harness (every failure exits 0).

## 4. Operator decisions (asked once, 2026-09-14)

- **d1 Location:** the super-fr segment prints the new rows, with golden
  tests, skill wiring docs, and the acceptance row, in one PR. The operator's
  `~/.claude/statusline.sh` is rewired after merge. Ship a version for every
  supported harness.
- **d2 Layout:** line 2 = `branch: <b> | ~/cwd`; line 3 = `worktree: <full
  path>` or `no fr-isolation`. Remove the `iso: ?` hint and the worktree
  gauge.
- **d3 Branch:** the bound workspace's branch; else the branch checked out at
  the cwd; else `no branch`. Green when fr, purple when not.
- **d4 Worktree:** a full path when the session is bound, or when the cwd's
  toplevel is an fr workspace. Native `.claude/worktrees/agent-*` and plain
  git worktrees show `no fr-isolation`. The colour rule of d3 applies.
- **d5 Harness versions (agent decision after research, flagged to the
  operator):** ship the neutral core with a `oneline` format; a Claude Code
  reference status line; Hermes wiring documented against the pending
  `custom_command` key, not written into `.hermes/config.snippet.yaml`; the
  OpenCode gap documented with its upstream issue.

## 5. Design

### A. Segment contract v2 (`plugins/super-fr/scripts/fr-statusline-segment.sh`)

**Input.**

- Default: Claude Code status-line JSON on stdin. Fields used:
  `session_id`, `workspace.current_dir // cwd`.
- `--cwd <dir>`: use this cwd and do **not** read stdin (Hermes runs the
  command with no JSON). `--session-id <id>` sets the session id with
  `--cwd`.
- `--format plain|ansi|oneline` (default `plain`).

**Resolution (first match wins).**

1. **Bound.** The session id is set, the index file exists, its `worktree`
   is non-empty and the directory exists. Then: state `fr`, branch =
   index `branch` (if empty: `no branch`), worktree = index `worktree`.
   A binding whose worktree is gone is ignored (stale, §6).
2. **cwd in a repo.** One call:
   `git -C <cwd> rev-parse --show-toplevel --git-common-dir --symbolic-full-name HEAD`.
   Branch = `X` when HEAD prints `refs/heads/X`; `no branch` when it prints
   `HEAD` (detached, or an unborn branch). The state is `fr` when a
   `<common>/fr/isolation/*.json` file has a `worktree` equal (physical
   path) to the toplevel; then worktree = that toplevel. Else state `none`,
   worktree row `no fr-isolation`.
3. **No repo / no cwd / bad JSON.** State `none`, `no branch`,
   `no fr-isolation`.

**Output.**

- `plain` — exactly three lines:
  ```
  fr | none
  branch: <b> | no branch
  worktree: <abs path> | no fr-isolation
  ```
- `ansi` — exactly two lines, rows 2–3 of `plain`, each wrapped in green
  (`\033[32m`) when `fr`, purple (`\033[35m`) when `none`, and reset.
- `oneline` — one line, sized for a 40-char slot: `fr:<branch>` when `fr`,
  `<branch>` when `none` (`no branch` spelled out). No ANSI.

**Budget.** Bound path: 1 `jq` (stdin) + 1 `jq` (index). cwd path: 1 `jq`
(stdin) + 1 `git` + at most 1 `jq` (state files). Well under the old
~100 ms. The CI timing guard stays at 0.5 s.

### B. Claude Code reference status line (`plugins/super-fr/scripts/fr-statusline-claude.sh`)

A complete status line a user can point `statusLine.command` at:

- line 1: model (context size) | `ctx:NN% of X` | `5h:NN% 7d:NN%` (colour
  thresholds 50/75), each part omitted when its JSON field is absent;
- line 2: `branch: <b>` (segment colour) `|` `~/cwd` (blue);
- line 3: the worktree row (segment colour).

It locates the segment next to itself (`dirname "$0"`), so it works from the
plugin cache and from a dev checkout. It puts a real git first on PATH when
Xcode's exists (Apple shim cost, journal 9ecae0965ac4).

### C. Hermes wiring (docs only)

The fr-isolation skill documents, for when hermes-agent#109596 ships:

```yaml
display:
  status_bar:
    fields: [..., custom]
    custom_command: "bash <install-dir>/fr-statusline-segment.sh --format oneline --cwd ."
```

Hermes runs the command in the session cwd, so rule A.2 applies (Hermes has
no bind transport, so rule A.1 never fires there). `config.snippet.yaml` is
not changed: `fr hermes install` must not write a key Hermes does not read.

### D. OpenCode (docs only)

The skill states that OpenCode has no status-line hook and names
anomalyco/opencode#37464. A user can still run
`fr-statusline-segment.sh --format oneline --cwd <dir>` from a tmux or herdr
status bar.

### E. Docs

- `plugins/super-fr/skills/fr-isolation/SKILL.md` "Session bindings": the
  v2 contract, the Claude Code wiring (point `statusLine.command` at
  `fr-statusline-claude.sh`, or call the segment with `--format ansi` from
  an own script), §C and §D. Mirror copies under `.hermes/skills` and
  `.opencode/skills` are regenerated with `scripts/sync-hermes.py` and
  `scripts/sync-opencode.py`, so their sync tripwires stay green.
- `README.md` "Isolation": replace the "bound workspace and the repo's other
  worktrees" sentence.
- `docs/superpowers/specs/2026-09-04-worktree-traceability-design.md`
  §5.E: one-line pointer to this spec.

## 6. Risks & mitigations

- **Contract break.** A user script that reads the v1 two-line output shows
  the new rows in the wrong places after a plugin update. Mitigation: the
  reference script (§B) is a drop-in; the skill shows the migration; the PR
  body calls out the break. The only known consumer is the operator's own
  script, rewired post-merge (d1).
- **Stale binding** (SessionEnd not fired, worktree removed). Rule A.1
  ignores a binding whose worktree directory is gone. A binding whose
  worktree still exists but is no longer used shows green until `gc` or a
  new attach — unchanged from today.
- **Unborn branch** shows `no branch`. Accepted: a repo with no commit has
  no work to trace.
- **Hermes key churn.** The pending PR may rename the key. Mitigation: docs
  only; nothing is installed.

## 7. Test plan

Golden-output tests (subprocess, `tests/unit/test_statusline_segment.py`,
rewritten) over a fixture repo with one fr workspace and one plain linked
worktree:

- bound session from the base clone → `fr`, bound branch, bound path;
- bound session whose worktree is gone → falls back to the cwd rule;
- unbound session in the base clone → `none`, `main`, `no fr-isolation`
  (no other workspace named);
- unbound session with cwd inside the fr workspace → `fr`, its branch, its
  path;
- plain linked worktree and native `agent-*` worktree → `none`;
- detached HEAD → `no branch`;
- non-repo and missing cwd → `none`, `no branch`, `no fr-isolation`;
- `--cwd` does not read stdin (a closed/blocking stdin must not hang);
- `ansi` colours: green for `fr`, purple for `none`; `oneline` ≤ 40 chars
  for short branches and has no ANSI;
- missing/unknown session id → unbound;
- timing guard 0.5 s; the `fr` CLI is never invoked (trap on PATH).

`fr-statusline-claude.sh`: golden test for a full JSON payload (three lines,
colours) and for a payload without `rate_limits`/`context_window`.

Post-merge (operator-driven): update the plugin, rewire
`~/.claude/statusline.sh` to the v2 segment, and look at the footer in a
bound session and in a plain base-clone session.

## Implementation Plans

_(filled by fr-plan)_

## 8. Acceptance rows (born here; presented at spec review)

| id | claim | level | status |
|---|---|---|---|
| `statusline-shows-bound-workspace` (updated) | The Claude Code status line shows the branch this session works on and its fr-isolation worktree path (or `no fr-isolation`), green when fr and purple when not, within one refresh. | int | ci |
| `statusline-harness-neutral-segment` (new) | Any harness can render the session branch and fr-isolation state from one shell command (`--cwd`, `--format oneline`), without the fr CLI and without stdin JSON. | int | ci |
