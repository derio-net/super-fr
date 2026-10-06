"""`fr run advance`'s pre-dispatch binding guard (spec
2026-10-06-model-binding-churn §C, R8, R9, R11), on both dispatch paths.

OpenCode is the harness throughout (`FR_HARNESS`), the prober is scripted
(`tests/unit/binding_fakes.py`), and the user layer lives under a tmp
`XDG_CONFIG_HOME`, so nothing here touches a real provider or config.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, parse_journal
from fr.run.model import load_run_state, run_path

from tests.unit import binding_fakes as bf
from tests.unit.test_run_cli import (
    _GROUPED_SHAPE,
    _attempts_by_unit,
    _invoke,
    _repo,
    _seed_journal,
    _started_grouped_with_plan,
    _write_repo_models,
    _write_shape,
)

PLAN_SLUG = "2026-05-09-fixture-minimal"
SPEC_REL = "docs/superpowers/specs/2026-10-06-x-design.md"
USER_STD = "opencode:\n  mechanical: prov/mech\n  standard: prov/std\n  hard: prov/hard\n"
CATALOGUE = [
    bf.ent("mech", "m", "2026-01-01", 5.0),
    bf.ent("std", "s", "2026-01-01", 10.0),
    bf.ent("std2", "s", "2026-04-01", 10.0),
    bf.ent("hard", "h", "2026-01-01", 20.0),
    bf.ent("hard2", "h", "2026-04-01", 20.0),
]

_FLAT_SHAPE = """
workflow: flat
schema: 1
unit: run
steps:
  - id: write-spec
    kind: agent
    emits: [spec]
  - id: spec-review
    kind: agent
    agent: super-fr:fr-spec-reviewer
    tier: hard
    needs: [spec]
"""


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("FR_HARNESS", "opencode")
    return tmp_path


def _grouped(tmp_path: Path, *, phase_tier: str | None = "standard", strip_tier: bool = False):
    """A run at `implement`, its one phase on `phase_tier`, the plan journal seeded."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, phase_tier=phase_tier, strip_tier=strip_tier)
    _seed_journal(repo, shipped)
    return repo, shipped


def _flat(tmp_path: Path):
    """A run whose next step is the flat `spec-review` (`tier: hard`), with a
    spec emitted and no plan artifact."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "flat", _FLAT_SHAPE)
    spec = repo / SPEC_REL
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# x\n")
    _invoke(repo, shipped, ["run", "start", "flat", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])
    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "write-spec", "--state", "done"]
        + ["--emitted", f"spec={SPEC_REL}"],
    )
    assert result.exit_code == 0, result.output
    return repo, shipped


def _plan_journal(repo: Path) -> Path:
    return journal_path(repo, "plan", PLAN_SLUG)


def _advance(repo: Path, shipped: Path):
    return _invoke(repo, shipped, ["run", "advance", "r1"])


def _head_files(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "show", "--name-only", "--format=", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return set(out.split())


# ---------------------------------------------------------------- (a) grouped


def test_a_dead_user_binding_is_substituted_before_a_grouped_dispatch(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models = bf.user_models(env, USER_STD)
    agent = bf.agent_file(env, "standard", "prov/std")
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, dead={"prov/std": None}))
    repo, shipped = _grouped(env)

    result = _advance(repo, shipped)

    assert result.exit_code == 0, result.output
    assert (
        "SUBSTITUTED opencode/standard: prov/std → prov/std2 "
        "(reason: retired, decider: autonomous, rule: family)"
    ) in result.output
    assert "standard: prov/std2" in models.read_text()
    assert "model: prov/std2" in agent.read_text()
    # the dispatch record carries the model that will actually run
    (attempt,) = _attempts_by_unit(load_run_state(repo, "r1").steps["implement"])["phase/1/code"]
    assert attempt.model == "prov/std2"
    entry = next(
        e
        for e in parse_journal(_plan_journal(repo).read_text())
        if e.id == "model-substitution-standard-1"
    )
    assert entry.kind == "decision"
    assert entry.phase == 1
    for field in (
        "old: prov/std",
        "new: prov/std2",
        "reason: retired",
        "decider: autonomous",
        "rule: family",
        "price ratio: ×1.0",
    ):
        assert field in entry.body, entry.body
    # recorded iff applied, and in the same commit as the cursor move
    head = _head_files(repo)
    assert str(_plan_journal(repo).relative_to(repo)) in head
    assert str(run_path(repo, "r1").relative_to(repo)) in head


# ------------------------------------------------------------------- (b) flat


def test_a_flat_tiered_step_gets_the_same_guard(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models = bf.user_models(env, USER_STD)
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, dead={"prov/hard": None}))
    repo, shipped = _flat(env)

    result = _advance(repo, shipped)

    assert result.exit_code == 0, result.output
    assert "SUBSTITUTED opencode/hard: prov/hard → prov/hard2" in result.output
    assert "hard: prov/hard2" in models.read_text()
    ((attempt,),) = _attempts_by_unit(load_run_state(repo, "r1").steps["spec-review"]).values()
    assert attempt.model == "prov/hard2"


# ------------------------------------------- (c) no autonomous pick: refuse


@pytest.mark.parametrize(
    ("catalogue", "hint", "named"),
    [
        # the only successor costs 3x: operator-only
        (
            [*CATALOGUE[:2], bf.ent("std2", "s", "2026-04-01", 30.0), *CATALOGUE[3:]],
            None,
            "prov/std2",
        ),
        # no entry, no snapshot: only the provider's hint, never autonomous
        ([CATALOGUE[0], *CATALOGUE[3:]], "std9", "prov/std9"),
    ],
    ids=["price-ratio-above-2", "hint-rule"],
)
def test_a_dead_binding_with_no_autonomous_pick_refuses_and_writes_nothing(
    env: Path, monkeypatch: pytest.MonkeyPatch, catalogue, hint, named
) -> None:
    models = bf.user_models(env, USER_STD)
    bf.install(monkeypatch, bf.ScriptedProber(catalogue, dead={"prov/std": hint}))
    repo, shipped = _grouped(env)
    cursor = run_path(repo, "r1").read_bytes()
    journal = _plan_journal(repo).read_bytes()

    result = _advance(repo, shipped)

    assert result.exit_code == 2, result.output
    assert named in result.output
    assert "tried" in result.output
    assert "fr models set --harness opencode --tier standard" in result.output
    assert "dispatch brief" not in result.output and '"run":' not in result.output
    assert run_path(repo, "r1").read_bytes() == cursor
    assert _plan_journal(repo).read_bytes() == journal
    assert models.read_text() == USER_STD
    assert load_run_state(repo, "r1").steps["implement"].state != "running"


# ------------------------------------------------- (d) repo layer: never rewritten


def test_a_dead_repo_layer_binding_refuses_naming_the_file(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, dead={"prov/std": None}))
    repo, shipped = _grouped(env)
    _write_repo_models(repo, "opencode:\n  standard: prov/std\n")
    repo_models = (repo / "docs/superpowers/models.yaml").read_bytes()
    cursor = run_path(repo, "r1").read_bytes()
    journal = _plan_journal(repo).read_bytes()

    result = _advance(repo, shipped)

    assert result.exit_code == 2, result.output
    assert "docs/superpowers/models.yaml" in result.output
    assert (repo / "docs/superpowers/models.yaml").read_bytes() == repo_models
    assert not (env / ".config" / "fr" / "models.yaml").exists()
    assert run_path(repo, "r1").read_bytes() == cursor
    assert _plan_journal(repo).read_bytes() == journal


# ---------------------------------------------------------- (e) unknown: warn


def test_an_unknown_verdict_warns_and_dispatches(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bf.user_models(env, USER_STD)
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, unknown=("prov/std",)))
    repo, shipped = _grouped(env)

    result = _advance(repo, shipped)

    assert result.exit_code == 0, result.output
    assert "warning" in result.output and "prov/std" in result.output
    assert "dispatch" in result.output and '"run":' in result.output
    assert "SUBSTITUTED" not in result.output


# ----------------------------------------- (f) nothing to check: no probe at all


def test_a_unit_with_no_tier_is_never_probed(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bf.user_models(env, USER_STD)
    prober = bf.ScriptedProber(CATALOGUE, dead={"prov/std": None})
    bf.install(monkeypatch, prober)
    repo, shipped = _grouped(env, phase_tier=None, strip_tier=True)
    prober.probed.clear()

    result = _advance(repo, shipped)

    assert result.exit_code == 0, result.output
    assert prober.probed == []


def test_a_harness_other_than_opencode_is_never_probed(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    bf.user_models(env, "claude-code:\n  standard: claude-sonnet-5\n")
    prober = bf.ScriptedProber(CATALOGUE, dead={"claude-sonnet-5": None})
    bf.install(monkeypatch, prober, any_harness=True)
    repo, shipped = _grouped(env)
    prober.probed.clear()

    result = _advance(repo, shipped)

    assert result.exit_code == 0, result.output
    assert prober.probed == []


# ------------------------------------------- (g) a failed apply is not recorded


def test_a_failed_apply_restores_both_files_and_exits_2(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.bindings.apply as apply_mod

    models = bf.user_models(env, USER_STD)
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, dead={"prov/std": None}))
    repo, shipped = _grouped(env)
    cursor = run_path(repo, "r1").read_bytes()
    journal = _plan_journal(repo).read_bytes()

    def half_write(path: Path, harness: str, tier: str, model: str) -> None:
        path.write_text("half written")
        raise OSError("disk full")

    monkeypatch.setattr(apply_mod, "set_binding", half_write)

    result = _advance(repo, shipped)

    assert result.exit_code == 2, result.output
    assert "SUBSTITUTION NOT APPLIED prov/std → prov/std2: disk full" in result.output
    assert models.read_text() == USER_STD
    assert _plan_journal(repo).read_bytes() == journal
    assert run_path(repo, "r1").read_bytes() == cursor
    assert "SUBSTITUTED opencode" not in result.output


# ------------------------------------------ (h) no plan yet: the spec journal


def test_a_run_with_no_plan_records_the_substitution_in_its_spec_journal(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bf.user_models(env, USER_STD)
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, dead={"prov/hard": None}))
    repo, shipped = _flat(env)

    result = _advance(repo, shipped)

    assert result.exit_code == 0, result.output
    spec_journal = journal_path(repo, "spec", "2026-10-06-x")
    (entry,) = [
        e for e in parse_journal(spec_journal.read_text()) if e.id == "model-substitution-hard-1"
    ]
    assert entry.kind == "decision"
    assert "decider: autonomous" in entry.body
    assert str(spec_journal.relative_to(repo)) in _head_files(repo)


# ---------------------------------------- review p2: cost, partial applies, ids


def test_a_live_binding_at_dispatch_reads_no_catalogue_and_probes_no_offer(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r1: the guard only needs a verdict. `std2` is a newer same-family
    model (an offer `check` would probe); dispatch must not spend on it."""
    bf.user_models(env, USER_STD)
    prober = bf.ScriptedProber(CATALOGUE)
    bf.install(monkeypatch, prober)
    repo, shipped = _grouped(env)
    _clear_probe_cache()  # `run start` cached the verdict; make dispatch ask
    prober.probed.clear()
    prober.catalogued.clear()

    result = _advance(repo, shipped)

    assert result.exit_code == 0, result.output
    assert prober.catalogued == []
    assert prober.probed == ["prov/std"]


def test_a_dispatched_tier_agent_file_left_unrewritten_is_not_a_substitution(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r2: `materialize_agents` reports a file it cannot rewrite rather
    than raising; for the tier being dispatched that is a failed apply."""
    models = bf.user_models(env, USER_STD)
    agent = bf.agent_file(env, "standard", "prov/std", anchor=False)
    agent_bytes = agent.read_bytes()
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, dead={"prov/std": None}))
    repo, shipped = _grouped(env)
    cursor = run_path(repo, "r1").read_bytes()
    journal = _plan_journal(repo).read_bytes()

    result = _advance(repo, shipped)

    assert result.exit_code == 2, result.output
    assert "SUBSTITUTION NOT APPLIED prov/std → prov/std2" in result.output
    assert "mode: subagent" in result.output
    assert "SUBSTITUTED opencode" not in result.output
    assert models.read_text() == USER_STD
    assert agent.read_bytes() == agent_bytes
    assert _plan_journal(repo).read_bytes() == journal
    assert run_path(repo, "r1").read_bytes() == cursor


def test_a_raising_materialise_restores_and_rematerialises_the_old_binding(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r4: `materialize_agents` raising after `set_binding` wrote."""
    import fr.bindings.apply as apply_mod

    models = bf.user_models(env, USER_STD)
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, dead={"prov/std": None}))
    repo, shipped = _grouped(env)
    cursor = run_path(repo, "r1").read_bytes()
    journal = _plan_journal(repo).read_bytes()
    real = apply_mod.materialize_agents
    seen: list[str | None] = []

    def flaky(config_home, *, models_cfg):
        seen.append(models_cfg.get("opencode", {}).get("standard"))
        if len(seen) == 1:
            raise OSError("agent dir vanished")
        return real(config_home, models_cfg=models_cfg)

    monkeypatch.setattr(apply_mod, "materialize_agents", flaky)

    result = _advance(repo, shipped)

    assert result.exit_code == 2, result.output
    assert "SUBSTITUTION NOT APPLIED prov/std → prov/std2: agent dir vanished" in result.output
    assert seen == ["prov/std2", "prov/std"]  # the re-materialise is of the restored map
    assert models.read_text() == USER_STD
    assert _plan_journal(repo).read_bytes() == journal
    assert run_path(repo, "r1").read_bytes() == cursor


def test_a_flat_path_refusal_leaves_the_cursor_byte_identical(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r4: the flat path refuses before anything is saved, no brief."""
    catalogue = [*CATALOGUE[:4], bf.ent("hard2", "h", "2026-04-01", 50.0)]
    bf.user_models(env, USER_STD)
    bf.install(monkeypatch, bf.ScriptedProber(catalogue, dead={"prov/hard": None}))
    repo, shipped = _flat(env)
    cursor = run_path(repo, "r1").read_bytes()

    result = _advance(repo, shipped)

    assert result.exit_code == 2, result.output
    assert "prov/hard2" in result.output
    assert "dispatch brief" not in result.output and '"run":' not in result.output
    assert run_path(repo, "r1").read_bytes() == cursor
    assert load_run_state(repo, "r1").steps["spec-review"].state != "running"


def test_the_guard_runs_on_redispatch(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """p2-r4: `--redispatch` re-opens a unit, so it dispatches on a binding too."""
    models = bf.user_models(env, USER_STD)
    prober = bf.ScriptedProber(CATALOGUE)
    bf.install(monkeypatch, prober)
    repo, shipped = _grouped(env)
    assert _advance(repo, shipped).exit_code == 0
    prober.dead["prov/std"] = None
    _clear_probe_cache()

    result = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert result.exit_code == 0, result.output
    assert "SUBSTITUTED opencode/standard: prov/std → prov/std2" in result.output
    assert "standard: prov/std2" in models.read_text()


def test_two_substitutions_of_one_tier_get_distinct_ids(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r3: the second substitution of `standard` in one run is `-2`."""
    catalogue = [*CATALOGUE, bf.ent("std3", "s", "2026-06-01", 10.0)]
    bf.user_models(env, USER_STD)
    prober = bf.ScriptedProber(catalogue, dead={"prov/std": None, "prov/std3": None})
    bf.install(monkeypatch, prober)
    repo, shipped = _grouped(env)
    assert _advance(repo, shipped).exit_code == 0  # std (dead) -> std2
    done = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1"] + ["--state", "done"],
    )
    assert done.exit_code == 0, done.output
    prober.dead["prov/std2"] = None
    del prober.dead["prov/std3"]
    _clear_probe_cache()

    result = _advance(repo, shipped)  # peer-review: std2 (dead) -> std3

    assert result.exit_code == 0, result.output
    assert "prov/std2 → prov/std3" in result.output
    ids = [e.id for e in parse_journal(_plan_journal(repo).read_text())]
    assert ids.count("model-substitution-standard-1") == 1
    assert ids.count("model-substitution-standard-2") == 1


def test_a_substitution_id_never_reuses_a_taken_suffix(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r3: with only `-2` on file, a count-based id would be `-2` again."""
    bf.user_models(env, USER_STD)
    bf.install(monkeypatch, bf.ScriptedProber(CATALOGUE, dead={"prov/std": None}))
    repo, shipped = _grouped(env)
    append_journal_entry(
        _plan_journal(repo),
        PLAN_SLUG,
        JournalEntry(
            kind="decision",
            scope="plan",
            id="model-substitution-standard-2",
            created="2026-10-06T00:00:00+00:00",
            title="an earlier one",
        ),
    )
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "seed"], check=True)

    result = _advance(repo, shipped)

    assert result.exit_code == 0, result.output
    ids = [e.id for e in parse_journal(_plan_journal(repo).read_text())]
    assert ids.count("model-substitution-standard-2") == 1
    assert "model-substitution-standard-3" in ids


def _clear_probe_cache() -> None:
    import os
    import shutil

    shutil.rmtree(os.environ["FR_MODELS_CACHE_DIR"], ignore_errors=True)
