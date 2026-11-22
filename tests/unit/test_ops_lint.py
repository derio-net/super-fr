"""An `apply` that only prints acts on nothing (gh#1614): the predicate, self-review's
error and `fr ops apply`'s refusal to count it as applied."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.ops.lint import print_only

from tests.unit.test_ops_apply import FakePrompt, World, op, run


@pytest.mark.parametrize(
    "command",
    [
        'echo "Build and push ghcr.io/example/img:v0.1.2, then make it public"',
        "printf '%s\\n' 'run: docker buildx build --push .'",
        "cat <<EOF\ndocker buildx build --push -t x .\nkubectl apply -f y\nEOF",
        "cat <<'EOF'\nrm -rf /srv/data\nEOF\necho done",
        # the frank shape: compute the tag, then print the command instead of running it
        'TAG="$(git rev-parse --short HEAD)"\necho "docker buildx build --push -t img:$TAG ."',
        "echo one; echo two && printf x || true",
        "echo hi >&2",
        "echo hi > /dev/stderr",
        ":",
        "# only a comment\necho note",
        # review: unquoted substitutions beside a separator, nested ones, value-only bodies
        'TAG=$(git rev-parse --short HEAD); echo "docker push img:$TAG"',
        'echo "tag: $(git describe --tags $(git rev-list -n1 HEAD))"',
        'for f in a b; do echo "$f"; done',
        "command echo hi",
        "/bin/echo hi",
        'echo "$((1 << 2))"',
    ],
)
def test_a_command_that_only_prints_is_print_only(command: str) -> None:
    assert print_only(command)


@pytest.mark.parametrize(
    "command",
    [
        "docker buildx build --push -t img .",
        'TAG="$(git rev-parse HEAD)"\ndocker push "img:$TAG"',
        "echo start && kubectl apply -f k8s/",
        "echo secret | gh secret set NAME",
        "cat manifest.yaml | kubectl apply -f -",
        "echo value > config/setting.txt",
        "printf x >> log.txt",
        "cat > out.yaml <<EOF\na: 1\nEOF",
        "bash scripts/deploy.sh",
        "./scripts/apply.sh --yes",
        "if true; then gh api -X PUT repos/x; fi",
        "sudo systemctl restart x",
        "echo a # a trailing comment\ndocker push img",  # the comment must not eat the newline
        # review (gh#1614): a substitution's body runs, so it is judged too
        "TAG=$(git rev-parse HEAD); docker push img:$TAG",
        "echo $(date); rm x",
        "echo $(date)|tee f",
        "echo $(date)>f",
        'OUT="$(kubectl apply -f m.yaml)"',
        "echo $(docker push x)",
        "echo `rm x`",
        "cat <(rm x)",
        ": ${X:=$(rm y)}",
        'echo "$(a $(rm b))"',
        "cat <<EOF\n$(docker push img)\nEOF",  # an unquoted heredoc body expands
        "git push origin HEAD",
        # review: a `<<` that opens no heredoc must not hide the next lines
        'echo "x <<EOF"\nrm x',
        "cat <<<EOF\nrm x",
        "# see <<EOF\nrm x",
        "echo $((1 << 2))\nrm x",
        # review: digits are a file after a plain `>`; `<>` opens a file for writing
        "echo x > 1",
        "cat <>f",
        "",
        "echo 'unterminated",  # unparseable: not judged, so never flagged
    ],
)
def test_a_command_that_can_act_is_not_print_only(command: str) -> None:
    assert not print_only(command)


def test_apply_does_not_count_a_print_only_apply_as_applied() -> None:
    """The false-DONE path: the echo exits 0 and the op must NOT be applied or
    recorded done; it is a manual step, and its text is shown."""
    w = World()
    o = op("img", apply='echo "docker buildx build --push"', mutating=True)
    res = run([o], w, FakePrompt(), yes=True, yes_mutating=True)
    assert w.ran == []
    assert w.written == []
    assert res.steps[-1].outcome == "manual"
    assert "only prints" in res.steps[-1].message
    assert "docker buildx build --push" in res.steps[-1].message


def _review_errors(plan_dir: Path) -> list[str]:
    from fr.parser import parse as parse_plan
    from fr.plan_ops import self_review

    return [i.message for i in self_review(parse_plan(plan_dir)) if i.severity == "error"]


def _with_ops(tmp_path: Path, monkeypatch, ops_yaml: str) -> Path:
    from tests.unit.test_ops_artifacts import _plan

    plan_dir = _plan(tmp_path, monkeypatch)
    (plan_dir / "ops.yaml").write_text(ops_yaml)
    return plan_dir


def test_self_review_errors_on_a_print_only_apply(tmp_path: Path, monkeypatch) -> None:
    plan_dir = _with_ops(
        tmp_path,
        monkeypatch,
        "schema_version: 2\nops:\n"
        "  - id: premerge-image\n    summary: build and push the image\n"
        "    phase: pre-merge\n    mutating: true\n"
        "    check: docker manifest inspect img:v1\n"
        '    apply: echo "docker buildx build --push -t img:v1 ."\n',
    )
    errors = [e for e in _review_errors(plan_dir) if "premerge-image" in e]
    assert len(errors) == 1, errors
    assert "only prints" in errors[0] and "commands:" in errors[0]


def test_self_review_accepts_an_apply_that_acts(tmp_path: Path, monkeypatch) -> None:
    plan_dir = _with_ops(
        tmp_path,
        monkeypatch,
        "schema_version: 2\nops:\n"
        "  - id: premerge-image\n    summary: build and push the image\n"
        "    phase: pre-merge\n    mutating: true\n"
        "    check: docker manifest inspect img:v1\n"
        "    apply: docker buildx build --push -t img:v1 .\n",
    )
    assert not [e for e in _review_errors(plan_dir) if "premerge-image" in e]


def test_a_done_entry_says_whether_the_apply_ran() -> None:
    """Audit finding (gh#1614): an op found already DONE and an op fr applied wrote the
    same `result: done` entry, so no journal could tell whether an apply acted. The
    entry now says which."""
    from fr.ops.apply import APPLIED_DONE, FOUND_DONE

    found, applied = World(done={"a"}), World()
    run([op("a")], found)
    run([op("b")], applied, FakePrompt(), yes=True)
    assert found.ran == [] and found.written[-1]["reason"] == FOUND_DONE
    assert applied.ran and applied.written[-1]["reason"] == APPLIED_DONE
    assert FOUND_DONE != APPLIED_DONE and "not run" in FOUND_DONE
