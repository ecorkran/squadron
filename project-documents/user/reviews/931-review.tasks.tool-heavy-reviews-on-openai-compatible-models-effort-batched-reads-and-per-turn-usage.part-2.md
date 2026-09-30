---
docType: review
layer: project
reviewType: tasks
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
project: squadron
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-2.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20260929
dateUpdated: 20260929
reviewedSha: 233c9bb339c093f19fd83ea01972edad41bed5c8
revision_number: 3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 36
runId: run-20260930-p5-f12cfe4d
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: concern
    category: scope-safety
    summary: "Task 18 sends effort to the wrong file for the summary path"
    location: "src/squadron/pipeline/summary_oneshot.py:102"
  - id: F002
    severity: note
    category: api-contract
    summary: "`read_chunk_usage` signature deviates from the design's stated contract"
    location: "unverified"
  - id: F003
    severity: note
    category: test-coverage
    summary: "The \"six call sites\" criterion is softened from equality to containment"
    location: "src/squadron/review/review_client.py:225"
  - id: F004
    severity: note
    category: task-scoping
    summary: "Task 23 bundles verification with a mutation of the user's global config"
    location: "project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-2.md"
  - id: F005
    severity: pass
    category: nfr
    summary: "NFR coverage and CI gating are correct and verified"
    location: "pyproject.toml:83"
  - id: F006
    severity: pass
    category: traceability
    summary: "Success criteria are fully covered, with correct sequencing and checkpoint distribution"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md"
---

# Review: tasks — slice 931

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Task 18 sends effort to the wrong file for the summary path

Task 18 lists three sites to receive `resolved.effort`: `pipeline/actions/review.py` (near 390 — verified correct), `pipeline/actions/dispatch.py` (AgentConfig at dispatch.py:157 — correct), and `pipeline/actions/summary.py`. But `pipeline/actions/summary.py` builds no `AgentConfig`; it only resolves the alias (`summary.py:222`, `resolved = context.resolver.resolve_full(...)`) and hands `model_id`/`profile`/`model_allows_tools` to `capture_summary_via_profile_with_telemetry`. The `AgentConfig` for the summary path is built in `pipeline/summary_oneshot.py:102`. Following Task 18 literally (edit the three named files, test in `test_summary.py`) leaves `agent_config.effort` unset for summaries — a silent no-op of exactly the kind D11 intends to cover, and one Task 20's DEBUG log of the sent level would confirm only if the value got there. The task should also change the `capture_summary_via_profile_with_telemetry` / `capture_summary_via_profile` signatures (and check the `cli/commands/summary_run.py:61` call site), or state explicitly that summary-mode effort is intentionally out of scope.

### [NOTE] `read_chunk_usage` signature deviates from the design's stated contract

Task 3 adds a keyword-only `warned: set[str] | None = None` to `read_chunk_usage`, where the design's D8/Component Structure describes `read_chunk_usage(chunk) -> TokenUsage | None`. The task documents the deviation and its rationale (D12's "once per `handle_message`" needs call-boundary state the reader cannot hold), and keeps the design's one-argument form working, so this is a legible, additive change rather than drift. Worth folding back into the slice design's D8/API Contracts when the design is next touched, so the two documents do not disagree about the function's signature.

### [NOTE] The "six call sites" criterion is softened from equality to containment

Technical Requirements says "All six call sites produce the same credentials as `profile_credentials`". Task 4B instead asserts each site's `credentials` *contains every item of* `profile_credentials(profile)`, explaining that equality would fail where a site adds keys. That reading is correct — `review_client.py:225` adds `hooks` and `mode`, and `cli/commands/spawn.py:38` adds `api_key_env` conditionally — but it means a site that silently *drops* a profile-derived key (the failure mode the criterion exists for) is still caught only if the dropped key is one of the three returned by the helper. The task's instruction to "check each other site's current extras before writing its assertion" is the right guard; keep it.

### [NOTE] Task 23 bundles verification with a mutation of the user's global config

Task 23 asks for a full suite/lint/typecheck run, frontmatter validation, a config edit to `~/.config/squadron/models.toml` (the path `aliases.py:models_toml_path` resolves), four live walkthrough steps, conditional runs for the other providers, and any fixups — in one commit boundary. Each piece is individually clarified and the deliverable is genuinely a verification pass, so this is not a split candidate so much as a note that the task is long and partly non-reproducible (live API access). Two specifics are worth tightening: step 10 sets `effort = "extreme"` on the same alias step 1 defines, and the task does not say to restore it afterwards, so a rerun can trip the invalid-value WARNING unexpectedly; and "add it there; this is the user's own config" makes an out-of-repo edit the task's first action, which is easy to forget once the walkthrough begins.

### [PASS] NFR coverage and CI gating are correct and verified

The slice's only NFR is the event-loop constraint. Tasks 11 and 15 each create a `tests/load/` test for it (`tests/load/test_usage_reader_loop.py`, `tests/load/test_read_file_batch_loop.py`), styled after the existing `tests/load/test_grep_timeout.py`, asserting a scheduling-gap bound, a per-call cost bound, and a single `asyncio.to_thread` hop for a batch. The tasks state no separate CI wiring is needed because `ci.yml` runs `uv run pytest` and `pyproject.toml:83` sets `testpaths = ["tests"]`, which includes `tests/load/` (existing load tests already ship there). I verified both facts directly, so the gating claim is sound rather than assumed.

### [PASS] Success criteria are fully covered, with correct sequencing and checkpoint distribution

All thirteen functional criteria and the full Technical Requirements unit-test list map to tasks: 1–2 (`none`-preserving sums), 3–10B (usage capture, D12 rows, failure artifact, rendering), 11 (greps, load test, live baseline), 12–15 (`read_file` helper extraction with a byte-for-byte characterization test written *before* the source change, `paths`/budget, guidance), 16–22 (Effort vocabulary, alias validation and reader, resolver plus the three alias-resolving call sites, CLI/client recording, rendering, per-provider application, Codex warning), 23–25 (verification, follow-up issues, close-out). Ordering is C → B → A as the design requires, no task depends on a later one, no task traces to nothing in the design, and each task ends in its own commit — so checkpoints are distributed per task rather than batched at the end. The design's citation anchors hold up: `resolver.py:73`, `review.py:390`, `cli/commands/review.py:703`, `aliases.py:225`, `base.py:56`, `file_tools.py:89`.

### Run Digest

- Response length: 6440 chars
- Response is newline-free: no
- Tool calls made: 36
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 25911
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

### Raw Response

## Summary
The task breakdown is thorough, well-sequenced (C → B → A, matching the design's Development Approach), and traces to every numbered success criterion. Test-with patterns and per-task commit checkpoints are present throughout; load tests exist for the one NFR and are already gated by CI. One CONCERN: Task 18's summary target names the wrong file, so the effort value cannot reach the config the summary path actually builds.

## Findings

### [CONCERN] Task 18 sends effort to the wrong file for the summary path
category: scope-safety
location: src/squadron/pipeline/summary_oneshot.py:102
Task 18 lists three sites to receive `resolved.effort`: `pipeline/actions/review.py` (near 390 — verified correct), `pipeline/actions/dispatch.py` (AgentConfig at dispatch.py:157 — correct), and `pipeline/actions/summary.py`. But `pipeline/actions/summary.py` builds no `AgentConfig`; it only resolves the alias (`summary.py:222`, `resolved = context.resolver.resolve_full(...)`) and hands `model_id`/`profile`/`model_allows_tools` to `capture_summary_via_profile_with_telemetry`. The `AgentConfig` for the summary path is built in `pipeline/summary_oneshot.py:102`. Following Task 18 literally (edit the three named files, test in `test_summary.py`) leaves `agent_config.effort` unset for summaries — a silent no-op of exactly the kind D11 intends to cover, and one Task 20's DEBUG log of the sent level would confirm only if the value got there. The task should also change the `capture_summary_via_profile_with_telemetry` / `capture_summary_via_profile` signatures (and check the `cli/commands/summary_run.py:61` call site), or state explicitly that summary-mode effort is intentionally out of scope.

### [NOTE] `read_chunk_usage` signature deviates from the design's stated contract
category: api-contract
location: unverified
Task 3 adds a keyword-only `warned: set[str] | None = None` to `read_chunk_usage`, where the design's D8/Component Structure describes `read_chunk_usage(chunk) -> TokenUsage | None`. The task documents the deviation and its rationale (D12's "once per `handle_message`" needs call-boundary state the reader cannot hold), and keeps the design's one-argument form working, so this is a legible, additive change rather than drift. Worth folding back into the slice design's D8/API Contracts when the design is next touched, so the two documents do not disagree about the function's signature.

### [NOTE] The "six call sites" criterion is softened from equality to containment
category: test-coverage
location: src/squadron/review/review_client.py:225
Technical Requirements says "All six call sites produce the same credentials as `profile_credentials`". Task 4B instead asserts each site's `credentials` *contains every item of* `profile_credentials(profile)`, explaining that equality would fail where a site adds keys. That reading is correct — `review_client.py:225` adds `hooks` and `mode`, and `cli/commands/spawn.py:38` adds `api_key_env` conditionally — but it means a site that silently *drops* a profile-derived key (the failure mode the criterion exists for) is still caught only if the dropped key is one of the three returned by the helper. The task's instruction to "check each other site's current extras before writing its assertion" is the right guard; keep it.

### [NOTE] Task 23 bundles verification with a mutation of the user's global config
category: task-scoping
location: project-documents/user/tasks/931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-2.md
Task 23 asks for a full suite/lint/typecheck run, frontmatter validation, a config edit to `~/.config/squadron/models.toml` (the path `aliases.py:models_toml_path` resolves), four live walkthrough steps, conditional runs for the other providers, and any fixups — in one commit boundary. Each piece is individually clarified and the deliverable is genuinely a verification pass, so this is not a split candidate so much as a note that the task is long and partly non-reproducible (live API access). Two specifics are worth tightening: step 10 sets `effort = "extreme"` on the same alias step 1 defines, and the task does not say to restore it afterwards, so a rerun can trip the invalid-value WARNING unexpectedly; and "add it there; this is the user's own config" makes an out-of-repo edit the task's first action, which is easy to forget once the walkthrough begins.

### [PASS] NFR coverage and CI gating are correct and verified
category: nfr
location: pyproject.toml:83
The slice's only NFR is the event-loop constraint. Tasks 11 and 15 each create a `tests/load/` test for it (`tests/load/test_usage_reader_loop.py`, `tests/load/test_read_file_batch_loop.py`), styled after the existing `tests/load/test_grep_timeout.py`, asserting a scheduling-gap bound, a per-call cost bound, and a single `asyncio.to_thread` hop for a batch. The tasks state no separate CI wiring is needed because `ci.yml` runs `uv run pytest` and `pyproject.toml:83` sets `testpaths = ["tests"]`, which includes `tests/load/` (existing load tests already ship there). I verified both facts directly, so the gating claim is sound rather than assumed.

### [PASS] Success criteria are fully covered, with correct sequencing and checkpoint distribution
category: traceability
location: project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md
All thirteen functional criteria and the full Technical Requirements unit-test list map to tasks: 1–2 (`none`-preserving sums), 3–10B (usage capture, D12 rows, failure artifact, rendering), 11 (greps, load test, live baseline), 12–15 (`read_file` helper extraction with a byte-for-byte characterization test written *before* the source change, `paths`/budget, guidance), 16–22 (Effort vocabulary, alias validation and reader, resolver plus the three alias-resolving call sites, CLI/client recording, rendering, per-provider application, Codex warning), 23–25 (verification, follow-up issues, close-out). Ordering is C → B → A as the design requires, no task depends on a later one, no task traces to nothing in the design, and each task ends in its own commit — so checkpoints are distributed per task rather than batched at the end. The design's citation anchors hold up: `resolver.py:73`, `review.py:390`, `cli/commands/review.py:703`, `aliases.py:225`, `base.py:56`, `file_tools.py:89`.
