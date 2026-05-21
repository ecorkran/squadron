---
docType: review
layer: project
reviewType: slice
slice: sq-setup-one-call-install-orchestrator
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/908-slice.sq-setup-one-call-install-orchestrator.md
aiModel: z-ai/glm-5
status: complete
dateCreated: 20260519
dateUpdated: 20260519
findings:
  - id: F001
    severity: fail
    category: scope-creep
    summary: "New feature scoped under maintenance architecture"
    location: 908-slice.sq-setup-one-call-install-orchestrator.md
  - id: F002
    severity: pass
    category: dependencies
    summary: "Dependency direction is correct"
    location: 908-slice.sq-setup-one-call-install-orchestrator.md#Dependencies
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes are comprehensively enumerated"
    location: 908-slice.sq-setup-one-call-install-orchestrator.md#Failure-mode-enumeration
  - id: F004
    severity: pass
    category: interfaces
    summary: "Integration points are well-defined"
    location: 908-slice.sq-setup-one-call-install-orchestrator.md#Interfaces-required
  - id: F005
    severity: note
    category: documentation
    summary: "Parent field correctly references slice plan, not architecture"
    location: 908-slice.sq-setup-one-call-install-orchestrator.md:4
---

# Review: slice — slice 908

**Verdict:** FAIL
**Model:** z-ai/glm-5

## Findings

### [FAIL] New feature scoped under maintenance architecture

The slice introduces a new user-facing command (`sq setup`) and a new bootstrap script (`install.sh`), which constitutes a new capability—not maintenance or refactoring work. The parent architecture document (900-arch.maintenance-and-refactoring.md) explicitly states under "Work that does **not** belong here: New features or capabilities (use the appropriate feature initiative)." This slice should be scoped under a feature initiative, not the maintenance architecture. The slice's own "Value" section confirms it delivers new user capabilities: a guided install path, one-liner for evaluators, and new command interface.

### [PASS] Dependency direction is correct

The slice correctly consumes from slice 905 (`run_all_checks()`, `CheckResult`, `CheckStatus`) without requiring API changes to its dependencies. It treats `sq doctor` as a stable contract and implements a renderer over its data, which aligns with proper layer separation.

### [PASS] Failure modes are comprehensively enumerated

The document provides explicit handling strategies for all relevant failure modes including: user marking done but check still missing (re-prompt with cap at 5), `run_all_checks` raising (catch, log, exit 3), invalid profile name (exit 64), and partial `install.sh` completion (idempotent re-run). No "TBD" or implicit handling—each case has a concrete strategy.

### [PASS] Integration points are well-defined

The slice clearly specifies the interfaces it requires from slice 905 (`run_all_checks()`, `CheckResult`, `CheckStatus`) and what it provides to downstream consumers (README pointer, QUICKSTART troubleshooting reference). The contract is explicit and versioned by slice number.

### [NOTE] Parent field correctly references slice plan, not architecture

The `parent` field references `user/architecture/900-slices.maintenance-and-refactoring.md`, which is the slice plan document (as expected per the reviewer instructions). This is correct behavior and not flagged as an error.
