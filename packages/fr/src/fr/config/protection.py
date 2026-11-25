"""Executable configuration behind verified protection (spec 2026-11-19-event-driven-a-la-carte
R7, §C).

Configuration that runs commands or decides merges (`.fr/candidate-install`, `.fr/ops.yaml`,
`.fr/ci.yaml`'s `gate_checks`, `tests` and `fast_tier` (`fr.run.ci_evidence.GUARDED_CI_KEYS`),
and the keys of `.fr/triage.yaml` that run a command or decide whose PRs are trusted or
merged, `GUARDED_TRIAGE_KEYS`) is read under `quiet` and `stealth`
from a configuration branch anyone able to push to the repository could write. fr runs or
gates on it only when the forge enforces, on that exact branch, a rule requiring a pull
request with at least one approving review, and blocks force-pushes and deletion.

The limit, said wherever fr claims protection: fr reads the branch's effective rules, which
do not name a ruleset's bypass actors, so a ruleset that lets someone bypass it still reads
as enforced. The operator keeps the configuration branch's bypass lists empty.

`branch_protection` asks the forge once per command (`GET repos/<repo>/rules/branches/<b>`,
the effective rules) and answers `Enforced` or `NotEnforced(reason)`. The free-plan 403
(`fr.real_ghrestclient._plan_lacks_rulesets`), a 404, an empty or partial rule list, an
unreadable reply and a forge whose adapter cannot read rules (GitLab, Gitea) are
`NotEnforced`. Any other failure (network, auth, 5xx) is neither: `ProtectionReadError`.
The answer is kept in memory until `forget()` (each `fr triage collect`, so each driver pass,
starts afresh), never on disk.

`require_protected(space, client, what)` is the one guard every executor calls: under `repo`
it returns at once; otherwise it refuses with `ProtectionError` naming the reason and the fix.
`require_checked_tip` adds that fr runs exactly what was reviewed (review p3-r2): it fetches
the configuration branch (`fetch_tip`, once per command) and, for a reader of the working
tree, refuses a configuration checkout that is dirty, ahead of or behind that fetched tip.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from fr.settings import SettingsError

if TYPE_CHECKING:
    from pathlib import Path

    from fr.config.space import ConfigSpace

_REPO: Final = "repo"
_STEALTH: Final = "stealth"

REQUIRED_RULES: Final = {
    "pull_request": "no rule requires a pull request",
    "non_fast_forward": "force-pushes are not blocked",
    "deletion": "deletion is not blocked",
}
"""The rule types an enforced branch carries, and what is said when one is missing."""

GUARDED_TRIAGE_KEYS: Final = (
    "post_merge",
    "version",
    "mirrors",
    "pr_authors",
    "queue",
    "exit",
    "export",
)
"""The top-level keys of `.fr/triage.yaml` that run a command (`post_merge`, the `version`
commands, `mirrors`) or decide whose PRs are trusted or how they merge (`pr_authors`, the
merge `queue`, the `exit` gate remap, the `export` PR the driver lands). Read from an
unprotected configuration branch, they are ignored: each one's absence is the safe default."""


BYPASS_LIMIT: Final = (
    "fr reads the branch's rules and cannot see bypass actors, so keep the ruleset's bypass "
    "list empty"
)
"""What fr cannot check (review p3-r3), said with every fix and every claim of protection."""

APPROVAL_MISSING: Final = "the pull-request rule requires no approving review"


def fix_text(branch: str) -> str:
    """What to change (spec §C), with the limit of what fr checks."""
    return (
        f"protect {branch} with a ruleset requiring pull requests with at least one approving "
        f"review (and blocking force-pushes and deletion); {BYPASS_LIMIT}; GitHub needs a "
        "public repo or a paid plan for a private one"
    )


@dataclass(frozen=True)
class Enforced:
    """The forge enforces an approved-pull-request rule on *branch* of *repo* (bypass actors
    unseen: `BYPASS_LIMIT`)."""

    repo: str
    branch: str


@dataclass(frozen=True)
class NotEnforced:
    """The forge does not, or cannot, enforce one; *reason* says which."""

    repo: str
    branch: str
    reason: str


Answer = Enforced | NotEnforced


class ProtectionError(SettingsError):
    """fr refuses an action on executable configuration from an unprotected branch."""


class ProtectionReadError(ProtectionError):
    """The forge's rules could not be read (network, auth, a 5xx): neither answer."""


_CACHE: dict[tuple[str, str | None, str, str], Answer] = {}
"""Answers by `(forge identity, host, repo, branch)`: one forge's answer never stands for
another's (a GitHub Enterprise host and github.com, or a glab client, with the same slug)."""


def _forge_identity(client: object) -> tuple[str, str | None]:
    """The adapter's class and host; a wrapper (triage's `ClientForge`) is seen through."""
    inner = getattr(client, "_client", None) or client
    kind = f"{type(inner).__module__}.{type(inner).__qualname__}"
    backend = getattr(inner, "backend", None)
    if isinstance(backend, str):
        kind = f"{kind}:{backend}"
    host = getattr(inner, "_host", None)
    return kind, host if isinstance(host, str) else None


_FETCHED: set[tuple[str, str]] = set()
"""`(git repo, ref)` pairs `require_checked_tip` fetched this command (cleared by `forget`)."""


def forget() -> None:
    """Drop every cached answer: the next ask reads the forge (and fetches) again."""
    _CACHE.clear()
    _FETCHED.clear()


def _chain(exc: BaseException) -> list[BaseException]:
    out: list[BaseException] = []
    seen: BaseException | None = exc
    while seen is not None and seen not in out:
        out.append(seen)
        seen = seen.__cause__ or seen.__context__
    return out


def _text(exc: BaseException) -> str:
    return f"{exc} {getattr(exc, 'stderr', '') or ''} {getattr(exc, 'stdout', '') or ''}"


_HTTP_404 = re.compile(r"\bHTTP 404\b")


def _classify(exc: BaseException) -> str | None:
    """The `NotEnforced` reason a failed rules read means, None when it is a failed read."""
    from fr.ghclient import HostRefusedError, UnsupportedForgeOperation
    from fr.real_ghrestclient import FREE_PLAN_RULESETS_NOTICE

    chain = _chain(exc)
    if any(isinstance(e, HostRefusedError) for e in chain):
        return None
    for e in chain:
        if isinstance(e, UnsupportedForgeOperation):
            return f"the {e.backend} forge adapter cannot read branch rules"
    for e in chain:
        text = _text(e)
        if "HTTP 403" in text and FREE_PLAN_RULESETS_NOTICE in text:
            return (
                "GitHub does not enforce rulesets on a private repository on the free plan "
                "(HTTP 403)"
            )
    for e in chain:
        if _HTTP_404.search(_text(e)):
            return "the forge answered HTTP 404 for its rules (no such repository, or no access)"
    return None


def _judge(reply: object) -> str | None:
    """Why *reply* (the parsed rules list) is not an enforced branch, None when it is."""
    if not isinstance(reply, list) or not all(isinstance(r, dict) for r in reply):
        return "the forge's rules answer is not a list of rules"
    if not reply:
        return (
            "no ruleset on this branch (classic branch protection is not read; protect it "
            "with a ruleset)"
        )
    types = {r.get("type") for r in reply}
    missing = [said for kind, said in REQUIRED_RULES.items() if kind not in types]
    if "pull_request" in types and not any(_approving(r) for r in reply):
        missing.append(APPROVAL_MISSING)
    return "; ".join(missing) if missing else None


def _approving(rule: dict[str, Any]) -> bool:
    """A `pull_request` rule that needs at least one approving review (review p3-r3). Every
    rule the forge returns applies, so one such rule is enough; a count that is not a
    positive integer is none."""
    if rule.get("type") != "pull_request":
        return False
    params = rule.get("parameters")
    count = params.get("required_approving_review_count") if isinstance(params, dict) else None
    return isinstance(count, int) and not isinstance(count, bool) and count >= 1


def branch_protection(client: object, repo: str, branch: str) -> Answer:
    """Whether the forge enforces a pull-request rule on *branch* of *repo* (R7).

    *client* is any forge adapter with `branch_rules(repo=, branch=)` (a `GhClient`, or
    triage's `ClientForge`); one without it cannot read rules. Raises `ProtectionReadError`
    on a failed read, which is never cached."""
    key = (*_forge_identity(client), repo.lower(), branch)
    if key in _CACHE:
        return _CACHE[key]
    answer = _ask(client, repo, branch)
    _CACHE[key] = answer
    return answer


def _ask(client: object, repo: str, branch: str) -> Answer:
    reader = getattr(client, "branch_rules", None)
    if reader is None:
        return NotEnforced(repo, branch, "this forge client cannot read branch rules")
    reply: Any
    try:
        reply = reader(repo=repo, branch=branch)
    except ValueError:  # the reply did not parse as JSON: an unreadable answer
        reply = None
    except Exception as exc:  # noqa: BLE001 — every backend's error, classified here
        reason = _classify(exc)
        if reason is None:
            raise ProtectionReadError(
                f"the rules of {branch} on {repo} could not be read: {exc}"
            ) from exc
        return NotEnforced(repo, branch, reason)
    why = _judge(reply)
    return Enforced(repo, branch) if why is None else NotEnforced(repo, branch, why)


# --- the configuration branch of a space ------------------------------------------------


def _origin_slug(root: Path) -> str | None:
    from fr._hosts import origin_slug

    return origin_slug(root)


def _target(space: ConfigSpace) -> tuple[str, str] | NotEnforced:
    """`(repo, branch)` the forge is asked about, or why no forge can enforce it."""
    from fr.config.space import CONFIG_BRANCH, CONFIG_SUFFIX

    if space.placement == _STEALTH:
        from fr._hosts import slug_from_url
        from fr.placement.stealth import is_local, parse_ref

        assert space.tracking is not None
        ref = parse_ref(space.tracking)
        branch = f"{ref.branch}{CONFIG_SUFFIX}"
        slug = None if is_local(ref.repo) else slug_from_url(ref.repo)
        if slug is None:
            return NotEnforced(
                ref.repo, branch, "the tracking repository is a local path, which no forge protects"
            )
        return slug.removesuffix(".git"), branch
    slug = _origin_slug(space.product)
    if slug is None:
        return NotEnforced(
            str(space.product), CONFIG_BRANCH, "origin is not a forge repository fr can ask"
        )
    return slug, CONFIG_BRANCH


def config_target(space: ConfigSpace) -> tuple[str, str] | None:
    """The `(repo, branch)` holding *space*'s configuration; None when no forge holds it."""
    found = _target(space)
    return None if isinstance(found, NotEnforced) else found


def _default_client(space: ConfigSpace) -> object:
    if space.placement == _STEALTH:
        from fr.hostclient import client_for_url
        from fr.placement.stealth import parse_ref

        assert space.tracking is not None
        url = parse_ref(space.tracking).repo
        if "://" not in url and ":" in url:  # scp-like: git@host:owner/repo.git
            host, _, path = url.partition(":")
            url = f"https://{host.rpartition('@')[2]}/{path}"
        return client_for_url(url)
    from fr.hostclient import client_for

    return client_for(space.product)


def protection_of(space: ConfigSpace, client: object | None = None) -> Answer | None:
    """*space*'s configuration branch's answer; None under `repo` (nothing is asked).

    *client* is the product repo's forge client, used under quiet (where `fr-config` lives on
    the product's origin). Under stealth the branch lives in the tracking repo, possibly on
    another forge, so a given client is never asked: the tracking repo's own is built (a
    product client's answer never stands for the tracking repo's rules)."""
    if space.placement == _REPO:
        return None
    found = _target(space)
    if isinstance(found, NotEnforced):
        return found
    repo, branch = found
    if client is None or space.placement == _STEALTH:
        try:
            client = _default_client(space)
        except Exception as exc:  # noqa: BLE001 — a client fr cannot build is a failed read
            raise ProtectionReadError(
                f"the rules of {branch} on {repo} could not be read: {exc}"
            ) from exc
    return branch_protection(client, repo, branch)


def require_protected(space: ConfigSpace, client: object | None, what: str) -> None:
    """The one guard (R7): return when *space* is `repo`, or its configuration branch is
    enforced; otherwise refuse *what* (`ProtectionError`, or `ProtectionReadError` when the
    forge could not be read), naming the reason and the fix."""
    try:
        answer = protection_of(space, client)
    except ProtectionReadError as exc:
        raise ProtectionReadError(f"fr will not {what}: {exc}") from exc
    if answer is None or isinstance(answer, Enforced):
        return
    raise ProtectionError(
        f"fr will not {what}: {answer.branch} on {answer.repo} is not protected "
        f"({answer.reason}); {fix_text(answer.branch)}"
    )


class UncheckedTipError(ProtectionError):
    """The configuration fr would run is not the fetched, reviewed tip of its branch."""


def require_checked_tip(
    space: ConfigSpace,
    client: object | None,
    what: str,
    *,
    working_tree: bool,
    no_fetch: bool = False,
    command: str | None = None,
) -> None:
    """`require_protected`, then the content fr runs is exactly the reviewed tip (review
    p3-r2, plan decision p3-run-the-checked-tip). Under `repo` it returns at once.

    The configuration branch is fetched first (once per command); a failed fetch refuses,
    since fr could not tell what the reviewed tip is. *no_fetch* (the command's own
    `--no-fetch`, named *command*) skips it and says the tip may be stale. With
    *working_tree* (a reader of `space.dir`: the walk's programs, `ops.yaml`, the `exit:`
    remap) the configuration checkout (the quiet `fr-config` worktree, the stealth
    configuration clone) must also be clean, untracked and ignored files included, with HEAD
    at the fetched tip; otherwise fr refuses naming each difference and its remedy. Without
    it (a blob reader, `at_default`) the read is of the fetched tip itself."""
    if space.placement == _REPO:
        return
    require_protected(space, client, what)
    fetch_tip(space, what, no_fetch=no_fetch, command=command)
    if working_tree:
        assert space.ref is not None
        _check_checkout(space.checkout, f"refs/remotes/{space.ref}", space.ref, what)


def fetch_tip(
    space: ConfigSpace, what: str, *, no_fetch: bool = False, command: str | None = None
) -> None:
    """Fetch *space*'s configuration branch into its remote-tracking ref, once per command
    (nothing under `repo`), so a read at `at_default` is of the reviewed tip as origin has it
    now; a failed fetch refuses `UncheckedTipError`. *no_fetch* says the tip may be stale."""
    if space.placement == _REPO or space.ref is None:
        return
    repo = space.product if space.placement != _STEALTH else space.checkout
    ref = f"refs/remotes/{space.ref}"
    if no_fetch:
        import sys

        print(
            f"fr: --no-fetch: {what} reads the last fetched {space.ref}, which may be stale",
            file=sys.stderr,
        )
    elif (str(repo), ref) not in _FETCHED:
        _fetch_tip(repo, space.ref.removeprefix("origin/"), ref, what, command)
        _FETCHED.add((str(repo), ref))


def _fetch_tip(repo: Path, branch: str, ref: str, what: str, command: str | None) -> None:
    from fr.placement.quiet import _default_network

    if not (repo / ".git").exists():
        raise UncheckedTipError(
            f"fr will not {what}: {repo} does not exist, so {branch} cannot be fetched"
        )
    done = _default_network(repo)(
        ["git", "fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{branch}:{ref}"]
    )
    if done.returncode != 0:
        remedy = f"; `{command} --no-fetch` reads the last fetched tip" if command else ""
        raise UncheckedTipError(
            f"fr will not {what}: cannot fetch {branch} from origin "
            f"({(done.stderr or 'git fetch failed').strip()}), so fr cannot tell which tip "
            f"was reviewed; check the remote (`git -C {repo} remote -v`){remedy}"
        )


def _git_out(where: Path, *args: str) -> str | None:
    from fr.git import GitUnavailableError, git_answer

    try:
        done = git_answer(where, *args)
    except GitUnavailableError:
        return None
    return done.stdout if done.returncode == 0 else None


def _check_checkout(checkout: Path, ref: str, short: str, what: str) -> None:
    """*checkout* is clean and at *ref*, or `UncheckedTipError` naming every difference."""
    head = "the configuration checkout"
    if not (checkout / ".git").exists():
        raise UncheckedTipError(
            f"fr will not {what}: {head} {checkout} does not exist; `fr isolation up` "
            "creates it at the configuration branch's tip"
        )
    status = _git_out(
        checkout, "status", "--porcelain", "--untracked-files=all", "--ignored=matching"
    )
    tip = _git_out(checkout, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    at = _git_out(checkout, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if status is None or not tip or not at:
        raise UncheckedTipError(
            f"fr will not {what}: git could not read {head} {checkout} or {short}, so fr "
            "cannot tell that it holds the reviewed tip"
        )
    problems: list[str] = []
    remedies: list[str] = []
    dirty = [line[3:] for line in status.splitlines() if line.strip()]
    if dirty:
        shown = ", ".join(dirty[:5]) + (f" and {len(dirty) - 5} more" if len(dirty) > 5 else "")
        problems.append(f"local changes not on {short}: {shown}")
        remedies.append(
            "a configuration change goes through a pull request: move the edit to one, then "
            f"discard it there (`git -C {checkout} stash push --include-untracked`)"
        )
    if at.strip() != tip.strip():
        counts = _git_out(checkout, "rev-list", "--left-right", "--count", f"HEAD...{ref}")
        ahead, behind = (counts or "? ?").split()[:2]
        if ahead != "0":
            problems.append(f"{ahead} local commit(s) ahead of {short}")
            remedies.append(
                f"open a pull request for them, then `git -C {checkout} reset --keep {short}`"
            )
        if behind != "0":
            problems.append(f"{behind} commit(s) behind {short}")
            remedies.append(f"`git -C {checkout} merge --ff-only {short}`")
    if problems:
        raise UncheckedTipError(
            f"fr will not {what}: {head} {checkout} is not the reviewed tip of {short} "
            f"({'; '.join(problems)}); {'; '.join(remedies)}"
        )


def refusal_at(
    root: Path, client: object | None, what: str, *, working_tree: bool = False
) -> str | None:
    """`require_protected` for the checkout at *root*, as the reason it refuses (None: go
    ahead); with *working_tree*, `require_checked_tip` for a reader of the configuration
    checkout's files. A configuration space that cannot be resolved refuses too."""
    from fr.config.space import config_space

    try:
        space = config_space(root)
        if working_tree:
            require_checked_tip(space, client, what, working_tree=True)
        else:
            require_protected(space, client, what)
    except SettingsError as exc:
        return str(exc)
    return None


# --- `.fr/triage.yaml`'s guarded keys --------------------------------------------------


def guarded_present(data: object) -> list[str]:
    """The `GUARDED_TRIAGE_KEYS` *data* (a parsed `.fr/triage.yaml`) sets."""
    if not isinstance(data, dict):
        return []
    return [k for k in GUARDED_TRIAGE_KEYS if k in data]


def without_guarded(data: object) -> object:
    """*data* with every guarded key removed (a non-mapping is returned as it is)."""
    if not isinstance(data, dict):
        return data
    return {k: v for k, v in data.items() if k not in GUARDED_TRIAGE_KEYS}


def ignored_line(keys: list[str], answer: NotEnforced, where: str) -> str:
    """The one line a reader says when it ignores *keys* of *where*."""
    return (
        f"ignoring {', '.join(keys)} in {where}: {answer.branch} on {answer.repo} is not "
        f"protected ({answer.reason}); {fix_text(answer.branch)}"
    )
