---
docType: slice-design
slice: design-phase-judge-templates
project: squadron
parent: 300-slices.eval-actions-llm-as-judge-scoring.md
dependencies: [301]
interfaces: [303, 304]
dateCreated: 20260705
dateUpdated: 20260714
status: complete
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

## Non-Functional Requirements

The architecture states four qualitative NFR targets for the judge path. This
slice introduces no new enforcement logic, so the targets are inherited from
slices 300 and 301; the two new templates and two new `TEMPLATE_INPUTS` entries
are the only additions. Each target is restated explicitly here with its
confirmation for this slice's paths.

| NFR | Architecture Target | Confirmation for This Slice |
|-----|--------------------|-----------------------------|
| **Conservative gating** | Default thresholds gate toward escalation when uncertain; a pass floor that cannot be cleared under doubt is preferred to one that silently auto-passes | `judge.slice-vs-arch` uses `pass_floor=82` (higher than `tasks-vs-slice`'s 78) because arch-alignment judgment is more interpretive; both floors are set conservatively, not generously, per the "bubble up the hard calls" principle |
| **No silent pass** | No failure mode may silently yield a passing result; every unobserved failure must surface as `UNKNOWN` or a score-derived verdict | Confirmed via the failure-mode table: all five enumerated failure modes (including the two new to this slice) terminate in `UNKNOWN` or a threshold-derived verdict — never a model-asserted pass that bypasses score gating |
| **Observability** | Non-passing outcomes are logged at `WARNING` or above so a checkpoint never advances on an unobserved failure | All `UNKNOWN` outcomes route through `enforce_judge()` (slice 301), which logs at `WARNING+`; this slice introduces no new exception paths that bypass that logging |
| **Score-with-rationale** | The judge prompt requires the model to justify each criterion's number before emitting it, which empirically reduces anchoring | Both templates implement this: the `## Rationale` block requires a per-criterion justification immediately before the value; the model cannot emit a number without stating a reason |

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
3. Running `judge.slice-vs-arch` via `run_review_with_profile()` directly (or
   via a `review` pipeline step naming that template) with a real
   slice-design/architecture pair produces a `ReviewResult` with a non-`None`
   score, and the resulting `ActionResult.verdict` is the threshold-derived
   value (not a parsed verdict) with `provenance == "judge"`. Same for
   `judge.tasks-vs-slice` with a task-file/slice-design pair. **Note:** `sq
   review`'s CLI subcommands (`slice`/`arch`/`tasks`/`code`) are each pinned to
   their own template name and have no path to invoke an arbitrary template —
   judge templates are reachable today only via the pipeline `review` step or
   direct API/internal use, not via a new `sq review` CLI subcommand (out of
   scope for this slice).
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
  - The two failure modes new to this slice (see Risk Assessment's failure-mode
    table): a judge `ReviewResult` with a non-`UNKNOWN` parsed `verdict` still
    yields a threshold-derived `ActionResult.verdict` (rogue verdict is
    discarded); a `SliceInfo` missing a field a judge template's
    `TEMPLATE_INPUTS` entry needs results in `ActionResult(verdict="UNKNOWN")`
    via the existing required-input `KeyError` path, not a silent skip.
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

# 3. End-to-end judge run against a real artifact pair (requires provider access).
# No `sq review` CLI subcommand exists for arbitrary template names (its four
# subcommands are each pinned to one template) — invoke directly via Python,
# or via a pipeline `review` step with `template: judge.slice-vs-arch`.
# (Environment-specific profile constraints: see Implementation Notes →
# Environment-Specific Notes.)
set -a && source .env && set +a
uv run python - <<'PY'
import asyncio
from squadron.review.templates import load_all_templates, get_template
from squadron.review.review_client import run_review_with_profile

async def main() -> None:
    load_all_templates()
    template = get_template("judge.slice-vs-arch")
    assert template is not None
    result = await run_review_with_profile(
        template,
        {
            "input": "project-documents/user/slices/302-slice.design-phase-judge-templates.md",
            "against": "project-documents/user/architecture/300-arch.eval-actions-llm-as-judge-scoring.md",
            "cwd": ".",
        },
        profile="openrouter",
        model="anthropic/claude-opus-4.5",
    )
    print(f"score={result.score} verdict={result.verdict} criteria={result.criteria}")

asyncio.run(main())
PY
# Expected: a non-None score, criteria map, findings, and no model-emitted
# verdict summary in raw_output (verdict prints UNKNOWN because none was
# parsed — expected, ignored by enforce_judge downstream).
#
# Actual (T9/T10, run 20260705): judge.tasks-vs-slice scored 91.0 against this
# slice's own task file vs. its slice design; judge.slice-vs-arch scored 86.0
# against this slice's design vs. its architecture doc. Both runs produced a
# criteria map, findings in the `### [SEVERITY] Title` / `location:` shape,
# and no `## Summary` or verdict line in raw_output. No prompt revision was
# required for either template. The slice-vs-arch score (86, clears
# pass_floor=82) is consistent with the design's already-addressed review
# findings (the committed 302-review.slice... CONCERNS verdict predates the
# d69ee7e fixes to failure-mode enumeration and no-silent-pass restatement).

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

### Failure Modes on the Judge Template Path

The architecture requires every enumerated failure mode to map to a named,
non-passing, logged outcome (Technical Considerations, "Failure modes and
their verdict mapping"). This slice introduces two new I/O paths (the
score-with-rationale prompt shape) and two new registry lookups
(`TEMPLATE_INPUTS`), but adds **no new handling code** — every case below
routes through infrastructure slice 301 or slice 300 already built and tested.
Enumerated here so the mapping is explicit for these specific paths, not
implicitly assumed:

| Failure mode | Where it's introduced | Handling | Verdict |
|---|---|---|---|
| LLM call times out / provider unavailable | Not new — inherent to any `review` action call | `ReviewAction.execute()`'s exception handler (301), judge-aware via template re-lookup | `UNKNOWN`, WARNING+ log |
| `score:` absent or outside 0–100 | Not new — parser (300) + enforcement (301) are prompt-shape-agnostic | `enforce_judge()` (301) | `UNKNOWN`, WARNING log |
| Model emits a verdict summary despite the prompt forbidding it | **New to this slice** — the prompt's no-verdict instruction is this slice's addition | `enforce_judge()` (301) never reads `result.verdict`; a rogue verdict is parsed but discarded, never surfacing on `ActionResult` | Threshold-derived verdict (score wins) |
| `TEMPLATE_INPUTS` resolution fails (e.g. `SliceInfo` missing `arch_file`/`design_file`) | **New to this slice** — new registry entries, new failure surface | Unresolved key stays absent from `inputs`; `ReviewAction._review()`'s existing required-input check raises `KeyError`, caught by `execute()`'s judge-aware exception handler | `UNKNOWN`, WARNING log |
| `## Rationale`/`criteria:` block malformed or partial | Not new — `_extract_criteria` (300) already returns `None` (never a partial map) on any malformed entry | Enforcement only requires `score`; a `None` criteria map does not block verdict derivation | Verdict derived from `score` alone; `criteria` absent from result |

**No silent pass**: every row above terminates in either `UNKNOWN` (via 301's
existing enforcement/exception paths) or a score-derived verdict — never a
verdict the judge template's own output could produce independently. This
restates the architecture's no-silent-pass NFR for this slice's specific
paths; the guarantee's *mechanism* is unchanged from slice 301, this slice
only confirms it holds for the two new templates and the two new registry
lookups.

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

### Environment-Specific Notes

When running Verification Walkthrough Step 3 from within an interactive Claude
Code session: `profile="sdk"` shells out to the Claude Code CLI, which refuses
to launch from inside another Claude Code session. Use `profile="openrouter"`
with an explicit model instead (the built-in templates' `model: opus` field is
an SDK-profile alias that does not resolve under openrouter). Also `source .env`
first — `sq`'s CLI loads provider API keys from `.env` automatically; a bare
`uv run python` script does not. This is an environmental constraint, not an
architectural requirement; any profile other than `sdk` works in a non-nested
context.
