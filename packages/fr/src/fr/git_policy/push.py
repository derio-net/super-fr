"""`fr push`'s engine (spec 2026-11-04-repo-feature-settings R12-R14).

What fr may push is the branch's UNPUSHED first-parent commits: those not on the
remote branch (read live with `ls-remote`, never only from a tracking ref that may
be stale) and not on any remote-tracking ref, which on a first push is the range
since the merge-base with the default ref. Nothing outside that range is ever
rewritten, so the push is always a fast-forward: no force flag exists here.

Under `git.history: squash-unpushed` the range is split into segments at every
merge commit and every `chore(fr): migrate …` commit (known by its `Fr-Commit:
migrate` trailer, or by its subject when it predates the trailer). Those are replayed as they
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

from fr.git_policy.templates import (
    fr_commit_kind,
    parse_subject,
    render_subject,
    subject_ok,
    template_for,
)
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
    """A `chore(fr): migrate …` commit: by its `Fr-Commit` trailer, which every
    template keeps (p4-r2); else, for a commit written before the trailer existed,
    by its subject, as written then or through a template naming type and scope."""
    kind = fr_commit_kind(commit.message)
    if kind is not None:
        return kind == "migrate"
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


def _is_fr_own(commit: Commit, values: Mapping[str, str]) -> bool:
    """fr's own commit: its `Fr-Commit` trailer, else (older commits) a parsed
    `chore`/`fr` type and scope."""
    if fr_commit_kind(commit.message) is not None:
        return True
    return (values.get("type"), values.get("scope")) == ("chore", "fr")


def _composed(settings: Settings, segment: Sequence[Commit], issue: int | None) -> str:
    """The subject of a squashed segment: the values of its first commit that is not
    fr's own bookkeeping (else its first commit), rendered through the templates."""
    commit_t = settings.git.commit
    parsed: list[tuple[Commit, dict[str, str]]] = []
    for c in segment:
        for template in (
            template_for(settings, issue),
            commit_t.without_issue,
            commit_t.with_issue,
        ):
            values = parse_subject(template, c.subject)
            if values is not None:
                parsed.append((c, values))
                break
    if not parsed:  # unreachable after check_subjects; never invent values
        raise PushRefusedError("no commit in a squash segment has a subject the template reads")
    chosen = next((v for c, v in parsed if not _is_fr_own(c, v)), parsed[0][1])
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


MAX_PUSH_ATTEMPTS = 3
"""Quiet's replay bound (R23): this many rejected pushes of `fr`, then a refusal."""

QUIET_BRANCH = "fr"


def _sha(root: Path, ref: str) -> str | None:
    done = run_git(root, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def fr_pending(root: Path, remote: str) -> bool:
    """Local `fr` holds commits `<remote>/fr` (as last fetched) does not."""
    local = _sha(root, f"refs/heads/{QUIET_BRANCH}")
    if local is None:
        return False
    tracking = _sha(root, f"refs/remotes/{remote}/{QUIET_BRANCH}")
    if tracking is None:
        return True
    return _git(root, "rev-list", "--count", f"{tracking}..{local}").strip() != "0"


def _replay(fr_root: Path, remote: str) -> None:
    """Fetch `<remote>/fr` and replay this checkout's own unpushed fr commits onto it.
    Features write disjoint paths, so the replay is clean; a conflict means the same
    path, which is refused naming it, with the worktree put back as it was."""
    from fr.placement.quiet import fr_worktree_problem

    problem = fr_worktree_problem(fr_root)
    if problem is not None:  # p3-r8: say what is wrong, never "the same path"
        raise PushRefusedError(f"cannot replay this feature's `{QUIET_BRANCH}` commits: {problem}")
    tracking = f"refs/remotes/{remote}/{QUIET_BRANCH}"
    _git(fr_root, "fetch", "--no-tags", remote, f"+refs/heads/{QUIET_BRANCH}:{tracking}")
    done = run_git(fr_root, ["rebase", "--no-autostash", tracking])
    if done.returncode == 0:
        return
    conflicted = run_git(fr_root, ["diff", "--name-only", "--diff-filter=U"]).stdout.split()
    run_git(fr_root, ["rebase", "--abort"])
    where = ", ".join(conflicted) or (done.stderr or done.stdout).strip()
    raise PushRefusedError(
        f"cannot replay this feature's `{QUIET_BRANCH}` commits onto {remote}/{QUIET_BRANCH}: "
        f"another push changed the same path ({where}). Each feature writes only its own "
        "path; resolve it on the fr worktree and push again"
    )


def atomic_push(root: Path, fr_root: Path, remote: str, branch: str, *, code: bool) -> list[str]:
    """Quiet's push (R23): the feature branch and `fr` in ONE `git push --atomic` when
    code moved, `fr` alone when only bookkeeping did. When `fr` is rejected because
    another feature moved it, fetch, replay, retry, at most `MAX_PUSH_ATTEMPTS` times.
    Never forced. The refs pushed, in order (empty: nothing was pending).

    Held under the fr worktree's lock (p3-r8): every workspace of the repo shares it."""
    from fr.placement.quiet import fr_worktree_lock
    from fr.settings import SettingsError

    try:
        with fr_worktree_lock(fr_root):
            return _atomic_push(root, fr_root, remote, branch, code=code)
    except SettingsError as e:
        raise PushRefusedError(str(e)) from e


def _atomic_push(root: Path, fr_root: Path, remote: str, branch: str, *, code: bool) -> list[str]:
    for _ in range(MAX_PUSH_ATTEMPTS):
        refs = ([branch] if code else []) + ([QUIET_BRANCH] if fr_pending(root, remote) else [])
        if not refs:
            return []
        argv = (
            ["push", "--atomic", "-u", remote, *refs]
            if len(refs) > 1
            else ["push", "-u", remote, *refs]
        )
        if any(a in FORCE_FLAGS for a in argv):  # unreachable; a last line of defence
            raise PushRefusedError(f"refusing a forced git call: git {' '.join(argv)}")
        done = run_git(root, argv)
        if done.returncode == 0:
            return refs
        detail = (done.stderr or done.stdout).strip()
        listed = run_git(root, ["ls-remote", "--heads", remote, f"refs/heads/{QUIET_BRANCH}"])
        words = listed.stdout.split()
        remote_fr = words[0] if words else None
        tracking = _sha(root, f"refs/remotes/{remote}/{QUIET_BRANCH}")
        if QUIET_BRANCH not in refs or listed.returncode != 0 or remote_fr == tracking:
            raise PushRefusedError(f"`git {' '.join(argv)}` failed: {detail}")
        _replay(fr_root, remote)
    raise PushRefusedError(
        f"{remote} rejected refs/heads/{QUIET_BRANCH} {MAX_PUSH_ATTEMPTS} times: it kept "
        "moving under other features' pushes. Nothing was forced; run `fr push` again"
    )
