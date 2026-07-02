"""`scripts/export-plan-schema.py` — the JSON Schema half of the parity
harness (cnc-fr spec 2026-07-02, §3.3).

The umbrella repo runs this script to vendor the v2 plan-as-folder
schema; cncd's Go parser is golden-tested against the output. Two
modes:

  - no args → one combined JSON document on stdout
    (`{"plan_meta": ..., "phase_doc": ...}`),
  - `<outdir>` → `plan_meta.schema.json` + `phase_doc.schema.json`
    written into the directory (created if missing).

The script must emit exactly `model_json_schema()` of the live pydantic
models — no hand-maintained copy that could drift.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "export-plan-schema.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_stdout_mode_emits_combined_schema_doc():
    result = _run()
    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    assert set(doc) == {"schema_version", "plan_meta", "phase_doc"}
    assert doc["schema_version"] == 2


def test_stdout_schemas_match_live_models():
    """No drift: the script's output IS model_json_schema() of fr.types."""
    from fr.types import PhaseDoc, PlanMeta

    result = _run()
    doc = json.loads(result.stdout)
    assert doc["plan_meta"] == PlanMeta.model_json_schema()
    assert doc["phase_doc"] == PhaseDoc.model_json_schema()


def test_schema_carries_the_contract_landmarks():
    """Spot-check the fields the reconciliation pinned: the slug field is
    `plan` (not `slug`), there is no `source_commit`, extra fields are
    forbidden, and the P.T.S step-id pattern is exported."""
    result = _run()
    doc = json.loads(result.stdout)
    meta = doc["plan_meta"]
    assert "plan" in meta["properties"]
    assert "slug" not in meta["properties"]
    assert "source_commit" not in meta["properties"]
    assert meta["additionalProperties"] is False
    step = doc["phase_doc"]["$defs"]["Step"]
    assert step["properties"]["id"]["pattern"] == r"^P\d+\.T\d+\.S\d+$"


def test_outdir_mode_writes_two_files(tmp_path):
    outdir = tmp_path / "vendored"
    result = _run(str(outdir))
    assert result.returncode == 0, result.stderr
    from fr.types import PhaseDoc, PlanMeta

    meta = json.loads((outdir / "plan_meta.schema.json").read_text())
    phase = json.loads((outdir / "phase_doc.schema.json").read_text())
    assert meta == PlanMeta.model_json_schema()
    assert phase == PhaseDoc.model_json_schema()


def test_too_many_args_is_a_usage_error(tmp_path):
    result = _run(str(tmp_path), "extra")
    assert result.returncode == 2
