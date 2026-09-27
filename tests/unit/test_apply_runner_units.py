"""A runner declares the units it takes; `fr apply --to` refuses one that takes no phases.

super-fr#644: `fr apply --to herdr` passed the name-only check, labelled phase
Issues `runner:herdr`, and every tick then refused each item — herdr takes
`unit="run"` work only — under a message that blamed the repo. `apply` could not
ask the runner, because a runner's unit limit lived only inside
`can_dispatch(item)`, which needs a built runner (vk and cncd cannot be built
outside their bridge). `Runner.units` is the declaration `apply` reads off the
registered class, before any forge call.
"""

from __future__ import annotations

from typing import Any, get_args

import pytest
from fr_dispatch.work_item import Unit


def _invoke_apply(tmp_path, monkeypatch, runner: str):
    from fr.cli import app
    from fr.commands import apply_cmd
    from typer.testing import CliRunner

    plans = tmp_path / "docs" / "superpowers" / "plans"
    (plans / "some-plan").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    forge_calls: list[str] = []

    def _no_forge() -> Any:
        forge_calls.append("gh")
        raise AssertionError("the forge client was built")

    monkeypatch.setattr(apply_cmd, "_make_gh_client", _no_forge)
    result = CliRunner().invoke(app, ["apply", "--all", "--to", runner])
    return result, result.output + (result.stderr or ""), forge_calls


def test_every_registered_runner_declares_the_units_it_takes():
    from fr_dispatch.registry import available_runners

    vocabulary = set(get_args(Unit))
    declared = {}
    for name, ep in available_runners().items():
        units = ep.load().units  # type: ignore[attr-defined]
        assert isinstance(units, frozenset) and units, (
            f"{name}: units must be a non-empty frozenset"
        )
        assert units <= vocabulary, f"{name}: {sorted(units - vocabulary)} is not a unit"
        declared[name] = units
    assert declared["vk"] == frozenset({"phase"})
    assert declared["cncd"] == frozenset({"phase"})
    assert declared["herdr"] == frozenset({"run"})


def test_apply_to_a_runner_that_takes_no_phases_refuses_before_the_forge(tmp_path, monkeypatch):
    result, out, forge_calls = _invoke_apply(tmp_path, monkeypatch, "herdr")

    assert result.exit_code == 2, out
    assert forge_calls == []
    assert "herdr" in out
    assert "phase" in out and "run" in out
    assert "unknown runner" not in out


def test_apply_to_a_runner_declaring_no_units_refuses(tmp_path, monkeypatch):
    import fr_dispatch.registry as registry

    class _Undeclared:
        name = "legacy"

    class _Ep:
        name = "legacy"

        def load(self) -> type:
            return _Undeclared

    monkeypatch.setattr(registry, "available_runners", lambda: {"legacy": _Ep()})
    result, out, forge_calls = _invoke_apply(tmp_path, monkeypatch, "legacy")

    assert result.exit_code == 2, out
    assert forge_calls == []
    assert "legacy" in out and "units" in out


@pytest.mark.parametrize("runner", ["vk", "cncd"])
def test_apply_to_a_phase_runner_passes_the_unit_check(tmp_path, monkeypatch, runner):
    result, out, forge_calls = _invoke_apply(tmp_path, monkeypatch, runner)

    # It gets as far as building the forge client — the unit check let it by.
    assert forge_calls == ["gh"], out


# ── tick: a can_dispatch refusal names its real reason ────────────────


def _tick_refusing(units: frozenset[str] | None):
    from fr_dispatch import tick

    from tests.unit.fakes import FakeGhClient
    from tests.unit.test_tick_workitem import (
        MINIMAL_PHASE_1_ID,
        FakeRunner,
        RecordingMetrics,
        _one_phase_plan,
        _ready,
    )

    plan, repo, n = _one_phase_plan()
    gh = FakeGhClient()
    _ready(gh, plan, repo, (n,))
    m = RecordingMetrics()
    runner = FakeRunner(unroutable={MINIMAL_PHASE_1_ID})
    if units is not None:
        runner.units = units  # type: ignore[attr-defined]
    result = tick(plan, gh, runner, metrics=m)
    return result, m, repo


def test_tick_names_the_unit_when_the_runner_does_not_take_it():
    result, m, _repo = _tick_refusing(frozenset({"run"}))

    assert result.errors == 1
    (failure,) = result.failures
    assert "unknown repo" not in failure
    assert "'phase'" in failure and "run" in failure and "'fake'" in failure
    assert m.reasons == ["unit_mismatch"]


def test_tick_does_not_claim_an_unknown_repo_it_cannot_know_about():
    """A refusal for any other reason names the runner, unit and repo — not a verdict."""
    result, m, repo = _tick_refusing(frozenset({"phase"}))

    (failure,) = result.failures
    assert "unknown repo" not in failure
    assert "'fake'" in failure and "'phase'" in failure and repr(repo) in failure
    assert m.reasons == ["unknown_repo"]
