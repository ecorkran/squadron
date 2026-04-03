---
docType: review
layer: project
reviewType: code
slice: pipeline-definitions-and-loader
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/148-slice.pipeline-definitions-and-loader.md
aiModel: gemini-3-flash-preview
status: complete
dateCreated: 20260403
dateUpdated: 20260403
---

# Review: code — slice 148

**Verdict:** CONCERNS
**Model:** gemini-3-flash-preview

## Findings

### [CONCERN] Redundant parameters and imports in `loader.py`

In `src/squadron/pipeline/loader.py`, the private helper functions `_validate_model_alias` (line 217) and `_validate_review_template` (line 244) take function/object references as arguments (e.g., `resolver`, `get_template_fn`) which are then ignored in favor of local imports within the same functions. For example:

```python
# line 223
def _validate_model_alias(..., resolver: object) -> None:
    ...
    from squadron.models.aliases import resolve_model_alias
    _model_id, profile = resolve_model_alias(alias)  # Uses local import, ignores 'resolver'
```

This redundancy should be cleaned up by either using the passed arguments or removing them from the signature.

### [CONCERN] Shallow placeholder validation in `_validate_param_placeholders`

In `src/squadron/pipeline/loader.py` (line 284), the `_validate_param_placeholders` function only iterates over top-level keys in `step.config` and checks for string values:

```python
for key, value in step.config.items():
    if not isinstance(value, str):
        continue
    for match in placeholder_re.finditer(value):
        ...
```

This logic will fail to detect undeclared parameter placeholders if they are nested within dictionaries or lists (e.g., `review: { template: "{my_tpl}" }`). While current built-in pipelines are largely flat, the validator should ideally be recursive or specifically target known nested fields that support placeholders to ensure semantic correctness.

### [PASS] Robust Pydantic schema and shorthand expansion

The `PipelineSchema` in `src/squadron/pipeline/schema.py` effectively uses Pydantic v2's `@model_validator(mode="before")` to transform the terse YAML step grammar (single-key mappings and scalar shorthands) into a structured internal model. The `to_definition()` method correctly maps these to the project's existing dataclasses while handling auto-generation of step names (e.g., `design-0`).

### [PASS] Comprehensive Test Coverage

The PR follows the "test-with" pattern, providing unit tests for the schema, loading logic, and semantic validation, as well as integration tests for all four new built-in pipelines. The test suite correctly uses `Path("/nonexistent")` to isolate built-in loading tests from the local filesystem environment.

### [PASS] Project Convention Adherence

The changes correctly update `CHANGELOG.md`, `DEVLOG.md`, and the architectural slice documentation. The code follows the project's style for dynamic registration of step types and handles errors without swallowing them, raising appropriate `FileNotFoundError` or `pydantic.ValidationError` exceptions.
