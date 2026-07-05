---
docType: slice-design
slice: design-phase-judge-templates
project: squadron
parent: 300-slices.eval-actions-llm-as-judge-scoring.md
dependencies: [301]
interfaces: [303, 304]
dateCreated: 20260705
dateUpdated: 20260705
status: not_started
---

# Slice Design: Design-Phase Judge Templates

## Overview

This slice authors the first real judge templates: judge-flavored variants of the
existing `slice` and `tasks` review templates that emit a **score + findings**
instead of a verdict. They run on the unmodified `review` action and are
identified as judges purely by the `judge:` YAML block the enforcement layer
(slice 301) already recognizes — no engine change.

Slice 301 built the enforcement contract with a synthetic minimal template in
tests. This slice is the first time that contract is exercised by a template
whose system prompt, ground truth, and evaluation criteria are real — the point
at which "a judge is a review template with a judge system prompt" (architecture,
Current State) stops being a claim and becomes two working templates.

## Value

**User/developer value.** After this slice, a pipeline step (or the `sq review`
CLI) can run `template: judge.slice-vs-arch` or `template: judge.tasks-vs-slice`
and receive a numeric score, a threshold-derived verdict, and findings — the
first working judges in the system. This unblocks slice 303 (judge-gated cycle
conventions), which needs a real judge to compose into a pipeline.

## Technical Scope

### What changes

1. **Two new built-in template YAML files** in `src/squadron/data/templates/`:
   - `judge-slice-vs-arch.yaml` (`name: judge.slice-vs-arch`) — judge variant of
     `slice.yaml`; scores a slice design against its architecture/HLD.
   - `judge-tasks-vs-slice.yaml` (`name: judge.tasks-vs-slice`) — judge variant of
     `tasks.yaml`; scores a task breakdown against its parent slice design.

   Each carries a `judge:` block with template-level default thresholds and a
   system prompt that requires **score + rationale + findings**, and explicitly
   forbids emitting a verdict summary.

2. **`review/template_inputs.py`** — two new `TEMPLATE_INPUTS` registry entries,
   `"judge.slice-vs-arch"` and `"judge.tasks-vs-slice"`, reusing the existing
   `_design_file`/`_arch_file`/`_tasks_input` source functions unchanged. This is
   the one required code change: the registry is keyed by exact template name,
   and a judge template is a distinct name from its standard counterpart, so
   `sq review slice 154` auto-input-resolution (and the pipeline step's
   `slice:` shorthand) needs its own entries to work for judge templates.

### What does NOT change

- The `review` action, the enforcement layer (`judge.py`), the parser, or the
  pipeline step schema — all consume the new templates exactly as they consume
  any other template, per the architecture's "no engine change" commitment.
- The existing `slice` / `tasks` templates — untouched; the judge templates are
  new files, not edits to the standard ones.
- `resolve_thresholds` / `enforce_judge` — this slice only supplies the `judge:`
  block values the resolver already knows how to merge (slice 301).

### Explicitly out of scope

- Judge-gated cycle conventions (`each`/`loop`/`commit` composition) — slice 303.
- Gate composition (judge + review verdict combination) — slice 304.
- Multi-sample judging (fan-out + median) — Future Work 1.
- Any judge template beyond the two design-phase gates named in the slice plan
  (`slice-vs-arch`, `tasks-vs-slice`). Additional judges (e.g. `code`, `arch`)
  are a straightforward repeat of this pattern but are not authored here.

## Dependencies

### Prerequisites
- **Slice 301 (complete):** `ReviewTemplate.judge` field / `is_judge` property;
  `enforce_judge()`, `resolve_thresholds()`, `Provenance` — the enforcement
  contract this slice's templates plug into with no further changes.

### Interfaces Required
- `ReviewTemplate.judge: dict[str, object] | None` — the field this slice's YAML
  populates (`pass_floor`, `concerns_floor` keys).
- `load_all_templates()` — discovers built-in templates from
  `src/squadron/data/templates/*.yaml` by glob; the two new files need no
  registration code, only correct placement.
- `TEMPLATE_INPUTS` registry (`review/template_inputs.py`) — the dict this slice
  adds two entries to.
- The parser's existing `_extract_score` / `_extract_criteria` (slice 300) — a
  lenient top-level `score:` line and optional `criteria:` block; this slice's
  prompt is written to produce exactly that shape, no parser change needed.

## Architecture

### Component Structure

| File | Change |
|------|--------|
| `src/squadron/data/templates/judge-slice-vs-arch.yaml` (new) | Judge template: slice-design vs. architecture |
| `src/squadron/data/templates/judge-tasks-vs-slice.yaml` (new) | Judge template: task breakdown vs. slice design |
| `src/squadron/review/template_inputs.py` | Two new `TEMPLATE_INPUTS` entries |

No other module changes. Both templates run through the unmodified path:
`ReviewAction._review()` → `run_review_with_profile()` → parser → `enforce_judge()`.

### Data Flow

```
Pipeline step or CLI (template: judge.slice-vs-arch, slice: 154)
    │
    ▼
ReviewAction._review()
    │  load_all_templates() → get_template("judge.slice-vs-arch")
    │  template.is_judge == True (judge: block present)
    │  slice param present → resolve_template_inputs("judge.slice-vs-arch", info, cwd, inputs)
    │      → inputs["input"]  = design_file from SliceInfo
    │      → inputs["against"] = arch_file from SliceInfo
    │
    ▼
run_review_with_profile(template, inputs, ...)
    │  system_prompt instructs: read input + against, emit score + rationale +
    │  findings, do NOT emit a verdict summary
    │
    ▼
raw_output (markdown):
    score: 82
    criteria:
      alignment: 85
      scope: 80
    ## Findings
    ### [CONCERN] ...
    │
    ▼
Parser (slice 300, unchanged): _extract_score, _extract_criteria, findings
    → ReviewResult(score=82.0, criteria={...}, verdict=UNKNOWN, findings=[...])
      (verdict is UNKNOWN because no ## Summary is emitted — expected; ignored
       by enforce_judge per the one-directional-from-score commitment)
    │
    ▼
enforce_judge(result, thresholds, "judge.slice-vs-arch", logger)   [slice 301]
    → thresholds from template.judge (this slice) + any step override
    → score=82 ≥ pass_floor(78) → ("PASS", "judge")
    │
    ▼
ActionResult(verdict="PASS", score=82.0, criteria={...}, provenance="judge", ...)
```

### Score-with-Rationale Prompt Shape

The architecture requires "a score-with-rationale prompt shape (require the
model to justify the number) to reduce anchoring." Both templates implement
this the same way: the system prompt requires the model to state, per
criterion, a short justification immediately before its numeric value, then
roll the criteria into the top-level `score:`. This reuses the existing
`criteria:` block (slice 300 parser) as the structured carrier — no new field.

```
## Rationale
- alignment (85): the slice restates the NFR from the architecture doc
  verbatim and the data flow matches the parent's component diagram.
- scope (80): one section (Risk Assessment) exceeds what the architecture
  calls for, but the core scope is bounded correctly.

score: 82
criteria:
  alignment: 85
  scope: 80

## Findings

### [CONCERN] Risk Assessment section is speculative
location: 302-slice.design-phase-judge-templates.md#risk-assessment
...
```

The `## Rationale` heading is prose scaffolding for the model, not a new parser
target — only `score:`, `criteria:`, and the existing finding blocks are parsed.
This keeps the parser judging-unaware (slice 300's committed layering) while
still requiring the model to justify each number before emitting it.

## Technical Decisions

### Template naming: `judge.{comparison}` — human-readable, not a dispatch signal

Templates are named `judge.slice-vs-arch` and `judge.tasks-vs-slice`, matching
the architecture's own example (`template: judge.slice-vs-arch`, Technical
Considerations). This name is **never** read as a logical signal anywhere in
the engine — `ReviewTemplate.is_judge` (the `judge:` block's presence) is the
only dispatch signal, per the project rule against user-accessible labels as
logical structure and per slice 301's own precedent. The `judge.` prefix exists
so a human reading a pipeline YAML or `sq review list` output can tell what a
step does; it carries no runtime meaning.

### Reuse existing evaluation criteria, don't re-derive them

Each judge template's evaluation-criteria list (what to check for) is the same
list already proven in `slice.yaml` / `tasks.yaml` — alignment with parent
scope, dependency direction, sequencing, NFR restatement, etc. Only the output
contract changes (score+rationale+findings instead of verdict+findings). This
avoids drift between what a human-reviewed `slice` template checks and what its
judge counterpart checks — the two should agree on *what* good looks like and
differ only in *how the result is expressed*.

### Judge system prompt forbids a verdict summary

The prompt explicitly instructs the model not to emit a `## Summary` /
PASS|CONCERNS|FAIL line. This is belt-and-suspenders with slice 301's
enforcement (`enforce_judge` already ignores `result.verdict` unconditionally),
but keeping the model from emitting a verdict at all avoids a raw_output that
contains two conflicting judgments (a verdict a human skimming the persisted
review file could mistake for authoritative, next to the actual authoritative
score-derived one).

### Conservative default thresholds, differentiated by ground-truth strength

Per the architecture's "bubble up the hard calls" principle, the two templates'
`judge:` defaults are **not** identical:

| Template | Ground truth strength | `pass_floor` | `concerns_floor` |
|---|---|---|---|
| `judge.tasks-vs-slice` | Strong (slice design is concrete, cross-referenceable) | 78 | 55 |
| `judge.slice-vs-arch` | Moderate (architecture intent is more interpretive) | 82 | 60 |

`judge.slice-vs-arch` gets a higher floor (harder to auto-pass) because
judging alignment to an architecture document involves more interpretive
judgment than cross-referencing a task list against concrete success criteria
— consistent with the architecture's instruction that weak-ground-truth judges
should be configured toward escalation. Both remain overridable per step via
the existing `resolve_thresholds` step-override mechanism (slice 301); a
pipeline can raise or lower either floor without touching the template file.

### `TEMPLATE_INPUTS` registry entries duplicate their standard counterpart's sources

`judge.slice-vs-arch` reuses `_design_file`/`_arch_file`; `judge.tasks-vs-slice`
reuses `_tasks_input`/`_design_file` — the exact functions `slice` and `tasks`
already use. Alternative considered: make the registry lookup fall back from
`judge.X` to `X` by stripping the prefix. Rejected — that reintroduces a
naming-convention dependency (exactly what "template naming... not a dispatch
signal" above forbids) into a second module. Two explicit dict entries costs
four lines and keeps every dispatch in the codebase keyed off data
(`is_judge`) or an explicit registry, never a string pattern.

## Integration Points

### Provides to Other Slices

- **Two working judge templates** — slice 303 needs a real judge to compose
  into an `each`/`loop`/`commit` pipeline; this slice is what makes that
  possible.
- **The score-with-rationale prompt pattern** — a template for authoring any
  future judge template (e.g. `judge.code`, `judge.arch`) by the same recipe:
  copy the standard template's criteria, swap the output contract, add a
  `judge:` block, add a `TEMPLATE_INPUTS` entry.

### Consumes from Other Slices

- **Slice 301**: `judge:` block parsing, `is_judge`, `enforce_judge`,
  `resolve_thresholds` — consumed as-is, no changes requested back.
- **Slice 300**: the parser's `_extract_score` / `_extract_criteria` — consumed
  as-is; this slice's prompt is written to fit the parser's existing lenient
  contract rather than asking the parser to change.

## Success Criteria

### Functional Requirements

1. `judge.slice-vs-arch` and `judge.tasks-vs-slice` templates load via
   `load_all_templates()` with `is_judge == True` and non-`None`
   `pass_floor`/`concerns_floor` in their `judge:` block.
2. Each template's system prompt instructs the model to emit `score:` +
   `criteria:` + findings, and explicitly instructs it not to emit a verdict
   summary.
3. Running `sq review slice-vs-arch <artifact> <against>` (or the equivalent
   `judge.slice-vs-arch` invocation) with a real slice-design/architecture pair
   produces a `ReviewResult` with a non-`None` score, and the resulting
   `ActionResult.verdict` is the threshold-derived value (not a parsed verdict)
   with `provenance == "judge"`. Same for `judge.tasks-vs-slice` with a
   task-file/slice-design pair.
4. A pipeline `review` step with `slice: <n>` and `template: judge.slice-vs-arch`
   (or `judge.tasks-vs-slice`) auto-resolves `input`/`against` via
   `TEMPLATE_INPUTS`, matching the existing behavior for `slice`/`tasks`.
5. Each template's default thresholds differ per the ground-truth-strength
   rationale above, and each is overridable via a step-level `judge:` dict
   (slice 301 mechanism, unchanged).

### Technical Requirements

- New template YAML files pass the existing `load_template` validation
  (`TemplateValidationError` on malformed YAML — this is existing engine
  behavior, not new for this slice).
- New unit tests (or extensions of existing ones) cover:
  - Both new templates load with `is_judge == True` and the expected default
    thresholds.
  - `TEMPLATE_INPUTS` resolves `input`/`against` correctly for both new
    template names given a `SliceInfo`.
- No changes to `pyright` strict / `ruff` status — new YAML files are data,
  not typed code; the one Python change (`template_inputs.py`) passes the
  same strict gates as the rest of the module.

### Integration Requirements

- Slice 303 can select either judge template by name in a `review` step with
  no further template authoring for the design-phase gates.
- `sq review list` (or equivalent template-listing surface) shows both new
  templates alongside the existing four.

### Verification Walkthrough

```bash
# 1. Both judge templates load with correct is_judge / thresholds
uv run python - <<'PY'
from squadron.review.templates import load_all_templates, get_template

load_all_templates()
for name, expected_pass, expected_concerns in [
    ("judge.slice-vs-arch", 82.0, 60.0),
    ("judge.tasks-vs-slice", 78.0, 55.0),
]:
    t = get_template(name)
    assert t is not None, f"{name} not found"
    assert t.is_judge, f"{name}: expected is_judge=True"
    assert t.judge is not None
    assert float(t.judge["pass_floor"]) == expected_pass
    assert float(t.judge["concerns_floor"]) == expected_concerns
print("PASS: both judge templates load with correct is_judge/thresholds")
PY

# 2. TEMPLATE_INPUTS resolves input/against for both judge template names
uv run python - <<'PY'
from squadron.review.template_inputs import resolve_template_inputs
from squadron.review.persistence import SliceInfo

info: SliceInfo = {
    "index": 302, "slice_name": "design-phase-judge-templates",
    "design_file": "project-documents/user/slices/302-slice.design-phase-judge-templates.md",
    "task_files": ["302-tasks.design-phase-judge-templates.md"],
    "arch_file": "project-documents/user/architecture/300-arch.eval-actions-llm-as-judge-scoring.md",
}
inputs: dict[str, str] = {}
resolve_template_inputs("judge.slice-vs-arch", info, ".", inputs)
assert inputs["input"] == info["design_file"]
assert inputs["against"] == info["arch_file"]

inputs2: dict[str, str] = {}
resolve_template_inputs("judge.tasks-vs-slice", info, ".", inputs2)
assert inputs2["input"] == "project-documents/user/tasks/302-tasks.design-phase-judge-templates.md"
assert inputs2["against"] == info["design_file"]
print("PASS: TEMPLATE_INPUTS resolves both judge template names correctly")
PY

# 3. End-to-end judge run against a real artifact pair (requires provider access)
sq review slice-vs-arch \
  project-documents/user/slices/302-slice.design-phase-judge-templates.md \
  project-documents/user/architecture/300-arch.eval-actions-llm-as-judge-scoring.md \
  --template judge.slice-vs-arch
# Expected: persisted review file with `score:` and `criteria:` frontmatter,
# a derived verdict (PASS/CONCERNS/FAIL/UNKNOWN), and findings — no model-emitted
# verdict line in the raw output.

# 4. Full regression + static analysis
uv run pytest
uv run pyright
uv run ruff check && uv run ruff format --check
```

> Step 3's exact CLI invocation shape (positional args vs. flags) should be
> confirmed against the current `sq review` CLI surface during implementation;
> the walkthrough's intent — run a judge template against a real artifact pair
> and inspect the persisted output — is the fixed part.

## Risk Assessment

### Technical Risks

- **Prompt quality is unverifiable until a real provider run happens.** Unlike
  slice 301 (pure logic, fully unit-testable), whether the score-with-rationale
  shape actually reduces anchoring, and whether the model reliably omits a
  verdict summary, can only be observed against a live provider. Unit tests
  cover template loading and input resolution; they cannot cover prompt
  quality.

### Mitigation Strategies

- Task breakdown should include at least one live-provider verification run
  per template (not just mocked `run_review_with_profile` tests), matching how
  slice 301 flagged its own enforcement-vs-mock gap. Treat the first few real
  runs' scores as data for tuning the prompt, not as a one-shot final draft.

## Implementation Notes

### Development Approach

Suggested order:

1. Author `judge-tasks-vs-slice.yaml` first (stronger ground truth, simpler
   criteria list to adapt from `tasks.yaml`). Verify `is_judge`/thresholds load
   correctly.
2. Author `judge-slice-vs-arch.yaml` (adapt from `slice.yaml`).
3. Add both `TEMPLATE_INPUTS` entries; unit test resolution for both.
4. Run each template against a real in-repo artifact pair (e.g. this slice
   design vs. its own architecture doc) to sanity-check the prompt shape
   end-to-end before considering the slice done.

### Special Considerations

- Do not copy-paste the `## Summary` / verdict instructions from `slice.yaml` /
  `tasks.yaml` into the judge variants — the CRITICAL block about
  verdict/findings consistency in those templates is specifically about a
  *verdict* the judge templates must not emit at all.
- Keep the `judge:` block's threshold values in the YAML, not hardcoded
  anywhere in Python — `resolve_thresholds` (slice 301) already reads them from
  `template.judge`; this slice's only job is to put sensible numbers there.
