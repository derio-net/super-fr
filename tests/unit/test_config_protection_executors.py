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
    for rel in files:
        if rel.endswith("candidate-install"):
            p = where / rel
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
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
