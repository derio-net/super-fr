"""Waves and dependencies on a triage batch (spec 2026-10-02-wave-driver §A, R1).

Every state directory is tmp_path; no forge is touched (create/edit/list only).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.triage.model import Batch, Facts, Issue, Judgements, PullRequest, load_judgements
from typer.testing import CliRunner

REPO = "derio-net/super-fr"

JUDGED = """\
{schema}tiers:
  - {{n: 1, title: Now}}
issues:
  super-fr#1: {{tier: 1}}
  super-fr#2: {{tier: 1}}
  super-fr#3: {{tier: 1}}
  super-fr#4: {{tier: 1}}
"""

DISPATCHED = """\
    events:
      - {kind: dispatch, at: 2026-09-25T10:00:00Z, runner: fake, handle: "w1:p0",
         branch: feat/batch-%s}
"""


def _facts(*, closed: tuple[int, ...] = (), prs: list[PullRequest] | None = None) -> Facts:
    return Facts(
        viewer="operator",
        schema=3,
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-09-26T12:00:00+00:00",
        repos=[REPO],
        issues=[
            Issue(
                repo=REPO,
                number=n,
                title=f"issue {n}",
                state="closed" if n in closed else "open",
                url=f"https://github.com/{REPO}/issues/{n}",
            )
            for n in (1, 2, 3, 4)
        ],
        prs=prs or [],
        config={},
    )


def _pr(batch: str, state: str, number: int = 700) -> PullRequest:
    return PullRequest(
        author="operator",
        cross_repo=False,
        repo=REPO,
        number=number,
        title="batch PR",
        state=state,  # type: ignore[arg-type]
        is_draft=False,
        url=f"https://github.com/{REPO}/pull/{number}",
        head_ref=f"feat/batch-{batch}",
        created_at="2026-09-25T10:30:00+00:00",
    )


def _state(
    tmp_path: Path, batches: str = "", *, schema: int | None = 2, facts: Facts | None = None
) -> Path:
    head = f"schema: {schema}\n" if schema is not None else ""
    text = JUDGED.format(schema=head) + (f"batches:\n{batches}" if batches else "")
    (tmp_path / "judgements.yaml").write_text(text, encoding="utf-8")
    (tmp_path / "facts.json").write_text(json.dumps((facts or _facts()).to_json()), "utf-8")
    return tmp_path


def _batch_yaml(bid: str, issue: int, extra: str = "", *, dispatched: bool = False) -> str:
    out = f"  - id: {bid}\n    title: T {bid}\n    ids: [super-fr#{issue}]\n{extra}"
    return out + (DISPATCHED % bid if dispatched else "")


def _run(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, " ".join(result.output.split())


def _raw(tmp_path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((tmp_path / "judgements.yaml").read_text("utf-8"))
    return data


def _batches(tmp_path: Path) -> list[Batch]:
    return load_judgements(tmp_path / "judgements.yaml").batches


# ----------------------------------------------------------------- model


def test_a_batch_carries_a_wave_and_dependencies() -> None:
    doc = {"id": "a", "title": "A", "ids": ["super-fr#1"]}
    batch = Batch.model_validate({**doc, "wave": 2, "after": ["B", "c"]})
    assert (batch.wave, batch.after) == (2, ["b", "c"])
    bare = Batch.model_validate(doc)
    assert (bare.wave, bare.after) == (None, [])


def test_wave_and_after_round_trip_through_schema_3(tmp_path: Path) -> None:
    _state(
        tmp_path,
        _batch_yaml("a", 1, "    wave: 1\n") + _batch_yaml("b", 2, "    wave: 2\n    after: [a]\n"),
        schema=3,
    )
    judgements = load_judgements(tmp_path / "judgements.yaml")
    assert judgements.schema_ == 3
    by_id = {b.id: b for b in judgements.batches}
    assert (by_id["a"].wave, by_id["b"].wave, by_id["b"].after) == (1, 2, ["a"])


@pytest.mark.parametrize("schema", [1, 2, 3])
def test_every_schema_this_fr_reads_loads(tmp_path: Path, schema: int) -> None:
    batches = _batch_yaml("a", 1) if schema > 1 else ""
    _state(tmp_path, batches, schema=schema)
    assert load_judgements(tmp_path / "judgements.yaml").schema_ == schema


def test_a_future_schema_is_refused(tmp_path: Path) -> None:
    _state(tmp_path, schema=8)
    code, out = _run(tmp_path, "list")
    assert code == 2 and "unsupported schema 8" in out


def test_wave_and_after_need_schema_3(tmp_path: Path) -> None:
    """Written only at 3: an older stamp over them is a writer that forgot to restamp."""
    _state(tmp_path, _batch_yaml("a", 1, "    wave: 1\n"), schema=2)
    code, out = _run(tmp_path, "list")
    assert code == 2 and "schema 3" in out


def test_the_first_write_stamps_5_and_keeps_the_rest(tmp_path: Path) -> None:
    _state(tmp_path, schema=1)
    code, out = _run(tmp_path, "create", "a", "--title", "t", "--issue", "super-fr#1")
    assert code == 0, out
    assert (tmp_path / "judgements.yaml").read_text("utf-8").startswith("schema: 8\n")


# ------------------------------------------------------------ create / edit


def test_create_takes_wave_and_repeatable_after(tmp_path: Path) -> None:
    _state(tmp_path, _batch_yaml("a", 1) + _batch_yaml("b", 2))
    code, out = _run(
        tmp_path, "create", "c", "--title", "t", "--issue", "super-fr#3",
        "--wave", "2", "--after", "a", "--after", "B",
    )  # fmt: skip
    assert code == 0, out
    new = next(b for b in _batches(tmp_path) if b.id == "c")
    assert (new.wave, new.after) == (2, ["a", "b"])
    assert _raw(tmp_path)["schema"] == 7


def test_edit_changes_wave_and_after_of_a_proposed_batch(tmp_path: Path) -> None:
    _state(tmp_path, _batch_yaml("a", 1) + _batch_yaml("b", 2))
    code, out = _run(tmp_path, "edit", "b", "--wave", "3", "--after", "a")
    assert code == 0, out
    b = next(x for x in _batches(tmp_path) if x.id == "b")
    assert (b.wave, b.after) == (3, ["a"])


@pytest.mark.parametrize(
    ("args", "needle"),
    [
        (["--after", "ghost"], "ghost"),
        (["--after", "b"], "itself"),
    ],
)
def test_an_unknown_id_and_a_self_dependency_are_refused(
    tmp_path: Path, args: list[str], needle: str
) -> None:
    _state(tmp_path, _batch_yaml("a", 1) + _batch_yaml("b", 2))
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _run(tmp_path, "edit", "b", *args)
    assert code == 2 and needle in out
    assert (tmp_path / "judgements.yaml").read_bytes() == before


def test_a_cycle_is_refused_and_the_file_unchanged(tmp_path: Path) -> None:
    _state(
        tmp_path,
        _batch_yaml("a", 1, "    after: [b]\n")
        + _batch_yaml("b", 2, "    after: [c]\n")
        + _batch_yaml("c", 3),
        schema=3,
    )
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _run(tmp_path, "edit", "c", "--after", "a")
    assert code == 2 and "cycle" in out
    assert (tmp_path / "judgements.yaml").read_bytes() == before


def test_create_refuses_an_unknown_dependency_and_writes_nothing(tmp_path: Path) -> None:
    _state(tmp_path)
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _run(
        tmp_path, "create", "a", "--title", "t", "--issue", "super-fr#1", "--after", "ghost"
    )
    assert code == 2 and "ghost" in out
    assert (tmp_path / "judgements.yaml").read_bytes() == before


def test_wave_and_after_stay_editable_on_a_dispatched_unmerged_batch(tmp_path: Path) -> None:
    _state(tmp_path, _batch_yaml("a", 1) + _batch_yaml("b", 2, dispatched=True))
    code, out = _run(tmp_path, "edit", "b", "--wave", "4", "--after", "a")
    assert code == 0, out
    code, out = _run(tmp_path, "edit", "b", "--title", "renamed")
    assert code == 2 and "dispatched" in out


def test_wave_cannot_change_on_a_merged_batch(tmp_path: Path) -> None:
    facts = _facts(closed=(2,), prs=[_pr("b", "MERGED")])
    _state(tmp_path, _batch_yaml("b", 2, dispatched=True), facts=facts)
    code, out = _run(tmp_path, "edit", "b", "--wave", "4")
    assert code == 2 and "merged" in out


# ------------------------------------------------------------------- list


def test_list_shows_wave_dependencies_and_closeout(tmp_path: Path) -> None:
    _state(
        tmp_path,
        _batch_yaml("a", 1, "    wave: 1\n") + _batch_yaml("b", 2, "    wave: 2\n    after: [a]\n"),
        schema=3,
    )
    code, out = _run(tmp_path, "list")
    assert code == 0, out
    assert "wave 1" in out and "wave 2" in out
    assert "after a(waiting)" in out
    assert out.count("close-out none") == 2


def test_list_marks_a_batch_with_no_wave(tmp_path: Path) -> None:
    _state(tmp_path, _batch_yaml("a", 1))
    assert "wave -" in _run(tmp_path, "list")[1]


@pytest.mark.parametrize(
    ("prs", "closed", "events", "word"),
    [
        ([_pr("a", "MERGED")], (1,), True, "satisfied"),
        ([_pr("a", "MERGED")], (), True, "unsatisfiable"),  # partial
        ([_pr("a", "CLOSED")], (), True, "unsatisfiable"),  # abandoned
        ([], (), False, "waiting"),  # proposed
    ],
)
def test_dependency_reads_satisfied_only_by_merged(
    tmp_path: Path, prs: list[PullRequest], closed: tuple[int, ...], events: bool, word: str
) -> None:
    _state(
        tmp_path,
        _batch_yaml("a", 1, dispatched=events) + _batch_yaml("b", 2, "    after: [a]\n"),
        schema=3,
        facts=_facts(closed=closed, prs=prs),
    )
    assert f"after a({word})" in _run(tmp_path, "list")[1]


def test_a_cancelled_dependency_is_unsatisfiable(tmp_path: Path) -> None:
    cancelled = DISPATCHED % "a" + "      - {kind: cancel, at: 2026-09-25T11:00:00Z}\n"
    text = f"  - id: a\n    title: T\n    ids: [super-fr#1]\n{cancelled}" + _batch_yaml(
        "b", 2, "    after: [a]\n"
    )
    _state(tmp_path, text, schema=3)
    assert "after a(unsatisfiable)" in _run(tmp_path, "list")[1]


def test_judgements_model_has_a_schema_of_3() -> None:
    assert Judgements.model_validate({"schema": 3}).schema_ == 3


# ------------------------------------------------- clearing, close-out event

CLOSEOUT = """\
      - {kind: closeout, at: 2026-09-26T10:00:00Z, runner: fake, handle: "w2:p0"}
"""


def test_no_after_and_no_wave_clear_them_on_a_dispatched_unmerged_batch(tmp_path: Path) -> None:
    _state(
        tmp_path,
        _batch_yaml("a", 1) + _batch_yaml("b", 2, "    wave: 2\n    after: [a]\n", dispatched=True),
        schema=3,
    )
    code, out = _run(tmp_path, "edit", "b", "--no-after")
    assert code == 0, out
    b = next(x for x in _batches(tmp_path) if x.id == "b")
    assert (b.wave, b.after) == (2, [])
    code, out = _run(tmp_path, "edit", "b", "--no-wave")
    assert code == 0, out
    b = next(x for x in _batches(tmp_path) if x.id == "b")
    assert (b.wave, b.after) == (None, [])


@pytest.mark.parametrize("args", [["--no-after", "--after", "a"], ["--no-wave", "--wave", "1"]])
def test_a_clear_flag_refuses_its_value_option_and_the_file_is_unchanged(
    tmp_path: Path, args: list[str]
) -> None:
    _state(
        tmp_path,
        _batch_yaml("a", 1) + _batch_yaml("b", 2, "    wave: 2\n    after: [a]\n"),
        schema=3,
    )
    before = (tmp_path / "judgements.yaml").read_text("utf-8")
    code, out = _run(tmp_path, "edit", "b", *args)
    assert code == 2 and "contradict" in out
    assert (tmp_path / "judgements.yaml").read_text("utf-8") == before


def _closeout_batch(*, schema_events: bool = True) -> Batch:
    text = _batch_yaml("b", 2, dispatched=True) + (CLOSEOUT if schema_events else "")
    doc = yaml.safe_load(f"batches:\n{text}")
    return Batch.model_validate(doc["batches"][0])


def test_closeout_state_none_started_archived() -> None:
    from fr.triage.batch import closeout_state

    assert closeout_state(_closeout_batch(schema_events=False)) == "none"
    assert closeout_state(_closeout_batch()) == "started"
    started = _closeout_batch()
    recorded = started.events[-1].model_copy(update={"archived": 701})
    archived = started.model_copy(update={"events": [*started.events, recorded]})
    assert closeout_state(archived) == "archived"  # the event, never facts.prs (gh#882)


def test_a_closeout_event_needs_schema_3(tmp_path: Path) -> None:
    _state(tmp_path, _batch_yaml("b", 2, dispatched=True) + CLOSEOUT, schema=3)
    assert load_judgements(tmp_path / "judgements.yaml").batches[0].events[-1].kind == "closeout"
    _state(tmp_path, _batch_yaml("b", 2, dispatched=True) + CLOSEOUT, schema=2)
    with pytest.raises(Exception, match="closeout"):
        load_judgements(tmp_path / "judgements.yaml")
