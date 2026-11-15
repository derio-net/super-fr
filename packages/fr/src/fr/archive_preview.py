"""What `fr archive --dry-run` runs against (spec 2026-11-15-owed-archive-side-effects
R10, R11, design §C).

The archive writes the product checkout from many helpers, so a flag threaded through
each would leave every future write a chance to forget it. The dry run therefore runs
the REAL command against a disposable copy of the checkout (`scratch_checkout`) with a
forge (`PreviewForge`) that reads through and records every write instead of making it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCRATCH_PREFIX = "fr-archive-dry-run-"

# Every `GhClient` method is in exactly one set (a test pins it): a method the protocol
# gains later must be classified here before a dry run can use it.
READS = frozenset(
    {
        "view_issue",
        "list_linked_prs",
        "pr_status_by_url",
        "pr_body",
        "list_open_issues_with_body",
        "file_exists",
        "list_dir",
        "read_file",
        "list_issue_comments",
        "list_prs_by_head",
        "prs_for_commit",
        "ref_kind",
        "pr_view",
        "label_exists",
        "pr_required_checks",
        "pr_checks",
        "commit_checks",
        "required_check_names",
        "base_rules",
        "open_pr_for_head",
        "pr_queue_state",
        "open_pr_in_repo",
        "authenticated_login",
        "closing_ref",
        "repo_merge_methods",
        "list_repos",
        "list_issues",
        "list_prs",
        "list_open_prs",
        "list_merged_prs_by_label",
        "read_file_at_ref",
        "latest_release",
        "viewer_login",
        "rate_limit",
        "probe",
        "view_issue_record",
        "default_branch",
        "pr_for_branch",
        "issues_enabled",
        "repo_visibility",
        "pages_visibility",
    }
)
WRITES = frozenset(
    {
        "edit_issue_labels",
        "edit_pr_labels",
        "comment_pr",
        "edit_issue_state",
        "edit_issue_body",
        "comment_issue",
        "edit_issue",
        "close_issue",
        "create_issue",
        "ensure_labels",
        "edit_issue_comment",
        "pr_ready",
        "pr_merge",
        "pr_enqueue",
        "pr_dequeue",
        "pr_create",
        "create_pr",
        "close_pr",
        "edit_pr",
        "delete_branch",
        "dispatch_workflow",
    }
)

FIRST_PREVIEW_NUMBER = 900000


class PreviewForge:
    """The forge a dry run sees: allowlisted reads go to the wrapped client; known writes
    are recorded and never made; a method in neither set is recorded as REFUSED, so the
    dry run exits 1 naming it rather than guessing it was harmless."""

    def __init__(self, wrapped: Any, *, host: str = "github.com", ledger: Any = None) -> None:
        self._wrapped = wrapped
        self._host = host
        self._ledger = ledger if ledger is not None else PreviewLedger()

    @property
    def writes(self) -> list[str]:
        return self._ledger.writes

    @property
    def refused(self) -> list[str]:
        return self._ledger.refused

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in READS:
            return getattr(self._wrapped, name)
        if name == "create_issue":
            return self._create_issue
        if name in WRITES:
            return lambda *a, **k: self._record(name, a, k)
        return lambda *a, **k: self._refuse(name)

    def _record(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        head = ", ".join(repr(a) for a in args[:2])
        title = kwargs.get("title")
        self._ledger.writes.append(f"{name}({head}{', ' if head and title else ''}{title or ''})")

    def _refuse(self, name: str) -> None:
        self._ledger.refused.append(name)

    def _create_issue(self, repo: str, *, title: str, body: str, labels: frozenset[str]) -> str:
        number = self._ledger.take_number()
        self._record("create_issue", (repo,), {"title": title})
        return f"https://{self._host}/{repo}/issues/{number}"


class PreviewLedger:
    """What a dry run's forges recorded, shared by every `PreviewForge` of one run."""

    def __init__(self) -> None:
        self.writes: list[str] = []
        self.refused: list[str] = []
        self._next = FIRST_PREVIEW_NUMBER

    def take_number(self) -> int:
        n = self._next
        self._next += 1
        return n


# --- the scratch checkout -----------------------------------------------------------


def scratch_root() -> Path:
    return Path(tempfile.gettempdir()).resolve()


def _git(root: Path, *argv: str, stdin: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), *argv], input=stdin, capture_output=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(argv)} failed: {proc.stderr.decode(errors='replace').strip()}"
        )
    return proc.stdout


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def prune_stale(repo_root: Path) -> None:
    """Remove scratch worktrees whose process is gone (a dry run killed before its
    `finally`), after `git worktree prune` has forgotten the ones already deleted."""
    subprocess.run(["git", "-C", str(repo_root), "worktree", "prune"], capture_output=True)
    listing = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    for line in listing.splitlines():
        if not line.startswith("worktree "):
            continue
        path = Path(line.removeprefix("worktree "))
        suffix = path.name.removeprefix(SCRATCH_PREFIX)
        if path.parent != scratch_root() or suffix == path.name or not suffix.isdigit():
            continue
        if _alive(int(suffix)):
            continue
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(path)],
            capture_output=True,
        )
        shutil.rmtree(path, ignore_errors=True)
    subprocess.run(["git", "-C", str(repo_root), "worktree", "prune"], capture_output=True)


@contextmanager
def scratch_checkout(repo_root: Path) -> Iterator[Path]:
    """A detached worktree of HEAD carrying the checkout's staged changes, unstaged
    changes and untracked files, with the staged/unstaged split kept so the dirty
    checks answer as they do in the real checkout. Ignored files are not copied. It is
    removed on exit, an exception included."""
    repo_root = repo_root.resolve()
    prune_stale(repo_root)
    path = scratch_root() / f"{SCRATCH_PREFIX}{os.getpid()}"
    if path.exists():
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(path)],
            capture_output=True,
        )
        shutil.rmtree(path, ignore_errors=True)
    try:
        _git(repo_root, "worktree", "add", "-q", "--detach", str(path), "HEAD")
        staged = _git(repo_root, "diff", "--cached", "--binary", "HEAD")
        if staged:
            _git(path, "apply", "--index", "--binary", stdin=staged)
        unstaged = _git(repo_root, "diff", "--binary")
        if unstaged:
            _git(path, "apply", "--binary", stdin=unstaged)
        untracked = _git(repo_root, "ls-files", "-o", "--exclude-standard", "-z")
        for rel in filter(None, untracked.decode().split("\0")):
            dst = path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo_root / rel, dst, follow_symlinks=False)
        yield path
    finally:
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(path)],
            capture_output=True,
        )
        shutil.rmtree(path, ignore_errors=True)
        subprocess.run(["git", "-C", str(repo_root), "worktree", "prune"], capture_output=True)
