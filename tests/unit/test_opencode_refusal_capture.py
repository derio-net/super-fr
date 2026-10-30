"""Offline native-runner refusal capture regressions, sharing existing fakes."""

import json
import os
import re
from pathlib import Path

import pytest
from fr_dispatch.testing import run_item
from fr_herdr import opencode, refusal, runner

from tests.unit.test_opencode_rendered_readiness import metadata_capture

pytest_plugins = (
    "tests.unit.test_opencode_rendered_readiness",
    "tests.unit.test_opencode_startup_deadline",
)


@pytest.mark.parametrize("failure", ["text", "spinner", "draft", "metadata"])
@pytest.mark.parametrize("write_failure", [False, True])
def test_same_owned_frame_recorded_before_cleanup_once(
    timeline, tmp_path, monkeypatch, failure, write_failure
):
    d, fake = timeline
    screen = metadata_capture("ready")
    if failure == "text":
        screen += "\nplugin failed private-title /private/key sk-secret"
    elif failure == "spinner":
        screen = "⠋ Task private-title\n" + screen
    elif failure == "draft":
        screen = json.loads(
            (Path(__file__).parents[1] / "fixtures/herdr/opencode/draft.json").read_text()
        )["raw"]
    else:
        screen += "\npermission required"
    fake.refusal_screen = screen
    events = []
    directory = tmp_path.resolve() / "evidence"
    directory.mkdir(mode=0o700)
    original = refusal.publish

    def publish(path, evidence):
        events.append("capture")
        assert fake.reads == 1
        assert path == directory
        if write_failure:
            raise OSError("private path and disk failure")
        original(path, evidence)

    monkeypatch.setattr(refusal, "publish", publish)

    def cleanup():
        events.append("cleanup")

    monkeypatch.setattr(runner.HerdrRunner, "_open_tab", lambda *args: (d.pane, cleanup))
    item = run_item(
        "example/alpha",
        "batch-test",
        harness="opencode",
        model=d.model,
        checkout=d.checkout,
        branch=d.branch,
        brief="HOLD",
    )
    expected = "draft" if failure == "draft" else "unknown-dialog-or-background"
    with pytest.raises(Exception, match=expected) as caught:
        runner.HerdrRunner("w2", readiness_evidence_dir=directory).dispatch(item)
    assert str(caught.value) == expected
    assert fake.reads == 1
    assert sum(c[:2] == ["agent", "list"] for c in fake.calls) == 1
    assert sum(c[:2] == ["pane", "process-info"] for c in fake.calls) == 1
    assert all(c[2] == d.pane for c in fake.calls if c[:2] == ["pane", "read"])
    assert events == ["capture", "cleanup"]
    assert not any(c[:2] == ["agent", "prompt"] for c in fake.calls)
    if write_failure:
        assert caught.value.__notes__ == ["readiness evidence: unavailable"]
        assert list(directory.iterdir()) == []
    else:
        data = json.loads((directory / refusal.FILENAME).read_text())
        assert data["classification"] == expected
        assert (
            data["predicate"]
            == {
                "text": "plugin-error-or-failed",
                "spinner": "braille-task",
                "draft": "other",
                "metadata": "permission-required",
            }[failure]
        )
        assert data["metadata_present"]
        assert re.fullmatch(r"[0-9a-f]{64}", data["identity_sha256"])
        assert data["recorded_at"].endswith("+00:00")
        assert "private-title" not in json.dumps(data)
        assert "sk-secret" not in json.dumps(data)


def test_disabled_writer_has_zero_filesystem_calls(monkeypatch):
    monkeypatch.setattr(os, "open", lambda *a, **k: pytest.fail("filesystem opened"))
    assert opencode.capture_refusal(None, None, "draft secret", "draft") is None


def test_writer_serialization_failure_preserves_refusal(timeline, monkeypatch, tmp_path):
    d, fake = timeline
    monkeypatch.setattr(opencode, "refusal_evidence", lambda *args: {"bad": object()})
    assert opencode.capture_refusal(tmp_path, d, "permission required", "draft") == (
        "readiness evidence: unavailable"
    )
    assert list(tmp_path.iterdir()) == []


def test_late_parse_with_capture_enabled_still_times_out_without_write(
    deadline_env, monkeypatch, tmp_path
):
    d, clock, calls, observe = deadline_env

    def late_parse(screen):
        clock.now += 30
        return "unknown-dialog-or-background"

    monkeypatch.setattr(opencode, "input_reason", late_parse)
    with pytest.raises(opencode.HerdrError, match="rendered-input-timeout"):
        opencode.wait_ready(d, run=observe, evidence_dir=tmp_path)
    assert len(calls) == 3
    assert list(tmp_path.iterdir()) == []


def test_named_pattern_matches_frozen_original_regex_on_fixtures_and_boundaries():
    baseline = re.compile(
        r"permission required|allow once|allow this action|search provider setup|"
        r"web search setup|plugin (?:error|failed)|failed plugin|plugin must export|"
        r"herdr-agent-state\.js.{0,80}(?:failed|error)"
    )
    values = [
        "permission required",
        "ALLOW ONCE",
        "allow this action",
        "search provider setup",
        "web search setup",
        "plugin error",
        "plugin failed",
        "failed plugin",
        "plugin must export",
        "herdr-agent-state.js" + "x" * 80 + "error",
        "herdr-agent-state.js" + "x" * 81 + "error",
        "herdr-agent-state.js\nerror",
        "plugin\nerror",
        "permission  required",
        "allow on",
        "PLUGIN FAILED permission required",
    ]
    for path in (Path(__file__).parents[1] / "fixtures/herdr/opencode").glob("*.json"):
        data = json.loads(path.read_text())
        if isinstance(data, dict) and isinstance(data.get("raw"), str):
            values.append(data["raw"])
    for value in values:
        joined = "\n".join(
            opencode._ANSI.sub("", s).rstrip() for s in value.splitlines()
        ).casefold()
        old, new = baseline.search(joined), opencode._DIALOG.search(joined)
        assert (old.span() if old else None) == (new.span() if new else None)


@pytest.mark.parametrize("unsafe", ["symlink", "public", "missing", "relative"])
def test_actual_unsafe_destination_is_safe_annotation_only(timeline, tmp_path, unsafe):
    d, _ = timeline
    target = tmp_path.resolve() / "private"
    target.mkdir(mode=0o700)
    destination = target
    if unsafe == "symlink":
        destination = tmp_path.resolve() / "link"
        destination.symlink_to(target, target_is_directory=True)
    elif unsafe == "public":
        target.chmod(0o755)
    elif unsafe == "missing":
        destination = target / "absent"
    else:
        destination = Path("relative-evidence")
    assert opencode.capture_refusal(
        destination, d, "permission required", "unknown-dialog-or-background"
    ) == ("readiness evidence: unavailable")
    assert list(target.iterdir()) == []


def test_existing_final_symlink_is_not_followed_or_replaced(tmp_path):
    directory = tmp_path.resolve() / "private"
    directory.mkdir(mode=0o700)
    victim = tmp_path / "untouched"
    victim.write_text("operator work")
    final = directory / refusal.FILENAME
    final.symlink_to(victim)
    with pytest.raises(FileExistsError):
        refusal.publish(directory, {"frame": []})
    assert final.is_symlink()
    assert victim.read_text() == "operator work"
    assert list(directory.iterdir()) == [final]
