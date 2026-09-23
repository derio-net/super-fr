"""`fr.archive.merge_evidence` and the `fr.git` default-ref helpers (#526/#544).

Spec `2026-09-23-archive-merge-evidence-design.md` §3.A, Test Plan §5 items 1–2.

Every repo here is a real temp git repo whose remote is a FILE PATH (a bare
repo beside it), so nothing touches a network. Global and system git config
are cut off per test, so an operator's `checkout.defaultRemote` or
`init.defaultBranch` cannot change an answer.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import fr.archive as archive_mod
import pytest
import yaml
from fr.archive import DefaultRef, MergeEvidence, merge_evidence
from fr.git import GitRefusal, remote_default_ref, remote_name

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
PLANS_REL = Path("docs/superpowers/plans")


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def stub_fetch(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Hermetic git plus a recorder in place of ``fr.archive._fetch``.

    Shared by every test module that drives a merge-evidence surface through
    the CLI (sweep, archive gate, nudges): no operator git config, no network,
    and the returned list records one remote name per fetch, so a test can
    assert "one ``merge_evidence(fetch=True)`` per invocation".
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    fetched: list[str] = []
    monkeypatch.setattr(archive_mod, "_fetch", lambda root, remote: fetched.append(remote))
    return fetched


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _phase_yaml(number: int, tag: str, *, ticked: bool) -> str:
    doc = yaml.safe_load((FIXTURE / "01.yaml").read_text())
    doc["phase"]["number"] = number
    doc["phase"]["tag"] = tag
    doc["phase"]["skeleton"] = number == 1
    step_id = f"P{number}.T1.S1"
    doc["tasks"][0]["steps"][0]["id"] = step_id
    doc["state"]["steps"] = {
        step_id: {"state": "x" if ticked else " ", "ticked_at": None, "note": None}
    }
    return yaml.safe_dump(doc, sort_keys=False)


def _write_plan(repo: Path, name: str, phases: list[tuple[str, bool]]) -> Path:
    """A plan dir with one phase per `(tag, ticked)` entry, numbered from 1."""
    plan_dir = repo / PLANS_REL / name
    plan_dir.mkdir(parents=True, exist_ok=True)
    meta = yaml.safe_load((FIXTURE / "_meta.yaml").read_text())
    meta["plan"] = name
    (plan_dir / "_meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    shutil.copy(FIXTURE / "_prose.md", plan_dir / "_prose.md")
    for f in plan_dir.glob("[0-9][0-9].yaml"):
        f.unlink()
    for i, (tag, ticked) in enumerate(phases, start=1):
        (plan_dir / f"{i:02d}.yaml").write_text(_phase_yaml(i, tag, ticked=ticked))
    return plan_dir


def _init(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def _commit(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", msg)


def _add_remote(repo: Path, bare: Path, name: str = "origin") -> Path:
    if not bare.exists():
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    _git(repo, "remote", "add", name, str(bare))
    return bare


def _publish(repo: Path, remote: str = "origin", branch: str = "main") -> None:
    """Push HEAD to `<remote>/<branch>` and fetch, so the tracking ref exists."""
    _git(repo, "push", "-q", remote, f"HEAD:refs/heads/{branch}")
    _git(repo, "fetch", "-q", remote)


# --- fr.git.remote_name / remote_default_ref ---------------------------------


def test_remote_name_is_none_without_a_remote(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    assert remote_name(repo) is None


def test_remote_name_is_the_single_remote_of_any_name(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "up.git", name="upstream")
    assert remote_name(repo) == "upstream"


def test_remote_name_refuses_two_remotes_without_default(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "a.git", name="a")
    _add_remote(repo, tmp_path / "b.git", name="b")
    got = remote_name(repo)
    assert isinstance(got, GitRefusal)
    assert "checkout.defaultRemote" in got.reason


def test_remote_name_honours_checkout_default_remote(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "a.git", name="a")
    _add_remote(repo, tmp_path / "b.git", name="b")
    _git(repo, "config", "checkout.defaultRemote", "b")
    assert remote_name(repo) == "b"


def test_remote_default_ref_follows_origin_head(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo, branch="main")
    _publish(repo, branch="trunk")
    _git(repo, "remote", "set-head", "origin", "trunk")
    assert remote_default_ref(repo) == "origin/trunk"


def test_remote_default_ref_falls_back_to_a_well_known_remote_branch(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo, branch="master")  # a plain fetch never writes origin/HEAD
    assert remote_default_ref(repo) == "origin/master"


def test_remote_default_ref_ignores_a_local_main(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")  # local `main` exists, no remote
    assert remote_default_ref(repo) is None
    _add_remote(repo, tmp_path / "o.git")  # remote with no branches fetched
    assert remote_default_ref(repo) is None


def test_remote_default_ref_passes_the_refusal_through(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "a.git", name="a")
    _add_remote(repo, tmp_path / "b.git", name="b")
    assert isinstance(remote_default_ref(repo), GitRefusal)


# --- merge_evidence: the default ref -----------------------------------------


def test_evidence_names_the_resolved_ref_and_its_sha(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo)
    ev = merge_evidence(repo, fetch=False)
    assert isinstance(ev, MergeEvidence)
    assert isinstance(ev.ref, DefaultRef)
    assert ev.ref.ref == "origin/main"
    assert ev.ref.sha == _git(repo, "rev-parse", "--short", "origin/main")
    assert ev.ref_error is None
    assert ev.fetched is False and ev.fetch_error is None


def test_evidence_without_a_remote_is_unknown_not_merged(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _write_plan(repo, "2026-01-01-done", [("agentic", True)])
    _commit(repo, "plan on local main only")
    ev = merge_evidence(repo, fetch=True)
    assert ev.ref is None
    assert ev.ref_error
    assert ev.landed_phases == {}
    assert ev.agentic_landed == frozenset()
    assert ev.complete_on_ref == frozenset()


def test_evidence_with_two_ambiguous_remotes_is_unknown(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "a.git", name="a")
    _add_remote(repo, tmp_path / "b.git", name="b")
    _publish(repo, remote="a")
    ev = merge_evidence(repo, fetch=False)
    assert ev.ref is None
    assert ev.ref_error is not None and "checkout.defaultRemote" in ev.ref_error


# --- merge_evidence: per-phase landing ---------------------------------------


def test_landed_phases_are_per_phase_and_local_only_phases_are_absent(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _write_plan(repo, "2026-02-01-part", [("agentic", True), ("agentic", False)])
    _commit(repo, "phase 1 landed, phase 2 not")
    _publish(repo)
    # Locally: phase 2 ticked and a phase 3 added and ticked — neither on the ref.
    _write_plan(repo, "2026-02-01-part", [("agentic", True), ("agentic", True), ("agentic", True)])
    ev = merge_evidence(repo, fetch=False)
    assert ev.landed_phases["2026-02-01-part"] == frozenset({1})
    assert "2026-02-01-part" not in ev.agentic_landed
    assert "2026-02-01-part" not in ev.complete_on_ref


def test_a_plan_not_on_the_ref_is_absent(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo)
    _write_plan(repo, "2026-02-02-new", [("agentic", True)])
    _commit(repo, "only on the branch")
    ev = merge_evidence(repo, fetch=False)
    assert "2026-02-02-new" not in ev.landed_phases
    assert ev.agentic_landed == frozenset()


def test_agentic_landed_ignores_an_open_trailing_manual_phase(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _write_plan(repo, "2026-02-03-goal", [("agentic", True), ("agentic", True), ("manual", False)])
    _write_plan(repo, "2026-02-04-all", [("agentic", True), ("manual", True)])
    _commit(repo, "two plans")
    _publish(repo)
    ev = merge_evidence(repo, fetch=False)
    assert ev.landed_phases["2026-02-03-goal"] == frozenset({1, 2})
    assert "2026-02-03-goal" in ev.agentic_landed
    assert "2026-02-03-goal" not in ev.complete_on_ref
    assert "2026-02-04-all" in ev.agentic_landed
    assert "2026-02-04-all" in ev.complete_on_ref


def test_a_manual_only_plan_is_landed_when_its_dir_is_on_the_ref(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _write_plan(repo, "2026-02-05-manual", [("manual", False)])
    _commit(repo, "manual-only plan")
    _publish(repo)
    ev = merge_evidence(repo, fetch=False)
    assert "2026-02-05-manual" in ev.agentic_landed
    assert "2026-02-05-manual" not in ev.complete_on_ref


def test_a_plan_the_parser_rejects_on_the_ref_is_reported_unparsed(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    plan_dir = _write_plan(repo, "2026-02-06-old", [("agentic", True)])
    meta = yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["a_key_no_fr_knows"] = 1  # extra="forbid": the current parser rejects it
    (plan_dir / "_meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    _write_plan(repo, "2026-02-07-fine", [("agentic", True)])
    _commit(repo, "one unparseable plan")
    _publish(repo)
    ev = merge_evidence(repo, fetch=False)
    assert ev.unparsed_on_ref == ("2026-02-06-old",)
    assert "2026-02-06-old" not in ev.landed_phases
    assert "2026-02-06-old" not in ev.agentic_landed
    assert ev.complete_on_ref == frozenset({"2026-02-07-fine"})


def test_a_ref_without_a_plans_tree_gives_empty_sets(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo)
    ev = merge_evidence(repo, fetch=False)
    assert ev.ref is not None
    assert ev.landed_phases == {}
    assert ev.agentic_landed == frozenset()
    assert ev.complete_on_ref == frozenset()
    assert ev.unparsed_on_ref == ()


# --- merge_evidence: fetch ---------------------------------------------------


def test_fetch_through_a_file_remote_sees_a_commit_pushed_after_the_last_fetch(
    tmp_path: Path,
) -> None:
    repo = _init(tmp_path / "r")
    bare = _add_remote(repo, tmp_path / "o.git")
    _publish(repo)
    # Someone else merges a complete plan to the remote.
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(bare), str(other)], check=True)
    _write_plan(other, "2026-03-01-merged", [("agentic", True)])
    _commit(other, "merged elsewhere")
    _git(other, "push", "-q", "origin", "HEAD:main")

    stale = merge_evidence(repo, fetch=False)
    assert "2026-03-01-merged" not in stale.complete_on_ref

    ev = merge_evidence(repo, fetch=True)
    assert ev.fetched is True
    assert ev.fetch_error is None
    assert "2026-03-01-merged" in ev.complete_on_ref


def test_a_real_fetch_failure_degrades_to_the_local_ref(tmp_path: Path) -> None:
    repo = _init(tmp_path / "r")
    bare = _add_remote(repo, tmp_path / "o.git")
    _write_plan(repo, "2026-03-02-done", [("agentic", True)])
    _commit(repo, "plan")
    _publish(repo)
    shutil.rmtree(bare)  # the remote is gone: fetch fails, the tracking ref stays
    ev = merge_evidence(repo, fetch=True)
    assert ev.fetched is False
    assert ev.fetch_error
    assert ev.ref is not None and ev.ref.ref == "origin/main"
    assert "2026-03-02-done" in ev.complete_on_ref


@pytest.mark.parametrize(
    "exc",
    [
        subprocess.CalledProcessError(128, ["git", "fetch"], stderr="fatal: offline"),
        subprocess.TimeoutExpired(["git", "fetch"], 30),
    ],
    ids=["fails", "times-out"],
)
def test_a_failing_fetch_seam_sets_fetch_error_and_still_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: Exception
) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _write_plan(repo, "2026-03-03-done", [("agentic", True)])
    _commit(repo, "plan")
    _publish(repo)
    calls: list[tuple[Path, str]] = []

    def boom(repo_root: Path, remote: str) -> None:
        calls.append((repo_root, remote))
        raise exc

    monkeypatch.setattr(archive_mod, "_fetch", boom)
    ev = merge_evidence(repo, fetch=True)
    assert calls and calls[0][1] == "origin"
    assert ev.fetched is False
    assert ev.fetch_error
    assert "2026-03-03-done" in ev.complete_on_ref


def test_fetch_false_never_calls_the_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo)

    def never(repo_root: Path, remote: str) -> None:
        raise AssertionError("fetch=False must not fetch")

    monkeypatch.setattr(archive_mod, "_fetch", never)
    assert merge_evidence(repo, fetch=False).fetched is False


def test_the_fetch_seam_is_prompt_free_tagless_and_time_boxed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(archive_mod.subprocess, "run", fake_run)
    archive_mod._fetch(tmp_path, "origin")
    cmd = seen["cmd"]
    assert isinstance(cmd, list)
    assert cmd[-4:] == ["fetch", "--quiet", "--no-tags", "origin"]
    env = seen["env"]
    assert isinstance(env, dict) and env["GIT_TERMINAL_PROMPT"] == "0"
    assert seen["timeout"] == 30
