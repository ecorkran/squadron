---
docType: review
layer: project
reviewType: code
slice: sq-skills-uninstall-and-sq-doctor-integration
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/343-slice.sq-skills-uninstall-and-sq-doctor-integration.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260716
dateUpdated: 20260716
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Receipt write failure logging"
    location: src/squadron/skills/installer.py:65-67
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Proper exception handling in uninstall CLI"
    location: src/squadron/cli/commands/skills.py:84-88
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Graceful handling of missing files during uninstall"
    location: src/squadron/cli/commands/skills.py:93-98
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Receipt persistence layer design"
    location: src/squadron/skills/receipts.py
  - id: F005
    severity: pass
    category: uncategorized
    summary: "InstallReceipt model at correct boundary"
    location: src/squadron/skills/models.py:47-52
  - id: F006
    severity: pass
    category: uncategorized
    summary: "SurfaceType enum follows project convention"
    location: src/squadron/skills/models.py:8-12
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Idempotent receipt overwriting"
    location: src/squadron/skills/receipts.py:26-27
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Tests use proper isolation"
    location: tests/skills/test_installer.py:11-18
  - id: F009
    severity: pass
    category: uncategorized
    summary: "Doctor check integration is additive"
    location: src/squadron/cli/commands/doctor_checks.py:433
  - id: F010
    severity: pass
    category: uncategorized
    summary: "check_skill_packs follows existing patterns"
    location: src/squadron/cli/commands/doctor_checks.py:235-287
  - id: F011
    severity: pass
    category: uncategorized
    summary: "Test for check_skill_packs no manifest case"
    location: tests/cli/test_doctor_checks.py:312-317
---

# Review: code — slice 343

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Receipt write failure logging

The `_write_install_receipt` function logs receipt write failures at WARNING level, which is appropriate since the install itself succeeded and files are in place. The `exc_info=True` parameter ensures stack traces are included for debugging. This follows the pattern documented in the function's docstring.

### [PASS] Proper exception handling in uninstall CLI

The `uninstall` command properly catches `ValueError` from `read_receipt()` and exits with code 1 when the receipt is malformed. This is an explicit, handled failure case that provides user feedback. Follows the CLAUDE.md rule: handle specific exceptions with appropriate responses.

### [PASS] Graceful handling of missing files during uninstall

The uninstall logic uses `target.unlink(missing_ok=True)` and tracks removal counts, allowing idempotent uninstallation even when files have been manually deleted. This is explicitly tested in `test_uninstall_idempotent_when_file_already_gone`. The output accurately reports `0 file(s) removed` when all files are already gone.

### [PASS] Receipt persistence layer design

New file with clean separation of concerns:
- `write_receipt` creates the receipts directory if needed (`mkdir(parents=True, exist_ok=True)`)
- `read_receipt` returns `None` for missing files (not an error) but raises `ValueError` for malformed TOML
- Uses `tomllib` for reading and `tomli_w` for writing (appropriate TOML library pairing)
- Small, single-responsibility module (~52 lines)

### [PASS] InstallReceipt model at correct boundary

`InstallReceipt` is defined in `models.py` (internal data) rather than `receipts.py` (persistence), correctly placing the Pydantic model as the internal representation. The persistence layer (`receipts.py`) handles serialization/deserialization to/from TOML.

### [PASS] SurfaceType enum follows project convention

`SurfaceType` uses `StrEnum` (Python 3.11+) per project conventions. The enum values (`PREFIX`, `DISPATCH_FILE`) match the two surface forms from `PackEntry`.

### [PASS] Idempotent receipt overwriting

The docstring explicitly states "Overwrites any existing receipt for the pack (reinstall is idempotent)" and `write_receipt` uses direct file write (not checking existence first). This is the correct behavior for reinstall scenarios.

### [PASS] Tests use proper isolation

The `_isolate_receipts` autouse fixture redirects `DEFAULT_RECEIPTS_DIR` to a temp directory, preventing test pollution of the user's actual config directory. This is a critical pattern for tests that touch filesystem state.

### [PASS] Doctor check integration is additive

The skill packs check is integrated into `run_all_checks()` without modifying existing check behavior. The new `SECTION_SKILLS` is placed between `SECTION_INTEGRATIONS` and `SECTION_CONFIG` as shown in the reordered `_SECTION_ORDER` list.

### [PASS] check_skill_packs follows existing patterns

- Returns `list[CheckResult]` (matches other check functions that handle multiple entries)
- Uses `CheckStatus.WARN` for uninstalled packs (informational, not blocking)
- `required=False` on all results
- Results sorted by name before returning for deterministic output
- No manifest found returns `OK` status with informative detail

### [PASS] Test for check_skill_packs no manifest case

Monkeypatches `load_effective` to return `None`, verifying the graceful handling of missing manifest. This directly tests the edge case documented in the function's docstring.
