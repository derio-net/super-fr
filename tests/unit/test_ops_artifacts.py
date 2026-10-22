"""Artifact compliance for fr ops (spec 2026-10-22-fr-ops R17, §D).

`ops.yaml` is a registered `ops` kind; the journal kind moves 2 -> 3 for the `op`
entry kind (stamp-only); a step record can never carry an `op` entry;
`fr journal check` ignores op entries; and `fr plan self-review` refuses a plan
with ops whose `fr_version` floor predates the release that ships `fr ops`.
"""

from __future__ import annotations

import dataclasses
import re
import subprocess
from pathlib import Path
from typing import get_args

import pytest
from fr.artifacts import ARTIFACT_KINDS, MIGRATIONS, iter_paths_of, run_migrations
from fr.artifacts.structure import validate_journal
from fr.cli import app
from fr.journal.model import (
    OP_BODY_KEYS,
    JournalEntry,
    JournalKind,
    append_journal_entry,
    journal_path,
    op_body,
    op_fields,
    parse_journal,
    serialize_entry,
)
from fr.parser import parse as parse_plan
from fr.plan_ops import OPS_FR_FLOOR, self_review
from fr.record.model import JournalItem
from fr.version_floor import CEILING_VERSION, admits
from packaging.version import InvalidVersion, Version
from pydantic import ValidationError
from typer.testing import CliRunner

runner = CliRunner()
REPO = Path(__file__).resolve().parents[2]

GOOD_OPS = (
    "schema_version: 1\nops:\n"
    "  - id: a\n    summary: s\n    phase: pre-merge\n    check: 'true'\n"
    "  - id: b\n    summary: t\n    phase: post-merge\n    needs: [a]\n"
)


def _op_entry(eid: str = "op-a-1", result: str = "done") -> JournalEntry:
    return JournalEntry(
        kind="op",
        scope="plan",
        id=eid,
        created="2026-10-22T10:00:00+00:00",
        title=f"op a: {result}",
        body=op_body(op="a", result=result, phase="pre-merge", reason="ok"),
    )


# --- the `ops` artifact kind ---------------------------------------------------


def test_ops_is_a_registered_kind_at_version_one() -> None:
    kind = ARTIFACT_KINDS["ops"]
    assert kind.current_version == 1
    assert kind.locator == "docs/superpowers/plans/*/ops.yaml"


def test_the_ops_kind_locates_and_validates_a_plans_ops_yaml(tmp_path: Path) -> None:
    path = tmp_path / "docs/superpowers/plans/p/ops.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(GOOD_OPS)
    kind = ARTIFACT_KINDS["ops"]
    assert list(iter_paths_of(tmp_path, kind)) == [path]
    assert kind.read_version(path) == 1
    assert kind.validate is not None and kind.validate(path) == []


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        (GOOD_OPS.replace("check:", "chekc:"), "chekc"),
        (GOOD_OPS.replace("phase: pre-merge", "phase: soon"), "phase"),
        (GOOD_OPS.replace("id: b", "id: a"), "twice"),
        (GOOD_OPS + "extra: 1\n", "extra"),
        (GOOD_OPS.replace("summary: s\n", "summary: s\n    summary: again\n"), "duplicate"),
    ],
)
def test_the_ops_validator_reports_a_bad_file(tmp_path: Path, text: str, needle: str) -> None:
    path = tmp_path / "ops.yaml"
    path.write_text(text)
    validate = ARTIFACT_KINDS["ops"].validate
    assert validate is not None
    problems = validate(path)
    assert any(needle in p for p in problems), problems


# --- journal kind 3 ------------------------------------------------------------


def test_the_journal_kind_moved_to_version_three() -> None:
    assert ARTIFACT_KINDS["journal"].current_version == 3


def test_the_journal_kind_is_reachable_from_version_two() -> None:
    chain = MIGRATIONS.chain("journal", 2)
    assert [m.from_version for m in chain] == [2]
    assert [m.to_version for m in chain] == [3]
    full = MIGRATIONS.chain("journal", 1)
    assert [m.from_version for m in full] == [1, 2]


def test_the_journal_migration_to_three_is_stamp_only(tmp_path: Path) -> None:
    path = tmp_path / "docs/superpowers/journals/plans/p.md"
    path.parent.mkdir(parents=True)
    body = (
        "# Journal: p\n\n"
        "<!-- fr:journal kind=discovery scope=plan id=d1 created=2026-01-01T00:00:00 -->\n"
        "### d1 · discovery · t\n\nbody\n"
    )
    path.write_text("<!-- fr:journal-schema=2 -->\n" + body)
    report = run_migrations(tmp_path, dry_run=False)
    assert report.ok, report.failed
    assert path.read_text() == "<!-- fr:journal-schema=3 -->\n" + body


def test_a_version_two_journal_with_an_op_entry_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "docs/superpowers/journals/plans/p.md"
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=2 -->\n# Journal: p\n\n" + serialize_entry(_op_entry()))
    before = path.read_bytes()
    problems = validate_journal(path)
    assert any("op" in p and "schema 2" in p for p in problems), problems
    report = run_migrations(tmp_path, dry_run=False)
    assert not report.ok
    assert path.read_bytes() == before


def test_journal_kind_contains_op() -> None:
    assert "op" in get_args(JournalKind)


def test_an_op_entry_round_trips_and_carries_its_body_keys() -> None:
    (entry,) = parse_journal("# Journal: p\n\n" + serialize_entry(_op_entry()))
    assert entry.kind == "op"
    fields = op_fields(entry)
    assert fields == {"op": "a", "result": "done", "phase": "pre-merge", "reason": "ok"}
    assert set(fields) <= set(OP_BODY_KEYS)


def test_op_body_refuses_an_unknown_result_and_a_multiline_value() -> None:
    with pytest.raises(ValueError):
        op_body(op="a", result="maybe")
    with pytest.raises(ValueError):
        op_body(op="a", result="done", reason="two\nlines")


def test_appending_an_op_entry_to_an_older_journal_stamps_it(tmp_path: Path) -> None:
    path = journal_path(tmp_path, "plan", "p")
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=2 -->\n# Journal: p\n")
    append_journal_entry(path, "p", _op_entry())
    assert ARTIFACT_KINDS["journal"].read_version(path) == 3
    assert validate_journal(path) == []


def test_a_step_record_refuses_an_op_entry() -> None:
    with pytest.raises(ValidationError, match="op"):
        JournalItem.model_validate({"kind": "op", "title": "t"})
    assert JournalItem.model_validate({"kind": "decision", "title": "t"}).kind == "decision"


def test_journal_check_ignores_op_entries(tmp_path: Path, monkeypatch) -> None:
    path = journal_path(tmp_path, "plan", "p")
    append_journal_entry(path, "p", _op_entry())
    append_journal_entry(path, "p", _op_entry("op-a-2", "open"))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "p"])
    assert result.exit_code == 0, result.output


# --- the self-review floor -----------------------------------------------------


def _cut_versions() -> list[Version]:
    """Every `v*` tag reachable here, as a PEP 440 version (unparseable tags skipped)."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "tag", "-l", "v*"], capture_output=True, text=True
    ).stdout
    found = []
    for tag in out.split():
        try:
            found.append(Version(tag[1:]))
        except InvalidVersion:
            continue
    return found


def _predicted_release() -> Version:
    """The next release `scripts/release.py` cuts from this tree: the next RC of the
    final packages/fr/pyproject.toml is an RC of (`X.Y.ZrcN` -> `X.Y.Zrc(N+1)`), or
    that final plus this PR's minor bump when the tree sits on a final."""
    text = (REPO / "packages/fr/pyproject.toml").read_text()
    m = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert m is not None
    current = Version(m.group(1))
    if current.pre is not None and current.pre[0] == "rc":
        return Version(f"{current.base_version}rc{current.pre[1] + 1}")
    return Version(f"{current.major}.{current.minor + 1}.0")


def test_the_ops_floor_is_the_predicted_release() -> None:
    """p1-r1: rc1..rc3 of 5.27.0 shipped without fr ops, and `admits` lets an RC of a
    named final pass, so a `>=5.27.0` floor would admit them."""
    assert Version(OPS_FR_FLOOR) == _predicted_release()


def test_the_ops_floor_is_above_every_cut_release() -> None:
    """A release cut before this merges ships without fr ops: the floor must move."""
    cut = _cut_versions()
    if not cut:
        pytest.skip("no v* tags in this checkout")
    newest = max(cut)
    assert Version(OPS_FR_FLOOR) > newest, (
        f"OPS_FR_FLOOR {OPS_FR_FLOOR} does not exclude the cut release {newest}: raise it"
    )


@pytest.mark.parametrize(
    ("version", "admitted"),
    [("5.27.0rc3", False), ("5.27.0rc1", False), ("5.26.0", False), ("5.27.0rc4", True),
     ("5.27.0", True), ("5.28.0", True)],
)  # fmt: skip
def test_the_ops_floor_admits_only_fr_ops_releases(version: str, admitted: bool) -> None:
    assert admits(f">={OPS_FR_FLOOR},<{CEILING_VERSION}", version) is admitted


def test_self_review_refuses_a_floor_that_admits_an_earlier_rc(tmp_path: Path, monkeypatch) -> None:
    """`>=5.27.0` admits 5.27.0rc3 through the RC rule, which lacks fr ops."""
    plan_dir = _plan(tmp_path, monkeypatch)
    (plan_dir / "ops.yaml").write_text(GOOD_OPS)
    plan = parse_plan(plan_dir)
    loose = f">=5.27.0,<{CEILING_VERSION}"
    plan = dataclasses.replace(plan, meta=plan.meta.model_copy(update={"fr_version": loose}))
    assert [i for i in self_review(plan) if "fr ops" in i.message]


def _plan(tmp_path: Path, monkeypatch) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    specs = tmp_path / "docs/superpowers/specs"
    specs.mkdir(parents=True)
    (tmp_path / "docs/superpowers/plans").mkdir()
    (specs / "2026-10-22-toy.md").write_text(
        "# Toy\n\n## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    )
    phases = tmp_path / "phases.yaml"
    phases.write_text(
        "- number: 1\n  title: One\n  tier: standard\n"
        "  tasks:\n    - number: 1\n      title: t\n"
        "      steps:\n        - id: P1.T1.S1\n          text: s\n"
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "plan", "create", "--slug", "2026-10-22-toy", "--target-repo", "derio-net/own",
            "--spec", "docs/superpowers/specs/2026-10-22-toy.md", "--phases-file", str(phases),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return tmp_path / "docs/superpowers/plans/2026-10-22-toy"


def _floor_errors(plan_dir: Path) -> list[str]:
    return [
        i.message
        for i in self_review(parse_plan(plan_dir))
        if i.severity == "error" and "fr ops" in i.message
    ]


def test_self_review_refuses_a_plan_with_ops_below_the_floor(tmp_path: Path, monkeypatch) -> None:
    plan_dir = _plan(tmp_path, monkeypatch)
    assert _floor_errors(plan_dir) == []  # no ops, no floor
    (plan_dir / "ops.yaml").write_text(GOOD_OPS)
    errors = _floor_errors(plan_dir)
    assert len(errors) == 1 and OPS_FR_FLOOR in errors[0], errors


def test_self_review_passes_ops_at_the_floor(tmp_path: Path, monkeypatch) -> None:
    plan_dir = _plan(tmp_path, monkeypatch)
    (plan_dir / "ops.yaml").write_text(GOOD_OPS)
    # Not written to `_meta.yaml`: the installed fr predates the floor, so the
    # parser itself would refuse the plan. The lint reads the parsed meta.
    plan = parse_plan(plan_dir)
    floored = f">={OPS_FR_FLOOR},<{CEILING_VERSION}"
    plan = dataclasses.replace(plan, meta=plan.meta.model_copy(update={"fr_version": floored}))
    assert [i for i in self_review(plan) if "fr ops" in i.message] == []


def test_self_review_counts_step_text_ops_too(tmp_path: Path, monkeypatch) -> None:
    plan_dir = _plan(tmp_path, monkeypatch)
    phase = plan_dir / "01.yaml"
    phase.write_text(
        phase.read_text().replace(
            "text: |-\n      s\n",
            "text: |-\n      ```yaml\n      # manual-operation\n      id: x\n"
            "      why_manual: needs a click\n      ```\n",
        )
    )
    assert len(_floor_errors(plan_dir)) == 1


def test_journal_add_refuses_an_op_entry(tmp_path: Path, monkeypatch) -> None:
    """`op` entries are written only by `fr ops` (R17), never by `fr journal add`."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs/superpowers/plans/p").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["journal", "add", "--scope", "plan", "--slug", "p", "--kind", "op", "--title", "t"]
        + ["--global"],
    )
    assert result.exit_code != 0
    assert "fr ops" in result.output
    assert not journal_path(tmp_path, "plan", "p").exists()


def test_a_handoff_collapses_op_and_op_trust_entries(tmp_path: Path) -> None:
    """p1-r7: op evidence and trust decisions are written unphased; rendered in full
    they would land in every phase's handoff. They collapse to one line each."""
    from fr.journal.model import compose_handoff
    from fr.ops.trust import record_trust

    (tmp_path / "docs/superpowers/plans/p").mkdir(parents=True)
    record_trust(tmp_path, "p", {"a": "0" * 64})
    path = journal_path(tmp_path, "plan", "p")
    append_journal_entry(path, "p", _op_entry())
    decision = JournalEntry(
        kind="decision", scope="plan", id="d1", created="2026-10-22T10:00:00+00:00",
        title="a real decision", body="keep me in full",
    )  # fmt: skip
    append_journal_entry(path, "p", decision)
    text = compose_handoff(parse_journal(path.read_text()), phase=2, scope="plan", slug="p")
    assert "0" * 64 not in text and "result: done" not in text
    assert "- op-trust-1 · decision" in text and "- op-a-1 · op" in text
    assert "keep me in full" in text
