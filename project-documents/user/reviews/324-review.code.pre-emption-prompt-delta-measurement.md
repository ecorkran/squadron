---
docType: review
layer: project
reviewType: code
slice: pre-emption-prompt-delta-measurement
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/324-slice.pre-emption-prompt-delta-measurement.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260728
dateUpdated: 20260728
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`NO_FLOOR_MEASURED` added to `__all__` without a visible definition"
    location: src/squadron/metrology/audit_models.py:55
  - id: F002
    severity: note
    category: performance
    summary: "File is read up to three times in the dispatch hot path"
    location: src/squadron/pipeline/actions/dispatch.py:330-355
  - id: F003
    severity: note
    category: code-quality
    summary: "Dead code in `_cell_interpretation` floor guard"
    location: src/squadron/cli/commands/metrology_preemption.py:195
  - id: F004
    severity: note
    category: dry
    summary: "Duplicated exception handling across CLI commands"
    location: src/squadron/cli/commands/metrology_preemption.py:140-144
  - id: F005
    severity: note
    category: structure
    summary: "`preemption.py` slightly exceeds the 300-line guideline"
    location: src/squadron/metrology/preemption.py
---

# Review: code — slice 324

**Verdict:** PASS
**Model:** z-ai/glm-5.2

## Findings

### [CONCERN] `NO_FLOOR_MEASURED` added to `__all__` without a visible definition

The diff adds `"NO_FLOOR_MEASURED"` to `__all__`, but no definition for this constant appears anywhere in the diff. `DELTA_DISCLAIMER` is added to `__all__` and also defined later in the same diff, but `NO_FLOOR_MEASURED` has no corresponding definition shown. If this constant does not already exist elsewhere in the file (not visible in the diff), this would cause an `AttributeError` on `from squadron.metrology.audit_models import *` and would be flagged by pyright strict mode—which the project rules require at zero errors as a merge blocker. If the constant does exist in the pre-diff portion of the file, this is a non-issue; please verify.

### [NOTE] File is read up to three times in the dispatch hot path

`_apply_pre_emption_fragment` calls `read_fragment_header(path)` to check validity, then `read_fragment_body(path)` which internally calls `read_fragment_header(path)` again (which reads the file) and then `_read_text(path)` (which reads it again). The fragment file is thus read and parsed up to three times for a single dispatch. For a small markdown file at dispatch time the practical impact is negligible, but the API could expose a single `read_fragment(path) -> tuple[header, body] | None` to read once. Consider this for a future cleanup.

### [NOTE] Dead code in `_cell_interpretation` floor guard

```python
spread = cell.floor.max - cell.floor.min if cell.floor is not None else 0
```

This line is only reached when `cell.within_floor` is `True`. Since `is_within_floor` returns `None` (not `True`) when `floor is None`, the `else 0` branch is unreachable. The guard is harmless defensive programming, but it could confuse a future reader into thinking `within_floor=True` with `floor=None` is a reachable state.

### [NOTE] Duplicated exception handling across CLI commands

The `MetrologyIdentityError` / `MetrologyStoreError` catch-and-exit blocks are duplicated between `preempt_generate` (lines 140-144) and `audit_delta` (lines 170-174 and 196-199). A small shared helper like `_exit_on_metrology_error(exc)` would reduce repetition, though the contexts are slightly different (the delta command has an additional `AuditPreflightError`/`AuditSkillError` catch), so the duplication is understandable.

### [NOTE] `preemption.py` slightly exceeds the 300-line guideline

At 325 lines, this file exceeds the ~300-line guideline from CLAUDE.md. The `CATEGORY_GUIDANCE` table (lines ~68-112) accounts for much of the length and is difficult to extract meaningfully since it's tightly coupled to the `AuditCategory` enum. This is a minor boundary case rather than a clear violation.

## Disposition (20260728)

Verdict stands at **PASS**. One finding fixed, one false positive, three declined with reasons.

### F001 — false positive, no change

The review flagged this itself as conditional ("If the constant does exist in the pre-diff portion of the file, this is a non-issue; please verify"). It does. `NO_FLOOR_MEASURED` is defined at `audit_models.py:67` and predates this slice — it landed in 323. Only the `__all__` line appeared in the diff because that is the only line 324 touched. Verified: `from squadron.metrology.audit_models import NO_FLOOR_MEASURED` resolves to `'no floor measured'`, and `pyright` reports 0 errors on the file.

### F003 — fixed

Correct: `is_within_floor` returns `None` (not `True`) when `floor is None`, so the `else 0` branch was genuinely unreachable. Replaced the defensive ternary with an `assert cell.floor is not None` plus a comment stating *why* the state is impossible. This preserves the type-narrowing pyright needs while removing the implication that `within_floor=True` with `floor=None` is a state worth defending against.

### F002 — declined (accurate, but the trade is wrong)

The read-count claim is correct: `read_fragment_header` runs, then `read_fragment_body` re-runs it internally plus `_read_text`. The proposed single `read_fragment(path) -> tuple[header, body] | None` would, however, collapse two failure modes this slice deliberately keeps separate — "malformed header" and "empty body" emit *distinguishable* WARNINGs, which is a T8 requirement with an explicit test (`test_empty_body_is_distinguishable_from_malformed_header`). Saving two reads of a ~2 KB file once per dispatch does not justify losing that distinction. The review characterizes the practical impact as "negligible" and files it as future cleanup; recorded as such.

### F004 — declined (duplication is the lesser cost)

Three catch sites, and as the review notes, their contexts differ — `audit delta` additionally catches `AuditPreflightError`/`AuditSkillError`. A shared `_exit_on_metrology_error` helper would save roughly four lines while adding indirection on error paths, where an explicit local catch is easier to audit than a helper that exits on the caller's behalf. The review's own assessment ("the duplication is understandable") is accepted.

### F005 — declined (PM decision)

`preemption.py` is 325 lines against a "~300 lines where practical" guideline. The overage is almost entirely the `CATEGORY_GUIDANCE` table, which the review correctly notes is "difficult to extract meaningfully since it's tightly coupled to the `AuditCategory` enum." Splitting it would add a module and an import to satisfy a number rather than a design need, and would separate the table from its only consumer. Left as-is per PM decision; the review's own framing — "a minor boundary case rather than a clear violation" — is accepted.
