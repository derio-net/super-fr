"""The quiet placement (spec 2026-11-04-repo-feature-settings R2, R23; §3.E).

**The switch.** A repo is quiet when its remote has an orphan branch `fr` whose root
`settings.yaml` says `placement: quiet`. fr reads it from `refs/remotes/origin/fr`, by
the commit that ref names, never a working tree, and fetches that ref at `fr isolation
up` and `fr run start` (`fetch_switch`), refusing both when `origin` is unreachable. A
repo with no `origin` is `repo`, whatever local branches it has.

**The worktree.** Under quiet every artifact lives in a second worktree of `fr`, at
`~/.cache/fr/worktrees/<repo>/fr`, below `features/<feature-id>/` (the layout rule of
`fr.artifacts.paths`). It is created on demand from `origin/fr` (`ensure_worktree`),
never with a force flag, and only ever moves by fast-forward or by appending fr's own
commits.

**The feature id** is the branch slug, which is not injective (`feat/a__b` and
`feat__a/b` share `feat__a__b`, gh#1419). Since the slug is a feature's PATH here, a
branch whose id another branch already holds is refused, naming both: otherwise two
features would write one path, and R23's "each commit touches one feature's path" would
be false without anything noticing.
"""

from __future__ import annotations

import fcntl
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from fr.artifacts import paths
from fr.settings import SettingsError

QUIET_BRANCH: Final = "fr"
"""The orphan branch, local and on origin, that holds a quiet repo's artifacts."""
QUIET_REF: Final = f"refs/heads/{QUIET_BRANCH}"
FETCH_REFSPEC: Final = f"+{QUIET_REF}:{paths.MEMORY_REF}"
"""The fetch of the memory branch: it moves only the remote-tracking ref."""
CONFIG_BRANCH: Final = "fr-config"
"""The configuration branch (spec 2026-11-19-event-driven-a-la-carte R1, R5): an orphan
branch beside `fr` whose tree is `.fr/`, holding the switch (`fr.config.space.CONFIG_BRANCH`)."""
CONFIG_REF: Final = f"refs/heads/{CONFIG_BRANCH}"
CONFIG_FETCH_REFSPEC: Final = f"+{CONFIG_REF}:{paths.SWITCH_REF}"
"""The fetch of the configuration branch, beside `FETCH_REFSPEC`."""

_NETWORK_TIMEOUT_S: Final = 60
_SOURCE: Final = f"{paths.SWITCH_REF}:{paths.SWITCH_SETTINGS}"
_LEGACY_SOURCE: Final = f"{paths.LEGACY_SWITCH_REF}:{paths.LEGACY_SWITCH_SETTINGS}"

Network = Callable[[list[str]], "subprocess.CompletedProcess[str]"]
"""Runs one git argv against origin (bounded, never prompting)."""


@dataclass(frozen=True)
class Switch:
    """A valid quiet switch: its settings, the raw mapping they came from (for per-key
    provenance), and the commit read."""

    settings: Any  # fr.settings.model.Settings (kept loose: no import cycle at load)
    data: object
    sha: str
    ref: str = paths.SWITCH_REF
    """The remote-tracking ref the switch was read at: `SWITCH_REF`, or under R13's
    fallback `LEGACY_SWITCH_REF`."""
    source: str = _SOURCE


_CACHE: dict[tuple[str, str, str], Switch | None] = {}
"""(common dir, fr-config sha, fr sha) -> the parsed switch. The shas are read from the
filesystem on every call, so a moved ref is a new key: the cache can never serve stale
settings."""


def _git_dir(root: Path) -> Path | None:
    dot = root / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        try:
            line = dot.read_text().strip()
        except OSError:
            return None
        if line.startswith("gitdir:"):
            return (root / line.removeprefix("gitdir:").strip()).resolve()
    return None


_REFSTORAGE: Final = re.compile(r"(?im)^\s*refstorage\s*=\s*(\S+)")


def _reftable(common: Path) -> bool:
    """Does this repository keep its refs in a reftable (review pr1431-r3)? Then there
    are no loose refs or `packed-refs` to read, and every ref read goes through git."""
    if (common / "reftable").exists():
        return True
    try:
        config = (common / "config").read_text()
    except OSError:
        return False
    found = _REFSTORAGE.search(config)
    return found is not None and found.group(1).strip().strip('"').lower() != "files"


def _git_ref_read(cwd: Path, *args: str) -> str | None:
    """One read of a ref through git (reftable only); None when git says there is no
    such ref. A git that cannot answer refuses: an unread ref is never read as absent."""
    from fr.git import GitUnavailableError, git_answer

    try:
        done = git_answer(cwd, *args)
    except GitUnavailableError as e:
        raise SettingsError(f"placement: cannot read the refs of a reftable repository: {e}") from e
    return done.stdout if done.returncode == 0 else None


def _ref_sha(common: Path, ref: str) -> str | None:
    """The sha a ref holds, read from the filesystem (loose, then packed-refs), or through
    git under reftable."""
    if _reftable(common):
        out = _git_ref_read(common, "rev-parse", "--verify", "--quiet", f"{ref}^{{object}}")
        return (out.strip() or None) if out is not None else None
    loose = common / ref
    try:
        if loose.is_file():
            value = loose.read_text().strip()
            return value or None
        packed = common / "packed-refs"
        if not packed.is_file():
            return None
        for line in packed.read_text().splitlines():
            if line.startswith(("#", "^")):
                continue
            sha, _, name = line.partition(" ")
            if name == ref:
                return sha
    except OSError:
        return None
    return None


def _has_origin(root: Path) -> bool:
    """An `origin` remote is configured. Not a git repo (or no such directory) is no:
    the caller's own repo check names that problem."""
    from fr.git import GitUnavailableError, git_answer

    if not Path(root).is_dir():
        return False
    try:
        return git_answer(root, "config", "--get", "remote.origin.url").returncode == 0
    except GitUnavailableError:
        return False


def switch_texts(root: Path) -> tuple[tuple[str, str] | None, tuple[str, str] | None]:
    """The raw switch files: ((sha, text) at `origin/fr-config:.fr/settings.yaml`, (sha,
    text) at `origin/fr:settings.yaml`), each None when its ref or its file is absent.
    No origin is no switch at all (R23)."""
    common = paths._common_dir(root)
    if common is None or not _has_origin(root):
        return None, None
    from fr.settings.load import show_at_commit

    out: list[tuple[str, str] | None] = []
    for ref, rel in (
        (paths.SWITCH_REF, paths.SWITCH_SETTINGS),
        (paths.LEGACY_SWITCH_REF, paths.LEGACY_SWITCH_SETTINGS),
    ):
        sha = _ref_sha(common, ref)
        text = None if sha is None else show_at_commit(root, sha, rel)
        out.append(None if sha is None or text is None else (sha, text))
    return out[0], out[1]


def _read_legacy(root: Path) -> Switch | None:
    """The switch as an fr below S1 reads it: `origin/fr:settings.yaml` alone (R6). The
    test of the legacy copy: what `write_settings` leaves there must read the same."""
    _, old = switch_texts(Path(root))
    if old is None:
        return None
    parsed = parse_switch_text(old[1], source=_LEGACY_SOURCE)
    return (
        None if parsed is None else Switch(*parsed, old[0], paths.LEGACY_SWITCH_REF, _LEGACY_SOURCE)
    )


def _read(root: Path) -> Switch | None:
    """The switch: `origin/fr-config:.fr/settings.yaml` (R5), else the old
    `origin/fr:settings.yaml` (R13). Both there and different refuses, naming both (R6)."""
    common = paths._common_dir(root)
    if common is None:
        return None
    new_sha = _ref_sha(common, paths.SWITCH_REF)
    old_sha = _ref_sha(common, paths.LEGACY_SWITCH_REF)
    if new_sha is None and old_sha is None:
        return None
    key = (str(common), new_sha or "", old_sha or "")
    if key in _CACHE:
        return _CACHE[key]
    new, old = switch_texts(root)
    result: Switch | None = None
    if new is not None and old is not None and new[1] != old[1]:
        _settle_differing(root, new, old)
    if new is not None:
        parsed = parse_switch_text(new[1], source=_SOURCE, branch=CONFIG_BRANCH)
        if parsed is not None:
            result = Switch(parsed[0], parsed[1], new[0], paths.SWITCH_REF, _SOURCE)
    elif old is not None:
        parsed = parse_switch_text(old[1], source=_LEGACY_SOURCE)
        if parsed is not None:
            result = Switch(parsed[0], parsed[1], old[0], paths.LEGACY_SWITCH_REF, _LEGACY_SOURCE)
    _CACHE[key] = result
    return result


_HISTORY_LIMIT: Final = 500
"""How far back fr-config's first-parent history is searched for the legacy copy's bytes."""


def history_blobs(cwd: Path, ref: str, rel: str, limit: int = _HISTORY_LIMIT) -> set[str]:
    """Every blob *rel* held on *ref*'s first-parent history (its last *limit* commits
    that touched it), read from one `git log --raw`."""
    done = _git(
        cwd, "log", "--first-parent", "--no-abbrev", "--format=", "--raw", "-n", str(limit),
        ref, "--", rel,
    )  # fmt: skip
    blobs: set[str] = set()
    for line in done.stdout.splitlines() if done.returncode == 0 else []:
        fields = line.split("\t", 1)[0].split()
        if len(fields) >= 4 and line.startswith(":"):
            blobs.update(b for b in fields[2:4] if b.strip("0"))
    return blobs


def legacy_lags(cwd: Path, ref: str, rel: str, legacy_blob: str | None) -> bool:
    """The legacy copy's bytes (*legacy_blob*) are those *rel* held at some commit on
    *ref*'s first-parent history: the configuration branch advanced through a reviewed
    change (spec 2026-11-19-event-driven-a-la-carte R6, §B "Older readers") and the old
    file has not followed yet."""
    return legacy_blob is not None and legacy_blob in history_blobs(cwd, ref, rel)


def _blob(cwd: Path, spec: str) -> str | None:
    done = _git(cwd, "rev-parse", "--verify", "--quiet", spec)
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def settled_message(root: Path, text: str, summary: str) -> str:
    """`chore(fr): <summary>` through the commit templates of the settings *text* (the
    reviewed configuration being brought in step). `fr_message` would read the settings,
    which is the very read that is settling: it would recurse."""
    from fr.git_policy.templates import FrCommitKind, _with_trailer, render_subject
    from fr.settings.load import parse_settings_text

    # No run issue either: `run_issue` resolves the artifact space, which reads the switch.
    settings = parse_settings_text(text, source="the configuration branch", servable=False)
    kind: FrCommitKind = "bookkeeping"
    return _with_trailer(render_subject(settings, "chore", "fr", summary, None), kind)


SYNC_COMMAND: Final = "fr settings sync"
"""The operator's command that brings a lagging legacy copy in step (R6): it previews; with
`--yes` it writes. No reader writes the legacy copy on its own (review of decision
p2-config-changes-by-pr): a push straight to an unprotected configuration branch would
otherwise be copied silently, and the one signal that it moved outside review would go."""


def lag_refusal(what: str, new_at: str, old_at: str) -> SettingsError:
    """R6's refusal when the old copy holds an earlier first-parent version of the new."""
    return SettingsError(
        f"placement: {what} differ: {new_at} and {old_at}. The old one holds an earlier "
        f"version of the new one (the configuration branch moved on since), so fr will not "
        f"act until they are in step (R6). Preview the move with `{SYNC_COMMAND}` (both refs, "
        f"the tip, the commits between with their second parents), then "
        f"`{SYNC_COMMAND} --yes --expect <tip>` writes the old copy"
    )


def mismatch_refusal(what: str, new_at: str, old_at: str) -> SettingsError:
    """R6's refusal when neither file is an earlier version of the other."""
    return SettingsError(
        f"placement: {what} differ: {new_at} and {old_at}, and neither matches the other "
        "at any earlier version, so fr cannot tell which is meant (R6). Edit them by hand to "
        "the same bytes (the configuration branch through a pull request) and push them"
    )


def _settle_differing(root: Path, new: tuple[str, str], old: tuple[str, str]) -> None:
    """The two switches differ (R6): refuse, saying whether the old one lags (and naming
    `fr settings sync`) or neither matches. Never writes."""
    what = "the two quiet switches"
    new_at = f"{_SOURCE} ({new[0][:12]})"
    old_at = f"{_LEGACY_SOURCE} ({old[0][:12]})"
    if legacy_lags(root, paths.SWITCH_REF, paths.SWITCH_SETTINGS, _blob(root, _LEGACY_SOURCE)):
        raise lag_refusal(what, new_at, old_at)
    raise mismatch_refusal(what, new_at, old_at)


CHANGE_REFSPEC: Final = "+refs/heads/fr-config-change/*:refs/remotes/origin/fr-config-change/*"
"""The fetch of the configuration change branches, so `changes_since` can match a merge's
second parent against their tips."""


@dataclass(frozen=True)
class SyncPlan:
    """What `fr settings sync` would do: the two refs, the configuration branch's tip and
    file blob, its first-parent commits since the old copy's version (newest first: sha,
    second-parent sha or "", subject, whether that second parent is the tip of a fetched
    `fr-config-change/*` branch), and the state. The label is information for the
    operator, never an authorization: only the operator's `--yes --expect <tip>` is.

    `absent` (lens review l-errors-r1): the configuration branch holds the switch and the
    old copy is not there at all, the state a write that stopped between the two pushes
    leaves (`fr settings init` pushed the configuration branch, then origin refused the
    old one). Its commits are the configuration branch's whole first-parent history (up
    to the history limit), and `--yes --expect <tip>` lands the old copy from that tip."""

    new_at: str
    old_at: str
    state: str  # "in-step" | "lags" | "mismatch" | "absent" | "none"
    commits: tuple[tuple[str, str, str, bool], ...] = ()
    text: str | None = None
    tip: str = ""
    blob: str = ""


def changes_since(
    cwd: Path, ref: str, rel: str, blob: str
) -> tuple[tuple[str, str, str, bool], ...]:
    """The first-parent commits of *ref* after the last one where *rel* was *blob*,
    newest first: (sha, second parent, subject, merged). *merged* is true only when the
    second parent IS the tip of a fetched `refs/remotes/origin/fr-config-change/*`; the
    subject is never read for it (anyone can write a subject)."""
    listed = _git(cwd, "log", "--first-parent", "--format=%H%x09%P%x09%s",
                  "-n", str(_HISTORY_LIMIT), ref)  # fmt: skip
    changes = _git(cwd, "for-each-ref", "--format=%(objectname)",
                   "refs/remotes/origin/fr-config-change/")  # fmt: skip
    heads = set(changes.stdout.split())
    out: list[tuple[str, str, str, bool]] = []
    for line in listed.stdout.splitlines():
        sha, parents, subject = (line.split("\t", 2) + ["", ""])[:3]
        if _blob(cwd, f"{sha}:{rel}") == blob:
            break
        second = (parents.split()[1:2] or [""])[0]
        out.append((sha, second, subject, bool(second) and second in heads))
    return tuple(out)


def expect_refusal(plan: SyncPlan, expect: str | None) -> SettingsError | None:
    """`--yes` writes only from the tip the operator previewed (no TOCTOU): None when
    *expect* is that tip, else the refusal naming the preview to run again."""
    if expect is not None and expect == plan.tip:
        return None
    why = (
        "`--yes` needs `--expect <tip>`, the configuration branch tip its preview showed"
        if expect is None
        else f"the configuration branch tip is now {plan.tip}, not {expect}"
    )
    return SettingsError(
        f"fr settings sync: {why}; nothing was written. Run `{SYNC_COMMAND}` to preview it "
        f"again, then `{SYNC_COMMAND} --yes --expect <tip>`"
    )


def sync_plan(root: Path) -> SyncPlan:
    """The quiet `fr settings sync` preview: fetches the two switch branches and the change
    branches, then reads (nothing is pushed)."""
    root = Path(root)
    net = _default_network(root)
    _fetch_both(root, net, None)
    net(["git", "fetch", "--quiet", "--no-tags", "--prune", "origin", CHANGE_REFSPEC])
    _CACHE.clear()
    new, old = switch_texts(root)
    new_at = f"{_SOURCE} ({new[0][:12]})" if new else f"{_SOURCE} (absent)"
    old_at = f"{_LEGACY_SOURCE} ({old[0][:12]})" if old else f"{_LEGACY_SOURCE} (absent)"
    if new is not None and old is None and parse_switch_text(new[1]) is not None:
        tip, blob = new[0], _blob(root, _SOURCE) or ""
        commits = changes_since(root, paths.SWITCH_REF, paths.SWITCH_SETTINGS, "")
        return SyncPlan(new_at, old_at, "absent", commits, new[1], tip, blob)
    if new is None or old is None:
        return SyncPlan(new_at, old_at, "none")
    tip, blob = new[0], _blob(root, _SOURCE) or ""
    if new[1] == old[1]:
        return SyncPlan(new_at, old_at, "in-step", tip=tip, blob=blob)
    old_blob = _blob(root, _LEGACY_SOURCE)
    if not legacy_lags(root, paths.SWITCH_REF, paths.SWITCH_SETTINGS, old_blob):
        return SyncPlan(new_at, old_at, "mismatch", tip=tip, blob=blob)
    assert old_blob is not None
    commits = changes_since(root, paths.SWITCH_REF, paths.SWITCH_SETTINGS, old_blob)
    return SyncPlan(new_at, old_at, "lags", commits, new[1], tip, blob)


def half_written(root: Path) -> SyncPlan | None:
    """The `absent` sync plan when origin's `fr-config` holds the quiet switch and the old
    copy on `fr` is missing (a write that stopped between its two pushes), else None.
    Fetches like the preview; writes nothing."""
    plan = sync_plan(root)
    return plan if plan.state == "absent" else None


def finish_refusal(command: str, plan: SyncPlan) -> SettingsError:
    """What a command says when it meets a half-written switch (lens review l-errors-r1):
    the sync that finishes it, previewed first."""
    return SettingsError(
        f"{command}: {plan.new_at} holds the switch but {plan.old_at} is missing: an "
        "earlier write stopped before the old copy, which an older fr reads. Finish it: "
        f"run `{SYNC_COMMAND}` to preview it, then `{SYNC_COMMAND} --yes --expect {plan.tip}`"
    )


def sync_legacy(root: Path, *, expect: str | None) -> SyncPlan:
    """`fr settings sync --yes --expect <tip>` under quiet: fetch, refuse unless the tip is
    *expect* and the old copy lags, then write it with `write_legacy`."""
    root = Path(root)
    plan = sync_plan(root)
    if plan.state == "mismatch":
        raise mismatch_refusal("the two quiet switches", plan.new_at, plan.old_at)
    if plan.state in ("lags", "absent") and plan.text is not None:
        refused = expect_refusal(plan, expect)
        if refused is not None:
            raise refused
        message = settled_message(
            root, plan.text, f"bring the old quiet switch in step with {CONFIG_BRANCH}"
        )
        write_legacy(root, plan.text, message)
        _CACHE.clear()
    return plan


def parse_switch_text(
    text: str, source: str = _SOURCE, branch: str = QUIET_BRANCH
) -> tuple[Any, object] | None:
    """A switch file's quiet settings and raw mapping, or None when it is no quiet switch:
    no live `placement` line, or `placement: repo`. One validation for every reader of a
    switch, local or through the forge (review p1-r2): a schema error, a non-canonical
    spelling or `placement: stealth` refuses (`SettingsError`), never reads as absent.

    Review pr1431-r8: a file with no live `placement` line is not a switch (an unrelated
    branch that happens to be named `fr`), so it reads as `repo`, as the hooks read it,
    and its schema is nobody's business here."""
    from fr.settings.load import parse_settings_text, yaml_of

    if not names_placement(text):
        return None
    settings = parse_settings_text(text, source=source, servable=False)
    data = yaml_of(text, source)
    problem = switch_spelling_problem(text, data, source, branch)
    if problem is not None:
        raise SettingsError(problem)
    if settings.placement == paths.QUIET:
        return settings, data
    if settings.placement != paths.REPO:
        raise SettingsError(
            f"{source}: placement: {settings.placement} cannot be set on the `{branch}` "
            "switch: stealth is chosen per run, never by repo settings (R24); the switch "
            "says `placement: quiet`"
        )
    return None


_CANONICAL_PLACEMENT: Final = re.compile(r"placement: [a-z]+")


def _live_placement_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if "placement" in line and not line.lstrip().startswith("#")
    ]


def names_placement(text: str) -> bool:
    """Does a root `settings.yaml` on `fr` have a live line naming `placement`? Only
    such a file is a switch, quiet or repo (review pr1431-r8); the hooks ask the same."""
    return bool(_live_placement_lines(text))


def is_switch_branch(root: Path) -> bool:
    """`origin/fr` (as last fetched) is fr's memory branch: its root `settings.yaml`
    (the legacy switch, R6) names a placement. False when it is absent or is some other
    branch named `fr`."""
    from fr.settings.load import show_at_commit

    common = paths._common_dir(Path(root))
    sha = _ref_sha(common, paths.MEMORY_REF) if common is not None else None
    if sha is None:
        return False
    text = show_at_commit(Path(root), sha, paths.LEGACY_SWITCH_SETTINGS)
    return text is not None and names_placement(text)


def switch_spelling_problem(
    text: str, data: object, source: str = _SOURCE, branch: str = QUIET_BRANCH
) -> str | None:
    """Why the switch's `placement` is not spelled canonically, or None (review p6-r3).

    The hooks and the OpenCode plugin read the switch WITHOUT `fr` (R26), so they and fr
    must agree on what a valid switch is: one line `placement: <value>`, at column 0,
    unquoted, with no comment and no trailing space, and no other live line naming
    `placement`. Every other spelling YAML accepts (quoted, commented, flow, indented,
    a quoted or escaped key) is refused here, and the hooks treat it as fr-enabled, so
    neither side reads it as `repo`. `fr settings init --quiet` writes the canonical
    line. A file naming no placement at all is fine (the default, `repo`)."""
    live = _live_placement_lines(text)
    if len(live) == 1 and _CANONICAL_PLACEMENT.fullmatch(live[0]):
        return None
    if not live and not (isinstance(data, dict) and "placement" in data):
        return None
    found = "; ".join(repr(line) for line in live) or "a key that does not read `placement`"
    return (
        f"{source}: the placement must be spelled exactly `placement: quiet` (or "
        "`placement: repo`): one line, at column 0, unquoted, with no comment, and no other "
        "line naming placement, because the hooks read the switch without fr (R26); found "
        f"{found}. Rewrite it and push `{branch}`"
    )


def read_switch(root: Path) -> Any:
    """The quiet settings `origin/fr` carries (`fr.settings.model.Settings`), or None
    when there is no switch: no origin, no `origin/fr`, no root `settings.yaml`, or one
    saying `placement: repo`. A file that is there but unreadable or invalid refuses
    (`SettingsError`, R2): it is never read as absent."""
    switch = _read(Path(root))
    return None if switch is None else switch.settings


def switch(root: Path) -> Switch | None:
    """`read_switch` with the raw mapping and the commit, for the settings loader."""
    return _read(Path(root))


def refuse_under_quiet(root: Path, command: str, why: str) -> None:
    """Refuse *command* BEFORE it writes anything when the repo is quiet (review p3-r1):
    a writer that cannot yet put its files on the `fr` branch must not leave them in the
    product checkout, where a plain `git add -A` carries them to the feature branch.
    Reads the switch alone (no fr worktree is created to refuse); a stealth workspace
    refuses the same way (R24: no fr file reaches the target)."""
    from fr.artifacts.paths import outside_repo

    placement = outside_repo(Path(root))
    if placement is not None:
        raise SettingsError(
            f"`{command}` is not available under placement {placement} yet: {why}. Nothing "
            "was written (R23, R24: no fr file reaches a product branch)"
        )


def worktree_path(root: Path) -> Path:
    """`~/.cache/fr/worktrees/<repo>/fr`, beside isolation's own worktrees (same `<repo>`
    as `fr.isolation.types.repo_cache_name`, read without a subprocess). A relative *root*
    (`.`) is resolved first: its name would otherwise be empty."""
    root = Path(root).resolve()
    common = paths._common_dir(root)
    name = common.parent.name if common is not None and common.name == ".git" else root.name
    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".cache" / "fr" / "worktrees" / name / QUIET_BRANCH


def head_branch(root: Path) -> str | None:
    """The branch checked out at *root*, from its HEAD file; None when detached."""
    git_dir = _git_dir(Path(root))
    if git_dir is None:
        return None
    common = paths._common_dir(Path(root))
    if common is not None and _reftable(common):
        out = (_git_ref_read(Path(root), "symbolic-ref", "--quiet", "HEAD") or "").strip()
        return out.removeprefix("refs/heads/") if out.startswith("refs/heads/") else None
    try:
        head = (git_dir / "HEAD").read_text().strip()
    except OSError:
        return None
    return head.removeprefix("ref: refs/heads/") if head.startswith("ref: refs/heads/") else None


def _branch_names(common: Path) -> set[str]:
    """Every local and `origin` branch name, from the filesystem."""
    prefixes = ("refs/heads/", "refs/remotes/origin/")
    names: set[str] = set()
    if _reftable(common):
        out = _git_ref_read(common, "for-each-ref", "--format=%(refname)", *prefixes) or ""
        for name in out.splitlines():
            for prefix in prefixes:
                if name.startswith(prefix):
                    names.add(name.removeprefix(prefix))
        names.discard("HEAD")
        names.difference_update((QUIET_BRANCH, CONFIG_BRANCH))
        return names
    for prefix in prefixes:
        base = common / prefix
        if base.is_dir():
            names.update(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())
    packed = common / "packed-refs"
    try:
        lines = packed.read_text().splitlines() if packed.is_file() else []
    except OSError:
        lines = []
    for line in lines:
        name = line.partition(" ")[2]
        for prefix in prefixes:
            if name.startswith(prefix):
                names.add(name.removeprefix(prefix))
    names.discard("HEAD")
    names.difference_update((QUIET_BRANCH, CONFIG_BRANCH))
    return names


def _where(placement: str) -> tuple[str, str]:
    """(refusal prefix, where a feature path lives) for the shared quiet/stealth checks."""
    if placement == "stealth":
        return "placement stealth", "the tracking repo's directory for this target"
    return "placement quiet", f"the `{QUIET_BRANCH}` branch"


def check_feature_id(root: Path, branch: str, placement: str = "quiet") -> str:
    """*branch*'s feature id, refusing one another branch already holds (gh#1419)."""
    if branch in (QUIET_BRANCH, CONFIG_BRANCH):
        raise SettingsError(
            f"placement quiet: a feature branch cannot be named `{branch}`, the branch "
            "that holds the " + ("artifacts" if branch == QUIET_BRANCH else "configuration")
        )
    fid = paths.checked_feature_id(branch)
    common = paths._common_dir(Path(root))
    others = (
        sorted(n for n in _branch_names(common) if n != branch and paths.feature_id(n) == fid)
        if common is not None
        else []
    )
    if others:
        raise SettingsError(
            f"{_where(placement)[0]}: branch {branch!r} and {', '.join(map(repr, others))} "
            f"share the feature id {fid!r} (the branch name with `/` as `__`), which is one "
            f"path in {_where(placement)[1]}. Rename one of them"
        )
    return fid


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    from fr.git import GitUnavailableError, git_answer

    try:
        return git_answer(root, *args)
    except GitUnavailableError as e:
        raise SettingsError(f"placement quiet: {e}") from e


_OWNED: set[tuple[str, str]] = set()
"""(common dir, worktree path) pairs already verified this process."""


def _check_owner(root: Path, path: Path, branch: str = QUIET_BRANCH) -> None:
    """The worktree at *path* must be THIS repo's, on `fr`. The path is keyed by the
    repo's directory name only, so two repos of the same name share it: reusing another
    repo's worktree would commit this repo's artifacts to that repo's `fr` branch and
    push them to its origin."""
    mine = paths._common_dir(Path(root))
    if mine is not None and (str(mine), str(path)) in _OWNED:
        return
    theirs = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    owner = Path(theirs.stdout.strip()).resolve() if theirs.returncode == 0 else None
    if mine is None or owner is None or owner != mine.resolve():
        owner_repo = owner.parent if owner is not None and owner.name == ".git" else owner
        raise SettingsError(
            f"placement quiet: {path} is the `{branch}` worktree of another repository "
            f"({owner_repo or 'unknown'}), not of {Path(root).resolve()}: two repos with the "
            "same directory name share that path. Move one of them (or that worktree) "
            "away and retry"
        )
    head = _git(path, "symbolic-ref", "--quiet", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != f"refs/heads/{branch}":
        raise SettingsError(
            f"placement quiet: {path} is a worktree of {Path(root).resolve()} but its HEAD is "
            f"{head.stdout.strip() or 'detached'}, not refs/heads/{branch}; fr writes there "
            f"only on `{branch}`. Switch it back (`git -C {path} switch {branch}`)"
        )
    _OWNED.add((str(mine), str(path)))


def _refuse_unrelated_local(
    root: Path, branch: str = QUIET_BRANCH, tracking: str = paths.MEMORY_REF
) -> None:
    """A local `fr` (or `fr-config`) branch is adopted only when it is an ancestor or a
    descendant of its `origin/` ref (review p3-r9): any other one is somebody else's
    history, and committing on it would push a second, unrelated root to origin."""
    remote = _git(root, "rev-parse", "--verify", "--quiet", f"{tracking}^{{commit}}")
    if remote.returncode != 0:
        return
    local = f"refs/heads/{branch}"
    for older, newer in ((local, tracking), (tracking, local)):
        if _git(root, "merge-base", "--is-ancestor", older, newer).returncode == 0:
            return
    raise SettingsError(
        f"placement quiet: the local `{branch}` branch is neither an ancestor nor a "
        f"descendant of origin/{branch}, so it is not this repo's history there; "
        f"fr will not adopt it. Rename or delete it (`git branch -m {branch} "
        f"{branch}-old`) and retry"
    )


def config_tree_problem(names: list[str], depth: int) -> str | None:
    """The first path of a configuration branch's tree outside `.fr/` (*depth* 0, quiet's
    `fr-config`) or outside `<one segment>/.fr/` (*depth* 1, a stealth `<branch>-config`),
    or None. Spec 2026-11-19-event-driven-a-la-carte §B: the tree is `.fr/`. The hooks'
    `_fr_config_tree_ok` and marker.ts `configTreeOk` are the same rule."""
    from fr.config.space import SPACE_DIR

    top = f"{SPACE_DIR}/"
    below = f"/{SPACE_DIR}/"
    for name in names:
        if not name:
            continue
        if depth == 0:
            if not (name.startswith(top) and len(name) > len(top)):
                return name
            continue
        at = name.find(below)
        if at <= 0 or "/" in name[:at] or len(name) <= at + len(below):
            return name
    return None


def refuse_foreign_config(
    cwd: Path, ref: str, *, branch: str, depth: int, product_refs: list[str]
) -> None:
    """Refuse to adopt (or push) *ref* as the configuration branch *branch* unless it is
    one (review p2-r2): its tree lies below `.fr/` (`config_tree_problem`) and none of its
    commits is reachable from *product_refs* (an orphan beside the product, never a branch
    cut from it). Mirrors `fr.placement.move._refuse_foreign_fr_branch`."""
    sha = _git(cwd, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").stdout.strip()
    if not sha:
        return
    from fr.config.space import SPACE_DIR

    where = f"{SPACE_DIR}/" if depth == 0 else f"<target-dir>/{SPACE_DIR}/"
    listed = _git(cwd, "ls-tree", "-r", "-z", "--name-only", sha)
    if listed.returncode != 0:
        raise SettingsError(
            f"placement: cannot read the tree of `{branch}` ({sha[:12]}): "
            f"{listed.stderr.strip()}; fr will not adopt a branch it cannot inspect"
        )
    bad = config_tree_problem(listed.stdout.split("\0"), depth)
    if bad is not None:
        raise SettingsError(
            f"placement: `{branch}` ({sha[:12]}) is not a configuration branch: its tree "
            f"holds {bad!r}, outside {where} (spec 2026-11-19-event-driven-a-la-carte §B: an "
            f"orphan branch whose tree is {where}). fr will not adopt or push it; rename or "
            "remove that branch and retry"
        )
    others = [r for r in product_refs if r]
    if not others:
        return
    total = _git(cwd, "rev-list", "--count", sha).stdout.strip()
    own = _git(cwd, "rev-list", "--count", sha, "--not", *others).stdout.strip()
    if total != own:
        raise SettingsError(
            f"placement: `{branch}` ({sha[:12]}) is not a configuration branch: it shares "
            "history with the product's branches, where it must be an orphan (spec "
            "2026-11-19-event-driven-a-la-carte §B). fr will not adopt or push it; rename "
            "or remove that branch and retry"
        )


_OWN_REFS: Final = (
    QUIET_REF,
    CONFIG_REF,
    paths.MEMORY_REF,
    paths.SWITCH_REF,
    "refs/remotes/origin/HEAD",
)


def product_refs(root: Path) -> list[str]:
    """Every local and origin branch of *root* that is the product's: all but quiet's own
    (`fr`, `fr-config`) and the configuration change branches."""
    listed = _git(root, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes/origin")
    return [
        r for r in listed.stdout.split() if r not in _OWN_REFS and "/fr-config-change/" not in r
    ]


def _check_config_refs(root: Path) -> None:
    """`origin/fr-config` and a local `fr-config`, each when present, are configuration
    branches (`refuse_foreign_config`)."""
    others = product_refs(root)
    for ref in (paths.SWITCH_REF, CONFIG_REF):
        refuse_foreign_config(root, ref, branch=CONFIG_BRANCH, depth=0, product_refs=others)


def _forget_own_stale_entry(root: Path, path: Path) -> None:
    """Clear the registration of the fr worktree at *path* when its directory is gone
    (else `worktree add` refuses a "missing but already registered worktree"), and no
    other. Never a global `git worktree prune` (review pr1431-n1): in a devcontainer the
    host's other worktrees are not mounted, so prune would deregister every one of them.
    A locked entry is left alone, as prune leaves it."""
    import shutil

    common = paths._common_dir(Path(root))
    if common is None:
        return
    want = (path / ".git").resolve()
    for entry in sorted((common / "worktrees").glob("*")):
        try:
            recorded = Path((entry / "gitdir").read_text().strip())
        except OSError:
            continue
        if recorded.resolve() != want or recorded.exists() or (entry / "locked").exists():
            continue
        shutil.rmtree(entry, ignore_errors=True)


def ensure_worktree(root: Path) -> Path:
    """The fr worktree, created on demand from `origin/fr` (a local `fr` branch tracking
    it), never with a force flag. Refuses a path that is there but is not it."""
    return _ensure_linked(root, worktree_path(root), QUIET_BRANCH, paths.MEMORY_REF)


def config_worktree_path(root: Path) -> Path:
    """`~/.cache/fr/worktrees/<repo>/fr-config`, beside the `fr` worktree
    (`fr.config.space.quiet_checkout` answers the same path)."""
    return worktree_path(root).parent / CONFIG_BRANCH


def ensure_config_worktree(root: Path) -> Path | None:
    """The `fr-config` worktree (R5), created on demand from `origin/fr-config` like the
    `fr` one; None while neither that ref nor a local `fr-config` exists."""
    common = paths._common_dir(Path(root))
    if common is None:
        return None
    if _ref_sha(common, paths.SWITCH_REF) is None and _ref_sha(common, CONFIG_REF) is None:
        return None
    _check_config_refs(root)
    path = _ensure_linked(root, config_worktree_path(root), CONFIG_BRANCH, paths.SWITCH_REF)
    _fast_forward_linked(root, path, CONFIG_BRANCH, paths.SWITCH_REF)
    return path


def require_current_config_worktree(root: Path) -> Path | None:
    """The `fr-config` worktree, fast-forwarded to `origin/fr-config` and refused unless it
    then IS that tip with no uncommitted or untracked file (review p4-r7). Readers read this
    worktree, so a migration that moves a file into the configuration space refuses here,
    before any product file leaves, rather than skip a fast-forward silently. None while
    there is no `fr-config` (nothing to check)."""
    path = ensure_config_worktree(root)
    if path is None:
        return None
    dirty = _git(path, "status", "--porcelain", "--untracked-files=all").stdout.splitlines()
    if dirty:
        raise SettingsError(
            f"placement quiet: the `{CONFIG_BRANCH}` worktree {path} has uncommitted changes "
            f"({len(dirty)} path(s), e.g. {dirty[0].strip()}): fr reads that worktree, so it "
            f"will not move configuration into it. Propose them as a pull request to "
            f"`{CONFIG_BRANCH}`, or set them aside (`git -C {path} stash -u`), then run "
            "`fr migrate artifacts --yes` again (S1 R10)"
        )
    head = _git(path, "rev-parse", "--verify", "--quiet", "HEAD").stdout.strip()
    tip = _git(path, "rev-parse", "--verify", "--quiet", paths.SWITCH_REF).stdout.strip()
    if head != tip:
        raise SettingsError(
            f"placement quiet: the `{CONFIG_BRANCH}` worktree {path} has diverged from "
            f"{paths.SWITCH_REF} (HEAD {head[:12] or 'none'}, tip {tip[:12] or 'none'}): its "
            f"commits are not on origin, and fr will not move configuration into it. Propose "
            f"them as a pull request to `{CONFIG_BRANCH}`, or drop them "
            f"(`git -C {path} reset --keep {paths.SWITCH_REF}`), then run "
            "`fr migrate artifacts --yes` again (S1 R10)"
        )
    return path


def _ensure_linked(root: Path, path: Path, branch: str, tracking: str) -> Path:
    """A linked worktree of *root* at *path* on *branch*, created from *tracking* (or the
    local branch), never with a force flag. Refuses a path that is there but is not it."""
    if (path / ".git").exists():
        _check_owner(root, path, branch)
        return path
    if path.exists() and any(path.iterdir()):
        raise SettingsError(
            f"placement quiet: {path} exists and is not the `{branch}` worktree; "
            "move it away and retry"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    _forget_own_stale_entry(root, path)
    local = _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}")
    if local.returncode == 0:
        _refuse_unrelated_local(root, branch, tracking)
        argv = ["worktree", "add", str(path), branch]
    else:
        argv = ["worktree", "add", "--no-track", "-b", branch, str(path), tracking]
    done = _git(root, *argv)
    if done.returncode != 0 and not (path / ".git").exists():
        raise SettingsError(
            f"placement quiet: cannot create the `{branch}` worktree at {path}: "
            f"{done.stderr.strip()}"
        )
    if local.returncode != 0:
        _git(root, "config", f"branch.{branch}.remote", "origin")
        _git(root, "config", f"branch.{branch}.merge", f"refs/heads/{branch}")
    return path


def preview_problem(root: Path) -> str | None:
    """Why a read-only preview (`fr archive --dry-run`, review p3-r5) cannot see what a
    real run at *root* would read, or None when it can: the real run creates the `fr`
    worktree from `origin/fr` on demand, and a preview creates nothing."""
    path = worktree_path(root)
    if not (path / ".git").exists():
        return (
            f"there is no `{QUIET_BRANCH}` worktree yet at {path} (the real run creates it "
            f"from origin/{QUIET_BRANCH} before it reads)"
        )
    return None


def fast_forward(root: Path) -> None:
    """Move the fr worktree up to `origin/fr` when it is strictly behind (never a reset:
    a local `fr` that diverged keeps its commits, and `fr push` replays them)."""
    _fast_forward_linked(root, worktree_path(root), QUIET_BRANCH, paths.MEMORY_REF)


def _fast_forward_linked(root: Path, path: Path, branch: str, tracking: str) -> None:
    if not (path / ".git").exists():
        return
    _check_owner(root, path, branch)
    if _git(path, "rev-parse", "--verify", "--quiet", tracking).returncode != 0:
        return
    behind = _git(path, "merge-base", "--is-ancestor", "HEAD", tracking)
    if behind.returncode == 0:
        _git(path, "merge", "--ff-only", "--quiet", tracking)


def owner_of(fr_root: Path, fid: str) -> str | None:
    """The branch the feature root *fid* records as its owner, or None when unrecorded.

    OWNER is input from whoever can push to the `fr` branch, and it is printed into
    suggested commands (`fr archive --branch <owner>`): text that is no safe branch name
    (`paths.unsafe_branch`: a space, a newline or another control character, a leading
    `-`...) is ignored, with a notice that names the file but never echoes the text
    (lens l-security-r2)."""
    try:
        text = (fr_root / paths.FEATURES_DIR / fid / paths.FEATURE_OWNER).read_text()
    except OSError, UnicodeDecodeError:
        return None
    owner = text.strip()
    if not owner:
        return None
    why = paths.unsafe_branch(owner)
    if why is not None:
        print(
            f"fr: ignoring {paths.FEATURES_DIR}/{fid}/{paths.FEATURE_OWNER}: it does not "
            f"hold a safe branch name ({why})",
            file=sys.stderr,
        )
        return None
    return owner


def check_owner(fr_root: Path, fid: str, branch: str, placement: str = "quiet") -> None:
    """Refuse when *fid*'s feature root is owned by a branch other than *branch*: the id
    is not injective, and the other branch may live only in another clone (p3-r6)."""
    owner = owner_of(fr_root, fid)
    if owner is not None and owner != branch:
        raise SettingsError(
            f"{_where(placement)[0]}: branch {branch!r} has the feature id {fid!r}, whose path "
            f"in {_where(placement)[1]} is owned by {owner!r} "
            f"({paths.FEATURES_DIR}/{fid}/{paths.FEATURE_OWNER}). Rename the branch"
        )


def branch_of(root: Path) -> str | None:
    """The branch a checkout works on: its HEAD, or the marker's branch when detached."""
    branch = head_branch(root)
    if branch is None:
        from fr.isolation.marker import marker_at

        marker = marker_at(root)
        recorded = marker.get("branch") if marker else None
        branch = recorded if isinstance(recorded, str) else None
    return branch


def quiet_space(root: Path, *, create: bool = True) -> paths.ArtifactSpace:
    """The quiet `ArtifactSpace` of the checkout at *root*: the fr worktree, and the
    feature its branch names (none in the fr worktree itself). `create=False` (`fr
    settings paths --no-create`, the hooks' read, review p6-r4) computes the space
    without creating the local `fr` branch or the fr worktree."""
    root = Path(root)
    path = worktree_path(root)
    branch = branch_of(root)
    if branch == QUIET_BRANCH or root.resolve() == path.resolve():
        return paths.ArtifactSpace(paths.QUIET, path, None)
    if branch is None:
        raise SettingsError(
            f"placement quiet: {root} has a detached HEAD and no workspace marker naming "
            "its branch; a quiet feature is named by its branch"
        )
    fid = check_feature_id(root, branch)
    if create:
        ensure_worktree(root)
    check_owner(path, fid, branch)
    return paths.ArtifactSpace(paths.QUIET, path, fid)


LOCK_NAME: Final = "fr-worktree.lock"
"""The fr worktree's lock, in ITS git dir: every workspace of a repo shares one fr
worktree and one index there, so its commits, replays and pushes are serialised."""
LOCK_WAIT_SECONDS: float = 10.0
_LOCK_POLL_S: Final = 0.05


def _fr_git_dir(fr_root: Path) -> Path:
    done = _git(fr_root, "rev-parse", "--absolute-git-dir")
    if done.returncode != 0 or not done.stdout.strip():
        raise SettingsError(
            f"placement quiet: git cannot name the git dir of the `{QUIET_BRANCH}` worktree "
            f"at {fr_root}: {done.stderr.strip()}"
        )
    return Path(done.stdout.strip())


@contextmanager
def fr_worktree_lock(fr_root: Path) -> Iterator[None]:
    """Hold the fr worktree's exclusive lock (review p3-r8), waiting a bounded
    `LOCK_WAIT_SECONDS` for another fr command to release it, then refusing, named."""
    path = _fr_git_dir(fr_root) / LOCK_NAME
    with path.open("a") as handle:
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SettingsError(
                        f"placement quiet: another fr command holds {path} (it is committing "
                        f"or pushing on the shared `{QUIET_BRANCH}` worktree); retry when it "
                        "is done"
                    ) from None
                time.sleep(_LOCK_POLL_S)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def fr_worktree_problem(fr_root: Path, *, dirty: bool = True) -> str | None:
    """Why fr cannot commit or replay on the fr worktree right now, or None: a rebase or
    merge someone left in progress there, or (with *dirty*, for a replay) uncommitted
    changes to tracked files. A pathspec commit is not blocked by unrelated edits."""
    git_dir = _fr_git_dir(fr_root)
    for name, what in (
        ("rebase-merge", "a rebase in progress"),
        ("rebase-apply", "a rebase in progress"),
        ("MERGE_HEAD", "a merge in progress"),
        ("CHERRY_PICK_HEAD", "a cherry-pick in progress"),
    ):
        if (git_dir / name).exists():
            return (
                f"the `{QUIET_BRANCH}` worktree at {fr_root} has {what}; finish or abort it "
                f"there (`git -C {fr_root} rebase --abort`) and retry"
            )
    if not dirty:
        return None
    status = _git(fr_root, "status", "--porcelain", "--untracked-files=no")
    if status.returncode == 0 and status.stdout.strip():
        first = status.stdout.strip().splitlines()[0][3:]
        return (
            f"the `{QUIET_BRANCH}` worktree at {fr_root} has uncommitted changes to tracked "
            f"files ({first}); commit or discard them there and retry"
        )
    return None


def _default_network(root: Path) -> Network:
    def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            return subprocess.run(
                argv,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=_NETWORK_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(argv, 124, "", "timed out")
        except OSError as e:
            return subprocess.CompletedProcess(argv, 127, "", str(e))

    return run


def unreachable(why: str, command: str | None = "fr isolation up") -> SettingsError:
    """The R23 reachability refusal. *command* is the one that refused, whose own
    `--no-fetch` is the remedy; None for a command that has no such flag."""
    remedy = (
        f"; `{command} --no-fetch` reads the last fetched origin/{QUIET_BRANCH} instead"
        if command is not None
        else ""
    )
    return SettingsError(
        f"origin is unreachable ({why}): fr reads the quiet switch (origin/{QUIET_BRANCH}) at "
        "`fr isolation up` and `fr run start` and will not guess the placement without it "
        f"(R23). Check the remote with `git remote -v`{remedy}"
    )


def fetch_switch(
    root: Path,
    *,
    no_fetch: bool = False,
    network: Network | None = None,
    command: str = "fr isolation up",
) -> str:
    """Fetch `origin/fr` and `origin/fr-config` and return the placement the switch names
    (`quiet` or `repo`).

    No `origin` is `repo`, with nothing fetched. `--no-fetch` reads the last fetched refs
    and says so (it is not a reachability check). Otherwise an origin that cannot be
    reached refuses; a branch origin does not have deletes its stale tracking ref, so a
    deleted switch is noticed (the sticky check then refuses in a quiet workspace).

    Under quiet both worktrees are then brought up to their refs: the `fr-config` one
    only when that branch exists (`ensure_config_worktree` adopts it). Entering a
    workspace fetches and never pushes (spec 2026-11-19-event-driven-a-la-carte §B; plan
    decision p2-create-at-init-and-migration): fr creates `fr-config` only at the
    migration and at `fr settings init --quiet`, and until then a configuration read
    refuses, naming both (`fr.config.space.ConfigSpace._missing`)."""
    root = Path(root)
    if not _has_origin(root):
        return paths.REPO
    net = network or _default_network(root)
    if no_fetch:
        print(
            f"fr: --no-fetch: reading the last fetched origin/{CONFIG_BRANCH} and "
            f"origin/{QUIET_BRANCH} for the placement (not a reachability check)",
            file=sys.stderr,
        )
    else:
        _fetch_both(root, net, command)
    placement = paths.QUIET if read_switch(root) is not None else paths.REPO
    if placement == paths.QUIET:
        fast_forward(root)
        ensure_config_worktree(root)
    return placement


_BRANCHES: Final = (
    (QUIET_REF, FETCH_REFSPEC, paths.MEMORY_REF),
    (CONFIG_REF, CONFIG_FETCH_REFSPEC, paths.SWITCH_REF),
)


def _fetch_both(root: Path, net: Network, command: str | None) -> None:
    """One probe, one fetch: the branches origin has are fetched, the tracking ref of a
    branch it does not have is deleted."""
    # `fr` last: callers that recognise the switch probe by its last argument still do
    probe = net(["git", "ls-remote", "--exit-code", "origin", CONFIG_REF, QUIET_REF])
    if probe.returncode not in (0, 2):
        raise unreachable((probe.stderr or probe.stdout or "git ls-remote failed").strip(), command)
    present = {
        line.split("\t", 1)[1].strip()
        for line in (probe.stdout if probe.returncode == 0 else "").splitlines()
        if "\t" in line
    }
    specs = []
    for head, spec, tracking in _BRANCHES:
        if head in present:
            specs.append(spec)
        elif _git(root, "rev-parse", "--verify", "--quiet", tracking).returncode == 0:
            _git(root, "update-ref", "-d", tracking)
    if specs:
        fetched = net(["git", "fetch", "--no-tags", "origin", *specs])
        if fetched.returncode != 0:
            raise unreachable((fetched.stderr or "git fetch failed").strip(), command)


def ensure_config_branch(root: Path, *, network: Network | None = None) -> bool:
    """Create `origin/fr-config` from the old switch when the old one is the only switch
    (S1 R5, R6): one orphan commit whose tree is `.fr/settings.yaml`, holding the old
    root settings.yaml's bytes, pushed with a plain push (never forced). Whether it
    pushed. Nothing to do when `origin/fr-config` already holds settings or there is no
    old switch. Called by `fr settings init --quiet` and the migration only (decision
    p2-create-at-init-and-migration), never on entering a workspace. The rest of `.fr/`
    (the product's `ci.yaml` and the like) moves with `fr migrate artifacts --yes` (R11)."""
    root = Path(root)
    new, old = switch_texts(root)
    if new is not None or old is None:
        return False
    from fr.git_policy.templates import fr_message

    message = fr_message(root, "chore(fr): move the quiet switch to fr-config")
    try:
        write_branch_file(
            root, CONFIG_BRANCH, paths.SWITCH_REF, paths.SWITCH_SETTINGS, old[1], message,
            network=network,
        )  # fmt: skip
    except SettingsError:
        # Another clone may have created it meanwhile: that one stands, if it holds settings.
        _fetch_both(root, network or _default_network(root), None)
        if switch_texts(root)[0] is None:
            raise
        return False
    print(
        f"fr: created origin/{CONFIG_BRANCH} holding {paths.SWITCH_SETTINGS} (the quiet switch, "
        f"copied from origin/{QUIET_BRANCH}:{paths.LEGACY_SWITCH_SETTINGS}; S1 R5)",
        file=sys.stderr,
    )
    return True


Push = Callable[[Path, str], None]
"""Pushes one branch (`fr` or `fr-config`) to origin and fetches its tracking ref."""


def write_switch(
    root: Path,
    text: str,
    message: str,
    *,
    network: Network | None = None,
    push: Push | None = None,
) -> str | None:
    """Write the quiet switch (R5, R6; plan decision p2-config-changes-by-pr).

    When origin has no `fr-config` yet, this is its creation (`fr settings init`, the
    migration): `.fr/settings.yaml` on a new orphan `fr-config`, then the same bytes as
    the root `settings.yaml` on `fr` (`write_legacy`). When `fr-config` already holds
    *text*, only the legacy copy is landed, so a retry after a partial failure converges.
    Any other change to an existing `fr-config` is reviewed: fr opens a pull request from
    `fr-config-change/<slug>` (`fr.config.change.open_change`) and returns its URL; the
    legacy copy follows after the merge (`_settle_differing`).

    The legacy copy is written until the release R14's owed entry names
    (`s1-refuse-old-paths`); that release drops it."""
    root = Path(root)
    net = network or _default_network(root)
    _fetch_both(root, net, None)
    common = paths._common_dir(root)
    exists = common is not None and _ref_sha(common, paths.SWITCH_REF) is not None
    new, _ = switch_texts(root)
    if exists and (new is None or new[1] != text):
        from fr.config.change import open_change

        _check_config_refs(root)
        url = open_change(
            root,
            product=root,
            remote=_git(root, "config", "--get", "remote.origin.url").stdout.strip(),
            base_branch=CONFIG_BRANCH,
            base_ref=paths.SWITCH_REF,
            rel=paths.SWITCH_SETTINGS,
            text=text,
            message=message,
        )
        print(
            f"fr: opened {url}: the change to {paths.SWITCH_SETTINGS} waits for review on "
            f"`{CONFIG_BRANCH}`; once it merges, fr brings the old copy on `{QUIET_BRANCH}` "
            "in step",
            file=sys.stderr,
        )
        _CACHE.clear()
        return url
    if not exists:
        write_branch_file(
            root, CONFIG_BRANCH, paths.SWITCH_REF, paths.SWITCH_SETTINGS, text, message,
            network=net, push=push,
        )  # fmt: skip
    write_legacy(root, text, message, network=net, push=push)
    _CACHE.clear()
    return None


_LEGACY_ATTEMPTS: Final = 3
"""How many times `write_legacy` refetches and retries a push origin refused as not a
fast-forward (another clone pushed to `fr` meanwhile)."""


class _NotFastForwardError(SettingsError):
    """Origin refused a push because its branch moved meanwhile."""


def write_legacy(
    root: Path,
    text: str,
    message: str,
    *,
    network: Network | None = None,
    push: Push | None = None,
) -> None:
    """Make the root `settings.yaml` on `fr` hold *text* (R6), robust against the memory
    branch moving: fetch `fr` immediately before committing, bring the local `fr` onto it
    (fast-forward, or a rebase of fr's own unpushed commits), commit, push; a push refused
    as not a fast-forward is retried a bounded number of times. Nothing is ever forced.
    *push* (`fr placement move`'s own pusher) replaces the plain push; its refusal is not
    retried."""
    root = Path(root)
    net = network or _default_network(root)
    for _ in range(_LEGACY_ATTEMPTS):
        fetched = net(["git", "fetch", "--quiet", "--no-tags", "origin", FETCH_REFSPEC])
        if fetched.returncode != 0:
            probe = net(["git", "ls-remote", "--exit-code", "origin", QUIET_REF])
            if probe.returncode != 2:
                raise unreachable((fetched.stderr or "git fetch failed").strip(), None)
        _onto_memory(root)
        try:
            write_branch_file(
                root, QUIET_BRANCH, paths.MEMORY_REF, paths.LEGACY_SWITCH_SETTINGS, text,
                message, network=net, push=push,
            )  # fmt: skip
            return
        except _NotFastForwardError:
            continue
    raise SettingsError(
        f"placement quiet: origin's `{QUIET_BRANCH}` kept moving while fr wrote the old "
        f"switch ({paths.LEGACY_SWITCH_SETTINGS}); {_LEGACY_ATTEMPTS} attempts were refused "
        "as not fast-forwards. Nothing was forced; run the command again"
    )


def _onto_memory(root: Path) -> None:
    """Bring the local `fr` (its worktree) onto the freshly fetched `origin/fr`: a
    fast-forward when behind, a rebase of fr's own unpushed commits when the two
    diverged. A rebase that stops refuses (and is aborted), never resolved by guessing."""
    common = paths._common_dir(root)
    if common is None or _ref_sha(common, paths.MEMORY_REF) is None:
        return
    if _git(root, "rev-parse", "--verify", "--quiet", QUIET_REF).returncode != 0:
        return
    wt = ensure_worktree(root)
    with fr_worktree_lock(wt):
        if _git(wt, "merge-base", "--is-ancestor", "HEAD", paths.MEMORY_REF).returncode == 0:
            _git(wt, "merge", "--ff-only", "--quiet", paths.MEMORY_REF)
            return
        if _git(wt, "merge-base", "--is-ancestor", paths.MEMORY_REF, "HEAD").returncode == 0:
            return
        done = _git(wt, "rebase", "--quiet", paths.MEMORY_REF)
        if done.returncode != 0:
            _git(wt, "rebase", "--abort")
            raise SettingsError(
                f"placement quiet: the local `{QUIET_BRANCH}` holds unpushed commits that do "
                f"not rebase onto origin/{QUIET_BRANCH} "
                f"({(done.stderr or done.stdout).strip()}); fr refuses rather than guess. "
                f"Inspect them (`git -C {wt} log origin/{QUIET_BRANCH}..HEAD`) and retry"
            )


def write_branch_file(
    root: Path,
    branch: str,
    tracking: str,
    rel: str,
    text: str,
    message: str,
    *,
    network: Network | None = None,
    push: Push | None = None,
) -> None:
    """Make *rel* on origin's *branch* hold *text*: an orphan commit when neither origin
    nor this clone has the branch, else a commit in its worktree; then a plain push and
    a fetch of *tracking*. A push origin refuses raises `SettingsError`, naming it."""
    net = network or _default_network(root)
    common = paths._common_dir(root)
    local = _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}")
    remote = _ref_sha(common, tracking) if common is not None else None
    if branch == CONFIG_BRANCH:
        _check_config_refs(root)  # never adopt, or push, a branch that is not one
    created = None
    if remote is None and local.returncode != 0:
        created = _orphan_commit(root, {rel: text}, message)
        _git(root, "update-ref", f"refs/heads/{branch}", created, "0" * 40)
    else:
        path = worktree_path(root).parent / branch
        wt = _ensure_linked(root, path, branch, tracking)
        _fast_forward_linked(root, wt, branch, tracking)
        with fr_worktree_lock(wt):
            target = wt / rel
            try:
                current = target.read_text()
            except OSError:
                current = None
            if current != text:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
                _git(wt, "add", "--", rel)
                done = _git(wt, "commit", "--quiet", "--no-verify", "-m", message, "--", rel)
                if done.returncode != 0:
                    raise SettingsError(
                        f"placement quiet: cannot commit {rel} on `{branch}`: "
                        f"{(done.stderr or done.stdout).strip()}"
                    )
    head = _git(root, "rev-parse", f"refs/heads/{branch}").stdout.strip()
    if remote == head:
        return
    if push is not None:
        push(root, branch)
        return
    pushed = net(["git", "push", "--quiet", "origin", f"refs/heads/{branch}:refs/heads/{branch}"])
    if pushed.returncode != 0:
        if created is not None:  # never leave an unrelated root behind to be adopted
            _git(root, "update-ref", "-d", f"refs/heads/{branch}", created)
        why = (pushed.stderr or pushed.stdout or "").lower()
        refused = (
            _NotFastForwardError
            if ("non-fast-forward" in why or "fetch first" in why)
            else SettingsError
        )
        raise refused(
            f"placement quiet: origin refused the push of `{branch}` ({rel}): "
            f"{(pushed.stderr or pushed.stdout or 'git push failed').strip()}. Nothing was "
            "forced; fix the remote (or pull its changes) and retry"
        )
    net(["git", "fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{branch}:{tracking}"])


def create_config_branch(
    root: Path,
    files: dict[str, str],
    message: str,
    *,
    network: Network | None = None,
    executable: Collection[str] = (),
) -> None:
    """Create origin's `fr-config` as ONE orphan commit holding *files* (tree path ->
    text), pushed with a plain push (never forced): the migration's creation of the
    configuration space (S1 R10, plan decision p2-create-at-init-and-migration). A push
    origin refuses raises `SettingsError` and leaves no local branch behind. Refuses when
    origin or this clone already has a `fr-config`: a change to an existing one is a pull
    request (`fr.config.change.open_change`)."""
    net = network or _default_network(root)
    common = paths._common_dir(root)
    local = _git(root, "rev-parse", "--verify", "--quiet", f"{CONFIG_REF}^{{commit}}")
    if local.returncode == 0 or (common is not None and _ref_sha(common, paths.SWITCH_REF)):
        raise SettingsError(
            f"placement quiet: `{CONFIG_BRANCH}` exists already; fr changes it only by a pull "
            "request"
        )
    created = _orphan_commit(root, files, message, executable=executable)
    _git(root, "update-ref", CONFIG_REF, created, "0" * 40)
    pushed = net(["git", "push", "--quiet", "origin", f"{CONFIG_REF}:{CONFIG_REF}"])
    if pushed.returncode != 0:
        _git(root, "update-ref", "-d", CONFIG_REF, created)
        raise SettingsError(
            f"placement quiet: origin refused the push of the new `{CONFIG_BRANCH}`: "
            f"{(pushed.stderr or pushed.stdout or 'git push failed').strip()}. Nothing was "
            "forced and nothing was removed from the product"
        )
    net(["git", "fetch", "--quiet", "--no-tags", "origin", CONFIG_FETCH_REFSPEC])


def _orphan_commit(
    root: Path, files: dict[str, str], message: str, *, executable: Collection[str] = ()
) -> str:
    """A parentless commit holding exactly *files* (path -> text), made with plumbing in
    a private index, so no working tree is touched; a path in *executable* is committed
    `100755` (a moved `.fr/candidate-install` stays runnable)."""
    import tempfile

    from fr.git import git_argv

    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}

        def run(*args: str, stdin: str | None = None) -> str:
            done = subprocess.run(
                git_argv(root, *args),
                cwd=root,
                env=env,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=_NETWORK_TIMEOUT_S,
                check=False,
            )
            if done.returncode != 0:
                raise SettingsError(
                    f"placement: `git {' '.join(args)}` failed: {done.stderr.strip()}"
                )
            return done.stdout.strip()

        for rel, text in files.items():
            blob = run("hash-object", "-w", "--stdin", stdin=text)
            mode = "100755" if rel in executable else "100644"
            run("update-index", "--add", "--cacheinfo", f"{mode},{blob},{rel}")
        tree = run("write-tree")
        return run("commit-tree", tree, "-F", "-", stdin=message)
