"""The walk — spec 2026-10-06-verification-strategies §C (R8, R9, R10, R11).

Two halves, kept apart so the pure one can be read without the other:

- planning and judging (pure): which rows a walk covers, the argv each step
  runs, the `fr-walk: 1` log's header, and whether a log satisfies what
  `deliver` owes (`walk_owed`, `check_walk_log`);
- the driver (`run_walk`): installs the candidate into a throwaway prefix
  through the repo's install contract, runs the smoke and each row's scenario,
  and writes the log. It never touches the operator's installed `fr`: every
  child gets `UV_TOOL_DIR` / `UV_TOOL_BIN_DIR` under the prefix, and the
  operator's resolved `fr` is fingerprinted before and after (gh#683's class).
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from fr.verification.model import StrategyManifest

if TYPE_CHECKING:
    from fr.acceptance.model import Matrix, Row
    from fr.verification.rows import SpecVerification

__all__ = [
    "CANDIDATE_INSTALL",
    "STEP_TIMEOUT_SECONDS",
    "WALK_SCHEMA",
    "WalkError",
    "WalkLog",
    "WalkOwed",
    "WalkStep",
    "check_walk_log",
    "operator_fr_fingerprint",
    "parse_walk_log",
    "plan_rows",
    "render_argv",
    "run_walk",
    "walk_log_dir",
    "walk_owed",
]

WALK_SCHEMA = 1
CANDIDATE_INSTALL = ".fr/candidate-install"
STEP_TIMEOUT_SECONDS = 1800
SMOKE_VERSION = "smoke:version"
SMOKE_STATUS = "smoke:status"
INSTALL = "install"
ROW_PREFIX = "row:"
_SEPARATOR = "---"


class WalkError(Exception):
    """A walk that cannot run (or a log that cannot be read) — the message
    names the cause."""


# --- what is owed ---------------------------------------------------------------


def _agent_pre_merge(strategy: str | None, repo_root: Path) -> bool:
    from fr.verification.effective import is_post_merge
    from fr.verification.model import RESERVED
    from fr.verification.resolve import resolve_strategy

    if strategy is None or strategy == RESERVED:
        return False
    manifest = resolve_strategy(strategy, repo_root)
    return manifest.driver == "agent" and not is_post_merge(strategy, repo_root)


@dataclass(frozen=True)
class WalkOwed:
    """What `deliver` owes a walk for: the agent-driven pre-merge rows citing
    the run's spec, and the run-level strategy when that is agent-driven
    pre-merge too. Owed when either is present."""

    rows: tuple[Row, ...] = ()
    run_strategy: str | None = None

    @property
    def owed(self) -> bool:
        return bool(self.rows) or self.run_strategy is not None


def walk_owed(
    matrix: Matrix, spec_ref: str, verification: SpecVerification, repo_root: Path
) -> WalkOwed:
    """Whether a walk is owed (§C). A spec with no `## Verification` section
    gives the run no strategy, so only a row's own `verify:` can make it owed —
    which is how an in-flight run delivers unchanged. A strategy that does not
    resolve raises `StrategyError`."""
    from fr.requirements import rows_citing

    rows = tuple(
        r
        for r in rows_citing(matrix, spec_ref)
        if _agent_pre_merge(verification.strategy(r), repo_root)
    )
    section = verification.section
    run_level: str | None = None
    if section is not None:
        candidate = section.strategy or verification.shape_default
        if _agent_pre_merge(candidate, repo_root):
            run_level = candidate
    return WalkOwed(rows=rows, run_strategy=run_level)


def plan_rows(
    matrix: Matrix,
    spec_ref: str,
    verification: SpecVerification,
    strategy: str,
    only: Sequence[str] = (),
) -> list[Row]:
    """The rows citing the spec whose effective strategy is `strategy`,
    narrowed to `only` when given. Raises `WalkError` for a `--row` that is not
    one of them."""
    from fr.requirements import rows_citing

    covered = [r for r in rows_citing(matrix, spec_ref) if verification.strategy(r) == strategy]
    if only:
        known = {r.id for r in covered}
        unknown = [i for i in only if i not in known]
        if unknown:
            raise WalkError(
                f"--row {unknown[0]!r} is not a row of this run on strategy {strategy!r} "
                f"(rows: {', '.join(sorted(known)) or 'none'})"
            )
        covered = [r for r in covered if r.id in set(only)]
    return covered


def render_argv(template: Sequence[str], values: Mapping[str, str]) -> list[str]:
    """`template` with each `{name}` replaced by `values[name]`."""
    out: list[str] = []
    for arg in template:
        for name, value in values.items():
            arg = arg.replace("{" + name + "}", value)
        out.append(arg)
    return out


# --- the log ----------------------------------------------------------------------


@dataclass(frozen=True)
class WalkStep:
    name: str
    exit: int
    seconds: float


@dataclass(frozen=True)
class WalkLog:
    run: str
    strategy: str
    code_tree: str
    harness: str
    model: str
    steps: tuple[WalkStep, ...]
    body: str = ""

    @property
    def rows(self) -> tuple[str, ...]:
        return tuple(s.name.removeprefix(ROW_PREFIX) for s in self.steps if _is_row(s.name))

    @property
    def passed(self) -> bool:
        return all(s.exit == 0 for s in self.steps)

    def render(self) -> str:
        header = {
            "fr-walk": WALK_SCHEMA,
            "run": self.run,
            "strategy": self.strategy,
            "code_tree": self.code_tree,
            "harness": self.harness,
            "model": self.model,
            "steps": [
                {"name": s.name, "exit": s.exit, "seconds": round(s.seconds, 2)} for s in self.steps
            ],
        }
        return f"{_SEPARATOR}\n{yaml.safe_dump(header, sort_keys=False)}{_SEPARATOR}\n{self.body}"


def _is_row(name: str) -> bool:
    return name.startswith(ROW_PREFIX)


def parse_walk_log(text: str) -> WalkLog:
    """The log's header, or `WalkError` naming why `text` is not a log
    `fr verification walk` wrote."""
    lines = text.split("\n")
    if not lines or lines[0] != _SEPARATOR:
        raise WalkError("not a walk log — it has no `fr-walk: 1` header")
    try:
        end = lines.index(_SEPARATOR, 1)
    except ValueError as e:
        raise WalkError("not a walk log — its header is never closed") from e
    try:
        header = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as e:
        raise WalkError(f"not a walk log — its header is not YAML: {e}") from e
    if not isinstance(header, dict) or header.get("fr-walk") != WALK_SCHEMA:
        raise WalkError(f"not a walk log — its header lacks `fr-walk: {WALK_SCHEMA}`")
    try:
        steps = tuple(
            WalkStep(str(s["name"]), int(s["exit"]), float(s["seconds"])) for s in header["steps"]
        )
        return WalkLog(
            run=str(header["run"]),
            strategy=str(header["strategy"]),
            code_tree=str(header["code_tree"]),
            harness=str(header["harness"]),
            model=str(header["model"]),
            steps=steps,
            body="\n".join(lines[end + 1 :]),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise WalkError(f"not a walk log — its header is incomplete ({e!r})") from e


def check_walk_log(log: WalkLog, owed: WalkOwed, head_tree: str) -> list[str]:
    """Every reason `log` does not satisfy `owed` at `head_tree` (empty when it
    does): the stale tree, each failing step, a missing smoke, each owed row it
    does not cover — each naming its cause."""
    problems: list[str] = []
    if log.code_tree != head_tree:
        problems.append(
            f"the walk covers code tree {log.code_tree[:12]} but HEAD's is {head_tree[:12]} — "
            "the code changed since it ran; walk again"
        )
    names = {s.name for s in log.steps}
    problems += [f"step {s.name!r} failed (exit {s.exit})" for s in log.steps if s.exit != 0]
    problems += [
        f"the smoke is missing ({step!r} is not in the log)"
        for step in (INSTALL, SMOKE_VERSION, SMOKE_STATUS)
        if step not in names
    ]
    covered = set(log.rows)
    problems += [
        f"row {r.id!r} is not covered by the walk" for r in owed.rows if r.id not in covered
    ]
    return problems


def walk_log_dir(run: str) -> Path:
    return Path.home() / ".cache" / "fr" / "walks" / run


# --- the operator's fr ------------------------------------------------------------


def operator_fr_fingerprint(env: Mapping[str, str]) -> tuple[str, int, int] | None:
    """What the operator's resolved `fr` is — the `FR_HARNESS_FR` pin, else the
    one on PATH: its target, mtime and size. `None` when there is none to
    protect."""
    found = env.get("FR_HARNESS_FR") or shutil.which("fr", path=env.get("PATH"))
    if not found:
        return None
    try:
        target = os.path.realpath(found)
        st = os.stat(target)
    except OSError:
        return (found, -1, -1)
    return (target, st.st_mtime_ns, st.st_size)


# --- the driver -------------------------------------------------------------------


@dataclass(frozen=True)
class _Ran:
    step: WalkStep
    output: str


def _run(name: str, argv: Sequence[str], cwd: Path, env: Mapping[str, str]) -> tuple[_Ran, str]:
    """Run `argv`; `(record, stdout)`. A command that cannot start or times out
    is a failed step, never an exception — the log is the report."""
    started = time.monotonic()
    try:
        proc = subprocess.run(
            list(argv),
            cwd=cwd,
            env=dict(env),
            capture_output=True,
            text=True,
            timeout=STEP_TIMEOUT_SECONDS,
            check=False,
        )
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        partial = e.stdout or ""
        out = partial.decode() if isinstance(partial, bytes) else partial
        code, err = 124, f"timed out after {STEP_TIMEOUT_SECONDS}s"
    except OSError as e:
        code, out, err = 127, "", f"cannot run {argv[0]!r}: {e}"
    seconds = time.monotonic() - started
    shown = f"$ {' '.join(argv)}\n{out}{err}"
    return _Ran(WalkStep(name, code, seconds), shown), out


def _contract(repo_root: Path, manifest: StrategyManifest) -> None:
    """R8: the install template's program must exist in the repo and be
    executable — and a repo without it is told so BY NAME."""
    if not manifest.install:
        raise WalkError(
            f"strategy {manifest.verification!r} has no install — there is nothing to walk"
        )
    program = manifest.install[0]
    if "/" not in program or program.startswith("/"):
        return
    path = repo_root / program
    if not path.is_file() or not os.access(path, os.X_OK):
        raise WalkError(
            f"strategy {manifest.verification!r} needs the repo's executable `{program}` "
            f"<prefix> <source> (the candidate-install contract, spec R8), and {path} "
            + ("is not executable" if path.is_file() else "does not exist")
        )


def run_walk(
    *,
    repo_root: Path,
    run: str,
    manifest: StrategyManifest,
    rows: Sequence[Row],
    model: str,
    harness: str,
    code_tree: str,
    client: Path | None = None,
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> tuple[Path, WalkLog]:
    """Install, smoke, scenarios; write the log; return `(path, log)`.

    Raises `WalkError` before anything runs for a missing contract, scenario or
    unsupported source, and AFTER the log is written when the install moved the
    operator's `fr` — that is a failure louder than any step's exit code.
    """
    base = dict(os.environ if env is None else env)
    _contract(repo_root, manifest)
    if manifest.source == "prerelease":
        raise WalkError(
            f"strategy {manifest.verification!r} installs from a pre-release, which `walk` "
            "does not build: install the rc yourself and run the scenarios with --client"
        )
    scenarios: dict[str, Path] = {}
    for row in rows:
        if not row.scenario:
            raise WalkError(f"row {row.id!r} names no `scenario` — an agent-driven walk needs one")
        path = repo_root / row.scenario
        if not path.is_file():
            raise WalkError(f"row {row.id!r}: scenario {row.scenario!r} does not exist")
        scenarios[row.id] = path
    if client is not None and not client.is_dir():
        raise WalkError(f"--client {client} is not a directory")

    before = operator_fr_fingerprint(base)
    prefix = Path(tempfile.mkdtemp(prefix="fr-walk-")).resolve()
    bin_dir = prefix / "bin"
    child = {
        **{k: v for k, v in base.items() if k != "FR_HARNESS_FR"},
        "UV_TOOL_DIR": str(prefix / "uv-tools"),
        "UV_TOOL_BIN_DIR": str(bin_dir),
        "FR_WALK_PREFIX": str(prefix),
        "PATH": f"{bin_dir}{os.pathsep}{base.get('PATH', '')}",
    }
    fixture = prefix / "fixture"
    values = {
        "repo": str(repo_root),
        "worktree": str(repo_root),
        "prefix": str(prefix),
        "bin": str(bin_dir),
        "fixture": str(fixture),
        "client": str(client) if client is not None else str(fixture),
        "source": str(repo_root),
    }
    ran: list[_Ran] = []

    def record(name: str, argv: Sequence[str], cwd: Path) -> str:
        r, out = _run(name, argv, cwd, child)
        ran.append(r)
        return out

    def render_template(template: Sequence[str], **extra: str) -> list[str]:
        argv = render_argv(template, {**values, **extra})
        # A repo-relative program (`.fr/candidate-install`) runs from the repo.
        if "/" in argv[0] and not os.path.isabs(argv[0]):
            argv[0] = str(repo_root / argv[0])
        return argv

    assert manifest.install is not None
    out = record(INSTALL, render_template(manifest.install), repo_root)
    if ran[-1].step.exit == 0:
        tool = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "")
        if not tool:
            ran[-1] = _Ran(
                WalkStep(INSTALL, 1, ran[-1].step.seconds),
                ran[-1].output + "\nthe install printed no tool name on its last line\n",
            )
        else:
            tool_path = str(bin_dir / tool)
            fixture.mkdir()
            record("smoke:fixture", ["git", "init", "-q", str(fixture)], prefix)
            record(SMOKE_VERSION, [tool_path, "--version"], prefix)
            record(SMOKE_STATUS, [tool_path, "status"], fixture)
            for row in rows:
                if client is not None:
                    cwd = client
                else:
                    cwd = prefix / f"work-{row.id}"
                    shutil.copytree(fixture, cwd)
                argv = render_template(
                    manifest.scenario or ("{scenario}",), scenario=str(scenarios[row.id])
                )
                if not _is_executable(Path(argv[0])) and Path(argv[0]).is_file():
                    argv = ["sh", *argv]
                record(f"{ROW_PREFIX}{row.id}", argv, cwd)

    steps = tuple(r.step for r in ran)
    body = "\n".join(f"=== {r.step.name} (exit {r.step.exit}) ===\n{r.output}" for r in ran)
    log = WalkLog(
        run=run,
        strategy=manifest.verification,
        code_tree=code_tree,
        harness=harness,
        model=model,
        steps=steps,
        body=body,
    )
    directory = walk_log_dir(run)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{now().strftime('%Y%m%dT%H%M%SZ')}.log"
    path.write_text(log.render())
    after = operator_fr_fingerprint(base)
    if after != before:
        raise WalkError(
            f"the install changed the operator's own fr ({before} -> {after}) — a candidate "
            "install must stay inside its prefix; the log was written to " + str(path)
        )
    return path, log


def _is_executable(path: Path) -> bool:
    try:
        return bool(path.stat().st_mode & stat.S_IXUSR)
    except OSError:
        return False
