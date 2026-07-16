---
docType: review
layer: project
reviewType: code
slice: manifest-format-and-sq-skills-install-list
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/341-slice.manifest-format-and-sq-skills-install-list.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260716
dateUpdated: 20260716
findings:
  - id: F001
    severity: concern
    category: code-style
    summary: "Missing `from __future__ import annotations` in test file"
    location: tests/skills/test_cli_skills.py:1
  - id: F002
    severity: concern
    category: resource-management
    summary: "Resource leak in `clone_github` on exception path"
    location: src/squadron/skills/resolver.py:64-66
  - id: F003
    severity: concern
    category: performance
    summary: "Unused `Console` instance created per command invocation"
    location: src/squadron/cli/commands/skills.py:100
  - id: F004
    severity: note
    category: error-handling
    summary: "Silent exception handling in `_detect_origin` is justified by context"
    location: src/squadron/cli/commands/skills.py:120-130
  - id: F005
    severity: pass
    category: error-handling
    summary: "Consistent error handling pattern across CLI commands"
    location: src/squadron/cli/commands/skills.py
  - id: F006
    severity: pass
    category: testing
    summary: "Well-structured test coverage"
    location: tests/skills/
  - id: F007
    severity: pass
    category: code-design
    summary: "Proper use of Pydantic for manifest validation"
    location: src/squadron/skills/models.py
  - id: F008
    severity: pass
    category: code-design
    summary: "Clean separation of concerns in skills module"
    location: src/squadron/skills/
---

# Review: code — slice 341

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Missing `from __future__ import annotations` in test file

The file is missing the `from __future__ import annotations` import. All other source and test files in this change set include it for Python 3.12/3.13 compatibility with forward references.

```python
# Should be added after the docstring:
from __future__ import annotations
```

---

### [CONCERN] Resource leak in `clone_github` on exception path

If `subprocess.run` succeeds but something fails afterward (before the return statement), the `TemporaryDirectory` created on line 64 would leak. The function creates a `TemporaryDirectory` that is only cleaned up via explicit `tmp.cleanup()` on failure, but the successful return path passes the `tmp` object directly to the caller.

Consider using a context manager pattern or wrapping the return with `try/finally` to guarantee cleanup on any exception between tmp creation and successful return:

```python
tmp = tempfile.TemporaryDirectory(prefix="squadron-skills-")
try:
    result = subprocess.run(["git", "clone", "--depth=1", url, tmp.name], capture_output=True)
    if result.returncode != 0:
        tmp.cleanup()
        stderr = result.stderr.decode(errors="replace").strip()
        raise SkillSourceError(...)
    return tmp
except Exception:
    tmp.cleanup()
    raise
```

---

### [CONCERN] Unused `Console` instance created per command invocation

Each call to `list_packs` creates a new `Console()` instance. While the `rich.table.Table` is the primary output mechanism and doesn't require an explicit console, this instantiation is unnecessary overhead. Consider either passing `Console().print()` to the table, or importing `console = Console()` at module level if terminal detection is needed.

---

### [NOTE] Silent exception handling in `_detect_origin` is justified by context

The silent catching of `(ValueError, OSError)` in `_detect_origin()` is defensible here because:
1. It's best-effort display metadata only
2. The main code path via `load_effective()` would surface any manifest parse errors earlier

However, document this explicitly in a code comment to prevent future developers from "fixing" the error handling by adding `logger.exception` or changing behavior:

```python
# Best-effort: silent failures here because load_effective() already 
# validated manifest files on the primary code path
```

---

### [PASS] Consistent error handling pattern across CLI commands

The CLI commands properly handle errors with specific exception types (`ValueError`, `SkillSourceError`) and exit with appropriate error codes. Error messages to users are actionable.

---

### [PASS] Well-structured test coverage

The test files follow the project's testing patterns:
- Tests are written alongside implementation
- Uses `pytest.raises` for error cases
- Tests use temporary directories for isolation
- Network-dependent tests are marked with `@pytest.mark.network`

---

### [PASS] Proper use of Pydantic for manifest validation

The `PackEntry` model uses a `model_validator` to enforce the constraint that exactly one of `prefix` or `dispatch_file` must be set. This is a clean validation approach that provides clear error messages to users.

---

### [PASS] Clean separation of concerns in skills module

The module is well-organized:
- `models.py`: Data models (`PackEntry`, `InstallResult`, `SkillSourceError`)
- `manifest.py`: TOML loading and merging logic
- `resolver.py`: Source resolution (bundled, local, github)
- `installer.py`: File installation orchestration

This follows the Single Responsibility Principle with clear boundaries between components.
