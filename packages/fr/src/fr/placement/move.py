"""Moving a repo between placements (spec 2026-11-04-repo-feature-settings R27; plan
2026-11-12-placement-resolver phase 7).

`fr placement move --to repo|quiet|stealth [--tracking <repo>@<branch>]` moves a whole
repo's artifacts, archived features included; `--run <id>` moves one stealth run out of
its tracking repo. Four steps, as data (`STEP_FUNCS`), always in this order:

- **copy** writes every feature into the destination. From `repo` it reads the default
  ref's tree and groups each artifact into a feature (`_owner`), synthesising the
  feature's `OWNER`, `BASE`, `HEADS` and `merged:` record from the default ref's
  history (R27): the feature's head is the newest first-parent commit that touched its
  files, its base that commit's first parent. Into quiet each feature is one commit on
  `fr` (R23: one feature path per commit), dated at that head so the fold freezes the
  feature's fragments there (`fr.placement.merged.frozen_commit`), pushed plainly; into
  stealth the same commits go through the stealth push seam (privacy guard, CAS push).
  Out of quiet only MERGED features are copied, frozen at their merge: an unmerged one is
  a live branch's, and `fr placement migrate-branch` moves it. Into `repo` the copy is a
  branch off the default ref, which lands through a PR.
- **verify** re-reads the destination and refuses unless its files, its fold and its
  `fr validate artifacts` report equal the source's.
- **switch** makes the destination the placement: the quiet switch commit on `fr`, or
  `placement: repo` written there by a NEW commit (never a force push). Into `repo` it
  waits, paused, until the copy has landed on the default ref.
- **remove**: out of `repo`, a branch deleting the files from the default branch,
  pushed, with the `fr pr create` command printed and the reminder that git history
  still holds them; nothing is pushed to the default branch and no PR is opened.

Every step is idempotent and the state file `<git common dir>/fr-placement-move.json`
records the ones done, so a move killed anywhere completes when re-run, and a different
move refuses while one is in progress. A move refuses while any workspace of the repo
has uncommitted work.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Final

import yaml

from fr.artifacts import paths
from fr.settings import SettingsError

STEPS: Final = ("copy", "verify", "switch", "remove")
STATE_NAME: Final = "fr-placement-move.json"
BODY_NAME: Final = "fr-placement-move-pr.md"
MOVED: Final = "moved"
"""Owner prefix of a feature synthesised from repo artifacts no run names: `moved/<key>`
(feature id `moved__<key>`)."""
MERGED_FILE: Final = "merged.yaml"
META: Final = frozenset({paths.FEATURE_OWNER, paths.FEATURE_BASE, paths.FEATURE_HEADS, MERGED_FILE})
"""fr's own bookkeeping in a feature root, never a repo-layout artifact."""
TARGETS: Final = (paths.REPO, paths.QUIET, paths.STEALTH)
_ZERO: Final = "0" * 40
_FR_REF: Final = "refs/heads/fr"


class MoveError(SettingsError):
    """A move refused (exit 2); the state file keeps what was done."""


class _PausedError(Exception):
    """A step waits on the operator (the copy into `repo` is not merged yet)."""


class _SourceMovedError(Exception):
    """The source changed after the copy (a feature merged meanwhile): the move copies
    again rather than switch on a stale copy (review p7-r1)."""


MAX_RECOPIES: Final = 3
"""How many times one invocation re-copies a source that keeps moving before it refuses
and asks for a re-run."""


# --- git, in bytes ---------------------------------------------------------------------


def _git(
    root: Path,
    *args: str,
    data: bytes | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> bytes:
    from fr.git import git_argv

    done = subprocess.run(
        git_argv(root, *args),
        cwd=root,
        input=data,
        capture_output=True,
        timeout=120,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", **(env or {})},
        check=False,
    )
    if check and done.returncode != 0:
        why = done.stderr.decode(errors="replace").strip()
        raise MoveError(f"fr placement move: `git {' '.join(args)}` failed: {why}")
    return done.stdout


def _ok(root: Path, *args: str) -> bool:
    from fr.git import git_argv

    return (
        subprocess.run(git_argv(root, *args), cwd=root, capture_output=True, check=False)
    ).returncode == 0


def _sha(root: Path, rev: str) -> str | None:
    out = _git(root, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", check=False)
    return out.decode().strip() or None


def _tree(root: Path, commit: str, prefix: str = "") -> dict[str, tuple[str, str]]:
    """path -> (mode, blob) of every file at *commit*, below *prefix* when given."""
    argv = ["ls-tree", "-r", "-z", "--full-tree", commit]
    if prefix:
        argv += ["--", prefix]
    out: dict[str, tuple[str, str]] = {}
    for entry in _git(root, *argv).split(b"\0"):
        if not entry:
            continue
        meta, _, name = entry.partition(b"\t")
        mode, kind, sha = meta.decode().split()
        if kind in ("blob", "commit"):
            out[name.decode()] = (mode, sha)
    return out


LINK_MODES: Final = {"120000": "a symlink", "160000": "a submodule (gitlink)"}
"""Tree entries a move never copies: a symlink's target could be anything on the host
(`~/.ssh/...`), and a gitlink is another repository. Refused, naming the path."""


def refuse_links(entries: Mapping[str, tuple[str, str]], where: str) -> None:
    for path, (mode, _) in sorted(entries.items()):
        if mode in LINK_MODES:
            raise MoveError(
                f"fr placement move: refused: {path} in {where} is {LINK_MODES[mode]}; fr "
                "copies only regular files (a link could read or write outside the repo)"
            )


_HFS_IGNORABLE: Final = frozenset(
    [*range(0x200C, 0x2010), *range(0x202A, 0x202F), *range(0x206A, 0x2070), 0xFEFF]
)
"""Codepoints HFS+ ignores in a name (git's `is_hfs_dotgit` list): `.g\u200cit` IS `.git`."""
_GIT_NAMES: Final = frozenset({".git", ".gitmodules", ".gitattributes", ".gitignore"})
"""The names git itself acts on in a tree: the repository, its submodules, its
attributes (filters and diff drivers), its ignore rules. `.gitkeep` is a plain file,
and fr's acceptance tree carries one (`docs/acceptance/features/.gitkeep`), so it stays."""
_NTFS_SHORT: Final = re.compile(r"(?:git|gitmod|gitatt|gitign)~\d+|gi[0-9a-f]{4}~\d+")
"""NTFS 8.3 short names git refuses for those (`git~1`, `gitmod~1`, and the hashed
`gi7eba~1` forms)."""


def git_like(component: str) -> bool:
    """Is one path component `.git`, `.gitmodules` or `.gitattributes` on SOME
    filesystem? Read as git's `verify_path` reads it (review p7-r5, security
    follow-up): NFC-normalised, HFS-ignorable codepoints removed, trailing dots and
    spaces stripped (NTFS), casefolded (APFS, HFS+, NTFS); and the NTFS short names.
    A component holding `:` is refused outright: on NTFS `.git::$INDEX_ALLOCATION` and
    `.gitattributes:s` are alternate streams of the real names, and no fr artifact name
    needs a colon."""
    import unicodedata

    if ":" in component:
        return True
    name = unicodedata.normalize("NFC", component)
    name = "".join(ch for ch in name if ord(ch) not in _HFS_IGNORABLE)
    name = name.rstrip(". ").casefold()
    return name in _GIT_NAMES or bool(_NTFS_SHORT.fullmatch(name))


def foreign(rel: str) -> bool:
    """Is *rel* (a repo-layout path) something other than an fr artifact? An allowlist
    first: only paths `paths.placement_bound` names, matched exactly and case-sensitively,
    are fr's to copy. Then, on top of it, never one with a `.git`-like component in any
    spelling a filesystem would honour (`git_like`): `.gitattributes`, `.GIT/hooks/`,
    `git~1/`, which configure git rather than holding fr state."""
    parts = PurePosixPath(rel).parts
    return not paths.placement_bound(rel) or any(git_like(p) for p in parts)


def refuse_foreign(rels: Iterable[str], where: str) -> None:
    """Refuse (exit 2, before anything is written) when *where* holds a path that is not an
    fr artifact (review p7-r5): whoever can push to `fr` or a tracking repo must not be able
    to plant `.github/workflows/x.yml` or `.gitattributes` in the product checkout."""
    bad = sorted({r for r in rels if foreign(r)})
    if bad:
        listed = ", ".join(bad[:5]) + (" ..." if len(bad) > 5 else "")
        raise MoveError(
            f"fr placement move: refused: {where} holds {listed}, which "
            f"{'is not an fr artifact' if len(bad) == 1 else 'are not fr artifacts'} (fr "
            "copies only its own placement-bound artifacts, never a file git acts on); "
            "nothing was written"
        )


def _blobs(root: Path, shas: Sequence[str]) -> dict[str, bytes]:
    """sha -> bytes, in one `git cat-file --batch`."""
    wanted = list(dict.fromkeys(shas))
    if not wanted:
        return {}
    raw = _git(root, "cat-file", "--batch", data="".join(f"{s}\n" for s in wanted).encode())
    out: dict[str, bytes] = {}
    pos = 0
    for sha in wanted:
        end = raw.index(b"\n", pos)
        header = raw[pos:end].decode().split()
        size = int(header[2])
        out[sha] = raw[end + 1 : end + 1 + size]
        pos = end + 1 + size + 1
    return out


def _files(
    root: Path, commit: str, prefix: str = "", keep: Callable[[str], bool] | None = None
) -> dict[str, tuple[str, bytes]]:
    """Every file (*keep*-filtered) at *commit*, read from git, never the working tree; a
    symlink or gitlink among them refuses (`refuse_links`)."""
    tree = {p: v for p, v in _tree(root, commit, prefix).items() if keep is None or keep(p)}
    refuse_links(tree, f"{root} at {commit[:12]}")
    data = _blobs(root, [b for _, b in tree.values()])
    return {p: (mode, data[b]) for p, (mode, b) in tree.items()}


def _hash(root: Path, data: bytes) -> str:
    return _git(root, "hash-object", "-w", "--stdin", data=data).decode().strip()


def _commit_tree(
    root: Path,
    parent: str | None,
    removals: Sequence[str],
    additions: Mapping[str, tuple[str, bytes]],
    message: str,
    date: str | None,
) -> str:
    """A commit of *parent*'s tree with *removals* dropped and *additions* written, built
    in a private index (no checkout is touched)."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        if parent:
            _git(root, "read-tree", parent, env=env)
        else:
            _git(root, "read-tree", "--empty", env=env)
        lines = [f"0 {_ZERO}\t{p}" for p in removals]
        lines += [f"{mode} {_hash(root, data)}\t{p}" for p, (mode, data) in additions.items()]
        if lines:
            _git(root, "update-index", "--index-info", data=("\n".join(lines) + "\n").encode(),
                 env=env)  # fmt: skip
        tree = _git(root, "write-tree", env=env).decode().strip()
    dated = {"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date} if date else {}
    argv = ["commit-tree", tree, *(["-p", parent] if parent else []), "-F", "-"]
    return _git(root, *argv, data=message.encode(), env=dated).decode().strip()


def _push_fr_branch(root: Path) -> None:
    """A plain push of quiet's `fr` branch to origin (never forced), then its tracking
    ref. The one branch this module pushes itself: a product branch goes through
    `fr.git_policy.product.push_product_branch` (`_push_product`, review pr1431-r1)."""
    _git(root, "push", "--quiet", "origin", "refs/heads/fr:refs/heads/fr")
    _git(root, "fetch", "--quiet", "--no-tags", "origin", "+refs/heads/fr:refs/remotes/origin/fr")


def _push_branch(root: Path, branch: str) -> None:
    """Every push this module makes: quiet's `fr` itself, any other branch through the
    one product pusher."""
    if branch == "fr":
        _push_fr_branch(root)
    else:
        _push_product(root, branch)


def _push_product(root: Path, branch: str) -> None:
    """A side branch this move opened on the product repo (the copy back, the removal),
    pushed through the one product pusher, so stealth's guard holds on it too."""
    from fr.git_policy.product import push_product_branch
    from fr.git_policy.push import PushRefusedError

    try:
        push_product_branch(root, "origin", branch, rev=f"refs/heads/{branch}")
    except PushRefusedError as e:
        raise MoveError(f"fr placement move: {e}") from e


def _fr_message(root: Path, text: str) -> str:
    from fr.git_policy.templates import fr_message

    try:
        return fr_message(root, text)
    except SettingsError:
        return text


# --- the source: which feature each repo artifact belongs to ----------------------------


def _under(rel: str, kind: str) -> str | None:
    prefix = paths.KIND_DIRS[kind] + "/"
    return rel[len(prefix) :] if rel.startswith(prefix) else None


def _stem(name: str) -> str:
    return name.rsplit(".", 1)[0]


def _spec_slug(name: str) -> str:
    from fr.archive import spec_slug_of

    return spec_slug_of(Path(name))


def _owner(rel: str, plan_spec: Mapping[str, str], run_branch: Mapping[str, str]) -> str:
    """The branch that owns *rel*'s feature root: a run's own branch for its cursor,
    records and usage; `moved/<spec slug>` for a spec, its plans, journals and fragment;
    `moved/debug-<slug>` for a debug journal; `moved/repo` for anything else."""

    def moved(key: str) -> str:
        return f"{MOVED}/{key}"

    rest = _under(rel, "acceptance-fragment")
    if rest is not None and "/" not in rest and rest.endswith(".yaml"):
        return moved(_stem(rest))
    for kind in ("journal-archived-specs", "journal-specs"):
        rest = _under(rel, kind)
        if rest is not None and "/" not in rest:
            return moved(_stem(rest))
    for kind in ("journal-archived-plans", "journal-plans"):
        rest = _under(rel, kind)
        if rest is not None and "/" not in rest:
            return moved(plan_spec.get(_stem(rest), _stem(rest)))
    for kind in ("journal-archived-debug", "journal-debug"):
        rest = _under(rel, kind)
        if rest is not None and "/" not in rest:
            return moved(f"debug-{_stem(rest)}")
    for kind in ("run-archived", "run", "usage-archived", "usage"):
        rest = _under(rel, kind)
        if rest is not None:
            rid = rest.split("/", 1)[0].partition(".")[0]
            return run_branch.get(rid) or moved(f"run-{rid}")
    for kind in ("plan-archived", "plan-legacy-archived", "plan"):
        rest = _under(rel, kind)
        if rest is not None and "/" in rest:
            plan = rest.split("/", 1)[0]
            return moved(plan_spec.get(plan, plan))
    for kind in ("spec-archived", "spec-legacy-archived", "spec"):
        rest = _under(rel, kind)
        if rest is not None and "/" not in rest:
            return moved(_spec_slug(rest))
    return moved("repo")


def _yaml_key(data: bytes, key: str) -> str | None:
    try:
        doc = yaml.safe_load(data.decode())
    except (yaml.YAMLError, UnicodeDecodeError):
        return None
    value = doc.get(key) if isinstance(doc, dict) else None
    return value if isinstance(value, str) and value else None


@dataclass
class Group:
    """One feature's files (relative to its feature root, bookkeeping included) and the
    date its fr commit carries."""

    fid: str
    owner: str
    files: dict[str, tuple[str, bytes]]
    date: str | None = None

    def content(self) -> dict[str, bytes]:
        return {rel: data for rel, (_, data) in self.files.items() if rel not in META}


def checked_owner(root: Path, owner: str) -> str:
    """*owner*'s feature id, refused unless the branch is a valid ref name (`git
    check-ref-format --branch`) and its id one safe path segment
    (`paths.checked_feature_id`): a run cursor's `branch:` is repo content, untrusted."""
    try:
        fid = paths.checked_feature_id(owner)
    except SettingsError as e:
        raise MoveError(f"fr placement move: refused: {e}") from e
    if not _ok(root, "check-ref-format", "--branch", owner):
        raise MoveError(
            f"fr placement move: refused: branch {owner!r} is not a valid branch name "
            "(`git check-ref-format --branch`), so it cannot name a feature root"
        )
    return fid


def inside(base: Path, rel: str) -> Path:
    """`base / rel`, refused unless it stays inside *base*: a relative path with no `..`,
    no component from *base* down to it a symlink (lstat), and resolving below *base*.
    The ONE check every write and unlink of a move or `fr placement migrate-branch` takes
    (defence in depth: each lands in its one feature root, or the workspace)."""
    path = base / rel
    if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise MoveError(f"fr placement move: refused: {rel!r} is not a path inside {base}")
    walk = Path(base)
    for part in Path(rel).parts:
        walk = walk / part
        if walk.is_symlink():
            raise MoveError(
                f"fr placement move: refused: {walk} is a symlink; fr writes nothing through "
                "a link (it could land outside the repo)"
            )
    real, top = path.resolve(), base.resolve()
    if real != top and not real.is_relative_to(top):
        raise MoveError(f"fr placement move: refused: {rel!r} leaves {base}")
    return path


def _repo_groups(root: Path, ref: str) -> list[Group]:
    """Every placement-bound artifact at *ref* (the default ref), grouped by feature, with
    the bookkeeping a feature root carries synthesised from the default ref's history."""
    from fr.placement.merged import record_text

    files = _files(root, ref, keep=lambda p: not foreign(p))
    plan_spec: dict[str, str] = {}
    run_branch: dict[str, str] = {}
    default = ref.rsplit("/", 1)[-1]
    for rel, (_, data) in files.items():
        for kind in ("plan-archived", "plan-legacy-archived", "plan"):
            rest = _under(rel, kind)
            if rest is not None and rest.count("/") == 1 and rest.endswith("/_meta.yaml"):
                spec = _yaml_key(data, "spec")
                if spec:
                    plan_spec[rest.split("/", 1)[0]] = _spec_slug(Path(spec).name)
        for kind in ("run-archived", "run"):
            rest = _under(rel, kind)
            if rest is not None and "/" not in rest and rest.endswith(".yaml"):
                branch = _yaml_key(data, "branch")
                if branch and branch not in (default, "fr"):
                    run_branch[_stem(rest)] = branch
    owned: dict[str, list[str]] = {}
    for rel in sorted(files):
        owned.setdefault(_owner(rel, plan_spec, run_branch), []).append(rel)
    groups: list[Group] = []
    seen: dict[str, str] = {}
    for owner, rels in sorted(owned.items()):
        fid = checked_owner(root, owner)
        if fid in seen:
            raise MoveError(
                f"fr placement move: {owner!r} and {seen[fid]!r} share the feature id {fid!r}; "
                "rename one of the branches the runs name and retry"
            )
        seen[fid] = owner
        head = _git(root, "log", "--first-parent", "-1", "--format=%H", ref, "--", *rels)
        head_sha = head.decode().strip()
        base = _sha(root, f"{head_sha}^1") if head_sha else None
        meta: dict[str, tuple[str, bytes]] = {
            paths.FEATURE_OWNER: ("100644", f"{owner}\n".encode())
        }
        date = None
        if head_sha:
            ct = _git(root, "log", "-1", "--format=%ct", head_sha).decode().strip()
            date = f"{ct} +0000"
            meta[paths.FEATURE_HEADS] = ("100644", f"{head_sha}\n".encode())
            if base:
                meta[paths.FEATURE_BASE] = ("100644", f"{base}\n".encode())
                meta[MERGED_FILE] = ("100644", record_text(head_sha, (head_sha,)).encode())
        body = {rel: files[rel] for rel in rels}
        groups.append(Group(fid, owner, {**body, **meta}, date))
    return groups


def _outside_groups(ctx: Ctx, space: paths.ArtifactSpace) -> list[Group]:
    """The MERGED features below a quiet or stealth *space*, each at the fr commit its
    fragments are frozen at; an unmerged feature is a live branch's and stays."""
    from fr.placement.merged import frozen_commit, merged_features, pushed_ref

    view = merged_features(space, ctx.root)
    for fid in view.unmerged:
        ctx.emit(
            f"left in place: {fid} is not merged; its branch moves with "
            "`fr placement migrate-branch` (R28)"
        )
    groups: list[Group] = []
    for feature in view.features:
        commit, why = frozen_commit(feature, space.placement, ctx.root)
        found = pushed_ref(feature.root, space.placement)
        if commit is None or found is None:
            raise MoveError(f"fr placement move: {why or feature.feature}: nothing to copy")
        top = found[0]
        rel = feature.root.resolve().relative_to(top.resolve()).as_posix()
        got = _files(top, commit, f"{rel}/")
        ct = _git(ctx.root, "log", "-1", "--format=%ct", feature.sha).decode().strip()
        group = Group(
            feature.feature,
            feature.branch or feature.feature,
            {p.removeprefix(f"{rel}/"): v for p, v in got.items()},
            f"{ct} +0000",
        )
        refuse_foreign(group.content(), f"{rel}/ on {space.placement}")
        groups.append(group)
    return groups


# --- the move's context and state ---------------------------------------------------------


def state_path(root: Path) -> Path:
    common = paths._common_dir(Path(root))
    if common is None:
        raise MoveError(f"fr placement move: {root} is not a git checkout")
    return common / STATE_NAME


@dataclass
class Ctx:
    root: Path
    to: str
    source: str
    state: dict[str, Any]
    emit: Callable[[str], None]
    tracking: Any = None  # StealthRef
    run: str | None = None
    _groups: list[Group] | None = field(default=None, repr=False)

    def save(self) -> None:
        path = state_path(self.root)
        path.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n")

    def default_ref(self) -> str:
        from fr.placement.merged import default_ref

        ref, why = default_ref(self.root)
        if ref is None:
            raise MoveError(f"fr placement move: {why}")
        return ref

    def groups(self) -> list[Group]:
        if self._groups is None:
            self._groups = self._read_groups()
        return self._groups

    def _read_groups(self) -> list[Group]:
        if self.run is not None:
            return [_run_group(self)]
        if self.source == paths.REPO:
            sha = self.state.get("source_sha")
            if not sha:
                sha = _sha(self.root, self.default_ref())
                if sha is None:
                    raise MoveError("fr placement move: the default ref names no commit")
                self.state["source_sha"] = sha
            return _repo_groups(self.root, sha)
        from fr.placement import quiet

        wt = quiet.ensure_worktree(self.root)
        quiet.fast_forward(self.root)
        return _outside_groups(self, paths.ArtifactSpace(paths.QUIET, wt, None))

    def flat(self) -> dict[str, bytes]:
        """Every copied artifact at its repo-layout path; two features writing one path
        differently refuse."""
        out: dict[str, bytes] = {}
        owner: dict[str, str] = {}
        for g in self.groups():
            for rel, data in g.content().items():
                if rel in out and out[rel] != data:
                    raise MoveError(
                        f"fr placement move: {rel} differs between features {owner[rel]} and "
                        f"{g.fid}; the repo layout holds one file there"
                    )
                out[rel], owner[rel] = data, g.fid
        return out

    # The source's digest (review p7-r1): taken at copy, compared at verify and at switch,
    # so a move never switches on a copy the source has moved past.

    def copied_print(self) -> str | None:
        """The digest of the source this move's copy was made from (None for `--run`)."""
        if self.run is not None:
            return None
        if self.source == paths.REPO:
            return _tree_print(self.root, self.state["source_sha"])
        return _flat_print(self.flat())

    def current_print(self) -> str | None:
        """The digest of the source as it stands now, freshly fetched."""
        if self.run is not None:
            return None
        if self.source == paths.REPO:
            _git(self.root, "fetch", "--quiet", "--no-tags", "origin", check=False)
            sha = _sha(self.root, self.default_ref())
            if sha is None:
                raise MoveError("fr placement move: the default ref names no commit")
            return _tree_print(self.root, sha)
        from fr.placement import quiet

        _git(self.root, "fetch", "--quiet", "--no-tags", "origin", quiet.FETCH_REFSPEC,
             check=False)  # fmt: skip
        fresh = Ctx(self.root, self.to, self.source, {}, lambda _line: None, self.tracking)
        return _flat_print(fresh.flat())

    def check_source(self, step: str) -> None:
        """Raise `_SourceMovedError` when the source moved since the copy."""
        copied = self.state.get("source_print")
        now = self.current_print()
        if now is not None and copied != now:
            raise _SourceMovedError(
                f"the source (placement {self.source}) changed since the copy (a feature "
                f"merged or changed meanwhile): copying again before {step}"
            )


def _tree_print(root: Path, commit: str) -> str:
    """A digest of every placement-bound path (mode and blob) at *commit*."""
    entries = sorted(
        (p, mode, blob) for p, (mode, blob) in _tree(root, commit).items() if not foreign(p)
    )
    return hashlib.sha256(json.dumps(entries).encode()).hexdigest()


def _flat_print(flat: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(flat):
        digest.update(rel.encode() + b"\0" + hashlib.sha256(flat[rel]).digest())
    return digest.hexdigest()


# --- workspaces: the precondition, and the placement a workspace records ------------------


def dirty_workspaces(root: Path) -> list[str]:
    """Every workspace of the repo (and the checkout fr runs in) with uncommitted work,
    and fr's own clones a move writes through (review pr1431-n2): quiet's `fr` worktree,
    whose index the copy resets, and every stealth tracking clone of this repo."""
    from fr.isolation.types import list_states
    from fr.placement import quiet, stealth

    seen: set[Path] = set()
    out: list[str] = []
    places: list[tuple[Path, str | None]] = [
        (Path(root), None),
        *((s.worktree, s.branch) for s in list_states(Path(root))),
    ]
    frwt = quiet.worktree_path(root)
    places.append((frwt, quiet.QUIET_BRANCH))
    if frwt.parent.is_dir():
        places += [
            (p, "tracking clone") for p in sorted(frwt.parent.glob(f"{stealth.WORKTREE_PREFIX}*"))
        ]
    for where, branch in places:
        if not where.is_dir() or not (where / ".git").exists():
            continue
        real = where.resolve()
        if real in seen:
            continue
        seen.add(real)
        status = _git(where, "status", "--porcelain", check=False).decode().strip()
        if status:
            first = status.splitlines()[0][3:]
            out.append(f"{where}{f' ({branch})' if branch else ''}: {first}")
    return out


def record_placement(root: Path, placement: str, tracking: str | None = None) -> None:
    """Rewrite the placement a workspace recorded (its `.fr-isolation` marker and its
    isolation state): the one place a live workspace changes placement, used by a run's
    move and by `fr placement migrate-branch` (R28)."""
    from fr.isolation.marker import MARKER
    from fr.isolation.types import load_state, save_state
    from fr.placement.quiet import branch_of

    marker = Path(root) / MARKER
    if marker.is_file():
        data = json.loads(marker.read_text())
        data["placement"] = placement
        if tracking is None:
            data.pop("tracking", None)
        marker.write_text(json.dumps(data, indent=2) + "\n")
    branch = branch_of(Path(root))
    if branch is None:
        return
    state = load_state(Path(root), branch)
    if state is not None:
        save_state(state.model_copy(update={"placement": placement, "tracking": tracking}))
    paths_cache_reset()


def paths_cache_reset() -> None:
    from fr.acceptance.fold import clear_fold_cache
    from fr.placement import stealth

    stealth.reset_caches()
    clear_fold_cache()


# --- copy ---------------------------------------------------------------------------------


def _commit_feature(root: Path, parent: str | None, prefix: str, group: Group, message: str) -> str:
    """*parent* with `<prefix>/` holding exactly *group*'s files, as one commit (or
    *parent* itself when it already does: the copy is idempotent by content)."""
    have = _tree(root, parent, f"{prefix}/") if parent else {}
    fake = Path("/") / prefix
    for rel in group.files:
        inside(fake, rel)
    want = {f"{prefix}/{rel}": (mode, data) for rel, (mode, data) in group.files.items()}
    hashed = {p: (mode, _hash(root, data)) for p, (mode, data) in want.items()}
    if have == hashed:
        return parent or ""
    removals = [p for p in have if p not in want]
    return _commit_tree(root, parent, removals, want, message, group.date)


def _remote_branch(root: Path, branch: str) -> str | None:
    out = _git(root, "ls-remote", "--heads", "origin", f"refs/heads/{branch}").decode().split()
    return out[0] if out else None


def _copy_quiet(ctx: Ctx) -> None:
    from fr.placement import quiet

    root = ctx.root
    remote = _remote_branch(root, "fr")
    if remote is not None:
        _git(root, "fetch", "--quiet", "--no-tags", "origin", quiet.FETCH_REFSPEC)
    local = _sha(root, _FR_REF)
    if local and remote and not _ok(root, "merge-base", "--is-ancestor", remote, local):
        raise MoveError(
            "fr placement move: the local `fr` branch is not a descendant of origin/fr; "
            "rename it (`git branch -m fr fr-old`) and retry"
        )
    parent = local or (_sha(root, paths.SWITCH_REF) if remote else None)
    source = ctx.source
    for g in sorted(ctx.groups(), key=lambda g: (g.date or "", g.fid)):
        message = _fr_message(root, f"chore(fr): move {g.fid} from placement {source}")
        new = _commit_feature(root, parent, f"{paths.FEATURES_DIR}/{g.fid}", g, message)
        if new and new != parent:
            _git(root, "update-ref", _FR_REF, new, parent or _ZERO)
            parent = new
    if parent is None:
        raise MoveError("fr placement move: nothing to copy (no fr artifact found)")
    _push_branch(root, "fr")
    wt = quiet.worktree_path(root)
    if (wt / ".git").exists():
        _git(wt, "read-tree", "-u", "--reset", "HEAD")
    quiet.ensure_worktree(root)
    quiet.fast_forward(root)


@contextmanager
def _dated(date: str | None) -> Iterator[None]:
    keys = ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE")
    saved = {k: os.environ.get(k) for k in keys}
    if date:
        for k in keys:
            os.environ[k] = date
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _tracking(ctx: Ctx) -> tuple[Any, Path, str]:
    """(the tracking ref, its synced worktree, this target's directory), checked
    reachable and no more visible than the target before anything is written (R24)."""
    from fr.placement import stealth
    from fr.placement.quiet import fr_worktree_lock

    ref = ctx.tracking
    stealth.check_reachable(ref, ctx.root)
    stealth.check_privacy(ref, stealth.origin_url(ctx.root), target_root=ctx.root)
    wt = stealth.ensure_worktree(ctx.root, ref)
    with fr_worktree_lock(wt):
        stealth.sync(wt, ref)
    return ref, wt, stealth.target_dir(ctx.root)


def _copy_stealth(ctx: Ctx) -> None:
    from fr.placement import stealth

    ref, wt, target = _tracking(ctx)
    for g in sorted(ctx.groups(), key=lambda g: (g.date or "", g.fid)):
        prefix = f"{target}/{paths.FEATURES_DIR}/{g.fid}"
        have = _tree(wt, "HEAD", f"{prefix}/")
        want = {f"{prefix}/{rel}": (mode, _hash(wt, data)) for rel, (mode, data) in g.files.items()}
        if have == want:
            continue
        froot = wt / prefix
        inside(wt / target / paths.FEATURES_DIR, g.fid)
        written: list[Path] = []
        for rel, (mode, data) in g.files.items():
            path = inside(froot, rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if mode == "100755":
                path.chmod(0o755)
            written.append(path)
        for stale in (p for p in have if p not in want):
            if not stale.startswith(f"{prefix}/"):
                continue  # the stale pass is limited to exactly this feature's root
            gone = inside(froot, stale.removeprefix(f"{prefix}/"))
            gone.unlink(missing_ok=True)
            written.append(gone)
        message = _fr_message(ctx.root, f"chore(fr): move {g.fid} from placement {ctx.source}")
        with _dated(g.date):
            outcome = stealth.commit_and_push(
                ref,
                wt,
                written,
                message,
                stealth.plain_commit,
                target_remote=stealth.origin_url(ctx.root),
                target_root=ctx.root,
            )
        if not (outcome.committed or outcome.unchanged):
            raise MoveError(f"fr placement move: {outcome.reason}")
    ctx.emit(f"copied {len(ctx.groups())} feature(s) into {ref.text} ({target}/)")


COPY_BRANCH: Final = "chore/fr-placement-move-to-repo"


def _pr_command(ctx: Ctx, branch: str, title: str, body: str) -> None:
    path = state_path(ctx.root).parent / BODY_NAME
    path.write_text(body)
    ctx.emit(f"open its PR:  git switch {branch} && fr pr create --title {json.dumps(title)} "
             f"--body-file {path}")  # fmt: skip


def _copy_repo(ctx: Ctx) -> None:
    root = ctx.root
    _git(root, "fetch", "--quiet", "--no-tags", "origin")
    flat = ctx.flat()
    tip = _sha(root, ctx.default_ref())
    if tip is None:
        raise MoveError("fr placement move: the default ref names no commit")
    refuse_foreign(flat, "the copy")
    existing = _sha(root, f"refs/heads/{COPY_BRANCH}")
    message = _fr_message(root, "chore(fr): move fr artifacts to the repo placement")
    if existing is None:
        additions = {rel: ("100644", data) for rel, data in flat.items()}
        new = _commit_tree(root, tip, [], additions, message, None)
        _git(root, "update-ref", f"refs/heads/{COPY_BRANCH}", new, _ZERO)
        existing = new
    else:
        got = {p: d for p, (_, d) in _files(root, existing, keep=flat.__contains__).items()}
        if got != flat:
            ours = ctx.state.get("copy_sha")
            if not ours or not _ok(root, "merge-base", "--is-ancestor", ours, existing):
                raise MoveError(
                    f"fr placement move: the branch {COPY_BRANCH} already exists and does not "
                    "hold this copy; delete it and retry"
                )
            # The source moved after this move's own copy (p7-r1): one more commit on the
            # same branch brings it level, dropping what the source no longer holds.
            at_tip = _tree(root, tip)
            stale = [
                p for p in _tree(root, existing) if not foreign(p) and p not in flat
                and p not in at_tip
            ]  # fmt: skip
            changed = {rel: ("100644", d) for rel, d in flat.items() if got.get(rel) != d}
            new = _commit_tree(root, existing, stale, changed, message, None)
            _git(root, "update-ref", f"refs/heads/{COPY_BRANCH}", new, existing)
            existing = new
    _push_branch(root, COPY_BRANCH)
    ctx.state["copy_sha"] = existing
    ctx.emit(f"opened branch {COPY_BRANCH} (pushed to origin): it adds {len(flat)} fr file(s)")
    _pr_command(
        ctx,
        COPY_BRANCH,
        "chore(placement): bring fr's artifacts back to the repo placement",
        "Moves fr's artifacts back into the repository (`fr placement move --to repo`). "
        "Once this merges, re-run the move to switch the placement.\n",
    )


def _run_group(ctx: Ctx) -> Group:
    """The stealth run's feature root, as the tracking repo holds it."""
    from fr.artifacts.paths import feature_root
    from fr.placement import stealth

    space = stealth.stealth_space(ctx.root)
    froot = feature_root(space)
    cursor = paths.below(froot, "run") / f"{ctx.run}.yaml"
    if not cursor.is_file():
        raise MoveError(f"fr placement move: run {ctx.run} is not in this workspace's feature")
    wt = stealth.tracking_root(space)
    rel = froot.resolve().relative_to(wt.resolve()).as_posix()
    got = _files(wt, "HEAD", f"{rel}/")
    ctx.state.setdefault("run_prefix", rel)
    branch = space.feature or ""
    group = Group(
        space.feature or "", branch, {p.removeprefix(f"{rel}/"): v for p, v in got.items()}
    )
    refuse_foreign(group.content(), f"{rel}/ in the tracking repo")
    return group


def _copy_run(ctx: Ctx) -> None:
    root = ctx.root
    group = ctx.groups()[0]
    if ctx.to == paths.QUIET:
        _copy_quiet(ctx)
        return
    content = group.content()
    refuse_foreign(content, f"run {ctx.run}'s feature root")
    written: list[str] = []
    for rel, data in content.items():
        path = inside(root, rel)
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        written.append(rel)
    if written:
        _git(root, "add", "--", *written)
        _git(root, "commit", "--quiet", "--no-verify", "-m",
             f"chore(fr): move run {ctx.run} out of stealth", "--", *written)  # fmt: skip


# --- verify -------------------------------------------------------------------------------


def _fold_key(eff: Any) -> Any:
    return (
        eff.matrix.model_dump(),
        eff.revisions,
        sorted(eff.contested),
        sorted(r.id for r in eff.retired),
        eff.owners,
    )


def _validation(files: Mapping[str, bytes]) -> Any:
    """`fr validate artifacts`'s report over *files* laid out at their repo paths."""
    from fr.artifacts.validate import validate_repo

    with tempfile.TemporaryDirectory() as tmp:
        top = Path(tmp)
        for rel, data in files.items():
            (top / rel).parent.mkdir(parents=True, exist_ok=True)
            (top / rel).write_bytes(data)
        report = validate_repo(top)
        prefixes = sorted({str(top), str(top.resolve())}, key=len, reverse=True)

        def norm(text: str) -> str:
            for p in prefixes:
                text = text.replace(p, "<root>")
            return text

        issues = sorted((i.kind, norm(str(i.path)), norm(i.message)) for i in report.issues)
        return report.checked, issues


_SHA_LINE: Final = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


def bookkeeping_problems(fid: str, files: Mapping[str, bytes]) -> list[str]:
    """What is wrong with the bookkeeping a feature root *fid* carries (its `OWNER`,
    `BASE`, `HEADS` and `merged.yaml`, keyed relative to the root), as its readers
    (`fr.placement.quiet.owner_of`, `fr.placement.merged`) need it (review p7-r4)."""
    problems: list[str] = []

    def lines(name: str) -> list[str] | None:
        if name not in files:
            return None
        try:
            text = files[name].decode()
        except UnicodeDecodeError:
            problems.append(f"{fid}/{name} is not text")
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    owner = lines(paths.FEATURE_OWNER)
    if not owner or len(owner) != 1:
        problems.append(f"{fid}/{paths.FEATURE_OWNER} must hold one branch name")
    else:
        try:
            named = paths.checked_feature_id(owner[0])
        except SettingsError as e:
            problems.append(f"{fid}/{paths.FEATURE_OWNER}: {e}")
        else:
            if named != fid:
                problems.append(
                    f"{fid}/{paths.FEATURE_OWNER} names {owner[0]!r}, whose feature id is {named!r}"
                )
    for name, single in ((paths.FEATURE_BASE, True), (paths.FEATURE_HEADS, False)):
        found = lines(name)
        if found is None:
            continue
        if not found or (single and len(found) != 1):
            problems.append(f"{fid}/{name} must hold {'one commit' if single else 'commits'}")
        problems += [f"{fid}/{name}: {x!r} is not a commit" for x in found
                     if not _SHA_LINE.fullmatch(x)]  # fmt: skip
    if MERGED_FILE in files:
        try:
            doc = yaml.safe_load(files[MERGED_FILE].decode())
        except (yaml.YAMLError, UnicodeDecodeError) as e:
            problems.append(f"{fid}/{MERGED_FILE} does not parse: {e}")
        else:
            entries = doc if isinstance(doc, list) else None
            ok = entries is not None and all(
                isinstance(x, dict)
                and isinstance(x.get("merged"), str)
                and _SHA_LINE.fullmatch(x["merged"].strip())
                and (
                    x.get("head") is None
                    or (isinstance(x["head"], str) and _SHA_LINE.fullmatch(x["head"].strip()))
                )  # fmt: skip
                for x in entries
            )
            if not ok:
                problems.append(f"{fid}/{MERGED_FILE} is not a list of `merged:` records")
    return problems


def _dest_roots(ctx: Ctx) -> dict[str, dict[str, bytes]] | None:
    """The destination's feature roots for this move's features, every file of each
    (bookkeeping included), as the destination holds them; None for a repo destination."""
    root = ctx.root
    fids = {g.fid for g in ctx.groups()}
    if ctx.to == paths.QUIET:
        prefix = f"{paths.FEATURES_DIR}/"
        got = _files(root, paths.SWITCH_REF, prefix)
    elif ctx.to == paths.STEALTH:
        from fr.placement import stealth

        wt = stealth.worktree_path(root, ctx.tracking)
        prefix = f"{stealth.target_dir(root)}/{paths.FEATURES_DIR}/"
        got = _files(wt, stealth._remote_ref(ctx.tracking), prefix)
    else:
        return None
    out: dict[str, dict[str, bytes]] = {}
    for p, (_, data) in got.items():
        fid, _, rel = p.removeprefix(prefix).partition("/")
        if fid in fids:
            out.setdefault(fid, {})[rel] = data
    return out


def _dest_files(ctx: Ctx) -> dict[str, bytes]:
    roots = _dest_roots(ctx)
    if roots is not None:
        return {rel: d for files in roots.values() for rel, d in files.items() if rel not in META}
    head = ctx.state.get("copy_sha") or "HEAD"
    return {
        p: d
        for p, (_, d) in _files(ctx.root, head, keep=paths.placement_bound).items()
        if (ctx.run is None or p in ctx.groups()[0].content())
    }


def _space_validation(roots: Mapping[str, Mapping[str, bytes]]) -> tuple[int, list[Any]]:
    """`fr validate artifacts`'s report over a quiet or stealth space laid out as its
    readers see it: every feature root below `features/`, each validated the way
    `fr.artifacts.registry.iter_paths_of` reaches it under that placement (every kind's
    locator below each root), paths reported repo-relative."""
    from fr.artifacts.validate import validate_repo

    checked, issues = 0, []
    with tempfile.TemporaryDirectory() as tmp:
        for fid, files in sorted(roots.items()):
            top = inside(Path(tmp) / paths.FEATURES_DIR, fid)
            for rel, data in files.items():
                path = inside(top, rel)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            top.mkdir(parents=True, exist_ok=True)
            report = validate_repo(top)
            checked += report.checked
            prefixes = sorted({str(top), str(top.resolve())}, key=len, reverse=True)

            def norm(text: str, prefixes: list[str] = prefixes) -> str:
                for p in prefixes:
                    text = text.replace(p, "<root>")
                return text

            issues += [(i.kind, norm(str(i.path)), norm(i.message)) for i in report.issues]
    return checked, sorted(issues)


def _validate_destination(ctx: Ctx, source: Mapping[str, bytes]) -> list[str]:
    """Why the destination, AS LAID OUT, fails validation where the source does not
    (review p7-r4): its feature roots with their synthesised bookkeeping under quiet and
    stealth, the copy branch's tree under repo."""
    want_checked, want = _validation(source)
    problems: list[str] = []
    roots = _dest_roots(ctx)
    if roots is None:
        head = ctx.state.get("copy_sha") or "HEAD"
        laid = {
            p: d
            for p, (_, d) in _files(ctx.root, head, keep=paths.placement_bound).items()
            if ctx.run is None or p in source
        }
        checked, got = _validation(laid)
    else:
        for g in ctx.groups():
            have = roots.get(g.fid, {})
            problems += bookkeeping_problems(g.fid, have)
            for name in sorted(META & (set(have) | set(g.files))):
                if have.get(name) != (g.files[name][1] if name in g.files else None):
                    problems.append(f"{g.fid}/{name} differs from the bookkeeping fr synthesised")
        checked, got = _space_validation(roots)
    if checked < want_checked:
        problems.append(f"{checked} artifact(s) validated, the source has {want_checked}")
    problems += [f"{kind}: {path}: {message}" for kind, path, message in got
                 if (kind, path, message) not in want]  # fmt: skip
    return problems


def _space_fold(ctx: Ctx, placement: str) -> Any:
    from fr.acceptance.fold import clear_fold_cache, fold, fold_of_space

    clear_fold_cache()
    root = ctx.root
    if placement == paths.REPO:
        sha = ctx.state["source_sha"] if ctx.source == paths.REPO else ctx.state["copy_sha"]
        return fold(root, ref=sha, include_pending=False)
    if placement == paths.QUIET:
        from fr.placement import quiet

        wt = quiet.ensure_worktree(root)
        quiet.fast_forward(root)
        return fold_of_space(root, paths.ArtifactSpace(paths.QUIET, wt, None))
    from fr.placement import stealth

    wt = stealth.worktree_path(root, ctx.tracking)
    space = paths.ArtifactSpace(paths.STEALTH, wt / stealth.target_dir(root), None)
    return fold_of_space(root, space)


def _verify(ctx: Ctx) -> None:
    ctx.check_source("verify")
    source = ctx.flat()
    dest = _dest_files(ctx)
    if dest != source:
        missing = sorted(set(source) - set(dest))
        extra = sorted(set(dest) - set(source))
        changed = sorted(p for p in set(source) & set(dest) if source[p] != dest[p])
        raise MoveError(
            "fr placement move: verify refused: the destination's files differ from the "
            f"source's (missing {missing[:3]}, extra {extra[:3]}, changed {changed[:3]}); "
            "nothing was switched"
        )
    if ctx.run is None and _fold_key(_space_fold(ctx, ctx.source)) != _fold_key(
        _space_fold(ctx, ctx.to)
    ):
        raise MoveError(
            "fr placement move: verify refused: the destination's acceptance fold differs "
            "from the source's (an amendment would apply in another order); nothing was "
            "switched"
        )
    problems = _validate_destination(ctx, source)
    if problems:
        listed = "; ".join(problems[:3]) + (" ..." if len(problems) > 3 else "")
        raise MoveError(
            "fr placement move: verify refused: `fr validate artifacts` fails on the "
            f"destination as laid out where the source passes ({listed}); nothing was "
            "switched"
        )
    ctx.emit(f"verified: {len(source)} file(s), the fold and the validation report agree")


# --- switch -------------------------------------------------------------------------------

_QUIET_LINE: Final = re.compile(r"(?m)^placement: quiet$")


def _switch_text(root: Path, ref: str = paths.SWITCH_REF) -> str | None:
    out = _git(root, "show", f"{ref}:{paths.SWITCH_SETTINGS}", check=False)
    return out.decode() if out else None


def _settle_switch(root: Path, rewrite: Callable[[str | None], str | None], subject: str) -> None:
    """Make the switch say what *rewrite* wants, then push it. Idempotent mid-step (review
    p7-r2): the decision reads the LOCAL `fr` (the fr worktree's branch, fast-forwarded to
    origin/fr first), so a switch commit made by a run killed before its push is found and
    pushed, never committed a second time."""
    from fr.placement import quiet

    _git(root, "fetch", "--quiet", "--no-tags", "origin", quiet.FETCH_REFSPEC, check=False)
    wt = quiet.ensure_worktree(root)
    quiet.fast_forward(root)
    with quiet.fr_worktree_lock(wt):
        text = rewrite(_switch_text(root, _FR_REF))
        if text is not None:
            (wt / paths.SWITCH_SETTINGS).write_text(text)
            _git(wt, "add", "--", paths.SWITCH_SETTINGS)
            _git(wt, "commit", "--quiet", "--no-verify", "-m", _fr_message(root, subject),
                 "--", paths.SWITCH_SETTINGS)  # fmt: skip
    if _sha(root, _FR_REF) != _sha(root, paths.SWITCH_REF):
        _push_branch(root, "fr")
    paths_cache_reset()


def _to_quiet(text: str | None) -> str | None:
    from fr.settings.render import render_init

    return render_init("quiet") if text is None or not _QUIET_LINE.search(text) else None


def _to_repo(text: str | None) -> str | None:
    return _QUIET_LINE.sub("placement: repo", text) if text and _QUIET_LINE.search(text) else None


def live_quiet_features(root: Path) -> list[str]:
    """The quiet features that are not merged: each is a live branch's (review p7-r6)."""
    from fr.placement import quiet
    from fr.placement.merged import merged_features

    wt = quiet.ensure_worktree(root)
    quiet.fast_forward(root)
    return sorted(merged_features(paths.ArtifactSpace(paths.QUIET, wt, None), root).unmerged)


def refuse_live_quiet(root: Path) -> None:
    """A quiet-to-stealth move refuses while any quiet feature is unmerged (review p7-r6):
    once the switch says repo, `fr placement migrate-branch` would carry that live branch's
    artifacts into its product branch, and R24 lets no fr file reach a stealth target."""
    live = live_quiet_features(root)
    if live:
        raise MoveError(
            "fr placement move --to stealth: refused while a quiet feature is not merged "
            f"({', '.join(live)}): a live branch cannot follow the repo into stealth (R24). "
            "Merge or abandon each, then run the move again"
        )


def _switch(ctx: Ctx) -> None:
    root = ctx.root
    if ctx.run is not None:
        tracking = None
        record_placement(root, ctx.to, tracking)
        ctx.emit(f"this workspace's run {ctx.run} is now under placement {ctx.to}")
        return
    ctx.check_source("switch")
    if ctx.to == paths.QUIET:
        _settle_switch(root, _to_quiet, "chore(fr): switch this repo to the quiet placement")
        ctx.emit("switched: origin/fr says placement: quiet")
        return
    if ctx.to == paths.REPO:
        _git(root, "fetch", "--quiet", "--no-tags", "origin")
        flat = ctx.flat()
        landed = {
            p: d for p, (_, d) in _files(root, ctx.default_ref(), keep=flat.__contains__).items()
        }
        if landed != flat:
            raise _PausedError(
                f"paused: {COPY_BRANCH} has not landed on the default branch yet; merge its PR, "
                "then re-run `fr placement move --to repo` to switch"
            )
    if ctx.source == paths.QUIET:
        if ctx.to == paths.STEALTH:
            refuse_live_quiet(root)
        _settle_switch(root, _to_repo, "chore(fr): switch this repo back to the repo placement")
        ctx.emit("switched: origin/fr says placement: repo (a new commit; nothing forced)")
    if ctx.to == paths.STEALTH:
        ctx.emit(
            f"stealth is chosen per run (R24): start each run with "
            f"`fr isolation up --stealth {ctx.tracking.text} --branch <branch>`"
        )


# --- remove -------------------------------------------------------------------------------


def _remove(ctx: Ctx) -> None:
    root = ctx.root
    if ctx.run is not None:
        _remove_run(ctx)
        return
    if ctx.source == paths.QUIET:
        ctx.emit(
            "nothing removed: origin/fr is append-only (R23), and git history still holds "
            "the moved files there"
        )
        return
    gone = sorted(ctx.flat())
    branch = f"chore/fr-placement-move-to-{ctx.to}"
    ref = ctx.default_ref()
    tip = _sha(root, ref)
    if tip is None:
        raise MoveError("fr placement move: the default ref names no commit")
    existing = _sha(root, f"refs/heads/{branch}")
    if existing is None:
        at_tip = _tree(root, tip)
        present = [p for p in gone if p in at_tip]
        subject = f"chore(placement): remove fr's artifacts (moved to placement {ctx.to})"
        new = _commit_tree(root, tip, present, {}, subject, None)
        _git(root, "update-ref", f"refs/heads/{branch}", new, _ZERO)
        existing = new
    elif set(gone) & set(_tree(root, existing)):
        raise MoveError(
            f"fr placement move: the branch {branch} already exists and still holds fr files; "
            "delete it and retry"
        )
    _push_branch(root, branch)
    default = ref.rsplit("/", 1)[-1]
    ctx.emit(
        f"opened branch {branch} (pushed to origin): it deletes {len(gone)} fr file(s) from "
        f"{default}. Nothing was pushed to {default}, and no PR was opened."
    )
    ctx.emit(
        "git history still holds the removed files: they stay readable in every earlier "
        f"commit of {default}"
    )
    _pr_command(
        ctx,
        branch,
        f"chore(placement): remove fr's artifacts (moved to placement {ctx.to})",
        f"Removes fr's artifacts from the default branch: they now live under placement "
        f"{ctx.to} (`fr placement move`). Git history still holds them.\n",
    )


def _remove_run(ctx: Ctx) -> None:
    from fr.placement import stealth

    ref = stealth.parse_ref(ctx.state["tracking"])
    wt = stealth.worktree_path(ctx.root, ref)
    prefix = ctx.state.get("run_prefix")
    if not prefix:
        return
    present = list(_tree(wt, "HEAD", f"{prefix}/"))
    if not present:
        return
    files = [inside(wt, p) for p in present if p.startswith(f"{prefix}/")]
    for f in files:
        f.unlink(missing_ok=True)
    outcome = stealth.commit_and_push(
        ref,
        wt,
        files,
        _fr_message(ctx.root, f"chore(fr): run {ctx.run} moved out of stealth"),
        stealth.plain_commit,
        target_remote=stealth.origin_url(ctx.root),
        target_root=ctx.root,
    )
    if not (outcome.committed or outcome.unchanged):
        raise MoveError(f"fr placement move: {outcome.reason}")
    ctx.emit(f"removed {prefix}/ from {ref.text}; its history still holds the run")


# --- the steps, as data ---------------------------------------------------------------------


def _copy(ctx: Ctx) -> None:
    if ctx.run is not None:
        _copy_run(ctx)
    elif ctx.to == paths.QUIET:
        _copy_quiet(ctx)
    elif ctx.to == paths.STEALTH:
        _copy_stealth(ctx)
    else:
        _copy_repo(ctx)
    if ctx.run is None:
        ctx.state["source_print"] = ctx.copied_print()  # what verify and switch compare


STEP_FUNCS: dict[str, Callable[[Ctx], None]] = {
    "copy": _copy,
    "verify": _verify,
    "switch": _switch,
    "remove": _remove,
}


def _current(root: Path) -> str:
    from fr.artifacts.paths import _marker_placement
    from fr.placement.quiet import read_switch

    if _marker_placement(root) == paths.STEALTH:
        return paths.STEALTH
    return paths.QUIET if read_switch(root) is not None else paths.REPO


def _refuse_foreign_fr_branch(root: Path) -> None:
    """Review pr1431-r8: a move to quiet adopts an existing `origin/fr` as the parent of
    its commits, so one that is not fr's switch branch (no root `settings.yaml` naming a
    placement: some other branch that happens to be named `fr`) refuses, naming it."""
    from fr.placement import quiet

    remote = _remote_branch(root, "fr")
    if remote is None:
        return
    _git(root, "fetch", "--quiet", "--no-tags", "origin", quiet.FETCH_REFSPEC)
    quiet._CACHE.clear()
    if not quiet.is_switch_branch(root):
        raise MoveError(
            f"fr placement move --to quiet: origin/fr ({remote[:12]}) exists and is not an fr "
            f"switch branch (its root {paths.SWITCH_SETTINGS} names no placement), and quiet "
            "keeps its artifacts on a branch named `fr`. Rename or remove that branch on "
            "origin first; nothing was written"
        )


def _start(
    root: Path, to: str, tracking: str | None, run: str | None, emit: Callable[[str], None]
) -> Ctx | None:
    """A fresh move's context, or None when there is nothing to move."""
    from fr.placement import stealth

    current = _current(root)
    if run is not None:
        if current != paths.STEALTH:
            raise MoveError(
                "fr placement move --run: run it in the stealth workspace whose run it moves"
            )
        if to not in (paths.REPO, paths.QUIET):
            raise MoveError(
                "fr placement move --run moves a stealth run to repo or quiet (moving a run "
                "between tracking repos is a non-goal)"
            )
        from fr.placement.quiet import read_switch

        repo_now = paths.QUIET if read_switch(root) is not None else paths.REPO
        if repo_now != to:
            raise MoveError(
                f"fr placement move --run: this repo's placement is {repo_now}, so its run "
                f"moves to {repo_now}, not {to}"
            )
        found = stealth.marker_tracking(root)
        assert found is not None
        state: dict[str, Any] = {
            "to": to,
            "from": paths.STEALTH,
            "run": run,
            "tracking": found[0].text,
            "done": [],
            "started": datetime.now(UTC).isoformat(),
        }
        return Ctx(root, to, paths.STEALTH, state, emit, found[0], run)
    if current == paths.STEALTH:
        raise MoveError(
            "fr placement move: this is a stealth workspace; move its run with --run <id>"
        )
    if current == to:
        emit(f"already at placement {to}: nothing to move")
        return None
    if to == paths.STEALTH and not tracking:
        raise MoveError("fr placement move --to stealth needs --tracking <repo>@<branch>")
    if to != paths.STEALTH and tracking:
        raise MoveError("--tracking names the stealth tracking repo; it goes with --to stealth")
    ref = stealth.parse_ref(tracking) if tracking else None
    if to == paths.STEALTH and current == paths.QUIET:
        refuse_live_quiet(root)  # before any state is written: nothing is in progress
    if to == paths.QUIET and current == paths.REPO:
        from fr.placement.quiet import _has_origin

        if not _has_origin(root):
            raise MoveError("fr placement move --to quiet: this repository has no `origin`")
        _refuse_foreign_fr_branch(root)
    state = {
        "to": to,
        "from": current,
        "run": None,
        "tracking": tracking,
        "done": [],
        "started": datetime.now(UTC).isoformat(),
    }
    return Ctx(root, to, current, state, emit, ref, None)


def _steps(ctx: Ctx) -> str:
    """Run every step not yet done, in order; `done` or `paused`."""
    for step in STEPS:
        if step in ctx.state["done"]:
            continue
        try:
            STEP_FUNCS[step](ctx)
        except _PausedError as e:
            ctx.save()
            ctx.emit(str(e))
            return "paused"
        except _SourceMovedError:
            raise
        except BaseException:
            if not ctx.state["done"]:
                # Nothing verified yet: a re-run reads the default ref afresh, so a fixed
                # source (a crafted cursor removed) is what it copies.
                ctx.state.pop("source_sha", None)
                ctx.state.pop("source_print", None)
            ctx.save()
            raise
        ctx.state["done"].append(step)
        ctx.save()
    return "done"


def move(
    root: Path,
    to: str,
    *,
    tracking: str | None = None,
    run: str | None = None,
    emit: Callable[[str], None] = print,
) -> str:
    """Move the repo (or, with *run*, one stealth run) to placement *to*. Returns `done`,
    `paused` (the copy into `repo` waits for its PR) or `noop`."""
    from fr.placement import stealth

    root = Path(root)
    if to not in TARGETS:
        raise MoveError(f"fr placement move: --to is one of {', '.join(TARGETS)}, not {to!r}")
    dirty = dirty_workspaces(root)
    if dirty:
        raise MoveError(
            "fr placement move: refused while a workspace has uncommitted work (R27); commit "
            "or discard it first:\n  " + "\n  ".join(dirty)
        )
    path = state_path(root)
    if path.is_file():
        state = json.loads(path.read_text())
        asked = (to, tracking if run is None else state.get("tracking"), run)
        if (state.get("to"), state.get("tracking"), state.get("run")) != asked:
            raise MoveError(
                f"fr placement move: a move to {state.get('to')} is in progress ({path}, steps "
                f"done: {', '.join(state.get('done', [])) or 'none'}); re-run "
                f"`fr placement move --to {state.get('to')}` to finish it"
            )
        ref = stealth.parse_ref(state["tracking"]) if state.get("tracking") else None
        ctx = Ctx(root, to, state["from"], state, emit, ref, run)
        emit(f"resuming the move to {to} (done: {', '.join(state['done']) or 'nothing'})")
    else:
        fresh = _start(root, to, tracking, run, emit)
        if fresh is None:
            return "noop"
        ctx = fresh
        ctx.save()
    for attempt in range(MAX_RECOPIES + 1):
        try:
            outcome = _steps(ctx)
        except _SourceMovedError as e:
            # Never switch on a stale copy (review p7-r1): forget the copy's source and
            # copy again. Every copy is idempotent by content, so what already landed in
            # the destination is kept and only what the source gained is added.
            ctx.state["done"] = []
            ctx.state.pop("source_sha", None)
            ctx.state.pop("source_print", None)
            ctx._groups = None
            ctx.save()
            if attempt == MAX_RECOPIES:
                raise MoveError(
                    f"fr placement move: {e}, {MAX_RECOPIES + 1} times in a row; nothing was "
                    f"switched. Re-run `fr placement move --to {to}` once the source is quiet"
                ) from None
            emit(str(e))
            continue
        if outcome != "done":
            return outcome
        break
    path.unlink(missing_ok=True)
    emit(f"moved to placement {to}")
    return "done"
