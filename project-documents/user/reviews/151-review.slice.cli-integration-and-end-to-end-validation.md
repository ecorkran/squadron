---
docType: review
layer: project
reviewType: slice
slice: cli-integration-and-end-to-end-validation
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/151-slice.cli-integration-and-end-to-end-validation.md
aiModel: claude-sonnet-4-6
status: complete
dateCreated: 20260403
dateUpdated: 20260403
---

# Review: slice — slice 151

**Verdict:** CONCERNS
**Model:** claude-sonnet-4-6

## Findings

### [PASS] Command surface matches architecture exactly

The slice implements every command variant from the architecture's Command Surface section (`sq run <pipeline>`, `--resume`, `--status [run-id]`, `--list`, `--validate <pipeline>`, `--dry-run`) and all common options (`--slice`, `--model`, `--from`). The `sq run phase` subcommand is correctly deferred to future work, matching the architecture's "TBD" treatment and the slice plan's "FUTURE" tag.

### [PASS] Layer responsibilities correctly scoped

The slice places all implementation in `src/squadron/cli/commands/run.py` and limits its role to wiring: load → validate → construct dependencies → execute → display. It does not re-implement any executor, state, or loader logic. The architecture's component diagram explicitly positions the CLI as the outermost layer that "parse args, load definition, start executor," and this design honours that boundary precisely.

### [PASS] Dependency direction is correct

All consumed interfaces flow inward from the pipeline layer to the CLI layer: `squadron.pipeline.loader` (148), `squadron.pipeline.executor` (149), `squadron.pipeline.state` (150), `squadron.pipeline.resolver` (142), and `squadron.integrations.context_forge` (126). No import cycles are introduced. The interface table is explicit and traceable to the originating slices.

### [PASS] 160-scope items correctly excluded

Weighted convergence strategies, model pools, conversation persistence, and escalation behaviours are absent. The slice explicitly calls out exclusions ("convergence strategies, model pools — 160 scope") and does not add any extension-point stubs of its own, leaving that to the layers that define them.

### [PASS] Integration point to slice 152 is well-defined

The slice cleanly provides the working `sq run` surface and example invocations to slice 152 (Documentation). This matches the slice plan's sequencing: 152 depends on all prior slices being complete, and 151 is the last feature slice before 152.

### [CONCERN] `--status` without a run-id cannot be parsed as designed

The architecture specifies `sq run --status [run-id]` with an optional run-id, and success criterion 7 requires `sq run --status` (no argument) to display the most recent run. The slice implements this as:

```python
status: str | None = typer.Option(None, "--status", ...)
```

With this Typer definition, `--status` invoked without a value will raise a parse error because Typer string options require a value when the flag is present. The "Implementation Notes" section acknowledges the desired behaviour ("Uses `StateManager.list_runs()` sorted by `started_at` descending…") but does not address the CLI parsing challenge. A workable approach — such as using a sentinel default (`"latest"`), a separate `--recent` flag, or `nargs='?'` via direct Click annotation — needs to be specified to make success criterion 7 achievable.

### [CONCERN] Model injected at both cascade level 1 and into `params` dict

The architecture defines a precise 5-level model resolution cascade; level 1 is the CLI override. The data flow shows:

```python
ModelResolver(cli_override="opus", pipeline_model=definition.model)
execute_pipeline(definition, {"slice": "191", "model": "opus"}, resolver=resolver, ...)
StateManager().init_run("slice-lifecycle", {"slice": "191", "model": "opus"})
```

Passing `model` in both `ModelResolver(cli_override=...)` (cascade level 1) and the `params` dict (which the pipeline grammar defines as a pipeline-level parameter, cascade level 4) is architecturally ambiguous. If the executor reads `params["model"]` as the pipeline default, the cascade is being populated at two levels from the same source. The design does not explain whether the executor treats `params["model"]` as a level-4 default, ignores it in favour of the resolver, or whether this is intentional redundancy purely for state-file record-keeping. A brief clarification — e.g., "model in params is recorded for resume; the resolver is authoritative for dispatch" — would prevent an implementer from inadvertently creating double-application behaviour.

### [CONCERN] Integration test scope understates slice plan's stated requirement

The slice plan (151) specifies: *"Integration testing of built-in pipelines against a real CF project structure."* The slice design delivers tests that call the async helper `_run_pipeline()` directly with mock action registries and explicitly avoids invoking the Typer CLI runner. While this is a pragmatic and fast approach, it diverges from the "real CF project structure" wording in the slice plan. If the intent was for at least one integration test to exercise CF-driven context assembly (even against a fixture project), that path is not covered. If mock registries are sufficient and the slice plan wording is informal, this should be acknowledged explicitly in the slice design to avoid a misunderstanding when reviewers compare the two documents.
