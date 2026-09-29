---
docType: slice-design
slice: pipeline-tasks-review-covers-every-split-task-file
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [195]
interfaces: []
dateCreated: 20260928
dateUpdated: 20260928
status: not_started
---

# Slice Design: Pipeline Tasks Review Covers Every Split Task File

## Overview

Fixes [issue #153](https://github.com/ecorkran/squadron/issues/153). When a slice's task breakdown is split across files (`914-tasks.name-1.md`, `-2.md`, `-3.md`), a pipeline `review:` step reviews only the first. `_tasks_input` in `src/squadron/review/template_inputs.py` returns `task_files[0]`, and `judge.tasks-vs-slice` uses the same source. The review saves unsuffixed, reports that one part's verdict, and a `skip_if_met` loop can finish with parts 2..N never read.

`sq review tasks <slice>` already reviews every part, saves each as `part-N`, and exits on the worst verdict. This slice gives the pipeline review action the same behavior and moves the pieces both callers need into one shared module so they can't drift again.

## Value

- `tasks-plan`, the `tasks` phase step, `P5`, `slice`, `example`, and any user pipeline that reviews tasks by slice now review the whole breakdown. A PASS on part 1 no longer clears a slice whose part 3 is broken.
- The revise loop gets every part's findings and is told which file each finding belongs to, so it can fix the right file.
- `sq review tasks 914` and a pipeline review of 914 write the same artifact names. The workaround in the issue (rerun the CLI, delete the unsuffixed review) goes away.
- Fixes a latent crash: `_aggregate_verdicts` in `cli/commands/review.py` indexes a rank table that has no `UNKNOWN` entry, so a split-tasks CLI review where any part parses as UNKNOWN raises `KeyError`.

## Technical Scope

**In scope**
- `template_inputs.py`: the registry can say that a key fans out across parts, and the slice resolver returns one inputs dict per part.
- New `src/squadron/review/parts.py`: part naming and worst-verdict folding, used by the CLI and the pipeline.
- `ReviewAction`: review each part, save each with its `part-N` suffix, and return one `ActionResult` carrying the worst verdict and every part's findings.
- `DispatchAction._resolve_feedback_prompt` / `_findings_block`: name every file to revise, and tag each finding with its file when the review had more than one part.
- `review_tasks` (CLI): switch to the shared helpers. Behavior stays the same except the UNKNOWN fix.
- New `src/squadron/pipeline/actions/review_outputs.py`: the review action's output and finding key names plus typed readers. The review action writes through it; dispatch and the batch report read through it.
- `pipeline/batch_report.py`: show `unsaved: <paths>` for an item whose review had parts that failed to save.

**Out of scope**
- Splitting or merging task files.
- Cleaning up unsuffixed reviews that earlier pipeline runs already wrote (for example `914-review.tasks.strict-type-checking-over-the-test-suite.md`). Delete those by hand; see Special Considerations.
- Context-forge's review gate. It reads only one tasks review per slice (see Integration Points). That fix belongs in context-forge: [context-forge#106](https://github.com/ecorkran/context-forge/issues/106).
- Running parts concurrently. Parts run one after another, the same as the CLI.

## Dependencies

### Prerequisites
- Slice 195 (complete): `tasks-plan`, `cf.untasked_slices`, `feedback: review`, loop `skip_if_met`.

### Interfaces Required
- `SliceInfo.task_files` (already ordered by `resolve_slice_info`; the CLI relies on the same order).
- `save_review_result(..., name_suffix=...)` and `save_provider_failure(..., name_suffix=...)`. Both already accept a suffix.
- `enforce_judge` / `resolve_thresholds` for judge templates, applied per part.

## Architecture

### Component Structure

```
review/parts.py              (new)  ReviewPart, review_parts(), worst_verdict()
review/template_inputs.py    (edit) per-part resolution for fan-out keys
pipeline/actions/review.py   (edit) resolve parts → run+save each → fold
pipeline/actions/dispatch.py (edit) multi-file feedback prompt
cli/commands/review.py       (edit) review_tasks uses parts.py; _aggregate_verdicts removed
pipeline/actions/review_outputs.py (new) ReviewOutputKey, FINDING_INPUT_FILE, typed readers
pipeline/batch_report.py     (edit) render unsaved parts for an item
```

**`review/parts.py`**

```python
@dataclass(frozen=True)
class ReviewPart:
    input_path: str
    name_suffix: str | None   # "part-N" when there are 2+ parts, else None

def review_parts(input_paths: list[str]) -> list[ReviewPart]: ...
def worst_verdict(verdicts: Iterable[str]) -> str: ...
```

- `review_parts` is the single place that decides the suffix: `None` for one path, `part-1..part-N` for more than one. Both callers get their artifact names from it.
- `worst_verdict` ranks `PASS < CONCERNS < FAIL < UNKNOWN` over `Verdict` values. UNKNOWN ranks worst because a part we couldn't read must not let the slice clear a gate. The pipeline passes these as strings (a judge verdict is already a string), and `Verdict` is a `StrEnum`, so the CLI passes `result.verdict` directly. An empty input raises `ValueError`, since zero parts means nothing was reviewed. The CLI's `_aggregate_verdicts` returned PASS for an empty list, which is exactly the silent failure this slice exists to remove.

**`template_inputs.py`**

`TemplateInputSpec` gains `fans_out: bool = False`. The `tasks` and `judge.tasks-vs-slice` entries set it on `input`. Their source is renamed `_task_files` and returns every path. The spec's source type becomes `Callable[[SliceInfo, str], list[str]]`: every source returns a list, empty when it has nothing. Scalar sources return one element. That gives a single signature instead of a union.

`resolve_template_input_parts(template, info, cwd, inputs) -> list[dict[str, str]]` (replaces `resolve_template_inputs`; see Migration Plan) returns one fully populated inputs dict per part. Scalar keys are copied into every dict. The one fan-out key gets one value per dict. Rules:
- If a caller already supplied a key, the caller's value still wins. An explicit `input:` means one part, as today.
- If more than one spec in an entry sets `fans_out`, the call raises `ValueError`. Only one axis can fan out, and nothing needs two.
- If the fan-out source returns nothing, the result is one dict without that key, and the existing missing-required-input `KeyError` in `ReviewAction` reports it, as today.

### Data Flow

```
ReviewAction._review(context)
  ├─ resolve template / model / profile          (unchanged)
  ├─ base inputs from params                      (unchanged)
  ├─ slice given and no explicit input?
  │     part_inputs = resolve_template_input_parts(...)  → [inputs_1 .. inputs_N]
  │   else part_inputs = [inputs]
  ├─ validate every part (required inputs, files exist) BEFORE any model call
  ├─ rules content resolved once                  (same for every part)
  ├─ parts = review_parts([p["input"] ...])       (paths → suffixes)
  ├─ for each part, in order:
  │     result = await _run_part(...)             run → judge enforce → save(name_suffix)
  │     provider failure → failure artifact in this part's slot, re-raise
  └─ _fold(part_results) → ActionResult
```

Every part is validated before the first model call. A missing part-3 file then fails the step without paying for parts 1 and 2.

**Folding into one `ActionResult`** (for a single part this is exactly what the action returns today):

| Field | Multi-part value |
|---|---|
| `verdict` | `worst_verdict` over the parts' verdicts (judge-enforced where applicable) |
| `provenance` | same for every part (template-level), taken from the first part |
| `findings` | every part's findings, in part order. Each finding dict gets an `input_file` key naming its part. |
| `score` / `criteria` | from the lowest-scoring part among the parts that have a score, first part on ties. Parts with no score are skipped. `None` only when no part has a score. |
| `outputs["unsaved_parts"]` | input paths of the parts whose save failed. Omitted when every part saved. |
| `outputs["response"]` | the parts' raw outputs joined, each under a `## <input path>` header |
| `outputs["input_files"]` / `outputs["review_files"]` | all parts, in order |
| `outputs["input_file"]` / `outputs["review_file"]` | the part with the worst verdict (first one on ties). The batch report shows the file that sank the item. |
| `metadata` | first part's model and profile values (all parts use the same ones). `tool_calls_made` is summed. |

Edge cases for the fold:
- **Verdict:** ties go to the first part in order. All UNKNOWN gives UNKNOWN. A judge part whose threshold enforcement degraded to UNKNOWN (malformed override) ranks as UNKNOWN like any other part. A value outside `Verdict` raises `ValueError` in `worst_verdict`; it doesn't default to a rank. Every producer already emits a `Verdict` value, so this only fires on a real bug.
- **Score vs. verdict:** these are chosen independently. For a judge template the verdict comes from the score, so the lowest-scoring part is also the worst-verdict part, unless a per-part threshold degraded to UNKNOWN. In that case the verdict is UNKNOWN and the score still reports the lowest real score. Both facts are true, and neither one hides the other.

The loop condition (`until`, `accept_if`, `skip_if_met`) reads `verdict` through `last_with_verdict`, so it now sees the worst part without any change to loop code.

**The output contract (`pipeline/actions/review_outputs.py`).** `ActionResult.outputs` is a `dict[str, object]` and findings are `dict[str, object]`. Today, dispatch and the batch report each spell out `"input_file"` / `"review_file"` as literals and cast whatever comes back. This slice adds three keys and a per-finding key, so those names move into one module:

```python
class ReviewOutputKey(StrEnum):
    RESPONSE = "response"
    INPUT_FILE = "input_file"
    INPUT_FILES = "input_files"
    REVIEW_FILE = "review_file"
    REVIEW_FILES = "review_files"
    UNSAVED_PARTS = "unsaved_parts"

FINDING_INPUT_FILE = "input_file"   # per-finding key naming the part it came from

def review_input_files(result: ActionResult) -> list[str]: ...  # INPUT_FILES, else [INPUT_FILE], else []
def unsaved_parts(result: ActionResult) -> list[str]: ...       # [] when absent
def finding_input_file(finding: dict[str, object]) -> str | None: ...
```

- The key values match today's literals exactly, so a single-part `ActionResult` is unchanged.
- The readers check types at the boundary. A present key whose value is the wrong type (for example `input_files` not being a `list[str]`) raises `TypeError`. It's never treated as absent, because a wrong shape here is a bug in the writer.
- `ReviewAction` builds outputs with `ReviewOutputKey` members. `DispatchAction` and `batch_report` read only through the readers, and after the change neither contains a string literal for these keys. Findings still come from `StructuredFinding.__dict__`; the review action adds `FINDING_INPUT_FILE` to multi-part findings. `StructuredFinding` itself doesn't gain a field, since it's serialized into review artifacts and single-part artifacts must stay byte-identical.

**Feedback dispatch** (`feedback: review`):
- If `review_input_files(review)` has more than one entry, the instruction becomes "Revise each of these files in place; do not create new files:" followed by the list. With one entry it keeps today's sentence.
- `_findings_block` renders `- [SEV] summary (location) — <file>` when `finding_input_file(finding)` returns a path. Single-part findings have no such key, so their prompt text is unchanged.

### State Management

No new state. Each part writes its own review artifact. A revise-loop iteration rewrites each part's artifact under the existing `revision_number`/archive path, one call per part. Run state records the one folded `ActionResult` per review action, as today.

## Technical Decisions

### Technology Choices

- **Share part naming and verdict folding, not the loop body.** The slice plan called for extracting the CLI's whole per-part loop into one helper. The loop body can't be shared cleanly. The CLI's body is synchronous and drives terminal display through `_run_review_command`. The pipeline's is async, pushes saves to threads, and applies judge enforcement. A helper that takes both would need async/sync adapters and display callbacks to share about four lines. What actually produces the parity problem in #153 is which files get reviewed, what the artifacts are called, and which verdict wins. `review_parts` decides the first two and `worst_verdict` decides the third. Both callers now depend on those.
- **The fan-out lives in the registry, not in `ReviewAction`.** Hard-coding "tasks means split" in the action would be template-name string dispatch. The registry already describes where each template's inputs come from, so it's the right place to say an input has several values.
- **Sequential parts.** Same as the CLI. It keeps the parts' artifacts and failure slots in a predictable order.

### Patterns and Conventions

- Suffix format `part-N` is unchanged (existing artifacts for 265, 305, 306, 381, 382 use it). `review_parts` becomes its only producer. `persistence.py` still only appends whatever suffix it's given.
### Failure Modes

The per-part path adds no new kind of I/O. Each part makes the same model call and the same save that a single-file review makes today, just N times in a row. Here is each failure, what it produces, and how it shows up:

| Failure on part k | Behavior | Observable signal |
|---|---|---|
| Provider error (including `ProviderTimeoutError`, which the OpenAI path raises on a client timeout) | Write a failure artifact into part k's slot, re-raise, and the step fails. Parts 1..k-1 stay saved and parts k+1..N are not run, same as the CLI. | WARNING `review: provider failed in step %s part %d/%d; failure artifact: %s`, plus the failure artifact and `success=False` |
| Model call hangs (SDK path, which has no client timeout) | Same as a single-file review today: the step waits. No new per-part timeout here. A hang is a provider-level gap, and fixing it one review action at a time would be the wrong layer. | INFO `review: step %s part %d/%d: %s` logged before each call, so a stalled run shows exactly which part it's stuck on |
| Save's git subprocess hangs | Already capped at 30s inside `resolve_reviewed_sha`, and it runs off-thread. | The existing save-failure path below |
| Save fails (write error, or an archive refusal as `OSError`) | The step does not fail, same rule as today, because the review succeeded and its verdict still counts in the fold. The part's path goes into `outputs["unsaved_parts"]`. | ERROR via `logger.exception` naming the part. The batch report lists `unsaved: <paths>` next to the item. |

An unsaved part is where silence would hurt. The step's verdict includes that part, but context-forge's gate can't see it on disk, and a stale `part-k` from an earlier run could be sitting there instead. That's why an unsaved part is a named output shown in the batch report, not just a log line. It is still not fatal: failing the step would throw away N paid reviews to report one file write, and the operator can rerun `sq review tasks <slice>` to fill the slot.

## Implementation Details

### Migration Plan

- `_aggregate_verdicts` (`cli/commands/review.py`) → replaced by `parts.worst_verdict`. `review_tasks` is its only caller.
- `review_tasks`'s inline `multi_part` / `f"part-{part_idx}"` logic → `review_parts(task_file_paths)`. Its `SaveOutcome` folding stays in the CLI, because it's CLI-specific (exit codes).
- `_tasks_input` → `_task_files` (list return). The `TEMPLATE_INPUTS` source signature changes for every entry. The only callers are the resolver (renamed below) and `tests/review/test_template_inputs.py`.
- `resolve_template_inputs` (mutates `inputs` in place, returns `None`) is replaced by `resolve_template_input_parts` (doesn't mutate, returns `list[dict[str, str]]`). The rename is on purpose. A caller that kept the old name and ignored the return value would silently lose the resolved inputs. With the old name gone, that becomes an import error and a pyright error instead. Its single production caller is `ReviewAction._resolve_slice_inputs`, which is updated here. `grep -rn resolve_template_inputs src tests` must come back empty after the change.
- **Behavior check:** the existing `tests/pipeline/actions/test_review_action*.py` and CLI review tests pass unchanged for single-file slices. The byte-for-byte check is the Success Criteria test below.

## Integration Points

### Provides to Other Slices
- `review/parts.py` is available to any future multi-input review (for example a split slice design, if that ever exists).

### Consumes from Other Slices
- **Context-forge review gate (not changed here, finding recorded).** `detectDocuments` (`context-forge/packages/core/src/introspection/parsers/documentDetector.ts`) matches `{index}-review.tasks.*.md` with `docType: review` and takes the **lexicographically last** match. Consequences:
  - With `part-1..part-N` present, the gate reads only `part-N`'s verdict, not the worst part's. That's true today for CLI-produced parts too, so this slice doesn't make it worse. The pipeline now writes the same shape the CLI already does.
  - `part-10` sorts before `part-2`. That only shows up at 10+ parts, which is rare but possible.
  - A stale unsuffixed review (`….md`) sorts before `….part-1.md` (`m` < `p`), so a leftover never wins.

  Tracked as [context-forge#106](https://github.com/ecorkran/context-forge/issues/106): the tasks gate should fold every `part-N` review for the slice into the worst verdict, with numeric part ordering. Until that lands, the pipeline's own loop gate is correct. Only a later `cf next` or a Phase 6 gate check can clear a slice whose last part passes but an earlier part fails.
- **`cf.untasked_slices`** (`pipeline/sources.py`) reads only the **slice design** review (`slice_review_stem(index, 'slice', …)`), never a tasks review. Split task reviews don't affect it.

## Success Criteria

### Functional Requirements
- A pipeline `review: { template: tasks, slice: N }` over a slice with 2+ task files makes one model call per file and writes `N-review.tasks.<name>.part-1.md` … `part-K.md`, each with `sourceDocument` naming its own file.
- The step's verdict is the worst part's: PASS + CONCERNS gives CONCERNS, so a `skip_if_met: true` loop with `until: review.pass` runs a revise round instead of logging "already met". PASS + UNKNOWN gives UNKNOWN.
- `feedback: review` after a multi-part review lists every part file to revise, and each finding names its file.
- `judge.tasks-vs-slice` fans out the same way. Its verdict is the worst judge-enforced part verdict. Its score is the lowest part score.
- A single-task-file slice produces a review artifact byte-for-byte identical to today's (unsuffixed name, same content) and an identical `ActionResult`.
- `sq review tasks N` and the pipeline write identical artifact filenames for the same slice.
- `sq review tasks N` with a part that parses UNKNOWN folds to UNKNOWN instead of raising `KeyError`, and exits on that verdict as a single-file UNKNOWN review does (exit 0 unless a save failed).

### Technical Requirements
- ruff format, ruff check, and pyright strict all clean. The full test suite passes.
- Tests:
  - `tests/review/test_parts.py`: suffixes for 1 and 3 paths, `worst_verdict` ordering including UNKNOWN, empty input raises.
  - `tests/review/test_template_inputs.py`: multi-file `tasks` yields K dicts with shared `against`. A caller-supplied `input` yields 1. Two `fans_out` specs raise.
  - `tests/pipeline/actions/test_review_action.py`: 2 task files → 2 review calls, 2 `part-N` saves, verdict PASS + CONCERNS → CONCERNS, findings tagged with `input_file`, `review_file` points at the CONCERNS part. A missing part-2 file fails before any model call. A provider failure on part 2 keeps part 1's artifact, writes the failure artifact under `part-2`, and logs the part-numbered WARNING (checked with `caplog`). A save failure on part 2 still returns the folded verdict, puts part 2's path in `outputs["unsaved_parts"]`, and logs at ERROR. The batch report renders `unsaved:` for that item. `worst_verdict` breaks ties in favor of the first part, and score is taken from the lowest part that has one while unscored parts are skipped.
  - Single-file regression: the saved artifact matches a snapshot of today's output.
  - Parity: the CLI (`review_tasks`) and the pipeline over the same fixture slice write the same set of filenames.
  - `tests/pipeline/actions/test_dispatch*.py`: the multi-file feedback prompt lists every file. The single-file prompt is unchanged.

### Integration Requirements
- `tasks-plan` over a plan containing a split-task slice reviews every part and doesn't skip the revise loop when any part is below `pass-threshold`.

### Verification Walkthrough

Use the real split slice from the issue (914, three task files):

1. Confirm the split exists:
   ```bash
   ls project-documents/user/tasks/914-tasks.*
   ```
   Expect `-1.md`, `-2.md`, `-3.md`.
2. Remove the stale unsuffixed review the old pipeline wrote, if it's still there:
   ```bash
   git rm project-documents/user/reviews/914-review.tasks.strict-type-checking-over-the-test-suite.md
   ```
3. Run a review-only pipeline. Don't use the `tasks` pipeline here, because its Phase 5 dispatch would regenerate the task files. Save this as `/tmp/review-tasks-only.yaml`:
   ```yaml
   name: review-tasks-only
   description: Review a slice's task files only
   params:
     slice: required
     review-model: glm-flash
   steps:
     - review: { template: tasks, model: "{review-model}", slice: "{slice}" }
   ```
   ```bash
   sq run /tmp/review-tasks-only.yaml 914 -v
   ```
   Expect three review calls, one per part, in order. If `sq run` doesn't accept a file path, copy the YAML into the project pipelines directory instead.
4. Check the artifacts:
   ```bash
   ls project-documents/user/reviews/914-review.tasks.*
   grep -H '^sourceDocument\|^verdict' project-documents/user/reviews/914-review.tasks.*part-*.md
   ```
   Expect `part-1`, `part-2`, `part-3`, and each `sourceDocument` should name its own `-N.md` file.
5. Parity: rerun through the CLI and compare names:
   ```bash
   sq review tasks 914 --model glm-flash
   ls project-documents/user/reviews/914-review.tasks.*
   ```
   Expect the same three filenames (the CLI run archives and overwrites them) and no new unsuffixed file.
6. Worst-verdict gating: in the run digest or state for step 3, the review step's verdict is the worst of the three parts' `verdict:` frontmatter values from step 4. If any part is below PASS, the loop log does **not** say `review.pass already met; 0 rounds run`.
7. Single-file regression: run the same review-only pipeline on a slice with one task file. The review saves as `<idx>-review.tasks.<name>.md` with no suffix, as before.

## Implementation Notes

### Development Approach
1. `review/parts.py` and its tests.
2. Switch the CLI `review_tasks` to `parts.py`, delete `_aggregate_verdicts`. The CLI tests stay green and the new UNKNOWN test passes.
3. Registry changes in `template_inputs.py` and its tests.
4. `ReviewAction`: pull the per-part run/judge/save out of `_review` into `_run_part`, add the fold, and validate every part up front. `_review` currently runs about 290 lines, and this extraction shrinks it.
5. `review_outputs.py` and its tests (reader shapes, `TypeError` on a wrong-typed value). Then move `ReviewAction`, dispatch feedback, and `batch_report` onto it. Tests for all three follow.
6. Parity test, then the verification walkthrough against 914.

Effort: 2/5.

### Special Considerations
- Existing stale unsuffixed task reviews from earlier pipeline runs stay on disk. They never win context-forge's selection (they sort before `part-1`), but they're misleading. Delete them by hand. So far only 914 is known.
