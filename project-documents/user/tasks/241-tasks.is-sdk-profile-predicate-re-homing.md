---
docType: tasks
slice: is-sdk-profile-predicate-re-homing
sliceIndex: 241
project: squadron
lldReference: user/slices/241-slice.is-sdk-profile-predicate-re-homing.md
dependencies:
  - slice 164 (complete) — original predicate location
  - slice 170 (complete) — added prompt_renderer importer
status: complete
dateCreated: 20260502
dateUpdated: 20260503
---

# Tasks: Slice 241 — `is_sdk_profile` Predicate Re-Homing

## Context

Mechanical refactor: move `is_sdk_profile()` from `pipeline/summary_oneshot.py` (its
slice-164 birthplace) to `providers/profiles.py` (canonical home for profile semantics).
6 files change; no behavior change; no new callers. Foundation for all 240-band slices.

Files touched:
- `src/squadron/providers/profiles.py` — add predicate + update `__all__`
- `tests/providers/test_profiles.py` — add parametric test
- `src/squadron/pipeline/prompt_renderer.py` — update import line 23
- `src/squadron/pipeline/actions/summary.py` — split multi-name import
- `tests/pipeline/test_summary_oneshot.py` — remove predicate import + test
- `src/squadron/pipeline/summary_oneshot.py` — delete definition + update `__all__` + update docstring

---

## Tasks

### T1: Add `is_sdk_profile()` to `providers/profiles.py`

- [x] Open `src/squadron/providers/profiles.py`
- [x] Add `is_sdk_profile()` after `get_profile()` (currently ends at line 128):
  ```python
  def is_sdk_profile(profile: str | None) -> bool:
      """Return True iff the profile routes through the Claude Code SDK session.

      Pure function of the profiles registry. Returns True for the 'sdk'
      profile name and for None (sentinel meaning "no profile specified —
      fall back to the SDK session's default model"; preserves the
      existing renderer / summary semantics). Returns False for every
      other registered profile (openrouter, openai, gemini, local,
      openai_oauth) and for unknown profile strings.

      Does not probe the Claude CLI, check authentication, or read
      config. Callers needing auth checks must do so separately. The
      classification layer (slice 243 pre-scan) operates only on
      resolved profiles and does not pass None to this predicate.
      """
      return profile is None or profile == ProfileName.SDK
  ```
- [x] Confirm `ProfileName` is already imported in the module (it is — used by `BUILT_IN_PROFILES`); no new import needed
- [x] Add or update `__all__` in `providers/profiles.py` to include `"is_sdk_profile"`

### T2: Test `is_sdk_profile()` at the new home

- [x] Confirm `tests/providers/` directory exists; create it if absent
- [x] Confirm `tests/providers/__init__.py` exists; create it (empty) if absent
- [x] Confirm `tests/providers/test_profiles.py` exists; create it if absent (it already exists as of task authoring — this check guards against unexpected state)
- [x] Add parametric test (append after existing tests):
  ```python
  @pytest.mark.parametrize(
      "profile,expected",
      [
          (None, True),
          ("sdk", True),
          ("openrouter", False),
          ("openai", False),
          ("openai_oauth", False),
          ("gemini", False),
          ("local", False),
          ("unknown-profile", False),
          ("", False),
      ],
  )
  def test_is_sdk_profile(profile: str | None, expected: bool) -> None:
      assert is_sdk_profile(profile) is expected
  ```
- [x] Add `from squadron.providers.profiles import is_sdk_profile` to the import block of `test_profiles.py`
- [x] Run `pytest tests/providers/test_profiles.py -v` — confirm all parametric cases pass

### T3: Update `prompt_renderer.py` import

- [x] Open `src/squadron/pipeline/prompt_renderer.py`
- [x] Change line 23 from:
  `from squadron.pipeline.summary_oneshot import is_sdk_profile`
  to:
  `from squadron.providers.profiles import is_sdk_profile`
- [x] Confirm the two call sites (lines 159 and 312) are unchanged
- [x] Run `pytest tests/pipeline/test_dispatch_render.py -v` — confirm all tests pass

### T4: Update `actions/summary.py` import

- [x] Open `src/squadron/pipeline/actions/summary.py`
- [x] Locate the multi-name import block (lines 10–13):
  ```python
  from squadron.pipeline.summary_oneshot import (
      capture_summary_via_profile,
      is_sdk_profile,
  )
  ```
- [x] Split into two separate imports:
  ```python
  from squadron.pipeline.summary_oneshot import capture_summary_via_profile
  from squadron.providers.profiles import is_sdk_profile
  ```
- [x] Confirm the four call sites (lines 209, 220, 239, 248) are unchanged
- [x] Run `pytest tests/pipeline/actions/test_summary.py -v` — confirm all tests pass

### T5: Remove `is_sdk_profile` from `test_summary_oneshot.py`

- [x] Open `tests/pipeline/test_summary_oneshot.py`
- [x] Remove `is_sdk_profile` from the import block (lines 11–13); keep `capture_summary_via_profile`
- [x] Delete the `test_is_sdk_profile` parametric test and its `@pytest.mark.parametrize` decorator (currently at lines 18–36)
- [x] Run `pytest tests/pipeline/test_summary_oneshot.py -v` — confirm remaining tests pass

### T6: Delete `is_sdk_profile()` from `summary_oneshot.py`

- [x] Open `src/squadron/pipeline/summary_oneshot.py`
- [x] Delete the `is_sdk_profile()` function definition (lines 19–24 including docstring)
- [x] Update `__all__` from `["is_sdk_profile", "capture_summary_via_profile"]` to `["capture_summary_via_profile"]`
- [x] Update the module docstring to remove the reference to `is_sdk_profile()` (currently in the first paragraph)

### T7: Verify grep sentinel conditions

- [x] Run: `grep -rn "from squadron.pipeline.summary_oneshot import is_sdk_profile" src/ tests/`
  - [x] Confirm zero matches
- [x] Run: `grep -rn "from squadron.providers.profiles import is_sdk_profile" src/ tests/`
  - [x] Confirm exactly 2 hits in `src/` (`prompt_renderer.py`, `actions/summary.py`) and 1 hit in `tests/` (`test_profiles.py`)
- [x] Run: `grep -n "is_sdk_profile" src/squadron/pipeline/summary_oneshot.py`
  - [x] Confirm zero matches

### T8: Quality gates

- [x] Run `ruff format src/ tests/` — confirm no formatting issues
- [x] Run `ruff check src/ tests/` — confirm zero lint errors
- [x] Run `pyright` — confirm zero type errors
- [x] Run `pytest` — confirm full suite passes (1763+ tests)

### T9: Commit

- [x] Stage all changed files (6 confirmed; 7 if `tests/providers/__init__.py` was created in T2):
  - `src/squadron/providers/profiles.py`
  - `tests/providers/test_profiles.py`
  - `tests/providers/__init__.py` (only if created in T2)
  - `src/squadron/pipeline/prompt_renderer.py`
  - `src/squadron/pipeline/actions/summary.py`
  - `tests/pipeline/test_summary_oneshot.py`
  - `src/squadron/pipeline/summary_oneshot.py`
- [x] Commit with message: `refactor: promote is_sdk_profile predicate to providers/profiles`

### T10: Slice closeout

- [x] Mark slice 241 `status: complete` in `user/slices/241-slice.is-sdk-profile-predicate-re-homing.md`
- [x] Mark slice 241 entry `[x]` in `user/architecture/240-slices.pipeline-auth-boundary-flexibility.md`
- [x] Write DEVLOG entry for Phase 6 completion
