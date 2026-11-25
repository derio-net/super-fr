"""A change to an existing configuration branch goes through a pull request (spec
2026-11-19-event-driven-a-la-carte §B; plan decision p2-config-changes-by-pr).

fr creates `fr-config` (stealth: `<branch>-config`) directly, at the migration and at
`fr settings init`. Every later change is reviewed, as a change to repo configuration is
under `repo`: fr commits it on a branch `fr-config-change/<slug>` cut from the
configuration branch's tip, pushes that branch, and opens a pull request into the
configuration branch through the forge client. Under stealth the pull request goes to the
TRACKING repo, never the target. The legacy copy (R6) is not written then: once the pull
request merges, the next fr read brings it in step (`fr.placement.quiet._read`).

The slug is the content's hash, so a retry of the same change reuses its branch and its
open pull request instead of opening a second one.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Final

from fr.settings import SettingsError

CHANGE_PREFIX: Final = "fr-config-change/"
"""The branch prefix of a pending configuration change (spec §B)."""

_TIMEOUT_S: Final = 60

OpenPr = Callable[[str, str, str, str, str], str]
"""(remote URL, head branch, base branch, title, body) -> the pull request's URL."""


def change_branch(rel: str, text: str) -> str:
    """`fr-config-change/<slug>`: the slug is a hash of the path and the bytes."""
    digest = hashlib.sha256(f"{rel}\0{text}".encode()).hexdigest()[:10]
    return f"{CHANGE_PREFIX}settings-{digest}"


def _forge_open_pr(remote: str, head: str, base: str, title: str, body: str) -> str:
    """The default `OpenPr`: the forge client for *remote*'s URL, reusing an open pull
    request whose head is *head*."""
    from fr._hosts import slug_from_url
    from fr.hostclient import FORGE_ERRORS, client_for_url

    slug = slug_from_url(remote) if "://" in remote or "@" in remote else None
    if not slug:
        raise SettingsError(
            f"fr cannot open a pull request on {remote}: it is no forge URL. The change is "
            f"pushed as `{head}`; open a pull request from it into `{base}` yourself"
        )
    try:
        client = client_for_url(remote)
        found = client.open_pr_for_head(slug, head)
        if found is not None:
            return str(found["url"])
        made = client.create_pr(slug, head=head, base=base, title=title, body=body, draft=False)
    except FORGE_ERRORS as e:
        raise SettingsError(
            f"fr pushed `{head}` but the forge refused the pull request into `{base}` "
            f"({str(e).strip()}); open it yourself"
        ) from e
    return str(made["url"])


open_pr: OpenPr = _forge_open_pr
"""The forge seam (tests replace it; nothing here calls a forge in a test)."""


def _run(cwd: Path, *args: str, env: dict[str, str] | None = None, stdin: str | None = None) -> str:
    from fr.git import git_argv

    done = subprocess.run(
        git_argv(cwd, *args),
        cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
    )
    if done.returncode != 0:
        raise SettingsError(
            f"`git {' '.join(args)}` failed: {(done.stderr or done.stdout).strip()}"
        )
    return done.stdout.strip()


def _commit_on(cwd: Path, base_sha: str, rel: str, text: str, message: str) -> str:
    """A commit whose parent is *base_sha* and whose tree is *base_sha*'s with *rel* =
    *text*, made with plumbing in a private index: no working tree is touched."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _run(cwd, "read-tree", base_sha, env=env)
        blob = _run(cwd, "hash-object", "-w", "--stdin", stdin=text)
        _run(cwd, "update-index", "--add", "--cacheinfo", f"100644,{blob},{rel}", env=env)
        tree = _run(cwd, "write-tree", env=env)
        return _run(cwd, "commit-tree", tree, "-p", base_sha, "-F", "-", stdin=message)


def open_change(
    cwd: Path,
    *,
    remote: str,
    base_branch: str,
    base_ref: str,
    rel: str,
    text: str,
    message: str,
) -> str:
    """Propose *rel* = *text* on *base_branch* (its last fetched tip *base_ref* in the
    clone *cwd*): commit it on `change_branch(rel, text)`, push that branch to origin
    (plain, never forced; a branch already holding the same change is reused), and open
    a pull request into *base_branch*. Returns the pull request's URL."""
    base_sha = _run(cwd, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    head = change_branch(rel, text)
    commit = _commit_on(cwd, base_sha, rel, text, message)
    pushed = subprocess.run(
        ["git", "push", "--quiet", "origin", f"{commit}:refs/heads/{head}"],
        cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
    )
    if pushed.returncode != 0 and not _already_proposed(cwd, head, rel, text):
        raise SettingsError(
            f"origin refused the push of `{head}`: "
            f"{(pushed.stderr or pushed.stdout or 'git push failed').strip()}. Nothing was "
            "forced; the configuration branch is unchanged"
        )
    subject = message.splitlines()[0] if message.strip() else f"chore(fr): change {rel}"
    body = (
        f"fr proposes this change to `{rel}` on `{base_branch}` (spec "
        "2026-11-19-event-driven-a-la-carte §B: every change to repo configuration after "
        "its creation is reviewed). Once it merges, the next fr command brings the copy "
        "older fr reads in step."
    )
    return open_pr(remote, head, base_branch, subject, body)


def _already_proposed(cwd: Path, head: str, rel: str, text: str) -> bool:
    """Origin's *head* already holds *rel* = *text* (a retry of the same change)."""
    fetched = subprocess.run(
        ["git", "-C", str(cwd), "fetch", "--quiet", "--no-tags", "origin", f"refs/heads/{head}"],
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
    )
    if fetched.returncode != 0:
        return False
    shown = subprocess.run(
        ["git", "-C", str(cwd), "show", f"FETCH_HEAD:{rel}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return shown.returncode == 0 and shown.stdout == text
