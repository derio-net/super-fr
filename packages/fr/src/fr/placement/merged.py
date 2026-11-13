"""Merged status outside `repo` (spec 2026-11-04-repo-feature-settings R17's quiet and
stealth clause, R25; plan 2026-11-12-placement-resolver phase 5).

Under `repo` a feature is merged when its fragments are on the default ref. Under quiet
and stealth the default ref holds no fr file (R23, R24), so a feature's merged status
and its ORDER come from its code branch's merge into the product's default ref.

- **Its own commits.** A feature root names its branch in `OWNER` and, written by the
  same first fr commit, the product commit the branch stood on when it claimed the root
  in `BASE` (its merge base with the default ref). Only commits `BASE` does not contain
  are the feature's: a branch fresh from the default ref, or behind it, has none, and is
  never merged (review p5-r1). A root with no `BASE` (claimed before fr wrote one) is
  merged only through the forge, and says so.
- **Its heads.** The branch's live refs in the product repository (`refs/heads/<b>`,
  `refs/remotes/<remote>/<b>`, the remote the default ref names) plus the heads fr
  recorded for it: `HEADS` (one sha a line, appended by `fr push`) and the product heads
  stealth recorded per run (`<run-id>.stealth.json`). The recorded ones are owned
  evidence that outlives the branch's refs (review p5-r3).
- **Merged (git)** iff at least one head holds a commit of the feature's own and is
  reachable from the default ref: a true merge or a fast-forward. **Order**: the
  first-parent commit of the default ref that introduced the earliest such head, ties
  broken by feature id. Monotone: a later commit on the branch, or a deleted branch,
  never un-merges a feature whose recorded head is on the default ref.
- **Merged (forge).** A squash or a rebase merge leaves no head on the default ref; the
  forge's merged PR for the head branch does (review p5-r2, a READ: the stealth forge
  guard blocks writes only). Its merge commit must be on the default ref's first-parent
  line, after `BASE`, which gives the order. Only the callers that may reach a forge pass
  one (`fr archive --branch`, `fr acceptance status`); without it such a feature is
  unmerged, and those commands say why.
- **The cache.** `features/<feature-id>/merged.yaml` is a list of `{merged: <sha>,
  head: <sha>[, pr: <n>]}` records, appended by `fr archive --branch` (R25) and never
  rewritten. A record agreeing with the truth is a cache hit; one disagreeing is ignored
  with a notice. It never makes a feature merged on its own (review p5-r4): a git merge
  is re-derived from the heads, and a forge merge's record (`pr:`) counts only when its
  head is one fr recorded for the feature and neither it nor its merge commit is in
  `BASE`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

import yaml

from fr.artifacts import paths

if TYPE_CHECKING:
    from fr.ghclient import GhClient

MERGED_FILE: Final = "merged.yaml"
"""`<root>/features/<feature-id>/merged.yaml`: the feature's merged-status cache (R25)."""


@dataclass(frozen=True)
class MergedPr:
    """One merged pull request of a head branch, as the forge reports it."""

    number: int
    head: str | None
    merge_commit: str


class MergedPrs(Protocol):
    """The one forge read merged status makes: a head branch's merged PRs."""

    def merged_prs(self, branch: str) -> list[MergedPr]: ...


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
    how: str = "git"
    """`git` (a head is on the default ref), `forge` (a merged PR), `record` (a
    corroborated record of an earlier forge read)."""
    pr: int | None = None


@dataclass(frozen=True)
class MergedView:
    """Every feature root of a space, split into merged (in merge order) and not."""

    ref: str | None
    features: tuple[MergedFeature, ...]
    unmerged: tuple[str, ...]
    notices: tuple[str, ...]
    forge: str = "not read"
    """What the forge said: `read`, `not read` (no forge was given or asked), or why it
    could not be read."""

    def get(self, feature: str) -> MergedFeature | None:
        return next((f for f in self.features if f.feature == feature), None)

    def no_merge(self, branch: str) -> str:
        """Why *branch* reads unmerged, for the commands that report it."""
        where = self.ref or "the default ref"
        forge = (
            "the forge has no merged PR for it on that line"
            if self.forge == "read"
            else f"the forge was {self.forge}"
        )
        return (
            f"{branch} is not merged into {where}: git found no merge of its own commits "
            f"there (R17), and {forge}. A squash or rebase merge is found only through "
            "the forge's merged PR, so it needs the forge readable"
        )


@dataclass(frozen=True)
class CacheRecord:
    merged: str
    head: str | None
    pr: int | None = None


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
        pr = entry.get("pr")
        out.append(
            CacheRecord(
                entry["merged"].strip(),
                head.strip() if isinstance(head, str) else None,
                pr if isinstance(pr, int) and not isinstance(pr, bool) else None,
            )
        )
    return out, None


def record_text(sha: str, heads: tuple[str, ...], pr: int | None = None) -> str:
    """The YAML appended for one record: a list item, so the file stays a valid list."""
    lines = [f"- merged: {sha}"]
    if heads:
        lines.append(f"  head: {heads[-1]}")
    if pr is not None:
        lines.append(f"  pr: {pr}")
    return "\n".join(lines) + "\n"


def _append(path: Path, text: str) -> Path:
    before = path.read_text(encoding="utf-8") if path.is_file() else ""
    if before and not before.endswith("\n"):
        before += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(before + text, encoding="utf-8")
    return path


def append_record(
    feature_root: Path, sha: str, heads: tuple[str, ...], *, pr: int | None = None
) -> Path:
    """Append one `merged:` record to the feature's cache (R25: append-only)."""
    return _append(merged_file(feature_root), record_text(sha, heads, pr))


_FULL_SHA: Final = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
"""A full SHA-1 or SHA-256 commit id: the only thing BASE, HEADS and a stealth
placement file's `product_head` may hold. They are input from whoever can push to the
placement's repo and reach git argv, so anything else is dropped (lens l-security-r2)."""


def is_full_sha(text: str) -> bool:
    return bool(_FULL_SHA.fullmatch(text))


def _sha_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [line.strip() for line in text.splitlines() if is_full_sha(line.strip())]


def base_of(feature_root: Path) -> str | None:
    """The product commit the feature claimed its root from (`BASE`), or None."""
    found = _sha_lines(Path(feature_root) / paths.FEATURE_BASE)
    return found[0] if found else None


def recorded_heads(feature_root: Path) -> list[str]:
    """The product heads `fr push` recorded for the feature (`HEADS`), oldest first."""
    return list(dict.fromkeys(_sha_lines(Path(feature_root) / paths.FEATURE_HEADS)))


def record_head(feature_root: Path, sha: str) -> Path | None:
    """Append *sha* to the feature's `HEADS` (append-only); the file when it changed,
    None when it already held *sha*."""
    if sha in recorded_heads(feature_root):
        return None
    return _append(Path(feature_root) / paths.FEATURE_HEADS, f"{sha}\n")


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
        if isinstance(head, str) and is_full_sha(head):
            out.append(head)
    return out


def owned_heads(feature_root: Path) -> list[str]:
    """Every head fr itself recorded for the feature: `HEADS`, then stealth's."""
    return list(dict.fromkeys([*recorded_heads(feature_root), *_stealth_heads(feature_root)]))


class _Git:
    """Read-only git in one repository."""

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


def remote_of(ref: str) -> str:
    """The remote a `refs/remotes/<remote>/<branch>` ref names (review p5-r6)."""
    return ref.removeprefix("refs/remotes/").split("/", 1)[0]


def _live_heads(git: _Git, branch: str | None, remote: str) -> list[str]:
    out: list[str] = []
    if branch:
        for ref in (f"refs/heads/{branch}", f"refs/remotes/{remote}/{branch}"):
            sha = git.commit(ref)
            if sha and sha not in out:
                out.append(sha)
    return out


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


@dataclass
class _Line:
    """The default ref's first-parent line, read once per view."""

    git: _Git
    ref: str
    history: list[str]
    index: dict[str, int]

    def own(self, sha: str, base: str) -> bool:
        """*sha* is on the default ref and holds a commit *base* does not."""
        return self.git.is_ancestor(sha, self.ref) and not self.git.is_ancestor(sha, base)


def _corroborated(line: _Line, rec: CacheRecord, base: str | None, owned: list[str]) -> bool:
    """A forge merge's record counts only on owned evidence (review p5-r4): its head is
    one fr recorded for the feature, its merge commit is on the first-parent line, and
    neither is in the base."""
    if rec.pr is None or rec.head is None or base is None or rec.merged not in line.index:
        return False
    if rec.head not in owned:
        return False
    git = line.git
    return not git.is_ancestor(rec.merged, base) and not git.is_ancestor(rec.head, base)


@dataclass
class _Judge:
    line: _Line
    forge: MergedPrs | None
    notices: list[str]
    forge_state: str = "not read"

    def _forge_hit(self, branch: str, base: str | None) -> tuple[int, MergedPr] | None:
        if self.forge is None:
            return None
        try:
            prs = self.forge.merged_prs(branch)
        except Exception as e:  # a forge failure is "unmerged, and why", never a crash
            self.forge_state = f"unreadable ({type(e).__name__}: {e})"
            return None
        if self.forge_state == "not read":
            self.forge_state = "read"
        git = self.line.git
        hits = [
            (self.line.index[p.merge_commit], p)
            for p in prs
            if p.merge_commit in self.line.index
            and (base is None or not git.is_ancestor(p.merge_commit, base))
        ]
        return min(hits, key=lambda t: t[0]) if hits else None

    def __call__(self, root: Path, branch: str | None) -> MergedFeature | None:
        fid = root.name
        line, git = self.line, self.line.git
        cache, problem = read_cache(root)
        if problem:
            self.notices.append(problem)
        base = base_of(root)
        if base is not None and git.commit(base) is None:
            self.notices.append(
                f"{root / paths.FEATURE_BASE}: {base} is not a commit this clone holds; "
                f"{fid}'s own commits cannot be told apart"
            )
            base = None
        owned = owned_heads(root)
        live = _live_heads(git, branch, remote_of(line.ref))
        found: list[tuple[int, str]] = []
        if base is None:
            if live or owned or cache:
                self.notices.append(
                    f"{fid} records no {paths.FEATURE_BASE} (its root was claimed before fr "
                    "wrote one), so git cannot tell its commits from the default ref's: it "
                    "is merged only through the forge's merged PR"
                )
        else:
            for head in dict.fromkeys([*live, *owned]):
                sha = git.commit(head)
                if sha is not None and line.own(sha, base):
                    found.append((_introduced(git, line.history, sha), sha))
        how: str = "git"
        pr: int | None = None
        heads = tuple(sha for _, sha in found)
        pos: int | None = min(p for p, _ in found) if found else None
        if pos is None:
            rec = next((r for r in reversed(cache) if _corroborated(line, r, base, owned)), None)
            if rec is not None and rec.head is not None:
                how, pr, heads, pos = "record", rec.pr, (rec.head,), line.index[rec.merged]
        if pos is None and branch:
            hit = self._forge_hit(branch, base)
            if hit is not None:
                pos, merged_pr = hit
                how, pr = "forge", merged_pr.number
                heads = (merged_pr.head,) if merged_pr.head else ()
        last = cache[-1] if cache else None
        if pos is None:
            if last is not None:
                self.notices.append(
                    f"{merged_file(root)}: `merged: {last.merged}` ignored: {fid}'s branch "
                    f"{branch or '(unknown)'} is not merged into {line.ref} by anything fr "
                    "can verify (a cache, never the truth)"
                )
            return None
        sha = line.history[pos]
        cached = last is not None and last.merged == sha
        if last is not None and not cached:
            self.notices.append(
                f"{merged_file(root)}: `merged: {last.merged}` ignored: {fid} entered "
                f"{line.ref} at {sha} (a cache, never the truth)"
            )
        return MergedFeature(fid, root, branch, sha, heads, pos, cached, how, pr)


def merged_features(
    space: paths.ArtifactSpace, product_root: Path, *, forge: MergedPrs | None = None
) -> MergedView:
    """Every feature root of *space*, merged (ordered by R17) or not, judged against the
    default ref of the product repository at *product_root*; *forge* finds squash and
    rebase merges. Under `repo` there are no feature roots to judge: an empty view."""
    if space.placement == paths.REPO:
        return MergedView(None, (), (), ())
    roots = list(paths.feature_roots(space))
    ref, why = default_ref(product_root)
    if ref is None:
        return MergedView(None, (), tuple(r.name for r in roots), (why,) if why and roots else ())
    git = _Git(product_root)
    tip = git.commit(ref)
    listed = git.out("rev-list", "--first-parent", "--reverse", ref) if tip else None
    history = listed.split() if listed else []
    line = _Line(git, ref, history, {sha: i for i, sha in enumerate(history)})
    default_branch = ref.removeprefix("refs/remotes/").split("/", 1)[-1]
    from fr.placement.quiet import owner_of

    judge = _Judge(line, forge, [])
    merged: list[MergedFeature] = []
    unmerged: list[str] = []
    for root in roots:
        branch = owner_of(space.root, root.name)
        feature = None if branch == default_branch or not history else judge(root, branch)
        if feature is None:
            unmerged.append(root.name)
        else:
            merged.append(feature)
    merged.sort(key=lambda f: (f.position, f.feature))
    return MergedView(ref, tuple(merged), tuple(unmerged), tuple(judge.notices), judge.forge_state)


# --- the fr commit a merged feature's fragments are frozen at (review p5-r5) --------


def pushed_ref(feature_root: Path, placement: str) -> tuple[Path, str] | None:
    """(the placement repo's toplevel, its pushed ref): `origin/fr` under quiet, the
    tracking branch's remote ref under stealth. A merged feature is read from what was
    PUSHED, never from a host's unpushed commits."""
    top = _Git(feature_root).out("rev-parse", "--show-toplevel")
    if not top:
        return None
    if placement == paths.QUIET:
        return Path(top), paths.SWITCH_REF
    there = _Git(Path(top))
    upstream = there.out("rev-parse", "--symbolic-full-name", "@{upstream}")
    if upstream:
        return Path(top), upstream
    branch = there.out("symbolic-ref", "--short", "HEAD")
    return (Path(top), f"refs/remotes/origin/{branch}") if branch else None


def _rel(feature_root: Path, top: Path) -> str:
    return Path(feature_root).resolve().relative_to(top.resolve()).as_posix()


def frozen_commit(
    feature: MergedFeature, placement: str, product_root: Path
) -> tuple[str | None, str | None]:
    """(the last PUSHED fr commit touching *feature*'s root at or before its merge
    commit's committer time, a notice when there is none). Its fragments are the merged
    ones; anything the feature's path gained later is pending on its branch."""
    when = _Git(product_root).out("log", "-1", "--format=%ct", feature.sha)
    found = pushed_ref(feature.root, placement)
    if not when or found is None:
        return None, f"{feature.feature}: cannot read the fr history its merge is frozen at"
    top, ref = found
    rel = _rel(feature.root, top)
    sha = _Git(top).out("log", "-1", "--format=%H", f"--before={when}", ref, "--", rel)
    if not sha:
        return None, (
            f"{feature.feature}: no pushed fr commit of {rel} at or before its merge at "
            f"{feature.sha[:12]}; none of its fragments count as merged"
        )
    return sha, None


def files_at(feature_root: Path, placement: str, commit: str, sub: str) -> dict[str, str]:
    """Every file below *sub* of *feature_root* at the placement repo's *commit*, keyed
    relative to the feature root."""
    found = pushed_ref(feature_root, placement)
    if found is None:
        return {}
    top = found[0]
    rel = _rel(feature_root, top)
    there = _Git(top)
    listed = there.out("ls-tree", "-r", "--name-only", commit, "--", f"{rel}/{sub}")
    out: dict[str, str] = {}
    for name in (listed or "").splitlines():
        text = there.out("show", f"{commit}:{name}")
        if text is not None:
            out[name.removeprefix(f"{rel}/")] = text + "\n"
    return out


# --- the forge read (review p5-r2) -----------------------------------------------


class ClientMergedPrs:
    """`MergedPrs` over the `GhClient` adapter: the head branch's merged PRs from this
    repository (a fork's PR of the same branch name is not this feature's), each with
    its merge commit and head. Reads only."""

    def __init__(self, client: GhClient, repo: str) -> None:
        self._client = client
        self._repo = repo

    def merged_prs(self, branch: str) -> list[MergedPr]:
        out: list[MergedPr] = []
        for pr in self._client.list_prs_by_head(self._repo, branch):
            merged = pr.get("mergedAt") or str(pr.get("state") or "").upper() == "MERGED"
            if not merged or pr.get("isCrossRepository") or pr.get("headRefName") != branch:
                continue
            number = int(pr["number"])
            view = self._client.pr_view(self._repo, number)
            commit = str(view.get("merge_commit") or "")
            if commit:
                head = view.get("head_oid") or pr.get("headRefOid") or None
                out.append(MergedPr(number, str(head) if head else None, commit))
        return out


def forge_for(product_root: Path) -> tuple[MergedPrs | None, str]:
    """The forge merged status may read for *product_root*, or (None, why not). Never
    raises: a forge that cannot be built is "not read", and the caller says so."""
    from fr import _hosts

    slug = _hosts.origin_slug(Path(product_root))
    if not slug:
        return None, "not read (no origin remote names a forge repository)"
    try:
        from fr.hostclient import client_for

        client = client_for(Path(product_root))
    except Exception as e:
        return None, f"not read ({type(e).__name__}: {e})"
    return ClientMergedPrs(client, slug), ""


__all__ = [
    "MERGED_FILE",
    "CacheRecord",
    "ClientMergedPrs",
    "MergedFeature",
    "MergedPr",
    "MergedPrs",
    "MergedView",
    "append_record",
    "base_of",
    "default_ref",
    "files_at",
    "forge_for",
    "frozen_commit",
    "merged_features",
    "merged_file",
    "owned_heads",
    "pushed_ref",
    "read_cache",
    "record_head",
    "recorded_heads",
    "remote_of",
]
