#!/usr/bin/env python3
"""Turn pending change fragments into a bot release on `main`.

    scripts/release.py [--version X.Y.Z] [--dry-run]

Spec 2026-09-26-version-bump-churn §3.C, §3.E, §5. Run by `release.yml` on
every push to `main` (and by hand through `workflow_dispatch`):

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
4. Test the committed tree AT the new version (`_run_staged_tests`), before the
   push. The diff check proves which lines changed, not how the code behaves
   at the new number; 5.0.0 shipped refusing its own plans (gh#854) because
   the first commit to run at 5.0.0 was the untested release commit. A red
   suite refuses here, with `main` and the tags untouched.
5. Push. A non-fast-forward fetches, resets and recomputes from scratch (up to
   3 attempts) — never a rebase, the newer main may carry more fragments. A
   refusal by branch protection fails at once: the bot needs a bypass actor.
6. If the version has no `v` tag: check the `fr_version` floors changed since
   the previous tag (§3.E), create the annotated tag and the GitHub Release —
   notes are the release commit's body plus `--generate-notes` — and then, on
   a floor mismatch, open an issue and exit `EXIT_FLOOR`. Idempotent: a rerun
   finds the tag, or reads its notes from the release commit that made the
   version (`git log -1 -S<version> -- pyproject.toml`).

`--dry-run` reads the working tree as it is (no fetch, no reset), prints what
it would release, and writes nothing. Stdlib only; the bump, the lock check, the
staged-tree tests and `gh` are injectable (`Commands`) so tests never run real `uv` or `gh`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import changes  # noqa: E402
import floors  # noqa: E402
import version_surfaces as vs  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REMOTE = "origin"
BRANCH = "main"
MAX_ATTEMPTS = 3
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
RELEASE_PREFIX = "release: v"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
GROUP_TITLES = {"major": "Major changes", "minor": "Minor changes", "patch": "Patch changes"}

EXIT_OK = 0
EXIT_REFUSED = 1  # a refusal: invalid input, stale lock, stray diff, protection
EXIT_RACE = 2  # lost the push race MAX_ATTEMPTS times; the next push retries
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
        [sys.executable, str(repo / "scripts" / "bump-version.py"), new], cwd=repo, check=True
    )


def _run_lock_check(repo: Path) -> str | None:
    r = subprocess.run(["uv", "lock", "--check"], cwd=repo, capture_output=True, text=True)
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
    )
    if r.returncode == 0:
        return None
    return "\n".join(f"{r.stdout}\n{r.stderr}".strip().splitlines()[-_TAIL_LINES:])


_FR_VERSION_PROBE = "import importlib.metadata as m; print(m.version('fr'))"
_TAIL_LINES = 30


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
    uv = ["uv", "run", "--locked"]
    probe = run([*uv, "python", "-c", _FR_VERSION_PROBE], cwd=repo, capture_output=True, text=True)
    installed = probe.stdout.strip()
    if probe.returncode != 0 or installed != new:
        return (
            f"the test env runs fr {installed or '(unknown)'}, not {new}; "
            f"refusing to test at the wrong number\n{probe.stderr.strip()}"
        ).strip()
    r = run(
        [*uv, "pytest", "-q", "--no-cov", "-n", "auto", "-p", "no:cacheprovider"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return None
    return "\n".join(f"{r.stdout}\n{r.stderr}".strip().splitlines()[-_TAIL_LINES:])


@dataclass
class Commands:
    """Everything release.py runs that is not git: swapped out by the tests."""

    bump: Callable[[Path, str], None] = _run_bump
    lock_check: Callable[[Path], str | None] = _run_lock_check
    gh: Callable[[list[str]], subprocess.CompletedProcess[str]] = _run_gh
    test: Callable[[Path, str], str | None] = _run_staged_tests
    migrate: Callable[[Path], str | None] = _run_migrate


# -- git ---------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
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
    _git(repo, "fetch", "--quiet", "--force", "--prune", "--prune-tags", "--tags", REMOTE)
    _git(repo, "checkout", "--quiet", "-B", BRANCH, f"{REMOTE}/{BRANCH}")
    _git(repo, "reset", "--quiet", "--hard", f"{REMOTE}/{BRANCH}")


def tag_exists(repo: Path, version: str) -> bool:
    ref = f"refs/tags/v{version}"
    return _git(repo, "rev-parse", "-q", "--verify", ref, check=False).returncode == 0


def current_version(repo: Path) -> str:
    return next(s.value for s in vs.version_surfaces(repo) if s.file == vs.ROOT_PYPROJECT)


# -- what to release -----------------------------------------------------------


@dataclass
class Plan:
    current: str
    new: str | None  # None: nothing to release
    bump: str | None
    fragments: list[changes.Fragment] = field(default_factory=list)


def _vtuple(version: str) -> tuple[int, ...]:
    return floors.parse_version(version)


def compute(repo: Path, override: str | None) -> Plan:
    """The release the working tree asks for; raises on an invalid fragment or override."""
    try:
        fragments = changes.load_pending(repo)
    except changes.FragmentError as exc:
        raise ReleaseError(f"invalid fragment, refusing to release over it — {exc}") from None
    current = current_version(repo)
    bump = changes.aggregate(fragments)
    if override is not None:
        if not SEMVER_RE.match(override):
            raise ReleaseError(f"--version {override!r} is not X.Y.Z")
        if _vtuple(override) <= _vtuple(current):
            raise ReleaseError(f"--version {override} must be above the current version {current}")
        if tag_exists(repo, override):
            raise ReleaseError(f"--version {override}: tag v{override} already exists")
        return Plan(current, override, bump, fragments)
    if bump is None:
        return Plan(current, None, None, fragments)
    new = changes.bumped(current, bump)
    while tag_exists(repo, new):  # a manual tag: bump past it, never re-tag
        new = changes.bumped(new, bump)
    return Plan(current, new, bump, fragments)


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
    top = _vtuple(new)[0] + 1
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
    r"^(?:docs/superpowers/(?:runs/[^/]+\.yaml|usage/[^/]+\.yaml|journals/.+\.md)"
    r"|docs/acceptance/matrix\.yaml)$"
)
"""Live artifacts whose stamp a release may move (`fr.artifacts.registry`'s locators,
minus plans, which have their own ceiling rule). `implemented/` never matches."""

_STAMP_LINE_RES = (
    re.compile(r"^schema_version: (\d+)$"),
    re.compile(r"^<!--[ \t]*fr:journal-schema=(\d+)[ \t]*-->[ \t]*$"),
)


def _stamp_of(line: str) -> tuple[int, int] | None:
    """`(carrier, version)` when `line` is an artifact stamp, else None."""
    for carrier, rx in enumerate(_STAMP_LINE_RES):
        m = rx.match(line)
        if m:
            return carrier, int(m.group(1))
    return None


def _stamp_moved_up(removed: list[str], added: list[str]) -> bool:
    """The whole change is one stamp line moving up, or one missing stamp inserted.

    A PR that merged after another PR moved an artifact's version carries its live
    artifacts at the old stamp; the release's own migration rewrites exactly that
    line. Anything else (a body line, a stamp moving down) is not mechanical and
    still refuses."""
    if len(added) != 1 or len(removed) > 1:
        return False
    new = _stamp_of(added[0])
    if new is None:
        return False
    if not removed:
        return True
    old = _stamp_of(removed[0])
    return old is not None and old[0] == new[0] and new[1] > old[1]


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
        diff = _out(repo, "diff", "--cached", "-U0", "--", path).splitlines()
        removed = [d[1:] for d in diff if d.startswith("-") and not d.startswith("---")]
        added = [d[1:] for d in diff if d.startswith("+") and not d.startswith("+++")]
        if path not in per_file and LIVE_PLAN_META_RE.match(path) and status == "M":
            if not _plan_ceiling_widened(removed, added, new):
                bad.append(f"{path} (a plan line other than its fr_version ceiling)")
            continue
        if path not in per_file and LIVE_ARTIFACT_RE.match(path) and status == "M":
            if not _stamp_moved_up(removed, added):
                bad.append(f"{path} (a line other than its artifact stamp)")
            continue
        if path not in per_file or status != "M":
            bad.append(f"{path} ({status})")
            continue
        if (
            len(added) != per_file[path]
            or [r.replace(old, new) for r in removed] != added
            or any(old not in r for r in removed)
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
    if body:
        message += ["-m", body]
    _git(repo, *_bot("commit", "--quiet", "--cleanup=verbatim", "-m", *message))


def push(repo: Path) -> str:
    """Push HEAD to main: 'ok', 'race', or raise on a protection refusal / other error."""
    r = _git(repo, "push", "--porcelain", REMOTE, f"HEAD:refs/heads/{BRANCH}", check=False)
    if r.returncode == 0:
        return "ok"
    reply = f"{r.stdout}\n{r.stderr}"
    if any(m.lower() in reply.lower() for m in _PROTECTED_MARKERS):
        raise ReleaseError(
            "the push to main was refused by branch protection, not lost to a race: "
            "the release bot needs a bypass actor on main's rules "
            "(Settings > Rules > protect main > Bypass list).\n" + reply.strip()
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


def release_to_main(repo: Path, override: str | None, cmds: Commands) -> Plan:
    """Steps 1-5: recompute from the tip until the release commit lands (or there is none)."""
    for _attempt in range(MAX_ATTEMPTS):
        sync_to_tip(repo)
        plan = compute(repo, override)
        if plan.new is None:
            return plan
        make_release_commit(repo, plan, cmds)
        check_staged_suite(repo, plan.new, cmds)
        if push(repo) == "ok":
            print(f"pushed {RELEASE_PREFIX}{plan.new} ({len(plan.fragments)} fragment(s))")
            return plan
        print("main moved under the release; recomputing from the new tip", file=sys.stderr)
    raise ReleaseError(
        f"lost the push race to main {MAX_ATTEMPTS} times; the next push to main retries",
        EXIT_RACE,
    )


# -- tag, notes, floors ----------------------------------------------------------


def release_notes(repo: Path, version: str) -> str:
    """The body of the `release: vX.Y.Z` commit that made `version`, or '' if none did."""
    log = _out(repo, "log", "-1", f"-S{version}", "--format=%s%x00%b", "--", vs.ROOT_PYPROJECT)
    subject, _, body = log.partition("\x00")
    return body.strip() if subject.strip() == f"{RELEASE_PREFIX}{version}" else ""


def previous_tag(repo: Path) -> str | None:
    r = _git(repo, "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", "HEAD", check=False)
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def floor_mismatches(repo: Path, version: str) -> list[str]:
    """§3.E: every floor added since the previous tag newer than it must name `version`."""
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
    """The annotated tag and the GitHub Release, exactly as auto-tag.yml made them."""
    tag = f"v{version}"
    _git(repo, *_bot("tag", "-a", tag, "-m", tag))
    _git(repo, "push", "--quiet", REMOTE, f"refs/tags/{tag}")
    args = ["release", "create", tag, "--title", tag]
    notes = release_notes(repo, version)
    if notes:
        args += ["--notes", notes]
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
    version = current_version(repo)
    if tag_exists(repo, version):
        print(f"v{version} is already tagged; nothing to do")
        return EXIT_OK
    bad = floor_mismatches(repo, version)
    tag_and_release(repo, version, cmds)  # the number is right, so it tags regardless
    if not bad:
        return EXIT_OK
    file_floor_issue(version, bad, cmds)
    print("ERROR: fr_version floor mismatch at release:", file=sys.stderr)
    for b in bad:
        print(f"  - {b}", file=sys.stderr)
    return EXIT_FLOOR


# -- entry -------------------------------------------------------------------------


def dry_run(repo: Path, override: str | None) -> int:
    plan = compute(repo, override)
    if plan.new is None:
        tagged = "tagged" if tag_exists(repo, plan.current) else "untagged — would tag it"
        print(f"no pending fragments; {plan.current} is {tagged}")
        return EXIT_OK
    how = f"override {override}" if override else f"{plan.bump} bump"
    print(
        f"would release {plan.current} -> {plan.new} ({how}) "
        f"from {len(plan.fragments)} fragment(s):"
    )
    for f in plan.fragments:
        print(f"  - {f.path.name}: {f.bump}: {f.summary}")
    return EXIT_OK


def main(
    argv: list[str] | None = None, repo: Path | None = None, commands: Commands | None = None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--version", default=None, help="release exactly this X.Y.Z")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    repo = Path(repo or REPO)
    cmds = commands or Commands()
    override = args.version or None
    try:
        if args.dry_run:
            return dry_run(repo, override)
        release_to_main(repo, override, cmds)
        return finish(repo, cmds)
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
