---
docType: review
layer: project
reviewType: code
slice: calibration-to-threshold-feedback
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/322-slice.calibration-to-threshold-feedback.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260726
dateUpdated: 20260726
findings:
  - id: F001
    severity: concern
    category: dry
    summary: "Duplicate, divergent config-validation for the same metrology keys"
    location: src/squadron/cli/commands/metrology.py:423-452
    resolution: fixed
  - id: F002
    severity: concern
    category: error-handling
    summary: "Silent exception swallow breaks the project's own tolerant-skip convention"
    location: src/squadron/cli/commands/metrology.py:661-677
    resolution: fixed
  - id: F003
    severity: concern
    category: efficiency
    summary: "`graduate` command scans the graduation store three times for one write"
    location: src/squadron/cli/commands/metrology.py:570-576
    resolution: fixed
  - id: F004
    severity: note
    category: documentation
    summary: "`enrich_samples`/`_enrich_one` docstring overstates its I/O guarantee"
    location: src/squadron/metrology/report.py:180-186
    resolution: fixed
  - id: F005
    severity: pass
    category: error-handling
    summary: "Exception handling discipline"
    location: src/squadron/metrology
resolutionDate: 20260726
---

# Review: code — slice 322

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Resolution (20260726)

All three CONCERNS (F001, F002, F003) and the NOTE (F004) have been addressed:

- **F001** — added `get_typed_config()` to `src/squadron/config/manager.py` as the single typed int/float config reader; `report.py`'s `_min_evidence_n` and the CLI's `_read_int_config`/`_read_float_config` now delegate to it, each wrapping its `ValueError` in their own domain exception.
- **F002** — `_derive_judge_config_and_level` now logs a WARNING on its except path, matching the sibling tolerant-skip convention.
- **F003** — `write_graduation` now returns `(record_id, was_update)` from its existing scan; the CLI's `graduate` command dropped the redundant `find_graduation` call.
- **F004** — corrected the `enrich_samples`/module docstrings to accurately describe the two-read-per-sample behavior.

Verdict left as **CONCERNS** — this section records disposition only, not a re-review.

## Findings

### [CONCERN] Duplicate, divergent config-validation for the same metrology keys

`report.py` has its own private readers (`_min_evidence_n` at report.py:189-196, `_default_trend_bucket` at report.py:326-333) that validate `metrology.min_evidence_n`/`metrology.trend_bucket` and raise `MetrologyTargetError` on a bad type. `cli/commands/metrology.py` has a second, independent implementation (`_read_int_config`/`_read_float_config`, lines 423-439) that validates the *same* keys (`metrology.min_evidence_n`, `metrology.graduate_match_rate`, `metrology.tighten_match_rate`, `metrology.residual_sample_rate`) but raises `typer.BadParameter` instead. Concretely, `recommend()` reads and validates `metrology.min_evidence_n` twice in one invocation: once inside `agreement_report()` (via `_min_evidence_n`, raising `MetrologyTargetError`, caught by the command's own try/except) and again via `_build_recommendation_report()` → `_read_int_config` (raising `typer.BadParameter`, not one of the caught types in that same try block). Today the second read never fails in practice because the first read already proved the value is valid, but this is two independent sources of truth for "how do I validate a metrology numeric config key," with two different error types and CLI exit codes/formatting for what is conceptually the same failure mode. CLAUDE.md is explicit: comparison/validation logic should be defined once. Recommend consolidating into one typed config-reader helper in `report.py` (or a shared `config` helper) that both the core and the CLI call.

### [CONCERN] Silent exception swallow breaks the project's own tolerant-skip convention

`_derive_judge_config_and_level` catches `MetrologyTargetError` and returns `(None, None)` with no logging at all. Every sibling tolerant-skip in this same slice logs a WARNING before skipping: `discover_judge_results` (discovery.py:49-51), `_review_reviewtype` (graduation.py:93-95), `_candidates_by_type`'s fallback (capture.py, via `_read_review_type`), and `select_residual_offers`'s per-file skip (graduation.py:136). This one silently drops a file that fails to parse during the `offers` command's lapse-vs-exhausted classification, which the docstring says is used to distinguish "graduation has lapsed" from "no offers due" — a case where silently mis-classifying a parse failure as "still current" or vice versa is exactly the kind of failure mode the project's Failure-Mode Enumeration rule requires to be observable. Add a `_logger.warning(...)` on the except path to match the established pattern.

### [CONCERN] `graduate` command scans the graduation store three times for one write

`graduate()` calls `find_graduation(store, ...)` (which internally calls `store.list_graduations()` — a full glob + per-file read/validate of the store dir) purely to learn whether a matching record already exists, then immediately calls `write_graduation_record(...)` (`graduation.write_graduation`, graduation.py:50-67), which *itself* calls `store.list_graduations()` again and re-runs the identical `_identity_matches` scan to decide whether to update in place. That's two full store scans doing the same identity match, plus whatever `store.list_graduations()` costs at call sites elsewhere in the same command. Since `write_graduation` already knows internally whether it updated vs. created, a small refactor (have it return `(record_id, was_update)`) would let the CLI drop the redundant `find_graduation` call and its extra scan.

### [NOTE] `enrich_samples`/`_enrich_one` docstring overstates its I/O guarantee

The docstring for `enrich_samples` states "One frontmatter read per sample yields both the judge verdict (agreement) and the resolved `source_document` (dispersion key) — no extra I/O." In practice `_enrich_one` reads the review frontmatter directly (report.py:87) *and* calls `derive_result_ref` (report.py:117-121), which internally calls `read_review_frontmatter` again (identity.py:286) to recompute the content hash. So there are two frontmatter reads per sample, not one. This is likely unavoidable (the hash must be recomputed from a fresh read to catch a changed file), but the docstring's "no extra I/O" claim is inaccurate and should be corrected or the redundant read should be avoided by threading the already-parsed frontmatter through.

### [PASS] Exception handling discipline

No bare `except:` or `except Exception: pass` anywhere in the new modules; every catch is scoped to a specific exception type and either logs at WARNING with an explanatory comment (e.g. `store.py:182`, `discovery.py:49`, `identity.py:83-89` for the git-remote timeout) or re-raises a typed `MetrologyError` with an actionable message naming the fix. This matches both the global CLAUDE.md and Python-rules exception-handling requirements well.
