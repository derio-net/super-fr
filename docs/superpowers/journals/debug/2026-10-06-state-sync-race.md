# Journal: 2026-10-06-state-sync-race

<!-- fr:journal kind=repro scope=debug id=23b1534454a6 created=2026-10-06T16:35:42+00:00 -->
### 23b1534454a6 · repro · state_sync checks for a symlink, then copy2 opens the paths again

packages/fr/src/fr/triage/state_sync.py _sync: the source is classified (durable_entries, lstat) and the destination checked (_symlinked_dest, lstat per component), then shutil.copy2(source, target) re-resolves both paths by name. A swap in between (target -> symlink, a destination directory -> symlink, or the source -> symlink) is written through or copied as a link: copy2's follow_symlinks=False only governs the SOURCE, and copies a source symlink AS a symlink into the destination. Repro: monkeypatch the check to swap the path right after it returns.

<!-- fr:journal kind=hypothesis scope=debug id=975eabbb195b created=2026-10-06T16:35:47+00:00 -->
### 975eabbb195b · hypothesis · single cause: path-based re-resolution between check and open (gh#1003)

Every variant is the same defect: the check and the write resolve the name independently. Fix: open every component with O_NOFOLLOW from a held directory descriptor (dir_fd walk, O_DIRECTORY|O_NOFOLLOW), open the file itself O_NOFOLLOW, fstat it regular, and copy fd-to-fd, restoring mode and times on the descriptor.

<!-- fr:journal kind=root-cause scope=debug id=895a7c5680d0 created=2026-10-06T16:48:26+00:00 -->
### 895a7c5680d0 · root-cause · check and copy resolved the paths independently

state_sync._sync lstat-checked source and destination by name, then shutil.copy2 opened both by name again. copy2(follow_symlinks=False) governs only the source and, for a source that became a symlink, recreates the link in the destination, so a swap after the check either wrote through a destination symlink or planted a symlink in the export.
