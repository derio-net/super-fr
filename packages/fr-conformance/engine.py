"""Conformance engine: launches real harness binary, snapshots repo before/after."""

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConformanceEngine:
    """Runs conformance probes against a real harness binary."""

    def __init__(self, harness_binary: str, cwd: Path):
        self.harness_binary = harness_binary
        self.cwd = cwd
        self.temp_dir: Optional[Path] = None

    async def setup_fixture_repo(self, fixture_name: str) -> Path:
        """Create a temporary fixture repo for testing."""
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"fr-conformance-{fixture_name}-"))
        fixture_repo = self.temp_dir / "repo"
        fixture_repo.mkdir()

        # Initialize git repo
        proc = await asyncio.create_subprocess_exec(
            "git", "init", cwd=fixture_repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.email", "test@example.com", cwd=fixture_repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        proc = await asyncio.create_subprocess_exec(
            "git", "config", "user.name", "Test User", cwd=fixture_repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        # Create basic fr-enabled structure
        (fixture_repo / "docs").mkdir()
        (fixture_repo / "docs" / "superpowers").mkdir()
        (fixture_repo / "docs" / "superpowers" / "plans").mkdir()

        # Write a minimal plan to make it fr-enabled
        (fixture_repo / "docs" / "superpowers" / "plans" / "test-plan").mkdir()
        (fixture_repo / "docs" / "superpowers" / "plans" / "test-plan" / "_meta.yaml").write_text("""schema_version: 2
plan: test-plan
spec: docs/superpowers/specs/test-spec.md
target_repo: test/repo
fr_version: '>=4.2.0,<5.0.0'
created: '2026-09-22'
""")

        # Initial commit
        proc = await asyncio.create_subprocess_exec(
            "git", "add", "-A", cwd=fixture_repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        proc = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", "Initial commit", cwd=fixture_repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        return fixture_repo

    async def run_harness(self, args: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Run the harness binary and return result."""
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        # Set up baseURL for mock server if needed
        if "OPENCODE_BASE_URL" not in full_env:
            full_env["OPENCODE_BASE_URL"] = "http://localhost:12345/v1"

        proc = await asyncio.create_subprocess_exec(
            self.harness_binary, *args,
            cwd=cwd,
            env=full_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        return {
            "returncode": proc.returncode,
            "stdout": stdout.decode() if stdout else "",
            "stderr": stderr.decode() if stderr else "",
        }

    async def run_probe(self, probe_name: str, scenario: "Scenario") -> Dict[str, Any]:
        """Run a single probe with the given scenario."""
        fixture_repo = await self.setup_fixture_repo(probe_name)

        # Run the scenario against the harness
        results = await scenario.execute(self, fixture_repo)

        # Cleanup
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

        return results

    def cleanup(self):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
