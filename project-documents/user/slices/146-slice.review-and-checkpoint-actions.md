---
docType: slice-design
slice: review-and-checkpoint-actions
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [143, 145]
interfaces: [147, 149, 150]
dateCreated: 20260331
dateUpdated: 20260331
status: not_started
---

# Slice Design: Review and Checkpoint Actions (146)

## Overview

This slice implements two pipeline actions that form the quality gate layer of the pipeline system:

- **Review action** — runs a review template against an artifact within a pipeline step, consumes structured findings from the review system (slice 143), produces a verdict and structured finding set in `ActionResult`, and handles review file persistence.
- **Checkpoint action** — pauses pipeline execution for human decision, serializes pipeline state for resume, presents findings and status summary, and accepts human input (approve, revise, skip, abort, override model/config for subsequent steps).

Together, these actions enable the `review → checkpoint` pattern that appears in every phase step type (slice 147). The review action evaluates quality; the checkpoint action gates progression based on that evaluation.

**Slice plan entry:** **(146) Review and Checkpoint Actions** — Review action: run a review template against an artifact within a pipeline step, consume structured findings from slice 143, produce verdict and structured finding set, handle review file persistence. Checkpoint action: pause pipeline execution for human decision, serialize pipeline state for resume, present findings and status summary, accept human input (approve, revise, skip, abort, override model/config for subsequent steps). Checkpoint triggers: always, on-concerns, on-fail, never. Dependencies: [143, 145]. Risk: Medium (checkpoint interactive UX). Effort: 3/5

---

## Value

- **Review gates in pipelines.** Without the review action, pipelines can dispatch to models but cannot evaluate the quality of the output. The review action closes the loop: dispatch produces artifacts, review evaluates them, and the verdict feeds into flow control.
- **Human-in-the-loop checkpoints.** Fully automated pipelines are risky for non-trivial work. Checkpoints give humans control over whether to proceed, revise, or abort — without losing pipeline state. This is especially important for design and implementation phases where review findings need human judgment.
- **Structured findings in pipeline results.** The review action bridges the review system (slice 143) and the pipeline system (slice 142) by populating `ActionResult.verdict` and `ActionResult.findings` with machine-readable structured data. This enables downstream flow control (slice 149) and future convergence loops (160).
- **Reuse of existing review infrastructure.** The review action delegates to `run_review_with_profile()` — no new review execution path. This means all existing review templates, rules injection, provider routing, and structured output instructions work identically in pipelines.

---

## Technical Scope

### Included

**Review Action (`review.py`):**
- `ReviewAction` class satisfying the `Action` protocol
- Validation: `template` required; `cwd` required
- Template resolution via `get_template()` from the review template registry
- Review execution via `run_review_with_profile()` from `review_client.py`
- Model resolution via `context.resolver.resolve()` (same pattern as dispatch)
- Profile resolution (same cascade as dispatch: explicit param → alias-derived → default)
- Populate `ActionResult.verdict` from `ReviewResult.verdict`
- Populate `ActionResult.findings` from `ReviewResult.structured_findings`
- Review file persistence: save review output to the standard review file location using existing formatting logic
- Raw review output in `ActionResult.outputs["response"]`
- Metadata capture: model, profile, template name
- Auto-registration at module level

**Checkpoint Action (`checkpoint.py`):**
- `CheckpointAction` class satisfying the `Action` protocol
- Checkpoint trigger evaluation: `always`, `on-concerns`, `on-fail`, `never`
- Trigger resolution from `context.params["trigger"]` with default `on-concerns`
- Verdict evaluation: compare prior review verdict from `context.prior_outputs` against trigger threshold
- When checkpoint fires: return `ActionResult(success=True)` with `outputs["checkpoint"] = "paused"` and `outputs["reason"]` — the executor (slice 149) interprets this to pause
- When checkpoint is skipped (trigger not met): return `ActionResult(success=True)` with `outputs["checkpoint"] = "skipped"`
- Human input options: `approve`, `revise`, `skip`, `abort`
- Model/config override: `outputs["overrides"]` dict for downstream step modifications
- Status summary construction from prior step outputs
- Auto-registration at module level

**Checkpoint trigger enum:**
- `CheckpointTrigger` StrEnum: `ALWAYS`, `ON_CONCERNS`, `ON_FAIL`, `NEVER`
- Defined in pipeline models or checkpoint module

### Excluded

- Pipeline state serialization to disk (slice 150 — state persistence)
- Actual pipeline pausing/resume mechanics (slice 149 — executor interprets checkpoint result)
- Interactive terminal UI for checkpoint presentation (slice 151 — CLI integration; checkpoint action returns data, CLI renders it)
- Convergence loop integration (160 scope)
- Review template creation (existing infrastructure from slices 105/143)

---

## Dependencies

### Prerequisites

- **Slice 143** (Structured Review Findings) — `ReviewResult.structured_findings`, `StructuredFinding` model, structured output in review frontmatter
- **Slice 145** (Dispatch Action) — pattern reference for action implementation; shared provider loader
- **Slice 142** (Pipeline Core Models) — `Action` protocol, `ActionType`, `ActionContext`, `ActionResult`, `ValidationError`, `ModelResolver`, action registry
- **Review system** (slices 105/128) — `run_review_with_profile()`, `ReviewTemplate`, `get_template()`, template registry, review file formatting

### Interfaces Required

- `ActionContext.resolver: ModelResolver` — cascade resolution returns `(model_id, profile_name)`
- `ActionContext.params: dict[str, object]` — carries `template`, `model`, `profile`, `trigger`, `cwd`, and inputs for review
- `ActionContext.prior_outputs: dict[str, ActionResult]` — checkpoint reads review verdict from prior step
- `ReviewResult.verdict: Verdict` — PASS, CONCERNS, FAIL, UNKNOWN
- `ReviewResult.structured_findings: list[StructuredFinding]` — machine-readable findings
- `run_review_with_profile()` — async review execution returning `ReviewResult`
- `get_template(name)` — template resolution from registry
- Review file formatting functions from CLI commands module

---

## Architecture

### Data Flow — Review Action

```
context.params["template"] ──► get_template() ──► ReviewTemplate
                                                      │
context.params.get("model") ──► ModelResolver.resolve() ──► (model_id, profile)
context.params.get("step_model")─┘
                                                      │
context.params (inputs: diff, files, cwd) ────────────┤
                                                      ▼
                              run_review_with_profile(
                                  template, inputs,
                                  profile=..., model=...,
                                  rules_content=...,
                              )
                                      │
                                      ▼
                              ReviewResult
                                  ├── verdict ──► ActionResult.verdict
                                  ├── structured_findings ──► ActionResult.findings
                                  ├── raw_output ──► ActionResult.outputs["response"]
                                  └── (file persistence) ──► review file on disk
```

### Data Flow — Checkpoint Action

```
context.params["trigger"] ──► CheckpointTrigger enum
                                      │
context.prior_outputs ──► find latest review ActionResult
                              │
                              ├── verdict (PASS/CONCERNS/FAIL)
                              │
                              ▼
                    trigger evaluation:
                      NEVER → skip
                      ALWAYS → fire
                      ON_FAIL → fire if verdict == FAIL
                      ON_CONCERNS → fire if verdict in (CONCERNS, FAIL)
                              │
                     ┌────────┴────────┐
                     │                 │
                   skip              fire
                     │                 │
                     ▼                 ▼
           ActionResult(           ActionResult(
             checkpoint="skipped"    checkpoint="paused",
           )                         reason="...",
                                     summary={...},
                                     human_options=[
                                       "approve","revise",
                                       "skip","abort"
                                     ]
                                   )
```

### Key Design Decisions

**1. Delegate to existing review infrastructure**

The review action calls `run_review_with_profile()` directly — the same function used by `sq review code`, `sq review slice`, etc. This avoids duplicating review execution logic and ensures all review improvements (rules injection, structured output instructions, provider routing) apply equally to pipeline reviews.

**2. Review inputs come from `context.params`**

The step type (slice 147) assembles the review inputs dict before the review action runs. The review action does not know about slices, phases, or CF context — it receives `template`, `cwd`, and template-specific inputs (e.g., `diff`, `files`, `against`) through `context.params`. This keeps the action focused on execution, not context assembly.

**3. File persistence is the review action's responsibility**

Review file persistence (saving the review markdown with YAML frontmatter to `project-documents/user/reviews/`) is handled by the review action, not the executor or step type. The action has access to all the data needed: `ReviewResult`, template name, and slice context from params. This follows the architecture's principle that each action "owns" its domain.

The formatting logic already exists in `cli/commands/review.py` (`_format_review_markdown`, `_save_review_file`). The review action will extract or reuse these functions. If they're tightly coupled to CLI concerns (e.g., `typer.echo`), extract the pure formatting/saving logic to a shared location (e.g., `review/persistence.py`).

**4. Checkpoint action returns data, does not block**

The checkpoint action does not implement interactive blocking. It returns an `ActionResult` with `outputs["checkpoint"] = "paused"` and the executor (slice 149) interprets this to pause execution and serialize state. The CLI layer (slice 151) is responsible for presenting the checkpoint to the user and collecting input.

This separation means the checkpoint action is testable without terminal I/O and the executor can handle checkpoints differently in different contexts (CLI interactive, CI headless, future web UI).

**5. Checkpoint trigger evaluation uses prior review output**

The checkpoint reads the verdict from `context.prior_outputs` — specifically, it looks for the most recent `ActionResult` with `verdict != None`. This means the step type must ensure the review action runs before the checkpoint in the action sequence. The checkpoint does not re-execute a review.

**6. Human input options are data, not behavior**

The checkpoint action declares what options the human has (`approve`, `revise`, `skip`, `abort`) and what overrides are possible, but does not implement the behavior of each option. The executor (slice 149) and CLI (slice 151) implement the actual response handling. This keeps the action simple and the behavior composable.

**7. Verdict mapping from ReviewResult to ActionResult**

`ReviewResult.verdict` is a `Verdict` enum (`PASS`, `CONCERNS`, `FAIL`, `UNKNOWN`). `ActionResult.verdict` is `str | None`. The review action converts: `ActionResult.verdict = result.verdict.value`. This preserves the verdict as a string for serialization while keeping enum safety during execution.

---

## Implementation Details

### ReviewAction Class

```python
# src/squadron/pipeline/actions/review.py

class ReviewAction:
    @property
    def action_type(self) -> str:
        return ActionType.REVIEW

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        # "template" is required
        # "cwd" is required (needed for review execution)

    async def execute(self, context: ActionContext) -> ActionResult:
        # 1. Resolve template via get_template()
        # 2. Resolve model via context.resolver.resolve()
        # 3. Resolve profile (same pattern as dispatch)
        # 4. Build review inputs dict from context.params
        # 5. Load rules content if applicable
        # 6. Call run_review_with_profile()
        # 7. Persist review file to disk
        # 8. Map ReviewResult → ActionResult with verdict and findings
        # 9. Return result

register_action(ActionType.REVIEW, ReviewAction())
```

### Execute Behavior — Review

**Template resolution:**
```python
template_name = str(context.params["template"])
template = get_template(template_name)
```

**Model and profile resolution (same pattern as dispatch):**
```python
action_model = str(context.params["model"]) if "model" in context.params else None
step_model = str(context.params["step_model"]) if "step_model" in context.params else None
model_id, alias_profile = context.resolver.resolve(action_model, step_model)

profile_name = (
    str(context.params["profile"])
    if "profile" in context.params
    else alias_profile or ProfileName.SDK
)
```

**Build review inputs:**
```python
# Template-specific inputs from context.params
inputs: dict[str, str] = {}
inputs["cwd"] = str(context.params["cwd"])

# Pass through template-relevant keys
for key in ("diff", "files", "against", "input"):
    if key in context.params:
        inputs[key] = str(context.params[key])
```

**Execute review:**
```python
result = await run_review_with_profile(
    template=template,
    inputs=inputs,
    profile=profile_name,
    model=model_id,
    rules_content=rules_content,
)
```

**Persist review file:**
```python
# Extract or reuse persistence logic from cli/commands/review.py
review_path = save_review_file(
    result=result,
    review_type=template_name,
    slice_info=slice_info,  # from context.params if available
    cwd=context.cwd,
)
```

**Result mapping:**
```python
return ActionResult(
    success=True,
    action_type=self.action_type,
    outputs={
        "response": result.raw_output,
        "review_file": str(review_path) if review_path else "",
    },
    verdict=result.verdict.value,
    findings=[f.__dict__ for f in result.structured_findings],
    metadata={
        "model": model_id,
        "profile": profile_name,
        "template": template_name,
    },
)
```

### Error Handling — Review

| Error | Source | Handling |
|-------|--------|----------|
| `KeyError` from `get_template()` | Unknown template name | Return `ActionResult(success=False, error=...)` |
| `ModelResolutionError` | `resolver.resolve()` | Return `ActionResult(success=False, error=...)` |
| `ModelPoolNotImplemented` | `resolver.resolve()` | Return `ActionResult(success=False, error=...)` |
| Any exception from `run_review_with_profile()` | Provider/API failure | Return `ActionResult(success=False, error=...)`, log at ERROR |
| File persistence failure | Disk I/O | Log warning, continue (non-fatal — the review result is still returned) |

Same pattern as dispatch: the review action never raises. All errors become `ActionResult(success=False)`.

### CheckpointAction Class

```python
# src/squadron/pipeline/actions/checkpoint.py

class CheckpointTrigger(StrEnum):
    ALWAYS = "always"
    ON_CONCERNS = "on-concerns"
    ON_FAIL = "on-fail"
    NEVER = "never"

class CheckpointAction:
    @property
    def action_type(self) -> str:
        return ActionType.CHECKPOINT

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        # "trigger" is optional (defaults to ON_CONCERNS)
        # If present, must be a valid CheckpointTrigger value

    async def execute(self, context: ActionContext) -> ActionResult:
        # 1. Resolve trigger from context.params
        # 2. Find most recent review verdict in prior_outputs
        # 3. Evaluate trigger against verdict
        # 4. If skip: return skipped result
        # 5. If fire: build summary and return paused result

register_action(ActionType.CHECKPOINT, CheckpointAction())
```

### Execute Behavior — Checkpoint

**Trigger resolution:**
```python
trigger_str = str(context.params.get("trigger", CheckpointTrigger.ON_CONCERNS))
trigger = CheckpointTrigger(trigger_str)
```

**Find prior review verdict:**
```python
def _find_review_verdict(prior_outputs: dict[str, ActionResult]) -> str | None:
    """Return the most recent review verdict from prior step outputs."""
    for result in reversed(list(prior_outputs.values())):
        if result.verdict is not None:
            return result.verdict
    return None
```

**Trigger evaluation:**
```python
_TRIGGER_THRESHOLDS: dict[CheckpointTrigger, set[str]] = {
    CheckpointTrigger.ALWAYS: set(),  # fires regardless
    CheckpointTrigger.ON_CONCERNS: {"CONCERNS", "FAIL"},
    CheckpointTrigger.ON_FAIL: {"FAIL"},
    CheckpointTrigger.NEVER: set(),  # never fires
}

def _should_fire(trigger: CheckpointTrigger, verdict: str | None) -> bool:
    if trigger == CheckpointTrigger.ALWAYS:
        return True
    if trigger == CheckpointTrigger.NEVER:
        return False
    if verdict is None:
        return False  # no review to evaluate
    return verdict.upper() in _TRIGGER_THRESHOLDS[trigger]
```

**Checkpoint result when fired:**
```python
return ActionResult(
    success=True,
    action_type=self.action_type,
    outputs={
        "checkpoint": "paused",
        "reason": f"Review verdict: {verdict}",
        "trigger": trigger.value,
        "human_options": ["approve", "revise", "skip", "abort"],
    },
    verdict=verdict,
    metadata={
        "step": context.step_name,
        "pipeline": context.pipeline_name,
    },
)
```

**Checkpoint result when skipped:**
```python
return ActionResult(
    success=True,
    action_type=self.action_type,
    outputs={
        "checkpoint": "skipped",
        "trigger": trigger.value,
        "verdict_seen": verdict or "none",
    },
)
```

### Review File Persistence

The review CLI commands module (`cli/commands/review.py`) contains `_format_review_markdown()` and `_save_review_file()` which are currently private to the CLI. The review action needs this same functionality.

**Approach:** Extract the pure formatting and persistence logic into `review/persistence.py`:

```python
# src/squadron/review/persistence.py

def format_review_markdown(
    result: ReviewResult,
    review_type: str,
    slice_info: SliceInfo | None,
    source_document: str | None,
) -> str:
    """Format a ReviewResult as markdown with YAML frontmatter."""

def save_review_file(
    content: str,
    review_type: str,
    slice_name: str,
    slice_index: int | None,
    cwd: str,
) -> Path | None:
    """Save review markdown to the standard location. Returns path or None."""
```

The CLI commands would then import from `review/persistence.py` instead of using private functions. This is a minor refactor that makes the persistence logic available to both the CLI and the pipeline review action.

**Note:** If `SliceInfo` or slice context is not available in `context.params`, the review action saves with whatever metadata it has. Missing slice info is not an error — the review file will have fewer frontmatter fields but is still valid.

---

## Integration Points

### Provides to Other Slices

- **Slice 147 (Step Types)** — Phase step type composes: `cf-op → dispatch → review → checkpoint → commit`. The review and checkpoint actions are the quality gate in this sequence.
- **Slice 149 (Executor)** — Executor reads `ActionResult.outputs["checkpoint"]` to determine whether to pause. Reads `ActionResult.verdict` and `ActionResult.findings` for flow control.
- **Slice 150 (State & Resume)** — Checkpoint result provides the data that state persistence serializes. On resume, the executor restores from checkpoint.
- **Slice 160 (Convergence)** — `ActionResult.findings` with structured `StructuredFinding` data enables cross-iteration identity matching.

### Consumes from Other Slices

- **Slice 142** — `Action` protocol, `ActionContext`, `ActionResult`, `ModelResolver`, action registry, `ActionType.REVIEW`, `ActionType.CHECKPOINT`
- **Slice 143** — `ReviewResult.structured_findings`, `StructuredFinding` dataclass
- **Review system (105/128)** — `run_review_with_profile()`, template registry, review models
- **Provider system** — `get_profile()`, `ProfileName`, provider loading via `ensure_provider_loaded()`

---

## Success Criteria

### Functional Requirements

- [ ] `ReviewAction` satisfies the `Action` protocol (`isinstance` check passes)
- [ ] `ReviewAction.action_type` returns `"review"`
- [ ] `ReviewAction.validate()` returns error when `template` is missing
- [ ] `ReviewAction.validate()` returns error when `cwd` is missing
- [ ] `ReviewAction.validate()` returns empty list for valid config
- [ ] `ReviewAction.execute()` resolves template via `get_template()`
- [ ] `ReviewAction.execute()` resolves model through `context.resolver.resolve()`
- [ ] `ReviewAction.execute()` calls `run_review_with_profile()` with correct template, inputs, model, profile
- [ ] `ReviewAction.execute()` populates `ActionResult.verdict` from review verdict
- [ ] `ReviewAction.execute()` populates `ActionResult.findings` from structured findings
- [ ] `ReviewAction.execute()` persists review file to disk
- [ ] `ReviewAction.execute()` returns `success=False` on any error (never raises)
- [ ] `ReviewAction` auto-registers at module import time
- [ ] `CheckpointAction` satisfies the `Action` protocol
- [ ] `CheckpointAction.action_type` returns `"checkpoint"`
- [ ] `CheckpointAction.validate()` rejects invalid trigger values
- [ ] `CheckpointAction.validate()` accepts valid triggers and empty config
- [ ] `CheckpointAction.execute()` returns `checkpoint="skipped"` when trigger is `never`
- [ ] `CheckpointAction.execute()` returns `checkpoint="paused"` when trigger is `always`
- [ ] `CheckpointAction.execute()` evaluates `on-concerns` correctly: fires on CONCERNS and FAIL, skips on PASS
- [ ] `CheckpointAction.execute()` evaluates `on-fail` correctly: fires on FAIL only, skips on PASS and CONCERNS
- [ ] `CheckpointAction.execute()` handles missing prior review verdict gracefully (no review = no fire, except `always`)
- [ ] `CheckpointAction` auto-registers at module import time
- [ ] `CheckpointTrigger` enum has values: `always`, `on-concerns`, `on-fail`, `never`

### Technical Requirements

- [ ] pyright clean (0 errors) on both action modules
- [ ] ruff clean on all modified files
- [ ] All existing tests continue to pass
- [ ] New tests mock all external boundaries (no real API calls, no real file I/O for review)
- [ ] Review persistence logic extracted to shared module (not duplicated from CLI)
- [ ] Both actions registered and visible in `list_actions()`
- [ ] Integration tests verify coexistence with dispatch, cf-op, commit, devlog actions

### Verification Walkthrough

**1. Protocol compliance:**
```bash
python -c "
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.actions.checkpoint import CheckpointAction
r = ReviewAction()
c = CheckpointAction()
print('review protocol:', isinstance(r, Action))
print('review type:', r.action_type)
print('checkpoint protocol:', isinstance(c, Action))
print('checkpoint type:', c.action_type)
"
# Expected: review protocol: True, review type: review
# Expected: checkpoint protocol: True, checkpoint type: checkpoint
```

**2. Registration:**
```bash
python -c "
import squadron.pipeline.actions.review
import squadron.pipeline.actions.checkpoint
from squadron.pipeline.actions import list_actions
actions = list_actions()
print('review registered:', 'review' in actions)
print('checkpoint registered:', 'checkpoint' in actions)
"
# Expected: both True
```

**3. Checkpoint trigger enum:**
```bash
python -c "
from squadron.pipeline.actions.checkpoint import CheckpointTrigger
for t in CheckpointTrigger:
    print(t.name, '=', t.value)
"
# Expected: ALWAYS=always, ON_CONCERNS=on-concerns, ON_FAIL=on-fail, NEVER=never
```

**4. Validation:**
```bash
python -c "
from squadron.pipeline.actions.review import ReviewAction
a = ReviewAction()
print('missing template:', a.validate({}))
print('valid:', a.validate({'template': 'code', 'cwd': '.'}))
"
# Expected: missing template returns ValidationError; valid returns []
```

**5. Full test suite:**
```bash
python -m pytest tests/pipeline/actions/test_review_action.py -v
python -m pytest tests/pipeline/actions/test_checkpoint.py -v
python -m pytest tests/pipeline/actions/test_registry_integration.py -v
python -m pytest --tb=short -q  # all tests pass
pyright src/squadron/pipeline/actions/review.py
pyright src/squadron/pipeline/actions/checkpoint.py
ruff check src/squadron/pipeline/actions/
```

---

## Risk Assessment

### Technical Risks

**Checkpoint interactive UX (Medium)**

The checkpoint action defines what data the executor needs to pause and resume, but the actual interactive experience depends on slices 149 (executor) and 151 (CLI). If the data contract between checkpoint result and executor is wrong, it will require rework.

**Mitigation:** Keep the checkpoint action's output simple and data-oriented. The `outputs` dict is flexible — the executor can interpret whatever fields are present. Start with the minimal set (`checkpoint`, `reason`, `human_options`) and extend if needed during executor implementation.

**Review file persistence coupling (Low)**

The review file formatting logic in `cli/commands/review.py` may be more tightly coupled to CLI concerns than expected (e.g., `SliceInfo` resolution via CF, Rich formatting).

**Mitigation:** Extract only the pure formatting and file-writing logic. If `SliceInfo` is hard to construct in a pipeline context, make it optional — the review file will have fewer frontmatter fields but remains valid.

---

## Implementation Notes

### Development Approach

1. **Extract review persistence** — Move `_format_review_markdown()` and `_save_review_file()` from `cli/commands/review.py` to `review/persistence.py`. Update CLI imports. Verify existing review CLI tests still pass.
2. **Implement `CheckpointAction`** — Simpler of the two; no external dependencies beyond pipeline models. Includes `CheckpointTrigger` enum. Write tests.
3. **Implement `ReviewAction`** — Depends on persistence extraction. Mock `run_review_with_profile()`, template registry, and file I/O. Write tests.
4. **Integration tests** — Verify both actions register alongside existing actions. Verify coexistence in `list_actions()`.

### Testing Strategy

**Review action tests:**
- Mock `get_template()` → return test `ReviewTemplate`
- Mock `run_review_with_profile()` → return canned `ReviewResult` with structured findings
- Mock `ModelResolver.resolve()` → return known `(model_id, profile)` tuples
- Mock file persistence → verify called with correct args, no real disk I/O
- Test scenarios: happy path, template not found, model resolution failure, review execution error, persistence failure (non-fatal), verdict mapping for each severity

**Checkpoint action tests:**
- No external mocks needed beyond `ActionContext` construction
- Test each trigger × verdict combination:
  - `always` + any verdict → fires
  - `never` + any verdict → skips
  - `on-concerns` + PASS → skips
  - `on-concerns` + CONCERNS → fires
  - `on-concerns` + FAIL → fires
  - `on-fail` + PASS → skips
  - `on-fail` + CONCERNS → skips
  - `on-fail` + FAIL → fires
- Test missing prior review verdict → skips (except `always`)
- Test invalid trigger value in validate
- Test default trigger (on-concerns when not specified)
