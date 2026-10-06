"""The PR body's verification sections and the premature-close gate (spec
2026-10-06-verification-strategies §D, R12, R15)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.exceptions import Exit
from fr.acceptance.model import Matrix, Row
from fr.record.pr_body import (
    REQUIRED_SECTIONS,
    closing_refs,
    normalize_issue_ref,
    premature_closes,
    render_pr_body,
    shared_closing_keywords,
)
from fr.run.model import load_run_state

from tests.unit.test_verification_walk import RUN, SPEC_REF, _git, _repo

IDENTITY = ("o", "proj")


def _row(rid: str, *, verify: str | None = None, issues: tuple[str, ...] = (), walks=()) -> Row:
    return Row(
        id=rid,
        capability="c",
        acceptance=f"{rid} works",
        origin=(f"{SPEC_REF}#R1",),
        status="not-implemented",
        verify=verify,
        issues=issues,
        walks=walks,
    )


def _live(row: Row) -> bool:
    return row.verify == "live" and not row.walks


# --- closing_refs ---------------------------------------------------------------


def test_closing_refs_pairs_each_reference_with_the_keyword_before_it() -> None:
    body = "Closes #1\nFixes: o/r#2 and resolves https://github.com/o/r/issues/3\n"

    assert closing_refs(body) == [
        ("Closes #1", "Closes", "#1"),
        ("Fixes: o/r#2 and resolves https://github.com/o/r/issues/3", "Fixes", "o/r#2"),
        (
            "Fixes: o/r#2 and resolves https://github.com/o/r/issues/3",
            "resolves",
            "https://github.com/o/r/issues/3",
        ),
    ]


@pytest.mark.parametrize(
    "body",
    [
        "```\nCloses #1\n```\n",
        "Quoting `Closes #1` here\n",
        "See #1 for context\n",
        "<!-- rendered by fr for run r1; edit above this line only -->\n- p1 fixed → #4\n",
        "Fixes the parser\n",
    ],
)
def test_closing_refs_skips_code_mentions_and_fr_renders(body: str) -> None:
    assert closing_refs(body) == []


def test_shared_closing_keywords_is_unchanged_by_the_factoring() -> None:
    [(bad, fixed)] = shared_closing_keywords("Closes #1, o/r#2 and #3\n")

    assert bad == "Closes #1, o/r#2 and #3"
    assert fixed == ["Closes #1", "Closes o/r#2", "Closes #3"]


# --- normalisation (no forge call) -------------------------------------------------


@pytest.mark.parametrize(
    ("written", "want"),
    [
        ("#7", "o/proj#7"),
        ("other/repo#7", "other/repo#7"),
        ("https://github.com/other/repo/issues/7", "other/repo#7"),
        ("https://gitlab.example.com/other/repo/-/issues/7", "other/repo#7"),
        ("https://gitlab.example.com/grp/sub/repo/-/issues/7", "grp/sub/repo#7"),
        ("nonsense", None),
    ],
)
def test_references_normalise_to_owner_repo_number(written: str, want: str | None) -> None:
    assert normalize_issue_ref(written, IDENTITY) == want


# --- premature_closes ----------------------------------------------------------------


def test_a_close_of_an_issue_a_live_row_holds_open_is_reported_with_the_refs_fix() -> None:
    matrix = Matrix(
        rows=(
            _row("held", verify="live", issues=("o/proj#7",)),
            _row("free", verify="candidate", issues=("o/proj#8",)),
        )
    )
    body = "Closes #7\nFixes o/proj#8\nCloses https://github.com/o/proj/issues/7\n"

    found = premature_closes(body, matrix, IDENTITY, _live)

    assert [(p.line, p.ref, p.rows, p.fix) for p in found] == [
        ("Closes #7", "o/proj#7", ("held",), "Refs o/proj#7"),
        (
            "Closes https://github.com/o/proj/issues/7",
            "o/proj#7",
            ("held",),
            "Refs o/proj#7",
        ),
    ]


def test_a_walk_verified_row_no_longer_holds_its_issue() -> None:
    from fr.acceptance.model import Walk

    walk = Walk(
        strategy="live", harness="h", model="m", outcome="pass", at="2026-10-06", evidence="n"
    )
    matrix = Matrix(rows=(_row("done", verify="live", issues=("o/proj#7",), walks=(walk,)),))

    assert premature_closes("Closes #7\n", matrix, IDENTITY, _live) == []


def test_a_mention_without_a_keyword_is_not_a_close() -> None:
    matrix = Matrix(rows=(_row("held", verify="live", issues=("o/proj#7",)),))

    assert premature_closes("Refs #7\nSee #7\n", matrix, IDENTITY, _live) == []


# --- the sections ---------------------------------------------------------------------


def test_the_pre_merge_section_is_required_and_precedes_the_post_merge_one() -> None:
    assert REQUIRED_SECTIONS.index("## Pre-merge verification owed") < REQUIRED_SECTIONS.index(
        "## Post-merge verification owed"
    )


def _matrix(root: Path, rows: list[dict[str, object]]) -> None:
    base = {"capability": "c", "origin": [f"{SPEC_REF}#R1"], "status": "not-implemented"}
    (root / "docs/acceptance/matrix.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 4,
                "org": "o",
                "repo": "proj",
                "rows": [{**base, "acceptance": f"{r['id']} works", **r} for r in rows],
            }
        )
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "matrix", "--no-verify")


def _body(root: Path) -> str:
    return render_pr_body(root, load_run_state(root, RUN))


def test_the_body_lists_each_operator_row_with_its_exact_walk_command(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _matrix(
        root,
        [
            {"id": "client-row", "verify": "client-live"},
            {"id": "scripted", "verify": "candidate"},
            {"id": "after", "verify": "live"},
        ],
    )

    body = _body(root)

    pre = body.split("## Pre-merge verification owed")[1].split("## Post-merge")[0]
    assert (
        f"`fr verification walk --run {RUN} --model <model> --strategy client-live "
        "--client <client-repo> --row client-row`" in pre
    )
    assert "scripted" not in pre and "`after`" not in pre  # agent-driven / post-merge
    assert "- [ ] Ready" in pre
    post = body.split("## Post-merge verification owed")[1].split("## Proportionality")[0]
    assert "`after`" in post and "no reason recorded (legacy)" in post


def test_a_run_with_no_operator_row_renders_none(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    pre = _body(root).split("## Pre-merge verification owed")[1].split("## Post-merge")[0]

    assert pre.strip() == "None."


# --- the gate ---------------------------------------------------------------------------


def _gate(root: Path, live: str) -> None:
    from fr.commands import run_cmd

    run_cmd._refuse_premature_closes(root, load_run_state(root, RUN), live)


def test_the_gate_refuses_a_premature_close_printing_the_line_and_the_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    _matrix(root, [{"id": "after", "verify": "live", "issues": ["o/proj#7"]}])

    with pytest.raises(Exit) as exc:
        _gate(root, "Summary\n\nCloses #7\n")

    assert exc.value.exit_code == 2
    err = capsys.readouterr().err.replace("\n", " ")
    assert "Closes #7" in err and "Refs o/proj#7" in err and "after" in err


def test_the_gate_passes_refs_and_unrelated_closes(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _matrix(root, [{"id": "after", "verify": "live", "issues": ["o/proj#7"]}])

    _gate(root, "Refs #7\nCloses #9\n")  # no raise


def test_the_gate_is_inert_without_a_matrix_citing_an_issue(tmp_path: Path) -> None:
    root = _repo(tmp_path)  # rows cite no issue

    _gate(root, "Closes #7\n")  # no raise, and no identity lookup needed


def test_a_walk_verified_row_lets_the_close_through(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _matrix(
        root,
        [
            {
                "id": "after",
                "verify": "live",
                "issues": ["o/proj#7"],
                "walks": [
                    {
                        "strategy": "live",
                        "harness": "h",
                        "model": "m",
                        "outcome": "pass",
                        "at": "2026-10-06T00:00:00+00:00",
                        "evidence": "note",
                    }
                ],
            }
        ],
    )

    _gate(root, "Closes #7\n")
