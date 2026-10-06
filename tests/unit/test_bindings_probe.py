"""Probe, classifier and cache for `fr.bindings` (spec 2026-10-06-model-binding-churn §A).

The classifier is pinned against CAPTURES of the real OpenCode CLI
(tests/fixtures/bindings/README.md); the one exception, the in-catalogue
"not supported" text, is transcribed from super-fr#591 and labelled so there."""

from __future__ import annotations

import subprocess
from pathlib import Path

import fr.bindings
from fr.bindings.probe import (
    OpenCodeProber,
    ProbeCache,
    ProbeResult,
    classify,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "bindings"


def _read(name: str) -> str:
    return (FIX / name).read_text()


def test_the_bindings_package_imports() -> None:
    assert fr.bindings.__doc__


def test_a_text_event_is_live() -> None:
    got = classify(_read("opencode-run-live.stdout"), _read("opencode-run-live.stderr"), 0)
    assert got.verdict == "live"


def test_model_not_found_is_dead_with_the_line_and_the_hint() -> None:
    got = classify(
        _read("opencode-run-not-found.stdout"), _read("opencode-run-not-found.stderr"), 1
    )
    assert got.verdict == "dead"
    assert "ProviderModelNotFoundError" in got.detail
    assert got.hint == "gpt-6.1-sol"


def test_not_supported_transcribed_from_591_is_dead() -> None:
    # Transcribed from super-fr#591 (the retired-but-still-listed shape), not captured here.
    got = classify("", _read("opencode-run-not-supported.stderr"), 1)
    assert got.verdict == "dead"
    assert "not supported" in got.detail.lower()
    assert got.hint is None
    assert classify("", "ERROR: THE REQUESTED MODEL IS NOT SUPPORTED.", 1).verdict == "dead"


def test_the_catalogue_status_is_never_read() -> None:
    # The catalogue says "status": "active" for this model; the provider says
    # not supported. The verdict is dead, because no code path reads `status`.
    catalogue_line = '{"id": "m", "status": "active"}'
    got = classify(catalogue_line, _read("opencode-run-not-supported.stderr"), 1)
    assert got.verdict == "dead"
    src = (Path(fr.bindings.__file__).parent).glob("*.py")
    reads = ('get("status"', "get('status'", '["status"]', "['status']", ".status")
    assert not any(r in p.read_text() for p in src for r in reads)


def test_any_other_failure_is_unknown() -> None:
    assert classify("", "", 0).verdict == "unknown"
    assert classify("", "boom", 1).verdict == "unknown"
    err = '{"type":"error","error":{"name":"UnknownError"}}'
    assert classify(err, "", 1).verdict == "unknown"
    assert classify("not json at all", "401 unauthorized", 1).verdict == "unknown"


class _Seam:
    """A fake `run_opencode`: records argv/cwd/timeout and replays a result."""

    def __init__(self, stdout: str = "", stderr: str = "", rc: int = 0, raises=None) -> None:
        self.calls: list[tuple[list[str], Path, float]] = []
        self._r = (stdout, stderr, rc)
        self._raises = raises

    def __call__(self, argv: list[str], *, cwd: Path, timeout: float):
        self.calls.append((argv, cwd, timeout))
        assert cwd.is_dir()
        if self._raises:
            raise self._raises
        return subprocess.CompletedProcess(argv, self._r[2], self._r[0], self._r[1])


def test_the_prober_runs_the_spec_argv_in_a_fresh_cwd() -> None:
    seam = _Seam(stdout=_read("opencode-run-live.stdout"))
    got = OpenCodeProber(run_opencode=seam).probe("github-copilot/claude-haiku-4.5")
    assert got.verdict == "live"
    (argv, cwd, timeout), = seam.calls
    assert argv == [
        "opencode", "run", "--pure", "--print-logs", "--log-level", "ERROR",
        "--format", "json", "-m", "github-copilot/claude-haiku-4.5", "Reply with exactly: OK",
    ]  # fmt: skip
    assert timeout == 60
    assert not (Path.cwd() == cwd) and not cwd.exists()  # a throwaway dir, gone after


def test_a_missing_cli_or_a_timeout_is_unknown_never_a_crash() -> None:
    for exc in (FileNotFoundError("opencode"), subprocess.TimeoutExpired("opencode", 60)):
        got = OpenCodeProber(run_opencode=_Seam(raises=exc)).probe("p/m")
        assert got.verdict == "unknown"
        assert got.detail


def test_the_prober_reads_the_catalogue_through_the_same_seam() -> None:
    seam = _Seam(stdout=_read("opencode-models-verbose.txt"))
    entries = OpenCodeProber(run_opencode=seam).catalogue("github-copilot")
    assert len(entries) == 4
    assert seam.calls[0][0] == ["opencode", "models", "github-copilot", "--verbose"]
    assert OpenCodeProber(run_opencode=_Seam(raises=FileNotFoundError())).catalogue("p") == []


def test_prober_for_covers_opencode_only() -> None:
    assert isinstance(fr.bindings.prober_for("opencode"), OpenCodeProber)
    assert fr.bindings.prober_for("claude-code") is None
    assert fr.bindings.prober_for("hermes") is None


class _Counting:
    def __init__(self) -> None:
        self.n = 0

    def probe(self, model: str) -> ProbeResult:
        self.n += 1
        return ProbeResult("live", "", None, 0.0)

    def catalogue(self, provider: str):
        return []


def test_the_probe_cache_honours_ttl_and_fresh(tmp_path: Path) -> None:
    now = [1000.0]
    cache = ProbeCache(tmp_path / "probes.json", clock=lambda: now[0])
    prober = _Counting()
    assert cache.probe(prober, "opencode", "p/m").verdict == "live"
    cache.probe(prober, "opencode", "p/m")
    assert prober.n == 1  # cached
    cache.probe(prober, "opencode", "p/m", fresh=True)
    assert prober.n == 2  # fresh bypasses
    now[0] += 6 * 3600 - 1
    cache.probe(prober, "opencode", "p/m")
    assert prober.n == 2  # still inside 6 h
    now[0] += 2
    cache.probe(prober, "opencode", "p/m")
    assert prober.n == 3  # expired
    # Keyed per (harness, model).
    cache.probe(prober, "opencode", "p/other")
    assert prober.n == 4
    # A second cache object over the same file sees the stored verdict.
    again = ProbeCache(tmp_path / "probes.json", clock=lambda: now[0])
    again.probe(prober, "opencode", "p/m")
    assert prober.n == 4


def test_an_unknown_verdict_is_not_cached(tmp_path: Path) -> None:
    class Flaky(_Counting):
        def probe(self, model: str) -> ProbeResult:
            self.n += 1
            return ProbeResult("unknown", "timeout", None, 0.0)

    cache = ProbeCache(tmp_path / "probes.json", clock=lambda: 1.0)
    p = Flaky()
    cache.probe(p, "opencode", "p/m")
    cache.probe(p, "opencode", "p/m")
    assert p.n == 2
