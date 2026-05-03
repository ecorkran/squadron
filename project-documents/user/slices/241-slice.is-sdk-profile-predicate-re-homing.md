---
docType: slice-design
parent: 240-slices.pipeline-auth-boundary-flexibility.md
project: squadron
sliceIndex: 241
slice: is-sdk-profile-predicate-re-homing
dateCreated: 20260501
dateUpdated: 20260503
status: complete
---

# Slice 241: `is_sdk_profile` Predicate Re-Homing

## Parent Documents
- Slice plan: [240-slices.pipeline-auth-boundary-flexibility.md](../architecture/240-slices.pipeline-auth-boundary-flexibility.md)
- Architecture: [240-arch.pipeline-auth-boundary-flexibility.md](../architecture/240-arch.pipeline-auth-boundary-flexibility.md)

---

## Summary

Promote `is_sdk_profile()` from its current location at [pipeline/summary_oneshot.py:19-24](../../src/squadron/pipeline/summary_oneshot.py#L19-L24) to a canonical home in `providers/profiles.py`, alongside `get_profile()` where profile semantics already live. Document the contract, update the two production importers and the one test file, delete the old definition. Mechanical refactor; foundation for the rest of the 240-band initiative because every subsequent slice (242 dispatch router, 243 pre-scan, 244 conditional session, 245 mid-run construction, 248 test matrix) depends on a single, owned predicate.

---

## Motivation

The predicate currently lives in `pipeline/summary_oneshot.py` because slice 164 (Profile-Aware Summary Model Routing) was the first caller and that file was the natural home at the time. Subsequent callers — slice 170 (dispatch renderer) — already reach across the package boundary to import it from there. The 240-band initiative will add several more callers (dispatch router, pre-scan, classification report, diagnostics CLI), at which point "the SDK-profile predicate lives in the summary module" stops being defensible.

The architecture document promotes the predicate to `providers/profiles.py` with an explicit contract (see [240-arch §`is_sdk_profile()` predicate — ownership and contract](../architecture/240-arch.pipeline-auth-boundary-flexibility.md)). This slice executes that promotion.

---

## Scope

In scope:
- New `is_sdk_profile()` definition in `providers/profiles.py`.
- Update 2 production importers and 1 test importer to the new home.
- Delete the old definition from `pipeline/summary_oneshot.py`.
- Update `__all__` of both modules.
- Add unit tests for the predicate at the new home (parametric coverage of `None`, `"sdk"`, every other registered `ProfileName` value, and unknown strings).

Out of scope:
- No behavior change. The predicate's return value for any given input is identical before and after.
- No new callers (the dispatch router branch is slice 242's work).
- No change to `capture_summary_via_profile()` — it stays in `summary_oneshot.py` because it's about summary execution, not profile semantics.
- No changes to the existing branch logic in [prompt_renderer.py](../../src/squadron/pipeline/prompt_renderer.py) or [actions/summary.py](../../src/squadron/pipeline/actions/summary.py) beyond the import statement.

---

## Design

### Canonical Home: `providers/profiles.py`

Add the predicate directly below `get_profile()` in [providers/profiles.py](../../src/squadron/providers/profiles.py). The function is a pure read against the profile name enum — it lives next to `get_profile`, `get_all_profiles`, and the built-in profile dict, all of which are the existing canonical surface for profile semantics.

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

Add `"is_sdk_profile"` to the module's `__all__` (or add an `__all__` if absent).

### Contract (matches arch §`is_sdk_profile()` predicate, iteration 3)

| Input | Output | Rationale |
|---|---|---|
| `None` | `True` | Sentinel: "no profile specified — fall back to the SDK session's default model." Existing call sites in [prompt_renderer.py:155-159](../../src/squadron/pipeline/prompt_renderer.py#L155-L159) and [actions/summary.py:220](../../src/squadron/pipeline/actions/summary.py#L220) rely on this — the renderer sets `profile = None` on resolver failure to keep the SDK in-session path; the summary action treats absence-of-`summary_model_alias` as "use the session default." Predicate preserves this semantics. |
| `"sdk"` | `True` | Routes through `ClaudeSDKAgent` provider (`provider == "sdk"` in profiles registry). |
| Any other registered profile (`"openrouter"`, `"openai"`, `"gemini"`, `"local"`, `"openai_oauth"`) | `False` | Routes through a non-SDK provider. |
| Any unknown string | `False` | Conservative: unknown profiles do not route through SDK. |

**Classification-layer note (forward reference to slice 243).** The predicate's `None` → `True` semantics serve the existing renderer / summary call sites only. The pre-scan slice (243) operates on resolved profiles produced by `ModelResolver.resolve()` for configured pipeline steps; pipelines whose steps have no model configuration are misconfigured and the classification layer fails fast rather than calling the predicate with `None`. Raw-literal-model-id input (e.g. `--param model=gpt-4o` with no alias) is not a supported workflow — squadron's model surface is alias-driven. This isolation means the `None` → `True` sentinel and the per-step classification model are not in conflict.

The predicate **does not** call `get_profile()`. It reads the enum value directly, which means:
- Side-effect free (no logging, no config read, no I/O).
- Returns `False` for unknown profile strings rather than raising — matching the predicate's role as a routing classifier, not a validator.
- Callers that need profile validation must call `get_profile()` separately and handle the `KeyError`.

### Old Definition: Removal

Delete `is_sdk_profile()` from [pipeline/summary_oneshot.py](../../src/squadron/pipeline/summary_oneshot.py). Update its `__all__` from `["is_sdk_profile", "capture_summary_via_profile"]` to `["capture_summary_via_profile"]`. The module docstring mentions the predicate; update the docstring to drop the reference.

No re-export shim. The 240-band slices following this one all import from the new home; updating the existing 3 callers (2 production + 1 test) at the same time is a single PR's worth of work, and a re-export would only delay the cleanup.

### Caller Updates

Three files import `is_sdk_profile` today. All three change in this slice.

**Production:**
1. [src/squadron/pipeline/prompt_renderer.py:23](../../src/squadron/pipeline/prompt_renderer.py#L23) — change `from squadron.pipeline.summary_oneshot import is_sdk_profile` to `from squadron.providers.profiles import is_sdk_profile`. The other import on the line (`capture_summary_via_profile`) is not present here; this is a single-name import. Two call sites at line 159 and line 312 are unchanged.
2. [src/squadron/pipeline/actions/summary.py:10-13](../../src/squadron/pipeline/actions/summary.py#L10-L13) — currently a multi-name import:
   ```python
   from squadron.pipeline.summary_oneshot import (
       capture_summary_via_profile,
       is_sdk_profile,
   )
   ```
   Split into two: keep `capture_summary_via_profile` from `summary_oneshot`, move `is_sdk_profile` to a new `from squadron.providers.profiles import is_sdk_profile` line. Four call sites at lines 209, 220, 239, 248 unchanged.

**Tests:**
3. [tests/pipeline/test_summary_oneshot.py:11-13](../../tests/pipeline/test_summary_oneshot.py#L11-L13) — currently imports both names from `summary_oneshot`. Split: keep `capture_summary_via_profile` import; move the `is_sdk_profile` import to the new home. The existing `test_is_sdk_profile` parametric test (test_summary_oneshot.py:35) is **moved** to a new `tests/providers/test_profiles.py` file alongside any other profile-module tests. (If `tests/providers/` doesn't exist, create it with an `__init__.py`.)

### Test Coverage at the New Home

Create `tests/providers/test_profiles.py` (or extend it if it exists) with parametric coverage for `is_sdk_profile`:

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

This is functionally a relocation of [tests/pipeline/test_summary_oneshot.py:18-36](../../tests/pipeline/test_summary_oneshot.py#L18-L36) with broader coverage of the registered `ProfileName` values. The original test in `test_summary_oneshot.py` is removed.

---

## Migration Plan

This is a refactoring slice. The migration is mechanical and atomic — single PR, single commit possible.

| Step | File | Action |
|---|---|---|
| 1 | `src/squadron/providers/profiles.py` | Add `is_sdk_profile()` definition; update `__all__`. |
| 2 | `tests/providers/test_profiles.py` | Create file with parametric `test_is_sdk_profile`. Add `__init__.py` to `tests/providers/` if missing. |
| 3 | `src/squadron/pipeline/prompt_renderer.py` | Change import line 23. |
| 4 | `src/squadron/pipeline/actions/summary.py` | Split multi-name import; new line for `is_sdk_profile` from `providers.profiles`. |
| 5 | `tests/pipeline/test_summary_oneshot.py` | Remove `is_sdk_profile` from import; remove `test_is_sdk_profile` test. |
| 6 | `src/squadron/pipeline/summary_oneshot.py` | Delete `is_sdk_profile()` function and its 6-line docstring; update `__all__`; update module docstring to drop the predicate reference. |

Verification:
- `ruff format` and `ruff check` pass.
- `pyright` passes (the predicate's signature is identical, callers see no type change).
- Full test suite passes — both relocated test and unchanged callers continue to work.
- `grep -rn "from squadron.pipeline.summary_oneshot import is_sdk_profile" src/ tests/` returns zero hits.
- `grep -rn "from squadron.providers.profiles import is_sdk_profile" src/ tests/` returns 2 hits in src + 1 hit in tests.

---

## Component Interactions

```
Before:                                After:
                                       
pipeline/summary_oneshot.py            providers/profiles.py
  ├── is_sdk_profile()      ◄──┐         ├── get_profile()
  └── capture_summary_       │         ├── get_all_profiles()
       via_profile()         │         └── is_sdk_profile()    ◄──┐
                             │                                     │
imports:                     │       imports:                      │
  prompt_renderer.py ────────┤         prompt_renderer.py ─────────┤
  actions/summary.py ────────┘         actions/summary.py ─────────┤
                                       (and future 240-band ─────  ┘
                                        slices: 242, 243, 244, 246)
                                       
                                       pipeline/summary_oneshot.py
                                         └── capture_summary_
                                              via_profile()
                                              (still imported by
                                               actions/summary.py
                                               and summary_run.py)
```

No runtime data flow change. The function is pure and stateless; relocating it does not affect any caller's behavior.

---

## Cross-Slice Dependencies

**Depends on:**
- Slice 164 (complete) — original predicate location.
- Slice 170 (complete) — added the prompt_renderer importer that this slice updates.

**Enables:**
- Slice 242 (Profile-Aware Dispatch Router) — imports the predicate at its new home.
- Slice 243 (Resolution Pre-Scan) — imports the predicate for per-step classification.
- Slice 244 (Conditional Persistent Session) — imports for pipeline-level classification.
- Slice 245 (Pool-Resolution Classification Policy) — imports for pool-uncertain handling.
- Slice 246 (Auth-Classification Diagnostics CLI) — imports for the diagnostic surface.
- Slice 248 (Adversarial Test Matrix) — imports for test fixtures.

Coordination note: any 240-band slice that imports the predicate must wait for this slice to merge first, otherwise the import will need to be rewritten when 241 lands.

---

## Success Criteria

- [ ] `is_sdk_profile()` is defined in `src/squadron/providers/profiles.py` with the documented contract docstring.
- [ ] `is_sdk_profile()` is no longer defined in `src/squadron/pipeline/summary_oneshot.py`.
- [ ] `summary_oneshot.py:__all__` no longer lists `is_sdk_profile`; module docstring no longer references it.
- [ ] [prompt_renderer.py](../../src/squadron/pipeline/prompt_renderer.py) imports `is_sdk_profile` from `providers.profiles`; both call sites work unchanged.
- [ ] [actions/summary.py](../../src/squadron/pipeline/actions/summary.py) imports `is_sdk_profile` from `providers.profiles`; all four call sites work unchanged.
- [ ] [test_summary_oneshot.py](../../tests/pipeline/test_summary_oneshot.py) no longer imports or tests `is_sdk_profile`.
- [ ] `tests/providers/test_profiles.py` exists and contains parametric coverage of `is_sdk_profile` over all registered `ProfileName` values plus `None` and unknown strings.
- [ ] `grep -rn "from squadron.pipeline.summary_oneshot import is_sdk_profile" src/ tests/` returns zero matches.
- [ ] Full test suite passes (`pytest`).
- [ ] `ruff format && ruff check && pyright` pass clean.
- [ ] Behavior of every existing caller is identical to before the slice.

---

## Verification Walkthrough

This is the demo script — what a reviewer can run after the slice lands to prove it delivers what it claims.

> **Verified 20260503 against commit 393af52** (`refactor: promote is_sdk_profile predicate to providers/profiles`). All commands below were executed; observed output matches the documented expectations.

### Step 1: Confirm the new home

```bash
# Predicate lives at the canonical home with the documented contract.
grep -A 12 "def is_sdk_profile" src/squadron/providers/profiles.py
```

Expect: function definition with the contract docstring covering `None`, `"sdk"`, and "every other registered profile."

### Step 2: Confirm the old home is gone

```bash
# Old definition removed from summary_oneshot.py.
grep -n "is_sdk_profile" src/squadron/pipeline/summary_oneshot.py
```

Expect: zero matches.

### Step 3: Confirm callers updated

```bash
# Production callers import from the new home.
grep -rn "from squadron.providers.profiles import is_sdk_profile" src/
# Expect 2 hits: prompt_renderer.py and actions/summary.py

# Old import path is gone.
grep -rn "from squadron.pipeline.summary_oneshot import is_sdk_profile" src/ tests/
# Expect zero hits.
```

### Step 4: Confirm test coverage moved

```bash
# Test is at the new location.
grep -n "test_is_sdk_profile" tests/providers/test_profiles.py
# Expect 1 hit.

# Test is gone from the old location.
grep -n "test_is_sdk_profile" tests/pipeline/test_summary_oneshot.py
# Expect zero hits.
```

### Step 5: Behavior unchanged — exercise existing callers

```bash
# Run the summary-action test suite (exercises is_sdk_profile via summary action).
pytest tests/pipeline/actions/test_summary.py -v

# Run the prompt-renderer test suite (exercises is_sdk_profile via render branch).
pytest tests/pipeline/test_dispatch_render.py -v

# Run the relocated predicate test directly.
pytest tests/providers/test_profiles.py -v
```

Expect: all green. No test changes besides the relocation.

### Step 6: End-to-end smoke (optional, manual)

```bash
# Behavior unchanged: a non-SDK summary still routes through the
# one-shot path; an SDK summary still routes through the session.
# Easiest signal: render a summary step in prompt-only mode with a
# non-SDK model and confirm the rendered command is identical to
# pre-slice output.
sq run --prompt-only --next <some-pipeline-with-summary-step> --param model=minimax
```

Expect: identical rendered output to before the slice (the rendering branch reads the same predicate; only the import path changed).

### Step 7: Quality gates

```bash
ruff format --check
ruff check
pyright
pytest
```

Expect: all clean.

---

## Effort

1/5 — mechanical refactor across 6 files, no behavior change, no design risk.

---

## Risks

Low. The single risk worth naming: a stale 240-band branch that already imports `is_sdk_profile` from the old location will need its import path updated. Mitigation: this slice merges first; subsequent 240-band slices import from the new home from the start.
