# Journal: 2026-10-06-state-sync-race

<!-- fr:journal kind=repro scope=debug id=23b1534454a6 created=2026-10-06T16:35:42+00:00 -->
### 23b1534454a6 · repro · state_sync checks for a symlink, then copy2 opens the paths again

packages/fr/src/fr/triage/state_sync.py _sync: the source is classified (durable_entries, lstat) and the destination checked (_symlinked_dest, lstat per component), then shutil.copy2(source, target) re-resolves both paths by name. A swap in between (target -> symlink, a destination directory -> symlink, or the source -> symlink) is written through or copied as a link: copy2's follow_symlinks=False only governs the SOURCE, and copies a source symlink AS a symlink into the destination. Repro: monkeypatch the check to swap the path right after it returns.
