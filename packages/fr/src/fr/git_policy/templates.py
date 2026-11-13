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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _Lit:
    text: str


@dataclass(frozen=True)
class _Field:
    name: str


@dataclass(frozen=True)
class _Scope:
    """`{scope}` with the delimiters that vanish with it (see `segments`)."""

    left: str
    right: str


_Segment = _Lit | _Field | _Scope

_OPENERS = re.compile(r"[(\[{<]*$")
_CLOSERS = re.compile(r"[)\]}>]*")
_ONLY_OPENERS = re.compile(r"[(\[{<]+")


def _follows_type(raw: list[_Lit | _Field], i: int) -> bool:
    """True when the `{scope}` at *i* is Conventional Commits' `{type}(<scope>)`.

    Only that shape makes the scope optional: `{type}`, then nothing but
    opening brackets, then `{scope}`. Anywhere else (`[{scope}] {summary}`) the
    template's author asked for a scope, and an optional one would let any
    subject through as a bare summary.
    """
    if i >= 2 and isinstance(raw[i - 1], _Lit) and isinstance(raw[i - 2], _Field):
        lit, field = raw[i - 1], raw[i - 2]
        return field.name == "type" and bool(_ONLY_OPENERS.fullmatch(lit.text))  # type: ignore[union-attr]
    return False


def segments(template: str) -> list[_Segment]:
    """*template* split into literals, placeholders and optional scopes.

    The scope is optional, as in Conventional Commits (p4-deliver-r1), but only
    in that shape: `{type}` followed by opening brackets and `{scope}`
    (`_follows_type`). Anywhere else `{scope}` is a required placeholder. An
    optional `{scope}` takes with it, as one optional unit:

    - the run of opening brackets `( [ { <` immediately before it, and
    - the run of closing brackets `) ] } >` immediately after it, and
    - when that unit is a whole whitespace-separated token (at the template's
      start or after whitespace, and followed by whitespace or the template's
      end), one whitespace character beside it: the one after it, else (the
      token ends the template) the one before it.

    So `{type}({scope}): {summary}` drops `({scope})`, while `[{scope}] {summary}`
    and `{type}/{scope}: …` keep their scope required. `{type}`, `{summary}`
    and `{issue}` are always required, and
    a placeholder directly before a bracketed scope never contains its opening
    bracket (`subject_regex`), so `test(): x` is not read as type `test()`.
    """
    raw: list[_Lit | _Field] = []
    for literal, field, _spec, _conv in string.Formatter().parse(template):
        if literal:
            raw.append(_Lit(literal))
        if field is not None:
            raw.append(_Field(field))
    # Every `{scope}` must sit in the Conventional Commits position for any to
    # be optional: a scope repeated elsewhere is required everywhere.
    optional_scope = all(
        _follows_type(raw, j)
        for j, s in enumerate(raw)
        if isinstance(s, _Field) and s.name == "scope"
    )
    out: list[_Segment] = []
    pending = ""  # leading text of the next literal still to emit
    for i, seg in enumerate(raw):
        if isinstance(seg, _Lit):
            out.append(_Lit(seg.text[len(pending) :]) if pending else seg)
            pending = ""
            continue
        if seg.name != "scope" or not optional_scope:
            out.append(seg)
            continue
        left = ""
        prev = out[-1] if out else None
        if isinstance(prev, _Lit):
            out.pop()
            m = _OPENERS.search(prev.text)
            left = m.group() if m else ""
            rest = prev.text[: len(prev.text) - len(left)]
            if rest:
                out.append(_Lit(rest))
        nxt = raw[i + 1] if i + 1 < len(raw) else None
        right, after = "", ""
        if isinstance(nxt, _Lit):
            m = _CLOSERS.match(nxt.text)
            right = m.group() if m else ""
            after = nxt.text[len(right) :]
        last = out[-1] if out else None
        before = last.text if isinstance(last, _Lit) else None
        token_start = not out or (before is not None and before[-1:].isspace())
        if token_start and after[:1].isspace():
            right += after[0]
        elif token_start and not after and i + 2 >= len(raw) and before:  # ends the template
            out[-1] = _Lit(before[:-1])
            left = before[-1] + left
        if isinstance(nxt, _Lit):
            pending = right
        out.append(_Scope(left, right))
    return [s for s in out if not (isinstance(s, _Lit) and not s.text)]


def render(template: str, values: dict[str, str]) -> str:
    """*template* with *values*; an empty or missing scope drops its delimiters."""
    parts: list[str] = []
    for seg in segments(template):
        if isinstance(seg, _Lit):
            parts.append(seg.text)
        elif isinstance(seg, _Field):
            parts.append(values[seg.name])
        elif values.get("scope"):
            parts.append(f"{seg.left}{values['scope']}{seg.right}")
    return "".join(parts)


def render_subject(
    settings: Settings, type_: str, scope: str, summary: str, issue: int | None
) -> str:
    """The subject for these values: `with_issue` iff *issue* is not None. An
    empty *scope* renders without its delimiters (`test: x`, never `test(): x`)."""
    values = {"type": type_, "scope": scope, "summary": summary}
    if issue is not None:
        values["issue"] = str(issue)
    return render(template_for(settings, issue), values)


def subject_regex(template: str) -> re.Pattern[str]:
    """*template* as an anchored regex: literal text escaped, each placeholder a
    named non-greedy group (a repeated placeholder must repeat its value), and
    each scope optional with its delimiters (`segments`): absent at its first
    occurrence, it is absent at every later one."""
    parts: list[str] = ["^"]
    seen: set[str] = set()
    segs = segments(template)
    for i, seg in enumerate(segs):
        if isinstance(seg, _Lit):
            parts.append(re.escape(seg.text))
            continue
        name = seg.name if isinstance(seg, _Field) else "scope"
        pattern = _GROUPS.get(name, ".+?")
        nxt = segs[i + 1] if i + 1 < len(segs) else None
        opener = nxt.left.lstrip()[:1] if isinstance(nxt, _Scope) else ""
        if opener and name not in _GROUPS:
            # `{type}({scope})`: the type stops at the scope's bracket, so an
            # absent scope never lets it swallow one (`test(): x` is no subject).
            pattern = f"[^{re.escape(opener)}]+?"
        if name in seen:
            group = f"(?P={name})"
        else:
            seen.add(name)
            group = f"(?P<{name}>{pattern})"
        if isinstance(seg, _Field):
            parts.append(group)
            continue
        inner = f"{re.escape(seg.left)}{group}{re.escape(seg.right)}"
        parts.append(f"(?({name}){inner})" if group.startswith("(?P=") else f"(?:{inner})?")
    parts.append("$")
    return re.compile("".join(parts))


def parse_subject(template: str, subject: str) -> dict[str, str] | None:
    """The placeholder values *subject* was rendered from, or None if it was not.
    An absent scope has no key."""
    m = subject_regex(template).match(subject)
    if m is None:
        return None
    return {k: v for k, v in m.groupdict().items() if v is not None}


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
    from fr.artifacts.paths import artifact_root
    from fr.run.adopt import current_branch
    from fr.run.model import RUNS_REL, RunStateError, parse_run_state

    branch = current_branch(repo_root)
    runs = artifact_root(repo_root) / RUNS_REL
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
