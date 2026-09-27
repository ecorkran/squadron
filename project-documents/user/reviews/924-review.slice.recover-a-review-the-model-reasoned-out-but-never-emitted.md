---
docType: review
layer: project
reviewType: slice
slice: recover-a-review-the-model-reasoned-out-but-never-emitted
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 16194f3e130855cdf673d88c4d65af2ef3f1bb44
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Recovery/verdict provenance is architecturally sound and correctly layered"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md:145-157"
  - id: F002
    severity: pass
    category: integration-points
    summary: "Dependency contracts (918, 919, 927) are consumed exactly as specified"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md:69-84"
  - id: F003
    severity: pass
    category: scope-control
    summary: "Scope is well-bounded with explicit exclusions; no scope creep"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md:53-67"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with explicit handling, not TBD"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md:107-137"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Alias capability parity (D6) fixes a real latent gate bug with correct dependency direction"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md:194-200"
  - id: F006
    severity: pass
    category: integration-points
    summary: "Budget plumbing is end-to-end consistent and centralized"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md:222-247"
  - id: F007
    severity: note
    category: documentation
    summary: "Doc metadata: `interfaces: []` and `status: not_started` understate the shipped state"
    location: "project-documents/user/slices/924-slice.recover-a-review-the-model-reasoned-out-but-never-emitted.md:7-10"
---

# Review: slice — slice 924

**Verdict:** PASS
**Model:** moonshotai/kimi-k3

## Findings

### [PASS] Recovery/verdict provenance is architecturally sound and correctly layered

The D1 decision to flag a recovered verdict with its own `recoveryTurn: true` frontmatter key — rather than adding a `VerdictSource.RECOVERED` enum value — is the correct layering call and is faithfully implemented. Slice 919's D7 establishes `verdictSource` as answering "did the model say this?" (closed vocabulary `stated | derived`); a recovered verdict is itself stated or derived, so conflating the two axes into one enum would discard information gates filter on. The conditional-emission rule (key present only when the recovery turn ran) follows the 927 convention verified in `persistence.py:405` (`if recovery_turn: lines.append("recoveryTurn: true")`), and `verdictSource` is left untouched as the parser sets it. Dependency directions are correct: 924 consumes 919's contract without modifying it.

### [PASS] Dependency contracts (918, 919, 927) are consumed exactly as specified

The slice consumes 918's `TurnCapture.stop_reason` (verified present in `turn_capture.py`), 919's `VerdictSource` (unchanged), and 927's conditional-frontmatter convention. The declared `dependencies: [918, 919, 927]` match the actual coupling. `budget_exhausted` reads only `capture.stop_reason`, and the doc explicitly notes the fail-safe direction: if a provider stops stamping stop reasons, `budget_exhausted` returns False and recovery proceeds as today — only an actual budget signal suppresses the second turn. This is the correct failure bias (recover on ambiguity, never silently skip).

### [PASS] Scope is well-bounded with explicit exclusions; no scope creep

The Excluded list is disciplined and each exclusion is justified: no prose-verdict inference (correctly avoids reopening the #91 incidental-match surface), no global/provider default budget (D4 rejects a one-size number that some backends would 400-reject), no SDK/Codex budget implementation (warning instead), and no second recovery attempt (one bounded turn remains the contract). Deferring the dispatch/summary budget threading to a follow-up (#151) rather than silently expanding keeps the risk surface on reviews, as the maintenance-initiative guideline ("small and focused, independently deliverable") requires.

### [PASS] Failure modes are enumerated with explicit handling, not TBD

The recovery-decision flow enumerates each branch's failure behavior: empty-turn-with-budget-exhausted re-raises the `EmptyFinalTurnError` so the failure artifact reads as today; an empty recovery turn propagates (still one turn); a parsed mid-task turn with exhausted budget sets `output_budget_exhausted` and skips. Verified in `review_client.py:_collect_review` — the `EmptyFinalTurnError` catch folds telemetry via `fold_empty_turn`, the budget skip both logs and re-raises, and the recovery turn is exactly one `collect_turn(FINISH_REVIEW_PROMPT)` call. D5 also names the misconfiguration failure mode: a budget set on an alias whose backend rejects `max_completion_tokens` surfaces as an explicit `ProviderAPIError`, not silent truncation.

### [PASS] Alias capability parity (D6) fixes a real latent gate bug with correct dependency direction

The switch from `resolve()` to `resolve_full()` in the pipeline review action closes a verified parity gap: `resolve()` returned only `(model_id, profile)`, so `model_allows_tools` fell back to an id-keyed lookup against an alias-keyed table that always missed, meaning `tool_use = false` was never enforced in pipeline reviews. `ResolvedModel`'s own docstring confirms an id cannot be traced back to its alias. Verified in `pipeline/actions/review.py` (both the primary and the `ModelResolutionError` fallback paths use `resolve_full`, and pass `resolved.allows_tools` / `resolved.max_output_tokens`) and `resolver.py` (`_resolved` reads the capability while the alias name is known). The capability is read at the last point it can be — correct direction, no hidden dependency.

### [PASS] Budget plumbing is end-to-end consistent and centralized

The data flow alias → resolved model → `AgentConfig` → request → result is verified at every hop: `model_max_output_tokens` is the single reader (`aliases.py`), loader validation rejects non-int/non-positive/bool (`_extract_metadata`), `ResolvedModel.max_output_tokens` (`resolver.py`), `AgentConfig.max_output_tokens` and the request sending `max_completion_tokens` or `omit` (`agent.py:_stream_turn`), and `ReviewResult.max_output_tokens`/`output_budget_exhausted` in `to_dict()` (`models.py:308-309`). `OUTPUT_BUDGET_STOP_REASONS` is the single definition of the stop-reason strings (`turn_capture.py`), satisfying the project rule against scattered comparison values. Built-in `models.toml` values are set only on OpenRouter-profile aliases, consistent with D5's "no backend gets the parameter unless checked."

### [NOTE] Doc metadata: `interfaces: []` and `status: not_started` understate the shipped state

The frontmatter `interfaces: []` is empty even though the slice provides a concrete cross-tool contract (`recoveryTurn` frontmatter key for Context Forge's gate and Amoeba, per D1 and "Provides to Other Slices"), and `status: not_started` does not reflect that Part A's recovery turn already shipped in `7dbd1e18` and Parts A/B/C are all present in the current source. Neither blocks the design's correctness — the body is explicit and accurate about what shipped and what remains — but the metadata is worth correcting for accurate indexing and downstream tooling that reads frontmatter.

### Run Digest

- Response length: 6596 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 943718 tokens
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
