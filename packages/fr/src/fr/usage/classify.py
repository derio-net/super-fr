"""What a tool call was FOR: `(tool name, command or path) -> activity` (spec §5.A.4).

A pure function — no I/O, no clock, no environment — so a rule is a table row
and a table test. Three activities, each with a finer `sub`:

- **paperwork**: fr's own bookkeeping — writing and reading specs, plans,
  journals, run cursors and the acceptance matrix, checking them, and learning
  the fr CLI (`--help`).
- **implementation**: reading and writing code, and verifying it (tests, lint).
- **other**: version control, orchestration (dispatch, skills, todos), chores,
  and narration (a message with no tool call).

Shell commands are unwrapped first — `fr isolation exec [...] --`, a leading
`cd <dir> &&`, `VAR=value &&` / `export VAR=...;` prefixes — then matched by
`fr` verb, then path, then `git`/`gh`, in the order of `_BASH_RULES`. Tool names
from every harness canonicalize onto Claude Code's (`bash`/`terminal` -> Bash,
`read_file` -> Read, ...), so one rule set serves all three.
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

Activity = Literal["paperwork", "implementation", "other"]

PAPERWORK_SUBS = frozenset(
    {
        "spec_write",
        "plan_write",
        "journal_write",
        "plan_tick",
        "run_cursor",
        "acceptance",
        "paper_read",
        "paper_check",
        "fr_cli_learning",
    }
)
IMPLEMENTATION_SUBS = frozenset({"code_write", "code_read", "verify"})


class Classification(NamedTuple):
    activity: Activity
    sub: str


def _of(sub: str) -> Classification:
    if sub in PAPERWORK_SUBS:
        return Classification("paperwork", sub)
    if sub in IMPLEMENTATION_SUBS:
        return Classification("implementation", sub)
    return Classification("other", sub)


NARRATION = _of("narration")
"""A message that made no tool call: thinking and prose."""

_ALIASES: dict[str, str] = {
    # shell
    "bash": "Bash",
    "terminal": "Bash",
    "execute_code": "Bash",
    # reads
    "read": "Read",
    "read_file": "Read",
    "view": "Read",
    # writes
    "edit": "Edit",
    "write": "Write",
    "multiedit": "Edit",
    "MultiEdit": "Edit",
    "NotebookEdit": "Edit",
    "apply_patch": "Edit",
    "patch": "Edit",
    "write_file": "Write",
    # searches
    "grep": "Grep",
    "glob": "Glob",
    "search_files": "Grep",
    "list": "Glob",
    # orchestration
    "task": "Agent",
    "Task": "Agent",
    "delegate_task": "Agent",
    "SendMessage": "Agent",
    "TaskOutput": "Agent",
    "TaskStop": "Agent",
    "skill": "Skill",
    "todowrite": "TodoWrite",
}

_ORCHESTRATION = frozenset({"Agent", "Skill", "TodoWrite", "ToolSearch"})

_FR = r"\bfr "
"""An `fr` invocation, bare or behind `uv run [--flags]` — the verb follows."""

_BASH_RULES: tuple[tuple[str, str], ...] = (
    # learning the CLI: `fr <verb> [<sub>] --help`, before any verb rule claims it
    (r"\bfr [a-z-]+(?: [a-z-]+)? --help|\bfr --help", "fr_cli_learning"),
    # journal writes: the durable run-state log
    (_FR + r"journal (add|resolve)", "journal_write"),
    # plan step ticks and phase completion
    (_FR + r"plan (edit|tick)", "plan_tick"),
    # run-cursor movement
    (_FR + r"run (start|adopt|advance|resolve|claim|release)", "run_cursor"),
    # authoring a plan through the CLI
    (_FR + r"plan (create|new|phase)", "plan_write"),
    # acceptance-matrix writes
    (_FR + r"acceptance (add|set-status|report)", "acceptance"),
    # validators over the paper trail
    (
        _FR + r"(acceptance (check|status)|journal (check|render)|validate|"
        r"plan (self-review|proportionality|check|lint)|run check|workflow check|harness parity)",
        "paper_check",
    ),
    # reading the paper trail through fr
    (
        _FR + r"(pickup|run (status|cost|show)|plan (show|status|list)|journal (show|list|handoff)|"
        r"status\b|progress)",
        "paper_read",
    ),
    # artifact migration and generated-mirror / version chores
    (_FR + r"migrate", "chores"),
    (r"sync-(opencode|hermes)\.py|bump-version\.py|render_explainer", "chores"),
    # tests, lint, type checks and their logs
    (r"\b(pytest|ruff|mypy|bun test|tsc)\b|full\d*\.log|fullsuite|coverage|\.fr-deliver", "verify"),
    # a shell write (heredoc / redirect / tee) is classified by the path it writes
    (r"__WRITE__", "__write__"),
    # any other touch of the paper trail by path
    (r"docs/superpowers/|docs/acceptance", "paper_read"),
    # version control
    (r"^(git|gh)\b|&& (git|gh) |; (git|gh) ", "vcs"),
    # isolation lifecycle
    (_FR + r"isolation", "isolation"),
    # any other touch of code by path
    (r"(packages|tests|plugins|scripts|src)/|\.py\b|\.ts\b", "code_read"),
)
"""Ordered: the first matching rule wins. `__WRITE__` is the one non-regex row."""

_WRITE_TARGET = re.compile(r"""(?:\bcat\s*>>?|\btee(?:\s+-a)?)\s*(["']?)([^\s;&|'"<>]+)\1""")


_PREFIX = re.compile(
    r"^(?:cd\s+\S+\s*(?:&&|;)\s*"  # cd <dir> && / ;
    r"|(?:export\s+)?(\w+)=(\S*)\s*(?:&&|;)\s*"  # [export] VAR=value && / ;
    r"|(\w+)=(\S+)\s+)"  # VAR=value <command>
)


def _unwrap(command: str) -> str:
    """The command that actually runs, without the wrappers around it.

    A stripped `VAR=value` is not thrown away: its value is substituted for
    `$VAR` / `${VAR}` in the rest, because the value is often the only place
    the path lives (`F=docs/superpowers/plans/x && cat $F`)."""
    c = command.strip()
    c = re.sub(r"^(cd\s+\S+\s*&&\s*)+", "", c)
    wrapped = re.search(r"fr isolation exec(?:\s+--?[\w-]+(?:\s+[^-\s]\S*)?)*\s+--\s+(.*)", c, re.S)
    if wrapped:
        c = wrapped.group(1).strip().strip("'\"")
        c = re.sub(r"^(bash|sh) -l?c\s+", "", c).strip("'\"")
    while True:
        match = _PREFIX.match(c)
        if match is None or not match.group(0):
            return c
        c = c[match.end() :]
        name, value = match.group(1) or match.group(3), match.group(2) or match.group(4)
        if name and value:
            value = value.strip("'\"")
            c = re.sub(r"\$\{?" + name + r"\b\}?", lambda _m: value, c)


def _path(path: str, write: bool) -> Classification:
    p = path or ""
    if re.search(r"(^|/)\.fr-deliver/", p):
        # deliver's `tests=<log>` evidence: the suite's own output, so touching
        # it is verification — the same answer the shell rule gives
        return _of("verify")
    if re.search(r"(^|/)docs/superpowers/specs/", p):
        return _of("spec_write" if write else "paper_read")
    if re.search(r"(^|/)docs/superpowers/plans/", p):
        return _of("plan_write" if write else "paper_read")
    if re.search(r"(^|/)docs/superpowers/(journals|runs)/", p):
        return _of("journal_write" if write else "paper_read")
    if re.search(r"(^|/)docs/superpowers/", p):
        return _of("paper_read")
    if re.search(r"(^|/)docs/acceptance/", p):
        return _of("acceptance" if write else "paper_read")
    if re.search(r"(^|/)(\.opencode|\.hermes|docs/explainers)/|CHANGELOG", p):
        return _of("chores")
    if re.search(r"(^|/)(packages|tests|plugins|scripts)/", p):
        return _of("code_write" if write else "code_read")
    return _of("other_file")


def _bash(command: str) -> Classification:
    c = _unwrap(command)
    for pattern, sub in _BASH_RULES:
        if sub == "__write__":
            target = _WRITE_TARGET.search(c)
            written = _path(target.group(2), write=True) if target else None
            # only a write into the repo's own trees is classified by its path;
            # a scratch file falls through to what the command otherwise does
            if written is not None and written.sub not in ("other_file", "chores"):
                return written
            continue
        if re.search(pattern, c):
            return _of(sub)
    return _of("shell_other")


def classify(name: str, target: str = "") -> Classification:
    """What the tool call `name(target)` was for. Pure; never raises."""
    tool = _ALIASES.get(name, name)
    if tool == "Bash":
        return _bash(target or "")
    if tool in ("Edit", "Write"):
        return _path(target, write=True)
    if tool == "Read":
        return _path(target, write=False)
    if tool in ("Grep", "Glob"):
        return _path(target, write=False) if target else _of("code_read")
    if tool in _ORCHESTRATION:
        return _of("orchestration")
    return _of("other_tool")
