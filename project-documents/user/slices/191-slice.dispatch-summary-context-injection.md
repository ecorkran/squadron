---
docType: slice-design
slice: dispatch-summary-context-injection
project: squadron
parent: 180-slices.pipeline-intelligence.md
dependencies: [161-summary-step-with-emit-destinations, 164-profile-aware-summary-model-routing]
interfaces: []
dateCreated: 20260412
dateUpdated: 20260412
status: complete
---

# Slice Design: Dispatch Summary Context Injection

## Overview

When a pipeline summary step routes through a non-SDK profile (slice
164), the one-shot model receives the rendered compaction template
instructions but zero pipeline context. The model has nothing to
summarize and produces empty or hallucinated output like "The
conversation began in this session with no prior history."

SDK-session summaries work because the SDK model already holds the full
conversation from prior pipeline steps. One-shot dispatch models do not
— they see only the single message sent to `capture_summary_via_profile`.

This slice assembles the results of prior pipeline steps into a context
block and prepends it to the instructions sent to the one-shot summary
model. The SDK path is unaffected — the context block is only injected
for non-SDK profiles where the model has no session history.

---

## Motivation

- **Broken user-facing flow.** Non-SDK summary models (minimax,
  gemini-flash) produce empty summaries today. Slice 164 unblocked
  routing to these models but did not solve the context problem.
- **Cost savings blocked.** Summarization is token-cheap work. Users
  cannot use $0.30/M-token models for it because those models produce
  garbage without context.
- **General pattern.** "Give a dispatch agent the results of prior
  pipeline steps" is needed beyond summary — summary is the first
  consumer, but any future one-shot dispatch benefits from the same
  assembly.

---

## Technical Scope

### In Scope

1. **New module `src/squadron/pipeline/summary_context.py`** — a single
   public function that assembles pipeline context from `prior_outputs`
   into a string suitable for prepending to one-shot dispatch
   instructions.

2. **Integration into `_execute_summary()`** — for non-SDK profiles,
   call the context assembler and prepend the result to `instructions`
   before passing to `capture_summary_via_profile`.

3. **Tests** for the context assembler (unit) and the integration point
   in `_execute_summary` (action-level).

### Out of Scope

- **SDK-session summary path.** Unchanged — the SDK model already has
  full conversation history.
- **Dispatch action context injection.** The same pattern could benefit
  `DispatchAction._dispatch_via_agent()`, but dispatch actions receive
  their prompt from `build_context` (cf-op), which already contains the
  phase context. Summary is the action type that has no context source.
  Generalize later if a second consumer appears.
- **Context compression / pre-summarization.** If context assembly
  eventually produces tokens beyond a model's window, a haiku-tier
  pre-compression step could be added. Not needed now — typical pipeline
  runs produce ~30-50k tokens of prior outputs, well within minimax's
  1M context window.
- **New pipeline YAML fields.** No configuration changes — context
  injection is unconditional for non-SDK summary profiles. There is no
  scenario where a non-SDK summary model benefits from receiving zero
  context.

---

## Dependencies

### Prerequisites

- **Slice 161 (Summary Step with Emit Destinations)** — provides the
  `_execute_summary()` shared helper and the `SummaryAction` that this
  slice modifies.
- **Slice 164 (Profile-Aware Summary Model Routing)** — provides the
  SDK/non-SDK profile branch in `_execute_summary()` and
  `capture_summary_via_profile()` in `summary_oneshot.py`.

### Interfaces Required

- `ActionContext.prior_outputs: dict[str, ActionResult]` — the
  accumulated step results from the current pipeline run. Each entry
  has `action_type`, `outputs`, `metadata`, `verdict`, and `findings`.

---

## Architecture

### Context Assembly Flow

```
_execute_summary(context, instructions, ...)
  ├── resolve alias → (model_id, profile)
  ├── if is_sdk_profile(profile):
  │     sdk_session.capture_summary(instructions)   ← unchanged
  └── else:
        context_block = assemble_dispatch_context(context.prior_outputs)
        augmented = context_block + "\n\n" + instructions
        capture_summary_via_profile(
            instructions=augmented,
            model_id=model_id,
            profile=profile,
        )
```

### Context Block Structure

The assembled context block is a plain-text document with delimited
sections, one per prior step that produced meaningful output. The
structure prioritizes readability for a language model over compactness:

```
--- Pipeline Context (for summarization) ---

## Step: design (dispatch)
[response content from the dispatch action]

## Step: review-1 (review)
Verdict: CONCERNS
Findings:
- [finding 1 text]
- [finding 2 text]

## Step: implement (dispatch)
[response content from the dispatch action]

## Step: build-context (cf-op)
[context text from build_context operation]

--- End Pipeline Context ---
```

### What Gets Included

The assembler iterates `prior_outputs` in insertion order (which matches
execution order) and extracts content based on `action_type`:

| `action_type` | Extracted content |
|---|---|
| `dispatch` | `outputs["response"]` — the full model response |
| `review` | `verdict` + `findings` list (text of each finding) |
| `cf-op` | `outputs["stdout"]` when `operation == "build_context"` |
| `summary` | `outputs["summary"]` — covers both `summary` and `compact` steps; the compact step expands to a `summary` action so both appear with `action_type == "summary"` |
| `checkpoint` | Skipped — no meaningful content |
| `commit` | Skipped — git operation metadata, not summarizable |

Steps that produced `success=False` are included with a note:
`[Step failed: {error}]`. Failed steps are pipeline context too — the
summary model should know what was attempted and what went wrong.

Steps with empty or missing content for their expected output key are
skipped silently — they contributed nothing to summarize.

### Module Design

```python
# src/squadron/pipeline/summary_context.py

def assemble_dispatch_context(
    prior_outputs: dict[str, ActionResult],
) -> str:
    """Assemble prior pipeline step results into a context block.

    Returns an empty string if no prior steps produced meaningful
    content, so the caller can unconditionally prepend without
    checking.
    """
```

The function is a pure function of `prior_outputs` — no I/O, no
provider calls, no side effects. This makes it trivially testable and
reusable if a future action type needs the same assembly.

The function returns `""` (empty string) when no prior steps have
extractable content. The caller prepends unconditionally:

```python
if context_block:
    augmented = context_block + "\n\n" + instructions
else:
    augmented = instructions
```

This avoids sending a bare delimiter frame with no content.

---

## Technical Decisions

### Decision 1 — Prepend to instructions, not a separate system message

`capture_summary_via_profile` sends a single `Message` with
`content=instructions`. We prepend the context block to that content
rather than adding a separate system prompt or a second message.

**Rationale:** The one-shot helper builds an `AgentConfig` with
`instructions=""` (no system prompt) by design — it's a
single-message exchange. Adding a system prompt would require changing
the `AgentConfig` shape in `capture_summary_via_profile` and reasoning
about how each provider handles system prompts. Prepending keeps the
interface unchanged and works identically across all providers.

### Decision 2 — Context assembly is unconditional for non-SDK profiles

There is no `inject_context: true/false` YAML knob. Every non-SDK
summary gets context injected. The only scenario where context injection
is not wanted is when the model already has context (the SDK path), and
that path is already branched separately.

**Rationale:** Adding a toggle creates a configuration axis that no
user would set to `false`. If a future need arises for "one-shot
summary without context" (hard to imagine), the toggle can be added
then.

### Decision 3 — Full artifact content, not metadata summaries

The context block includes the full text of dispatch responses, review
findings, and build_context outputs. It does not summarize them into
metadata like "a dispatch action ran successfully."

**Rationale:** The summary model's job is to summarize. Giving it
pre-summarized metadata ("a file was created") defeats the purpose.
Token cost is not a concern — minimax is $0.30/M input tokens, and
typical pipeline runs produce ~30-50k tokens of prior outputs.

### Decision 4 — Extraction logic uses `action_type` dispatch, not string labels

Each `action_type` has a dedicated extraction branch that knows which
output keys to look for. This is a `match/case` on `ActionType` enum
values, not string comparison against step names or labels.

**Rationale:** `action_type` is a stable enum managed by the action
registry. Step names are user-assigned strings that could be anything.

### Decision 5 — Integration point is `_execute_summary`, not `capture_summary_via_profile`

Context injection happens in `_execute_summary()` before the call to
`capture_summary_via_profile`, not inside the one-shot helper itself.

**Rationale:** `capture_summary_via_profile` is a generic one-shot
dispatch helper that takes instructions and sends them to a model. It
should not know about pipeline context assembly — that is a concern of
the summary action, which has access to `ActionContext.prior_outputs`.
Keeping the helper generic means it remains reusable for non-pipeline
use cases (e.g., the `sq _summary-run` CLI command from slice 164).

---

## Implementation Details

### New File

**`src/squadron/pipeline/summary_context.py`**

Single module, single public function. Estimated ~80 lines including
the per-action-type extraction logic.

```python
from __future__ import annotations

from squadron.pipeline.actions import ActionType
from squadron.pipeline.models import ActionResult

_HEADER = "--- Pipeline Context (for summarization) ---"
_FOOTER = "--- End Pipeline Context ---"

# Action types that carry no summarizable content.
_SKIP_TYPES: frozenset[str] = frozenset({
    ActionType.CHECKPOINT,
    ActionType.COMMIT,
})


def assemble_dispatch_context(
    prior_outputs: dict[str, ActionResult],
) -> str:
    """Assemble prior pipeline step results into a context block."""
    sections: list[str] = []

    for step_name, result in prior_outputs.items():
        if result.action_type in _SKIP_TYPES:
            continue

        content = _extract_content(result)
        if not content:
            continue

        header = f"## Step: {step_name} ({result.action_type})"
        sections.append(f"{header}\n{content}")

    if not sections:
        return ""

    body = "\n\n".join(sections)
    return f"{_HEADER}\n\n{body}\n\n{_FOOTER}"


def _extract_content(result: ActionResult) -> str:
    """Extract summarizable content from an ActionResult."""
    if not result.success:
        return f"[Step failed: {result.error}]"

    match result.action_type:
        case ActionType.DISPATCH:
            return str(result.outputs.get("response", ""))
        case ActionType.REVIEW:
            return _format_review(result)
        case ActionType.CF_OP:
            if result.outputs.get("operation") == "build_context":
                return str(result.outputs.get("stdout", ""))
            return ""
        case ActionType.SUMMARY:
            # Covers both summary and compact steps: the compact step expands
            # to a summary action, so both appear with action_type "summary".
            return str(result.outputs.get("summary", ""))
        case _:
            return ""


def _format_review(result: ActionResult) -> str:
    """Format review verdict and findings into readable text."""
    parts: list[str] = []
    if result.verdict:
        parts.append(f"Verdict: {result.verdict}")
    if result.findings:
        parts.append("Findings:")
        for finding in result.findings:
            parts.append(f"- {finding}")
    return "\n".join(parts)
```

### Modified File

**`src/squadron/pipeline/actions/summary.py`** — `_execute_summary()`

The change is ~5 lines in the non-SDK branch:

```python
# In _execute_summary(), after the profile branch is determined:
if is_sdk_profile(profile):
    # ... existing SDK path unchanged ...
else:
    from squadron.pipeline.summary_context import assemble_dispatch_context

    context_block = assemble_dispatch_context(context.prior_outputs)
    augmented_instructions = (
        f"{context_block}\n\n{instructions}" if context_block
        else instructions
    )
    summary = await capture_summary_via_profile(
        instructions=augmented_instructions,
        model_id=model_id,
        profile=profile,
    )
```

### Test Files

**`tests/pipeline/test_summary_context.py`** (new)

Unit tests for `assemble_dispatch_context`:

- `test_empty_prior_outputs_returns_empty_string` — no prior steps.
- `test_dispatch_output_included` — a dispatch step's response is
  extracted.
- `test_review_output_includes_verdict_and_findings` — review content
  is formatted correctly.
- `test_cf_op_build_context_included` — build_context stdout is
  extracted.
- `test_cf_op_non_build_context_skipped` — other cf-op operations
  (set_phase, set_slice) are not included.
- `test_failed_step_included_with_error` — failed steps show their
  error text.
- `test_checkpoint_skipped` — checkpoint actions produce no content.
- `test_commit_skipped` — commit actions produce no content.
- `test_summary_output_included` — prior summary results are included.
- `test_multiple_steps_ordered` — output preserves execution order.
- `test_step_with_empty_response_skipped` — dispatch with
  `response: ""` produces no section.
- `test_header_and_footer_present` — output is framed with delimiters.

**`tests/pipeline/actions/test_summary.py`** (extend)

Integration test for context injection:

- `test_non_sdk_summary_injects_prior_context` — mock
  `capture_summary_via_profile`, set up `prior_outputs` with a dispatch
  result, verify that the `instructions` argument passed to the mock
  contains the pipeline context header and the dispatch response text.
- `test_sdk_summary_does_not_inject_context` — verify SDK path does
  NOT call `assemble_dispatch_context` or modify instructions.

---

## Integration Points

### Provides

- `assemble_dispatch_context()` — a pure function any future action
  can call to get a text representation of prior pipeline results. Not
  exposed as a public API yet; import path is
  `squadron.pipeline.summary_context`.

### Consumes

- `ActionContext.prior_outputs` — the step result accumulator from
  the pipeline executor.
- `ActionType` enum values — for type-safe extraction dispatch.
- `_execute_summary()` in `actions/summary.py` — the integration
  point.
- `capture_summary_via_profile()` in `summary_oneshot.py` — unchanged,
  just receives longer instructions.

---

## Success Criteria

### Functional

1. A pipeline with `summary: { template: minimal, model: minimax,
   emit: [stdout] }` following a dispatch step produces a summary that
   references content from the dispatch step's response.
2. The same pipeline with `model: haiku` (SDK profile) produces a
   summary using the SDK session's conversation history, not the
   assembled context block.
3. A pipeline where all prior steps are checkpoint/commit (no
   extractable content) runs the non-SDK summary with unmodified
   instructions — no empty context delimiters in the output.
4. A pipeline with a failed prior step includes `[Step failed: ...]`
   in the context block sent to the summary model.
5. Review findings from a prior review step appear in the context block
   with verdict and individual finding text.

### Technical

1. `assemble_dispatch_context` is a pure function with no I/O — all
   tests run without mocking providers, sessions, or network calls.
2. The SDK summary path in `_execute_summary()` is not modified — no
   new imports, no new branches, no behavioral change.
3. No new pipeline YAML fields or configuration — context injection is
   automatic for non-SDK profiles.

---

## Verification Walkthrough

> **Environment note:** Scenarios 1–3 use `dispatch` steps which require
> `ClaudeSDKClient` (the straight-CLI executor). They cannot run inside a
> Claude Code session (IDE or Claude Code CLI). Run these from a standard
> terminal using `sq run`. Scenario 4 (unit tests) runs anywhere.

### Setup

```bash
# Confirm minimax alias resolves to a non-SDK profile
uv run python -c "
from squadron.models.aliases import resolve_model_alias
print(resolve_model_alias('minimax'))
"
# Actual output: ('minimax/minimax-m2.7', 'openrouter')

# Confirm OpenRouter API key is available
echo "OPENROUTER_API_KEY present: $([ -n \"$OPENROUTER_API_KEY\" ] && echo yes || echo no)"
```

### Scenario 1 — Non-SDK summary with pipeline context

Run from a standard terminal (not inside Claude Code):

```bash
cat > /tmp/test-191.yaml <<'EOF'
name: test-191-context-injection
params:
  slice: "191"
  phase: "4"
steps:
  - dispatch:
      prompt: "Describe the architecture of a simple web server in 3 paragraphs."
      model: haiku
  - summary:
      template: minimal
      model: minimax
      emit: [stdout]
EOF

sq run /tmp/test-191.yaml -vv
```

**Expected:** The summary output references the web server architecture
content from the dispatch step. At `-vv` verbosity, the log shows the
assembled context block being prepended to the summary instructions.

**Failure indicator:** The summary says "no prior history" or produces
generic content unrelated to web server architecture.

### Scenario 2 — SDK summary unchanged

Run from a standard terminal:

```bash
cat > /tmp/test-191-sdk.yaml <<'EOF'
name: test-191-sdk-path
params:
  slice: "191"
  phase: "4"
steps:
  - dispatch:
      prompt: "Describe the architecture of a simple web server in 3 paragraphs."
      model: haiku
  - summary:
      template: minimal
      model: haiku
      emit: [stdout]
EOF

sq run /tmp/test-191-sdk.yaml -vv
```

**Expected:** Summary runs via the SDK session path. The instructions
sent to `capture_summary` are the rendered template only — no pipeline
context prefix. The summary still works because the SDK session has
the full conversation history.

### Scenario 3 — Empty prior outputs

Run from a standard terminal:

```bash
cat > /tmp/test-191-empty.yaml <<'EOF'
name: test-191-empty
params:
  slice: "191"
  phase: "4"
steps:
  - summary:
      template: minimal
      model: minimax
      emit: [stdout]
EOF

sq run /tmp/test-191-empty.yaml -vv
```

**Expected:** The summary model receives only the template instructions
(no context prefix, no empty delimiters). The summary will be minimal
since there is nothing to summarize, but it should not crash or produce
a malformed context block.

### Scenario 4 — Unit tests pass

```bash
uv run pytest tests/pipeline/test_summary_context.py -v
uv run pytest tests/pipeline/actions/test_summary.py -v -k "context"
```

**Expected:** All new tests pass. Existing summary tests are unaffected.

**Actual result (20260412):** 13/13 unit tests pass; 2/2 integration tests
pass; all 26 total summary action tests pass. 615/615 pipeline tests pass.

---

## Risk Assessment

- **Low: Context block size.** Typical pipeline runs produce ~30-50k
  tokens. Minimax and similar models have 1M+ context windows. No risk
  of overflow in normal usage. If a pipeline generates unusual volume
  (e.g., multiple large dispatch responses), the summary model handles
  it — summarization is inherently tolerant of long input.

- **Low: Extraction logic maintenance.** New action types added in
  future slices need a corresponding extraction branch in
  `_extract_content`. The `match/case` default returns `""`, so an
  unrecognized type is silently skipped rather than crashing. A
  follow-up slice that adds a new action type should add its extraction
  branch at that time.

---

## Implementation Notes

- **Effort: 2/5.** One new ~80-line module, a ~5-line edit to the
  summary action, and ~150 lines of tests. No new dependencies, no
  schema changes, no configuration changes.

- **Ordering note.** This slice has no dependency on any 180-band slice
  and should land first in the 180 initiative. It depends only on
  140-band slices 161 and 164, both of which are complete.
