```
packages/fr/src/fr/triage/
  state_sync.py   + RECORD_FILE "exported-files": JSON {schema: 1, files: {path: sha256}}
                    naming every durable regular file the root holds after an export
                  + read_record (O_NOFOLLOW; BadRecord(forceable=) on a link, non-regular
                    file, bad JSON, wrong schema, or a key that is not a durable path)
                  + find_drift over state ∪ repo ∪ record -> Drift(path, changed|deleted|added)
                  + ExportDrift; drift_text / drift_stop_text (shell-quoted remedy, scope args)
                  + _refuse_non_regular (stamp/record checked before any copy)
                  ~ export_state(force=)   bad record / drift refused before _sync
                  ~ import_state(only=)    named paths copied (mtime ignored) or removed
                  + stop_on: records the driver's export-drift:<repo> stop
  merge_stops.py  + export_drift_stop_key(repo) -> "export-drift:<repo>"
  views.py        + export_drift_needs(stops); NEED_LABELS["export-drift"]; needs_you rows
packages/fr/src/fr/commands/
  triage_state_cmd.py  ~ export --force (remedy re-rendered with its own scope options)
                       ~ import --only (repeatable), prints `removed <path>`
  triage_batch_cmd.py  ~ _export: default sha read up front; ExportDrift|BadRecord -> stop
                         + refusal (a failed stop write stays a refusal); clean -> clear_stop

export:
  stamp ok ─▶ stamp/record regular? ─no─▶ refuse (remove by hand)
                  │yes
                  ▼
           record? ─none─▶ copy ─▶ write record (repo-only files included)
                  │bad: refuse unless --force (forceable)
                  ▼
           find_drift ─none─▶ copy ─▶ write record
                  │some
                  ▼
     hand: exit 2, remedy with its scope    driver: stop + Need, push nothing
     (--force: copy, rewrite record)        (next clean export clears the stop)

remedy:  import --only <each drifted path>  ─▶  export  ─▶  no drift
```
