"""Version drift: when a run, or the driver itself, must be re-homed onto a new fr
(spec 2026-10-07-cloud-triage R17, R18, §G).

Pure apart from `load_ledger`/`save_ledger`, which read and write `rehomes.yaml` in the
scope's state directory (it travels in the state ref, `fr.triage.state_ref.REF_FILES`,
so a driver restored on a fresh container never re-homes a run twice):

- `plan_drift`: each active batch's run cursor (read by the pass from the batch branch's
  head: the cursor whose `branch` is the batch's, `pick_cursor`, p6-r3) against the
  latest fr release. Equal major → nothing; another major → one re-home per (run,
  release MAJOR, p6-r2), asked only once the run's session is idle (R17's "next
  idle moment", the same rule the conflict hand-back keeps); no recorded version →
  reported once, never re-homed.
- `plan_self_update`: the cloud driver before each pass (R18). A release major other
  than the one the driver session started with → re-home the driver itself; else an
  installed fr older than the release → reinstall and run the pass on the new one.

The ledger also holds the driver's own state: the fr version its session started
with, and the self-re-home request still pending.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import yaml
from packaging.version import InvalidVersion, Version

from fr.triage.errors import TriageError

__all__ = ["TriageError"]  # re-exported: a corrupt ledger raises it

FR_RELEASE_REPO = "derio-net/super-fr"
"""Where fr is released: the latest release's tag is the version every session should
run (R17, R18)."""

REHOMES_FILE = "rehomes.yaml"
RUNS_DIR = "docs/superpowers/runs"
DRIVER_REQUEST_PREFIX = "driver:rehome:"
"""A self-re-home request's id is this plus the release; `drive record` routes its result
here rather than to the runner's mailbox."""

_MAJOR = re.compile(r"^[vV]?(\d+)(?:\.|$)")


def major(version: str | None) -> int | None:
    """The major of a version or tag (`5.17.1`, `v6.0.0`); None when it is not one."""
    m = _MAJOR.match(version or "")
    return int(m.group(1)) if m else None


def older(installed: str, release: str) -> bool:
    """Is *installed* older than *release* (a tag, `v` optional)? False when either
    does not parse: an unknown order is never a reason to reinstall."""
    try:
        return Version(installed.lstrip("vV")) < Version(release.lstrip("vV"))
    except InvalidVersion:
        return False


def cursor_paths(files: Iterable[str]) -> list[str]:
    """The run cursors among a PR's changed files: `docs/superpowers/runs/<run>.yaml`.
    A PR may carry several (`fr migrate artifacts` touches every live one)."""
    return [
        f
        for f in files
        if str(PurePosixPath(f).parent) == RUNS_DIR and PurePosixPath(f).suffix == ".yaml"
    ]


def cursor_branch(text: str) -> str | None:
    """The `branch` a run cursor's text records; None when it records none."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    branch = data.get("branch") if isinstance(data, Mapping) else None
    return branch if isinstance(branch, str) and branch else None


def pick_cursor(texts: Mapping[str, str], branch: str) -> str | None:
    """The one cursor (path → text, as read at the PR head) whose `branch` is *branch*;
    None when none or several are (p6-r3): another run's cursor is never lent."""
    matching = [path for path, text in texts.items() if cursor_branch(text) == branch]
    return matching[0] if len(matching) == 1 else None


def read_cursor(text: str) -> tuple[str | None, str | None]:
    """`(run, fr_version)` of a run cursor's text; None for what it does not carry."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None, None
    if not isinstance(data, Mapping):
        return None, None
    run, version = data.get("run"), data.get("fr_version")
    return (
        str(run) if isinstance(run, str) and run else None,
        str(version) if isinstance(version, str) and version else None,
    )


@dataclass(frozen=True)
class RunVersion:
    """One active batch's run, as the pass read it: its cursor's run id and recorded fr
    version, and its session's status (`fr_dispatch.protocols.SessionStatus`)."""

    batch: str
    item: str
    branch: str
    run: str | None
    fr_version: str | None
    status: str


@dataclass(frozen=True)
class Rehome:
    """Re-home *item*'s session: it pushes and stops, and a fresh session continues
    *branch* from *brief* (R17)."""

    batch: str
    item: str
    run: str
    branch: str
    recorded: str
    release: str
    brief: str


@dataclass(frozen=True)
class Drift:
    rehomes: tuple[Rehome, ...] = ()
    unknown: tuple[RunVersion, ...] = ()  # no recorded version: report, never re-home


@dataclass(frozen=True)
class Ledger:
    """`rehomes.yaml`: the re-homes asked per (run, release major), the runs reported
    with no recorded version, and the driver's own session (`start`, `pending`)."""

    rehomes: tuple[dict[str, Any], ...] = ()
    reported: tuple[str, ...] = ()
    driver: dict[str, Any] = field(default_factory=dict)

    def rehomed(self, run: str, release: str) -> bool:
        """Was *run* re-homed onto *release*'s major (p6-r2)? An entry's major is its
        `major`, else its `release`'s (an entry written before the major was recorded)."""
        want = major(release)
        return want is not None and any(
            e.get("run") == run and _entry_major(e) == want for e in self.rehomes
        )

    def with_rehomes(self, rehomes: Iterable[Rehome], *, at: str) -> Ledger:
        new = tuple(
            {"run": r.run, "release": r.release, "major": major(r.release), "item": r.item,
             "recorded": r.recorded, "at": at}
            for r in rehomes
        )  # fmt: skip
        return replace(self, rehomes=self.rehomes + new)

    def with_reported(self, unknown: Iterable[RunVersion]) -> Ledger:
        runs = [u.run or u.item for u in unknown]
        return replace(
            self, reported=self.reported + tuple(r for r in runs if r not in self.reported)
        )

    def with_driver(self, **values: Any) -> Ledger:
        driver = {**self.driver, **values}
        return replace(self, driver={k: v for k, v in driver.items() if v is not None})


def _entry_major(entry: Mapping[str, Any]) -> int | None:
    value = entry.get("major")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return major(str(entry.get("release") or ""))


def resume_brief(run: str, branch: str, release: str) -> str:
    """The fresh session's brief: continue *run* on *branch* from its cursor and journal."""
    return (
        f"Continue run {run} on branch `{branch}`: its session was re-homed onto fr "
        f"{release}, whose major differs from the fr the run started with.\n"
        f"Check out `{branch}`, run `fr pickup --run {run}` and follow the brief it prints, "
        "in order. Do not start a new run."
    )


def plan_drift(runs: Sequence[RunVersion], release: str | None, ledger: Ledger) -> Drift:
    """R17: what this pass asks, given each active batch's run and the latest release."""
    want = major(release)
    if release is None or want is None:
        return Drift()
    rehomes: list[Rehome] = []
    unknown: list[RunVersion] = []
    for rv in runs:
        key = rv.run or rv.item
        have = major(rv.fr_version)
        if have is None:
            if key not in ledger.reported:
                unknown.append(rv)
            continue
        if have == want or rv.run is None or ledger.rehomed(rv.run, release):
            continue
        if rv.status != "idle":
            continue  # at the session's next idle moment, never mid-turn
        rehomes.append(
            Rehome(
                batch=rv.batch,
                item=rv.item,
                run=rv.run,
                branch=rv.branch,
                recorded=str(rv.fr_version),
                release=release,
                brief=resume_brief(rv.run, rv.branch, release),
            )
        )
    return Drift(rehomes=tuple(rehomes), unknown=tuple(unknown))


# ------------------------------------------------------------------ the ledger


def load_ledger(state_dir: Path) -> Ledger:
    path = state_dir / REHOMES_FILE
    if not path.is_file():
        return Ledger()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise TriageError(f"{path}: unreadable ({exc})") from exc
    if not isinstance(data, Mapping):
        raise TriageError(f"{path}: not a re-home ledger (rehomes, reported, driver)")
    rehomes = data.get("rehomes") or []
    reported = data.get("reported") or []
    driver = data.get("driver") or {}
    if (
        not isinstance(rehomes, list)
        or not all(isinstance(e, Mapping) for e in rehomes)
        or not isinstance(reported, list)
        or not isinstance(driver, Mapping)
    ):
        raise TriageError(f"{path}: not a re-home ledger (rehomes, reported, driver)")
    return Ledger(
        rehomes=tuple(dict(e) for e in rehomes),
        reported=tuple(str(r) for r in reported),
        driver=dict(driver),
    )


def save_ledger(state_dir: Path, ledger: Ledger) -> None:
    from fr.artifacts.atomic import write_text_atomic

    data: dict[str, Any] = {"rehomes": list(ledger.rehomes), "reported": list(ledger.reported)}
    if ledger.driver:
        data["driver"] = ledger.driver
    state_dir.mkdir(parents=True, exist_ok=True)
    write_text_atomic(state_dir / REHOMES_FILE, yaml.safe_dump(data, sort_keys=False))


# ------------------------------------------------------- the driver itself (R18)

REEXEC_ENV = "FR_TRIAGE_REEXEC"
"""Set to the release a pass re-executed itself for: a pass that still finds an older fr
under it runs on that fr rather than reinstalling again (no loop)."""

SelfAction = Literal["none", "reinstall", "rehome"]


@dataclass(frozen=True)
class SelfUpdate:
    action: SelfAction
    release: str | None = None
    start: str | None = None  # the driver session's start version, to record


def plan_self_update(installed: str, release: str | None, ledger: Ledger) -> SelfUpdate:
    """R18, before each pass. The session's start version is the ledger's, else the
    installed fr (its first pass). A release major past the start's → re-home the driver
    (the skill text it loaded cannot refresh in place); else an installed fr older than
    the release → reinstall. A dev build newer than every release does neither."""
    start = str(ledger.driver.get("start") or installed)
    want, have = major(release), major(start)
    if release is None or want is None:
        return SelfUpdate("none", start=start)
    if have is not None and want > have:
        return SelfUpdate("rehome", release, start)
    if older(installed, release):
        return SelfUpdate("reinstall", release, start)
    return SelfUpdate("none", release, start)


def driver_brief(*, scope_args: Sequence[str], state_repo: str | None, host_id: str,
                 release: str, generation: int) -> str:  # fmt: skip
    """The fresh driver session's brief: the same driver (host id, so the same lease
    holder, §D), on the release it re-homes onto, as lease *generation* (p6-r4): every
    pass and record it runs names it, so the session it replaces stops."""
    args = " ".join(scope_args)
    state = f" --state-repo {state_repo}" if state_repo else ""
    gen = f" --generation {generation}"
    return (
        f"You are the cloud triage driver, re-homed onto fr {release}.\n"
        f"1. Write `{host_id}` to ~/.config/fr/host-id when that file is missing: it is "
        "this driver's identity, and the drive lease it holds.\n"
        f"2. Run the fr-triage skill's driver section: `fr triage drive pass {args}{state}"
        f"{gen} --outbox <outbox>`, execute the outbox, `fr triage drive record {args}{gen} "
        "--outbox <outbox> --result <results>`, and schedule the next wake. Pass "
        f"`{gen.strip()}` to every pass and record."
    )


def driver_request(release: str, brief: str, *, generation: int) -> dict[str, Any]:
    """The self-re-home request the pass writes to the outbox, and stops. It carries a
    request tag like every creating request (§F), so a replay finds the session it
    created rather than making a second; `generation` is the new session's (p6-r4)."""
    rid = f"{DRIVER_REQUEST_PREFIX}{release}"
    return {
        "id": rid,
        "kind": "rehome",
        "item": "driver",
        "session": "self",
        "release": release,
        "generation": generation,
        "request_tag": rid,
        "prompt": brief,
        "execute": "list_sessions and look for one tagged `request_tag`; when one exists, "
        "create nothing and record its id; otherwise create_session(this repo, model = this "
        "session's, tags = [request_tag], prompt) for a fresh driver session. Then stop this "
        "one: schedule no further wake",
        "record": "{id, session: <new session id>}",
    }


def adopt_pending(ledger: Ledger, generation: int) -> Ledger | None:
    """The ledger with the pending self-re-home taken as done, when the session asking is
    the one it created, or a later one (*generation* at least the request's): the agent's
    record of it was lost, but the session exists. None when there is nothing to adopt."""
    pending = ledger.driver.get("pending")
    if not isinstance(pending, Mapping):
        return None
    made = pending.get("generation")
    if not isinstance(made, int) or isinstance(made, bool) or generation < made:
        return None
    release = str(pending.get("release") or "")
    driver = {k: v for k, v in ledger.driver.items() if k != "pending"}
    driver["start"] = release.lstrip("vV")
    return replace(ledger, driver=driver)


def superseded(lease_generation: int, generation: int, ledger: Ledger) -> bool:
    """Is a driver session of *generation* superseded by the lease's (p6-r4)? Yes when the
    lease's is newer, except for the session whose own self-re-home moved it (the
    pending request's generation, one past its own): it still re-emits and records that
    request, and nothing else."""
    if generation >= lease_generation:
        return False
    pending = ledger.driver.get("pending")
    made = pending.get("generation") if isinstance(pending, Mapping) else None
    return not (made == lease_generation and generation == lease_generation - 1)


def record_driver_result(ledger: Ledger, result: Mapping[str, Any]) -> Ledger:
    """Apply the agent's result for the pending self-re-home: the new session runs the
    release, so it becomes the driver's start. Raises when no such request is pending."""
    pending = ledger.driver.get("pending")
    rid = result.get("id")
    if not isinstance(pending, Mapping) or pending.get("id") != rid:
        raise TriageError(f"no pending driver request is named {rid}")
    if not result.get("session"):
        raise TriageError(f"{rid}: a re-home result names the new session (`session`)")
    release = str(pending.get("release") or "")
    driver = {k: v for k, v in ledger.driver.items() if k != "pending"}
    driver["start"] = release.lstrip("vV")
    return replace(ledger, driver=driver)
