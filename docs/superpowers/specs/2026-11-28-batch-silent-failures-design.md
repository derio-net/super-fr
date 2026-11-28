# Silent failures: errors that report success or lose their reason

Issues: derio-net/super-fr#1682, derio-net/super-fr#1668, derio-net/super-fr#1592,
derio-net/super-fr#1689 (triage batch `silent-failures`).

## Background

Four places swallow a failure. Each one leaves either a success report or a missing
value, and none of them says why.

1. **install.sh, `fr models apply`** (#1682). `scripts/install.sh` runs
   `fr models apply --harness opencode || true` after it copies the OpenCode agent
   files. The `|| true` was meant for an unbound tier, a missing `fr` or a hand-edited
   agent file. It also hides every refusal `fr` makes. PR #1583 hit this: the CLI-entry
   migration gate refused with exit 2 (a stale plan ceiling in a detached checkout),
   and the only symptom was tier agent files without a `model:` line. An unbound tier
   already exits 0 (`fr.opencode_agents.materialize_agents` leaves the file without a
   `model:`), so the tolerance the `|| true` was written for does not need it.
   The install prints 17 `WARNING:` lines from different steps, all scrolled past by the
   time `Installation complete.` appears.
2. **bootstrap.sh, `installable_tags`** (#1668). `scripts/bootstrap.sh` lists the remote's
   release tags and keeps those whose `scripts/install.sh` carries the
   `# fr-install-channels: 1` marker. A tag whose `git show refs/tags/<t>:scripts/install.sh`
   fails is dropped with `|| continue`, and git's stderr goes to `/dev/null`.
   `test_the_refusal_lists_installable_tags_in_version_order` failed once on CI with exactly
   one marked tag (`v1.2.0-rc.10`) missing. The cause is not proven: 300 parallel local
   runs (16 at a time) of the same fixture dropped nothing. Two more defects sit in the
   same lines. The marker check is `printf '%s\n' "$content" | grep -qx …` under
   `set -o pipefail`: `grep -q` stops reading at its first match, so a producer still
   writing gets `SIGPIPE`, and the pipeline then reads as "no marker". And the callers run
   `installable_tags` inside `$( … )` (`TAG="$(installable_tags | … || true)"`, `refuse`'s
   `all="$(installable_tags | sort_versions)"`), so an `exit` inside it would end only the
   subshell.
3. **`fr run adopt` and `fr push`** (#1592). `fr.run.adopt.default_pr_state` reads a PR's
   state through the host adapter and answers `None` on any exception
   (`packages/fr/src/fr/run/adopt.py:787-789`). `fr.commands.push_cmd.refuse_closed_pr`
   skips a PR whose state it cannot read (`except FORGE_ERRORS: continue`,
   `packages/fr/src/fr/commands/push_cmd.py:156-158`). Both fail open on purpose. But the
   adapters now re-raise an error that names an SSO or forward-auth login page
   (`fr.forge_body.names_login_page`, gh#1554), and these two sites drop that reason
   without a word.
4. **`fr debt`** (#1689). `fr.debt.engine.compute` records a failed forge read as
   `SourceStatus(state="unavailable", why=f"{type(e).__name__}: {e}")`.
   `fr.debt.render.source_category` maps every unavailable `forge` source to the
   publishable category `forge error`, so a Gitea backend that raises
   `UnsupportedForgeOperation` for `list_issues` (gh#611) is published as a failure. The
   category's docstring says the detail stays "in `fr debt`'s terminal output and the CI
   log", but `fr debt issue` prints only `create:`/`refresh:`/`close:`, so the CI log has
   no reason at all.

## Requirements

R1. When `fr models apply --harness opencode` exits non-zero during install, the install
    continues and prints a `WARNING:` that names the exit code, `fr`'s own message (its
    stderr, at most 5 lines) and the remedy: fix what `fr` names, then run
    `fr models apply --harness opencode`. When `fr` is not on PATH at that step, the
    install continues and prints a `WARNING:` saying the tier models were not applied
    because `fr` is not on PATH. An exit 0 prints no warning.
R2. install.sh records every `WARNING:` it prints, including one printed from a function
    or a subshell. When the install completes, its closing lines name the installed `fr`
    version (`fr --version` of the `fr` on PATH, or that no `fr` is on PATH) and then repeat
    every recorded warning, in the order printed, under a heading that gives their count.
    An install with no warnings says so in one line. An install that stops on an `ERROR:`
    still ends on that error.
R3. bootstrap.sh tells three cases apart for each release tag. A tag whose
    `scripts/install.sh` is absent, or present without the channel marker, is skipped
    without a message, as today. A tag whose `scripts/install.sh` git cannot read (the
    listing or the read fails) stops bootstrap with exit 1 and
    `ERROR: could not read scripts/install.sh at <tag>: <git's message>`, before anything
    is checked out. No tag is ever dropped without a message. This holds on every path
    that lists tags: the default newest release, `--version RC`, an explicit version, and
    the refusal's list of installable versions.
R4. bootstrap.sh's marker check cannot read a marked `install.sh` as unmarked because of a
    pipe: it does not pipe the file's content into a reader that may stop early.
R5. `fr run adopt` still treats a PR whose state it cannot read as unknown (fail-open),
    and prints one line on stderr, `warning: could not read the state of PR <url>: <reason>`.
    The reason is the error's own message, redacted (`fr.debt.render.redact`), cut to one
    line of at most 300 characters. A login-page error is therefore named.
    `fr.run` stays free of `typer` and console imports: the line reaches the operator
    through the command layer.
R6. `fr push`'s merged-PR guard still skips a PR whose state it cannot read (fail-open),
    and prints the same one-line warning as R5 on stderr for it.
R7. `fr debt` publishes a forge source that is unavailable because the backend does not
    support an operation (`UnsupportedForgeOperation`) under the category
    `not supported on <backend> (<tracking issue>)`, for example
    `not supported on gitea (gh#611)`. It never publishes it as `forge error`. The backend
    and the tracking issue reach the category only as fixed-shape tokens (a lowercase word;
    `gh#<n>` or `<owner>/<repo>#<n>`), else the category is `not supported by this forge`.
    Every other forge failure keeps its current category.
R8. `fr debt issue` prints one line on stderr per unavailable source,
    `unavailable: <source>: <reason>` (the reason redacted and cut as in R5), in preview and
    with `--yes`, before it writes anything.

## Design

**install.sh (R1, R2).** One helper, `warn`, prints its message to stderr and appends it
to a warnings file created with `mktemp` near the top of the script (removed by the
script's existing cleanup on exit). A file, not an array, because a warning printed from a
`$( … )` or a subshell must still reach the summary. Every `WARNING:` site in install.sh
calls `warn`; a multi-line warning records its lines together. The
`fr models apply … || true` becomes: if `fr` is not on PATH, `warn` that; else run it with
stderr captured to a temp file and, on a non-zero exit, `warn` with the code, up to 5
lines of that stderr and the remedy. Stdout still flows as today. After
`Installation complete.`, a closing block prints `fr version: <fr --version>` (or
`fr: not on PATH`), then `Warnings (N):` and each recorded warning, or `No warnings.`.

**bootstrap.sh (R3, R4).** `installable_tags` reads each tag in two steps:
`git ls-tree --name-only refs/tags/<t> -- scripts/install.sh` (exit 0 with empty output:
absent, skip; non-zero: an error), then `git show refs/tags/<t>:scripts/install.sh` with
its stderr captured (non-zero: an error). On an error it prints the R3 `ERROR:` line with
git's first stderr line and returns non-zero. The marker test reads the content through a
here-string (`grep -qx … <<<"$content"`), which has no producer to signal. Bootstrap
computes the list once, `if ! INSTALLABLE="$(installable_tags)"; then exit 1; fi`, before
any channel is chosen, and every later use (`refuse`, the default, `RC`, an explicit
version) filters `$INSTALLABLE` instead of calling `installable_tags` again. The ERROR line
is already on stderr, so the subshell does not hide it.

**adopt and push (R5, R6).** A small helper in `fr.forge_body` (already the home of
`names_login_page` and `not_json_reason`), `read_failure(url, exc) -> str`, builds the R5
line: redacted, the first line only, at most 300 characters. `default_pr_state` takes an
optional `warn: Callable[[str], None]` and calls it with that line in its `except`; the
adopt command passes a function that writes to stderr (`typer.echo(..., err=True)`).
`refuse_closed_pr` lives in the command layer and prints the line itself before its
`continue`. `fr.run` imports neither `typer` nor a console, which
`tests/unit/test_run_writes_layering.py` already holds.

**fr debt (R7, R8).** `compute` keeps `why` as `f"{type(e).__name__}: {e}"`, which for this
exception reads `` UnsupportedForgeOperation: `list_issues` is not supported on the gitea backend yet (tracked in gh#611) ``
(the exception's fixed message, `fr.ghclient.UnsupportedForgeOperation.__init__`).
`source_category`, for `name == "forge"`, matches that shape with an anchored pattern and
returns `not supported on <backend> (<tracking issue>)` when both tokens fit R7's shapes,
`not supported by this forge` when the prefix matches and a token does not, and
`forge error` otherwise. A test builds the `why` from a real `UnsupportedForgeOperation`,
so a change to its message fails the test instead of the category. `SourceStatus` and the
`DebtReport` JSON keep their shape. `issue_cmd` prints the R8 lines right after
`_compute`, through the existing `_clean` (redact and strip control characters).

## Design shape

```
scripts/
  install.sh          ~ warn() + warnings file; every WARNING: through warn       R2
                      ~ fr models apply: capture exit + stderr, warn, no || true   R1
                      ~ closing block: fr version, Warnings (N) / No warnings.     R2
  bootstrap.sh        ~ installable_tags: ls-tree (absent) vs show (error → ERROR) R3
                      ~ marker test via here-string, no pipe                       R4
                      ~ INSTALLABLE computed once, checked; every path filters it  R3
packages/fr/src/fr/
  forge_body.py       + read_failure(url, exc): redacted one-line warning          R5 R6
  run/adopt.py        ~ default_pr_state(repo_root, warn=None): warn in except     R5
  commands/run_cmd.py ~ adopt passes a stderr warn                                 R5
  commands/push_cmd.py~ refuse_closed_pr: print read_failure before continue       R6
  debt/render.py      ~ source_category: "not supported on <backend> (<issue>)"    R7
  commands/debt_cmd.py~ issue_cmd: "unavailable: <source>: <reason>" on stderr     R8
tests/
  integration/test_install_opencode_agents.py  + refusing fr stub → WARNING + summary
  integration/test_install_channels.py         + unreadable tag → ERROR; marker cases
  unit/                                        + adopt/push warn lines; debt category
                                                 + debt issue stderr lines
```

## Verification

strategy: candidate
gate: developer
settle.conflicts: report — batch silent-failures: the wave driver owns this PR's mergeability
settle.ci: report — batch silent-failures: the wave driver owns this PR's CI

- install-warns-on-fr-refusal: none — CI runs install.sh against a stub `fr` that refuses (tests/integration/test_install_opencode_agents.py)
- bootstrap-unreadable-tag-refuses: none — CI runs bootstrap.sh against a fixture remote with an unreadable tag (tests/integration/test_install_channels.py)
- forge-read-failure-named: none — unit tests drive adopt and push with a forge that raises
- debt-unsupported-forge-named: none — unit tests drive `fr debt` and `fr debt issue` with a forge that raises UnsupportedForgeOperation

The run's `candidate` walk installs the branch into a throwaway prefix and smokes it. Each
row is proven by the CI tests named on its line; none needs a released build, so there is
no Test Plan.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-28-batch-silent-failures | `derio-net/super-fr` | `2026-11-28-batch-silent-failures` | — |
