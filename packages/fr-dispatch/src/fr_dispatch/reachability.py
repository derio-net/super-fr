"""`check_reachable` — the §4.E gate over an item graph (Phase 8).

**A step's `needs` are inputs and must be reachable; its `emits` are
outputs and need not be.** By the time a `WorkItem` exists that rule has
already been applied: `item_graph.build_items` gives an item an
`ArtifactRef` for exactly the artifacts its shape requires, so this module
asks one question per ref — is it on `origin/HEAD`? — and never consults
the manifest again.

That is why the asymmetry falls out instead of being coded: a `unit: run`
item of a shape that emits its spec and plan carries **no** refs, so it
dispatches against a tree where neither exists; a `unit: phase` item
carries both, so it still refuses an unmerged plan.

The local half delegates to `fr.workflow.reachability.unreachable_paths`,
so `fr apply`'s gate and this one cannot drift about what "on origin/HEAD"
means. `fr apply` does not merely share that primitive — it walks **this**
module over **this** graph (`unreachable_inputs`), so §4.E's promise of one
derived rule is one function rather than two that happen to agree today
(review r5-a1: before it, `apply_cmd` rebuilt the path list by hand from
`required_inputs`, and the two already disagreed about cross-repo).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fr.workflow.reachability import ORIGIN_HEAD, unreachable_paths

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from fr.ghclient import GhClient

    from fr_dispatch.work_item import ArtifactRef, WorkItem

__all__ = ["Unreachable", "check_reachable", "unreachable_inputs", "unverifiable_inputs"]


@dataclass(frozen=True)
class Unreachable:
    """One item's declared inputs that are not on `origin/HEAD`.

    `paths` are *coordinates as the operator must read them*: a
    repo-relative path for a local ref, `"<owner>/<repo>:<path>"` for one
    answered through the tracker — the same strings the refusal prints.
    """

    item: WorkItem
    paths: tuple[str, ...]


def _home_repo_of(item: WorkItem, override: str | None) -> str:
    """Which repo `repo_root` is a checkout of, for THIS item.

    Not `item.repo` (review r5-a1). A phase tracked by an Issue in another
    repo is keyed on the *Issue's* repo — `_phase_items` does that
    deliberately, because `can_dispatch(item)` routes on `item.repo` — while
    its plan and spec still live in `target_repo`, which is what the
    checkout holds. Comparing against `item.repo` therefore classified the
    plan's OWN ref as cross-repo and skipped the local check outright: an
    unmerged plan passed the gate.

    The plan ref *is* the home coordinate (`plan_artifact_refs` always emits
    it at `plan.meta.target_repo`), so it is the default. An explicit
    `home_repo` wins, and an item with no plan ref falls back to `item.repo`
    — the pre-review behaviour, which is the best available answer when the
    item carries nothing better.
    """
    if override is not None:
        return override
    for ref in item.inputs:
        if ref.kind == "plan":
            return ref.repo
    return item.repo


def _missing_remotely(ref: ArtifactRef, gh: GhClient) -> bool:
    """Is `ref` absent from its own repo, read through the tracker?

    A `plan` ref names a **folder**, and `file_exists` asks the contents API
    a question about a file. GitHub happens to answer 200 with a JSON array
    for a directory, so the probe was accidentally right — but "accidentally
    right on one backend" is not a contract (`fr` also speaks glab and tea),
    and an *empty* directory would read as present. `list_dir` is the
    dir-aware read `fr spec status` already uses for exactly this, and it
    returns `[]` for both "absent" and "empty" — the safe direction here.
    """
    if ref.kind == "plan":
        return not gh.list_dir(ref.repo, ref.path)
    return not gh.file_exists(ref.repo, ref.path)


def unreachable_inputs(
    items: Sequence[WorkItem],
    repo_root: Path,
    *,
    gh: GhClient | None = None,
    home_repo: str | None = None,
) -> list[Unreachable]:
    """Per item, which declared inputs are not on `origin/HEAD`.

    The one derivation. `check_reachable` formats the first offender into a
    refusal string for a runner tick; `fr apply`'s gate flattens the local
    coordinates into the `list[Path]` its JSON output has published since
    the 2026-05-17 design. Neither rebuilds the rule.

    `repo_root` is the checkout the *local* refs are resolved against, and
    `home_repo` names the repo it is a checkout of (see `_home_repo_of` for
    the default). A ref naming a **different** repo cannot be answered by
    this repo's git at all: with `gh` it is resolved through the tracker's
    contents API (the same read path `compute_status` uses for a cross-repo
    plan row), and without one it is skipped — which is precisely what the
    old gate did with a cross-repo spec, trusting the operator to keep it
    correct.
    """
    out: list[Unreachable] = []
    for item in items:
        home = _home_repo_of(item, home_repo)
        missing: list[str] = []
        for ref in item.inputs:
            if ref.repo != home:
                if gh is not None and _missing_remotely(ref, gh):
                    missing.append(f"{ref.repo}:{ref.path}")
                continue
            missing.extend(str(p) for p in unreachable_paths(repo_root, [ref.path]))
        if missing:
            out.append(Unreachable(item=item, paths=tuple(missing)))
    return out


def check_reachable(
    items: Sequence[WorkItem],
    repo_root: Path,
    *,
    gh: GhClient | None = None,
    home_repo: str | None = None,
) -> str | None:
    """`None` when every item's declared inputs are reachable, else a refusal.

    The returned string is a blocker in the same shape `runner.preflight`
    returns and the same wording the 2026-05-17 gate used — an operator who
    has seen `refuse to dispatch: N file(s) not at origin/HEAD` recognises
    it — with the item id added, because a tick carries many items and
    "which one" is the first question.
    """
    for u in unreachable_inputs(items, repo_root, gh=gh, home_repo=home_repo):
        return "\n".join(
            [
                f"{u.item.id}: refuse to dispatch: {len(u.paths)} file(s) not at {ORIGIN_HEAD}:",
                *(f"  {p}" for p in u.paths),
                "",
                "Merge the plan + spec to the default branch first, then re-run.",
            ]
        )
    return None


def unverifiable_inputs(
    items: Sequence[WorkItem],
    *,
    gh: GhClient | None = None,
    home_repo: str | None = None,
) -> list[ArtifactRef]:
    """Refs this gate CANNOT answer — cross-repo, with no client to ask.

    Skipping them is the right default and has been since the 2026-05-17 gate:
    a file in another repo is not resolvable by this repo's git, and the
    operator is trusted for it. What was wrong is that the skip was **silent**
    (review r5-e13), so a cross-repo dispatch reported the same clean verdict
    as a fully-verified one. Naming them keeps the default and removes the
    false confidence.

    Empty when `gh` is given: a client can be asked, so nothing is
    unverifiable — it is either reachable or reported missing.
    """
    if gh is not None:
        return []
    out: list[ArtifactRef] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        home = _home_repo_of(item, home_repo)
        for ref in item.inputs:
            key = (ref.repo, ref.path)
            if ref.repo != home and key not in seen:
                seen.add(key)
                out.append(ref)
    return out
