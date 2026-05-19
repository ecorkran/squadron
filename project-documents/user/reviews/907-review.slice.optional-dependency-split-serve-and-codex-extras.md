---
docType: review
layer: project
reviewType: slice
slice: optional-dependency-split-serve-and-codex-extras
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/907-slice.optional-dependency-split-serve-and-codex-extras.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260514
dateUpdated: 20260514
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Alignment with architecture scope and guidelines"
    location: 907-slice.optional-dependency-split-serve-and-codex-extras.md
  - id: F002
    severity: concern
    category: error-handling
    summary: "ProviderAuthError used for missing binary — semantic mismatch"
    location: 907-slice.optional-dependency-split-serve-and-codex-extras.md:67-75
  - id: F003
    severity: concern
    category: under-specification
    summary: "Transitive import verification left as \"verify this\" rather than resolved in design"
    location: 907-slice.optional-dependency-split-serve-and-codex-extras.md:46-50
  - id: F004
    severity: note
    category: error-handling
    summary: "Import guard message is imprecise for edge-case failures"
    location: 907-slice.optional-dependency-split-serve-and-codex-extras.md:28-35
  - id: F005
    severity: pass
    category: verification
    summary: "Migration plan and verification walkthrough are thorough"
    location: 907-slice.optional-dependency-split-serve-and-codex-extras.md
---

# Review: slice — slice 907

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [PASS] Alignment with architecture scope and guidelines

The slice falls squarely within the architecture document's stated scope for "Dependency management" and "Refactoring" (improving module boundaries). It is small, focused, and independently deliverable, matching the guidelines. No new features are introduced—only restructuring of existing dependency declarations and addition of fast-fail guards.

### [CONCERN] ProviderAuthError used for missing binary — semantic mismatch

The design raises `ProviderAuthError` when the Codex CLI binary is not found on PATH. A missing binary is a dependency/availability problem, not an authentication problem. Downstream handlers that catch `ProviderAuthError` specifically (e.g., to prompt re-login or credential refresh) will take the wrong corrective action. The existing pattern in `_run_prompt` uses `ProviderError` for the analogous missing-SDK case. The binary-absent case should raise `ProviderError` (or a new `ProviderDependencyError`) to be consistent and semantically correct.

### [CONCERN] Transitive import verification left as "verify this" rather than resolved in design

The design states that `DaemonConfig`, `is_daemon_running`, and `read_pid_file` "don't transitively import fastapi/uvicorn — verify this," with a fallback to extract them into `pid.py`. Since the entire success of `sq serve --status` / `--stop` working without the `[serve]` extra depends on this being true, the design should either (a) confirm the current import chain is clean and commit to it as an invariant, or (b) proactively include the `pid.py` extraction as part of this slice's scope, removing the conditional. Leaving it as "verify this" during implementation risks discovering late that the fallback extraction is needed but was never scoped or tested.

### [NOTE] Import guard message is imprecise for edge-case failures

The `ImportError` guard in `_start_daemon` always tells the user to install the `[serve]` extra, even if the extra is already installed and the import fails due to a corrupted environment or version conflict. This is a minor UX issue—standard practice for optional-dependency guards and unlikely to cause real confusion—but worth noting that a more precise message (e.g., checking `importlib.util.find_spec` first) could distinguish "never installed" from "installed but broken."

### [PASS] Migration plan and verification walkthrough are thorough

The migration plan correctly identifies CI updates, the verification walkthrough covers both the happy path and the guarded path, and the success criteria are testable and complete. Cross-slice dependencies (906, 908) are noted.
