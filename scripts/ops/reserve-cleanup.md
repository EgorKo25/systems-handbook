# Planning maintenance for old release reserves

`plan_reserve_cleanup.py` compares two trusted inventory snapshots and prints a JSON report. It reads the snapshots without changing them. The command has no deletion mode and needs no network or privileges.

```bash
python3 -B scripts/ops/plan_reserve_cleanup.py current.json --earlier previous.json
python3 -B -m unittest discover -s tests -p test_plan_reserve_cleanup.py -v
```

With a single snapshot, the report identifies objects that still need an earlier observation. Two snapshots at least 72 hours apart can qualify the same verified reserve. A missing receipt, ambiguous abbreviated name, changed identity, protected revision or guard failure leaves the object outside the candidate list.

## Interpreting the report

- **Exit code `2` with `invalid inventory:` on stderr.** The CLI rejected the
  inventory input, including any invalid `--earlier` snapshot, and produced no
  JSON on stdout. Record the diagnostic and obtain valid, trusted input before
  retrying the report.
- **Exit code `0` with a reason in `blocked`.** The current snapshot tripped a
  report-wide guard, such as `pending cutover` or `Caddy digest changed`.
  Candidate selection stops and `candidates` is empty. Entries in `skipped` may
  repeat the guard reason. Investigate the guard and collect a fresh trusted
  snapshot once it clears. A blocked snapshot cannot serve as the earlier
  observation.
- **Exit code `0` with `blocked: null`.** Each `skipped` entry gives the reason
  that reserve was left out of `candidates`. Leave a `protected` reserve in
  place. For `matching earlier observation required`, look for a matching,
  trusted earlier observation. Start a new observation period if continuity
  cannot be established.

Use the report to review candidates and the evidence behind them. Acting on a
candidate requires separate authorization and the rechecks under locks below.

## Inventory contract

A controller adapter supplies the following data. Keep snapshots and any actual topology outside the public repository.

| Field | Meaning |
| --- | --- |
| `observed_at` | Whole epoch seconds from a trusted clock at the end of inventory collection. Directory ctime is compared at the same one-second resolution. |
| `generation` | A 64-character lowercase hex continuity token. The adapter changes it whenever protected state changes, including changes that return to a previously seen set. A missing or ambiguous history requires a new first observation. A hash of the current list alone is insufficient. |
| `protected` | Full release SHAs for `active`, `rollback`, `blue`, `green`, `initial` and `pinned`. The planner also protects the corresponding abbreviated names. |
| `pending` | A boolean indicating an unfinished switch. |
| `caddy` | Expected and observed live configuration SHA‑256 values, plus a sorted `reserves` list of reserve names referenced by live configuration. Abort inventory if imports or reserve references cannot be resolved. |
| `active_manifest`, `loopback` | Expected manifest SHA‑256 and the full observed `revision` and `manifest` from the active loopback route. |
| `owner_uid`, `receipts` | Expected deploy owner UID and a map from full revision to manifest SHA‑256, populated only from current ownership records that expressly claim the reserve. |
| `trees` | Observations for the known reserve-name format. Each row has `name`, full `revision`, `manifest`, `kind`, `uid`, `device`, `inode`, `ctime_ns`, `contains_mount`, `verified` and `reclaimable_bytes`. Use metadata from the directory itself without following symlinks. The same device and inode under multiple names is ambiguous. Report estimated bytes in 512-byte units from the allocated block count. A trusted verifier sets `verified` only after checking the full revision marker, manifest and all files. |

The adapter must serialize inventory against the existing controller's release lock. Any later operation must hold that lock and the relevant host-side configuration and reserve locks, with a single documented lock order. The planner only consumes evidence. A report does not establish that locks are held or a candidate still matches the inventory. Recheck generation, protected state, ownership receipt, identity and content under those locks immediately before an independently authorized operation.

Collect other temporary or historical objects separately for investigation. The planner accepts only the explicit reserve names and ownership model above. If a filesystem entry lacks verified metadata, the adapter must preserve that uncertainty. A calculated byte count should exclude blocks shared via hardlinks outside the candidate, and recorded free space should come from the filesystem rather than the sum of estimates.

The first maintenance review should compare an inventory and report with independent records and verify the active and rollback routes. Start any future schedule in report mode. Installing a timer, integrating an adapter or enabling removal is separate from this planner.
