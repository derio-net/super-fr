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


def test_ops_is_a_registered_kind_at_version_two() -> None:
    kind = ARTIFACT_KINDS["ops"]
    assert kind.current_version == 2
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


@pytest.mark.parametrize("stamp", ["schema_version: 1\n", ""])
def test_the_ops_validator_refuses_none_below_version_two(tmp_path: Path, stamp: str) -> None:
    """spec 2026-11-01-ops-gate-probes R4: `none:` arrived with version 2."""
    path = tmp_path / "ops.yaml"
    path.write_text(stamp + "none: nothing to run\n")
    validate = ARTIFACT_KINDS["ops"].validate
    assert validate is not None
    problems = validate(path)
    assert any("none" in p and "2" in p for p in problems), problems


def test_the_ops_validator_accepts_none_at_version_two(tmp_path: Path) -> None:
    path = tmp_path / "ops.yaml"
    path.write_text("schema_version: 2\nnone: nothing to run\n")
    validate = ARTIFACT_KINDS["ops"].validate
    assert validate is not None and validate(path) == []


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


OPS_PACKAGE = "packages/fr/src/fr/ops"


def _cut_releases() -> dict[Version, bool]:
    """Every `v*` tag reachable here, as a PEP 440 version mapped to whether that
    release's tree ships `fr ops` (unparseable tags skipped)."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "tag", "-l", "v*"], capture_output=True, text=True
    ).stdout
    tags = {}
    for tag in out.split():
        try:
            tags[tag] = Version(tag[1:])
        except InvalidVersion:
            continue
    if not tags:
        return {}
    # One process for every tag: a `cat-file -e` per tag costs ~50ms each, x270.
    checked = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "--batch-check"],
        input="".join(f"{tag}:{OPS_PACKAGE}\n" for tag in tags),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert len(checked) == len(tags), checked
    return {
        version: not line.endswith(" missing")
        for version, line in zip(tags.values(), checked, strict=True)
    }


def _tree_version() -> Version:
    text = (REPO / "packages/fr/pyproject.toml").read_text()
    m = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert m is not None
    return Version(m.group(1))


def _next_release(current: Version) -> Version:
    """The release `scripts/release.py` cuts after `current`: its next RC
    (`X.Y.ZrcN` -> `X.Y.Zrc(N+1)`), or the next minor when it is a final."""
    if current.pre is not None and current.pre[0] == "rc":
        return Version(f"{current.base_version}rc{current.pre[1] + 1}")
    return Version(f"{current.major}.{current.minor + 1}.0")


def _first_ops_release(tree: Version, cut: dict[Version, bool]) -> Version:
    """The first release that ships fr ops, from wherever this tree sits: the oldest
    cut release that ships it; else this tree, when its version is not cut yet
    (release.py tests the staged tree before tagging it); else the next release."""
    shipped = [version for version, ships in cut.items() if ships]
    if shipped:
        return min(shipped)
    if tree not in cut:
        return tree
    return _next_release(tree)


@pytest.mark.parametrize(
    ("tree", "cut", "expected"),
    [
        # a PR (or main) before the release: the tree sits on the last cut RC
        ("6.0.0rc2", {"6.0.0rc1": False, "6.0.0rc2": False}, "6.0.0rc3"),
        # release.py's staged tree: bumped, suite run BEFORE the tag (gh run 39897787577)
        ("6.0.0rc3", {"6.0.0rc1": False, "6.0.0rc2": False}, "6.0.0rc3"),
        # main after the tag
        ("6.0.0rc3", {"6.0.0rc2": False, "6.0.0rc3": True}, "6.0.0rc3"),
        # later releases never move it
        ("6.1.0", {"6.0.0rc2": False, "6.0.0rc3": True, "6.0.0": True}, "6.0.0rc3"),
    ],
)  # fmt: skip
def test_the_first_ops_release_holds_across_the_release_lifecycle(
    tree: str, cut: dict[str, bool], expected: str
) -> None:
    """The floor tests run on PRs, on main, and on the release's own staged tree;
    a prediction from the tree's version alone fails the release it predicts."""
    releases = {Version(v): ships for v, ships in cut.items()}
    assert _first_ops_release(Version(tree), releases) == Version(expected)


def test_the_ops_floor_is_the_first_release_that_ships_ops() -> None:
    """p1-r1: the RCs cut before fr ops merged (5.27.0rc1-3, 6.0.0rc1-2) ship without it,
    and `admits` lets an RC of a named final pass, so a `>=6.0.0` floor would admit them."""
    cut = _cut_releases()
    if not cut:
        pytest.skip("no v* tags in this checkout")
    assert Version(OPS_FR_FLOOR) == _first_ops_release(_tree_version(), cut)


def test_the_ops_floor_excludes_every_release_without_ops() -> None:
    """A release cut before fr ops merged ships without it: the floor must exclude it,
    and must admit every release that does ship it."""
    cut = _cut_releases()
    if not cut:
        pytest.skip("no v* tags in this checkout")
    floor = Version(OPS_FR_FLOOR)
    wrong = [str(v) for v, ships in sorted(cut.items()) if (floor <= v) != ships]
    assert not wrong, f"OPS_FR_FLOOR {OPS_FR_FLOOR} misclassifies cut releases {wrong}"


@pytest.mark.parametrize(
    ("version", "admitted"),
    [("6.0.0rc2", False), ("6.0.0rc1", False), ("5.27.0rc3", False), ("5.26.0", False),
     ("6.0.0rc3", True), ("6.0.0", True), ("6.1.0", True)],
)  # fmt: skip
def test_the_ops_floor_admits_only_fr_ops_releases(version: str, admitted: bool) -> None:
    assert admits(f">={OPS_FR_FLOOR},<{CEILING_VERSION}", version) is admitted


def test_self_review_refuses_a_floor_that_admits_an_earlier_rc(tmp_path: Path, monkeypatch) -> None:
    """`>=6.0.0` admits 6.0.0rc2 through the RC rule, which lacks fr ops."""
    plan_dir = _plan(tmp_path, monkeypatch)
    (plan_dir / "ops.yaml").write_text(GOOD_OPS)
    plan = parse_plan(plan_dir)
    loose = f">=6.0.0,<{CEILING_VERSION}"
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
    from fr.ops.trust import grant_trust

    (tmp_path / "docs/superpowers/plans/p").mkdir(parents=True)
    grant_trust(tmp_path, "p", {"a": "0" * 64})
    path = journal_path(tmp_path, "plan", "p")
    append_journal_entry(path, "p", _op_entry())
    decision = JournalEntry(
        kind="decision", scope="plan", id="d1", created="2026-10-22T10:00:00+00:00",
        title="a real decision", body="keep me in full",
    )  # fmt: skip
    append_journal_entry(path, "p", decision)
    text = compose_handoff(parse_journal(path.read_text()), phase=2, scope="plan", slug="p")
    assert "sha256:" not in text and "result: done" not in text
    assert "- op-trust-1 · decision" in text and "- op-a-1 · op" in text
    assert "keep me in full" in text
