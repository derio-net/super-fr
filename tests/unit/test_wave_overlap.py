"""`fr.triage.wave_overlap`: which open batches of one wave expect to change the same
files (spec 2026-11-24-wave-queue-gaps R7-R10). Pure over fixture facts."""

from __future__ import annotations

from typing import Any

from fr.triage.model import Batch, Facts, Issue, Judgements, PullRequest, TriageConfig
from fr.triage.wave_overlap import (
    Overlap,
    expected_paths,
    overlap_brief_lines,
    overlap_line,
    overlap_lines,
    wave_overlaps,
)

REPO = "derio-net/super-fr"


def _issue(number: int, **kw: Any) -> Issue:
    return Issue(
        repo=REPO,
        number=number,
        title=f"issue {number}",
        state=kw.pop("state", "open"),
        url=f"https://github.com/{REPO}/issues/{number}",
        author_association=kw.pop("author_association", "OWNER"),
        **kw,
    )


def _facts(*issues: Issue, prs: list[PullRequest] | None = None, config: Any = None) -> Facts:
    return Facts(
        viewer="operator",
        schema=3,
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-11-25T12:00:00+00:00",
        repos=[REPO],
        issues=list(issues),
        prs=prs or [],
        config={REPO: TriageConfig.model_validate(config)} if config is not None else {},
    )


def _judged(**details: str) -> Judgements:
    issues = {f"super-fr#{n}": {"tier": 1, "detail": d} for n, d in details.items()}
    return Judgements.model_validate(
        {
            "schema": 14,
            "ranked_at": "2026-11-25",
            "tiers": [{"n": 1, "title": "Now"}],
            "issues": issues,
        }
    )


def _batch(bid: str, *numbers: int, wave: int | None = 1, dispatched: bool = False) -> Batch:
    doc: dict[str, Any] = {
        "id": bid,
        "title": bid,
        "ids": [f"super-fr#{n}" for n in numbers],
        "wave": wave,
    }
    if dispatched:  # a PR is the batch's only once the batch was dispatched
        doc["events"] = [
            {
                "kind": "dispatch",
                "at": "2026-11-24T10:00:00Z",
                "runner": "herdr",
                "handle": "w:p",
                "branch": f"feat/batch-{bid}",
            }
        ]
    return Batch.model_validate(doc)


def _pr(batch_id: str, files: list[str]) -> PullRequest:
    return PullRequest(
        repo=REPO,
        number=900,
        title="t",
        state="OPEN",
        is_draft=True,
        created_at="2026-11-25T00:00:00+00:00",
        url="https://x/pr",
        head_ref=f"feat/batch-{batch_id}",
        author="operator",
        cross_repo=False,
        files=files,
    )


def test_cited_paths_of_the_members_details_are_the_expected_paths() -> None:
    j = _judged(**{"1": "touches `packages/fr/src/fr/a.py` and b/c.py"})
    got = expected_paths(_batch("x", 1), j, _facts(_issue(1)))
    assert got == {"packages/fr/src/fr/a.py", "b/c.py"}


def test_a_trusted_issue_body_is_read_and_an_untrusted_one_is_skipped() -> None:
    j = _judged(**{"1": "nothing", "2": "nothing"})
    facts = _facts(
        _issue(1, body="see docs/x.md"),
        _issue(2, body="see docs/evil.md", author="eve", author_association="NONE"),
    )
    assert expected_paths(_batch("x", 1, 2), j, facts) == {"docs/x.md"}


def test_the_prs_changed_files_replace_the_citations_when_a_pr_exists() -> None:
    j = _judged(**{"1": "cites old/path.py"})
    facts = _facts(_issue(1), prs=[_pr("x", ["new/file.py"])])
    assert expected_paths(_batch("x", 1, dispatched=True), j, facts) == {"new/file.py"}


def test_generated_and_version_files_are_left_out() -> None:
    cfg = {
        "generated": ["docs/reference/*.md", "mirrors/**"],
        "version": {
            "source": {"file": "pyproject.toml", "key": "project.version"},
            "files": ["pyproject.toml", "uv.lock"],
            "set": "x {version}",
        },
    }
    j = _judged(**{"1": "a/real.py docs/reference/cli.md mirrors/skills/x.md uv.lock"})
    assert expected_paths(_batch("x", 1), j, _facts(_issue(1), config=cfg)) == {"a/real.py"}
    pr_facts = _facts(
        _issue(1),
        config=cfg,
        prs=[_pr("x", ["a/real.py", "docs/reference/cli.md", "pyproject.toml"])],
    )
    assert expected_paths(_batch("x", 1, dispatched=True), j, pr_facts) == {"a/real.py"}


def _two(
    a_text: str, b_text: str, *, wa: int | None = 1, wb: int | None = 1
) -> tuple[list[Batch], Judgements, Facts]:
    j = _judged(**{"1": a_text, "2": b_text})
    return [_batch("a", 1, wave=wa), _batch("b", 2, wave=wb)], j, _facts(_issue(1), _issue(2))


def test_two_open_batches_of_one_wave_sharing_a_path_overlap_by_suffix() -> None:
    batches, j, f = _two("tests/x.py", "x.py")
    (o,) = wave_overlaps(batches, j, f)
    assert (o.wave, o.a, o.b) == (1, "a", "b")
    assert o.paths == ("tests/x.py",)  # the longer spelling names the file


def test_no_overlap_across_waves_or_without_a_wave_or_without_a_shared_path() -> None:
    assert wave_overlaps(*_two("a/x.py", "a/x.py", wb=2)) == []
    assert wave_overlaps(*_two("a/x.py", "a/x.py", wa=None, wb=None)) == []
    assert wave_overlaps(*_two("a/x.py", "a/y.py")) == []


def test_a_closed_batch_overlaps_nothing() -> None:
    batches, j, f = _two("a/x.py", "a/x.py")
    f = f.model_copy(update={"issues": [_issue(1, state="closed"), _issue(2, state="closed")]})
    assert wave_overlaps(batches, j, f) == []


def test_only_keeps_the_pairs_that_batch_forms() -> None:
    j = _judged(**{"1": "p/x.py", "2": "p/x.py", "3": "q/y.py", "4": "q/y.py"})
    batches = [_batch("a", 1), _batch("b", 2), _batch("c", 3), _batch("d", 4)]
    f = _facts(*(_issue(n) for n in (1, 2, 3, 4)))
    assert [(o.a, o.b) for o in wave_overlaps(batches, j, f)] == [("a", "b"), ("c", "d")]
    assert [(o.a, o.b) for o in wave_overlaps(batches, j, f, only="d")] == [("c", "d")]


def test_the_line_names_wave_batches_paths_and_both_remedies() -> None:
    line = overlap_line(Overlap(2, "a", "b", ("p/x.py", "q/y.py")), 3)
    for needle in ("wave 2", "`a`", "`b`", "p/x.py", "q/y.py", "one batch", "wave 3"):
        assert needle in line


def test_overlap_lines_is_the_helper_the_verbs_print_from() -> None:
    batches, j, f = _two("p/x.py", "p/x.py")
    (line,) = overlap_lines(batches, j, f)
    assert line == overlap_line(wave_overlaps(batches, j, f)[0], 2)
    assert overlap_lines(batches, j, f, only="zzz") == []


def test_the_brief_lines_name_the_other_batch_the_paths_and_the_handback() -> None:
    batches, j, f = _two("p/x.py", "p/x.py")
    text = " ".join(overlap_brief_lines(batches[0], batches, j, f)).lower()
    assert "`b`" in text and "p/x.py" in text
    assert "whichever" in text and "lands second" in text and "conflict hand-back" in text
    assert overlap_brief_lines(_batch("c", 3), batches, j, f) == []
