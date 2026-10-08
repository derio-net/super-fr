"""One state across workspaces: every triage command syncs with the state ref through
ONE wrapper in the triage CLI (spec 2026-10-07-cloud-triage R5, §B "One state across
workspaces", review p3-r1).

Once a scope has a `state_repo`, a command that reads state fetches the ref first
(adopting it when the local copy is not ahead) and a command that changes state pushes
after; a push conflict refuses with the fetch-and-retry line. Every remote is a bare
repo under `tmp_path` (`triage_cmd.state_remote` is pointed at it); no ref is pushed
anywhere else.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_cmd, triage_state_cmd
from fr.triage import state_sync
from fr.triage.model import Scope
from fr.triage.scope_config import scope_id
from fr.triage.state_ref import RETRY_LINE, push_state, read_base, ref_name
from typer.testing import CliRunner

REPO = "o/r"
SCOPE = Scope(kind="repo", target=REPO)
DURABLE = b"state_repo: o/r\n"


class _Private:
    def repo_visibility(self, repo: str) -> str:
        return "private"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bare = tmp_path / "state.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(bare))
    monkeypatch.setattr(triage_cmd, "state_remote", lambda state_repo: str(bare))
    monkeypatch.setattr(triage_cmd, "make_visibility_client", lambda: _Private())
    return bare


def _workspace(tmp_path: Path, name: str, files: dict[str, bytes]) -> tuple[Path, Path]:
    ws = tmp_path / name
    _git(tmp_path, "init", "--quiet", str(ws))
    state = ws / ".fr" / "triage-state" / SCOPE.name
    state.mkdir(parents=True)
    for rel, content in files.items():
        (state / rel).parent.mkdir(parents=True, exist_ok=True)
        (state / rel).write_bytes(content)
    return ws, state


def _invoke(*args: str) -> Any:
    return CliRunner().invoke(app, ["triage", *args])


def _ref(origin: Path) -> str:
    out = _git(origin, "for-each-ref", "--format=%(objectname)", ref_name(scope_id(SCOPE)))
    return out.strip()


def _export_dir(tmp_path: Path, judgements: bytes) -> Path:
    src = tmp_path / "export"
    (src / SCOPE.name).mkdir(parents=True)
    (src / SCOPE.name / "judgements.yaml").write_bytes(judgements)
    return src


def test_a_command_that_changes_state_pushes_it_after(tmp_path: Path, origin: Path) -> None:
    ws, state = _workspace(tmp_path, "a", {"scope-durable.yaml": DURABLE})
    src = _export_dir(tmp_path, b"schema: 6\nissues: {}\n")

    result = _invoke("state", "import", "--from", str(src), "--repo", REPO, "--workspace", str(ws))

    assert result.exit_code == 0, result.output
    sha = _ref(origin)
    assert sha, "the change was not pushed"
    assert _git(origin, "show", f"{sha}:judgements.yaml") == "schema: 6\nissues: {}\n"
    assert read_base(state, remote=str(origin), ref=ref_name(scope_id(SCOPE))) == sha


def test_a_command_that_reads_state_fetches_the_ref_first(tmp_path: Path, origin: Path) -> None:
    _, state_a = _workspace(
        tmp_path, "a", {"scope-durable.yaml": DURABLE, "judgements.yaml": b"schema: 6\n"}
    )
    push_state(
        state_a, str(origin), scope_id(SCOPE), expected_old=None, scope=SCOPE,
        state_repo=REPO, client=_Private(),
    )  # fmt: skip
    ws_b, state_b = _workspace(tmp_path, "b", {"scope-durable.yaml": DURABLE})

    result = _invoke("batch", "list", "--repo", REPO, "--workspace", str(ws_b))

    assert result.exit_code == 0, result.output
    assert (state_b / "judgements.yaml").read_bytes() == b"schema: 6\n"


def test_a_command_that_only_reads_pushes_nothing(tmp_path: Path, origin: Path) -> None:
    ws, state = _workspace(
        tmp_path, "a", {"scope-durable.yaml": DURABLE, "judgements.yaml": b"schema: 6\n"}
    )
    before = push_state(
        state, str(origin), scope_id(SCOPE), expected_old=None, scope=SCOPE,
        state_repo=REPO, client=_Private(),
    )  # fmt: skip
    (state / "judgements.yaml").write_bytes(b"schema: 6\nissues: {}\n")  # local, unpushed

    result = _invoke("batch", "list", "--repo", REPO, "--workspace", str(ws))

    assert result.exit_code == 0, result.output
    assert _ref(origin) == before
    assert (state / "judgements.yaml").read_bytes() == b"schema: 6\nissues: {}\n"  # kept


def test_a_push_conflict_refuses_with_the_fetch_and_retry_line(
    tmp_path: Path, origin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws, state = _workspace(tmp_path, "a", {"scope-durable.yaml": DURABLE})
    _, other = _workspace(tmp_path, "b", {"scope-durable.yaml": DURABLE, "lease.yaml": b"x\n"})
    real = triage_state_cmd.import_state

    def racing(*args: Any, **kwargs: Any) -> state_sync.SyncReport:
        # Another workspace pushes between this command's fetch and its push.
        push_state(
            other, str(origin), scope_id(SCOPE), expected_old=None, scope=SCOPE,
            state_repo=REPO, client=_Private(),
        )  # fmt: skip
        return real(*args, **kwargs)

    monkeypatch.setattr(triage_state_cmd, "import_state", racing)
    src = _export_dir(tmp_path, b"schema: 6\n")

    result = _invoke("state", "import", "--from", str(src), "--repo", REPO, "--workspace", str(ws))

    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert " ".join(RETRY_LINE.split()) in flat
    assert _git(origin, "show", f"{_ref(origin)}:lease.yaml") == "x\n"  # theirs kept


def test_outside_a_clone_with_a_state_repo_nothing_is_synced_and_it_says_so(
    tmp_path: Path, origin: Path
) -> None:
    state = tmp_path / "plain"
    state.mkdir()
    (state / "scope-durable.yaml").write_bytes(DURABLE)

    result = _invoke("batch", "list", "--repo", REPO, "--dir", str(state))

    assert result.exit_code == 0, result.output
    assert "not synced" in result.output
    assert _ref(origin) == ""


def test_no_verb_reaches_the_ref_but_the_wrapper_and_the_state_verbs() -> None:
    """ONE wrapper, not per verb: only `triage_cmd` (the wrapper) and `triage_state_cmd`
    (the explicit `state push|fetch`) name the ref operations."""
    import fr.commands as commands

    root = Path(commands.__file__).parent
    hits = sorted(
        p.name
        for p in root.glob("triage*_cmd.py")
        if "push_state" in p.read_text() or "fetch_state" in p.read_text()
    )
    assert hits == ["triage_cmd.py", "triage_state_cmd.py"]


# ------------------------- a push the remote refuses (debug 2026-10-08-cloud-state-ref-proxy)


def _refuse_pushes(bare: Path) -> None:
    """A pre-receive hook refusing every push, standing in for the cloud git proxy's
    HTTP 403: the ref does not move, and it is no compare-and-swap conflict."""
    hook = bare / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'refused by policy' >&2\nexit 1\n")
    hook.chmod(0o755)


def test_collect_whose_push_is_refused_warns_and_exits_zero(
    tmp_path: Path, origin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.triage_fixtures import FakeForge

    forge = FakeForge(issues={REPO: []}, prs={REPO: []}, visibility={REPO: "private"})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    ws, state = _workspace(tmp_path, "a", {})
    _refuse_pushes(origin)

    result = _invoke("collect", "--repo", REPO, "--workspace", str(ws))

    assert result.exit_code == 0, result.output
    assert (state / "facts.json").is_file()
    flat = " ".join(result.output.split())
    assert "warning:" in flat
    assert ref_name(scope_id(SCOPE)) in flat
    assert "stays local until a push succeeds" in flat
    assert _ref(origin) == ""


def test_a_wrapped_command_whose_push_is_refused_warns_and_exits_zero(
    tmp_path: Path, origin: Path
) -> None:
    ws, state = _workspace(tmp_path, "a", {"scope-durable.yaml": DURABLE})
    src = _export_dir(tmp_path, b"schema: 6\nissues: {}\n")
    _refuse_pushes(origin)

    result = _invoke("state", "import", "--from", str(src), "--repo", REPO, "--workspace", str(ws))

    assert result.exit_code == 0, result.output
    assert "stays local until a push succeeds" in " ".join(result.output.split())
    assert (state / "judgements.yaml").read_bytes() == b"schema: 6\nissues: {}\n"
    assert read_base(state, remote=str(origin), ref=ref_name(scope_id(SCOPE))) is None


def test_state_push_whose_push_is_refused_still_fails(tmp_path: Path, origin: Path) -> None:
    """Pushing is `state push`'s whole job: a refusal is its failure, exit 2."""
    ws, _state = _workspace(
        tmp_path, "a", {"scope-durable.yaml": DURABLE, "judgements.yaml": b"schema: 6\n"}
    )
    _refuse_pushes(origin)

    result = _invoke("state", "push", "--repo", REPO, "--workspace", str(ws))

    assert result.exit_code == 2, result.output
    assert "refused by policy" in result.output
    assert _ref(origin) == ""
