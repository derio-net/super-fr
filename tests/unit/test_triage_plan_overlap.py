"""Plan file overlap between unmerged batches (spec 2026-11-25-wave-plan-file-overlap; R1-R5, R9).

The plan source is an in-memory fake holding the REAL shapes: a run cursor
(`docs/superpowers/runs/<run>.yaml`, `branch:` and `steps.<step>.emitted.plan`) and phase files
(`NN.yaml`, `schema_version: 2`, `phase.files`). The clone cases use a throwaway git repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout
from fr.triage.plan_overlap import (
    Entry,
    Overlap,
    OverlapReport,
    PlanPaths,
    Unread,
    card_lines,
    fix_text,
    overlaps,
    plan_overlap_report,
    read_plan_paths,
    report_json,
    source_for_clones,
)

from tests.unit.triage_board_fixtures import (
    REPO,
    batch,
    dispatch,
    facts,
    issue,
    j,
    judgements,
    pr,
)

RUNS = "docs/superpowers/runs"
PLAN = "docs/superpowers/plans/2026-11-25-x"


class FakeSource:
    """ref -> {path: text}; satisfies `PlanSource`."""

    def __init__(self, refs: dict[str, dict[str, str]], boom: dict[str, str] | None = None) -> None:
        self.refs = refs
        self.boom = boom or {}  # path -> message: `show` raises TriageError there

    def exists_at(self, ref: str, path: str) -> bool:
        files = self.refs.get(ref)
        if files is None:
            return False
        return path == "" or any(p == path or p.startswith(path + "/") for p in files)

    def list_dir(self, ref: str, directory: str) -> list[str]:
        prefix = directory + "/"
        names = {
            p[len(prefix) :].split("/", 1)[0]
            for p in self.refs.get(ref, {})
            if p.startswith(prefix)
        }
        return sorted(names)

    def show(self, ref: str, file: str) -> str | None:
        if file in self.boom:
            raise TriageError(self.boom[file])
        return self.refs.get(ref, {}).get(file)


def cursor(branch: str, plan: str | None = PLAN, step: str = "plan") -> str:
    steps: dict[str, Any] = {"brainstorm": {"state": "done", "emitted": {"spec": "docs/x.md"}}}
    if plan is not None:
        steps[step] = {"state": "done", "emitted": {"plan": plan}}
    return yaml.safe_dump(
        {
            "schema_version": 12,
            "run": "2026-11-25-feat-batch-x",
            "workflow": "fr-goal@1",
            "branch": branch,
            "cursor": "deliver",
            "steps": steps,
        }
    )


def phase(number: int, files: list[str]) -> str:
    return yaml.safe_dump(
        {
            "schema_version": 2,
            "phase": {"number": number, "title": "t", "tag": "agentic", "files": files},
            "tasks": [],
        }
    )


def world(branch: str, files: dict[str, list[str]], **kw: Any) -> FakeSource:
    """A source with one batch branch whose plan has the phases in *files* (01, 02, ...)."""
    tree = {f"{RUNS}/2026-11-25-feat-{branch.split('/')[-1]}.yaml": cursor(branch, **kw)}
    tree[f"{PLAN}/_meta.yaml"] = "schema_version: 1\n"
    for i, paths in enumerate(files.values(), start=1):
        tree[f"{PLAN}/{i:02d}.yaml"] = phase(i, paths)
    return FakeSource({f"refs/remotes/origin/{branch}": tree})


# ----------------------------------------------------------------- the reader (R1, R2)


def test_the_union_of_every_phases_files_is_read_at_the_remote_tracking_ref() -> None:
    src = world("feat/batch-x", {"1": ["a.py", "b.py"], "2": ["b.py", "tests/**/*.py"]})
    found = read_plan_paths(src, "feat/batch-x")
    assert isinstance(found, PlanPaths)
    assert found.plan == PLAN
    assert set(found.paths) == {"a.py", "b.py", "tests/**/*.py"}


def test_a_plan_recorded_under_another_step_name_is_still_found() -> None:
    src = world("feat/batch-x", {"1": ["a.py"]}, step="write-the-plan")
    assert isinstance(found := read_plan_paths(src, "feat/batch-x"), PlanPaths)
    assert found.paths == ("a.py",)


def test_an_absent_ref_is_not_compared() -> None:
    assert read_plan_paths(FakeSource({}), "feat/batch-x") == Unread("no ref origin/feat/batch-x")


def test_no_cursor_naming_the_branch_is_not_compared() -> None:
    src = world("feat/batch-other", {"1": ["a.py"]})
    src.refs["refs/remotes/origin/feat/batch-x"] = src.refs.pop(
        "refs/remotes/origin/feat/batch-other"
    )
    assert read_plan_paths(src, "feat/batch-x") == Unread("no run cursor")
    empty = FakeSource({"refs/remotes/origin/feat/batch-x": {"README.md": "x"}})
    assert read_plan_paths(empty, "feat/batch-x") == Unread("no run cursor")


def test_a_cursor_that_records_no_plan_is_not_compared() -> None:
    src = world("feat/batch-x", {}, plan=None)
    assert read_plan_paths(src, "feat/batch-x") == Unread("no recorded plan")


def test_invalid_yaml_in_a_cursor_is_unreadable() -> None:
    src = world("feat/batch-x", {"1": ["a.py"]})
    path = f"{RUNS}/0000-broken.yaml"
    src.refs["refs/remotes/origin/feat/batch-x"][path] = "a: [unclosed\n"
    found = read_plan_paths(src, "feat/batch-x")
    assert isinstance(found, Unread)
    assert found.reason.startswith(f"unreadable {path}: ")


def test_invalid_yaml_in_a_phase_file_is_unreadable() -> None:
    src = world("feat/batch-x", {"1": ["a.py"]})
    src.refs["refs/remotes/origin/feat/batch-x"][f"{PLAN}/01.yaml"] = "phase: [unclosed\n"
    found = read_plan_paths(src, "feat/batch-x")
    assert isinstance(found, Unread)
    assert found.reason.startswith(f"unreadable {PLAN}/01.yaml: ")


def test_a_yaml_scalar_that_is_not_a_real_date_is_unreadable_never_raised() -> None:
    # PyYAML raises a plain ValueError (not a YAMLError) for a date-shaped scalar such as
    # 2020-13-45; a branch's file is untrusted, so it must read as unreadable (p1-r1).
    src = world("feat/batch-x", {"1": ["a.py"]})
    src.refs["refs/remotes/origin/feat/batch-x"][f"{PLAN}/01.yaml"] = "created: 2020-13-45\n"
    found = read_plan_paths(src, "feat/batch-x")
    assert isinstance(found, Unread)
    assert found.reason.startswith(f"unreadable {PLAN}/01.yaml: ")


def test_a_git_failure_is_unreadable_never_raised() -> None:
    src = world("feat/batch-x", {"1": ["a.py"]})
    cursor_path = f"{RUNS}/2026-11-25-feat-batch-x.yaml"
    src.boom[cursor_path] = "git exploded"
    assert read_plan_paths(src, "feat/batch-x") == Unread(f"unreadable {cursor_path}: git exploded")


def test_a_plan_folder_that_is_not_on_the_branch_is_unreadable() -> None:
    src = world("feat/batch-x", {})
    del src.refs["refs/remotes/origin/feat/batch-x"][f"{PLAN}/_meta.yaml"]
    found = read_plan_paths(src, "feat/batch-x")
    assert isinstance(found, Unread)
    assert found.reason.startswith(f"unreadable {PLAN}: ")


def test_a_phase_whose_files_are_missing_or_not_a_list_adds_nothing() -> None:
    src = world("feat/batch-x", {"1": ["a.py"]})
    tree = src.refs["refs/remotes/origin/feat/batch-x"]
    tree[f"{PLAN}/02.yaml"] = yaml.safe_dump({"phase": {"number": 2}})
    tree[f"{PLAN}/03.yaml"] = yaml.safe_dump({"phase": {"number": 3, "files": "oops"}})
    assert isinstance(found := read_plan_paths(src, "feat/batch-x"), PlanPaths)
    assert found.paths == ("a.py",)


# ----------------------------------------------------------------- the rule (R3-R5)


def entry(bid: str, paths: list[str], *, repo: str = REPO, wave: int | None = 1, before: Any = ()):
    return Entry(bid, repo, wave, frozenset(before), tuple(paths))


def shared(a: list[str], b: list[str], ignore: tuple[str, ...] = ()) -> tuple[str, ...]:
    found = overlaps([entry("a", a), entry("b", b)], ignore=ignore)
    return found[0].paths if found else ()


def test_a_path_both_name_literally_is_shared() -> None:
    assert shared(["x.py", "y.py"], ["y.py", "z.py"]) == ("y.py",)


def test_a_glob_of_one_matching_a_literal_of_the_other_is_shared_both_ways() -> None:
    assert shared(["tests/**/*.py"], ["tests/unit/t.py", "src/a.py"]) == ("tests/unit/t.py",)
    assert shared(["tests/unit/t.py", "src/a.py"], ["tests/**/*.py"]) == ("tests/unit/t.py",)


def test_a_bracketed_literal_path_is_a_literal_not_a_glob() -> None:
    # `[` is common in real paths (route segments such as app/[id]/page.tsx); only `*` and
    # `?` make a plan path a glob (p1-r2).
    assert shared(["app/[id]/page.tsx"], ["app/[id]/page.tsx"]) == ("app/[id]/page.tsx",)
    assert shared(["app/**"], ["app/[id]/page.tsx"]) == ("app/[id]/page.tsx",)


def test_two_globs_are_never_shared() -> None:
    assert shared(["tests/**/*.py"], ["tests/**/*.py"]) == ()
    assert shared(["docs/**/*.md"], ["docs/*.md"]) == ()


def test_a_path_matching_an_ignore_glob_is_dropped() -> None:
    ignore = (".opencode/skills/*", "pyproject.toml")
    got = shared(
        [".opencode/skills/a/SKILL.md", "pyproject.toml", "real.py"],
        [".opencode/skills/a/SKILL.md", "pyproject.toml", "real.py"],
        ignore,
    )
    assert got == ("real.py",)
    assert shared([".opencode/skills/a/SKILL.md"], [".opencode/skills/*"], ignore) == ()


def test_shared_paths_are_sorted_and_a_pair_without_any_is_absent() -> None:
    assert shared(["b.py", "a.py"], ["a.py", "b.py"]) == ("a.py", "b.py")
    assert overlaps([entry("a", ["a.py"]), entry("b", ["b.py"])], ignore=()) == []


def test_batches_of_different_repos_are_never_paired() -> None:
    found = overlaps([entry("a", ["x.py"]), entry("b", ["x.py"], repo="o/other")], ignore=())
    assert found == []


def test_the_pair_is_reported_with_both_waves_and_the_repo() -> None:
    found = overlaps([entry("a", ["x.py"], wave=1), entry("b", ["x.py"], wave=3)], ignore=())
    assert found == [Overlap("a", "b", REPO, 1, 3, ("x.py",))]


def test_an_after_link_in_either_direction_or_through_a_third_batch_serialises_the_pair() -> None:
    a, b = ["x.py"], ["x.py"]
    assert overlaps([entry("a", a, before={"b"}), entry("b", b)], ignore=()) == []
    assert overlaps([entry("a", a), entry("b", b, before={"a"})], ignore=()) == []
    # A after C after B, C merged and so not an entry: the closure carries B in A's set.
    assert overlaps([entry("a", a, before={"c", "b"}), entry("b", b)], ignore=()) == []


def test_two_unlinked_batches_of_different_waves_are_compared() -> None:
    found = overlaps([entry("a", ["x.py"], wave=1), entry("b", ["x.py"], wave=2)], ignore=())
    assert len(found) == 1


# ----------------------------------------------------------------- the report (R1, R2, R5, R9)


def state(batches: list[dict[str, Any]], **kw: Any) -> Any:
    keys = sorted({k for b in batches for k in b["ids"]})
    issues = [issue(int(k.split("#")[1])) for k in keys]
    return facts(issues, **kw), judgements({k: j(1) for k in keys}, batches)


def clones(sources: dict[str, FakeSource]) -> Any:
    return lambda repo: sources.get(repo) or f"no clone of {repo} here"


def two_overlapping(**kw: Any) -> Any:
    b1 = batch("b1", [1], wave=1, events=[dispatch("b1")], **kw)
    b2 = batch("b2", [2], wave=2, events=[dispatch("b2")])
    return state([b1, b2])


def both_plans(a: list[str], b: list[str]) -> FakeSource:
    one, two = world("feat/batch-b1", {"1": a}), world("feat/batch-b2", {"1": b})
    one.refs.update(two.refs)
    return one


def test_dispatched_batches_whose_plans_share_a_file_are_reported() -> None:
    f, jd = two_overlapping()
    report = plan_overlap_report(jd, f, clones({REPO: both_plans(["a.py", "x.py"], ["x.py"])}))
    assert report == OverlapReport((Overlap("b1", "b2", REPO, 1, 2, ("x.py",)),), ())


def test_only_dispatched_and_pr_open_batches_are_read() -> None:
    cancel = {"kind": "cancel", "at": "2026-10-01T12:00:00Z"}
    f, jd = state(
        [
            batch("b1", [1], events=[dispatch("b1")]),
            batch("b2", [2]),  # proposed
            batch("b3", [3], events=[dispatch("b3"), cancel]),  # cancelled
        ]
    )
    asked: list[str] = []

    def source_for(repo: str) -> FakeSource:
        asked.append(repo)
        return both_plans(["x.py"], ["x.py"])

    report = plan_overlap_report(jd, f, source_for)
    assert report.overlaps == () and [b for b, _ in report.unread] == []
    assert asked == [REPO]  # only b1 was read


def test_a_batch_of_an_unknown_repo_is_not_compared() -> None:
    f, jd = two_overlapping()
    foreign = f.model_copy(update={"repos": ["o/elsewhere"]})
    report = plan_overlap_report(jd, foreign, clones({}))
    assert report.unread == (("b1", "repo of batch unknown"), ("b2", "repo of batch unknown"))


def test_a_str_from_the_source_factory_is_the_reason() -> None:
    f, jd = two_overlapping()
    report = plan_overlap_report(jd, f, lambda repo: "no clone here")
    assert report.unread == (("b1", "no clone here"), ("b2", "no clone here"))
    assert report.overlaps == ()


def test_an_unreadable_batch_is_listed_and_never_overlaps() -> None:
    f, jd = two_overlapping()
    only_b1 = world("feat/batch-b1", {"1": ["x.py"]})
    report = plan_overlap_report(jd, f, clones({REPO: only_b1}))
    assert report.overlaps == ()
    assert report.unread == (("b2", "no ref origin/feat/batch-b2"),)


def test_generated_and_version_files_from_the_repo_config_are_ignored() -> None:
    b1 = batch("b1", [1], wave=1, events=[dispatch("b1")])
    b2 = batch("b2", [2], wave=2, events=[dispatch("b2")])
    config = {
        REPO: {
            "generated": [".opencode/skills/*"],
            "version": {
                "source": {"file": "pyproject.toml", "key": "project.version"},
                "files": ["pyproject.toml", "packages/*/pyproject.toml"],
                "set": "bump {version}",
            },
        }
    }
    f, jd = state([b1, b2], config=config)
    common = [".opencode/skills/a/SKILL.md", "pyproject.toml", "packages/fr/pyproject.toml"]
    src = both_plans([*common, "r.py"], [*common, "r.py"])
    report = plan_overlap_report(jd, f, clones({REPO: src}))
    assert report.overlaps[0].paths == ("r.py",)


def test_an_after_chain_through_a_merged_batch_suppresses_the_pair() -> None:
    merged_pr = pr(50, "feat/batch-c", state="MERGED", merged_at="2026-10-01T12:00:00Z")
    b1 = batch("b1", [1], events=[dispatch("b1")], after=["c"])
    b2 = batch("b2", [2], events=[dispatch("b2")])
    c = batch("c", [3], events=[dispatch("c")], after=["b2"])
    f = facts([issue(1), issue(2), issue(3, state="closed", prs=[merged_pr])])
    jd = judgements({"widgets#1": j(), "widgets#2": j(), "widgets#3": j()}, [b1, b2, c])
    src = both_plans(["x.py"], ["x.py"])
    assert plan_overlap_report(jd, f, clones({REPO: src})).overlaps == ()


# ----------------------------------------------------------------- the clone rule (R9)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def clone(path: Path, origin: str | None = "https://github.com/o/r.git") -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q")
    if origin:
        git(path, "remote", "add", "origin", origin)
    return path


def test_checkouts_open_the_named_clone(tmp_path: Path) -> None:
    root = clone(tmp_path / "c")
    got = source_for_clones(tmp_path, {"o/r": root})("O/R")
    assert isinstance(got, Checkout) and got.path.resolve() == root.resolve()
    assert source_for_clones(tmp_path, {"o/r": root})("o/other") == "no clone of o/other here"


def test_checkouts_pointing_at_no_clone_say_no_clone_here(tmp_path: Path) -> None:
    assert source_for_clones(tmp_path, {"o/r": tmp_path / "gone"})("o/r") == "no clone here"


def test_the_cwd_clone_serves_only_the_repo_that_is_its_origin_case_insensitively(
    tmp_path: Path,
) -> None:
    root = clone(tmp_path / "c")
    source_for = source_for_clones(root, None)
    assert isinstance(source_for("O/r"), Checkout)
    assert source_for("o/other") == "no clone of o/other here"


def test_a_cwd_outside_a_clone_or_a_clone_with_no_origin_never_raises(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    assert source_for_clones(outside, None)("o/r") == "no clone here"
    assert source_for_clones(clone(tmp_path / "noorigin", origin=None), None)("o/r") == (
        "no clone here"
    )


def test_a_real_clone_satisfies_the_plan_source_for_a_missing_ref(tmp_path: Path) -> None:
    root = clone(tmp_path / "c")
    got = source_for_clones(root, None)("o/r")
    assert read_plan_paths(got, "feat/batch-x") == Unread("no ref origin/feat/batch-x")  # type: ignore[arg-type]


# ----------------------------------------------------------------- the wording and the card text


def test_the_fix_names_both_batches_and_both_remedies() -> None:
    text = fix_text("b1", "b2")
    assert "b1" in text and "b2" in text
    assert "fr triage batch edit b2 --after b1" in text
    assert "--wave" in text and "one batch" in text


def test_each_batch_gets_one_sentence_per_overlap_naming_the_other_and_the_paths() -> None:
    report = OverlapReport(
        (
            Overlap("b1", "b2", REPO, 1, 2, ("x.py", "y.py")),
            Overlap("b1", "b3", REPO, 1, 1, ("z.py",)),
        ),
        (),
    )
    lines = card_lines(report)
    assert set(lines) == {"b1", "b2", "b3"}
    assert len(lines["b1"]) == 2 and len(lines["b2"]) == 1
    assert "b2" in lines["b1"][0] and "x.py, y.py" in lines["b1"][0]
    assert "b1" in lines["b2"][0] and fix_text("b1", "b2") in lines["b2"][0]


def test_the_json_form_carries_overlaps_and_unread() -> None:
    report = OverlapReport(
        (Overlap("b1", "b2", REPO, 1, None, ("x.py",)),), (("b3", "no run cursor"),)
    )
    assert report_json(report) == {
        "overlaps": [
            {
                "a": "b1",
                "b": "b2",
                "repo": REPO,
                "waves": [1, None],
                "paths": ["x.py"],
                "fix": fix_text("b1", "b2"),
            }
        ],
        "unread": [{"batch": "b3", "reason": "no run cursor"}],
    }
