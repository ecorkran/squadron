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
reviewedSha: e560c6e36de187e209bb16092d77d00b58e9940e
toolsSuppressedReason: run-suppressed
diffTruncated: true
findings:
  - id: F001
    severity: concern
    category: dry
    summary: "`successful_calls` formula duplicated across two modules"
    location: "src/squadron/review/coverage.py:26"
  - id: F002
    severity: concern
    category: naming
    summary: "New `to_dict()` keys mix snake_case into a camelCase-keyed schema"
    location: "src/squadron/review/models.py#ReviewResult.to_dict"
  - id: F003
    severity: concern
    category: api-contract
    summary: "`metadata[\"model\"]` semantics silently flipped from requested → answering model"
    location: "src/squadron/pipeline/actions/review.py:420"
  - id: F004
    severity: note
    category: type-safety
    summary: "Possible `None` entering `answering_models: list[str]` from the SDK path"
    location: "src/squadron/providers/sdk/agent.py:184-194"
  - id: F005
    severity: note
    category: test-coverage
    summary: "No test diffs visible for the new logic"
    location: "unverified"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "`DiffInjection` and `answers_as_requested` are well-scoped and documented"
    location: "src/squadron/review/models.py#DiffInjection"
---

# Review: code — slice 927

**Verdict:** CONCERNS
**Model:** claude-sonnet-5
**Diff:** truncated: 20000 of 83324 characters reached the model

## Findings

### [CONCERN] `successful_calls` formula duplicated across two modules

`successful_calls = (result.tool_calls_made or 0) - (result.failed_tool_calls or 0)` appears verbatim in both `coverage.py:impose_diff_coverage` and the new digest-line block in `persistence.py` (`_run_digest_lines`). Both encode the same "no tools offered counts as zero successes" semantics via `or 0`. Per project rules ("Do not duplicate logic," "changing a value should require editing exactly one place"), this should be a single helper (e.g. a `ReviewResult.successful_tool_calls` property) that both call sites use, so the `or 0` vs `is None` distinction the coverage.py docstring is careful to document can't drift out of sync between the two copies.

### [CONCERN] New `to_dict()` keys mix snake_case into a camelCase-keyed schema

The diff shows `"verdictSource"` (existing, unchanged) immediately followed by new keys `"diff_chars"`, `"diff_chars_injected"`, `"diff_truncated"`, `"requested_model"`, `"answering_models"`, `"model_substituted"` — all snake_case. The accompanying comment says `"diff_truncated"` "mirrors frontmatter's `diffTruncated`," which itself signals the two should probably share a casing convention with the rest of this JSON output. I can't see the full `to_dict()` body (only the diff hunk), so I can't confirm whether snake_case or camelCase is actually the prevailing convention here — but whichever it is, the new fields should match it, not introduce a third mixed pattern. Worth a quick check before merge.

### [CONCERN] `metadata["model"]` semantics silently flipped from requested → answering model

Previously `metadata["model"]` held `model_id` (the requested model); now it holds `result.model` (the model that answered), with the requested id moved to a new `requested_model` key. The comment explains this is intentional (D10), but it's a breaking change to an existing, presumably-consumed field name rather than an additive one — any other code or downstream tooling reading `metadata["model"]` expecting "what was requested" will now silently get "what answered" instead. I don't have visibility into other readers of this metadata key (no grep/read tools available this session), so I can't confirm whether call sites were audited. Worth explicit confirmation that all consumers of this metadata key were updated, given the rule against silent behavior changes on shared contracts.

### [NOTE] Possible `None` entering `answering_models: list[str]` from the SDK path

```python
    
                                      
                                         
                                                   
  
                                                
```
This only excludes the synthetic placeholder and subagent messages; if `sdk_msg.model` can ever be `None` (I can't confirm the SDK's type from this session — no access to the `claude-agent-sdk` stubs), `None` would be appended to a field typed and documented elsewhere (`ReviewResult.answering_models: list[str] | None`) as "a real, observed fact" list of model ids, breaking that invariant and the `list[str]` type. Low confidence — flag for a quick check of the SDK's message type rather than a required fix.

### [NOTE] No test diffs visible for the new logic

The visible diff adds two new modules (`models/snapshot.py`, `review/coverage.py`) and new branching logic in both agent providers, but no `test_*.py` changes appear in what was shown. The diff was truncated at 20KB before reaching the end of `persistence.py`, so tests may exist further along and simply weren't shown — this is not a confirmed gap, just something to verify given the project's "write tests as you go" standard, especially for `answers_as_requested`'s snapshot-suffix regex and `impose_diff_coverage`'s boundary conditions (`successful_calls == 0` vs `> 0`, `diff_injection is None`).

### [PASS] `DiffInjection` and `answers_as_requested` are well-scoped and documented

Both are small, immutable (`frozen=True` / pure function), and each carries a docstring explaining the non-obvious "why" (chars vs. bytes, exact-match-only snapshot semantics) rather than restating the what. Good adherence to the comment-only-when-non-obvious rule.

### Run Digest

- Response length: 5082 chars
- Response is newline-free: no
- Tool calls made: not offered
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
