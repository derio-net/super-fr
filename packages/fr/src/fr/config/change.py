"""A change to an existing configuration branch goes through a pull request (spec
2026-11-19-event-driven-a-la-carte §B; plan decision p2-config-changes-by-pr).

fr creates `fr-config` (stealth: `<branch>-config`) directly, at the migration and at
`fr settings init`. Every later change is reviewed, as a change to repo configuration is
under `repo`: fr commits it on a branch `fr-config-change/<slug>` cut from the
configuration branch's tip, pushes that branch, and opens a pull request into the
configuration branch through the forge client. Under stealth the pull request goes to the
TRACKING repo, never the target. The legacy copy (R6) is not written then: once the pull
request merges, the next fr read brings it in step (`fr.placement.quiet._read`).

The branch names the change's kind and the content's hash (`fr-config-change/<kind>-<hash>`),
so a retry of the same change reuses its branch. A change whose pull request is already
open is not proposed again (its URL is the answer), and one whose pull request was closed
unmerged refuses once, naming it, until the operator asks for it again with
`fr migrate artifacts --yes --repropose` (`FR_CONFIG_REPROPOSE=1`; review p4-r12).
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


REPROPOSE_ENV: Final = "FR_CONFIG_REPROPOSE"
"""Set (by `fr migrate artifacts --repropose`): propose a change again although its pull
request was closed unmerged."""


def change_kind(rel: str) -> str:
    """The kind a change to *rel* names: its path below `.fr/`, `/` as `-`, without the
    suffix (`settings`, `models`, `workflows-mine`)."""
    from fr.config.space import SPACE_DIR

    below = rel.rsplit(f"{SPACE_DIR}/", 1)[-1]
    stem = below.rsplit(".", 1)[0] if "." in below.rsplit("/", 1)[-1] else below
    kind = "".join(c if c.isalnum() or c in "-_" else "-" for c in stem.replace("/", "-"))
    return kind.strip("-") or "config"


def change_branch(rel: str, text: str) -> str:
    """`fr-config-change/<kind>-<hash>`: the kind of *rel* and a hash of the path and the
    bytes (review p4-r12)."""
    digest = hashlib.sha256(f"{rel}\0{text}".encode()).hexdigest()[:10]
    return f"{CHANGE_PREFIX}{change_kind(rel)}-{digest}"


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

PrsForHead = Callable[[str, str], list[dict[str, object]]]
"""(remote URL, head branch) -> the pull requests from that head, any state, as
`{state: OPEN | CLOSED | MERGED, url, same_repo, base, head_oid}` records. `same_repo` is
True only when the head lives in the target repo itself (never a fork carrying the same
branch name); `base` is the branch the pull request merges into."""


def _forge_prs_for_head(remote: str, head: str) -> list[dict[str, object]]:
    """The default `PrsForHead` (security review of p4-r12): `list_prs_by_head`, keeping
    only the pull requests whose head is in the target repo (`isCrossRepository` False,
    the same test `open_pr_in_repo` makes by head-repo full name), each read with `pr_view`
    for its base and head commit. A forge fr cannot ask answers none (the change is then
    proposed, and `open_pr` still reuses an open pull request)."""
    from fr._hosts import slug_from_url
    from fr.ghclient import UnsupportedForgeOperation
    from fr.hostclient import FORGE_ERRORS, client_for_url

    slug = slug_from_url(remote) if "://" in remote or "@" in remote else None
    if not slug:
        return []
    slug = slug.removesuffix(".git")
    try:
        client = client_for_url(remote)
        out: list[dict[str, object]] = []
        for pr in client.list_prs_by_head(slug, head):
            if pr.get("isCrossRepository") is not False:
                continue  # a fork's head, or one fr cannot place: never trusted
            view = client.pr_view(slug, int(pr["number"]))
            out.append(
                {
                    "state": str(pr.get("state", "")),
                    "url": str(pr.get("url", "")),
                    "same_repo": True,
                    "base": str(view.get("base_ref", "")),
                    "head_oid": str(view.get("head_oid", "")),
                }
            )
        return out
    except FORGE_ERRORS + (UnsupportedForgeOperation,):
        return []


prs_for_head: PrsForHead = _forge_prs_for_head
"""The forge seam for earlier proposals (tests replace it)."""


def _earlier_proposal(
    cwd: Path, remote: str, head: str, base: str, rel: str, text: str
) -> str | None:
    """The URL of an earlier OPEN pull request to reuse, or None (propose). A pull request
    counts only when its head is in the target repo and it merges into *base*; an open one
    also only when origin's *head* holds *rel* = *text* exactly. One closed unmerged
    refuses, naming it and how to propose it again. Any other is ignored."""
    if os.environ.get(REPROPOSE_ENV):
        return None
    trusted = [
        pr
        for pr in prs_for_head(remote, head)
        if pr.get("same_repo") is True and str(pr.get("base", "")) == base
    ]
    for pr in trusted:
        if str(pr.get("state", "")).upper() == "OPEN" and _already_proposed(cwd, head, rel, text):
            return str(pr.get("url", ""))
    for pr in trusted:
        if str(pr.get("state", "")).upper() == "CLOSED":
            raise SettingsError(
                f"the change to {rel} was proposed in {pr.get('url', '')} and that pull "
                "request was closed unmerged, so fr does not propose it again on every "
                "command. Reopen it, or propose it again with `fr migrate artifacts --yes "
                f"--repropose` ({REPROPOSE_ENV}=1 for any other command)"
            )
    return None


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


def _commit_on(
    cwd: Path, base_sha: str, rel: str, text: str, message: str, *, executable: bool = False
) -> str:
    """A commit whose parent is *base_sha* and whose tree is *base_sha*'s with *rel* =
    *text*, made with plumbing in a private index: no working tree is touched."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _run(cwd, "read-tree", base_sha, env=env)
        blob = _run(cwd, "hash-object", "-w", "--stdin", stdin=text)
        mode = "100755" if executable else "100644"
        _run(cwd, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{rel}", env=env)
        tree = _run(cwd, "write-tree", env=env)
        return _run(cwd, "commit-tree", tree, "-p", base_sha, "-F", "-", stdin=message)


def pr_policy(product: Path) -> str:
    """`git.pr` of the product checkout's settings (`auto` | `ask`): the same setting `fr
    pr create` honours, read where the run is (under stealth, the target's workspace)."""
    from fr.settings import load_settings

    return str(load_settings(product).settings.git.pr)


def _approve(product: Path, head: str, request_head: str) -> Path | None:
    """Under `git.pr: ask`, the operator's verified approval for the pull request from
    *head*, exactly as `fr pr create` asks (`fr.git_policy.ask.require_approval`, recorded
    in the run's own journal); the git dir whose request `consume` clears after the PR is
    open. None under `auto`. A missing approval refuses BEFORE anything is pushed."""
    if pr_policy(product) != "ask":
        return None
    from fr.commands.push_cmd import approval_journal
    from fr.git_policy import ask

    git_dir = Path(_run(product, "rev-parse", "--absolute-git-dir"))
    try:
        ask.require_approval(
            product,
            kind="pr",
            branch=head,
            head=request_head,
            journal=approval_journal(product),
            git_dir=git_dir,
            still_current=True,
        )
    except ask.AskRefusedError as e:
        raise SettingsError(
            f"git.pr: ask: the configuration change's pull request from `{head}` waits for "
            f"the operator ({e}). Nothing was pushed; run the same command again once it is "
            "approved"
        ) from e
    return git_dir


def open_change(
    cwd: Path,
    *,
    product: Path,
    remote: str,
    base_branch: str,
    base_ref: str,
    rel: str,
    text: str,
    message: str,
    executable: bool = False,
) -> str:
    """Propose *rel* = *text* on *base_branch* (its last fetched tip *base_ref* in the
    clone *cwd*): commit it on `change_branch(rel, text)`, push that branch to origin
    (plain, never forced; a branch already holding the same change is reused), and open
    a pull request into *base_branch*. Returns the pull request's URL. *product* is the
    checkout whose `git.pr` applies (decision p2-config-pr-honours-git-pr): under `ask`
    the operator's approval comes first, as for `fr pr create`, and nothing is pushed
    without it."""
    base_sha = _run(cwd, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    head = change_branch(rel, text)
    earlier = _earlier_proposal(cwd, remote, head, base_branch, rel, text)
    if earlier:
        return earlier
    approved = _approve(product, head, f"{base_sha[:12]}+{head.rsplit('-', 1)[-1]}")
    commit = _commit_on(cwd, base_sha, rel, text, message, executable=executable)
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
    url = open_pr(remote, head, base_branch, subject, body)
    if approved is not None:
        from fr.git_policy import ask

        ask.consume(approved, "pr", head)
    return url


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
