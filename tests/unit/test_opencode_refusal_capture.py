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


@pytest.mark.parametrize("row,column", [(63, 141), (63, 142), (64, 0), (0, 161)])
def test_trigger_span_identifies_exact_crop_boundary(row, column):
    text = "permission required"
    screen = "\n" * row + "x" * column + text
    reason = opencode.input_reason(screen)
    assert reason == "unknown-dialog-or-background"
    evidence = opencode.refusal_evidence(screen, reason)
    assert evidence["predicate_span"] == {
        "start": [row, column],
        "end": [row, column + len(text)],
    }
    assert evidence["predicate_outside_capture"] == (row >= 64 or column + len(text) > 160)
    assert evidence["predicate"] == "permission-required"


@pytest.mark.parametrize("prefix", ["ß", "İ", "ßİ", "ß\nİ", "ß\r\nİ", "\x1b[31mßİ\x1b[0m"])
def test_casefold_expansion_maps_back_to_original_character_coordinates(prefix):
    screen = prefix + "plugin failed permission required"
    reason = opencode.input_reason(screen)
    evidence = opencode.refusal_evidence(screen, reason)
    clean = opencode._ANSI.sub("", prefix)
    row = clean.count("\n")
    col = len(clean.rsplit("\n", 1)[-1])
    assert reason == "unknown-dialog-or-background"
    assert evidence["predicate"] == "plugin-error-or-failed"
    assert evidence["predicate_span"] == {"start": [row, col], "end": [row, col + 13]}
    assert evidence["predicate_outside_capture"] is False


def test_span_reports_actual_text_before_spinner_branch_and_no_secret_payload():
    screen = (
        "⠋ Task secret\n" + metadata_capture("ready") + "\nherdr-agent-state.js sk-secret failed"
    )
    reason = opencode.input_reason(screen)
    assert reason == "unknown-dialog-or-background"
    evidence = opencode.refusal_evidence(screen, reason)
    assert evidence["predicate"] == "agent-state-plugin"
    assert evidence["predicate_span"]["start"][1] == 0
    assert "sk-secret" not in json.dumps(evidence)
    assert len(json.dumps(evidence, ensure_ascii=True).encode()) <= refusal.MAX_BYTES


def test_spinner_span_uses_original_casefold_coordinates_and_not_later_category():
    screen = "ßİ ⠋ Task private\n" + metadata_capture("ready")
    reason = opencode.input_reason(screen)
    assert reason == "unknown-dialog-or-background"
    evidence = opencode.refusal_evidence(screen, reason)
    assert evidence["predicate"] == "braille-task"
    assert evidence["predicate_span"] == {"start": [0, 3], "end": [0, 9]}


def test_expansion_inside_variable_plugin_pattern_emits_only_covering_span():
    text = "herdr-agent-state.js ßİ secret failed"
    reason = opencode.input_reason(text)
    evidence = opencode.refusal_evidence(text, reason)
    assert reason == "unknown-dialog-or-background"
    assert evidence["predicate_span"] == {"start": [0, 0], "end": [0, len(text)]}
    assert "secret" not in json.dumps(evidence)


def test_maximum_multibyte_projection_with_outside_span_still_fits_json_bound():
    screen = ("密" * 160 + "\n") * 64 + "ßİ permission required"
    reason = opencode.input_reason(screen)
    evidence = opencode.refusal_evidence(screen, reason)
    assert evidence["predicate_span"] == {"start": [64, 3], "end": [64, 22]}
    assert evidence["predicate_outside_capture"] is True
    encoded = json.dumps(evidence, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    assert len(encoded) <= refusal.MAX_BYTES
    assert "permission required" not in encoded.decode()


@pytest.mark.parametrize("row,column", [(63, 154), (63, 155), (64, 0), (0, 161)])
def test_task_trigger_span_at_crop_boundaries(row, column):
    screen = "\n" * row + "x" * column + "⠋ Task\n" + metadata_capture("ready")
    reason = opencode.input_reason(screen)
    assert reason == "unknown-dialog-or-background"
    evidence = opencode.refusal_evidence(screen, reason)
    assert evidence["predicate"] == "braille-task"
    assert evidence["predicate_span"] == {"start": [row, column], "end": [row, column + 6]}
    assert evidence["predicate_outside_capture"] == (row >= 64 or column + 6 > 160)
