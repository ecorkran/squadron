# Review test fixtures

## `383-premigration-*.md` — slice 383 byte-identity captures

Captured at commit **`1e6548b8`**, against unmodified `review/persistence.py`,
before slice 383's `SaveTarget` migration touched it.

| Fixture | Path it pins |
|---|---|
| `383-premigration-slice.md` | a slice review (`save_review_result` with a real `SliceInfo`) |
| `383-premigration-arch.md` | an arch review (the `SliceInfo` `_arch_slice_info` fabricates) |
| `383-premigration-step.md` | a pipeline step review (no `SliceInfo` at all) |

Consumed by `tests/review/test_persistence_migration.py`.

**These are not regenerated when output changes.** The migration's acceptance
test is that these three files are reproduced byte-for-byte; a diff means the
migration altered an artifact it was required to leave alone (design D2). The
one sanctioned regeneration is slice 383 Task 8.2, when `rulesSource` and
`targetKind` are added together — and that regeneration asserts the diff
contains exactly those two keys and nothing else.

`reviewedSha` is a pinned literal rather than a resolved value. The live save
path stamps `resolve_reviewed_sha(".")`, which changes on every commit and
would make a byte-identity fixture stale immediately; what these pin is the
rendered output *given* a sha.

## Other fixtures

- `clean_pass_artifact.md` — the non-degraded artifact snapshot for slice 918's
  Run Digest work, consumed by `test_persistence.py`. Regenerated only when a
  change to the clean rendering path is intended.
- `267-headingless-*.md`, `918-newline-free-response.txt` — captured model
  responses exercising parser edge cases.
