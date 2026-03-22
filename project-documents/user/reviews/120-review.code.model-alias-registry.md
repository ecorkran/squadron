---
docType: review
reviewType: code
slice: model-alias-registry
project: squadron
verdict: CONCERNS
dateCreated: 20260321
dateUpdated: 20260321
---

# Review: code — slice 120

**Verdict:** CONCERNS
**Model:** claude-haiku-4-5-20251001

## Findings

### [CONCERN] File Size Exceeds Guideline

**File:** `src/squadron/cli/commands/review.py` (735 lines)

The CLAUDE.md guideline specifies "Keep source files to ~300 lines." This file is 2.4x over the limit. The file contains multiple command handlers and helper functions that could be split into logical modules (e.g., `review_cli.py`, `review_helpers.py`, `review_output.py`).

Affected sections:
- Lines 449-517: `review_slice()` command
- Lines 570-641: `review_tasks()` command  
- Lines 645-721: `review_code()` command
- Lines 127-168: `_format_review_markdown()` helper (template handling)
- Lines 173-196: `_save_review_file()` helper (file I/O)

### [CONCERN] Multiple Functions Exceed 50-Line Guideline

**File:** `src/squadron/cli/commands/review.py`

CLAUDE.md specifies functions should be ~50 lines. Several functions exceed this:
- Line 450: `review_slice()` (66 lines)
- Line 570: `review_tasks()` (71 lines)
- Line 645: `review_code()` (75 lines)
- Line 355: `_run_review_command()` (69 lines)
- Line 267: `_resolve_slice_number()` (52 lines)

**File:** `src/squadron/review/review_client.py`
- Line 133: `_inject_file_contents()` (62 lines)

### [CONCERN] Weak Type Annotations for Callable Parameters

**File:** `src/squadron/review/review_client.py`

Lines 217-221: The `add_fn` parameter is typed as `object`:
```python
def _inject_glob_files(
    pattern: str,
    cwd: str,
    add_fn: object,  # ← Should be Callable[[str, str], bool]
) -> None:
```

This weakens type safety. The parameter is used as a callable on line 237 with `type: ignore[operator]` suppression, which suggests the type is incorrect. Should be:
```python
from collections.abc import Callable
add_fn: Callable[[str, str], bool],
```

Similarly, line 90 in `review_client.py` uses `type: ignore[arg-type]` for AsyncOpenAI instantiation:
```python
client = AsyncOpenAI(**client_kwargs)  # type: ignore[arg-type]
```

The specific reason should be documented or the type hints should be corrected.

### [CONCERN] Fragile Error Detection via String Matching

**File:** `src/squadron/cli/commands/review.py`, lines 408-416

Error handling relies on matching "rate_limit" in the lowercased error message:
```python
except Exception as exc:
    err_str = str(exc).lower()
    if "rate_limit" in err_str:
```

This is fragile and may miss legitimate rate-limit errors or produce false positives. Should either:
1. Catch specific exception types (e.g., `RateLimitError`)
2. Check exception attributes if available
3. Document why this approach is necessary

### [CONCERN] Silent Fallback in Model Resolution

**File:** `src/squadron/models/aliases.py`, lines 39-52

The `load_user_aliases()` function returns an empty dict when the config file is missing or malformed:
```python
except (tomllib.TOMLDecodeError, OSError) as exc:
    _logger.warning(...)
    return {}
```

While this prevents crashes, it silently accepts invalid configuration. Consider whether missing configuration should be an explicit error in certain contexts (e.g., if the user explicitly tried to load custom aliases).

### [PASS] Error Handling is Explicit

**File:** `src/squadron/review/review_client.py`, lines 77-81

Good explicit error with clear message when model is unspecified:
```python
if resolved_model is None:
    raise ValueError(
        f"No model specified for non-SDK profile '{profile}'. "
        "Use --model or set model in the template."
    )
```

Similarly strong validation in `src/squadron/cli/commands/review.py` lines 380-386.

### [PASS] No Credentials in Source Code

Verified across all reviewed files:
- API keys loaded from environment variables via `ApiKeyStrategy` (review_client.py)
- No hardcoded secrets in comments or code
- Proper use of `profile.api_key_env` for environment variable lookup

### [PASS] Comprehensive Test Coverage

**Files:** `tests/models/test_aliases.py`, `tests/cli/test_model_list.py`, `tests/review/test_cli_review.py`

Strong patterns observed:
- Edge cases covered (missing files, malformed TOML, null values)
- Mocking used appropriately with `@patch()` and `AsyncMock`
- CLI testing via `CliRunner` and stdout assertion
- Error paths tested (exit codes, failures)
- Tests are focused and readable with clear docstrings

Example: `test_aliases.py` lines 60-72 properly test override behavior with temporary files.

### [PASS] Semantic Naming and Code Clarity

- Functions use clear names: `resolve_model_alias()`, `_inject_file_contents()`, `_run_git_diff()`
- Private functions use `_` prefix consistently
- Variable names are descriptive: `resolved_model`, `client_kwargs`, `injections`
- Constants properly named: `_MAX_FILE_SIZE`, `_REVIEWS_DIR`

### [PASS] Appropriate Use of Type Hints

Most code uses proper type hints:
- `dict[str, ModelAlias]` (generic types)
- `str | None` (union types)  
- Return type annotations on all public functions
- `from __future__ import annotations` for forward compatibility

### [PASS] Meaningful Docstrings

All public functions have docstrings explaining purpose and behavior:
```python
def resolve_model_alias(name: str) -> tuple[str, str | None]:
    """Resolve a model alias to (full_model_id, profile_or_none).
    
    If the name matches a known alias (built-in or user), returns the
    alias's (model, profile). If not, returns (name, None)...
    """
```

### [PASS] Logical Code Organization

- Imports organized and necessary
- Related functions grouped (model resolution functions, output display functions)
- Clear separation of concerns (CLI commands, core logic, I/O)

---
