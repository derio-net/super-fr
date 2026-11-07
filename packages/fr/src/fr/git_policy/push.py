"""`fr push`'s engine (spec 2026-11-04-repo-feature-settings R12-R14).

What fr may push is the branch's UNPUSHED first-parent commits: those not on the
remote branch (read live with `ls-remote`, never only from a tracking ref that may
be stale) and not on any remote-tracking ref, which on a first push is the range
since the merge-base with the default ref. Nothing outside that range is ever
rewritten, so the push is always a fast-forward: no force flag exists here.

Under `git.history: squash-unpushed` the range is split into segments at every
merge commit and every `chore(fr): migrate …` commit. Those are replayed as they
are (`git commit-tree` with their own tree and parents, so each keeps its tree),
and each segment between them becomes one commit carrying the segment's last tree,
with a subject fr composes through the templates. The final tree never changes.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fr.git_policy.templates import parse_subject, render_subject, subject_ok, template_for
from fr.settings.model import Settings

FORCE_FLAGS = ("-f", "--force", "--force-with-lease", "--force-if-includes", "--mirror")
"""Never passed. `_git` refuses any argv carrying one, as a last line of defence."""

_TIMEOUT = 120


class PushRefusedError(Exception):
    """`fr push` will not push; the message names what and why."""


def run_git(
    cwd: Path,
    args: Sequence[str],
    env: Mapping[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """The one git runner `fr push` and `fr pr create` use (tests record its argv)."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        check=False,
    )


def _git(
    root: Path, *args: str, env: Mapping[str, str] | None = None, stdin: str | None = None
) -> str:
    if any(a in FORCE_FLAGS or a.startswith("--force") for a in args) or (
        args and args[0] == "push" and any(a.startswith("+") for a in args[1:])
    ):
        raise PushRefusedError(f"refusing a forced git call: git {' '.join(args)}")
    done = run_git(root, args, env, stdin)
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()
        raise PushRefusedError(f"`git {' '.join(args)}` failed: {detail}")
    return done.stdout


@dataclass(frozen=True)
class Commit:
    sha: str
    parents: tuple[str, ...]
    tree: str
    subject: str
    message: str
    author: dict[str, str]


def _commit(root: Path, sha: str) -> Commit:
    fmt = "%H%x00%P%x00%T%x00%an%x00%ae%x00%aI%x00%B"
    sha_, parents, tree, name, email, date, message = _git(
        root, "show", "-s", f"--format={fmt}", sha
    ).split("\x00", 6)
    message = message.rstrip("\n") + "\n"
    return Commit(
        sha=sha_,
        parents=tuple(parents.split()),
        tree=tree,
        subject=message.splitlines()[0] if message.strip() else "",
        message=message,
        author={
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_AUTHOR_DATE": date,
        },
    )


@dataclass(frozen=True)
class Range:
    """The unpushed first-parent commits, oldest first, and the remote branch's sha."""

    commits: tuple[Commit, ...]
    remote_sha: str | None


def unpushed(root: Path, remote: str, branch: str) -> Range:
    """The commits `fr push` may check and squash (see the module doc)."""
    listed = _git(root, "ls-remote", "--heads", remote, f"refs/heads/{branch}").split()
    remote_sha = listed[0] if listed else None
    exclude = [f"--remotes={remote}"]
    if remote_sha is not None:
        if run_git(root, ["cat-file", "-e", f"{remote_sha}^{{commit}}"]).returncode != 0:
            raise PushRefusedError(
                f"{remote}/{branch} is at {remote_sha[:12]}, which this clone does not have: "
                f"run `git fetch {remote}` and try again"
            )
        if run_git(root, ["merge-base", "--is-ancestor", remote_sha, "HEAD"]).returncode != 0:
            raise PushRefusedError(
                f"{remote}/{branch} ({remote_sha[:12]}) is not an ancestor of HEAD: the branch "
                "has diverged, and fr never force-pushes. Integrate the remote branch "
                "(merge or rebase onto it) and push again"
            )
        exclude.append(remote_sha)
    shas = _git(root, "rev-list", "--first-parent", "--reverse", "HEAD", "--not", *exclude).split()
    return Range(tuple(_commit(root, s) for s in shas), remote_sha)


def is_migration(settings: Settings, commit: Commit) -> bool:
    """A `chore(fr): migrate …` commit, as written today or through a template."""
    if commit.subject.startswith("chore(fr): migrate "):
        return True
    commit_t = settings.git.commit
    for template in (commit_t.without_issue, commit_t.with_issue):
        values = parse_subject(template, commit.subject)
        if (
            values is not None
            and values.get("type") == "chore"
            and values.get("scope") == "fr"
            and values.get("summary", "").startswith("migrate ")
        ):
            return True
    return False


def check_subjects(settings: Settings, commits: Sequence[Commit], issue: int | None) -> None:
    """R14: every unpushed non-merge commit's subject matches the template."""
    bad = [
        c
        for c in commits
        if not subject_ok(settings, c.subject, parents=len(c.parents), issue=issue)
    ]
    if bad:
        template = template_for(settings, issue)
        lines = "\n".join(f"  {c.sha[:12]} {c.subject}" for c in bad)
        raise PushRefusedError(
            f"{len(bad)} unpushed commit(s) do not match the commit template "
            f"{template!r} (git.commit.{'with' if issue is not None else 'without'}_issue):\n"
            f"{lines}\nReword them (e.g. `git commit --amend` on the last one, or an "
            "interactive rebase of unpushed commits) and push again"
        )


def _composed(settings: Settings, segment: Sequence[Commit], issue: int | None) -> str:
    """The subject of a squashed segment: the values of its first commit that is not
    fr's own bookkeeping (else its first commit), rendered through the templates."""
    commit_t = settings.git.commit
    parsed: list[dict[str, str]] = []
    for c in segment:
        for template in (
            template_for(settings, issue),
            commit_t.without_issue,
            commit_t.with_issue,
        ):
            values = parse_subject(template, c.subject)
            if values is not None:
                parsed.append(values)
                break
    if not parsed:  # unreachable after check_subjects; never invent values
        raise PushRefusedError("no commit in a squash segment has a subject the template reads")
    chosen = next(
        (v for v in parsed if (v.get("type"), v.get("scope")) != ("chore", "fr")), parsed[0]
    )
    # A template need not name every placeholder (`[{scope}] {summary}` has no type).
    subject = render_subject(
        settings,
        chosen.get("type", ""),
        chosen.get("scope", ""),
        chosen.get("summary", ""),
        issue,
    )
    folded = "\n".join(f"- {c.subject}" for c in segment)
    return f"{subject}\n\nSquashed by fr push (git.history: squash-unpushed) from:\n{folded}\n"


def squash(
    root: Path, settings: Settings, branch: str, commits: Sequence[Commit], issue: int | None
) -> str | None:
    """Rewrite the unpushed range (R13); the new head, or None when nothing changed."""
    if not commits:
        return None
    head = commits[-1].sha
    parent = commits[0].parents[0] if commits[0].parents else None
    if parent is None:
        raise PushRefusedError("refusing to squash a branch's root commit")
    segment: list[Commit] = []

    def flush(parent: str) -> str:
        if not segment:
            return parent
        if len(segment) == 1 and segment[0].parents[0] == parent:
            # One commit, parent unchanged: nothing to rewrite. It is still flushed:
            # a segment left behind would be folded again at the next flush (p4-r1).
            return segment.pop().sha
        message = _composed(settings, segment, issue)
        new = _git(
            root,
            "commit-tree",
            segment[-1].tree,
            "-p",
            parent,
            "-F",
            "-",
            env=segment[0].author,
            stdin=message,
        ).strip()
        segment.clear()
        return new

    for c in commits:
        if len(c.parents) > 1 or is_migration(settings, c):
            parent = flush(parent)
            if c.parents[0] == parent:
                parent = c.sha
                continue
            others = [p for q in c.parents[1:] for p in ("-p", q)]
            parent = _git(
                root,
                "commit-tree",
                c.tree,
                "-p",
                parent,
                *others,
                "-F",
                "-",
                env=c.author,
                stdin=c.message,
            ).strip()
        else:
            segment.append(c)
    parent = flush(parent)
    if parent == head:
        return None
    if _git(root, "rev-parse", f"{parent}^{{tree}}").strip() != commits[-1].tree:
        raise PushRefusedError("the squash would change the final tree; nothing was rewritten")
    _git(
        root,
        "update-ref",
        "-m",
        "fr push: squash-unpushed",
        f"refs/heads/{branch}",
        parent,
        head,
    )
    return parent


def push(root: Path, remote: str, branch: str) -> None:
    """`git push -u <remote> <branch>`: a fast-forward, never forced."""
    _git(root, "push", "-u", remote, branch)
