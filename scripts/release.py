#!/usr/bin/env python3
"""Turn pending change fragments into a bot release on `main`.

    scripts/release.py [--version X.Y.Z] [--dry-run]
    scripts/release.py prepare --out DIR [--version X.Y.Z] [--github-output FILE]
    scripts/release.py materialise --plan FILE --bundle FILE [--pin-base]
    scripts/release.py collect --out FILE
    scripts/release.py test-shard --plan FILE --group N --splits N --durations FILE --out FILE
    scripts/release.py publish --plan FILE --bundle FILE

Spec 2026-09-26-version-bump-churn §3.C, §3.E, §5, and 2026-10-14-exit-gates R20,
R25. Run by `release.yml` on every push to `main`, daily, and by hand through
`workflow_dispatch`.

Release gating (`compute`): while a PR merged since the last FINAL tag
(`vX.Y.Z` exactly) still waits on a post-merge gate (`waiting_prs`: a `gh` read here,
then `fr release status --from-json`, credential-free),
a run cuts a release candidate `vX.Y.Z-rc.N` (no fragment consumed, a GitHub
pre-release), or nothing when nothing merged since the newest RC tag; once nothing
waits, the final `X.Y.Z` consumes the fragments. Versions parse through
`versions.Version`: an RC is `X.Y.ZrcN` on the Python surfaces, `X.Y.Z-rc.N` elsewhere.

1. Fetch and reset to the **tip** of `origin/main`, so a run sees every
   fragment merged before it started.
2. Read `.changes/*.yaml` (`changes.load_pending`; an invalid one refuses the
   release rather than being skipped). The bump is the highest pending one; a
   `--version` override wins and must be above the current version. A version
   whose tag already exists (a manual tag) is bumped past, never re-tagged.
3. Refuse a stale `uv.lock` (`uv lock --check`), run `bump-version.py X.Y.Z`,
   then `fr migrate artifacts --yes` AT the new number (`_run_migrate`), `git rm`
   the fragments, and verify the staged diff touches nothing but
   `version_surfaces()` lines, those fragments and live plans' `fr_version`
   ceilings widened to the new major's (`_plan_ceiling_widened`): the commit is
   pushed with the `GITHUB_TOKEN`, so no CI ever runs on it. A plan's ceiling is
   derived from the installed major, so only the release knows it, and a major
   whose commit skipped the widening left this repo's own plans stale (gh#861).
   A live artifact's stamp moving up (`_stamp_moved_up`) is admitted too: a PR
   tested against a main from before another PR's artifact-version bump merges
   carrying the old stamps, and the release's migration is the first thing to
   see it (the #1058 release, which refused and released nothing).
   Commit `release: vX.Y.Z` as github-actions[bot], the summaries grouped by
   bump in the body.
4. Test the committed tree AT the new version, before the push. The diff check
   proves which lines changed, not how the code behaves at the new number;
   5.0.0 shipped refusing its own plans (gh#854) because the first commit to
   run at 5.0.0 was the untested release commit. A red suite refuses here, with
   `main` and the tags untouched.
5. Push, only if `origin/main` is still the commit the release was staged on.
   When it moved (or the push loses the race) the run is **superseded**: it
   pushes nothing and exits 0, because the push that moved main starts the
   Release run that recomputes from the new tip (spec 2026-11-01-ci-speed
   §3.D, R10). A run carrying `--version` exits non-zero instead, telling the
   operator to re-dispatch it: no later run carries the override. A refusal by
   branch protection still fails at once: the bot needs a bypass actor.
6. If the version has no `v` tag: check the `fr_version` floors changed since
   the previous tag (§3.E), create the annotated tag and the GitHub Release —
   notes are the release commit's body plus `--generate-notes` — and then, on
   a floor mismatch, open an issue and exit `EXIT_FLOOR`. Idempotent: a rerun
   finds the tag, or reads its notes from the release commit that made the
   version (`git log -1 -S<version> -- pyproject.toml`).

With no subcommand, steps 1-6 run in this one process, the suite unsharded (local
use and the unit tests). `release.yml` runs them as a job graph instead (spec
2026-11-01-ci-speed §3.D): `prepare` is steps 1-3 and writes `release-plan.json`
plus `staged.bundle` (or finishes there, `cut=false`, when there is nothing to
release); `collect` and six `test-shard` jobs each `materialise` the staged
commit, pinned to the plan's base, and run step 4 split six ways, credential-free;
`publish` is steps 5-6, after `scripts/split_check.py` proved the shards ran the
whole suite.

`--dry-run` reads the working tree as it is (no fetch, no reset), prints what
it would release, and writes nothing. Stdlib only; the bump, the lock check, the
staged-tree tests and `gh` are injectable (`Commands`) so tests never run real `uv` or `gh`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import changes  # noqa: E402
import floors  # noqa: E402
import version_surfaces as vs  # noqa: E402
from versions import FINAL_RE, FINAL_TAG_RE, RC_TAG_RE, Version  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REMOTE = "origin"
BRANCH = "main"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
RELEASE_PREFIX = "release: v"
GROUP_TITLES = {"major": "Major changes", "minor": "Minor changes", "patch": "Patch changes"}

EXIT_OK = 0
EXIT_REFUSED = 1  # a refusal: invalid input, stale lock, stray diff, protection
EXIT_SUPERSEDED = 2  # main moved under a run carrying --version: re-dispatch it
EXIT_FLOOR = 3  # tagged and released, but a floor names another release

# GH006 is classic branch protection, GH013 a ruleset (what `protect main` is);
# `[remote rejected]` is any server-side decline, which a lost race never is — a
# non-fast-forward is refused client-side as a plain `[rejected]`.
_PROTECTED_MARKERS = (
    "GH006",
    "protected branch",
    "GH013",
    "repository rule violations",
    "[remote rejected]",
)
_RACE_MARKERS = ("non-fast-forward", "fetch first", "[rejected]")


class ReleaseError(Exception):
    """A refusal; the message says why and what to do."""

    def __init__(self, message: str, code: int = EXIT_REFUSED) -> None:
        super().__init__(message)
        self.code = code


# -- injectable commands ----------------------------------------------------


def _run_bump(repo: Path, new: str) -> None:
    subprocess.run(
        [sys.executable, str(repo / "scripts" / "bump-version.py"), new],
        cwd=repo,
        check=True,
        env=_credential_free_env(),  # it runs `uv sync` and the repo's own `fr`
    )


def _run_lock_check(repo: Path) -> str | None:
    r = subprocess.run(
        ["uv", "lock", "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_credential_free_env(),  # resolving runs dependency build code
    )
    return None if r.returncode == 0 else (r.stderr or r.stdout).strip() or "uv lock --check failed"


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def _run_migrate(
    repo: Path, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> str | None:
    """`fr migrate artifacts --yes` in the locked env, i.e. at the bumped number: None when ok.

    At a major this widens every live plan's `fr_version` ceiling; otherwise it
    finds nothing to do. The verb never commits, so its writes ride the release
    commit, where `verify_staged` admits the ceiling lines and nothing else.
    """
    r = run(
        ["uv", "run", "--locked", "fr", "migrate", "artifacts", "--yes"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_credential_free_env(),
    )
    if r.returncode == 0:
        return None
    return "\n".join(f"{r.stdout}\n{r.stderr}".strip().splitlines()[-_TAIL_LINES:])


_FR_VERSION_PROBE = "import importlib.metadata as m; print(m.version('fr'))"
_TAIL_LINES = 30


_AUTH_ENV_VARS = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
    "FR_RELEASE_STATUS_TOKEN",  # release.yml's workflow token for the merged-PR read
)


def _credential_free_env() -> dict[str, str]:
    """The environment minus every forge credential: the staged test run reads none.

    The release token may be a ruleset bypass actor's, so nothing the suite (or
    a test it runs) executes may be able to read it (spec 2026-10-11 §F).
    """
    return {k: v for k, v in os.environ.items() if k not in _AUTH_ENV_VARS}


def _same_version(a: str, b: str) -> bool:
    """*a* and *b* name the same version in either spelling (`X.Y.ZrcN` is `X.Y.Z-rc.N`)."""
    try:
        return Version.parse(a) == Version.parse(b)
    except ValueError:
        return False


def _run_staged_tests(
    repo: Path, new: str, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> str | None:
    """The whole suite, in the locked env, with `fr` installed AT `new`: None when green.

    `uv run --locked` re-syncs the editable members from the bumped
    pyprojects, so the probe should report `new`. It is checked rather than
    assumed: a green suite at the old number is the gh#854 failure again.
    The full suite, not a curated "version-sensitive" subset: that list is
    the kind of literal that goes stale, which is how 5.0.0 broke.
    """
    return _probe_then_pytest(repo, new, [], run)


_UV_LOCKED = ["uv", "run", "--locked"]
# The release's shards and its collect job run with these options and no others, so
# `split_check.py` compares like with like (ci.yml's `collect` and `test` do the same).
SHARD_ADDOPTS = "addopts=--strict-markers"


def _probe_then_pytest(
    repo: Path,
    new: str,
    pytest_args: list[str],
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> str | None:
    """The version probe, then pytest, both credential-free: None when green.

    A probe that reports any number but `new` refuses before pytest runs.
    """
    env = _credential_free_env()
    probe = run(
        [*_UV_LOCKED, "python", "-c", _FR_VERSION_PROBE],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    installed = probe.stdout.strip()
    if probe.returncode != 0 or not _same_version(installed, new):
        return (
            f"the test env runs fr {installed or '(unknown)'}, not {new}; "
            f"refusing to test at the wrong number\n{probe.stderr.strip()}"
        ).strip()
    r = run(
        [*_UV_LOCKED, "pytest", "-q", "--no-cov", "-n", "auto", "-p", "no:cacheprovider"]
        + pytest_args,
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    if r.returncode == 0:
        return None
    return "\n".join(f"{r.stdout}\n{r.stderr}".strip().splitlines()[-_TAIL_LINES:])


def _run_shard_tests(
    repo: Path,
    new: str,
    *,
    group: int,
    splits: int,
    durations: Path,
    out: Path,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str | None:
    """One of the release's shards (spec 2026-11-01-ci-speed §3.D): the probe, then
    group `group` of `splits`, split by the plan's durations file.

    The plan file is copied to `out` first: `--store-durations --clean-durations`
    rewrites the file it splits by, so `out` ends holding exactly the tests this
    shard ran, which `split_check.py` compares with `collect`.
    """
    out.write_text(durations.read_text())
    return _probe_then_pytest(
        repo,
        new,
        [
            "-o",
            SHARD_ADDOPTS,
            "--splits",
            str(splits),
            "--group",
            str(group),
            "--splitting-algorithm",
            "least_duration",
            "--durations-path",
            str(out),
            "--store-durations",
            "--clean-durations",
        ],
        run,
    )


def _run_collect(
    repo: Path, out: Path, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> str | None:
    """What the release's shards must run between them, written to `out`: None when
    collection succeeded."""
    r = run(
        [*_UV_LOCKED, "pytest", "-o", SHARD_ADDOPTS, "--collect-only", "-q"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_credential_free_env(),
    )
    out.write_text(r.stdout)
    if r.returncode == 0:
        return None
    return "\n".join(f"{r.stdout}\n{r.stderr}".strip().splitlines()[-_TAIL_LINES:])


STATUS_SCHEMA = 1
STATUS_TOKEN_VAR = "FR_RELEASE_STATUS_TOKEN"
MERGED_PR_LIMIT = 1000
"""`gh pr list --limit`: a read that returns this many may be truncated, so it refuses."""
MERGED_PR_FIELDS = "number,title,url,mergedAt,headRefName,labels"


def _run_gh_read(args: list[str]) -> subprocess.CompletedProcess[str]:
    """A read-only `gh` call (the merged PRs and their labels). In release.yml it uses
    the workflow token (`FR_RELEASE_STATUS_TOKEN`, pull-requests read), not the app's."""
    env = dict(os.environ)
    if env.get(STATUS_TOKEN_VAR):
        env["GH_TOKEN"] = env[STATUS_TOKEN_VAR]
    return subprocess.run(["gh", *args], capture_output=True, text=True, env=env)


def _run_release_decide(
    repo: Path, facts: Path, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> list[dict[str, object]]:
    """`fr release status --from-json FACTS --json`'s `waiting` (exit-gates R21).

    fr only decides here: release.py already read the forge, so fr runs with no forge
    credential at all (`_credential_free_env`, plus an empty gh config dir so no stored
    login is readable either), the same rule as the staged suite. Any failure refuses:
    an empty answer would cut a final."""
    with tempfile.TemporaryDirectory(prefix="fr-release-gh-") as gh_config:
        env = {**_credential_free_env(), "GH_CONFIG_DIR": gh_config}
        r = run(
            [
                "uv",
                "run",
                "--locked",
                "fr",
                "release",
                "status",
                "--from-json",
                str(facts),
                "--json",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            env=env,
        )
    why = None
    waiting: object = None
    if r.returncode != 0:
        why = (r.stderr or r.stdout).strip() or f"exit {r.returncode}"
    else:
        try:
            doc = json.loads(r.stdout)
        except json.JSONDecodeError as exc:
            doc, why = None, f"not JSON: {exc}"
        if isinstance(doc, dict) and doc.get("schema") == STATUS_SCHEMA:
            waiting = doc.get("waiting")
        if why is None and not isinstance(waiting, list):
            why = f"no schema-{STATUS_SCHEMA} `waiting` list in {r.stdout.strip()[:200]!r}"
    if why is not None:
        raise ReleaseError(
            "`fr release status --from-json` failed, so what still waits on a post-merge "
            f"gate is unknown; refusing to choose between an RC and the final:\n{why}"
        )
    assert isinstance(waiting, list)
    return waiting


@dataclass
class Commands:
    """Everything release.py runs that is not git: swapped out by the tests."""

    bump: Callable[[Path, str], None] = _run_bump
    lock_check: Callable[[Path], str | None] = _run_lock_check
    gh: Callable[[list[str]], subprocess.CompletedProcess[str]] = _run_gh
    test: Callable[[Path, str], str | None] = _run_staged_tests
    migrate: Callable[[Path], str | None] = _run_migrate
    gh_read: Callable[[list[str]], subprocess.CompletedProcess[str]] = _run_gh_read
    decide: Callable[[Path, Path], list[dict[str, object]]] = _run_release_decide


# -- git ---------------------------------------------------------------------


# Authenticates ONE git command through gh's credential helper, which reads
# GH_TOKEN from this process's env. Nothing is persisted: checkout runs with
# persist-credentials: false, so no config file holds the token.
_PUSH_AUTH = ["-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential"]


def _git(
    repo: Path, *args: str, check: bool = True, auth: bool = False
) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *(_PUSH_AUTH if auth else []), *args]
    # Only an authenticated push reads the token (through gh's helper); every other git
    # command runs credential-free.
    env = None if auth else _credential_free_env()
    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


def _out(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout


def _bot(*args: str) -> list[str]:
    return ["-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}", *args]


def sync_to_tip(repo: Path) -> None:
    """The tip of origin/main, and origin's tags exactly (a deleted tag is gone).

    Untracked files are left alone, never cleaned: `git add -A` would stage them
    and `verify_staged` then refuses, which beats deleting a human's work.
    """
    fetch_origin(repo)
    _git(repo, "checkout", "--quiet", "-B", BRANCH, f"{REMOTE}/{BRANCH}")
    _git(repo, "reset", "--quiet", "--hard", f"{REMOTE}/{BRANCH}")


def fetch_origin(repo: Path) -> str:
    """origin's main and its tags exactly (a deleted tag is gone); returns main's sha."""
    _git(repo, "fetch", "--quiet", "--force", "--prune", "--prune-tags", "--tags", REMOTE)
    return _rev(repo, f"refs/remotes/{REMOTE}/{BRANCH}")


def _rev(repo: Path, ref: str) -> str:
    return _out(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def tag_exists(repo: Path, version: str) -> bool:
    ref = f"refs/tags/{Version.parse(version).tag}"
    return _git(repo, "rev-parse", "-q", "--verify", ref, check=False).returncode == 0


def current_version(repo: Path) -> str:
    return next(s.value for s in vs.version_surfaces(repo) if s.file == vs.ROOT_PYPROJECT)


# -- what to release -----------------------------------------------------------


@dataclass
class Plan:
    current: str  # as the root pyproject spells it
    new: str | None  # semver-spelled; None: nothing to release
    bump: str | None
    fragments: list[changes.Fragment] = field(default_factory=list)  # consumed by it
    rc: bool = False
    pending: list[changes.Fragment] = field(default_factory=list)  # every pending one
    why: str = ""  # why there is nothing to release, or why an RC


def _tags(repo: Path, *extra: str) -> list[str]:
    return _out(repo, "tag", "--list", *extra, "v*").split()


def last_final(repo: Path, *, merged: bool = False) -> Version | None:
    """The newest final tag (`^v\\d+\\.\\d+\\.\\d+$` only: an RC tag never is the
    last final), by version; with *merged*, only tags HEAD contains."""
    extra = ("--merged", "HEAD") if merged else ()
    finals = [Version.from_tag(t) for t in _tags(repo, *extra) if FINAL_TAG_RE.match(t)]
    return max(finals) if finals else None


def _rcs_above(repo: Path, base: Version | None) -> list[tuple[Version, str]]:
    """Every RC tag above *base*, oldest version first."""
    rcs = [(Version.from_tag(t), t) for t in _tags(repo) if RC_TAG_RE.match(t)]
    return sorted((v, t) for v, t in rcs if base is None or v > base)


def _merged_since(repo: Path, tag: str) -> bool:
    """Whether HEAD carries any commit *tag* does not."""
    return _out(repo, "rev-list", "--count", f"refs/tags/{tag}..HEAD").strip() != "0"


_PR_SUBJECT_RE = re.compile(r"\(#(\d+)\)\s*$|^Merge pull request #(\d+)\b")


def logged_prs(repo: Path, tag: Version) -> set[int]:
    """The PR numbers `git log <tag>..HEAD` names: a squash merge's `(#N)` subject or a
    merge commit's `Merge pull request #N`; the release bot's own commits are skipped."""
    out = _out(repo, "log", f"refs/tags/{tag.tag}..HEAD", "--format=%an%x00%s")
    numbers: set[int] = set()
    for line in out.splitlines():
        author, _, subject = line.partition("\x00")
        if author == BOT_NAME or subject.startswith(RELEASE_PREFIX):
            continue
        m = _PR_SUBJECT_RE.search(subject)
        if m:
            numbers.add(int(m.group(1) or m.group(2)))
    return numbers


class GateStateUnknownError(Exception):
    """What waits on a post-merge gate cannot be known: the run cuts an RC (R20)."""


def waiting_prs(repo: Path, cmds: Commands) -> list[dict[str, object]]:
    """What still waits on a post-merge gate (exit-gates R20, R21); raises `GateStateUnknownError`.

    release.py does the credentialed forge read itself (`cmds.gh_read`: every PR merged
    into main since the last final tag, with its labels), checks it covers every PR the
    git log names since that tag (the search index lags), writes the facts to a temp
    file and lets fr decide from them credential-free (`cmds.decide`). A failed read, a
    read at its limit, a PR the read misses or a failed decision is `GateStateUnknownError`."""
    tag = last_final(repo)
    since = _out(repo, "log", "-1", "--format=%cI", f"refs/tags/{tag.tag}").strip() if tag else None
    args = ["pr", "list", "--state", "merged", "--base", BRANCH, "--limit", str(MERGED_PR_LIMIT)]
    if since:
        args += ["--search", f"merged:>={since}"]
    args += ["--json", MERGED_PR_FIELDS]
    r = cmds.gh_read(args)
    if r.returncode != 0:
        raise GateStateUnknownError(f"the merged-PR read failed: {(r.stderr or r.stdout).strip()}")
    try:
        prs = json.loads(r.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise GateStateUnknownError(f"`gh pr list` did not return JSON: {exc}") from None
    if not isinstance(prs, list) or not all(isinstance(p, dict) for p in prs):
        raise GateStateUnknownError("`gh pr list` did not return a list of PRs")
    if len(prs) >= MERGED_PR_LIMIT:
        raise GateStateUnknownError(
            f"the merged-PR read returned {len(prs)} PRs, its limit: it may be truncated"
        )
    if tag is not None:
        read = {int(p["number"]) for p in prs if isinstance(p.get("number"), int)}
        missing = sorted(logged_prs(repo, tag) - read)
        if missing:
            names = ", ".join(f"#{n}" for n in missing)
            raise GateStateUnknownError(
                f"the merged-PR read misses {names}, merged since {tag.tag}"
            )
    facts = {"last_final": tag.tag if tag else None, "since": since, "prs": prs}
    with tempfile.TemporaryDirectory(prefix="fr-release-facts-") as tmp:
        path = Path(tmp) / "facts.json"
        path.write_text(json.dumps(facts))
        try:
            return cmds.decide(repo, path)
        except ReleaseError as exc:
            raise GateStateUnknownError(str(exc)) from None


def _final_plan(repo: Path, current: str, override: str, plan: Plan) -> Plan:
    if not FINAL_RE.match(override):
        raise ReleaseError(f"--version {override!r} is not X.Y.Z")
    if Version.parse(override) <= Version.parse(current):
        raise ReleaseError(f"--version {override} must be above the current version {current}")
    if tag_exists(repo, override):
        raise ReleaseError(f"--version {override}: tag v{override} already exists")
    plan.new, plan.fragments = override, plan.pending
    return plan


def compute(repo: Path, override: str | None, cmds: Commands | None = None) -> Plan:
    """The release the working tree asks for (exit-gates R20); raises on an invalid
    fragment or override, or when what waits cannot be read.

    1. Some PR merged since the last final tag still waits on a post-merge gate
       (`waiting_prs`): an RC `X.Y.Z-rc.N` that consumes no fragment, unless nothing
       merged since the newest RC tag; then nothing.
    2. Nothing waits, and HEAD is an RC or fragments are pending: the final `X.Y.Z`,
       consuming the fragments.
    3. Otherwise nothing. `--version` releases exactly that final, ungated.

    `X.Y.Z` is the last final plus the highest pending bump; `N` is one past the
    newest `vX.Y.Z-rc.*`. What waits is asked only when a release is possible.
    """
    cmds = cmds or Commands()
    try:
        fragments = changes.load_pending(repo)
    except changes.FragmentError as exc:
        raise ReleaseError(f"invalid fragment, refusing to release over it — {exc}") from None
    current = current_version(repo)
    head = Version.parse(current)
    bump = changes.aggregate(fragments)
    plan = Plan(current, None, bump, pending=fragments)
    if override is not None:
        return _final_plan(repo, current, override, plan)
    if bump is None and not head.is_rc:
        plan.why = "no pending fragments"
        return plan
    base = last_final(repo)
    if base is None:
        if head.is_rc:
            raise ReleaseError(
                f"HEAD is the RC {head} but no final tag vX.Y.Z exists to base it on"
            )
        base = head
    target = base.bumped(bump) if bump is not None else head.final
    while bump is not None and tag_exists(repo, target.semver):
        target = target.bumped(bump)  # a manual tag: bump past it, never re-tag
    try:
        waiting = waiting_prs(repo, cmds)
        reason = ""
        if waiting:
            numbers = ", ".join(f"#{w.get('number')}" for w in waiting)
            reason = f"{numbers} still wait on a post-merge gate"
    except (
        GateStateUnknownError
    ) as exc:  # R20: an unknown gate state degrades to an RC, never a final
        reason = f"what waits on a post-merge gate is unknown ({exc})"
    if not reason:
        plan.new, plan.fragments = target.semver, fragments
        return _not_backwards(plan, head)
    rcs = _rcs_above(repo, base)
    if rcs and not _merged_since(repo, rcs[-1][1]):
        plan.why = f"{reason}, and nothing merged since {rcs[-1][1]}"
        return plan
    n = 1 + max((v.rc or 0 for v, _ in rcs if v.final == target), default=0)
    plan.new, plan.rc, plan.why = target.with_rc(n).semver, True, reason
    return _not_backwards(plan, head)


def _not_backwards(plan: Plan, head: Version) -> Plan:
    """A release never moves the version backwards, or re-cuts HEAD's own (p7-r1, r6):
    a computed version at or below HEAD's releases nothing, and `finish` then tags HEAD
    if its tag is missing (a failed tag push)."""
    assert plan.new is not None
    if Version.parse(plan.new) > head:
        return plan
    plan.why = (
        f"the computed release {plan.new} is not above HEAD's {head.semver} "
        "(a fragment removed since HEAD's RC, or HEAD's tag push failed); "
        "releasing nothing new"
    )
    plan.new, plan.rc, plan.fragments = None, False, []
    return plan


def commit_body(fragments: list[changes.Fragment]) -> str:
    """Every summary, grouped by bump (major first)."""
    groups: list[str] = []
    for bump in reversed(changes.BUMPS):
        summaries = [f.summary for f in fragments if f.bump == bump]
        if summaries:
            groups.append("\n".join([f"{GROUP_TITLES[bump]}:", *(f"- {s}" for s in summaries)]))
    return "\n\n".join(groups)


# -- the release commit ----------------------------------------------------------


LIVE_PLAN_META_RE = re.compile(r"^docs/superpowers/plans/[^/]+/_meta\.yaml$")
"""A live plan's `_meta.yaml`; `implemented/` archives are frozen, never migrated."""

_FR_VERSION_LINE_RE = re.compile(
    r"^(?P<lead>fr_version\s*:\s*)(?P<q>['\"]?)(?P<value>[^'\"#\n]*)(?P=q)(?P<trail>[ \t]*)$"
)


def _plan_ceiling_widened(removed: list[str], added: list[str], new: str) -> bool:
    """One `fr_version` line whose only change is its ceiling becoming `<{new major + 1}.0.0`.

    The shape `fr.artifacts.fr_version.widen` writes, which this stdlib script
    cannot import: same key, quoting and floor, the `<`/`<=` bound replaced.
    """
    if len(removed) != 1 or len(added) != 1:
        return False
    before, after = _FR_VERSION_LINE_RE.match(removed[0]), _FR_VERSION_LINE_RE.match(added[0])
    if before is None or after is None:
        return False
    if any(before.group(g) != after.group(g) for g in ("lead", "q", "trail")):
        return False
    top = Version.parse(new).major + 1
    ceiling = f"<{top}.0.0"
    # Whitespace-free pieces: the repair re-joins with "," and writes each kept
    # specifier as `str(Specifier(p))`, which drops inner spaces (`>= 4.20`).
    old_specs = [re.sub(r"\s+", "", s) for s in before.group("value").split(",") if s.strip()]
    new_specs = [re.sub(r"\s+", "", s) for s in after.group("value").split(",") if s.strip()]
    bounds = [s.lstrip("<=") for s in old_specs if s.startswith("<")]
    if not bounds or any(_major_of(b) is None or _major_of(b) >= top for b in bounds):
        return False  # only a ceiling BELOW the new one widens; never a narrowing
    widened = [ceiling if s.startswith("<") else s for s in old_specs]
    return new_specs == widened


LIVE_ARTIFACT_RE = re.compile(
    r"^(?!.*(?:^|/)implemented/)"
    r"(?:docs/superpowers/(?:runs/[^/]+\.yaml|runs/[^/]+\.records/[^/]+\.yaml"
    r"|usage/[^/]+\.yaml|journals/.+\.md)"
    r"|docs/acceptance/matrix\.yaml)$"
)
"""Live artifacts whose stamp a release may move: `fr.artifacts.registry`'s run,
record, usage, journal and matrix locators. Plans have their own ceiling rule;
specs (`fr_schema:` front matter) and `.devcontainer/fr-profiles.yaml` carry their
stamp elsewhere and are left out, so their migrations still refuse. No path under
an `implemented/` segment matches: archives are frozen."""

_YAML_STAMP_RE = re.compile(r"^schema_version: (\d+)$")
_JOURNAL_STAMP_RE = re.compile(r"^<!--[ \t]*fr:journal-schema=(\d+)[ \t]*-->[ \t]*$")
_YAML_HEADER_RE = re.compile(r"^(?:---\s*|#.*|\s*)$")


def _stamp_moved_up(path: str, removed: list[str], added: list[str], staged: str) -> bool:
    """The whole change is the artifact's own stamp moving up, or a missing one inserted,
    where `fr`'s stamp writer puts it.

    A PR that merged after another PR moved an artifact's version carries its live
    artifacts at the old stamp; the release's own migration rewrites exactly that
    line. The carrier follows the path (a journal's header comment, else a top-level
    `schema_version:`), the staged file must hold exactly one stamp, and it must sit
    in the header: a journal's first non-blank line, or a YAML file's lines before
    its first key. Anything else (a body line, a stamp moving down, a duplicate)
    refuses."""
    rx = _JOURNAL_STAMP_RE if path.endswith(".md") else _YAML_STAMP_RE
    if len(added) != 1 or len(removed) > 1:
        return False
    new = rx.match(added[0])
    if new is None:
        return False
    if removed:
        old = rx.match(removed[0])
        if old is None or int(new.group(1)) <= int(old.group(1)):
            return False
    lines = staged.split("\n")
    if sum(1 for line in lines if rx.match(line.rstrip("\r"))) != 1:
        return False
    for line in lines:
        line = line.rstrip("\r")
        if rx.match(line):
            return True
        if path.endswith(".md") and line.strip():
            return False
        if not path.endswith(".md") and not _YAML_HEADER_RE.match(line):
            return False
    return False


def _major_of(bound: str) -> int | None:
    match = re.match(r"\d+", bound)
    return int(match.group()) if match else None


def verify_staged(repo: Path, old: str, new: str, fragments: list[changes.Fragment]) -> None:
    """The staged diff is only version values moving `old` -> `new`, removed fragments,
    and live plans' `fr_version` ceilings widened to `new`'s major."""
    consumed = {f.path.relative_to(repo).as_posix() for f in fragments}
    per_file: dict[str, int] = {}
    for s in vs.version_surfaces(repo):
        per_file[s.file] = per_file.get(s.file, 0) + 1
    bad: list[str] = []
    for line in _out(repo, "diff", "--cached", "--name-status", "--no-renames").splitlines():
        status, path = line.split("\t", 1)
        if path in consumed and status == "D":
            continue
        # `split("\n")`, never `splitlines()`: that also breaks on \x85, U+2028 and
        # friends, leaving the rest of a changed line unprefixed and so unchecked.
        diff = [
            d.rstrip("\r") for d in _out(repo, "diff", "--cached", "-U0", "--", path).split("\n")
        ]
        removed = [d[1:] for d in diff if d.startswith("-") and not d.startswith("---")]
        added = [d[1:] for d in diff if d.startswith("+") and not d.startswith("+++")]
        if path not in per_file and LIVE_PLAN_META_RE.match(path) and status == "M":
            if not _plan_ceiling_widened(removed, added, new):
                bad.append(f"{path} (a plan line other than its fr_version ceiling)")
            continue
        if path not in per_file and LIVE_ARTIFACT_RE.match(path) and status == "M":
            staged = _out(repo, "show", f":{path}")
            if not _stamp_moved_up(path, removed, added, staged):
                bad.append(f"{path} (a line other than its artifact stamp)")
            continue
        if path not in per_file or status != "M":
            bad.append(f"{path} ({status})")
            continue
        # Each surface in its own spelling: PEP 440 `X.Y.ZrcN` on a Python one (R25).
        was, now = vs.spelling(path, old), vs.spelling(path, new)
        if (
            len(added) != per_file[path]
            or [r.replace(was, now) for r in removed] != added
            or any(was not in r for r in removed)
        ):
            bad.append(f"{path} (a line other than its version value)")
    if bad:
        raise ReleaseError(
            "the release commit may carry only version values, consumed fragments, "
            "widened live-plan ceilings and live-artifact stamps moving up "
            "(no CI runs on it); refusing — staged outside that set:\n"
            + "\n".join(f"  - {b}" for b in bad)
        )


def make_release_commit(repo: Path, plan: Plan, cmds: Commands) -> None:
    assert plan.new is not None
    stale = cmds.lock_check(repo)
    if stale is not None:
        raise ReleaseError(
            f"uv.lock is stale, refusing to release (a re-resolve would ride a commit no CI runs): "
            f"{stale}\n  fix: run `uv lock` in a PR"
        )
    cmds.bump(repo, plan.new)
    failure = cmds.migrate(repo)
    if failure is not None:
        raise ReleaseError(
            f"`fr migrate artifacts --yes` failed at {plan.new}, refusing to release a tree "
            f"whose own artifacts are stale (main and the tags are untouched):\n{failure}\n"
            f"  fix: land a PR that makes these artifacts migratable; the next push to main "
            f"retries the release"
        )
    for f in plan.fragments:
        _git(repo, "rm", "--quiet", "--", f.path.relative_to(repo).as_posix())
    _git(repo, "add", "-A")
    verify_staged(repo, plan.current, plan.new, plan.fragments)
    message = [f"{RELEASE_PREFIX}{plan.new}"]
    body = commit_body(plan.fragments)
    if plan.rc:  # an RC consumes nothing; its notes name what it previews
        lead = f"Release candidate: {plan.why}."
        pending = commit_body(plan.pending)
        body = f"{lead}\n\n{pending}" if pending else lead
    if body:
        message += ["-m", body]
    _git(repo, *_bot("commit", "--quiet", "--cleanup=verbatim", "-m", *message))


def push(repo: Path) -> str:
    """Push HEAD to main: 'ok', 'race', or raise on a protection refusal / other error."""
    r = _git(
        repo, "push", "--porcelain", REMOTE, f"HEAD:refs/heads/{BRANCH}", check=False, auth=True
    )
    if r.returncode == 0:
        return "ok"
    reply = f"{r.stdout}\n{r.stderr}"
    if any(m.lower() in reply.lower() for m in _PROTECTED_MARKERS):
        raise ReleaseError(
            "the push to main was refused by branch protection, not lost to a race: "
            "the release bot needs a bypass actor on main's rules "
            "(Settings > Rules > protect main > Bypass list): the derio-fr-automation "
            "app, which pushes when the repo variable FR_AUTOMATION_APP_ID is set "
            "(scripts/configure-main-protection.sh --stage bypass does both).\n" + reply.strip()
        )
    if any(m in reply for m in _RACE_MARKERS):
        return "race"
    raise ReleaseError(f"git push failed:\n{reply.strip()}")


def check_staged_suite(repo: Path, new: str, cmds: Commands) -> None:
    """Refuse the release when the suite is red at `new`; the commit is still local."""
    print(f"testing the staged tree at {new} before the push")
    failure = cmds.test(repo, new)
    if failure is not None:
        raise ReleaseError(
            f"the suite is red at {new}; refusing to push, tag or publish "
            f"(main and the tags are untouched):\n{failure}\n"
            f"  fix: land a PR that makes the suite pass at {new}; the next push to main "
            f"retries the release"
        )


PLAN_FILE = "release-plan.json"
BUNDLE_FILE = "staged.bundle"


@dataclass
class Staged:
    """A staged release commit, handed from `prepare` to the jobs that test and push it."""

    version: str
    rc: bool
    override: str | None
    base_sha: str  # origin/main when the release was staged: the only commit it may land on
    staged_sha: str  # the release commit; every shard tests exactly this
    fragments: list[str]  # repo-relative, consumed by it

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def read(cls, path: Path) -> Staged:
        try:
            return cls(**json.loads(path.read_text()))
        except (OSError, ValueError, TypeError) as exc:
            raise ReleaseError(f"cannot read the release plan {path}: {exc}") from None


def prepare(
    repo: Path, override: str | None, cmds: Commands, out: Path | None = None
) -> Staged | None:
    """Steps 1-3: the release commit, staged locally and never pushed; None when there
    is nothing to release. With `out`, writes the plan and the bundle the other jobs
    materialise (spec 2026-11-01-ci-speed §3.D)."""
    sync_to_tip(repo)
    base = _rev(repo, "HEAD")
    plan = compute(repo, override, cmds)
    if plan.new is None:
        if plan.why:
            print(f"nothing to release: {plan.why}")
        return None
    if plan.rc:
        print(f"release candidate: {plan.why}")
    make_release_commit(repo, plan, cmds)
    staged = Staged(
        version=plan.new,
        rc=plan.rc,
        override=override,
        base_sha=base,
        staged_sha=_rev(repo, "HEAD"),
        fragments=[f.path.relative_to(repo).as_posix() for f in plan.fragments],
    )
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        staged.write(out / PLAN_FILE)
        bundle = out / BUNDLE_FILE
        _git(repo, "bundle", "create", "--quiet", str(bundle), f"{base}..refs/heads/{BRANCH}")
    print(f"staged {RELEASE_PREFIX}{staged.version} at {staged.staged_sha} on {base}")
    return staged


def materialise(repo: Path, staged: Staged, bundle: Path, *, pin_base: bool) -> None:
    """Check out the staged commit from the bundle, refusing any other commit; with
    `pin_base`, point `origin/main` at the plan's base so tests reading it (the
    unarchived-plans tripwire) judge the base the release pushes onto."""
    _git(repo, "fetch", "--quiet", str(bundle), f"refs/heads/{BRANCH}")
    head = _rev(repo, "FETCH_HEAD")
    if head != staged.staged_sha:
        raise ReleaseError(
            f"the bundle's head {head} is not the plan's staged_sha {staged.staged_sha}; "
            "refusing to test or push a commit the release did not stage"
        )
    _git(repo, "checkout", "--quiet", "--detach", staged.staged_sha)
    if pin_base:
        _git(repo, "update-ref", f"refs/remotes/{REMOTE}/{BRANCH}", staged.base_sha)
    print(f"materialised {staged.staged_sha} (base {staged.base_sha})")


def _superseded(staged: Staged, tip: str) -> int:
    """R10: main moved, so a later run releases from the new tip; nothing is pushed."""
    print(f"superseded: main moved to {tip}")
    if staged.override is None:
        return EXIT_OK
    raise ReleaseError(
        f"superseded: main moved to {tip} under the release of --version "
        f"{staged.override}, and no later run carries the override\n"
        f"  re-dispatch: gh workflow run release.yml -f version={staged.override}",
        EXIT_SUPERSEDED,
    )


def publish(repo: Path, staged: Staged, cmds: Commands) -> int:
    """Steps 5-6 for the commit checked out at HEAD: push it only onto the base it
    was staged on, then tag and release it. A protection refusal raises (`push`)."""
    tip = fetch_origin(repo)
    if tip != staged.base_sha:
        return _superseded(staged, tip)
    if push(repo) == "race":
        return _superseded(staged, fetch_origin(repo))
    kind = "an RC, no fragment consumed" if staged.rc else f"{len(staged.fragments)} fragment(s)"
    print(f"pushed {RELEASE_PREFIX}{staged.version} ({kind})")
    return finish(repo, cmds)


def release_to_main(repo: Path, override: str | None, cmds: Commands) -> int:
    """Steps 1-6 in one process: prepare, one unsharded suite, publish."""
    staged = prepare(repo, override, cmds)
    if staged is None:
        return finish(repo, cmds)
    check_staged_suite(repo, staged.version, cmds)
    return publish(repo, staged, cmds)


# -- tag, notes, floors ----------------------------------------------------------


def release_notes(repo: Path, version: str) -> str:
    """The body of the `release: vX.Y.Z[-rc.N]` commit that made `version`, or '' if none
    did. Found by its exact subject: an RC and its final share the `X.Y.Z` substring."""
    subject = f"{RELEASE_PREFIX}{Version.parse(version).semver}"
    log = _out(repo, "log", "--fixed-strings", f"--grep={subject}", "--format=%s%x00%b%x1e")
    for entry in log.split("\x1e"):
        found, _, body = entry.strip("\n").partition("\x00")
        if found.strip() == subject:
            return body.strip()
    return ""


def previous_tag(repo: Path) -> str | None:
    """The newest FINAL tag HEAD contains (`^v\\d+\\.\\d+\\.\\d+$`); RC tags never count."""
    found = last_final(repo, merged=True)
    return found.tag if found is not None else None


def floor_mismatches(repo: Path, version: str) -> list[str]:
    """§3.E: every floor added since the previous final tag newer than it must name
    `version`, a final: at an RC, the final it precedes (R26 lets the RC through)."""
    prev = previous_tag(repo)
    if prev is None:
        return []
    base = prev.removeprefix("v")
    changed = _out(repo, "diff", "--name-only", "--no-renames", prev, "HEAD").splitlines()
    bad: list[str] = []
    for path in changed:
        if not floors.is_floor_path(path) or not (repo / path).exists():
            continue
        before = _git(repo, "show", f"{prev}:{path}", check=False)
        old = before.stdout if before.returncode == 0 else None
        for floor in floors.new_floors(old, (repo / path).read_text()):
            if not floors.lower_bound_ok(floor.lower, base, version):
                bad.append(f"{path}:{floor.line}: >={floor.lower} should be >={version}")
    return bad


def tag_and_release(repo: Path, version: str, cmds: Commands) -> None:
    """The annotated tag and the GitHub Release, exactly as auto-tag.yml made them; an RC
    is published as a GitHub pre-release (R20)."""
    tag = Version.parse(version).tag
    _git(repo, *_bot("tag", "-a", tag, "-m", tag))
    _git(repo, "push", "--quiet", REMOTE, f"refs/tags/{tag}", auth=True)
    args = ["release", "create", tag, "--title", tag]
    notes = release_notes(repo, version)
    if notes:
        args += ["--notes", notes]
    if Version.parse(version).is_rc:
        args.append("--prerelease")
    args += ["--generate-notes", "--target", _out(repo, "rev-parse", "HEAD").strip()]
    r = cmds.gh(args)
    if r.returncode != 0:
        raise ReleaseError(f"gh release create {tag} failed: {r.stderr.strip()}")
    print(f"tagged and released {tag}")


def file_floor_issue(version: str, bad: list[str], cmds: Commands) -> None:
    title = f"release v{version}: an fr_version floor names a different release"
    body = "\n".join(
        [
            f"`release.py` tagged v{version}, but these floors, added since the previous "
            "tag, name an unreleased version other than the one that shipped them:",
            "",
            *(f"- `{b}`" for b in bad),
            "",
            f"Fix: a patch PR setting each lower bound to `>={version}` "
            "(spec 2026-09-26-version-bump-churn §3.E).",
        ]
    )
    r = cmds.gh(["issue", "create", "--title", title, "--body", body])
    if r.returncode != 0:
        print(f"could not open the floor issue: {r.stderr.strip()}", file=sys.stderr)


def finish(repo: Path, cmds: Commands) -> int:
    """Step 6: tag the current version if it is untagged; the floor check rides along."""
    version = Version.parse(current_version(repo)).semver
    if tag_exists(repo, version):
        print(f"v{version} is already tagged; nothing to do")
        return EXIT_OK
    bad = floor_mismatches(repo, Version.parse(version).final.semver)
    tag_and_release(repo, version, cmds)  # the number is right, so it tags regardless
    if not bad:
        return EXIT_OK
    file_floor_issue(version, bad, cmds)
    print("ERROR: fr_version floor mismatch at release:", file=sys.stderr)
    for b in bad:
        print(f"  - {b}", file=sys.stderr)
    return EXIT_FLOOR


# -- entry -------------------------------------------------------------------------


def dry_run(repo: Path, override: str | None, cmds: Commands) -> int:
    plan = compute(repo, override, cmds)
    if plan.new is None:
        tagged = "tagged" if tag_exists(repo, plan.current) else "untagged — would tag it"
        print(
            f"nothing to release ({plan.why or 'no pending fragments'}); {plan.current} is {tagged}"
        )
        return EXIT_OK
    if plan.rc:
        print(
            f"would cut the RC {plan.current} -> {plan.new} ({plan.why}); "
            f"{len(plan.pending)} fragment(s) stay pending:"
        )
        for f in plan.pending:
            print(f"  - {f.path.name}: {f.bump}: {f.summary}")
        return EXIT_OK
    how = f"override {override}" if override else f"{plan.bump or 'no'} bump"
    print(
        f"would release {plan.current} -> {plan.new} ({how}) "
        f"from {len(plan.fragments)} fragment(s):"
    )
    for f in plan.fragments:
        print(f"  - {f.path.name}: {f.bump}: {f.summary}")
    return EXIT_OK


def _github_output(path: Path | None, **values: str) -> None:
    if path is not None:
        with path.open("a") as fh:
            fh.writelines(f"{k}={v}\n" for k, v in values.items())


def _run_subcommand(args: argparse.Namespace, repo: Path, cmds: Commands) -> int:
    if args.cmd == "prepare":
        out = Path(args.out)
        staged = prepare(repo, args.version or None, cmds, out)
        if staged is None:
            _github_output(args.github_output, cut="false")
            return finish(repo, cmds)  # an untagged RC at HEAD is tagged here
        _github_output(
            args.github_output,
            cut="true",
            base_sha=staged.base_sha,
            staged_sha=staged.staged_sha,
            version=staged.version,
        )
        return EXIT_OK
    if args.cmd == "collect":
        failure = _run_collect(repo, Path(args.out))
        if failure is not None:
            raise ReleaseError(f"collection failed:\n{failure}")
        return EXIT_OK
    staged = Staged.read(Path(args.plan))
    if args.cmd == "materialise":
        materialise(repo, staged, Path(args.bundle), pin_base=args.pin_base)
        return EXIT_OK
    if args.cmd == "test-shard":
        print(f"testing shard {args.group}/{args.splits} of {staged.staged_sha}")
        failure = _run_shard_tests(
            repo,
            staged.version,
            group=args.group,
            splits=args.splits,
            durations=Path(args.durations),
            out=Path(args.out),
        )
        if failure is not None:
            raise ReleaseError(
                f"shard {args.group}/{args.splits} is red at {staged.version}; nothing is "
                f"pushed, tagged or published:\n{failure}"
            )
        return EXIT_OK
    assert args.cmd == "publish"
    materialise(repo, staged, Path(args.bundle), pin_base=False)
    return publish(repo, staged, cmds)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--version", default=None, help="release exactly this X.Y.Z")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("prepare", help="steps 1-3: stage the release commit, plan and bundle")
    p.add_argument("--out", required=True, help="directory for the plan and the bundle")
    p.add_argument("--version", default=argparse.SUPPRESS, help="release exactly this X.Y.Z")
    p.add_argument("--github-output", type=Path, default=None, help="append cut=... here")
    m = sub.add_parser("materialise", help="check out the staged commit from the bundle")
    m.add_argument("--plan", required=True)
    m.add_argument("--bundle", required=True)
    m.add_argument("--pin-base", action="store_true", help="pin origin/main to the base")
    c = sub.add_parser("collect", help="list the tests the shards must run")
    c.add_argument("--out", required=True)
    t = sub.add_parser("test-shard", help="step 4 for one shard: probe, then the split")
    t.add_argument("--plan", required=True)
    t.add_argument("--group", type=int, required=True)
    t.add_argument("--splits", type=int, required=True)
    t.add_argument("--durations", required=True, help="the run's one durations plan")
    t.add_argument("--out", required=True, help="this shard's measured durations")
    u = sub.add_parser("publish", help="steps 5-6: push onto the base, tag, release")
    u.add_argument("--plan", required=True)
    u.add_argument("--bundle", required=True)
    return parser


def main(
    argv: list[str] | None = None, repo: Path | None = None, commands: Commands | None = None
) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    repo = Path(repo or REPO)
    cmds = commands or Commands()
    try:
        if args.cmd is not None:
            return _run_subcommand(args, repo, cmds)
        if args.dry_run:
            return dry_run(repo, args.version or None, cmds)
        return release_to_main(repo, args.version or None, cmds)
    except ReleaseError as exc:
        phase = f"{args.cmd}: " if args.cmd else ""
        print(f"ERROR: {phase}{exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
