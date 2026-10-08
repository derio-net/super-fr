"""The single factory that turns "which backend" into "which client."

Every call site that used to hardcode `RealGhClient()` calls `client_for()`
instead — this is the seam that makes `fr apply`, the isolation lifecycle,
and the fr-vk dispatch bridge all work against GitLab/Gitea repos without
each one re-deriving backend detection itself. See docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §3.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal, cast, get_args
from urllib.parse import quote, urlparse

from fr import _hosts, forgeapi
from fr import gh as _gh
from fr.gh import GhError
from fr.ghclient import GhClient, HostRefusedError
from fr.glab import GlabError
from fr.labels import LabelDef
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient
from fr.tea import TeaError

# What a `GhClient` adapter raises when the FORGE refuses or fails: one error
# class per backend CLI. A caller that collects per-item forge failures catches
# exactly these, so a programming error is never reported as a forge failure.
FORGE_ERRORS: tuple[type[Exception], ...] = (GhError, GlabError, TeaError)

ForgeErrorKind = Literal["rate_limit", "info", "warn", "unknown"]
_KINDS = frozenset(get_args(ForgeErrorKind))


def forge_error_kind(exc: BaseException) -> ForgeErrorKind:
    """Classify any forge error for retry / back-off (spec
    2026-10-06-forge-remainder §4.C): `rate_limit` (back off the whole tick),
    `info` (the target is gone), `warn` (transient) or `unknown`.

    A host trust refusal (`HostRefusedError`, any backend) is `unknown` by
    TYPE, before any text is read: its message names the host, and a host can
    be called anything (gh#1013). Otherwise a `GhError` is `fr.gh.classify`'s
    call, and a `GlabError` / `TeaError` gets the same text rules over its
    stderr and message, with GitLab's and Gitea's 429 counted as a rate limit
    beside GitHub's 403. Anything that is not a forge error is `unknown`."""
    if isinstance(exc, HostRefusedError):
        return "unknown"
    if isinstance(exc, GhError):
        kind = _gh.classify(exc)
        return cast("ForgeErrorKind", kind) if kind in _KINDS else "unknown"
    if not isinstance(exc, (GlabError, TeaError)):
        return "unknown"
    text = ((exc.stderr or "") + " " + str(exc)).lower()
    if ("403" in text or "429" in text) and "rate limit" in text:
        return "rate_limit"
    if "404" in text or "not found" in text:
        return "info"
    if any(pat in text for pat in _gh._TRANSIENT_PATTERNS):
        return "warn"
    return "unknown"


# The command fr names when it tells an agent (or the operator) to act on a
# forge, per backend (gh#742: a refusal that says `gh pr create` on a GitLab
# checkout sends the agent to a CLI that cannot help). One table, so a backend
# cannot gain a PR verb and silently lack an issue verb.
#
# PR ops: `{body}` is a file holding the body and `{ref}` the PR. Each template
# was checked against its CLI's own `--help`: glab and tea take the description
# as a value, not a file, and tea's `--draft`/`--ready` are its
# WIP-title-prefix toggles.
#
# Issue ops (spec 2026-10-06-verification-strategies §E, R16): `{number}` and
# `{repo}` come from an `owner/repo#n` ref, `{comment}` and `{label}` are
# shell-quoted by `issue_command`. glab's `issue close` takes no comment.
#
# Label op (p4-r4): `label-create` makes a repo's label before an issue op adds it,
# which fails on a repo that never had it. `{name}`, `{description}` are shell-quoted
# by `label_command` and `{color}` is the 6-char hex with no `#`. Flags checked against
# `glab label create --help` and `tea labels create --help`; only gh's `--force`
# makes it idempotent, so on glab and tea an "already exists" refusal is harmless.
#
# `github-rest` (spec 2026-10-07-cloud-triage §A): the GitHub ops as `gh api`
# calls on REST routes, named when `forge.api: rest` is selected — a cloud
# session's proxy refuses every GraphQL-backed `gh` verb. `{repo}` is the
# checkout's `origin` (`owner/repo`), `{number}` the PR's number, or a `gh api`
# lookup of it by head branch. REST has no ready-for-review: `ready` is the CCR
# route a Claude Code cloud session's proxy offers for it, which is where `rest`
# is selected. `-f` never reads a file, so a value is passed as given; `-F
# body=@{body}` reads the body file.
CommandTable = Literal["github", "github-rest", "gitlab", "gitea"]
_REST_HEAD = '-f head="$(git branch --show-current)"'
_REST_BASE = '-f base="$(gh api repos/{repo} --jq .default_branch)"'
FORGE_COMMANDS: dict[CommandTable, dict[str, str]] = {
    "github": {
        "create": "gh pr create --draft --body-file {body}",
        "edit": "gh pr edit {ref} --body-file {body}",
        "ready": "gh pr ready {ref}",
        "fill": "gh pr create --fill",
        "issue-close": "gh issue close {number} --repo {repo} --comment {comment}",
        "issue-label": "gh issue edit {number} --repo {repo} --add-label {label}",
        "issue-unlabel": "gh issue edit {number} --repo {repo} --remove-label {label}",
        "label-create": "gh label create {name} --color {color} --description {description}"
        " --force --repo {repo}",
    },
    "github-rest": {
        "create": f"gh api repos/{{repo}}/pulls {_REST_HEAD} {_REST_BASE}"
        ' -f title="$(git log -1 --format=%s)" -F body=@{body} -F draft=true',
        "edit": "gh api -X PATCH repos/{repo}/pulls/{number} -F body=@{body}",
        "ready": "gh api -X POST repos/{repo}/pulls/{number}/ccr/ready_for_review",
        "fill": f"gh api repos/{{repo}}/pulls {_REST_HEAD} {_REST_BASE}"
        ' -f title="$(git log -1 --format=%s)" -f body="$(git log -1 --format=%b)"',
        "issue-close": "gh api repos/{repo}/issues/{number}/comments -f body={comment}"
        " && gh api -X PATCH repos/{repo}/issues/{number} -f state=closed",
        "issue-label": "gh api repos/{repo}/issues/{number}/labels -f 'labels[]='{label}",
        "issue-unlabel": "gh api -X DELETE repos/{repo}/issues/{number}/labels/{label_path}",
        "label-create": "gh api repos/{repo}/labels -f name={name} -f color={color}"
        " -f description={description}"
        " || gh api -X PATCH repos/{repo}/labels/{name_path} -f color={color}"
        " -f description={description}",
    },
    "gitlab": {
        "create": 'glab mr create --draft --description "$(cat {body})"',
        "edit": 'glab mr update {ref} --description "$(cat {body})"',
        "ready": "glab mr update {ref} --ready",
        "fill": "glab mr create --fill --yes",
        "issue-close": "glab issue close {number} --repo {repo}",
        "issue-label": "glab issue update {number} --repo {repo} --label {label}",
        "issue-unlabel": "glab issue update {number} --repo {repo} --unlabel {label}",
        "label-create": "glab label create --name {name} --color '#{color}'"
        " --description {description} --repo {repo}",
    },
    "gitea": {
        "create": 'tea pulls create --draft --description "$(cat {body})"',
        "edit": 'tea pulls edit {ref} --description "$(cat {body})"',
        "ready": "tea pulls edit {ref} --ready",
        "fill": 'tea pulls create --title "<title>"',
        "issue-close": "tea issues close {number} --repo {repo}",
        "issue-label": "tea issues edit {number} --repo {repo} --add-labels {label}",
        "issue-unlabel": "tea issues edit {number} --repo {repo} --remove-labels {label}",
        "label-create": "tea labels create --name {name} --color {color}"
        " --description {description} --repo {repo}",
    },
}

_ISSUE_OPS = ("issue-close", "issue-label", "issue-unlabel")
_LABEL_OPS = ("label-create",)

PR_COMMANDS: dict[CommandTable, dict[str, str]] = {
    backend: {op: t for op, t in table.items() if op not in (*_ISSUE_OPS, *_LABEL_OPS)}
    for backend, table in FORGE_COMMANDS.items()
}
"""The PR half of `FORGE_COMMANDS`."""

ISSUE_COMMANDS: dict[CommandTable, dict[str, str]] = {
    backend: {op: t for op, t in table.items() if op in _ISSUE_OPS}
    for backend, table in FORGE_COMMANDS.items()
}
"""The issue half of `FORGE_COMMANDS`."""

LABEL_COMMANDS: dict[CommandTable, dict[str, str]] = {
    backend: {op: t for op, t in table.items() if op in _LABEL_OPS}
    for backend, table in FORGE_COMMANDS.items()
}
"""The repo-label part of `FORGE_COMMANDS`."""


_TRAILING_NUMBER = re.compile(r"^https?://.*/(\d+)/?$")  # a URL only: `fix/742` is a branch
_ISSUE_REF = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<number>\d+)$")


def command_table(repo_root: Path) -> CommandTable:
    """Which `FORGE_COMMANDS` table `repo_root`'s forge is named from: its
    backend, or `github-rest` for GitHub when `forge.api` is `rest`."""
    backend = _hosts.detect_backend(repo_root)
    if backend == "github" and forgeapi.resolve() == "rest":
        return "github-rest"
    return backend


def _rest_repo(repo_root: Path) -> str:
    """`owner/repo` of the checkout's `origin`, else gh's own `{owner}/{repo}`
    placeholders, which `gh api` fills from the repository it runs in."""
    return _hosts.origin_slug(repo_root) or "{owner}/{repo}"


def _rest_pr_number(ref: str, repo: str) -> str:
    """A PR `ref` (URL, number or head branch) as the number a REST route takes:
    a branch becomes a `gh api` lookup of its PR, run by the shell. The branch is
    URL-encoded (`&`, `#`, `+`, a space would otherwise cut or bend the query),
    spelled as `RealGhRestClient`'s own head lookup."""
    import shlex
    import urllib.parse

    if ref.isdigit():
        return ref
    if m := _TRAILING_NUMBER.search(ref):
        return m.group(1)
    owner = repo.split("/", 1)[0]
    head = urllib.parse.quote(f"{owner}:{ref}", safe=":/")
    route = shlex.quote(f"repos/{repo}/pulls?head={head}&state=all&per_page=100&page=1")
    return f"$(gh api {route} --jq '.[0].number')"


def pr_command(repo_root: Path, op: str, **fields: str) -> str:
    """The `op` (create | edit | ready | fill) command for `repo_root`'s forge,
    with `fields` filled in — see `PR_COMMANDS`. `glab mr update` and
    `tea pulls edit` take no URL, so there a PR URL `ref` is reduced to its
    number, which both resolve against the checkout they run in. `github-rest`
    is also given `{repo}` and the PR's `{number}`."""
    table = command_table(repo_root)
    ref = fields.get("ref")
    if table == "github-rest":
        repo = _rest_repo(repo_root)
        fields = {**fields, "repo": repo}
        if ref:
            fields["number"] = _rest_pr_number(ref, repo)
    elif table != "github" and ref and (m := _TRAILING_NUMBER.search(ref)):
        fields = {**fields, "ref": m.group(1)}
    return PR_COMMANDS[table][op].format(**fields)


def issue_command(repo_root: Path, op: str, *, ref: str, comment: str = "", label: str = "") -> str:
    """The `op` (issue-close | issue-label | issue-unlabel) command for
    `repo_root`'s forge against the issue `ref` (`owner/repo#n`) — see
    `ISSUE_COMMANDS`. `comment` and `label` are shell-quoted."""
    import shlex

    m = _ISSUE_REF.match(ref)
    if m is None:
        raise ValueError(f"issue ref {ref!r} must be owner/repo#n")
    template = ISSUE_COMMANDS[command_table(repo_root)][op]
    return template.format(
        repo=m["repo"],
        number=m["number"],
        comment=shlex.quote(comment),
        label=shlex.quote(label),
        label_path=shlex.quote(quote(label, safe="")),
    )


def label_command(repo_root: Path, label: LabelDef, *, repo: str) -> str:
    """The `label-create` command for `repo_root`'s forge, creating *label* (its
    name, colour and description from `fr.labels`) in *repo* (`owner/repo`) — see
    `LABEL_COMMANDS`. The name and description are shell-quoted."""
    import shlex

    template = LABEL_COMMANDS[command_table(repo_root)]["label-create"]
    return template.format(
        name=shlex.quote(label.name),
        name_path=shlex.quote(quote(label.name, safe="")),
        color=label.color,
        description=shlex.quote(label.description),
        repo=repo,
    )


# Warn-once guard for a DECLARED host fr cannot thread to the resolved
# backend (gh-486, spec §4.D) — keyed on (host, backend) so a repo that
# later changes backend gets a fresh warning. Lives here, not in `_hosts`,
# and is deliberately NOT shared with `_hosts._WARNED_UNKNOWN_HOSTS` (see
# plan journal no-refactor-because P5.T2): the two warnings key on
# different things, and coupling them would put hostclient's provenance
# rule inside `_hosts`, undoing the split spec §4.D introduced.
_WARNED_DECLARED_HOSTS: set[tuple[str, str]] = set()


def client_for_backend(backend: _hosts.HostBackend, *, host: str | None = None) -> GhClient:
    """Return the `GhClient`-shaped adapter for an already-resolved
    backend. The shared dispatch table `client_for()` and any caller with
    its own backend-resolution path (e.g. `fr_vk.pr_observe`, which
    resolves from a bare PR URL via `fr._hosts.backend_for_url` rather
    than a local checkout) both go through this.

    `host` names a self-hosted instance. This function is deliberately
    PROVENANCE-BLIND: it never reads repo config (its one input beyond its
    arguments is the host-level `forge.api`, which picks GitHub's REST-only
    client) and cannot tell a declared
    `host:` from one derived from a remote or a PR URL, which is exactly
    why `client_for` — not this — owns the warning about a host fr cannot
    honour (gh-486; spec §4.D). The GitLab adapter threads it to `glab`,
    the GitHub one as `GH_HOST` (spec 2026-10-06-forge-remainder §4.E);
    `tea` still resolves its own host."""
    if backend == "gitlab":
        # gitlab.com likewise: never a GITLAB_HOST, so a SaaS repo needs no
        # glab config login past the trust gate (gh#1014).
        return RealGlabClient(host=_hosts.self_hosted_hostname(host))
    if backend == "gitea":
        return RealTeaClient()
    # A SaaS host (github.com) is gh's own default, never a GH_HOST: threading
    # it would demand a hosts.yml login that token-only CI does not have
    # (review p1-r2). `forge.api: rest` (spec 2026-10-07-cloud-triage §A, R3)
    # is this function's one config input: it picks the REST-only client.
    if forgeapi.resolve() == "rest":
        return RealGhRestClient(host=_hosts.self_hosted_hostname(host))
    return RealGhClient(host=_hosts.self_hosted_hostname(host))


def client_for_url(url: str) -> GhClient:
    """The client for the forge AND instance *url* lives on — the backend from
    the URL's path shape (else its hostname), and a host only when it is not a
    recognized SaaS domain (spec 2026-10-06-forge-remainder §4.D). For callers
    holding a URL and no checkout: `fr_vk.pr_state` and the triage batch verbs.

    A self-hosted GitLab URL with no MR path shape still reads as github
    here; triage facts are GitHub-only, so it cannot arise from them."""
    return client_for_backend(
        _hosts.backend_for_url(url),
        host=_hosts.self_hosted_hostname(urlparse(url).hostname),
    )


def client_for(repo_root: Path) -> GhClient:
    """Return the `GhClient`-shaped adapter for the repo checked out at
    `repo_root`, resolved via `fr._hosts.detect_backend`.

    Takes a local checkout path, not a bare `owner/repo` string: backend
    detection reads `repo_root`'s `.devcontainer/fr-profiles.yaml` and git
    remote, which requires being physically in that checkout. This means
    a cross-repo plan whose phase targets a DIFFERENT repo/backend than
    `repo_root` isn't resolved correctly by this call alone — a known,
    narrow scope limit (see the design doc's non-goals) rather than a
    silently-wrong guess: today's callers all resolve `repo_root` as
    `Path.cwd()`, matching the existing single-repo assumption `fr apply`
    already made before this factory existed.

    Being the only layer that HAS a `repo_root`, this is also the only one
    that can resolve a self-hosted instance hostname at all — and the only
    one that can tell a declared `host:` from one derived from the origin
    remote (`_hosts.declared_host` vs `_hosts.host_for`). That distinction
    is what spec §4.D's warning rests on, so it must stay here rather than
    move down into `client_for_backend`.

    GitHub is given only the DECLARED host (spec 2026-10-06-forge-remainder
    §4.E): inside a checkout `gh` infers the host from the remote itself, and
    a derived origin host may be an SSH alias, which must never become
    `GH_HOST`. GitLab keeps the derived host too. Only Gitea, which threads
    no host at all, still warns about a declared one.
    """
    backend = _hosts.detect_backend(repo_root)
    declared = _hosts.declared_host(repo_root)
    if declared and backend == "gitea" and (declared, backend) not in _WARNED_DECLARED_HOSTS:
        _WARNED_DECLARED_HOSTS.add((declared, backend))
        print(
            f"warning: host {declared!r} is declared in "
            ".devcontainer/fr-profiles.yaml but fr does not thread a host "
            f'to backend "{backend}" — the CLI\'s own host resolution '
            "applies instead. See gh-486.",
            file=sys.stderr,
        )
    if backend == "github":
        return client_for_backend(backend, host=declared)
    return client_for_backend(backend, host=_hosts.host_for(repo_root))
