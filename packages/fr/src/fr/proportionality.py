"""`fr plan proportionality` — compare a delivered diff with its plan
(2026-09-24 fr-goal-scope-proportion-cost spec §C, gh#597 §4).

**Report first, never a gate.** Nothing here blocks: the report is text, the
command always exits 0, and `fr run resolve --step deliver` stores only its
hash. Whether any section should become a gate is a later decision, made with
real runs' reports in hand — a heuristic promoted to a gate before anyone has
read its output is how false positives become policy.

The diff is taken from `git merge-base HEAD <base>` to `HEAD`: the merge-base,
not the base tip, because commits landing on the base after the branch forked
are not this branch's touches. Everything is read at committed `HEAD` — the
diff, the plan's phase headers and the plan journal — and the first line
names only the merge-base SHA, never the base's remote name, so the same
`HEAD` yields the same bytes in any clone: `deliver` hashes them.

Three sections, each a heuristic that names candidates for a human to judge:

1. **Unreferenced new files** — an added file whose repo-relative path, stem
   (at least 4 characters) or branch-created parent directory appears, as a
   whole word, in no other tracked file. Modules a test runner discovers by
   name (`test_*.py`, `*_test.py`, `conftest.py`) are skipped.
   The observed failure (gh#597) was a scratch fixture nothing loaded.
2. **Out-of-plan touches** — a changed file matching no phase's `files` glob
   (`*` spans `/`, as in `.fr-isolation-allow`), "justified" when a journal
   finding or recorded deviation names its path.
3. **Size** — added plus deleted lines against the summed `estimate_lines`,
   flagged above 2x.

fr's own artifacts (`docs/superpowers/**`, `docs/acceptance/**`) are exempt
everywhere: as candidates, because a plan, journal or run is bookkeeping the
estimate never covered; and as *referencers*, because a journal that narrates
"added x.json" does not make anything load it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from fr.git import GitRefusal, GitUnavailableError, git_answer, remote_default_ref
from fr.plan_validator_wrapper import WRAPPER_REL

if TYPE_CHECKING:
    from fr.journal.model import JournalEntry
    from fr.parser import Plan
    from fr.types import PhaseHeader

EXEMPT_PREFIXES = ("docs/superpowers/", "docs/acceptance/", WRAPPER_REL.as_posix())
"""fr's own artifacts: spec, plan, journals, runs, acceptance matrix + reports,
and the validator wrapper `fr plan create` installs on a repo's first plan."""

MIN_STEM_CHARS = 4
"""Shorter stems (`app`, `cli`, `io`) match half a repo by accident."""

SIZE_FLAG_RATIO = 2


@dataclass(frozen=True)
class Report:
    """`merge_base` is None exactly when no base could be established — the
    text is then the single line naming `--base`."""

    merge_base: str | None
    text: str


@dataclass(frozen=True)
class _Change:
    path: str
    status: str  # git's name-status letter: A, M, D, T
    added: int
    deleted: int


def build_report(repo_root: Path, plan: Plan, base: str | None) -> str:
    """The report text for `plan`'s branch at `repo_root`'s HEAD."""
    return run_report(repo_root, plan, base).text


def run_report(repo_root: Path, plan: Plan, base: str | None) -> Report:
    """`build_report`, keeping the merge-base SHA for `deliver`'s evidence."""
    try:
        return _run(repo_root, plan, base)
    except GitUnavailableError as e:
        return Report(
            None, f"proportionality: git could not answer ({e}); retry, or pass --base <ref>.\n"
        )


def _run(repo_root: Path, plan: Plan, base: str | None) -> Report:
    if base is None:
        found = remote_default_ref(repo_root)
        if found is None or isinstance(found, GitRefusal):
            why = found.reason if isinstance(found, GitRefusal) else "no remote default branch"
            return Report(
                None,
                f"proportionality: could not determine a base ({why}); pass --base <ref>.\n",
            )
        base = found
    mb = git_answer(repo_root, "merge-base", "HEAD", base)
    if mb.returncode != 0 or not mb.stdout.strip():
        return Report(
            None,
            f"proportionality: no merge-base between HEAD and {base!r}; pass --base <ref>.\n",
        )
    merge_base = mb.stdout.strip()

    phases = _phases_at_head(repo_root, plan)
    if phases is None:
        return Report(
            None,
            f"proportionality: the plan {_rel(repo_root, plan.dir)} is not committed at "
            "HEAD; commit it, then rerun.\n",
        )
    changes = [c for c in _changes(repo_root, merge_base) if not _exempt(c.path)]
    globs = [g for ph in phases for g in ph.files]
    estimates = [ph.estimate_lines for ph in phases if ph.estimate_lines is not None]

    # Only the SHA, never the base's name: `origin/main` in one clone is
    # `upstream/main` in another, and deliver hashes these bytes.
    lines = [f"proportionality: merge-base {merge_base}", ""]
    lines += ["## Unreferenced new files", ""]
    lines += _bullets(_unreferenced(repo_root, merge_base, changes))
    lines += ["", "## Out-of-plan touches", ""]
    if not globs:
        lines.append("no phase declares `files`; out-of-plan touches cannot be checked.")
    else:
        lines += _bullets(_out_of_plan(changes, globs, _justifiers(repo_root, plan)))
    lines += ["", "## Size", ""]
    lines += _size(changes, sum(estimates) if estimates else None)
    return Report(merge_base, "\n".join(lines) + "\n")


def _changes(repo_root: Path, merge_base: str) -> list[_Change]:
    """name-status and numstat of `merge_base..HEAD`, joined on path.

    `-z` so a path with spaces or non-ASCII survives unquoted; `--no-renames`
    so a rename is its honest delete + add (the add is a new file to check).
    """
    status_raw = _git_out(
        repo_root, "diff", "-z", "--no-renames", "--name-status", merge_base, "HEAD"
    )
    tokens = status_raw.split("\0")
    status = {tokens[i + 1]: tokens[i] for i in range(0, len(tokens) - 1, 2) if tokens[i]}
    counts: dict[str, tuple[int, int]] = {}
    numstat_raw = _git_out(repo_root, "diff", "-z", "--no-renames", "--numstat", merge_base, "HEAD")
    for record in numstat_raw.split("\0"):
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        # A binary file reports `-` for both; it has no lines to count.
        counts[path] = (int(added) if added != "-" else 0, int(deleted) if deleted != "-" else 0)
    return [_Change(path, status[path], *counts.get(path, (0, 0))) for path in sorted(status)]


def _unreferenced(repo_root: Path, merge_base: str, changes: list[_Change]) -> list[str]:
    """Needles, matched as whole words (`data` is not in `metadata`): the
    path, the stem when long enough, and every parent directory the BRANCH
    created — fixtures are loaded by globbing their directory, and a reference
    to a new directory is a reference to what is in it. A pre-existing parent
    (`src`, `tests/unit`) is named all over any repo for unrelated reasons, so
    counting it would pass every new file beneath it."""
    out: list[str] = []
    new_dirs: dict[str, bool] = {}
    for c in changes:
        if c.status != "A" or _runner_discovered(c.path):
            continue
        needles = [c.path]
        pure = PurePosixPath(c.path)
        if len(pure.stem) >= MIN_STEM_CHARS:
            needles.append(pure.stem)
        for parent in pure.parents:
            d = str(parent)
            if d == ".":
                break
            if d not in new_dirs:
                existed = git_answer(repo_root, "cat-file", "-e", f"{merge_base}:{d}")
                new_dirs[d] = existed.returncode != 0
            if new_dirs[d]:
                needles.append(d)
        if not _referenced_elsewhere(repo_root, c.path, needles):
            out.append(c.path)
    return out


RUNNER_DISCOVERED = ("test_*.py", "*_test.py", "conftest.py")
"""Basenames a test runner loads by convention (pytest's defaults): nothing
names them, so "unreferenced" is their normal state, not a signal (review
p3-f1 — on this feature's own branch they were every line of the section)."""


def _runner_discovered(path: str) -> bool:
    name = PurePosixPath(path).name
    return any(fnmatchcase(name, pattern) for pattern in RUNNER_DISCOVERED)


def _referenced_elsewhere(repo_root: Path, path: str, needles: list[str]) -> bool:
    args = ["grep", "-l", "-z", "-F", "-w"]
    for n in needles:
        args += ["-e", n]
    args += ["HEAD", "--", "."] + [f":(exclude){p}" for p in EXEMPT_PREFIXES]
    res = git_answer(repo_root, *args)
    # `git grep` exits 1 for "no match" — an answer. Anything above 1 is git
    # failing, and reading it as "no match" would list the file on no evidence.
    if res.returncode > 1:
        raise GitUnavailableError(f"`git grep` failed: {res.stderr.strip()}")
    hits = [h.removeprefix("HEAD:") for h in res.stdout.split("\0") if h]
    return any(h != path for h in hits)


def _out_of_plan(
    changes: list[_Change], globs: list[str], justifiers: list[JournalEntry]
) -> list[str]:
    out: list[str] = []
    for c in changes:
        if any(fnmatchcase(c.path, g) for g in globs):
            continue
        ids = [e.id for e in justifiers if c.path in e.title or c.path in e.body]
        out.append(f"{c.path} — justified by {', '.join(ids)}" if ids else c.path)
    return out


def _justifiers(repo_root: Path, plan: Plan) -> list[JournalEntry]:
    """Plan-journal entries that can justify an out-of-plan touch: findings
    (a reviewer asked for the change) and decisions recorded as deviations
    (the fr-execute convention: a `DEVIATION` title). A missing journal
    justifies nothing; an unreadable one is left to `fr journal check`."""
    from fr.journal.model import (
        JournalParseError,
        archived_journal_path,
        journal_path,
        parse_journal,
    )

    slug = plan.meta.plan
    text = None
    for path in (
        journal_path(repo_root, "plan", slug),
        archived_journal_path(repo_root, "plan", slug),
    ):
        text = _show_head(repo_root, _rel(repo_root, path))
        if text is not None:
            break
    if text is None:
        return []
    try:
        entries = parse_journal(text)
    except (JournalParseError, ValueError):
        return []
    return [
        e
        for e in entries
        if e.kind == "finding" or (e.kind == "decision" and "deviation" in e.title.casefold())
    ]


def _phases_at_head(repo_root: Path, plan: Plan) -> list[PhaseHeader] | None:
    """The plan's phase headers as committed at HEAD — None when HEAD has no
    phase file for it. Read from HEAD, not the parsed working-tree `plan`, so
    the report is a pure function of HEAD (review p3-f4): an uncommitted edit
    must not change the bytes `deliver` hashes."""
    import yaml

    from fr.types import PhaseHeader

    rel = _rel(repo_root, plan.dir)
    listing = git_answer(repo_root, "ls-tree", "-z", "--name-only", "HEAD", "--", f"{rel}/")
    names = sorted(
        n for n in listing.stdout.split("\0") if re.fullmatch(r"\d{2}\.yaml", PurePosixPath(n).name)
    )
    headers: list[PhaseHeader] = []
    for name in names:
        text = _show_head(repo_root, name)
        if text is None:
            continue
        headers.append(PhaseHeader.model_validate(yaml.safe_load(text)["phase"]))
    return headers or None


def _show_head(repo_root: Path, rel: str) -> str | None:
    res = git_answer(repo_root, "show", f"HEAD:{rel}")
    return res.stdout if res.returncode == 0 else None


def _rel(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _size(changes: list[_Change], estimate: int | None) -> list[str]:
    added = sum(c.added for c in changes)
    deleted = sum(c.deleted for c in changes)
    total = added + deleted
    counted = f"{total} lines changed (+{added} -{deleted}; fr artifacts excluded)"
    if estimate is None:
        return [f"{counted}; no phase declares `estimate_lines`."]
    if estimate == 0:
        ratio = "" if total == 0 else " — no ratio against a zero estimate"
        head = f"{counted} against an estimate of 0{ratio}."
    else:
        head = f"{counted} against an estimate of {estimate} ({total / estimate:.1f}×)."
    out = [head]
    if total > SIZE_FLAG_RATIO * estimate:
        out.append(
            f"FLAG: above {SIZE_FLAG_RATIO}× the estimate — add a justification line "
            f"to the PR body."
        )
    return out


def _exempt(path: str) -> bool:
    return path.startswith(EXEMPT_PREFIXES)


def _bullets(items: list[str]) -> list[str]:
    return [f"- {i}" for i in items] if items else ["none."]


def _git_out(repo_root: Path, *args: str) -> str:
    """stdout of a git call whose failure leaves no report to give — raised
    as `GitUnavailableError` so `run_report` turns it into its one line."""
    res = git_answer(repo_root, *args)
    if res.returncode != 0:
        raise GitUnavailableError(f"`git {' '.join(args)}` failed: {res.stderr.strip()}")
    return res.stdout
