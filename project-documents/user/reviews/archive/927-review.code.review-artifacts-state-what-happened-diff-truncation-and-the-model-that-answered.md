---
docType: review
layer: project
reviewType: code
slice: review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: ff39680bce8a9e05fe197acf72a52e38c4cf3834
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 28
diffTruncated: true
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Coverage finding always blames `max_file_size_bytes`, even when the cause was the total-injection budget"
    location: "src/squadron/review/coverage.py:35-40"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Model-substitution and answering-model plumbing is consistent end-to-end"
    location: "src/squadron/review/review_client.py:281-307"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "`answers_as_requested` correctly rejects same-family variants"
    location: "src/squadron/models/snapshot.py"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "VerdictSource.IMPOSED and successful_tool_calls are correctly centralized"
    location: "src/squadron/review/models.py:225-246"
---

# Review: code — slice 927

**Verdict:** CONCERNS
**Model:** claude-sonnet-5
**Diff:** truncated: 20000 of 84077 characters reached the model

## Findings

### [CONCERN] Coverage finding always blames `max_file_size_bytes`, even when the cause was the total-injection budget

`impose_diff_coverage`'s synthetic finding text is hardcoded to say the diff was truncated because of `review.max_file_size_bytes`:
```
                                                                           
                                    
                                                                                      
```
But `DiffInjection` (src/squadron/review/models.py:92-109) collapses two distinct causes into the same two numbers. Per the D3 branch in `_inject_file_contents` (src/squadron/review/review_client.py:469-472), a diff can be dropped **entirely** (`injected_chars=0`) not because the diff itself exceeded `max_file_size_bytes`, but because earlier file/CLAUDE.md injections had already exhausted `review.max_total_injection_bytes` before the diff was considered. In that case the finding still says "reached the model (review.max_file_size_bytes)" and tells the operator to "Raise review.max_file_size_bytes" — advice that does nothing for a total-budget exhaustion and sends whoever is triaging a CONCERNS-capped review toward the wrong config knob. `DiffInjection` would need to carry (or the finding text derive) which limit actually caused the shortfall to give accurate remediation guidance. `tests/review/test_coverage.py` only exercises generic partial-truncation numbers and does not cover this D3 "dropped by total budget" path, so the inaccuracy isn't caught by the test-with-implementation tests either.

### [PASS] Model-substitution and answering-model plumbing is consistent end-to-end

`diff_injection`/`requested_model`/`answering_models` are threaded consistently from provider agents (openai/agent.py, sdk/agent.py) through `TurnCapture` accumulation (turn_capture.py) into `ReviewResult`, with clear, non-conflicting fallback semantics for the "provider reported nothing" (Codex, D11) and "hand-built result" (None) cases, each backed by parametrized tests (test_snapshot.py, test_coverage.py, test_agentic_loop.py, test_agent.py for the SDK path).

### [PASS] `answers_as_requested` correctly rejects same-family variants

The exact-prefix + digit-only-suffix regex correctly distinguishes a dated snapshot (`gpt-5-2025-08-07`) from a same-family variant (`gpt-5-mini`), and is covered by both true/false parametrized cases including a dotted-id edge case (`a.b` vs `axb`).

### [PASS] VerdictSource.IMPOSED and successful_tool_calls are correctly centralized

`successful_tool_calls` is defined once and shared between `impose_diff_coverage` and the run-digest render, avoiding the scattered-comparison-value anti-pattern the project guidelines call out; the `IMPOSED` enum value is documented as parser-inaccessible and only settable from `impose_diff_coverage`, keeping the vocabulary closed as intended by D7.

### Run Digest

- Response length: 4321 chars
- Response is newline-free: no
- Tool calls made: 28
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
