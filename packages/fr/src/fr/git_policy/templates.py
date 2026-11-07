"""Commit subject templates (spec 2026-11-04-repo-feature-settings R14).

`git.commit.with_issue` applies when the run records an issue, `without_issue`
otherwise. fr's own commits pass through `fr_message`, the one seam: a
`chore(fr): <summary>` subject is re-rendered with type `chore`, scope `fr`, and
the body gains an `Fr-Commit` trailer. With the default templates and no issue the
subject is byte-identical to today's.
"""

from __future__ import annotations

import re
import string
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from fr.settings.model import Settings

FR_SUBJECT = re.compile(r"^chore\(fr\): (.*)$")
"""The subject every fr committer writes before the template applies."""

_GROUPS = {"issue": r"\d+"}
"""Placeholder patterns other than the default non-greedy `.+?`."""


def template_for(settings: Settings, issue: int | None) -> str:
    commit = settings.git.commit
    return commit.with_issue if issue is not None else commit.without_issue


def render_subject(
    settings: Settings, type_: str, scope: str, summary: str, issue: int | None
) -> str:
    """The subject for these values: `with_issue` iff *issue* is not None."""
    values = {"type": type_, "scope": scope, "summary": summary}
    if issue is not None:
        values["issue"] = str(issue)
    return template_for(settings, issue).format(**values)


def subject_regex(template: str) -> re.Pattern[str]:
    """*template* as an anchored regex: literal text escaped, each placeholder a
    named non-greedy group (a repeated placeholder must repeat its value)."""
    parts: list[str] = ["^"]
    seen: set[str] = set()
    for literal, field, _spec, _conv in string.Formatter().parse(template):
        parts.append(re.escape(literal))
        if field is None:
            continue
        if field in seen:
            parts.append(f"(?P={field})")
        else:
            seen.add(field)
            parts.append(f"(?P<{field}>{_GROUPS.get(field, '.+?')})")
    parts.append("$")
    return re.compile("".join(parts))


def parse_subject(template: str, subject: str) -> dict[str, str] | None:
    """The placeholder values *subject* was rendered from, or None if it was not."""
    m = subject_regex(template).match(subject)
    return m.groupdict() if m else None


def subject_matches(template: str, subject: str) -> bool:
    return parse_subject(template, subject) is not None


def subject_ok(settings: Settings, subject: str, *, parents: int, issue: int | None) -> bool:
    """R14's check: a merge commit (more than one parent) is exempt; any other
    commit's subject matches the template the run's issue selects."""
    if parents > 1:
        return True
    return subject_matches(template_for(settings, issue), subject)


def run_issue(repo_root: Path) -> int | None:
    """The issue recorded by the run of the branch checked out at *repo_root*.

    Every readable cursor whose `branch` is this one; None when none records an
    issue, or when they disagree (fr does not guess which one a commit is for).
    """
    from fr.run.adopt import current_branch
    from fr.run.model import RUNS_REL, RunStateError, parse_run_state

    branch = current_branch(repo_root)
    runs = repo_root / RUNS_REL
    if branch is None or not runs.is_dir():
        return None
    issues: set[int] = set()
    for path in sorted(runs.glob("*.yaml")):
        try:
            text = path.read_text()
            if "issue:" not in text:  # most cursors record none: skip the full parse
                continue
            state = parse_run_state(text)
        except (RunStateError, OSError, UnicodeDecodeError):
            continue
        if state.branch == branch and state.issue is not None:
            issues.add(state.issue)
    return issues.pop() if len(issues) == 1 else None


FR_COMMIT_TRAILER = "Fr-Commit"
"""The body trailer that marks a commit as fr's own (review p4-r2): `migrate` on a
`chore(fr): migrate …` commit, `bookkeeping` on every other. A subject rendered
through a template need not keep `{type}` or `{scope}`, so `fr push` cannot tell
fr's commits from the subject alone; the trailer survives every template, and a
trailer lives in the body, so a subject stays byte-identical."""

FrCommitKind = Literal["migrate", "bookkeeping"]

_TRAILER_LINE = re.compile(rf"^{FR_COMMIT_TRAILER}: (migrate|bookkeeping)$")


def fr_commit_kind(message: str) -> FrCommitKind | None:
    """The `Fr-Commit` trailer of *message* (its last paragraph), or None."""
    paragraphs = message.strip().split("\n\n")
    if len(paragraphs) < 2:  # a subject alone carries no trailer
        return None
    for line in paragraphs[-1].splitlines():
        m = _TRAILER_LINE.match(line.strip())
        if m is not None:
            return "migrate" if m.group(1) == "migrate" else "bookkeeping"
    return None


def _with_trailer(message: str, kind: FrCommitKind) -> str:
    if fr_commit_kind(message) is not None:
        return message
    body = message.rstrip("\n")
    return f"{body}\n\n{FR_COMMIT_TRAILER}: {kind}\n"


def fr_message(repo_root: Path, message: str) -> str:
    """*message* with an fr-written subject re-rendered through the templates,
    and the `Fr-Commit` trailer added to its body.

    Only a first line `chore(fr): <summary>` is touched; the body is kept. Raises
    `SettingsError` when the policy cannot be read: the caller refuses the commit.
    """
    first, sep, rest = message.partition("\n")
    m = FR_SUBJECT.match(first)
    if m is None:
        return message
    from fr.settings import load_settings

    settings = load_settings(repo_root).settings
    subject = render_subject(settings, "chore", "fr", m.group(1), run_issue(repo_root))
    kind: FrCommitKind = "migrate" if m.group(1).startswith("migrate ") else "bookkeeping"
    return _with_trailer(subject + sep + rest, kind)
