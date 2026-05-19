---
docType: review
layer: project
reviewType: tasks
slice: optional-dependency-split-serve-and-codex-extras
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/tasks/907-tasks.optional-dependency-split-serve-and-codex-extras.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260518
dateUpdated: 20260518
findings:
  - id: F001
    severity: fail
    category: completeness
    summary: "Success Criterion 10 (CI install command update) has no corresponding task"
    location: unverified
  - id: F002
    severity: concern
    category: test-coverage
    summary: "No test task for the new codex binary guard behavior"
    location: src/squadron/providers/codex/provider.py
  - id: F003
    severity: concern
    category: completeness
    summary: "SC6 partially verified — `--stop` not tested without `[serve]`"
    location: unverified
  - id: F004
    severity: concern
    category: completeness
    summary: "SC7 partially verified — `sq run` and `sq review` not tested without `[serve]`"
    location: unverified
  - id: F005
    severity: note
    category: commit-strategy
    summary: "Single commit checkpoint batches all changes"
    location: unverified
---

# Review: tasks — slice 907

**Verdict:** FAIL
**Model:** z-ai/glm-5.1

## Findings

### [FAIL] Success Criterion 10 (CI install command update) has no corresponding task

Success criterion 10 explicitly states: "CI install command updated to include `[serve]` (and `[dev]`)." No task in the breakdown touches any CI configuration file (e.g., `.github/workflows/*.yml`). The "Files touched" list in the task doc also omits CI config files. This is a hard gap — without updating CI, the pipeline will install the base package only and any CI job that runs `sq serve` or imports server modules will break. A task must be added to update the CI install command(s) to include `[serve]` and `[dev]`.

---

### [CONCERN] No test task for the new codex binary guard behavior

T5.2 adds a new code path in `CodexProvider.create_agent()` that raises `ProviderError` when `resolve_codex_binary()` returns `None`. However, T5.3 only runs *existing* codex tests (`pytest tests/providers/ -v -k codex`), which would have the binary present and thus never exercise the new guard. The test-with pattern requires a new test (likely a mock/monkeypatch of `resolve_codex_binary` returning `None`) that verifies `ProviderError` is raised with the `npm i -g @openai/codex` hint. Without this, the new code path is untested.

---

### [CONCERN] SC6 partially verified — `--stop` not tested without `[serve]`

Success criterion 6 requires both `sq serve --status` **and** `sq serve --stop` to work without `[serve]` installed. T7.6 only verifies `--status`. There is no task verifying `sq serve --stop` in a clean (no-serve) venv. While the implementation should make both work (they import from `pid.py`), the slice design's data flow diagram explicitly lists `--stop` as a path that "reads PID file only → works without [serve]", and this should be verified.

---

### [CONCERN] SC7 partially verified — `sq run` and `sq review` not tested without `[serve]`

Success criterion 7 requires `sq doctor`, `sq run`, and `sq review` to all work without `[serve]` installed. T7.4 only verifies `sq doctor`. There are no verification tasks for `sq run` or `sq review` in the clean venv. Adding two quick manual checks (T7.4a for `sq run --help`, T7.4b for `sq review --help`) would close this gap.

---

### [NOTE] Single commit checkpoint batches all changes

The only commit (T8) stages everything at the end. For a slice of this size (~6 source files + 1 test file), a single commit is borderline acceptable, but splitting into at least two commits — one for the `pid.py` extraction (pure refactor, no behavior change) and one for the guards + `pyproject.toml` changes — would make bisection easier if regressions appear. Not blocking, but worth considering.
