"""Executable configuration behind verified protection (spec 2026-11-19-event-driven-a-la-carte
R7, §C).

Configuration that runs commands or decides merges (`.fr/candidate-install`, `.fr/ops.yaml`,
`.fr/ci.yaml`'s `gate_checks`, and the keys of `.fr/triage.yaml` that run a command or decide
whose PRs are trusted or merged, `GUARDED_TRIAGE_KEYS`) is read under `quiet` and `stealth`
from a configuration branch anyone able to push to the repository could write. fr runs or
gates on it only when the forge enforces, on that exact branch, a rule requiring a pull
request and blocking force-pushes and deletion.

`branch_protection` asks the forge once per command (`GET repos/<repo>/rules/branches/<b>`,
the effective rules) and answers `Enforced` or `NotEnforced(reason)`. The free-plan 403
(`fr.real_ghrestclient._plan_lacks_rulesets`), a 404, an empty or partial rule list, an
unreadable reply and a forge whose adapter cannot read rules (GitLab, Gitea) are
`NotEnforced`. Any other failure (network, auth, 5xx) is neither: `ProtectionReadError`.
The answer is kept in memory until `forget()` (each `fr triage collect`, so each driver pass,
starts afresh), never on disk.

`require_protected(space, client, what)` is the one guard every executor calls: under `repo`
it returns at once; otherwise it refuses with `ProtectionError` naming the reason and the fix.
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


def fix_text(branch: str) -> str:
    """What to change (spec §C)."""
    return (
        f"protect {branch} with a ruleset requiring pull requests (and blocking force-pushes "
        "and deletion); GitHub needs a public repo or a paid plan for a private one"
    )


@dataclass(frozen=True)
class Enforced:
    """The forge enforces a pull-request rule on *branch* of *repo*."""

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


def forget() -> None:
    """Drop every cached answer: the next ask reads the forge again."""
    _CACHE.clear()


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
        return "the branch has no rules"
    types = {r.get("type") for r in reply}
    missing = [said for kind, said in REQUIRED_RULES.items() if kind not in types]
    return "; ".join(missing) if missing else None


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
    """*space*'s configuration branch's answer; None under `repo` (nothing is asked)."""
    if space.placement == _REPO:
        return None
    found = _target(space)
    if isinstance(found, NotEnforced):
        return found
    repo, branch = found
    if client is None:
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


def refusal_at(root: Path, client: object | None, what: str) -> str | None:
    """`require_protected` for the checkout at *root*, as the reason it refuses (None: go
    ahead). A configuration space that cannot be resolved refuses too."""
    from fr.config.space import config_space

    try:
        require_protected(config_space(root), client, what)
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
