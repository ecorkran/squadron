---
docType: devlog
scope: project-wide
description: Retired — squadron's development log lives at the repository root
dateUpdated: 20260823
status: deprecated
---

# Development Log — Retired

Squadron's development log is **`DEVLOG.md` at the repository root**. Write entries there.

This file was a second log that ran in parallel from 20260405 to 20260819. Its 78 unique
entries — initiatives 240, 300, 320, and slices 362, 911 among them — were merged into the root
log on 20260823, in date order, with nothing dropped. No content was lost and nothing here is
unique any more.

**Why the root file is canonical:** the `devlog` pipeline action resolves its default path as
`Path(context.cwd) / "DEVLOG.md"` ([devlog.py:44](../src/squadron/pipeline/actions/devlog.py#L44)),
so automated entries land at the root regardless of which file a human picks. Two logs meant
consecutive slices of one initiative were recorded in different places — slice 362 here, slice 363
at the root.

This stub is kept rather than deleted so that anything still pointing at this path finds the
redirect instead of a missing file.
