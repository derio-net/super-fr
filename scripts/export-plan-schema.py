#!/usr/bin/env python3
"""Export JSON Schema for the v2 plan-as-folder format (parity harness).

The cncd schema-parity harness (cnc-fr spec 2026-07-02, §3.3): the
umbrella repo vendors this output, and cncd's Go parser is golden-tested
against it plus the fixtures corpus under `tests/fixtures/plan_folders/`.
The schemas are `model_json_schema()` of the live pydantic models in
`fr.types` — generated, never hand-maintained, so they cannot drift from
what `fr` actually enforces.

Folder-level invariants (mandatory `_prose.md`, contiguous 1..N phase
numbering) are not expressible in JSON Schema; they are pinned by
`fr.parser.parse_strict` and the corpus manifest instead.

Usage:
    scripts/export-plan-schema.py            # combined JSON doc on stdout
    scripts/export-plan-schema.py <outdir>   # write plan_meta.schema.json
                                             #   + phase_doc.schema.json

Run via `uv run scripts/export-plan-schema.py` (needs the `fr` package
importable).
"""

from __future__ import annotations

import json
import pathlib
import sys


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        print(__doc__, file=sys.stderr)
        return 2

    from fr.types import PhaseDoc, PlanMeta

    plan_meta = PlanMeta.model_json_schema()
    phase_doc = PhaseDoc.model_json_schema()

    if not argv:
        combined = {"schema_version": 2, "plan_meta": plan_meta, "phase_doc": phase_doc}
        print(json.dumps(combined, indent=2))
        return 0

    outdir = pathlib.Path(argv[0])
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "plan_meta.schema.json").write_text(json.dumps(plan_meta, indent=2) + "\n")
    (outdir / "phase_doc.schema.json").write_text(json.dumps(phase_doc, indent=2) + "\n")
    print(f"wrote {outdir / 'plan_meta.schema.json'}")
    print(f"wrote {outdir / 'phase_doc.schema.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
