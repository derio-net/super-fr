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

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
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


def _push_branch(root: Path, branch: str) -> None:
    """A plain push of *branch* to origin (never forced), then its tracking ref."""
    _git(root, "push", "--quiet", "origin", f"refs/heads/{branch}:refs/heads/{branch}")
    _git(root, "fetch", "--quiet", "--no-tags", "origin",
         f"+refs/heads/{branch}:refs/remotes/origin/{branch}")  # fmt: skip


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

    files = _files(root, ref, keep=paths.placement_bound)
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
        groups.append(
            Group(
                feature.feature,
                feature.branch or feature.feature,
                {p.removeprefix(f"{rel}/"): v for p, v in got.items()},
                f"{ct} +0000",
            )
        )
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


# --- workspaces: the precondition, and the placement a workspace records ------------------


def dirty_workspaces(root: Path) -> list[str]:
    """Every workspace of the repo (and the checkout fr runs in) with uncommitted work."""
    from fr.isolation.types import list_states

    seen: set[Path] = set()
    out: list[str] = []
    places = [(Path(root), None), *((s.worktree, s.branch) for s in list_states(Path(root)))]
    for where, branch in places:
        if not where.is_dir():
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
    existing = _sha(root, f"refs/heads/{COPY_BRANCH}")
    if existing is None:
        message = _fr_message(root, "chore(fr): move fr artifacts to the repo placement")
        additions = {rel: ("100644", data) for rel, data in flat.items()}
        new = _commit_tree(root, tip, [], additions, message, None)
        _git(root, "update-ref", f"refs/heads/{COPY_BRANCH}", new, _ZERO)
        existing = new
    else:
        got = {p: d for p, (_, d) in _files(root, existing, keep=flat.__contains__).items()}
        if got != flat:
            raise MoveError(
                f"fr placement move: the branch {COPY_BRANCH} already exists and does not hold "
                "this copy; delete it and retry"
            )
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
    return Group(
        space.feature or "", branch, {p.removeprefix(f"{rel}/"): v for p, v in got.items()}
    )


def _copy_run(ctx: Ctx) -> None:
    root = ctx.root
    group = ctx.groups()[0]
    if ctx.to == paths.QUIET:
        _copy_quiet(ctx)
        return
    content = group.content()
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


def _dest_files(ctx: Ctx) -> dict[str, bytes]:
    root = ctx.root
    fids = {g.fid for g in ctx.groups()}

    def flatten(got: Mapping[str, tuple[str, bytes]], prefix: str) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for p, (_, data) in got.items():
            fid, _, rel = p.removeprefix(prefix).partition("/")
            if fid in fids and rel not in META:
                out[rel] = data
        return out

    if ctx.to == paths.QUIET:
        prefix = f"{paths.FEATURES_DIR}/"
        return flatten(_files(root, paths.SWITCH_REF, prefix), prefix)
    if ctx.to == paths.STEALTH:
        from fr.placement import stealth

        wt = stealth.worktree_path(root, ctx.tracking)
        prefix = f"{stealth.target_dir(root)}/{paths.FEATURES_DIR}/"
        return flatten(_files(wt, stealth._remote_ref(ctx.tracking), prefix), prefix)
    head = ctx.state.get("copy_sha") or "HEAD"
    return {
        p: d
        for p, (_, d) in _files(root, head, keep=paths.placement_bound).items()
        if (ctx.run is None or p in ctx.groups()[0].content())
    }


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
    if _validation(source) != _validation(dest):
        raise MoveError(
            "fr placement move: verify refused: `fr validate artifacts` reports differently "
            "on the destination; nothing was switched"
        )
    ctx.emit(f"verified: {len(source)} file(s), the fold and the validation report agree")


# --- switch -------------------------------------------------------------------------------

_QUIET_LINE: Final = re.compile(r"(?m)^placement: quiet$")


def _switch_text(root: Path) -> str | None:
    out = _git(root, "show", f"{paths.SWITCH_REF}:{paths.SWITCH_SETTINGS}", check=False)
    return out.decode() if out else None


def _commit_switch(root: Path, text: str, subject: str) -> None:
    from fr.placement import quiet

    wt = quiet.ensure_worktree(root)
    quiet.fast_forward(root)
    with quiet.fr_worktree_lock(wt):
        (wt / paths.SWITCH_SETTINGS).write_text(text)
        _git(wt, "add", "--", paths.SWITCH_SETTINGS)
        _git(wt, "commit", "--quiet", "--no-verify", "-m", _fr_message(root, subject), "--",
             paths.SWITCH_SETTINGS)  # fmt: skip
    _push_branch(root, "fr")
    paths_cache_reset()


def _switch(ctx: Ctx) -> None:
    root = ctx.root
    if ctx.run is not None:
        tracking = None
        record_placement(root, ctx.to, tracking)
        ctx.emit(f"this workspace's run {ctx.run} is now under placement {ctx.to}")
        return
    if ctx.to == paths.QUIET:
        from fr.settings.render import render_init

        current = _switch_text(root)
        if current is None or not _QUIET_LINE.search(current):
            _commit_switch(root, render_init("quiet"),
                           "chore(fr): switch this repo to the quiet placement")  # fmt: skip
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
        current = _switch_text(root) or ""
        if _QUIET_LINE.search(current):
            _commit_switch(root, _QUIET_LINE.sub("placement: repo", current),
                           "chore(fr): switch this repo back to the repo placement")  # fmt: skip
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
    if to == paths.QUIET and current == paths.REPO:
        from fr.placement.quiet import _has_origin

        if not _has_origin(root):
            raise MoveError("fr placement move --to quiet: this repository has no `origin`")
    state = {
        "to": to,
        "from": current,
        "run": None,
        "tracking": tracking,
        "done": [],
        "started": datetime.now(UTC).isoformat(),
    }
    return Ctx(root, to, current, state, emit, ref, None)


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
    for step in STEPS:
        if step in ctx.state["done"]:
            continue
        try:
            STEP_FUNCS[step](ctx)
        except _PausedError as e:
            ctx.save()
            emit(str(e))
            return "paused"
        except BaseException:
            if not ctx.state["done"]:
                # Nothing verified yet: a re-run reads the default ref afresh, so a fixed
                # source (a crafted cursor removed) is what it copies.
                ctx.state.pop("source_sha", None)
            ctx.save()
            raise
        ctx.state["done"].append(step)
        ctx.save()
    path.unlink(missing_ok=True)
    emit(f"moved to placement {to}")
    return "done"
