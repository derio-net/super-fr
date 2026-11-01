"""The delivering PR of an owed item (spec 2026-11-01-gate-backfill §C, R3).

An evidence chain, first step with a hit wins: `manifest` (a `pr:` override), `run` (a run
cursor that emitted the item's plan or spec → its branch's merged PR), `commit` (the merge on
the default ref of the commit that first added the plan or spec → the PR its subject names, or
the forge maps it to), `issue` (the merged PR linked to the issue). The chain never guesses: no
"newest PR touching the path" fallback. Every hit is confirmed merged through the forge; a
merge that touched only `docs/` is a planning PR; several merged PRs at one step are an
ambiguity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fr.gatebackfill.candidates import (
    IMPLEMENTED_PLANS_REL,
    IMPLEMENTED_SPECS_REL,
    PLANS_REL,
    SPECS_REL,
    Candidate,
)
from fr.gatebackfill.forge import BackfillForge, Git, pr_number_of
from fr.gatebackfill.model import PrHit
from fr.ghclient import UnsupportedForgeOperation

PR_SUBJECT_RE = re.compile(r"\(#(\d+)\)\s*$|^Merge pull request #(\d+)\b")
"""A squash merge's `(#N)` subject or a merge commit's `Merge pull request #N`."""


@dataclass(frozen=True)
class Delivery:
    """The answer for one candidate: a PR, an ambiguity (every number), or why neither."""

    pr: PrHit | None = None
    ambiguous: tuple[int, ...] = ()
    why: str = ""


def subject_pr(subject: str) -> int | None:
    m = PR_SUBJECT_RE.search(subject)
    return int(next(g for g in m.groups() if g)) if m else None


class DeliveryCache:
    """What is shared by every candidate of one run: each PR is read from the forge once, and
    the run cursors are parsed once into a `(plan names, spec names, branch)` index."""

    def __init__(self) -> None:
        self.views: dict[int, dict[str, object] | Exception] = {}
        self._cursors: list[tuple[frozenset[str], frozenset[str], str]] | None = None

    def cursors(self, root: Path) -> list[tuple[frozenset[str], frozenset[str], str]]:
        if self._cursors is None:
            from fr.run.cursors import all_cursors
            from fr.run.model import RunStateError, parse_run_state

            index = []
            for path in all_cursors(root):
                try:
                    state = parse_run_state(path.read_text())
                except (RunStateError, OSError):
                    continue
                if not state.branch:
                    continue
                emitted = [e for r in state.steps.values() for e in (r.emitted or {}).items()]
                plans = frozenset(Path(v).name for k, v in emitted if k == "plan")
                specs = frozenset(Path(v).name for k, v in emitted if k == "spec")
                index.append((plans, specs, state.branch))
            self._cursors = index
        return self._cursors


class _Chain:
    def __init__(
        self,
        root: Path,
        forge: BackfillForge,
        git: Git,
        ref: str | None,
        cache: DeliveryCache,
    ) -> None:
        self.root, self.forge, self.git, self.ref, self.cache = root, forge, git, ref, cache
        self.dropped: list[str] = []

    def _view(self, number: int) -> dict[str, object] | Exception:
        if number not in self.cache.views:
            try:
                self.cache.views[number] = dict(self.forge.pr_view(number))
            except Exception as exc:  # noqa: BLE001 — one unreadable PR degrades its entry only
                self.cache.views[number] = exc
        return self.cache.views[number]

    def confirm(self, number: int) -> dict[str, object] | None:
        """The PR's record when the forge says it is merged; else `None`, noting why."""
        view = self._view(number)
        if isinstance(view, Exception):
            self.dropped.append(f"PR unconfirmed: #{number}: {type(view).__name__}: {view}")
            return None
        state = str(view.get("state") or "UNKNOWN")
        if state != "MERGED":
            self.dropped.append(f"#{number} is {state}, not merged")
            return None
        return view

    def _merged(self, numbers: list[int]) -> list[int]:
        out: list[int] = []
        for n in dict.fromkeys(numbers):
            if self.confirm(n) is not None:
                out.append(n)
        return out

    def settle(self, numbers: list[int], basis: str, merge_sha: str | None) -> Delivery | None:
        merged = self._merged(numbers)
        if len(merged) > 1:
            return Delivery(ambiguous=tuple(sorted(merged)))
        if not merged:
            return None
        sha = merge_sha
        if sha is None:
            view = self.confirm(merged[0]) or {}
            sha = str(view.get("merge_commit") or "") or None
        planning = self._planning(sha) if sha and basis in ("commit", "run") else False
        return Delivery(pr=PrHit(number=merged[0], basis=basis, planning=planning))  # type: ignore[arg-type]

    def _planning(self, sha: str) -> bool:
        files = self.git.files(sha)
        return files is not None and bool(files) and all(f.startswith("docs/") for f in files)

    # --- the steps -------------------------------------------------------------------------

    def by_run(self, c: Candidate) -> Delivery | None:
        plans = set(c.plans)
        spec = Path(c.spec_rel).name if c.spec_rel else None
        numbers: list[int] = []
        branches: set[str] = set()
        for cur_plans, cur_specs, branch in self.cache.cursors(self.root):
            if not (plans & cur_plans or (spec and spec in cur_specs)) or branch in branches:
                continue
            branches.add(branch)
            try:
                records = self.forge.prs_by_head(branch)
            except Exception as exc:  # noqa: BLE001
                self.dropped.append(f"PR unconfirmed: {branch}: {type(exc).__name__}: {exc}")
                continue
            numbers += [
                n for r in records if str(r.get("state")) == "MERGED" and (n := pr_number_of(r))
            ]
        return self.settle(numbers, "run", None) if numbers else None

    def _origins(self, c: Candidate) -> list[list[str]]:
        """One group of paths per plan (or per spec): the live and the archived spelling of
        one thing, which has ONE origin commit — the oldest add among them (the archive PR's
        `git mv` reads as an add of the archived path)."""
        if c.plans:
            return [
                [(PLANS_REL / n).as_posix(), (IMPLEMENTED_PLANS_REL / n).as_posix()]
                for n in c.plans
            ]
        if c.spec_rel:
            name = Path(c.spec_rel).name
            return [[(SPECS_REL / name).as_posix(), (IMPLEMENTED_SPECS_REL / name).as_posix()]]
        return []

    def by_commit(self, c: Candidate) -> Delivery | None:
        if self.ref is None:
            return None
        numbers: list[int] = []
        merges: dict[int, str] = {}
        seen: set[str] = set()
        for paths in self._origins(c):
            sha = self.git.first_add(self.ref, *paths)
            merge = self.git.first_containing(self.ref, sha) if sha else None
            if merge is None or merge in seen:
                continue
            seen.add(merge)
            n = subject_pr(self.git.subject(merge))
            found = [n] if n is not None else self._forge_prs(merge)
            for pr in found:
                numbers.append(pr)
                merges.setdefault(pr, merge)
        if not numbers:
            return None
        merged = self._merged(numbers)
        if len(merged) > 1:
            return Delivery(ambiguous=tuple(sorted(merged)))
        if not merged:
            return None
        return self.settle(merged, "commit", merges[merged[0]])

    def _forge_prs(self, sha: str) -> list[int]:
        try:
            records = self.forge.prs_for_commit(sha)
        except UnsupportedForgeOperation:
            return []  # this forge cannot map a commit to a PR: the step yields nothing
        except Exception as exc:  # noqa: BLE001
            self.dropped.append(f"PR unconfirmed: commit {sha[:9]}: {type(exc).__name__}: {exc}")
            return []
        return [n for r in records if (n := pr_number_of(r))]

    def by_issue(self, c: Candidate) -> Delivery | None:
        if c.issue_number is None:
            return None
        try:
            records = self.forge.linked_prs(c.issue_number)
        except Exception as exc:  # noqa: BLE001
            self.dropped.append(f"PR unconfirmed: issue {c.issue_number}: {type(exc).__name__}")
            return None
        numbers = [
            n for r in records if (r.get("merged") or str(r.get("state")) == "MERGED")
            if (n := pr_number_of(r))
        ]  # fmt: skip
        return self.settle(numbers, "issue", None) if numbers else None


def delivering_pr(
    c: Candidate,
    *,
    root: Path,
    forge: BackfillForge,
    git: Git,
    ref: str | None,
    cache: DeliveryCache | None = None,
) -> Delivery:
    """The delivering PR of *c*, by the evidence chain. An explicit manifest `pr:` is the
    answer or the refusal, never a prompt to infer another."""
    chain = _Chain(root, forge, git, ref, cache if cache is not None else DeliveryCache())
    if c.manifest_pr is not None:
        got = chain.settle([c.manifest_pr], "manifest", None)
        if got is not None:
            return got
        reason = "; ".join(chain.dropped) or "not confirmed"
        return Delivery(why=f"manifest pr #{c.manifest_pr}: {reason}")
    for step in (chain.by_run, chain.by_commit, chain.by_issue):
        got = step(c)
        if got is not None:
            return got
    why = "; ".join(chain.dropped) or "no delivering PR found"
    return Delivery(why=why)
