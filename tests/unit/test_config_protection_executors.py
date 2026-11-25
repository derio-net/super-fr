"""Every executor of executable configuration asks `fr.config.protection` first under quiet
and stealth (spec 2026-11-19-event-driven-a-la-carte R7, §C; plan findings
sec-1-self-attesting-config-branch and p1-r1).

The repos are real git repos with local bare origins. A local origin is no forge repository,
so under quiet it is NOT enforced by itself (the real path); an enforced answer comes from a
fake forge client serving the captured `pull-request-approved.json` reply.
"""

from __future__ import annotations

import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fr.config import protection
from fr.config.space import quiet_checkout

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_config_space import QUIET, _push_orphan

RULES = Path(__file__).resolve().parents[1] / "fixtures" / "github_rest" / "rules"
SLUG = "example-org/example-repo"
FIX = "protect fr-config with a ruleset requiring pull requests"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


class _Rules:
    """A forge client answering `branch_rules` with a captured reply, counting asks."""

    def __init__(self, name: str = "pull-request-approved.json") -> None:
        import json

        self.reply = json.loads((RULES / name).read_text())
        self.asked: list[tuple[str, str]] = []

    def branch_rules(self, repo: str, branch: str) -> Any:
        self.asked.append((repo, branch))
        return self.reply

    def required_check_names(self, repo: str, base: str) -> list[str]:
        return ["from-the-base"]


class _NeverAsked:
    def branch_rules(self, repo: str, branch: str) -> Any:
        raise AssertionError("under repo nothing asks the forge")

    def required_check_names(self, repo: str, base: str) -> list[str]:
        return ["from-the-base"]


INSTALL = """#!/bin/sh
touch "{sentinel}"
mkdir -p "$1/bin"
printf '#!/bin/sh\\necho fake\\n' > "$1/bin/fakefr"
chmod +x "$1/bin/fakefr"
echo fakefr
"""


def _quiet_with_config(tmp_path: Path, files: dict[str, str]) -> Path:
    """A quiet product checkout whose `fr-config` (pushed, fetched, and checked out at the
    fr-config worktree) holds *files* below `.fr/`, and whose old switch matches."""
    root = make_repo(tmp_path)
    _push_orphan(root, "fr", {"settings.yaml": QUIET})
    _push_orphan(root, "fr-config", {".fr/settings.yaml": QUIET, **files})
    git(root, "fetch", "-q", "origin", "+refs/heads/*:refs/remotes/origin/*")
    where = quiet_checkout(root)
    where.parent.mkdir(parents=True, exist_ok=True)
    git(root, "worktree", "add", "-q", "-b", "fr-config", str(where), "origin/fr-config")
    programs = [rel for rel in files if rel.endswith("candidate-install")]
    for rel in programs:
        p = where / rel
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
    if programs:  # the executable bit is on fr-config itself: the worktree is its tip
        git(where, "commit", "-qam", "executable")
        git(where, "push", "-q", "origin", "fr-config")
        git(root, "fetch", "-q", "origin", "+refs/heads/fr-config:refs/remotes/origin/fr-config")
    git(root, "checkout", "-q", "-b", "feat/q")
    return root


# --- the guard at a checkout ------------------------------------------------------------


def test_a_local_origin_under_quiet_is_not_enforced_and_says_the_fix(tmp_path: Path) -> None:
    root = _quiet_with_config(tmp_path, {})
    why = protection.refusal_at(root, None, "run post_merge")
    assert why is not None
    assert "run post_merge" in why and "not a forge repository" in why and FIX in why


def test_under_repo_the_checkout_guard_asks_nothing(tmp_path: Path) -> None:
    assert protection.refusal_at(make_repo(tmp_path), _NeverAsked(), "run post_merge") is None


def test_an_enforced_configuration_branch_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _quiet_with_config(tmp_path, {})
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    client = _Rules()
    assert protection.refusal_at(root, client, "run post_merge") is None
    assert client.asked == [(SLUG, "fr-config")]


# --- fr verification walk ----------------------------------------------------------------


def _manifest() -> Any:
    from fr.verification.model import StrategyManifest

    return StrategyManifest.model_validate(
        {
            "verification": "candidate",
            "schema": 1,
            "when": "pre-merge",
            "driver": "agent",
            "install": [".fr/candidate-install", "{prefix}", "{source}"],
            "source": "worktree",
        }
    )


def _walk(root: Path, forge: object | None = None, manifest: Any = None, rows: Any = ()) -> Any:
    from fr.verification.walk import run_walk

    return run_walk(
        repo_root=root, run="r", manifest=manifest or _manifest(), rows=rows, model="m",
        harness="h", code_tree="t", forge=forge,
    )  # fmt: skip


def test_the_walk_refuses_under_quiet_before_running_the_candidate_install(
    tmp_path: Path,
) -> None:
    from fr.verification.walk import WalkError

    sentinel = tmp_path / "ran"
    root = _quiet_with_config(
        tmp_path, {".fr/candidate-install": INSTALL.format(sentinel=sentinel)}
    )
    with pytest.raises(WalkError) as caught:
        _walk(root)
    assert "candidate install" in str(caught.value) and FIX in str(caught.value)
    assert not sentinel.exists()


def test_the_walk_runs_the_configuration_branchs_install_when_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = tmp_path / "ran"
    root = _quiet_with_config(
        tmp_path, {".fr/candidate-install": INSTALL.format(sentinel=sentinel)}
    )
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    _walk(root, forge=_Rules())
    assert sentinel.exists()


def test_a_scenario_program_in_the_configuration_space_is_refused_before_anything_runs(
    tmp_path: Path,
) -> None:
    """Security review: every argv[0] resolved into the configuration space passes the guard,
    not only the install's, and the refusal comes before the install runs."""
    from fr.verification.model import StrategyManifest
    from fr.verification.walk import WalkError

    installed = tmp_path / "installed"
    scenario_ran = tmp_path / "scenario-ran"
    root = _quiet_with_config(
        tmp_path, {".fr/candidate-install": f"#!/bin/sh\ntouch {scenario_ran}\n"}
    )
    (root / "install.sh").write_text(INSTALL.format(sentinel=installed))
    (root / "install.sh").chmod(0o755)
    (root / "s.sh").write_text("#!/bin/sh\n")
    manifest = StrategyManifest.model_validate(
        {
            "verification": "candidate", "schema": 1, "when": "pre-merge", "driver": "agent",
            "install": ["./install.sh", "{prefix}"],
            "scenario": [".fr/candidate-install", "{scenario}"], "source": "worktree",
        }
    )  # fmt: skip
    row = SimpleNamespace(id="r1", scenario="s.sh")
    with pytest.raises(WalkError) as caught:
        _walk(root, manifest=manifest, rows=(row,))
    assert FIX in str(caught.value)
    assert not installed.exists() and not scenario_ran.exists()


# --- the reviewed tip, not a local copy of it (review p3-r2, decision p3-run-the-checked-tip)


def _protected_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    sentinel = tmp_path / "ran"
    root = _quiet_with_config(
        tmp_path, {".fr/candidate-install": INSTALL.format(sentinel=sentinel)}
    )
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    return root, sentinel


def test_a_local_edit_in_the_fr_config_worktree_is_refused_and_nothing_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.verification.walk import WalkError

    root, sentinel = _protected_install(tmp_path, monkeypatch)
    edited = quiet_checkout(root) / ".fr" / "candidate-install"
    edited.write_text(edited.read_text() + "echo unreviewed\n")
    with pytest.raises(WalkError) as caught:
        _walk(root, forge=_Rules())
    text = str(caught.value)
    assert "not the reviewed tip" in text and ".fr/candidate-install" in text
    assert "pull request" in text and "stash" in text
    assert not sentinel.exists()


def test_an_untracked_file_in_the_fr_config_worktree_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.verification.walk import WalkError

    root, sentinel = _protected_install(tmp_path, monkeypatch)
    (quiet_checkout(root) / ".fr" / "planted").write_text("x\n")
    with pytest.raises(WalkError, match="planted"):
        _walk(root, forge=_Rules())
    assert not sentinel.exists()


def test_a_local_commit_ahead_of_origin_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.verification.walk import WalkError

    root, sentinel = _protected_install(tmp_path, monkeypatch)
    where = quiet_checkout(root)
    (where / ".fr" / "candidate-install").write_text("#!/bin/sh\ntouch unreviewed\n")
    git(where, "commit", "-qam", "unreviewed")
    with pytest.raises(WalkError) as caught:
        _walk(root, forge=_Rules())
    assert "1 local commit(s) ahead of origin/fr-config" in str(caught.value)
    assert "reset --keep origin/fr-config" in str(caught.value)
    assert not sentinel.exists()


def test_a_worktree_behind_the_fetched_tip_is_refused_with_the_fast_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The walk fetches first: a change merged on origin since the last fetch is the
    reviewed tip, and the worktree that lacks it is not what was reviewed."""
    from fr.verification.walk import WalkError

    root, sentinel = _protected_install(tmp_path, monkeypatch)
    other = tmp_path / "other"
    origin = git(root, "remote", "get-url", "origin").strip()
    git(tmp_path, "clone", "-q", "--branch", "fr-config", origin, str(other))
    (other / ".fr" / "lenses.yaml").write_text("disable: []\n")
    git(other, "add", "-A")
    git(other, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "merged")
    git(other, "push", "-q", "origin", "fr-config")
    with pytest.raises(WalkError) as caught:
        _walk(root, forge=_Rules())
    assert "1 commit(s) behind origin/fr-config" in str(caught.value)
    assert "merge --ff-only origin/fr-config" in str(caught.value)
    assert not sentinel.exists()


def test_a_failed_fetch_of_the_configuration_branch_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.verification.walk import WalkError

    root, sentinel = _protected_install(tmp_path, monkeypatch)
    git(root, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    with pytest.raises(WalkError, match="cannot fetch fr-config"):
        _walk(root, forge=_Rules())
    assert not sentinel.exists()


def test_no_fetch_reads_the_last_fetched_tip_and_says_it_may_be_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.config.space import config_space

    root, _ = _protected_install(tmp_path, monkeypatch)
    git(root, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    protection.require_checked_tip(
        config_space(root), _Rules(), "run x", working_tree=True, no_fetch=True
    )
    assert "may be stale" in capsys.readouterr().err


def test_a_clean_worktree_at_the_fetched_tip_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, sentinel = _protected_install(tmp_path, monkeypatch)
    _walk(root, forge=_Rules())
    assert sentinel.exists()


def test_under_stealth_the_configuration_clone_must_be_its_fetched_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stealth configuration clone fetches `<branch>-config` itself and is held to the
    same rule as the quiet worktree."""
    from fr.config.space import ConfigSpace

    track = tmp_path / "track.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main-config", str(track))
    seed = tmp_path / "seed"
    git(tmp_path, "init", "-q", "-b", "main-config", str(seed))
    (seed / "local--work" / ".fr").mkdir(parents=True)
    (seed / "local--work" / ".fr" / "ops.yaml").write_text("env_passthrough: [A]\n")
    git(seed, "add", "-A")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "seed")
    git(seed, "remote", "add", "origin", str(track))
    git(seed, "push", "-q", "origin", "main-config")
    clone = tmp_path / "stealth--track--main-config"
    git(tmp_path, "clone", "-q", "-b", "main-config", str(track), str(clone))
    space = ConfigSpace(
        "stealth", clone / "local--work" / ".fr", clone, tmp_path, "origin/main-config",
        "local--work/.fr", "git@github.com:example-org/track.git@main",
    )  # fmt: skip
    monkeypatch.setattr(protection, "_default_client", lambda s: _Rules())
    protection.require_checked_tip(space, None, "run ops", working_tree=True)
    protection.forget()
    (clone / "local--work" / ".fr" / "ops.yaml").write_text("env_passthrough: [B]\n")
    with pytest.raises(protection.UncheckedTipError, match="local--work/.fr/ops.yaml"):
        protection.require_checked_tip(space, None, "run ops", working_tree=True)


def test_ops_config_from_a_dirty_fr_config_worktree_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.ops.load import OpsLoadError, load_ops_config

    root = _quiet_with_config(tmp_path, {".fr/ops.yaml": "env_passthrough: [SECRET]\n"})
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    monkeypatch.setattr(protection, "_default_client", lambda space: _Rules())
    (quiet_checkout(root) / ".fr" / "ops.yaml").write_text("env_passthrough: [OTHER]\n")
    with pytest.raises(OpsLoadError, match="not the reviewed tip"):
        load_ops_config(root)


def test_an_exit_remap_from_a_dirty_fr_config_worktree_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.verification.rows import load_remap

    root = _quiet_with_config(tmp_path, {".fr/triage.yaml": "exit:\n  gates:\n    tester: none\n"})
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    monkeypatch.setattr(protection, "_default_client", lambda space: _Rules())
    assert load_remap(root)[0]  # clean: read
    protection.forget()
    (quiet_checkout(root) / ".fr" / "triage.yaml").write_text(
        "exit:\n  gates:\n    tester: none\n    devops: none\n"
    )
    remap, why = load_remap(root)
    assert remap == {} and why is not None and "not the reviewed tip" in why


def test_under_repo_the_walk_asks_nothing(tmp_path: Path) -> None:
    sentinel = tmp_path / "ran"
    root = make_repo(tmp_path)
    path = root / ".fr" / "candidate-install"
    path.parent.mkdir()
    path.write_text(INSTALL.format(sentinel=sentinel))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    _walk(root, forge=_NeverAsked())
    assert sentinel.exists()


# --- the merge queue's gate_checks -------------------------------------------------------


def test_the_queue_refuses_gate_checks_from_an_unprotected_fr_config(tmp_path: Path) -> None:
    from fr.triage.errors import TriageError
    from fr.triage.gitseam import Checkout
    from fr.triage.queue_exec import required_names

    root = _quiet_with_config(tmp_path, {".fr/ci.yaml": "gate_checks: [anything]\n"})
    with pytest.raises(TriageError) as caught:
        required_names(_NeverAsked(), Checkout(root), "o/r", "main")  # type: ignore[arg-type]
    assert "gate_checks" in str(caught.value) and FIX in str(caught.value)


def test_the_queue_gates_on_gate_checks_from_a_protected_fr_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.gitseam import Checkout
    from fr.triage.queue_exec import required_names

    root = _quiet_with_config(tmp_path, {".fr/ci.yaml": "gate_checks: [reviewed]\n"})
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    got = required_names(_Rules(), Checkout(root), "o/r", "main")  # type: ignore[arg-type]
    assert got == ["reviewed"]


def test_under_repo_the_queue_reads_gate_checks_without_asking(tmp_path: Path) -> None:
    from fr.triage.gitseam import Checkout
    from fr.triage.queue_exec import required_names

    root = make_repo(tmp_path)
    (root / ".fr").mkdir()
    (root / ".fr/ci.yaml").write_text("gate_checks: [mine]\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "ci")
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    got = required_names(_NeverAsked(), Checkout(root), "o/r", "main")  # type: ignore[arg-type]
    assert got == ["mine"]


# --- `.fr/ci.yaml`'s gate_checks, tests and fast_tier (review p3-r1) --------------------

CI_ALL = "gate_checks: [config-gate]\ntests: ci\nfast_tier: pytest --since {base}\n"


def _executor_step() -> Any:
    from fr.workflow.model import Step

    return Step.model_validate(
        {"id": "implement-phase", "kind": "agent", "agent": "super-fr:fr-phase-executor"}
    )


def _deliver_step() -> Any:
    from fr.workflow.model import Step

    return Step.model_validate({"id": "deliver", "kind": "agent", "evidence": ["tests", "docs"]})


def test_unprotected_ci_keys_are_ignored_and_said_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Under quiet an unprotected `fr-config` cannot relax `deliver`'s suite evidence, put a
    command into a brief, or choose the gate set: the keys are ignored, with the reason."""
    from fr.commands.run_cmd import _tests_brief
    from fr.run.ci_evidence import declared_fast_tier, declared_gates, declared_tests_mode

    root = _quiet_with_config(tmp_path, {".fr/ci.yaml": CI_ALL})
    capsys.readouterr()
    assert declared_tests_mode(root) is None
    assert declared_fast_tier(root) is None
    assert declared_gates(root, "main") is None
    assert _tests_brief(root, _executor_step()) == {}
    assert _tests_brief(root, _deliver_step()) == {}
    err = capsys.readouterr().err
    said = [line for line in err.splitlines() if "ignoring" in line and "ci.yaml" in line]
    assert len(said) == 1, err
    assert "gate_checks, tests, fast_tier" in said[0] and FIX in said[0]
    assert "local full-suite log" in said[0]


def test_unprotected_gate_checks_fall_back_to_the_bases_required_checks(tmp_path: Path) -> None:
    from fr.run.ci_evidence import _gate_names

    root = _quiet_with_config(tmp_path, {".fr/ci.yaml": CI_ALL})
    assert _gate_names(root, _Rules(), "o/r", "main") == ["from-the-base"]


def test_protected_ci_keys_are_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.commands.run_cmd import _tests_brief
    from fr.run.ci_evidence import declared_fast_tier, declared_gates, declared_tests_mode

    root = _quiet_with_config(tmp_path, {".fr/ci.yaml": CI_ALL})
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    client = _Rules()
    monkeypatch.setattr(protection, "_default_client", lambda space: client)
    assert declared_tests_mode(root) == "ci"
    assert declared_fast_tier(root) == "pytest --since {base}"
    assert declared_gates(root, "main") == ["config-gate"]
    assert _tests_brief(root, _executor_step())["tests"]["mode"] == "ci"
    assert client.asked and set(client.asked) == {(SLUG, "fr-config")}


def test_a_failed_protection_read_refuses_the_ci_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr import gh as _gh
    from fr.run.ci_evidence import CiEvidenceRefused, declared_gates, declared_tests_mode

    class _Broken:
        def branch_rules(self, repo: str, branch: str) -> Any:
            raise _gh.GhError("gh: Server Error (HTTP 502)", stderr="x")

    root = _quiet_with_config(tmp_path, {".fr/ci.yaml": CI_ALL})
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    monkeypatch.setattr(protection, "_default_client", lambda space: _Broken())
    with pytest.raises(CiEvidenceRefused, match="HTTP 502"):
        declared_tests_mode(root)
    with pytest.raises(CiEvidenceRefused, match="HTTP 502"):
        declared_gates(root, "main")


def test_a_ci_yaml_without_guarded_keys_asks_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.run.ci_evidence import declared_tests_mode

    root = _quiet_with_config(tmp_path, {".fr/ci.yaml": "other: 1\n"})
    monkeypatch.setattr(protection, "_default_client", lambda space: _NeverAsked())
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    assert declared_tests_mode(root) is None


def test_under_repo_the_ci_keys_are_read_without_asking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.run.ci_evidence import declared_tests_mode

    root = make_repo(tmp_path)
    (root / ".fr").mkdir()
    (root / ".fr/ci.yaml").write_text(CI_ALL)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "ci")
    monkeypatch.setattr(protection, "_default_client", lambda space: _NeverAsked())
    assert declared_tests_mode(root) == "ci"


# --- the driver: post_merge and the queue's hold -------------------------------------


def _driver(tmp_path: Path, root: Path) -> Any:
    from fr.commands import triage_batch_cmd

    state = tmp_path / "state"
    state.mkdir()
    return triage_batch_cmd._Driver(
        triage_batch_cmd._scope("o/r", None), state, named=None, checkouts={"o/r": root},
        max_inflight=1, yes=True,
    )  # fmt: skip


def test_the_drivers_post_merge_is_held_on_an_unprotected_fr_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import triage_batch_cmd
    from fr.triage.model import TriageConfig

    root = _quiet_with_config(tmp_path, {})
    driver = _driver(tmp_path, root)
    ran: list[list[str]] = []
    checkout = SimpleNamespace(
        path=root, fast_forward=lambda **k: None, run_command=lambda argv: ran.append(argv)
    )
    monkeypatch.setattr(driver, "checkout", lambda repo: checkout)
    monkeypatch.setattr(driver, "client", lambda facts, repo: object())
    monkeypatch.setattr(triage_batch_cmd, "_fresh_config", lambda *a, **k: "origin/main")
    facts = SimpleNamespace(config_for=lambda repo: TriageConfig(post_merge=["./deploy"]))
    batch = SimpleNamespace(id="b1", launch=SimpleNamespace(runner="herdr"), events=[])
    line, did = driver._post_merge(facts, None, batch, "o/r")
    assert did is False and ran == []
    assert line.startswith("post_merge held:") and FIX in line


def test_the_drivers_queue_is_held_on_an_unprotected_fr_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import triage_batch_cmd

    root = _quiet_with_config(tmp_path, {})
    driver = _driver(tmp_path, root)
    monkeypatch.setattr(driver, "client", lambda facts, repo: object())
    monkeypatch.setattr(driver, "checkout", lambda repo: SimpleNamespace(path=root))
    monkeypatch.setattr(
        triage_batch_cmd._Driver, "_base_rules",
        lambda self, facts, repo: pytest.fail("held before the base rules are read"),
    )  # fmt: skip
    from fr.triage.model import QueueBlock, TriageConfig

    facts = SimpleNamespace(config_for=lambda repo: TriageConfig(queue=QueueBlock(ci="push")))
    why = driver._queue_refusal(facts, "o/r")
    assert why is not None and "merge queue" in why and FIX in why


# --- fr ops -----------------------------------------------------------------------------


def test_ops_config_from_an_unprotected_fr_config_refuses(tmp_path: Path) -> None:
    from fr.ops.load import OpsLoadError, load_ops_config

    root = _quiet_with_config(tmp_path, {".fr/ops.yaml": "env_passthrough: [SECRET]\n"})
    with pytest.raises(OpsLoadError) as caught:
        load_ops_config(root)
    assert "ops" in str(caught.value) and FIX in str(caught.value)


def test_ops_config_from_a_protected_fr_config_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.ops.load import load_ops_config

    root = _quiet_with_config(tmp_path, {".fr/ops.yaml": "env_passthrough: [SECRET]\n"})
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    monkeypatch.setattr(protection, "_default_client", lambda space: _Rules())
    assert load_ops_config(root).env_passthrough == ("SECRET",)


def test_no_ops_file_under_quiet_asks_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.ops.load import OpsConfig, load_ops_config

    root = _quiet_with_config(tmp_path, {})
    monkeypatch.setattr(protection, "_default_client", lambda space: _NeverAsked())
    assert load_ops_config(root) == OpsConfig()


def test_the_ops_gate_will_not_release_to_a_queue_an_unprotected_fr_config_declares(
    tmp_path: Path,
) -> None:
    from fr.commands.ops_gate_cmd import HostCheckout
    from fr.ops.gate import StageFailed

    root = _quiet_with_config(tmp_path, {".fr/triage.yaml": "queue:\n  ci: push\n"})
    with pytest.raises(StageFailed) as caught:
        HostCheckout(root).queue_configured("main")
    assert FIX in str(caught.value)


# --- the gate remap (`exit:`) ---------------------------------------------------------


def test_an_unprotected_exit_remap_is_ignored_with_the_reason(tmp_path: Path) -> None:
    from fr.verification.rows import load_remap

    root = _quiet_with_config(tmp_path, {".fr/triage.yaml": "exit:\n  gates:\n    live: none\n"})
    remap, why = load_remap(root)
    assert remap == {}
    assert why is not None and FIX in why


def test_a_protected_exit_remap_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.verification.rows import load_remap

    root = _quiet_with_config(tmp_path, {".fr/triage.yaml": "exit:\n  gates:\n    live: none\n"})
    monkeypatch.setattr(protection, "_origin_slug", lambda r: SLUG)
    monkeypatch.setattr(protection, "_default_client", lambda space: _Rules())
    assert load_remap(root) == ({"live": "none"}, None)


# --- the driver's freshness check reads the configuration branch ---------------------


def _facts(config: Any) -> Any:
    return SimpleNamespace(config={"o/r": config})


def test_the_freshness_check_reads_fr_config_and_leaves_out_what_collect_dropped(
    tmp_path: Path,
) -> None:
    """Under quiet the collected config came from fr-config, so it is compared with
    fr-config's; collect dropped the guarded keys (unprotected), so they are no change."""
    from fr.commands.triage_batch_cmd import _config_fresh
    from fr.triage.gitseam import Checkout
    from fr.triage.model import TriageConfig

    text = "post_merge: [./deploy]\nstale_dispatch_days: 9\n"
    root = _quiet_with_config(tmp_path, {".fr/triage.yaml": text})
    dropped = TriageConfig(stale_dispatch_days=9)
    assert _config_fresh(Checkout(root), _facts(dropped), "o/r") == "origin/main"


def test_the_freshness_check_still_sees_a_change_under_quiet(tmp_path: Path) -> None:
    from fr.commands.triage_batch_cmd import _config_fresh
    from fr.triage.errors import TriageError
    from fr.triage.gitseam import Checkout
    from fr.triage.model import TriageConfig

    root = _quiet_with_config(tmp_path, {".fr/triage.yaml": "post_merge: [./deploy]\n"})
    with pytest.raises(TriageError, match="re-collect"):  # collected with a different command
        _config_fresh(Checkout(root), _facts(TriageConfig(post_merge=["./other"])), "o/r")
    with pytest.raises(TriageError, match="re-collect"):  # a non-guarded key moved
        _config_fresh(Checkout(root), _facts(TriageConfig(stale_dispatch_days=1)), "o/r")
    full = TriageConfig(post_merge=["./deploy"])
    assert _config_fresh(Checkout(root), _facts(full), "o/r") == "origin/main"
