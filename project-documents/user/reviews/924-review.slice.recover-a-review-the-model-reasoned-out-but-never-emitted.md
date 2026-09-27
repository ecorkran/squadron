---
docType: review
layer: project
reviewType: slice
slice: recover-a-review-the-model-reasoned-out-but-never-emitted
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 5699b1d3b460bdd162ca9ba16387501127963ce7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
runId: run-20260927-slices-plan-1e83a3fb
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Slice fits the maintenance-and-refactoring container and its stated scope"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md#Overview"
  - id: F002
    severity: pass
    category: integration
    summary: "D6's claimed parity gap is verified against the code"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md#D6"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes for the new decision and I/O paths are enumerated, not TBD"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md#D2"
  - id: F004
    severity: pass
    category: alignment
    summary: "D1 is consistent with the 919/927/918 contracts it builds on"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md#D1"
  - id: F005
    severity: pass
    category: scope
    summary: "Scope is bounded; excluded items are explicit and justified"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md#Technical-Scope"
  - id: F006
    severity: note
    category: under-specification
    summary: "B5 budget values are specified against a live external listing at implementation time"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md#Budget-values"
  - id: F007
    severity: note
    category: alignment
    summary: "No NFR restatement required"
    location: "project-documents/user/architecture/900-arch.maintenance-and-refactoring.md"
---

# Review: slice — slice 924

**Verdict:** PASS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Slice fits the maintenance-and-refactoring container and its stated scope

The 900-arch document defines this initiative as tech debt, bug fixes, and operational improvements spanning subsystems, with no new features. This slice is a bug-fix completion (#92) plus a configuration capability (output budget) that the parent slice plan entry explicitly carves out as Part B (`900-slices.maintenance-and-refactoring.md:419`). The slice design supersedes the plan entry where they differ, and the plan entry has already been updated to record that supersession (`900-slices.maintenance-and-refactoring.md:421`), so plan/design are consistent, not contradictory.

### [PASS] D6's claimed parity gap is verified against the code

`pipeline/actions/review.py:176,180` indeed calls `context.resolver.resolve()` and passes no `model_allows_tools`; `run_review_with_profile` (review_client.py:137) then falls back to `_alias_allows_tools(resolved_model)`, which looks up a resolved model id in the alias table (`models/aliases.py:193`) and returns `True` on miss — exactly the always-True gate bypass the design describes. `resolve_full()` exists (`pipeline/resolver.py:151`) and `ResolvedModel` already carries `allows_tools`, so adding `max_output_tokens` there follows the established slice-266 pattern without breaking the `resolve()` tuple contract. Dependency direction (alias metadata read at the alias boundary, carried downward) is correct.

### [PASS] Failure modes for the new decision and I/O paths are enumerated, not TBD

The design covers: budget-exhausted stop reasons (`length`/`max_tokens`) → skip with WARNING and digest line; `None` stop reason (Codex) → recovery proceeds as today; a provider that stops stamping `stop_reason` → `budget_exhausted` returns False and behavior is unchanged (Integration Points); a backend rejecting `max_completion_tokens` → explicit `ProviderAPIError`, not silent truncation (D5); SDK/Codex agents that cannot apply a budget → WARNING, not silent ignore (B2). The "absent budget" case is disclosed in the digest (`Output budget: backend default`) rather than silently defaulted, honoring the no-silent-fallbacks rule.

### [PASS] D1 is consistent with the 919/927/918 contracts it builds on

919 D7 does define `verdictSource` as answering "did the model say this?" with the closed three-value vocabulary (confirmed in 919-slice:358–376 and `review/models.py` VerdictSource), and 927 established the optional-key-only-when-condition-holds convention (`diffTruncated`, `requestedModel`) that `recoveryTurn` follows. The design correctly distinguishes gate-facing evidence (frontmatter) from diagnostics (Run Digest only, per 918 D10), keeping `output_budget_exhausted` and the budget line out of frontmatter.

### [PASS] Scope is bounded; excluded items are explicit and justified

The Excluded list rejects prompt changes, prose verdict inference (correctly citing the #91 false-match surface), a global budget default, Claude/Codex budgets, and untouched call sites (`metrology/audit.py`, `review/addressed/judge.py`). The dispatch/summary follow-up is deferred with a filed-issue note rather than absorbed — no scope creep. The D3 reversal of the plan entry's tool-removal lean is evidence-based and pinned by a test.

### [NOTE] B5 budget values are specified against a live external listing at implementation time

Taking `top_provider.max_completion_tokens` from OpenRouter's models listing "at implementation time" makes the concrete values indeterminate at design time. The mitigation (record the listing date in the `models.toml` comment, leave null where the listing is null, never invent a value) is adequate, and the design correctly treats a too-small budget as an observable artifact condition (D2) rather than a hidden failure — but a reviewer of the implementation should verify the recorded date and values exist.

### [NOTE] No NFR restatement required

The parent architecture document states no latency/throughput/reliability NFRs, so no NFR targets needed restating. The one latency-adjacent consideration — a wasted second turn on a spent budget — is addressed head-on by A2.

### Run Digest

- Response length: 5126 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 3845
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
