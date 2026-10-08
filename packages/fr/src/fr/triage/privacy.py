"""The privacy guard: a private repo's issue never reaches a public state repo (spec
2026-10-07-cloud-triage R8, §C).

One predicate, `leak_risk`: a key whose repo is not public (private or internal) bound
for a state repo that is public. Two guards call it:

- `guard_write` — every engine write of `judgements.yaml` that adds a key to a judged set,
  a batch or a wave (`fr.commands.triage_batch_cmd._save`, which `batch create`, `batch
  edit --add-issue` and the wave setters all go through). The scope's repos' visibility
  is read from facts, refreshed by every collect; a repo facts do not name is read live.
- `guard_state` — every push of the state ref (`state_ref.push_state`, the lease push
  included) and every `state export`. The state repo's own visibility is ALWAYS read live
  (`GET repos/{state_repo}`) immediately before writing, whether or not it is in the scope
  and whether or not `facts.json` exists, and an unreadable answer refuses: a repo whose
  visibility changed, or a hand-edited file, is caught before it leaves the workspace.

A key's repo whose visibility cannot be read counts as private: the guard never lets an
unknown through to a public state repo. A scope with no state repo is never checked: its
state stays in the workspace.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from fr.triage.errors import TriageError
from fr.triage.model import Facts, Scope, load_judgements, load_scope_facts, normalize_key

ClientFor = Callable[[str], Any]
"""OWNER/REPO -> the forge client that reads its visibility (`GhClient.repo_visibility`)."""


class PrivacyError(TriageError):
    """A write would put a private repo's issue into a public state repo, or the state
    repo's visibility could not be read."""


def refusal(issue: str, repo: str, state_repo: str) -> str:
    """THE refusal line, shared by every call site (P3.T4.S4)."""
    return (
        f"{issue} is an issue of {repo}, which is not public, and this scope's state repo "
        f"{state_repo} is public: its state ref and exports would leak it. Keep {issue} out, "
        "or move the scope's state to a private repo (cloud-triage R8)"
    )


def unreadable(state_repo: str) -> str:
    return (
        f"cannot read the visibility of the state repo {state_repo} from the forge; refusing "
        "to write state that may hold private issues to it (cloud-triage R8)"
    )


def is_public(visibility: str | None) -> bool:
    return visibility == "public"


def leaks(
    keys: Mapping[str, str], state_repo: str, visibility: Mapping[str, str | None]
) -> list[tuple[str, str]]:
    """`(key, repo)` for each key in *keys* (key -> OWNER/REPO) whose repo is not public,
    when the state repo is public; `[]` otherwise. An unknown key repo is not public."""
    if not is_public(visibility.get(state_repo)):
        return []
    return [(k, r) for k, r in sorted(keys.items()) if not is_public(visibility.get(r))]


def leak_risk(
    keys: Mapping[str, str], state_repo: str, visibility: Mapping[str, str | None]
) -> bool:
    """True iff a key's repo is private and the state repo public (R8)."""
    return bool(leaks(keys, state_repo, visibility))


def check_or_refuse(
    keys: Mapping[str, str], state_repo: str, visibility: Mapping[str, str | None]
) -> None:
    """Raise `PrivacyError` naming every leaking issue, its repo and the state repo; or
    when the state repo's visibility is unknown and some key is not public."""
    if visibility.get(state_repo) is None:
        if any(not is_public(visibility.get(r)) for r in keys.values()):
            raise PrivacyError(unreadable(state_repo))
        return
    found = leaks(keys, state_repo, visibility)
    if found:
        raise PrivacyError("; ".join(refusal(k, r, state_repo) for k, r in found))


def live_visibility(client: Any, repo: str) -> str | None:
    """*repo*'s visibility as the forge answers now, lowercased; None when it cannot be
    read (a failed call, an unsupported backend, an empty answer)."""
    try:
        value = client.repo_visibility(repo)
    except Exception:  # noqa: BLE001 - every failure is "unreadable", which refuses
        return None
    return value.lower() if isinstance(value, str) and value else None


def key_repos(keys: Iterable[str], scope: Scope, facts: Facts | None) -> dict[str, str]:
    """key -> OWNER/REPO: from the facts' issues when they hold it, else from the scope
    (an org's `owner/<name>`, a repo or group member named `<name>`). A key naming no
    repo of the scope is left out: it is `check`'s orphan, with no repo to read."""
    from_facts = {normalize_key(f"{i.repo.split('/', 1)[1]}#{i.number}"): i.repo
                  for i in (facts.issues if facts else [])}  # fmt: skip
    members = [scope.target] if scope.kind == "repo" else list(scope.repos)
    by_name = {r.split("/", 1)[1].lower(): r for r in members}
    out: dict[str, str] = {}
    for key in keys:
        canon = normalize_key(key)
        name = canon.split("#", 1)[0]
        repo = from_facts.get(canon) or by_name.get(name)
        if repo is None and scope.kind == "org":
            repo = f"{scope.owner}/{name}"
        if repo is not None:
            out[canon] = repo
    return out


def _fill(
    vis: dict[str, str | None], repos: Iterable[str], client_for: ClientFor
) -> dict[str, str | None]:
    for repo in sorted(set(repos) - vis.keys()):
        vis[repo] = live_visibility(client_for(repo), repo)
    return vis


def guard_write(
    new_keys: Iterable[str],
    *,
    scope: Scope,
    facts: Facts,
    state_repo: str | None,
    client_for: ClientFor,
) -> None:
    """Refuse a judgements write that adds *new_keys* when one is private and the state
    repo public. Visibility comes from facts; the forge is asked only for a repo facts do
    not name, and the state repo only when some new key is not public."""
    keys = list(new_keys)
    if state_repo is None or not keys:
        return
    repos = key_repos(keys, scope, facts)
    vis: dict[str, str | None] = dict(facts.visibility)
    _fill(vis, repos.values(), client_for)
    if all(is_public(vis.get(r)) for r in repos.values()):
        return
    _fill(vis, [state_repo], client_for)
    check_or_refuse(repos, state_repo, vis)


def state_keys(state_dir: Path) -> list[str]:
    """Every issue key the state directory's ref files name: judged issues, batch and
    pattern members, and classified origins. An unreadable file is a `TriageError`:
    what cannot be read cannot be shown safe."""
    from fr.triage.origins import load_origins

    keys: set[str] = set()
    path = state_dir / "judgements.yaml"
    if path.exists():
        judgements = load_judgements(path)
        keys |= set(judgements.issues)
        keys |= {k for b in judgements.batches for k in b.ids}
        keys |= {k for p in judgements.patterns for k in p.ids}
    keys |= set(load_origins(state_dir / "origins.yaml").issues)
    return sorted(normalize_key(k) for k in keys)


def guard_state(state_dir: Path, *, scope: Scope, state_repo: str, client_for: ClientFor) -> None:
    """Refuse to push or export *state_dir* to *state_repo* when that would leak (R8). The
    state repo's visibility is read live first, and unreadable refuses; only when it is
    public are the keys read, their repos' visibility taken from facts (when present and
    for this scope) or read live."""
    now = live_visibility(client_for(state_repo), state_repo)
    if now is None:
        raise PrivacyError(unreadable(state_repo))
    if not is_public(now):
        return
    facts_path = state_dir / "facts.json"
    facts = None
    if facts_path.exists():
        try:
            facts = load_scope_facts(facts_path, scope)
        except TriageError:
            facts = None  # unusable facts: every repo is read live instead
    repos = key_repos(state_keys(state_dir), scope, facts)
    vis: dict[str, str | None] = dict(facts.visibility) if facts else {}
    vis[state_repo] = now
    _fill(vis, repos.values(), client_for)
    check_or_refuse(repos, state_repo, vis)
