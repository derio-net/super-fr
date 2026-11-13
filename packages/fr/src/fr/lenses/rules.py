"""Path rules in force (spec 2026-11-12-review-lenses R6, §3.A).

The rules in force are the union of `.fr/lenses.yaml`'s `require:` on the default
branch and on the branch, the rule `fr.run.ci_evidence.declared_gates` follows for
`.fr/ci.yaml`: a branch can add a rule and use it, and cannot drop one its base
holds. With no remote, the branch's rules are the rules in force; a remote whose
default branch cannot be read here is a refusal, never "no rules".
A glob matches with `fnmatchcase`, so `*` spans `/` as in `fr.proportionality`.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from fr.git import GitRefusal, GitUnavailableError, git_answer, remote_default_ref, remote_name
from fr.lenses.model import LensError, PathRule, parse_config, read_text
from fr.lenses.resolve import REPO_CONFIG_REL


@dataclass(frozen=True)
class RuleMatch:
    """Why a rule requires a lens: the rule's globs and one changed file they match."""

    lens: str
    paths: tuple[str, ...]
    file: str | None
    """None when there was no diff to match and the rule applied anyway."""


def rules_in_force(base_text: str | None, head_text: str | None) -> tuple[PathRule, ...]:
    """The base's rules then the branch's, a rule both hold once. `None` is no file.
    Raises `LensError` when either text is not a valid lens config."""
    found: list[PathRule] = []
    for text, source in ((base_text, "default branch"), (head_text, "branch")):
        if text is None:
            continue
        for rule in parse_config(text, source=f"{REPO_CONFIG_REL} on the {source}").require:
            if rule not in found:
                found.append(rule)
    return tuple(found)


def matched(rules: tuple[PathRule, ...], changed: list[str]) -> dict[str, RuleMatch]:
    """Per required lens, the first rule (in force order) that a changed file matches
    and the first such file (in `changed` order)."""
    out: dict[str, RuleMatch] = {}
    for rule in rules:
        hit = next((f for f in changed if any(fnmatchcase(f, g) for g in rule.paths)), None)
        if hit is None:
            continue
        for lens in rule.lenses:
            out.setdefault(lens, RuleMatch(lens=lens, paths=rule.paths, file=hit))
    return out


def every_rule(rules: tuple[PathRule, ...]) -> dict[str, RuleMatch]:
    """Every lens any rule requires, with no file: what applies when there is no diff
    to match (a repo with no remote), so that no rule is skipped for want of one."""
    out: dict[str, RuleMatch] = {}
    for rule in rules:
        for lens in rule.lenses:
            out.setdefault(lens, RuleMatch(lens=lens, paths=rule.paths, file=None))
    return out


def default_ref(root: Path) -> str | None:
    """The default branch as a remote-tracking ref, or None when there is no remote
    (or no git checkout). Raises `LensError` when there is a remote whose default
    branch cannot be read here: its rules are then unknown, which is not "none"."""
    try:
        ref = remote_default_ref(root)
        if isinstance(ref, str):
            return ref
        inside = git_answer(root, "rev-parse", "--is-inside-work-tree")
        remote = None if isinstance(ref, GitRefusal) else remote_name(root)
    except GitUnavailableError as e:
        raise LensError(f"git could not read the default branch: {e}") from e
    if inside.returncode != 0:
        return None
    if isinstance(ref, GitRefusal):
        raise LensError(f"cannot tell the default branch, so its path rules: {ref.reason}")
    if remote is None:
        return None
    raise LensError(
        f"remote {remote} has no default branch ref in this checkout, so its path rules "
        f"cannot be read; run `git fetch {remote}` (a shallow or single-ref checkout "
        "needs the default branch fetched)"
    )


def base_config_text(root: Path, ref: str | None) -> str | None:
    """`.fr/lenses.yaml` as the default branch `ref` holds it; None for no ref or no file."""
    if ref is None:
        return None
    rel = REPO_CONFIG_REL.as_posix()
    try:
        listed = git_answer(root, "ls-tree", "--name-only", ref, "--", rel)
        if listed.returncode == 0 and not listed.stdout.strip():
            return None  # the ref is readable and holds no such file
        res = listed if listed.returncode != 0 else git_answer(root, "show", f"{ref}:{rel}")
    except GitUnavailableError as e:
        raise LensError(f"git could not read {REPO_CONFIG_REL} on {ref}: {e}") from e
    if res.returncode != 0:
        # Unreadable is not absent: reading it as "no rules" would let a branch
        # drop a rule its base holds.
        raise LensError(
            f"git could not read {REPO_CONFIG_REL} on {ref}: "
            + (res.stderr.strip() or f"exit {res.returncode}")
        )
    return res.stdout


def head_config_text(root: Path) -> str | None:
    """The branch's `.fr/lenses.yaml`, read from the working tree as every other lens
    setting is (§3.A); None when there is no file."""
    path = root / REPO_CONFIG_REL
    return read_text(path, str(REPO_CONFIG_REL)) if path.is_file() else None


def rules_in_force_at(root: Path) -> tuple[PathRule, ...]:
    """The rules in force for the repo at `root`. Raises `LensError`."""
    return rules_in_force(base_config_text(root, default_ref(root)), head_config_text(root))
