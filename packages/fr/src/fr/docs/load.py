"""Reading the config, the pages and the changed paths (spec 2026-11-11-docs-currency R1, R6, R8).

Read-only git only: `ls-files`, `merge-base`, `rev-parse`, `diff`. Never
`remote set-head`, never a fetch (R8). Anything git cannot answer is a
`DocsEnvError` (exit 2), never a silent pass.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from fr import git as fr_git
from fr.docs.globs import match
from fr.docs.model import DocsConfig, Page, PageError, parse_page

CONFIG_PATH = ".fr/docs.yaml"


class DocsEnvError(Exception):
    """A usage or environment error: bad config, no git, no base (exit 2)."""


def load_config(root: Path) -> DocsConfig | None:
    """The strict config, or None when the repo has no `.fr/docs.yaml` (R1)."""
    path = root / CONFIG_PATH
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return DocsConfig.model_validate(data)
    except (yaml.YAMLError, ValidationError, OSError, UnicodeDecodeError) as e:
        first = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        raise DocsEnvError(f"{CONFIG_PATH} is unusable: {first}") from e


def _git(root: Path, *args: str) -> str:
    try:
        done = fr_git.git_answer(root, *args)
    except fr_git.GitUnavailableError as e:
        raise DocsEnvError(str(e)) from e
    if done.returncode != 0:
        raise DocsEnvError(f"`git {' '.join(args)}` failed: {done.stderr.strip()}")
    return done.stdout


def tracked_files(root: Path) -> list[str]:
    """Every tracked path, repo-relative."""
    return sorted(p for p in _git(root, "ls-files", "-z").split("\0") if p)


def load_pages(
    root: Path, config: DocsConfig, tracked: list[str]
) -> tuple[list[Page], list[PageError]]:
    """The tracked files matching `pages`, parsed; unusable ones become errors."""
    pages: list[Page] = []
    errors: list[PageError] = []
    for path in tracked:
        if not any(match(g, path) for g in config.pages):
            continue
        try:
            text = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            errors.append(PageError(path, f"unreadable: {e}"))
            continue
        parsed = parse_page(path, text)
        (pages if isinstance(parsed, Page) else errors).append(parsed)  # type: ignore[arg-type]
    return pages, errors


def resolve_base(root: Path, base: str | None) -> str:
    """`--base` as given, else the remote default branch ref (read-only, no network)."""
    if base:
        if not fr_git.ref_exists(root, base):
            raise DocsEnvError(f"--base {base!r} does not resolve to a ref")
        return base
    found = fr_git.remote_default_ref(root)
    if isinstance(found, fr_git.GitRefusal):
        raise DocsEnvError(found.reason)
    if found is None:
        raise DocsEnvError(
            "cannot tell the default branch (no remote, or no origin/HEAD or "
            "origin/main|master|trunk|develop); pass --base <ref>"
        )
    return found


def on_default_branch(root: Path, default_ref: str) -> bool:
    """Whether HEAD is the local branch of `default_ref` (`origin/main` -> `main`).

    True there even with commits the remote does not have yet: R6 runs only the
    structural checks on the default branch itself, pushed or not. A detached
    HEAD is on no branch.
    """
    try:
        done = fr_git.git_answer(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    except fr_git.GitUnavailableError as e:
        raise DocsEnvError(str(e)) from e
    branch = done.stdout.strip() if done.returncode == 0 else ""
    return bool(branch) and branch == default_ref.partition("/")[2]


def merge_base_of(root: Path, base: str) -> str:
    """The merge base of `base` and HEAD, or a `DocsEnvError`."""
    try:
        return _git(root, "merge-base", base, "HEAD").strip()
    except DocsEnvError as e:
        raise DocsEnvError(f"no merge base between {base} and HEAD: {e}") from e


def changed_paths(root: Path, base: str) -> list[str] | None:
    """Paths changed from the merge base of `base` and HEAD to HEAD, both sides of a rename.

    None when HEAD *is* the merge base (HEAD is on the base branch): there is
    nothing to compare, so only the structural checks run (R6).
    """
    merge_base = merge_base_of(root, base)
    head = _git(root, "rev-parse", "HEAD").strip()
    if merge_base == head:
        return None
    raw = _git(root, "diff", "--name-status", "-M", "-z", f"{merge_base}...HEAD").split("\0")
    out: set[str] = set()
    i = 0
    while i < len(raw) and raw[i]:
        status = raw[i]
        width = 2 if status[0] in "RC" else 1
        out.update(p for p in raw[i + 1 : i + 1 + width] if p)
        i += 1 + width
    return sorted(out)
