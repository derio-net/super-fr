"""Offline source-loaded tests: no installation or native observation required."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "packages/fr-herdr/src/fr_herdr/opencode.py"
WRITER_SPEC = importlib.util.spec_from_file_location(
    "refusal_writer", SOURCE.with_name("refusal.py")
)
assert WRITER_SPEC and WRITER_SPEC.loader
writer = importlib.util.module_from_spec(WRITER_SPEC)
WRITER_SPEC.loader.exec_module(writer)
SPEC = importlib.util.spec_from_file_location("refusal_candidate", SOURCE)
assert SPEC and SPEC.loader
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


class RefusalProjectionTests(unittest.TestCase):
    def test_disabled_capture_does_not_project_or_write(self):
        with patch.object(candidate, "refusal_evidence", side_effect=AssertionError("projection")):
            error = candidate.capture_refusal(None, None, "secret", "draft")
        self.assertIsNone(error)

    def test_enabled_capture_is_private_bounded_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw).resolve()
            os.chmod(directory, 0o700)
            writer.publish(directory, {"frame": ["·" * 160] * 64})
            output = directory / writer.FILENAME
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            first = output.read_bytes()
            self.assertLessEqual(len(first), writer.MAX_BYTES)
            with self.assertRaises(FileExistsError):
                writer.publish(directory, {"replacement": True})
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual([p.name for p in directory.iterdir()], [writer.FILENAME])

    def test_writer_rejects_unsafe_path_and_size(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            target = root / "target"
            target.mkdir(mode=0o700)
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises((OSError, ValueError)):
                writer.publish(link, {})
            os.chmod(target, 0o755)
            with self.assertRaises(ValueError):
                writer.publish(target, {})
            with self.assertRaises(ValueError):
                writer.publish(root, {"oversize": "x" * writer.MAX_BYTES})
            self.assertEqual(list(target.iterdir()), [])

    def test_text_refusal_categories_preserve_public_reason(self):
        for text, category in [
            ("permission required", "permission-required"),
            ("allow once", "allow-once"),
            ("allow this action", "allow-action"),
            ("search provider setup", "search-provider-setup"),
            ("web search setup", "web-search-setup"),
            ("plugin error", "plugin-error-or-failed"),
            ("plugin failed", "plugin-error-or-failed"),
            ("failed plugin", "failed-plugin"),
            ("plugin must export", "plugin-export"),
            ("herdr-agent-state.js private failed", "agent-state-plugin"),
        ]:
            with self.subTest(category=category):
                reason = candidate.input_reason(text)
                self.assertEqual(reason, "unknown-dialog-or-background")
                evidence = candidate.refusal_evidence(text, reason)
                self.assertEqual(evidence["predicate"], category)

    def test_projection_never_retains_unknown_text_or_controls(self):
        screen = (
            "private session title /Users/private/key sk-test-secret\x1b]52;c;payload\x07\n"
            "  ┃ draft=supersecret\n"
            "  \x1b[38;2;92;156;245m╹▀▀▀▀\x1b[0m\n"
            "permission required\n" + "secret" * 10000
        )
        evidence = candidate.refusal_evidence(screen, "unknown-dialog-or-background")
        encoded = json.dumps(evidence)
        for secret in ["private", "Users", "sk-test", "supersecret", "payload", "\x1b", "\x07"]:
            self.assertNotIn(secret, encoded)
        self.assertLessEqual(len(evidence["frame"]), 64)
        self.assertTrue(all(len(line) <= 160 for line in evidence["frame"]))
        self.assertIn("  ┃", evidence["frame"][1])
        self.assertTrue(evidence["focused_border"])


if __name__ == "__main__":
    unittest.main()
