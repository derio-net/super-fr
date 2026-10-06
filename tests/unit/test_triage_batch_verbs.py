"""`fr triage batch create|edit|cancel|suggest` and check's stale-dispatch set
(spec 2026-09-25-triage-batches §3.B, §3.E; Test Plan 3, 9, 10).

Every state directory is tmp_path; the forge adapter is `tests.unit.fakes.FakeGhClient`,
installed through `triage_batch_cmd.make_client`, so no `gh` ever runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.ghclient import UnsupportedForgeOperation
from fr.triage.batch import (
    ResolvedLaunch,
    Suggestion,
    fr_harness,
    mixed_themes,
    resolve_launch,
    suggest,
    theme_key,
)
from fr.triage.check import classify
from fr.triage.errors import TriageError
from fr.triage.model import (
    Batch,
    Facts,
    Issue,
    Judgements,
    Launch,
    PullRequest,
    TriageConfig,
    load_judgements,
)
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

REPO = "derio-net/super-fr"
ITEM = f"{REPO}/run/batch-lifecycle"

JUDGEMENTS = """\
schema: 1
ranked_at: 2026-09-25
tiers:
  - {n: 1, title: Now}
  - {n: 2, title: Next}
issues:
  super-fr#577:
    {tier: 1, theme: isolation, detail: "rebuild uses `packages/fr/src/fr/isolation/local.py`"}
  super-fr#575: {tier: 1, theme: isolation, detail: "stop re-uses `isolation/local.py` teardown"}
  super-fr#471: {tier: 2, theme: docs, detail: "README table"}
  super-fr#438: {tier: 2, theme: docs, detail: "HERMES prose"}
  super-fr#420: {tier: 2, theme: agents, detail: "executor guard"}
patterns:
  - {title: "Guards bypassed", ids: ["super-fr#420", "super-fr#438"], body: ""}
"""


def _issue(number: int, **kw: Any) -> Issue:
    return Issue(
        repo=REPO,
        number=number,
        title=f"issue {number}",
        state=kw.pop("state", "open"),
        url=f"https://github.com/{REPO}/issues/{number}",
        **kw,
    )


def _facts(*issues: Issue, config: dict[str, TriageConfig] | None = None, **kw: Any) -> Facts:
    return Facts(
        viewer="operator",
        schema=3,
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-09-26T12:00:00+00:00",
        repos=[REPO],
        issues=list(issues) or [_issue(n) for n in (577, 575, 471, 438, 420)],
        config=config or {},
        **kw,
    )


def _state(tmp_path: Path, facts: Facts | None = None, judgements: str = JUDGEMENTS) -> Path:
    (tmp_path / "judgements.yaml").write_text(judgements, encoding="utf-8")
    (tmp_path / "facts.json").write_text(json.dumps((facts or _facts()).to_json()), "utf-8")
    return tmp_path


def _run(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, result.output


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> FakeGhClient:
    from tests.unit.test_triage_batch_dispatch import FakeCheckout

    client = FakeGhClient()
    for n in (577, 575, 471, 438, 420):
        client.add_issue(REPO, n, labels={"fr:in-progress"})
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: client)
    # cancel --yes reads the clone's tracking declaration (gh#803): a clone of
    # REPO with none declared, never the cwd the suite happens to run in.
    clone = FakeCheckout(tmp_path_factory.mktemp("clone"))
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: clone)
    return client


def _batches(tmp_path: Path) -> list[Batch]:
    return load_judgements(tmp_path / "judgements.yaml").batches


def _raw(tmp_path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((tmp_path / "judgements.yaml").read_text("utf-8"))
    return data


# ------------------------------------------------------------------ create


def test_create_writes_the_batch_at_the_current_schema(tmp_path: Path) -> None:
    _state(tmp_path)
    code, out = _run(
        tmp_path,
        "create",
        "lifecycle",
        "--title",
        "Separate lifecycles",
        "--issue",
        "super-fr#577",
        "--issue",
        "Super-FR#575",
        "--rationale",
        "both route through down",
        "--bump",
        "minor",
    )
    assert code == 0, out
    (batch,) = _batches(tmp_path)
    assert (batch.id, batch.ids, batch.bump) == (
        "lifecycle",
        ["super-fr#577", "super-fr#575"],
        "minor",
    )
    assert _raw(tmp_path)["schema"] == 6


def test_create_stores_only_the_launch_values_given(tmp_path: Path) -> None:
    config = {REPO: TriageConfig.model_validate({"defaults": {"launch": {"runner": "herdr"}}})}
    _state(tmp_path, _facts(config=config))
    code, out = _run(
        tmp_path, "create", "lifecycle", "--title", "t", "--issue", "super-fr#577",
        "--model", "claude-opus-5-5",
    )  # fmt: skip
    assert code == 0, out
    assert _raw(tmp_path)["batches"][0]["launch"] == {"model": "claude-opus-5-5"}


def test_create_refuses_an_existing_id(tmp_path: Path) -> None:
    _state(tmp_path)
    assert _run(tmp_path, "create", "x", "--title", "t", "--issue", "super-fr#577")[0] == 0
    code, out = _run(tmp_path, "create", "x", "--title", "t", "--issue", "super-fr#471")
    assert code == 2
    assert "already exists" in out


def test_create_refuses_a_member_given_twice_and_writes_nothing(tmp_path: Path) -> None:
    """Review r2p-f5: refused at create, not later as 'super-fr#577 is in x, x'."""
    _state(tmp_path)
    before = (tmp_path / "judgements.yaml").read_text("utf-8")
    code, out = _run(
        tmp_path, "create", "x", "--title", "t",
        "--issue", "super-fr#577", "--issue", "Super-FR#577",
    )  # fmt: skip
    assert code == 2
    assert "more than once" in out
    assert " is in x, x" not in out
    assert (tmp_path / "judgements.yaml").read_text("utf-8") == before


def test_create_refuses_an_unjudged_member_and_writes_nothing(tmp_path: Path) -> None:
    _state(tmp_path)
    before = (tmp_path / "judgements.yaml").read_text("utf-8")
    code, out = _run(tmp_path, "create", "x", "--title", "t", "--issue", "super-fr#999")
    assert code == 2
    assert "not judged" in out
    assert (tmp_path / "judgements.yaml").read_text("utf-8") == before


def test_create_applies_the_open_batch_rule(tmp_path: Path) -> None:
    _state(tmp_path)
    assert _run(tmp_path, "create", "a", "--title", "t", "--issue", "super-fr#577")[0] == 0
    code, out = _run(tmp_path, "create", "b", "--title", "t", "--issue", "super-fr#577")
    assert code == 2
    assert "only one open batch" in " ".join(out.split())
    assert [b.id for b in _batches(tmp_path)] == ["a"]


def test_create_needs_facts(tmp_path: Path) -> None:
    (tmp_path / "judgements.yaml").write_text(JUDGEMENTS, encoding="utf-8")
    code, out = _run(tmp_path, "create", "a", "--title", "t", "--issue", "super-fr#577")
    assert code == 2
    assert "collect" in out


def test_create_with_skill_debug_stores_it(tmp_path: Path) -> None:
    _state(tmp_path)
    code, out = _run(
        tmp_path, "create", "x", "--title", "t", "--issue", "super-fr#577", "--skill", "debug",
    )  # fmt: skip
    assert code == 0, out
    assert _batches(tmp_path)[0].skill == "debug"


def test_create_without_skill_defaults_to_goal(tmp_path: Path) -> None:
    _state(tmp_path)
    code, out = _run(tmp_path, "create", "x", "--title", "t", "--issue", "super-fr#577")
    assert code == 0, out
    assert _batches(tmp_path)[0].skill == "goal"


# --------------------------------------------------------- mixed-theme warning


def test_create_warns_when_a_debug_batch_mixes_themes(tmp_path: Path) -> None:
    _state(tmp_path)
    code, out = _run(
        tmp_path, "create", "x", "--title", "t",
        "--issue", "super-fr#471", "--issue", "super-fr#420",  # themes docs, agents
        "--skill", "debug",
    )  # fmt: skip
    assert code == 0, out
    assert "warning: debug batch x mixes themes (agents, docs): a debug batch should be " in out
    assert "one root cause" in out


def test_create_prints_nothing_for_a_goal_batch_with_mixed_themes(tmp_path: Path) -> None:
    _state(tmp_path)
    code, out = _run(
        tmp_path, "create", "x", "--title", "t",
        "--issue", "super-fr#471", "--issue", "super-fr#420",
    )  # fmt: skip
    assert code == 0, out
    assert "warning" not in out


def test_create_prints_nothing_for_a_debug_batch_with_one_theme(tmp_path: Path) -> None:
    _state(tmp_path)
    code, out = _run(
        tmp_path, "create", "x", "--title", "t",
        "--issue", "super-fr#577", "--issue", "super-fr#575",  # both theme isolation
        "--skill", "debug",
    )  # fmt: skip
    assert code == 0, out
    assert "warning" not in out


def test_mixed_themes_unit_cases() -> None:
    judgements = Judgements.model_validate({**yaml.safe_load(JUDGEMENTS), "schema": 2})
    mixed = Batch.model_validate(
        {"id": "x", "title": "t", "ids": ["super-fr#471", "super-fr#420"], "skill": "debug"}
    )
    assert mixed_themes(mixed, judgements) == ["agents", "docs"]

    same = Batch.model_validate(
        {"id": "y", "title": "t", "ids": ["super-fr#577", "super-fr#575"], "skill": "debug"}
    )
    assert mixed_themes(same, judgements) == []

    goal = Batch.model_validate({"id": "z", "title": "t", "ids": ["super-fr#471", "super-fr#420"]})
    assert mixed_themes(goal, judgements) == []


def test_mixed_themes_ignores_empty_themes() -> None:
    judgements = Judgements.model_validate(
        {
            "schema": 2,
            "tiers": [{"n": 1, "title": "t"}],
            "issues": {"a#1": {"tier": 1}, "a#2": {"tier": 1, "theme": "x"}},
        }
    )
    batch = Batch.model_validate({"id": "x", "title": "t", "ids": ["a#1", "a#2"], "skill": "debug"})
    assert mixed_themes(batch, judgements) == []


_NS = (577, 575, 471, 438, 420)


def _themed(*themes: str) -> Judgements:
    """Judgements for the default facts' issues, one theme each, in `_NS` order."""
    return Judgements.model_validate(
        {
            "schema": 2,
            "tiers": [{"n": 1, "title": "t"}],
            "issues": {f"super-fr#{n}": {"tier": 1, "theme": t} for n, t in zip(_NS, themes)},
        }
    )


def test_theme_key_ignores_case_and_surrounding_space() -> None:
    assert theme_key("Docs") == theme_key("docs ") == theme_key(" DOCS\t") == "docs"
    assert theme_key("   ") == ""
    # Inner spacing is part of the theme; only the ends are trimmed.
    assert theme_key("fr isolation") != theme_key("fr  isolation")


def test_mixed_themes_treats_one_theme_spelled_two_ways_as_one() -> None:
    judgements = _themed("Docs", "docs ", " DOCS")
    batch = Batch.model_validate(
        {"id": "x", "title": "t", "ids": ["super-fr#577", "super-fr#575", "super-fr#471"],
         "skill": "debug"}
    )  # fmt: skip
    assert mixed_themes(batch, judgements) == []


def test_mixed_themes_keeps_the_stored_spelling_and_ignores_blank_themes() -> None:
    judgements = _themed("Docs", "docs", "Agents", "  ")
    batch = Batch.model_validate(
        {"id": "x", "title": "t", "skill": "debug",
         "ids": ["super-fr#577", "super-fr#575", "super-fr#471", "super-fr#438"]}
    )  # fmt: skip
    # The first member's spelling represents its theme; order is by the normalised key.
    assert mixed_themes(batch, judgements) == ["Agents", "Docs"]


# -------------------------------------------------------------------- edit


def _with(tmp_path: Path, *batches: dict[str, Any], facts: Facts | None = None) -> None:
    doc = yaml.safe_load(JUDGEMENTS) | {"schema": 2, "batches": list(batches)}
    _state(tmp_path, facts, yaml.safe_dump(doc, sort_keys=False))


_DISPATCH = {
    "kind": "dispatch",
    "at": "2026-09-25T10:00:00Z",
    "runner": "herdr",
    "handle": "w2:p1K",
    "branch": "feat/batch-lifecycle",
    "reserved_version": "4.22.0",
}


def test_edit_adds_and_removes_members(tmp_path: Path) -> None:
    _with(tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577", "super-fr#575"]})
    code, out = _run(
        tmp_path, "edit", "lifecycle", "--add-issue", "super-fr#471",
        "--remove-issue", "super-fr#575", "--title", "new",
    )  # fmt: skip
    assert code == 0, out
    (batch,) = _batches(tmp_path)
    assert (batch.title, batch.ids) == ("new", ["super-fr#577", "super-fr#471"])


@pytest.mark.parametrize(
    "added", [["super-fr#577"], ["super-fr#471", "Super-FR#471"]], ids=["member", "twice"]
)
def test_edit_refuses_adding_a_member_twice(tmp_path: Path, added: list[str]) -> None:
    _with(tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577", "super-fr#575"]})
    before = (tmp_path / "judgements.yaml").read_text("utf-8")
    args = [a for k in added for a in ("--add-issue", k)]
    code, out = _run(tmp_path, "edit", "lifecycle", *args)
    assert code == 2
    assert "more than once" in out
    assert (tmp_path / "judgements.yaml").read_text("utf-8") == before


def test_edit_refuses_removing_the_last_member(tmp_path: Path) -> None:
    _with(tmp_path, {"id": "x", "title": "t", "ids": ["super-fr#577"]})
    code, _ = _run(tmp_path, "edit", "x", "--remove-issue", "super-fr#577")
    assert code == 2


def test_edit_refuses_an_unknown_batch(tmp_path: Path) -> None:
    _with(tmp_path)
    code, out = _run(tmp_path, "edit", "nope", "--title", "t")
    assert code == 2
    assert "no batch" in out


def test_edit_past_proposed_is_refused_except_order(tmp_path: Path) -> None:
    _with(
        tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH]}
    )

    code, out = _run(tmp_path, "edit", "lifecycle", "--title", "renamed")
    assert code == 2
    assert "dispatched" in out

    code, out = _run(tmp_path, "edit", "lifecycle", "--order", "2")
    assert code == 0, out
    assert _batches(tmp_path)[0].order == 2


def test_edit_applies_the_open_batch_rule(tmp_path: Path) -> None:
    _with(
        tmp_path,
        {"id": "a", "title": "t", "ids": ["super-fr#577"]},
        {"id": "b", "title": "t", "ids": ["super-fr#575"]},
    )
    code, out = _run(tmp_path, "edit", "b", "--add-issue", "super-fr#577")
    assert code == 2
    assert "only one open batch" in " ".join(out.split())


def test_edit_skill_while_proposed(tmp_path: Path) -> None:
    _with(tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"]})
    code, out = _run(tmp_path, "edit", "lifecycle", "--skill", "debug")
    assert code == 0, out
    assert _batches(tmp_path)[0].skill == "debug"


def test_edit_skill_past_proposed_is_refused(tmp_path: Path) -> None:
    _with(
        tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH]}
    )
    code, out = _run(tmp_path, "edit", "lifecycle", "--skill", "debug")
    assert code == 2
    assert "dispatched" in out


def test_edit_add_issue_triggers_the_mixed_theme_warning(tmp_path: Path) -> None:
    _with(tmp_path, {"id": "x", "title": "t", "ids": ["super-fr#471"], "skill": "debug"})
    code, out = _run(tmp_path, "edit", "x", "--add-issue", "super-fr#420")
    assert code == 0, out
    assert "warning: debug batch x mixes themes (agents, docs)" in out


def test_edit_skill_flip_to_debug_triggers_the_mixed_theme_warning(tmp_path: Path) -> None:
    _with(tmp_path, {"id": "x", "title": "t", "ids": ["super-fr#471", "super-fr#420"]})
    code, out = _run(tmp_path, "edit", "x", "--skill", "debug")
    assert code == 0, out
    assert "warning: debug batch x mixes themes (agents, docs)" in out


def test_edit_prints_nothing_when_themes_stay_uniform(tmp_path: Path) -> None:
    _with(tmp_path, {"id": "x", "title": "t", "ids": ["super-fr#577"], "skill": "debug"})
    code, out = _run(tmp_path, "edit", "x", "--add-issue", "super-fr#575")
    assert code == 0, out
    assert "warning" not in out


def test_a_member_of_a_cancelled_batch_may_join_a_new_one(tmp_path: Path) -> None:
    cancel = {"kind": "cancel", "at": "2026-09-26T00:00:00Z"}
    _with(
        tmp_path, {"id": "a", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH, cancel]}
    )
    code, out = _run(tmp_path, "create", "b", "--title", "t", "--issue", "super-fr#577")
    assert code == 0, out


# ------------------------------------------------------------------ cancel


def test_cancel_without_yes_prints_the_plan_and_writes_nothing(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    _with(
        tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH]}
    )
    before = (tmp_path / "judgements.yaml").read_text("utf-8")

    code, out = _run(tmp_path, "cancel", "lifecycle", "--reason", "split")

    assert code == 0, out
    assert "--yes" in out
    assert (tmp_path / "judgements.yaml").read_text("utf-8") == before
    assert [c for c, _ in gh.calls if c != "list_issue_comments"] == []


def test_cancel_with_yes_removes_the_label_posts_the_withdrawal_and_appends_the_event(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    _with(
        tmp_path,
        {
            "id": "lifecycle",
            "title": "t",
            "ids": ["super-fr#577", "super-fr#575"],
            "events": [_DISPATCH],
        },
    )

    code, out = _run(tmp_path, "cancel", "lifecycle", "--reason", "split", "--yes")

    assert code == 0, out
    for n in (577, 575):
        assert "fr:in-progress" not in gh.issues[(REPO, n)].labels
        (comment,) = gh.issue_comments[(REPO, n)]
        assert comment["body"].startswith(f"<!-- fr-batch-withdrawn:{ITEM} -->")
        assert "batch `lifecycle` withdrawn" in comment["body"]
        assert "w2:p1K" not in comment["body"]
    (batch,) = _batches(tmp_path)
    assert batch.events[-1].kind == "cancel"
    assert batch.events[-1].reason == "split"  # type: ignore[union-attr]


def test_cancel_posts_no_second_withdrawal(tmp_path: Path, gh: FakeGhClient) -> None:
    """Re-running cancel after a partial forge failure adds only what is missing."""
    _with(
        tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH]}
    )
    gh.issue_comments[(REPO, 577)] = [
        {
            "author": "fr",
            "body": f"<!-- fr-batch-withdrawn:{ITEM} -->\nbatch `lifecycle` withdrawn",
            "created_at": "t",
        }
    ]

    code, out = _run(tmp_path, "cancel", "lifecycle", "--yes")

    assert code == 0, out
    assert len(gh.issue_comments[(REPO, 577)]) == 1


def test_a_forge_failure_during_cancel_appends_no_event_and_exits_1(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    _with(
        tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH]}
    )
    gh.fail_on_mutation = 0

    code, out = _run(tmp_path, "cancel", "lifecycle", "--yes")

    assert code == 1
    assert "super-fr#577" in out
    assert _batches(tmp_path)[0].events[-1].kind == "dispatch"


def test_cancel_refuses_to_overwrite_batches_changed_while_it_ran(
    tmp_path: Path, gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review r2p-f7: another writer adds a batch during cancel's forge writes;
    cancel exits 2 rather than silently dropping it."""
    _with(
        tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH]}
    )
    real = gh.comment_issue

    def racing(*args: Any, **kw: Any) -> Any:
        _with(
            tmp_path,
            {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH]},
            {"id": "docs", "title": "d", "ids": ["super-fr#471"]},
        )
        return real(*args, **kw)

    monkeypatch.setattr(gh, "comment_issue", racing)
    code, out = _run(tmp_path, "cancel", "lifecycle", "--yes")

    assert code == 2
    assert "changed since it was read; re-run" in out
    assert [b.id for b in _batches(tmp_path)] == ["lifecycle", "docs"]


def test_cancel_probes_an_unsupported_backend_before_any_write(
    tmp_path: Path, gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review r2p-f8: on a backend without comment reads, cancel refuses (exit 2)
    before unlabelling anyone, so no member is left half-withdrawn."""
    _with(
        tmp_path,
        {
            "id": "lifecycle",
            "title": "t",
            "ids": ["super-fr#577", "super-fr#575"],
            "events": [_DISPATCH],
        },
    )

    def unsupported(repo: str, number: int) -> list[dict[str, Any]]:
        raise UnsupportedForgeOperation("list_issue_comments", "gitlab")

    monkeypatch.setattr(gh, "list_issue_comments", unsupported)
    code, out = _run(tmp_path, "cancel", "lifecycle", "--yes")

    assert code == 2
    assert "list_issue_comments" in out
    for n in (577, 575):
        assert "fr:in-progress" in gh.issues[(REPO, n)].labels
    assert [c for c, _ in gh.calls if c not in {"list_issue_comments"}] == []
    assert _batches(tmp_path)[0].events[-1].kind == "dispatch"


def test_a_programming_error_during_cancel_is_not_reported_as_a_forge_failure(
    tmp_path: Path, gh: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review r2p-f8: only forge errors are collected per member; a bug raises."""
    _with(
        tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH]}
    )

    def buggy(*args: Any, **kw: Any) -> None:
        raise TypeError("comment_issue() got an unexpected keyword argument")

    monkeypatch.setattr(gh, "comment_issue", buggy)
    result = CliRunner().invoke(
        app,
        ["triage", "batch", "cancel", "lifecycle", "--yes", "--repo", REPO, "--dir", str(tmp_path)],
    )

    assert isinstance(result.exception, TypeError)
    assert "not fully withdrawn" not in result.output


def test_cancel_refuses_a_batch_already_closed_out(tmp_path: Path, gh: FakeGhClient) -> None:
    cancel = {"kind": "cancel", "at": "2026-09-26T00:00:00Z"}
    _with(
        tmp_path, {"id": "a", "title": "t", "ids": ["super-fr#577"], "events": [_DISPATCH, cancel]}
    )
    code, out = _run(tmp_path, "cancel", "a", "--yes")
    assert code == 2
    assert "cancelled" in out


# ----------------------------------------------------------------- suggest


def test_suggest_groups_by_cited_file_theme_and_pattern_and_writes_nothing(
    tmp_path: Path,
) -> None:
    _state(tmp_path)
    before = (tmp_path / "judgements.yaml").read_text("utf-8")

    code, out = _run(tmp_path, "suggest")

    assert code == 0, out
    lines = out.splitlines()
    shared_file = next(ln for ln in lines if ln.startswith("file "))
    assert "isolation/local.py" in shared_file
    assert "super-fr#577" in shared_file and "super-fr#575" in shared_file
    assert any(ln.startswith("theme docs") and "super-fr#471" in ln for ln in lines)
    assert any(ln.startswith("pattern Guards bypassed") for ln in lines)
    # Signal order: files, then themes, then patterns.
    kinds = [ln.split()[0] for ln in lines if ln.split()[:1] in (["file"], ["theme"], ["pattern"])]
    assert kinds == sorted(kinds, key=["file", "theme", "pattern"].index)
    assert (tmp_path / "judgements.yaml").read_text("utf-8") == before


def test_suggest_leaves_out_members_of_open_batches(tmp_path: Path) -> None:
    _with(tmp_path, {"id": "a", "title": "t", "ids": ["super-fr#577"]})
    code, out = _run(tmp_path, "suggest")
    assert code == 0, out
    assert "super-fr#577" not in out


def test_suggest_groups_one_theme_spelled_several_ways() -> None:
    judgements = _themed("Docs", "docs ", "docs", "  ", "  ")

    themes = [s for s in suggest(judgements, _facts()) if s.signal == "theme"]

    # One group, under the first member's stored spelling; blank themes form no group.
    assert themes == [Suggestion("theme", "Docs", ["super-fr#577", "super-fr#575", "super-fr#471"])]
    # Nothing is rewritten: the stored spellings survive.
    assert [judgements.issues[f"super-fr#{n}"].theme for n in (577, 575)] == ["Docs", "docs "]


# ---------------------------------------------------------- launch resolution


def test_launch_resolves_batch_then_defaults_then_refuses() -> None:
    batch = Batch(id="x", title="t", ids=["a#1"], launch=Launch(model="m"))
    defaults = TriageConfig.model_validate(
        {"defaults": {"launch": {"runner": "herdr", "harness": "claude", "model": "other"}}}
    )
    assert resolve_launch(batch, defaults).launch == Launch(
        runner="herdr", harness="claude", model="m"
    )
    with pytest.raises(TriageError, match=r"runner.*harness"):
        resolve_launch(batch, TriageConfig())


def test_launch_model_wins_from_the_batch() -> None:
    batch = Batch(
        id="x", title="t", ids=["a#1"], launch=Launch(runner="herdr", harness="claude", model="m")
    )
    defaults = TriageConfig.model_validate(
        {"defaults": {"launch": {"runner": "herdr", "harness": "claude", "model": "other"}}}
    )
    resolved = resolve_launch(batch, defaults, orchestrator=lambda h: "never-asked")
    assert resolved == ResolvedLaunch(
        launch=Launch(runner="herdr", harness="claude", model="m"), model_source="batch"
    )


def test_launch_model_falls_back_to_defaults_over_the_orchestrator() -> None:
    batch = Batch(id="x", title="t", ids=["a#1"], launch=Launch(runner="herdr", harness="claude"))
    defaults = TriageConfig.model_validate(
        {"defaults": {"launch": {"runner": "herdr", "harness": "claude", "model": "other"}}}
    )
    resolved = resolve_launch(batch, defaults, orchestrator=lambda h: "never-asked")
    assert resolved.launch.model == "other"
    assert resolved.model_source == "defaults.launch"


def test_launch_model_falls_back_to_the_orchestrator_binding_with_the_fr_harness_id() -> None:
    batch = Batch(id="x", title="t", ids=["a#1"], launch=Launch(runner="herdr", harness="claude"))
    defaults = TriageConfig.model_validate(
        {"defaults": {"launch": {"runner": "herdr", "harness": "claude"}}}
    )
    seen: list[str] = []

    def orchestrator(harness: str) -> str | None:
        seen.append(harness)
        return "claude-opus-5-5"

    resolved = resolve_launch(batch, defaults, orchestrator=orchestrator)
    assert seen == ["claude-code"]
    assert resolved.launch.model == "claude-opus-5-5"
    assert resolved.model_source == "orchestrator binding"


@pytest.mark.parametrize("orchestrator", [None, lambda h: None])
def test_launch_refuses_naming_fr_models_set_when_nothing_binds_a_model(
    orchestrator: object,
) -> None:
    batch = Batch(id="x", title="t", ids=["a#1"], launch=Launch(runner="herdr", harness="claude"))
    defaults = TriageConfig.model_validate(
        {"defaults": {"launch": {"runner": "herdr", "harness": "claude"}}}
    )
    with pytest.raises(
        TriageError, match=r"fr models set --harness claude-code --tier orchestrator --model"
    ):
        resolve_launch(batch, defaults, orchestrator=orchestrator)  # type: ignore[arg-type]


def test_launch_never_calls_the_orchestrator_when_harness_is_unset() -> None:
    batch = Batch(id="x", title="t", ids=["a#1"], launch=Launch(runner="herdr", model="m"))

    def orchestrator(harness: str) -> str | None:
        raise AssertionError("orchestrator must not be called: harness is unset")

    with pytest.raises(TriageError, match=r"harness"):
        resolve_launch(batch, TriageConfig(), orchestrator=orchestrator)


def test_fr_harness_maps_claude_and_passes_through_others() -> None:
    assert fr_harness("claude") == "claude-code"
    assert fr_harness("opencode") == "opencode"


# ---------------------------------------------------------- stale dispatch


def _in_progress(number: int, marker_at: str | None, prs: list[PullRequest] = ()) -> Issue:
    return _issue(number, labels=["fr:in-progress"], dispatch_marker_at=marker_at, prs=list(prs))


def test_check_reports_a_stale_dispatch_from_the_marker_age() -> None:
    facts = _facts(
        _in_progress(577, "2026-09-22T11:00:00Z"),  # 4 days before collect
        _in_progress(575, "2026-09-25T12:00:00Z"),  # 1 day
        _in_progress(471, None),  # a phase issue the bridge labelled: no batch marker
    )
    judgements = load_judgements_text(JUDGEMENTS)

    stale = classify(facts, judgements).stale
    assert [s.key for s in stale] == ["super-fr#577"]
    assert stale[0].days == 4


def test_a_linked_pr_is_not_stale() -> None:
    pr = PullRequest(repo=REPO, number=9, title="p", state="OPEN", is_draft=True, url="u")
    facts = _facts(_in_progress(577, "2026-09-01T00:00:00Z", prs=[pr]))
    assert classify(facts, load_judgements_text(JUDGEMENTS)).stale == []


def test_a_closed_unmerged_linked_pr_does_not_hide_a_stale_dispatch() -> None:
    """Review r2p-f13: 'no linked PR' means no OPEN or MERGED one."""
    old = PullRequest(repo=REPO, number=9, title="p", state="CLOSED", is_draft=False, url="u")
    facts = _facts(_in_progress(577, "2026-09-01T00:00:00Z", prs=[old]))
    assert [s.key for s in classify(facts, load_judgements_text(JUDGEMENTS)).stale] == [
        "super-fr#577"
    ]


def test_a_merged_linked_pr_is_not_stale() -> None:
    pr = PullRequest(repo=REPO, number=9, title="p", state="MERGED", is_draft=False, url="u")
    facts = _facts(_in_progress(577, "2026-09-01T00:00:00Z", prs=[pr]))
    assert classify(facts, load_judgements_text(JUDGEMENTS)).stale == []


@pytest.mark.parametrize("marker_at", ["", "not-a-date", "2026-09-01T00:00:00"])
def test_an_unreadable_marker_time_is_skipped_never_raised(tmp_path: Path, marker_at: str) -> None:
    """Review r2p-f13: check always exits 0; a marker it cannot date is skipped."""
    facts = _facts(_in_progress(577, marker_at), _in_progress(575, "2026-09-01T00:00:00Z"))
    assert [s.key for s in classify(facts, load_judgements_text(JUDGEMENTS)).stale] == [
        "super-fr#575"
    ]
    _state(tmp_path, facts)
    result = CliRunner().invoke(
        app, ["triage", "check", "--repo", REPO, "--dir", str(tmp_path), "--json"]
    )
    assert result.exit_code == 0, result.output


def test_the_stale_threshold_comes_from_the_collected_config() -> None:
    config = {REPO: TriageConfig(stale_dispatch_days=5)}
    facts = _facts(_in_progress(577, "2026-09-22T11:00:00Z"), config=config)
    assert classify(facts, load_judgements_text(JUDGEMENTS)).stale == []


def test_the_check_command_prints_the_stale_set(tmp_path: Path) -> None:
    _state(tmp_path, _facts(_in_progress(577, "2026-09-20T00:00:00Z")))
    result = CliRunner().invoke(
        app, ["triage", "check", "--repo", REPO, "--dir", str(tmp_path), "--json"]
    )
    assert result.exit_code == 0, result.output
    stale = json.loads(result.output)["stale_dispatch"]
    assert [s["key"] for s in stale] == ["super-fr#577"]


def load_judgements_text(text: str):  # noqa: ANN201 — test helper
    from fr.triage.model import Judgements

    return Judgements.model_validate(yaml.safe_load(text))


# ------------------------------------------- triage-claims: the batch-command gates

from tests.unit.triage_claim_fixtures import (  # noqa: E402
    FAR,
    OTHER,
    PAST,
    calls,
    held,
    marker,
    markers,
    put_marker,
)


def _with6(tmp_path: Path, *batches: dict[str, Any], facts: Facts | None = None) -> None:
    doc = yaml.safe_load(JUDGEMENTS) | {"schema": 6, "batches": list(batches)}
    _state(tmp_path, facts, yaml.safe_dump(doc, sort_keys=False))


def _me() -> str:
    from fr.triage.scope_config import scope_id

    return scope_id("derio-net--super-fr")


def _held_facts(live: bool = True) -> Facts:
    theirs = marker(OTHER, "theirs", expires=FAR if live else PAST)
    return _facts(_issue(577), _issue(575, **held(theirs)), _issue(471), _issue(438), _issue(420))


_CREATE = ("create", "lifecycle", "--title", "t", "--issue", "super-fr#577")


@pytest.mark.parametrize("wave", [[], ["--wave", "1"]])
def test_create_refuses_a_member_held_elsewhere_naming_holder_batch_and_expiry(
    tmp_path: Path, gh: FakeGhClient, wave: list[str]
) -> None:
    _state(tmp_path, _held_facts())
    before = (tmp_path / "judgements.yaml").read_text("utf-8")
    code, out = _run(tmp_path, *_CREATE, "--issue", "super-fr#575", *wave)
    text = " ".join(out.split())
    assert code == 2
    assert "super-fr#575" in text and OTHER in text and "theirs" in text and "2999" in text
    assert "claim take" not in text
    assert (tmp_path / "judgements.yaml").read_text("utf-8") == before
    assert gh.calls == []


def test_create_refusing_an_expired_claim_names_claim_take(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    _state(tmp_path, _held_facts(live=False))
    code, out = _run(tmp_path, *_CREATE, "--issue", "super-fr#575", "--wave", "1")
    assert code == 2
    assert "fr triage claim take super-fr#575" in " ".join(out.split())


def test_create_with_a_wave_and_no_yes_prints_the_owed_claims(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    _state(tmp_path)
    code, out = _run(tmp_path, *_CREATE, "--wave", "1")
    assert code == 0, out
    assert [b.id for b in _batches(tmp_path)] == ["lifecycle"]
    assert "claim super-fr#577 for lifecycle" in out
    assert "fr triage claim sync --yes" in out
    assert gh.calls == []


def test_create_with_a_wave_and_yes_writes_the_claims_after_the_judgements(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    _state(tmp_path)
    code, out = _run(tmp_path, *_CREATE, "--issue", "super-fr#575", "--wave", "1", "--yes")
    assert code == 0, out
    assert [b.id for b in _batches(tmp_path)] == ["lifecycle"]
    for n in (577, 575):
        (m,) = markers(gh, REPO, n)
        assert (m.signer, m.batch, m.released) == (_me(), "lifecycle", None)
        assert "fr:claimed" in gh.issues[(REPO, n)].labels


def test_create_without_a_wave_owes_no_claim(tmp_path: Path, gh: FakeGhClient) -> None:
    _state(tmp_path)
    code, out = _run(tmp_path, *_CREATE, "--yes")
    assert code == 0, out
    assert "fr triage claim sync" not in out
    assert gh.calls == []


def test_edit_add_issue_or_wave_refuses_a_member_held_elsewhere(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    _with6(
        tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"]}, facts=_held_facts()
    )
    code, out = _run(tmp_path, "edit", "lifecycle", "--add-issue", "super-fr#575")
    assert code == 2 and OTHER in out
    assert _batches(tmp_path)[0].ids == ["super-fr#577"]
    _with6(
        tmp_path,
        {"id": "lifecycle", "title": "t", "ids": ["super-fr#577", "super-fr#575"]},
        facts=_held_facts(),
    )
    code, out = _run(tmp_path, "edit", "lifecycle", "--wave", "2")
    assert code == 2 and OTHER in out
    assert _batches(tmp_path)[0].wave is None
    assert gh.calls == []


def test_edit_remove_issue_yes_releases_the_dropped_member(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    ids = ["super-fr#577", "super-fr#575"]
    _with6(tmp_path, {"id": "lifecycle", "title": "t", "ids": ids, "wave": 1})
    put_marker(gh, REPO, 575, marker(_me(), "lifecycle", expires=FAR), 7)
    code, out = _run(tmp_path, "edit", "lifecycle", "--remove-issue", "super-fr#575", "--yes")
    assert code == 0, out
    (m,) = markers(gh, REPO, 575)
    assert m.released is not None
    assert "fr:claimed" not in gh.issues[(REPO, 575)].labels


def test_edit_no_wave_yes_releases_a_proposed_batch(tmp_path: Path, gh: FakeGhClient) -> None:
    _with6(tmp_path, {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "wave": 1})
    put_marker(gh, REPO, 577, marker(_me(), "lifecycle", expires=FAR), 7)
    code, out = _run(tmp_path, "edit", "lifecycle", "--no-wave", "--yes")
    assert code == 0, out
    assert markers(gh, REPO, 577)[0].released is not None


def test_cancel_yes_on_a_held_batch_releases_own_claims_and_leaves_held_members_alone(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    ids = ["super-fr#577", "super-fr#575"]
    _with6(
        tmp_path,
        {"id": "lifecycle", "title": "t", "ids": ids, "wave": 1, "events": [_DISPATCH]},
        facts=_held_facts(),
    )
    put_marker(gh, REPO, 577, marker(_me(), "lifecycle", expires=FAR), 7)
    put_marker(gh, REPO, 575, marker(OTHER, "theirs", expires=FAR), 8)
    code, out = _run(tmp_path, "cancel", "lifecycle", "--yes")
    assert code == 0, out
    assert markers(gh, REPO, 577)[0].released is not None
    assert "fr:in-progress" not in gh.issues[(REPO, 577)].labels
    # the held member: its label and comments are its holder's
    assert "fr:in-progress" in gh.issues[(REPO, 575)].labels
    assert "fr:claimed" in gh.issues[(REPO, 575)].labels
    assert [m.signer for m in markers(gh, REPO, 575)] == [OTHER]
    assert len(gh.issue_comments[(REPO, 575)]) == 1
    events = [e.kind for e in _batches(tmp_path)[0].events]
    assert events[-2:] == ["cancel", "claims_released"]


def test_cancelling_a_proposed_batch_with_written_claims_uses_the_client(
    tmp_path: Path, gh: FakeGhClient
) -> None:
    own = marker(_me(), "lifecycle", expires=FAR)
    _with6(
        tmp_path,
        {"id": "lifecycle", "title": "t", "ids": ["super-fr#577"], "wave": 1},
        facts=_facts(
            _issue(577, **held(own, 7)), _issue(575), _issue(471), _issue(438), _issue(420)
        ),
    )
    put_marker(gh, REPO, 577, own, 7)
    code, out = _run(tmp_path, "cancel", "lifecycle", "--yes")
    assert code == 0, out
    assert markers(gh, REPO, 577)[0].released is not None
    assert "edit_issue_comment" in calls(gh)
    assert [e.kind for e in _batches(tmp_path)[0].events] == ["cancel", "claims_released"]
