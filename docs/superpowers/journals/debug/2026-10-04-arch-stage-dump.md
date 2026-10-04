# Journal: 2026-10-04-arch-stage-dump

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-04T04:39:59+00:00 -->
### repro-1 · repro · Snapshot tabs dump every batch stage

Architecture page 'Snapshot timeline': every snapshot tab renders one <span><code>batch</code> stage</span> per batch in Snapshot.batches inside div.stages, no heading or grouping (82 pairs on this repo, repeated per tab). Repro: _snapshot_panel(snap, None) with many batches.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-10-04T04:40:00+00:00 -->
### rc-1 · root-cause · _snapshot_panel prints the raw batches mapping

packages/fr/src/fr/triage/architecture.py _snapshot_panel (~L372-378) joins a span per (batch, stage) sorted by batch name: it prints the raw Snapshot.batches mapping instead of aggregating it. Renderer-only; Snapshot data and diff_snapshots are correct (Batch stage changes list is fine).
