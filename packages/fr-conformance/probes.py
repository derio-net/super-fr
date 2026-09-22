"""Probe definitions: fixture repo + scenario + assertion over side effects."""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .engine import ConformanceEngine
from .mock.server import MockServer
from .mock.scenario import (
    create_edit_gate_refuses_scenario,
    create_edit_gate_allows_scenario,
)


class ProbeResult:
    def __init__(self, name: str, passed: bool, message: str, details: Dict[str, Any] = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details or {}


async def run_probe(probe_name: str, harness_binary: str, cwd: Path) -> ProbeResult:
    """Run a single conformance probe."""
    # Create mock scenario
    if probe_name == "test_edit_gate_refuses":
        probe_scenario = create_edit_gate_refuses_scenario()
    elif probe_name == "test_edit_gate_allows":
        probe_scenario = create_edit_gate_allows_scenario()
    else:
        return ProbeResult(probe_name, False, f"Unknown probe: {probe_name}")

    # Start mock server
    mock_server = MockServer(probe_scenario.scenario)
    await mock_server.start()

    try:
        # Create engine
        engine = ConformanceEngine(harness_binary, cwd)

        # Run probe
        result = await engine.run_probe(probe_name, probe_scenario)

        # Run assertions
        passed, message = probe_scenario.assertions(engine, engine.temp_dir / "repo", mock_server.get_requests())

        return ProbeResult(probe_name, passed, message, result)
    finally:
        await mock_server.stop()


async def run_all_probes(harness_binary: str, cwd: Path) -> List[ProbeResult]:
    """Run all conformance probes."""
    probes = [
        "test_edit_gate_refuses",
        "test_edit_gate_allows",
        "test_patch_fails_closed",
        "test_bash_ungated",
        "test_idle_adapter_continues",
        "test_idle_adapter_respects_held_gate",
    ]

    results = []
    for probe in probes:
        result = await run_probe(probe, harness_binary, cwd)
        results.append(result)

    return results
