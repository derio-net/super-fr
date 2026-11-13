"""Merged status outside `repo` (spec 2026-11-04-repo-feature-settings R17's quiet and
stealth clause, R25; plan 2026-11-12-placement-resolver phase 5).

Under `repo` a feature is merged when its fragments are on the default ref. Under quiet
and stealth the default ref holds no fr file (R23, R24), so a feature's merged status
and its ORDER come from its code branch's merge into the product's default ref:

- **The head.** A feature root names its branch in `OWNER`. Its heads are that branch's
  live refs in the product repository (`refs/heads/<b>`, `refs/remotes/origin/<b>`),
  every one of which must be merged; with neither (the branch was deleted after its
  merge), the head the last `merged:` record verified, else the product heads stealth
  recorded for the feature's runs (`<run-id>.stealth.json`).
- **Merged** iff every head is reachable from the default ref. **Order**: the
  first-parent commit of the default ref that introduced it (the earliest one every
  head is an ancestor of), ties broken by feature id.
- **The cache.** `features/<feature-id>/merged.yaml` is a list of `{merged: <sha>,
  head: <sha>}` records, appended by `fr archive --branch` (R25) and never rewritten.
  A record agreeing with the truth (its sha IS the introducing commit) is a cache hit;
  one disagreeing is ignored with a notice. It never makes a feature merged on its own:
  even the head it carries is re-verified on every read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml

from fr.artifacts import paths

MERGED_FILE: Final = "merged.yaml"
"""`<root>/features/<feature-id>/merged.yaml`: the feature's merged-status cache (R25)."""


@dataclass(frozen=True)
class MergedFeature:
    """One merged feature: its id, root, branch, and where it entered the default ref."""

    feature: str
    root: Path
    branch: str | None
    sha: str
    """The first-parent commit of the default ref that introduced the feature."""
    heads: tuple[str, ...]
    position: int
    """*sha*'s index in the default ref's first-parent history, oldest first."""
    cached: bool
    """A `merged:` record already says exactly this (R25's archive is done)."""


@dataclass(frozen=True)
class MergedView:
    """Every feature root of a space, split into merged (in merge order) and not."""

    ref: str | None
    features: tuple[MergedFeature, ...]
    unmerged: tuple[str, ...]
    notices: tuple[str, ...]

    def get(self, feature: str) -> MergedFeature | None:
        return next((f for f in self.features if f.feature == feature), None)


@dataclass(frozen=True)
class CacheRecord:
    merged: str
    head: str | None


def merged_file(feature_root: Path) -> Path:
    return Path(feature_root) / MERGED_FILE


def read_cache(feature_root: Path) -> tuple[list[CacheRecord], str | None]:
    """The feature's `merged:` records (oldest first) and a notice when the file is not a
    readable list (a cache that cannot be read is no cache, never a failure)."""
    path = merged_file(feature_root)
    if not path.is_file():
        return [], None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        return [], f"{path}: unreadable merged cache ({e}); ignored"
    if data is None:
        return [], None
    if not isinstance(data, list):
        return [], f"{path}: merged cache is not a list; ignored"
    out: list[CacheRecord] = []
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get("merged"), str):
            continue
        head = entry.get("head")
        out.append(CacheRecord(entry["merged"].strip(), head if isinstance(head, str) else None))
    return out, None


def record_text(sha: str, heads: tuple[str, ...]) -> str:
    """The YAML appended for one record: a list item, so the file stays a valid list."""
    lines = [f"- merged: {sha}"]
    if heads:
        lines.append(f"  head: {heads[-1]}")
    return "\n".join(lines) + "\n"


def append_record(feature_root: Path, sha: str, heads: tuple[str, ...]) -> Path:
    """Append one `merged:` record to the feature's cache (R25: append-only)."""
    path = merged_file(feature_root)
    before = path.read_text(encoding="utf-8") if path.is_file() else ""
    if before and not before.endswith("\n"):
        before += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(before + record_text(sha, heads), encoding="utf-8")
    return path


class _Git:
    """Read-only git in the product repository."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def out(self, *args: str) -> str | None:
        from fr.git import GitUnavailableError, git_answer

        try:
            done = git_answer(self.root, *args)
        except GitUnavailableError:
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    def commit(self, rev: str) -> str | None:
        return self.out("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}") or None

    def is_ancestor(self, a: str, b: str) -> bool:
        from fr.git import GitUnavailableError, git_answer

        try:
            return git_answer(self.root, "merge-base", "--is-ancestor", a, b).returncode == 0
        except GitUnavailableError:
            return False


def default_ref(product_root: Path) -> tuple[str | None, str | None]:
    """(`refs/remotes/<remote>/<branch>`, None) or (None, why there is none)."""
    from fr.git import GitRefusal, GitUnavailableError, remote_default_ref

    try:
        named = remote_default_ref(Path(product_root))
    except GitUnavailableError as e:
        return None, f"cannot establish the default branch: {e}"
    if isinstance(named, GitRefusal):
        return None, f"cannot establish the default branch: {named.reason}"
    if named is None:
        return None, "no default ref (no remote, or none fetched): no feature is merged"
    return f"refs/remotes/{named}", None


def _stealth_heads(feature_root: Path) -> list[str]:
    from fr.placement.stealth import PLACEMENT_SUFFIX

    runs = paths.below(feature_root, "run")
    out: list[str] = []
    if not runs.is_dir():
        return out
    for p in sorted(runs.glob(f"*{PLACEMENT_SUFFIX}")):
        try:
            head = json.loads(p.read_text()).get("product_head")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(head, str) and head:
            out.append(head)
    return out


def _heads(
    git: _Git, feature_root: Path, branch: str | None, cache: list[CacheRecord]
) -> list[str]:
    """The heads that must all be on the default ref (see the module docstring)."""
    live: list[str] = []
    if branch:
        for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"):
            sha = git.commit(ref)
            if sha and sha not in live:
                live.append(sha)
    if live:
        return live
    recorded = next((r.head for r in reversed(cache) if r.head), None)
    if recorded:
        return [recorded]
    return list(dict.fromkeys(_stealth_heads(feature_root)))


def _introduced(git: _Git, history: list[str], head: str) -> int:
    """The index of the first commit of *history* (first-parent, oldest first) that
    *head* is an ancestor of; the caller knows the last one is. Ancestry is monotone
    along a first-parent chain, so a binary search asks git log2(n) times."""
    lo, hi = 0, len(history) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if git.is_ancestor(head, history[mid]):
            hi = mid
        else:
            lo = mid + 1
    return lo


def merged_features(space: paths.ArtifactSpace, product_root: Path) -> MergedView:
    """Every feature root of *space*, merged (ordered by R17) or not, judged against the
    default ref of the product repository at *product_root*. Under `repo` there are no
    feature roots to judge: an empty view."""
    if space.placement == paths.REPO:
        return MergedView(None, (), (), ())
    roots = list(paths.feature_roots(space))
    ref, why = default_ref(product_root)
    notices: list[str] = []
    if ref is None:
        return MergedView(None, (), tuple(r.name for r in roots), (why,) if why and roots else ())
    git = _Git(product_root)
    tip = git.commit(ref)
    listed = git.out("rev-list", "--first-parent", "--reverse", ref) if tip else None
    history = listed.split() if listed else []
    index = {sha: i for i, sha in enumerate(history)}
    default_branch = ref.split("/", 3)[-1]
    from fr.placement.quiet import owner_of

    merged: list[MergedFeature] = []
    unmerged: list[str] = []
    for root in roots:
        fid = root.name
        branch = owner_of(space.root, fid)
        cache, problem = read_cache(root)
        if problem:
            notices.append(problem)
        if branch == default_branch or not history:
            unmerged.append(fid)
            continue
        heads = _heads(git, root, branch, cache)
        resolved = [git.commit(h) for h in heads]
        on_ref = bool(heads) and all(h is not None and git.is_ancestor(h, ref) for h in resolved)
        last = cache[-1] if cache else None
        if not on_ref:
            unmerged.append(fid)
            if last is not None:
                notices.append(
                    f"{merged_file(root)}: `merged: {last.merged}` ignored: {fid}'s branch "
                    f"{branch or '(unknown)'} is not merged into {ref} (a cache, never the truth)"
                )
            continue
        good = [h for h in resolved if h is not None]
        if last is not None and _agrees(git, history, index, last.merged, good):
            pos = index[last.merged]
            cached = True
        else:
            pos = max(_introduced(git, history, h) for h in good)
            cached = False
            if last is not None:
                notices.append(
                    f"{merged_file(root)}: `merged: {last.merged}` ignored: {fid} entered "
                    f"{ref} at {history[pos]} (a cache, never the truth)"
                )
        merged.append(MergedFeature(fid, root, branch, history[pos], tuple(good), pos, cached))
    merged.sort(key=lambda f: (f.position, f.feature))
    return MergedView(ref, tuple(merged), tuple(unmerged), tuple(notices))


def _agrees(
    git: _Git, history: list[str], index: dict[str, int], sha: str, heads: list[str]
) -> bool:
    """A record agrees when its sha is on the default ref's first-parent history, every
    head is an ancestor of it, and of no first-parent commit before it."""
    pos = index.get(sha)
    if pos is None:
        return False
    if not all(git.is_ancestor(h, sha) for h in heads):
        return False
    return pos == 0 or not all(git.is_ancestor(h, history[pos - 1]) for h in heads)


__all__ = [
    "MERGED_FILE",
    "CacheRecord",
    "MergedFeature",
    "MergedView",
    "append_record",
    "default_ref",
    "merged_features",
    "merged_file",
    "read_cache",
]
