"""The forge and git ports of `fr gate backfill` (spec 2026-11-01-gate-backfill §A).

`BackfillForge` is the reads the engine needs, over one repo; `ClientBackfillForge` adapts the
`GhClient` (the one adapter fr talks to a forge through). `Git` is the one place this package
runs a subprocess.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Protocol

from fr.debt.forge import ClientDebtForge
from fr.ghclient import GhClient

OPEN_ISSUE_FIELDS = "number,title,body,labels,author"  # archive_followups.OWED_ISSUE_FIELDS + title
OPEN_ISSUE_LIMIT = 500
_PULL_URL = re.compile(r"/(?:pull|pulls|merge_requests|-/merge_requests)/(\d+)")


class BackfillForge(Protocol):
    """A `DebtForge` (`pr_for_branch`, `owed_issues`) plus the reads of C and B."""

    def pr_for_branch(self, branch: str) -> dict[str, Any] | None: ...

    def owed_issues(self) -> list[dict[str, Any]]: ...

    def open_issues(self) -> list[dict[str, Any]]:
        """Every open issue as `{ref, number, title, body, labels}` (capped, never silently)."""
        ...

    def viewer_login(self) -> str:
        """The login fr acts as: only issues it wrote can be its trackers (R8)."""
        ...

    def pr_view(self, number: int) -> dict[str, Any]: ...

    def prs_by_head(self, branch: str) -> list[dict[str, Any]]: ...

    def linked_prs(self, issue: int) -> list[dict[str, Any]]: ...

    def prs_for_commit(self, sha: str) -> list[dict[str, Any]]: ...


def pr_number_of(record: dict[str, Any]) -> int | None:
    """A PR record's number: its `number`, else the tail of its `url`."""
    n = record.get("number")
    if isinstance(n, int) and not isinstance(n, bool):
        return n
    m = _PULL_URL.search(str(record.get("url") or ""))
    return int(m.group(1)) if m else None


class ClientBackfillForge(ClientDebtForge):
    def __init__(self, client: GhClient, *, cwd: Path, repo: str) -> None:
        super().__init__(client, cwd=cwd, repo=repo)

    def open_issues(self) -> list[dict[str, Any]]:
        raw = self._client.list_issues(self._repo, "open", OPEN_ISSUE_LIMIT, OPEN_ISSUE_FIELDS)
        out = []
        for i in raw:
            labels = [
                str(lab.get("name", "")) if isinstance(lab, dict) else str(lab)
                for lab in i.get("labels") or []
            ]
            out.append(
                {
                    "ref": f"{self._repo}#{i.get('number')}",
                    "number": i.get("number"),
                    "title": str(i.get("title") or ""),
                    "body": str(i.get("body") or ""),
                    "labels": labels,
                    "author": i.get("author"),
                }
            )
        return out

    def viewer_login(self) -> str:
        return self._client.viewer_login()

    def pr_view(self, number: int) -> dict[str, Any]:
        return self._client.pr_view(self._repo, number)

    def prs_by_head(self, branch: str) -> list[dict[str, Any]]:
        return self._client.list_prs_by_head(self._repo, branch)

    def linked_prs(self, issue: int) -> list[dict[str, Any]]:
        return self._client.list_linked_prs(self._repo, issue)

    def prs_for_commit(self, sha: str) -> list[dict[str, Any]]:
        return self._client.prs_for_commit(self._repo, sha)


class Git:
    """The git reads of the evidence chain, over one checkout. Every method returns `None` (or
    an empty answer) when git cannot say, never raises."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lines: dict[str, list[str]] = {}

    def _run(self, *args: str) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None

    def _out(self, *args: str) -> str | None:
        done = self._run(*args)
        return done.stdout if done is not None and done.returncode == 0 else None

    def first_add(self, ref: str, *paths: str) -> str | None:
        """The oldest commit on *ref* that added a file under any of *paths*."""
        out = self._out("log", "--diff-filter=A", "--format=%H", "--reverse", ref, "--", *paths)
        shas = (out or "").split()
        return shas[0] if shas else None

    def first_containing(self, ref: str, sha: str) -> str | None:
        """The oldest commit on *ref*'s first-parent line that contains *sha*: *sha* itself for a
        squash or fast-forward, else the merge that brought its branch in. Containment is
        monotone along that line, so it is found by bisection."""
        if ref not in self._lines:
            out = self._out("rev-list", "--first-parent", "--reverse", ref)
            self._lines[ref] = (out or "").split()
        line = self._lines[ref]
        if not line:
            return None
        lo, hi = 0, len(line) - 1
        if not self._contains(line[hi], sha):
            return None
        while lo < hi:
            mid = (lo + hi) // 2
            if self._contains(line[mid], sha):
                hi = mid
            else:
                lo = mid + 1
        return line[lo]

    def _contains(self, commit: str, sha: str) -> bool:
        done = self._run("merge-base", "--is-ancestor", sha, commit)
        return done is not None and done.returncode == 0

    def subject(self, sha: str) -> str:
        return (self._out("log", "-1", "--format=%s", sha) or "").strip()

    def files(self, sha: str) -> list[str] | None:
        """The paths *sha* changed against its first parent; `None` when it has none."""
        out = self._out("diff", "--name-only", f"{sha}^1", sha)
        return None if out is None else out.split()

    def last_commit(self, ref: str, path: str) -> str | None:
        """ISO committer date of the last commit on *ref* touching *path*."""
        out = (self._out("log", "-1", "--format=%cI", ref, "--", path) or "").strip()
        return out or None
