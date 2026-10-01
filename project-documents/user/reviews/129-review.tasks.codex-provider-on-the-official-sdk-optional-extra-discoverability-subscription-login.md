---
docType: review
layer: project
reviewType: tasks
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261001
dateUpdated: 20261001
reviewedSha: dd709b1d18d83c0919d9d0d2be5ecb9b392e87d2
revision_number: 3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 49
turns: 20
promptTokens: 1167217
cachedTokens: 975360
completionTokens: 82402
reasoningTokens: 77233
durationSeconds: 480.4
runId: run-20261001-p5-9c2f4175
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Every success criterion traces to at least one task"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Sequencing and dependencies are respected; no cycles"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Test-with pattern and commit checkpoints are distributed, not batched"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "No NFR restatement in this slice; no load-test obligation"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F005
    severity: concern
    category: uncategorized
    summary: "CI never installs the `codex` extra, so the SDK drift test always skips"
    location: ".github/workflows/ci.yml:33"
  - id: F006
    severity: concern
    category: uncategorized
    summary: "The `sq models list` marker's target cell is ambiguous for default output"
    location: "src/squadron/cli/commands/models.py:82-90"
  - id: F007
    severity: note
    category: uncategorized
    summary: "Task 15a adds a Part B surface the slice design does not enumerate"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F008
    severity: note
    category: uncategorized
    summary: "Task 6 is the largest unit and bundles two separable behaviors"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
---

# Review: tasks — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Every success criterion traces to at least one task

Cross-reference: FR "review completes with no API key / no PATH codex" → Tasks 5, 6, 10, 13, 26 (+ PM walkthrough step 6); FR "without the extra, error contains the exact install command" → Tasks 5, 10, 14, 23, 24, 25; FR "sq auth login browser + --device-code" → Tasks 20, 23; FR "status shows email/plan; logout removes login" → Tasks 21, 24, 25; FR "other profiles byte-for-byte unchanged" → Task 23; FR "effort reaches the SDK; artifact records effort and usage" → Tasks 8, 9, 9b. Technical: `codex_app_server`/`AppServerConfig`/`resolve_codex_binary` removal → Task 11 + Task 26; no profile-name/auth-type string dispatch → Task 26 diff review; one test per Failure Modes row → Tasks 6, 7a, 7b, 9, 20, 21, 23, 24, 25; real-types SDK test → Task 12; ruff/format/pyright → Tasks 13, 26. Integration: default-install suite → Tasks 13, 26; `sq doctor` / `sq models list` with and without the extra → Tasks 15, 16. Verification-walkthrough steps 1–8 each map to a task (3, 4, 6, 8 are correctly carved out as PM-only manual steps). No criterion is orphaned, and no task except Task 15a (see NOTE) lacks a criterion behind it.

### [PASS] Sequencing and dependencies are respected; no cycles

Part 0 (1→2) gates the port; Part A order is 3→4→5→6→7a→7b→8→9→9b→10→11→12→13, with `runtime.py` (5) preceding every consumer (6, 10, 14), and the Part A gate (13) before Part B. Task 14 precedes its two consumers (15 doctor, 16 models); 15a follows 15; 18 is explicitly deferred until 15–17 exist so the hint-source test can assert a single `src` definition site. Part C orders 19 (Protocol) → 20/21 (`login.py`) → 22 (`OAuthFileStrategy` implements it) → 23/24/25 (CLI), which is the only order in which Tasks 23–25 can pass. No circular dependency and no task depends on a later one.

### [PASS] Test-with pattern and commit checkpoints are distributed, not batched

Every implementation task carries its own tests in the same task (5, 6, 7a, 7b, 8, 9, 10, 14, 15, 15a, 16, 19, 20, 21, 22, 23, 24, 25) and its own commit, so no task ends without a verifiable success statement. Only Tasks 11, 13, 18, 26 are audit/gate tasks, and each states "commit only if the audit required edits" rather than deferring commits to the end. The two exceptions are deliberate and labelled: 9b is a cross-module assertion over 8 and 9 ("no production code expected"), and Task 12 is a real-types test that follows the port.

### [PASS] No NFR restatement in this slice; no load-test obligation

The slice design has no Non-Functional Requirements section and sets no latency/throughput target — it explicitly declines one ("No latency target is set: the cost is dominated by the agentic turn itself, and the hang case is already bounded by `codex.turn_timeout_s`"), converting the one startup-cost concern into a DEBUG log (Task 6) instead of a benchmark. `tests/load/` holds prior slices' event-loop load tests; nothing here restates one, so no `tests/load/` task and no load-test CI gate are owed.

### [CONCERN] CI never installs the `codex` extra, so the SDK drift test always skips

D1 keeps the pin loose (`openai-codex>=0.159.3,<1`) precisely on the argument that "API drift is caught by the real-types test (Technical Requirements) instead." Task 12 writes that test with `pytest.importorskip("openai_codex")`, and Task 13/26 run the extra-installed suite only locally ("in a throwaway venv"). The `test` job installs the default dependency set (`uv sync --dev`) and the `hermetic` job clones the default install, so `test_sdk_surface.py` reports *skipped* in every automated run — the mitigation D1 relies on is never executed where it matters. The breakdown needs a CI wiring task (e.g. a job or matrix leg that does `uv sync --extra codex` and runs the suite, or at minimum the new test module) and a Gate on its result; as written, the guard is implicit and unenforced.

### [CONCERN] The `sq models list` marker's target cell is ambiguous for default output

Task 16 requires the marker in "the Notes/Profile cell" and asserts it is present "in default and verbose". Those cannot be the same cell: `_show_aliases` adds `Profile` unconditionally (line 82) but adds `Notes` only under `if verbose:` (line 90), so a marker written only into Notes is invisible in default output and a marker written only into Profile never appears under the Notes heading in verbose. The task also changes the marker wording from the design's `(needs [codex] extra)` to `(needs extra: <hint>)`, which is disclosed and justified (single hint source) but compounds the cell question, since the design located the marker in the Notes/Profile cell. A junior AI following the bullet literally can satisfy one assertion and fail the other; the task should name the cell per mode (or state that the marker is concatenated into Profile in both modes).

### [NOTE] Task 15a adds a Part B surface the slice design does not enumerate

The design's "Sub-part B surfaces" list is exhaustive — missing-package error, `sq doctor` row, `sq models list` marker, README — and its Integration Requirements mention only `sq doctor` and `sq models list` running cleanly. Task 15a additionally wires `codex provider` into `sq setup`'s four name-keyed tables plus its tests. This is defensible plumbing (without it the new doctor row renders as a raw check name with no recheck/explanation/anchor, per `setup_steps.py`), and no success criterion is contradicted by it, but it is scope beyond the design and worth confirming with the PM rather than treating it as implied.

### [NOTE] Task 6 is the largest unit and bundles two separable behaviors

Task 6 (Effort 4) simultaneously removes the legacy `resolve_codex_binary`/`_SDK_INSTALL_URL`/`_CLI_INSTALL_CMD`/GitHub-install error text, rebuilds the client lifecycle on `resolve_codex_runtime()`, introduces `Sandbox(value)` validation with its own error path (D4), changes the `thread_start` signature, adds startup-duration logging, preserves the `shutdown()` teardown contract, *and* re-points the whole `test_agent.py` fake set plus seven new assertions. The sandbox decision (D4) is independent of the port and carries its own error contract; splitting it into its own task/commit would leave the port commit failing for one reason at a time. Not blocking — the bullets are explicit enough to execute — but it is the one task where a mid-task failure would be hard to localise.

### Run Digest

- Response length: 7903 chars
- Response is newline-free: no
- Tool calls made: 49
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 304266
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 1167217 / 975360 / 82402 / 77233
- Duration: 480.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
