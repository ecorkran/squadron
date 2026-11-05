---
docType: review
layer: project
reviewType: slice
slice: benchmark-sandbox-and-case-record
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: ef6d51a92bef416c09d60faee087b218920b0079
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
effort: high
turns: 5
promptTokens: 325532
cachedTokens: 232974
cacheWriteTokens: 92550
completionTokens: 9169
durationSeconds: 75.7
costUsd: 0.51409
costBasis: provider
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and plan coverage"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md#Component-Structure"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Auth probe has no timeout and no hang handling"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md#D8"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Overweight for a 3/5 slice: cut or defer"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md#Technical-Scope"
  - id: F004
    severity: concern
    category: specification
    summary: "Classification rule for patch targets that are not found is not implementable as written"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md#D11"
  - id: F005
    severity: concern
    category: error-handling
    summary: "A tampered case record and an absent one are not distinguished on read"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md#D1"
  - id: F006
    severity: note
    category: architecture-alignment
    summary: "Documented deviations from the architecture are justified"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md#D1"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes for the suite runner and environment resolution"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md#D10"
  - id: F008
    severity: pass
    category: architecture-alignment
    summary: "Containment principles from the architecture are carried through"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md#D7"
---

# Review: slice — slice 421

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering, dependency direction and plan coverage

`benchmark/` depends on `metrology/` and `replay/sandbox.py`, and neither depends back. Concrete adapters are reachable only through `registry.py`. Every item the slice plan assigns to 421 is present: case and case-set records, environment resolution with an identity, the scrubbed environment, the auth check, and the suite runner. The providers named in "Provides to Other Slices" match what 422, 424 and 425 consume in the slice plan. The `BenchmarkAdapter` protocol is kept separate from 400's `LanguageAdapter` (D9), which keeps the snapshot adapters free of execution stubs. The slice plan's open questions (adapter shape, no-lockfile projects) are answered in D5 and D9.

### [CONCERN] Auth probe has no timeout and no hang handling

The probe is a live model call under a redirected `HOME`. The doc names this as the riskiest unknown, and the likeliest failure is a hang, not a clean non-zero exit. Claude Code or Codex may block on a login or onboarding prompt when credentials are not found. D12 defines only `install_timeout_s` and `suite_timeout_s`. D8 defines "No" as "exit 0 with a non-empty response, else no", so a hang is not covered. The slice does not say:
- how long a probe may run;
- how a timed-out probe's process tree is killed;
- that a timeout reports as `no` with a distinct reason.

Add a `benchmark.auth_probe_timeout_s` key, and make a timeout a defined `no` result that carries the partial stderr.

The same gap applies to the pytest and `uv sync` timeouts (D5, D10). The slice does not say whether `ProcessRunner` kills the child's whole process group, or what leaves the sandbox when it doesn't. State the kill semantics once and test that no orphan processes survive a timeout.

### [CONCERN] Overweight for a 3/5 slice: cut or defer

The slice bundles the following:
- a store refactor with two new primitives;
- an extraction of `HistoryFreeSandbox` from 177 with a changed `sweep_orphans` signature;
- a scrubbed environment with `SCRUB_SPEC_VERSION`;
- a per-profile symlink carryover table;
- an empirical auth check with a hidden probe command;
- an adapter protocol and registry;
- a uv resolver;
- a pytest reporter plugin shipped as package data;
- five-kind classification;
- three CLI subcommands plus a slash command.

Candidates to cut or defer:
- **Multi-adapter selection.** `claims(tree)` with the zero-or-many `SandboxError`, `AdapterRegistry` and `default_registry()` are built for several adapters, but only Python exists. The slice plan leaves shape beyond Python open and Future Work 1 adds languages. Key the lookup by `SourceLanguage` with one entry, and add `claims()` and the ambiguity handling when a second adapter arrives. The "doubly-claimed tree" test and failure path go with it.
- **`/sq:benchmark` slash command.** The slice plan does not assign it to 421, and the only commands are verification and diagnostic tools (`auth-check`, `sandbox`). Defer it until 422 gives the group a user-facing command. If project convention requires CLI and slash parity from the first command, say so in the doc.
- **`--keep` plus `env.txt`.** This is reproduction tooling for verification step 3. The `--keep` flag already leaves the paths in place. The `env.txt` writer could be a test helper instead of a shipped feature.

Keeping the five `FailureKind` values, the reporter plugin, and case-set versioning is justified. The slice plan assigns versioning and the failure split, and D10 rejects the lighter junitxml option for good reasons.

### [CONCERN] Classification rule for patch targets that are not found is not implementable as written

D11 detects `missing_symbol` for an `AttributeError` "whose `obj` is a project module" and says this includes a `mock.patch` target that is not found. As far as I know, `unittest.mock` raises its own `AttributeError("<target> does not have the attribute ...")` without setting `name` or `obj`, so the reporter has no `obj` to read. Please verify this against the pytest and Python versions in use.

This case matters because the architecture's fairness rule (test-first, point 1) lists "patch target that is not found" explicitly. If the case is misclassified as `other_exception` or `project_exception`, 422 will either admit or reject the wrong cases. The criteria already require a fixture test for it. D11 should name the detection mechanism. Options are the innermost frame being in `unittest.mock`, plus parsing the target from the message, or resolving the target module's `__file__`. Without that, the stated mechanism and the stated test cannot both hold.

### [CONCERN] A tampered case record and an absent one are not distinguished on read

D1 says a record whose stored id does not match its content "fails to load". The store API gives `get_case(case_id) -> BenchmarkCase | None`, and D3 builds on `iter_records()`, which exposes the store's "tolerant iteration". Two silent paths follow:
- `get_case` returns `None` for a tampered file, which looks the same as a missing case. `write_case_set` would then report it as a missing id.
- `list_cases` may skip the tampered file without a signal.

The project rule is to fail explicitly and log at ERROR. State that `get_case` raises `MetrologyStoreError` for an id mismatch, and that list and iterate paths log it at WARNING or higher. Add a test that checks the signal, not only that the record "fails to load".

### [NOTE] Documented deviations from the architecture are justified

- **`reference_sha` in case identity (D1).** The architecture's identity list leaves it out. The doc gives the reason (hidden-test source is read from the reference at grading time), and the exclusion list is already in identity per the slice plan. 422 and 425 should treat this as the governing definition.
- **Case sets keyed by name, not `ProjectId` (D2).** The architecture says new records are keyed on `ProjectId`. The architecture also allows pooling cases across projects in 422, so name-keyed sets are consistent. The slice should state where `case_set` files sit in the store layout, since there is no project directory to put them in.
- **Prerequisite on 420.** The doc says 421 "reads nothing from 420" yet lists it as a prerequisite and in `dependencies`. This is harmless, but it is an ordering constraint with no technical dependency behind it.

### [PASS] Failure modes for the suite runner and environment resolution

D5 and D10 enumerate the main failure modes with explicit handling: install timeout, an unsupported or missing lockfile, a stale lock, a missing `uv`, suite timeout (partial results with `not_run`), and a missing or unparseable JSONL (`SuiteRunError`, never an empty pass). Each failure carries stderr and a reason, and is logged at ERROR. The Technical Requirements ask for a test per failure path. This matches the architecture's "absent is not zero" principle, because the harness-caused reasons are distinct values 422 can count.

### [PASS] Containment principles from the architecture are carried through

The environment is built from an allowlist, not by deleting entries. `HOME` is redirected, which covers squadron's and the agents' config directories. No GitHub credentials are passed. `PATH` puts the sandbox environment first and leaves out the user's tool installs. The doc is honest about the limits (published-package install, store path reachable by absolute path) and hands them to 424's leak scan. It also puts the auth question first in the implementation order, as the architecture asks, so a `no` reaches the PM before later slices build on it.

### Run Digest

- Response length: 8857 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 325532 / 232974 / 92550 / 9169 / not computed
- Duration: 75.7 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Responses

- **F002 (fixed):** Added `benchmark.auth_probe_timeout_s` (D12), and a probe timeout is now a `no` with reason `timed out` plus a test. Kill semantics already exist: `ProcessRunner` starts each child in its own process group and kills the group on timeout, so D12 states that once instead of adding mechanism.
- **F003 (fixed):** Cut `claims()`, `AdapterRegistry` and the zero/many-claims failure path; the adapter now comes from `adapter_for(SourceLanguage)` with one entry. Deferred `/sq:benchmark` to 422, and dropped `env.txt`; verification step 3 now points at the scrubbed-environment integration test.
- **F004 (fixed):** Verified on Python 3.13: mock's `AttributeError` has no `name` or `obj`. D10 now has the plugin read the `_patch` object's `target` from the innermost `unittest/mock.py` frame, and D11 classifies on that.
- **F005 (fixed):** `get_case` raises `MetrologyStoreError` for an id mismatch. List paths already skip unreadable records with a WARNING in `_iter_records`, and the criteria now test both signals.
- **F006 (noted):** The store is one flat directory of `<record_id>.json`, so case-set files need no project directory. The 420 prerequisite is a deliberate ordering constraint and stays.
