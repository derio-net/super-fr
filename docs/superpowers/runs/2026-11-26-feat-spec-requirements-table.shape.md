```text
packages/fr/src/fr/
  requirements.py                   # the one Requirements reader: table, R<n>[a-z] list, pre-5.0 table
                                    #   list_layout() / table_form_problems() / requirement_order()
  artifacts/
    spec_requirements_table.py    + # spec 1 -> 2 SchemaMigration: list -> table, round-trip, refuse
    registry.py                     # spec kind current_version 1 -> 2
    structure.py                    # validate_spec: stamp >= 2 refuses list lines, bad table rows
    __init__.py                     # imports the migration so it registers
  plan_review/sizing.py             # lettered ids; a malformed section warns, never crashes
  proportionality.py                # orders asks by requirement_order; error names the cause
tests/scenarios/spec-requirements-table.sh  + # candidate walk: migrate, refuse, stamp-only
```

```text
_rewrite(spec):
  text = read(spec)
  if section already a 2-column table / pre-5.0 table / no requirement line: return   # stamp only
  layout = list_layout(text)              # raises on a bad id; a heading or a code fence in the list refuses
  new = build(text)                       # one row per requirement: continuations joined, paragraphs and
                                          #   bullets folded with <br>, `|` -> `\|`, endings kept
  refuse unless parse(new) == parse(text) # file:line, cause, hand fix; file left byte-identical
  write_text_atomic(spec, new)            # once; the runner then writes fr_schema: 2
```
