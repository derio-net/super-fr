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

    def __init__(
        self,
        wrapped: Any,
        *,
        host: str = "github.com",
        backend: str = "github",
        ledger: Any = None,
    ) -> None:
        self._wrapped = wrapped
        self._host = host
        self._backend = backend
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
        return issue_url(self._backend, self._host, repo, number)


SAAS_HOSTS = {"github": "github.com", "gitlab": "gitlab.com"}


def issue_url(backend: str, host: str, repo: str, number: int) -> str:
    """An issue URL in the forge's own shape (GitLab's carries `/-/`), review p3-r10."""
    infix = "/-" if backend == "gitlab" else ""
    return f"https://{host}/{repo}{infix}/issues/{number}"


def forge_of(repo_root: Path) -> tuple[str, str]:
    """(backend, host) of the forge *repo_root*'s client talks to, resolved as the real
    client resolves it (`fr._hosts`): the service's host, else the SaaS default, else
    the origin's own hostname."""
    from fr import _hosts

    backend = str(_hosts.detect_backend(repo_root))
    host = (
        _hosts.host_for(repo_root)
        or SAAS_HOSTS.get(backend)
        or _hosts.origin_hostname(repo_root)
        or "github.com"
    )
    return backend, host


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


SCRATCH_GIT_CONFIG: tuple[str, ...] = ("-c", "core.hooksPath=/dev/null")
"""Every git call that builds or removes the scratch runs no hook of the repo's (a
post-checkout hook would run on `worktree add`, review p3-r7)."""


def _env() -> dict[str, str]:
    """The scratch's git environment: no LFS smudge, so `worktree add` downloads nothing."""
    return {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}


def _git(root: Path, *argv: str, stdin: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ["git", *SCRATCH_GIT_CONFIG, "-C", str(root), *argv],
        input=stdin,
        capture_output=True,
        check=False,
        env=_env(),
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


def _scratch_pid(path: Path) -> int | None:
    """The pid a scratch worktree's name carries, or None when *path* is no scratch."""
    suffix = path.name.removeprefix(SCRATCH_PREFIX)
    if suffix == path.name or not suffix.isdigit():
        return None
    try:
        if path.parent.resolve() != scratch_root():
            return None
    except OSError:
        return None
    return int(suffix)


def _remove(repo_root: Path, path: Path) -> None:
    """Remove the scratch worktree at *path* and its registration, and nothing else.

    Never a global `git worktree prune` (review p3-r2, pr1431-n1): in a devcontainer the
    host's other worktrees are not mounted, so a prune would deregister every one of
    them. The registration is cleared by its own path, as the quiet `fr` worktree's is."""
    from fr.placement.quiet import _forget_own_stale_entry

    subprocess.run(
        ["git", *SCRATCH_GIT_CONFIG, "-C", str(repo_root), "worktree", "remove", "--force"]
        + [str(path)],
        capture_output=True,
        check=False,
        env=_env(),
    )
    shutil.rmtree(path, ignore_errors=True)
    _forget_own_stale_entry(repo_root, path)


def prune_stale(repo_root: Path) -> None:
    """Remove each registered scratch worktree whose process is gone (a dry run killed
    before its `finally`), one by one, by its own path."""
    from fr.artifacts.paths import _common_dir

    common = _common_dir(Path(repo_root))
    if common is None:
        return
    for entry in sorted((common / "worktrees").glob("*")):
        try:
            recorded = Path((entry / "gitdir").read_text().strip())
        except OSError:
            continue
        wt = recorded.parent
        pid = _scratch_pid(wt)
        if pid is None or _alive(pid):
            continue
        _remove(repo_root, wt)


def _intent_to_add(repo_root: Path) -> list[str]:
    """The paths the index holds as intent-to-add (`git add -N`): a diff cannot carry
    that state, so the scratch marks them again (review p3-r6)."""
    out = _git(repo_root, "status", "--porcelain=v2", "-z", "--no-renames", "--untracked-files=no")
    found: list[str] = []
    for record in out.split(b"\0"):
        if not record.startswith(b"1 "):
            continue
        fields = record.split(b" ", 8)
        if len(fields) == 9 and fields[1] == b".A":
            found.append(os.fsdecode(fields[8]))
    return found


def _copy_untracked(repo_root: Path, path: Path) -> None:
    """Copy every untracked, non-ignored path by its bytes name (`-z`: a name git would
    quote, or one that is not UTF-8, review p3-r6). A nested repository is listed as its
    directory and is copied whole, so the scratch's `git status` sees it as the real
    checkout's does."""
    untracked = _git(repo_root, "ls-files", "-o", "--exclude-standard", "-z")
    for raw in untracked.split(b"\0"):
        if not raw:
            continue
        rel = os.fsdecode(raw.rstrip(b"/"))
        src, dst = repo_root / rel, path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir() and not src.is_symlink():
            shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst, follow_symlinks=False)


@contextmanager
def scratch_checkout(repo_root: Path) -> Iterator[Path]:
    """A detached worktree of HEAD carrying the checkout's staged changes, unstaged
    changes, intent-to-add entries and untracked files, with the staged/unstaged split
    kept so the dirty checks answer as they do in the real checkout. Ignored files are not
    copied. It is removed on exit, an exception included."""
    repo_root = repo_root.resolve()
    prune_stale(repo_root)
    path = scratch_root() / f"{SCRATCH_PREFIX}{os.getpid()}"
    if path.exists():
        _remove(repo_root, path)
    try:
        _git(repo_root, "worktree", "add", "-q", "--detach", str(path), "HEAD")
        apply = ("apply", "--binary", "--whitespace=nowarn")
        staged = _git(repo_root, "diff", "--cached", "--binary", "HEAD")
        if staged:
            _git(path, *apply, "--index", stdin=staged)
        unstaged = _git(repo_root, "diff", "--binary")
        if unstaged:
            _git(path, *apply, stdin=unstaged)
        intent = _intent_to_add(repo_root)
        if intent:
            _git(path, "add", "-N", "--", *intent)
        _copy_untracked(repo_root, path)
        yield path
    finally:
        _remove(repo_root, path)
