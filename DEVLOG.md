---
docType: devlog
project: squadron
dateCreated: 20260218
dateUpdated: 20260831

---

# Development Log

A lightweight, append-only record of development activity. Newest entries first.

---

## 20260901

### Slice 263: Code Review and Live Verification

**The tool wiring is confirmed working against a real non-SDK model.** `sq run test-p4 264 -v`
from a standard terminal dispatched to `kimi27` and the model's response enumerated specific
filesystem paths it had probed and found missing — evidence only a model actually calling
`read_file` can produce. A tool-less model cannot know a path is absent; it would have invented
a design. The step nonetheless reported failure, for two reasons unrelated to this slice:

1. **The 909 post-condition cannot pass for an undesigned slice.** `expected_artifact_paths`
   resolves the target via the slice plan's `design_file`, which is `None` until a design exists
   (verified: 262/263 have paths, 264/265 are `None`), so the check fails closed before touching
   the disk. P4 exists to *create* that file — a chicken-and-egg in the post-condition.
2. **CF prompt-template guide paths do not match the tree** (`guide.ai-project.process` without
   `.md`; `file-naming-conventions.md` under `project-guides/` rather than one level up). The
   model correctly refused to invent a design it could not ground.

Both are pre-existing and worth filing separately.

**Code review found four issues; all four fixed.** Two were consequential and both were in code
this slice wrote:

- **The SDK session path silently dropped `allowed_tools`.** `_dispatch_via_session` never reads
  the field, so a step declaring tools that routed there ran tool-less and returned
  `success=True` — precisely the no-op-with-prose failure this slice exists to prevent, and
  invisible to load-time validation because the routing decision happens at runtime. Now both
  SDK paths fail loudly: the session path returns a failed `ActionResult`, and `one_shot_dispatch`
  raises when the resolved profile's provider is the SDK, since registry names
  (`read_file`) are not SDK vocabulary (`Read`). Slice 265 owns the mapping.
- **Unconditional `cwd` changed SDK one-shot behavior.** `providers/sdk/provider.py` forwards a
  non-None `cwd` into `ClaudeAgentOptions`, which previously never received the key. D2's
  "inert" justification only ever covered the non-SDK agent. Now gated on the resolved provider
  inside `one_shot_dispatch`, where the provider is actually known.

Two false starts worth recording, both caught by existing tests rather than by inspection: the
guard was first written against `profile_name == ProfileName.SDK`, which wrongly catches the
`None`-alias fallback (that case names the SDK profile but still routes through the one-shot
agent), and the `cwd` suppression was first put at the call site, where the provider is not yet
resolved. Both belong on `profile.provider`, not the profile name.

The remaining two findings were small: `validate_allowed_tools` returned on the first non-string
element instead of accumulating, contradicting its own batch-reporting docstring; and
`test-p4.yaml`'s tools could route to SDK under a `--model` override, which the new guard now
turns into a loud failure.

Four regression tests added for the guards.

### Slice 263: Implementation (Phase 6)

Tasks 1-10 and 12 complete on branch
`263-slice.dispatch-action-wiring-and-pipeline-yaml-surface`, one commit per task. Task 11's
manual end-to-end verification is partially done and the rest is deferred — see below.

**Diff shape matches the design exactly.** Five source files:
`pipeline/steps/utils.py` (the `validate_allowed_tools` helper), `pipeline/steps/dispatch.py`
and `pipeline/steps/phase.py` (validate + conditional expand pass-through),
`pipeline/actions/dispatch.py` (threading into `AgentConfig`), and
`data/pipelines/test-p4.yaml`. `schema.py`, `loader.py`, `executor.py`, `core/models.py`, the
agent, and the provider are untouched — the absence of a `loader.py` change is the signal that
D1's existing extension point carried the validation rather than a new one being added.

**Three corrections to the task file, found by running the commands rather than trusting
them.** First, `sq run` takes the slice index as a positional argument; the task file and the
design's walkthrough both used `--slice <n>`, which exits with `No such option: --slice`. The
walkthrough is corrected. Second, task 8's malformed-value case surfaces as
`ActionResult(success=False)` with `allowed_tools` named in the error, not as a propagating
exception — `execute` is a process boundary that wraps exceptions. The raise still happens in
`_resolve_allowed_tools` and no agent is spawned, so the fail-loudly requirement holds; only
the observable shape differs. Third, task 9's D2 guard has to model a reverted `cwd` as `None`,
not `""`: the agent's check is `cwd is None`, so an empty string slips past it and
`Path("").resolve()` silently writes to the process working directory instead — a subtly wrong
test that would have passed for the wrong reason.

**The conditional-expand guard was verified as live, not assumed.** Temporarily rewriting the
pass-through as unconditional fails five tests including
`test_expand_omits_allowed_tools_when_absent`, which is what the task text predicted.

**Task 11.2/11.3 deferred — environment, not defect.** `uv run sq run test-p4 264 -v` exits
immediately with "SDK pipeline execution cannot run inside a Claude Code session". The guard at
`cli/commands/run.py:148` triggers on the `CLAUDECODE` environment variable unconditionally,
before any pipeline-shape classification, so it blocks even a pipeline `--explain` reports as
Claude-free and needing no persistent session. Bypassing it would defeat a deliberate project
guard, so the live positive and contrast runs must be done from a standard terminal. Recorded
as an explicit NOT VERIFIED section in the slice design's walkthrough with the exact commands
to run.

The negative case (11.1) *was* verified through the shipped CLI: a pipeline with `read_fil`
exits 1 naming the bad tool and listing `['read_file', 'write_file', 'bash']` from
`tools.list_tools()`, before any model call. Both `--validate` and `--dry-run` reach that gate.

**Gates:** `ruff format` clean, `ruff check` all passed, `pyright` 0 errors, full suite
3144 passed / 2 skipped in 7m12s.

### Slice 263: Task Breakdown (Phase 5)

Twelve tasks written to
`project-documents/user/tasks/263-tasks.dispatch-action-wiring-and-pipeline-yaml-surface.md`
(297 lines, no split needed); slice plan entry 3 updated with the tasks reference. Phase 4
review came back PASS with all five findings at severity `pass`, so the breakdown follows the
design unchanged.

**Ordering.** Tasks are sequenced so each leaves the suite green: 1-4 add the validation helper
and wire it into the four step types while nothing yet produces the field; 5-6 add the
conditional `expand()` pass-through; 7-8 thread `allowed_tools` and `cwd` into `AgentConfig`;
9-11 prove the end-to-end path. Test tasks sit immediately after their implementation task
rather than batched at the end.

**Two guards written directly into the task text**, because both are places a junior
implementer would plausibly do the reasonable-looking wrong thing. First, the `expand()` change
must be conditional — an absent key has to leave the expanded dict byte-identical, and the
existing exact-equality tests will fail on an added `"allowed_tools": None`. The task says
explicitly that this failure is the guard working, not a test to update. Second, task 3 says
that if the implementer finds themselves editing `loader.py`, stop: `validate_pipeline` already
calls every step type's `validate()`, and needing a loader change means the design's D1 was
departed from.

**Assertion quality is specified, not left to taste.** Task 8 requires assertions on the
resulting `AgentConfig` field values rather than on mock call counts, and task 9 requires
asserting the file exists on disk. That is deliberate: the failure mode this slice exists to
prevent — a step running tool-less and the model describing a file it never wrote — is
invisible to a test that only checks a mock was called. Task 2 likewise requires the
unknown-name test to assert the bad name appears in the message, since a count-only assertion
would pass against a message naming the wrong tool.

Task 12 pins the expected diff shape: exactly five source files, with `schema.py`, `loader.py`,
`executor.py`, `core/models.py`, the agent, and the provider unmodified. Any change there means
the design was departed from and is a stop-and-reconcile condition rather than a judgment call
at commit time.

**Review pass (CONCERNS → addressed).** Both non-pass findings were real and are fixed. F001:
commits were batched into close-out, contradicting the project's commit-once-per-task rule and
wasting the fact that every task already leaves the suite green — a mid-sequence interruption
would have lost everything uncommitted. A commit protocol now sits in the Context Summary and
each of tasks 1-11 carries a commit checkbox with its own semantic message, so the history will
read as the task sequence. F002: task 12 asserted "integration branch is unset" as a fact frozen
at authoring time. Merge is now its own subtask (12.4) that re-reads
`cf config get git.integration_branch` at merge time and takes the target from that, not from
what the branch was forked from. The two PASS findings (success-criteria coverage, no circular
dependencies) needed no action.

---

### Slice 263: Dispatch Action Wiring and Pipeline YAML Surface Designed (Phase 4)

Design written to
`project-documents/user/slices/263-slice.dispatch-action-wiring-and-pipeline-yaml-surface.md`;
slice plan entry 3 updated with its design reference. No code changed.

**Two shipped-code facts revised the slice plan's assumptions.** The plan predated slice 262's
implementation and got two things wrong that reading the merged code corrected.

First, `cwd` must be threaded alongside `allowed_tools`, not treated as a separate concern.
`OpenAICompatibleAgent.__init__` raises `ProviderError` when `allowed_tools` is non-empty and
`cwd is None` (the D8 check added in 262), while `one_shot_dispatch` hardcodes `cwd=None`.
Wiring tools without `cwd` would fail 100% of the time on any step declaring a tool.
`ActionContext.cwd` already carries the executor's `effective_cwd` and is the source; the design
threads it unconditionally (D2) so the tool path cannot be reached with `cwd` unset.

Second, the plan's "matching the slice 245 `auth_policy` pattern" does not apply. `auth_policy`
is a **pipeline-level** typed field on `PipelineSchema`; step configs are a deliberately untyped
`dict[str, object]` so step types own their own contracts. A typed per-step field would need
either a schema model per step type (a refactor outside this slice) or a `StepSchema` field most
step types ignore (ISP violation). Validation goes in the step types' existing
`validate() -> list[ValidationError]` hook, which `validate_pipeline` already calls and all six
CLI entry points already surface — and which yields squadron's own `ValidationError` rather than
the `pydantic.ValidationError` the plan anticipated (D1).

**Load-time validation is the substance, not decoration.** The agent drops unknown tool names
with a WARNING and continues (262's D1, kept deliberately so shipped review templates carrying
Claude-vocabulary names keep working until 265). That tolerance is right for templates and wrong
for YAML: `allowed_tools: [read_fil]` would run the step with no tools and the model would
describe a file it never wrote — the same silent-no-op class as issue #15. The design keeps the
agent's WARNING (D5) and protects YAML with a registry check at load time instead, so each
surface gets the strictness it needs. Registry bootstrap follows `validate_pipeline`'s existing
lazy-import convention (`bootstrap_step_types()`, `load_all_templates()`); `squadron.tools`
registers built-ins as an import side effect and is otherwise only reachable through the lazily
loaded openai provider.

**Scope.** Five files: a shared `validate_allowed_tools` helper in `pipeline/steps/utils.py`
(one home, not four copies across `DispatchStepType` and three `PhaseStepType` instances),
validate/expand changes in `steps/dispatch.py` and `steps/phase.py`, threading in
`actions/dispatch.py`, and `allowed_tools: [read_file, write_file]` on `test-p4.yaml`'s design
step. `bash` is excluded from the shipped pipeline (D4) — the demo proves file writing and
`bash` is unrestricted beyond CWD scoping. Nothing changes in `schema.py`, `loader.py`,
`executor.py`, `AgentConfig`, the agent, or the provider; the absence of loader changes is the
signal that the design uses the existing extension point rather than adding one.

One risk carried forward: `allowed_tools` is the first list-valued step-config field to travel
the param-placeholder resolution path. The action narrows the type at the boundary and raises on
a malformed value rather than silently dropping tools (D3), and a test asserts the list arrives
intact at `AgentConfig`.

---

## 20260831

### Slice 264: Task Breakdown (Phase 5)

Converted the 264 design into `user/tasks/264-tasks.context-forge-mcp-tool-bridge.md` — nine
sequential tasks, test-with ordering (fake MCP server fixture lands before the bridge it
tests; each implementation task is immediately followed by its test task). Structure follows
the design's dependency order: config keys → fake-server fixture → `mcp_bridge.py` → bridge
tests (real stdio round-trips incl. timeout asserting the child process is reaped) →
`cf_tools.py` descriptors → mocked-transport arg-mapping tests → availability-gated live
contract test → walkthrough/close-out. Context summary pins the seven design facts an
implementer must not lose (one-way layering, errors-as-values, WARNING floor, single
mapping-table home for CF argument names, no project identity in schemas, SDK-owned process
teardown, unconditional registration). Next: PM approval, then Phase 6 on branch
`264-slice.context-forge-mcp-tool-bridge`.

### Slice 264: Slice-Design Review Findings Addressed

Two reviews of the 264 design at `054cb78`: claude-sonnet-5 (CONCERNS, 2 concerns + 1 note)
and a comparative kimi-k3 run (PASS, 2 notes). All actionable findings addressed:

- **F001 (isError below WARNING+ floor):** bumped the CF-reported `isError` row from DEBUG
  to WARNING — uniform compliance beats a prose exception.
- **F002 (npx grandchild survival on timeout):** verified against installed mcp 1.26.0
  rather than assumed — the SDK spawns with `start_new_session=True` and tears down via
  `os.killpg` with SIGKILL escalation (Windows tree-kill), so npx's forked node is reaped.
  Documented in the design; timeout test now asserts the child is gone.
- **Fifth-tool scope note (both reviews):** slice plan entry 4 now names all five tools with
  the `cf_workflow_status` rationale.
- **kimi F005 (metadata):** design frontmatter now `dependencies: [261, 262, 263]`,
  `interfaces: [265]`.

### Slice 264: Context-Forge MCP Tool Bridge — Design Complete

**Phase 4 design created:** `264-slice.context-forge-mcp-tool-bridge.md`; slice plan entry 4
updated with the design reference.

Delivered:
- Five curated CF tools via the 261 descriptor protocol: `cf_set_phase`, `cf_set_slice`,
  `cf_build_context`, `cf_prompt_get`, `cf_workflow_status` (status added beyond the plan's
  four — mutating tools without a read tool force the model to mutate blind).
- Real MCP stdio transport (D1), not a `cf` CLI wrapper: generic `tools/mcp_bridge.py`
  single-call helper + `tools/cf_tools.py` descriptors. Purely additive — no agent,
  executor, dispatch, or schema changes (263's validation is registry-driven).
- Narrow squadron-semantic schemas mapped to CF MCP calls in one table (D2); per-call
  spawn→call→teardown sessions since the descriptor protocol has no teardown hook (D3);
  unconditional registration for deterministic pipeline validation (D4).
- Config keys `cf.mcp_command` (default `npx -y @context-forge/mcp`) and `cf.mcp_timeout_s`.

Verified while designing: `@context-forge/mcp` is published (0.13.0); installed python `mcp`
1.26.0 supports `StdioServerParameters.cwd`; CF MCP schemas for `project_update`,
`context_build`, `prompt_get`, `workflow_status` confirmed against the live server. Schema
drift is covered by an availability-gated live contract test in the design.

Context for sequencing: with 261–263 landed plus this slice, a tool-capable non-SDK model
can run any phase's work end to end (files, bash, CF state/context). Review-path file access
remains slice 265.

---

## 20260829

### Slice 262: OpenAICompatibleAgent Agentic Loop Implemented (Phase 6)

Implementation complete on branch `262-slice.openaicompatibleagent-agentic-loop`, forked from
`main`. Eight per-group commits (config keys; translation helpers; constructor threading;
`_call_api`/`_stream_turn` split; tool-call execution; the loop itself; a slice-review fix; this
close-out), each leaving `pytest tests/providers/openai/ -q` green.

**Constructor threading (D8, D1).** `OpenAICompatibleAgent.__init__` gained keyword-only
`allowed_tools`/`cwd` params. The D8 check (raise `ProviderError` when a non-empty *requested*
tool set has `cwd=None`) runs before any registry call, against the requested set rather than
the post-D1-filter one — a caller asking only for unknown names with no `cwd` is still refused,
per the design's Constraint 3. `OpenAICompatibleProvider.create_agent` now passes
`config.allowed_tools`/`config.cwd` through; a dedicated test asserts on the *returned agent
object* (not just the constructor call) that materialization actually happened, closing the
slice-design review's F002 gap.

**`_stream_turn` split.** `_call_api` is gone. Its request/aggregate logic (delta accumulation,
multi-chunk tool-call assembly — moved verbatim, not rewritten) now lives in
`_stream_turn(messages, tool_schemas) -> TurnResult`, a pure primitive that touches neither
`self._history` nor `translation`. `handle_message`'s no-tools branch inlines the old
translate-and-append logic directly (review F006: no forwarding wrapper). The original 15-test
`test_agent.py` suite, including `test_handle_message_yields_system_for_tool_call`, passes with
**zero source modifications** — the slice's primary regression gate.

**The loop.** `_run_agentic_loop` reads both loop-limit config keys once, before iterating;
loops until a turn has no `tool_calls` (the *only* point that translates a turn into
caller-facing Messages — intermediate turns are executed against but never yielded);  executes
every tool call in a turn via `_execute_tool_call`, appending one `role: "tool"` result per
call in order; and enforces two of the design's three termination conditions as guards rather
than hard stops for max-iterations (D3: raises `ProviderError`, no partial-text return) and a
one-shot history-budget notice (D4: warns and asks the model to finalize, `max_iterations`
remains the hard backstop). `_execute_tool_call` implements the full five-branch error table
(malformed JSON, unknown tool, executor error-result, executor-raises, success) with D9's
WARNING-not-DEBUG logging for the two model-protocol-violation branches.

**Slice review caught a real bug before merge.** A multi-agent code review of the branch diff
(`/code-review high`) converged independently across several angles on one high-severity,
CONFIRMED finding: the history-budget notice was appended as a `role: "tool"` message with
`tool_call_id=""` — not a real pending call id — which a strict OpenAI-compatible backend would
reject with 400, and even where accepted, `tool_schemas` stayed attached on every following
turn so the model could simply ignore the notice and keep calling tools, defeating the guard's
purpose entirely. Fixed (commit `dbb7549`): the notice is now a plain `user`-role message (no
fake tool result, no invented id), and once the guard fires, `tool_schemas` is withdrawn from
every subsequent `_stream_turn` call so the model structurally cannot keep calling tools. The
budget-guard test was strengthened to assert both the new message shape and the absent `tools`
kwarg on the following API call.

The same review surfaced several lower-severity, real findings that were triaged with the
Project Manager and deliberately deferred rather than folded into this slice (see the design
document's Verification Walkthrough → "Known follow-ups" for the full list and reasoning):
`get_typed_config`'s uncaught `ValueError` on a misconfigured loop-limit value, sequential
rather than concurrent tool-call execution within a turn, `_execute_tool_call`'s ad hoc error
strings versus the `ToolResult`/`_error` convention already established in `tools/builtin.py`,
a silent empty-`tool_call_id` fallback for a genuinely malformed model response (distinct from
the fixed budget-guard case), and the `max_tool_iterations=0` edge case's misleading error
message. None of these are new information about D1's vocabulary-mismatch window — that
remains accepted, documented, and closed by slice 265, not by this list.

**Known, pre-existing pyright baseline issue — not introduced by this slice.** Scoped
`pyright src/squadron/providers/openai/` and `pyright src/squadron/config/` both report errors
whose root cause is the `openai` and `pydantic_settings`/`tomli_w` packages' type stubs not
resolving under this project's pyright/venv configuration — every symbol imported from them
type-checks as `Unknown`, cascading through every file that touches them. Verified via
`git stash` before any slice-262 change: `main` already reported 72 errors on
`providers/openai/` and a comparable count in `config/`. `config/keys.py` — the only file this
slice changed in `config/` — is independently clean. Raised to and explicitly accepted by the
Project Manager as out of scope for this slice; the fix (if one exists) is a project-wide
tooling/dependency task, not a slice-262 concern.

Full suite: `pytest -q` → **3115 passed, 2 skipped, 3 warnings in 430.59s** (design baseline was
~3078 passed, 2 skipped; the delta is this slice's additions). The ~7-minute runtime is a
pre-existing property of `tests/metrology/test_audit_cli.py`'s variance-series tests, which
sleep for real against `metrology.audit_run_cooldown_s` — unrelated to this slice, noted here
only because it was mistaken for a hang mid-session before the real cause (a genuine `time.sleep`
in already-merged code) was confirmed. `ruff check .` clean repo-wide.

Slice 262 is marked complete in both the design document and
`260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md` (entry 2). The initiative
itself stays `not_started` — 263 (pipeline YAML wiring), 264 (MCP bridge), 265 (review
coverage, which closes D1's WARNING window), and 266 (tool-use configuration) are unstarted, in
that dependency order after 262.

### Slice 262: Task Review Findings Addressed (Phase 5)

Review `262-review.tasks...md` (verdict CONCERNS, claude-sonnet-5, reviewedSha `e9bc278`):
2 pass, 2 concerns, 1 note. All three actionable findings verified against the task file's
actual text and fixed.

**F001 — Task 2 called a helper Task 3 hadn't built yet.** The original constructor-threading
task (then Task 2) built `self._tool_schemas` via `translation.build_tool_schemas`, which
wasn't implemented until Task 3.1 — sequenced after Task 2's own commit checkpoint. Executed in
order, Task 2's commit would have referenced a function that didn't exist. Fixed by swapping
the two groups: translation helpers are now Task 2 (no dependency on constructor work),
constructor threading is Task 3. All internal cross-references (six of them, found by a full
grep sweep) updated to match, including two pre-existing stale references the swap did not
cause (config-limit reads pointed at "Task 4" when they actually happen in the loop, Task 6).

**F002 — no dedicated test for the `create_agent`-level wiring path.** Task 3.3 (threading
`allowed_tools`/`cwd` through `create_agent`) had only "existing test passes unmodified" (which
exercises just the no-tools case) plus a manual diff read as its success bar — nothing would
catch a future edit silently dropping the wiring. Added Task 3.4: a test that calls
`create_agent` with a populated `AgentConfig.allowed_tools`/`cwd` and asserts on the *returned
agent object* that materialization actually happened, not just on the constructor called
directly.

**F006 (note) — Task 4.3 left `_call_api` vs. inline as an open choice.** Resolved: `_call_api`
is removed once `_stream_turn` exists, since a same-file one-line-forwarding wrapper adds
indirection the split already replaced. Title and body updated to state this directly rather
than leave it as a judgment call for whoever implements it.

The three remaining PASS findings (success-criteria traceability; distributed commit cadence;
no NFR restated so no load-test task needed) required no action.

---

## 20260828

### Slice 262: Task Breakdown (Phase 5)

Task file written: `262-tasks.openaicompatibleagent-agentic-loop.md`, 8 task groups (branch;
config keys; constructor threading; translation helpers; `_call_api`/`_stream_turn` split;
tool-call execution; the loop itself; full-suite verification; close-out), each ending in a
commit, mirroring slice 261's per-group cadence.

Structured around the design's two structural gaps and two review-driven fixes:

- Task 2 threads `allowed_tools`/`cwd` through the constructor and applies D8 (raise
  `ProviderError` when a non-empty tool set has no `cwd`) and D1 (drop unknown declared names
  with a WARNING) at construction time — before any registry call, per the design's ordering
  requirement (Constraint 3: the D8 check must use the *requested* set, not the post-D1-filter
  one, or a caller requesting only unknown names with no `cwd` would silently skip the check).
- Task 4 extracts `_stream_turn` from `_call_api` and pins the no-tools path as a hard
  regression gate: the existing 15-test suite, including
  `test_handle_message_yields_system_for_tool_call`, must pass with **zero source
  modifications** before Task 5 proceeds.
- Task 5 implements D9 (WARNING, not DEBUG, for malformed tool-call JSON and unknown tool
  names) with a five-branch test matrix (malformed JSON, unknown name, executor error-result,
  executor raises, success) asserting the log level of each.
- Task 6 tests all three termination conditions (normal, max-iterations, history-budget)
  against real temp-dir config files rather than monkeypatched module attributes — the loop
  limits are config keys (Task 1), not source constants, so the test needs to prove the keys
  are actually wired, not just that a patched variable is read.
- Task 8 explicitly notes the D1 WARNING window continues on every non-SDK review until slice
  265 migrates template vocabulary — not a defect to chase down in this slice's close-out.

### Slice 262: Slice Review Findings Addressed (Phase 5)

Review `262-review.slice...md` (verdict CONCERNS, claude-sonnet-5, reviewedSha `f576aaf`):
2 pass, 2 concerns. Both concerns verified valid against the shipped code and fixed in the
design.

**F002 — `cwd` fallback for a security-relevant jail root.** The original design fell back to
`Path.cwd()` with an INFO log when tools were configured but `cwd` was None, defended as
"explicit and observable." That defense was wrong: logging a fallback does not stop it being
one, and `cwd` is the trust boundary for `write_file` and `bash`. Revised (D8) to raise
`ProviderError` at construction — no default jail root. Checked every caller rather than
assuming: `dispatch.py:63` sets `cwd=None` but never sets `allowed_tools` (materializes no
tools, never reaches the check); `review_client.py:116` and `metrology/audit.py:621` both set
`cwd`. So nothing trips the raise today; it exists so a future caller cannot silently write
into whatever tree the process happens to be running from.

**F001 — loop protocol failures were DEBUG-only.** Malformed tool-call JSON and unknown tool
names in model responses originate in loop code this slice writes, and the Failure-Mode
Enumeration rule requires WARNING+ observability. The asymmetry the review claimed is real and
verified: slice 261's tool layer already logs path-escape (`builtin.py:76`) and bash timeout
(`builtin.py:308`) at WARNING, so the loop would have been quieter than the tools it calls.
Revised (D9) to WARNING; both stay non-fatal and still return an error tool result. Success
criteria updated to assert the log signal via `caplog`, not just the returned result — the
review correctly noted a regression swallowing a protocol violation would have passed the
original criteria.

Incidental finding while verifying F002: `metrology/audit.py` is a fourth caller passing Claude
vocabulary (`[Read, Glob, Grep, Bash]`), alongside the six review templates. Strengthens D1 —
the unknown-name filter is not review-template-specific.

Both PASS findings (scope/dependency alignment; bash-hang handling delegated to the tool layer)
needed no action.

## 20260827

### Slice 262: Agentic Loop Design (Phase 4)

Slice design written for `262-slice.openaicompatibleagent-agentic-loop.md`. Read the
initiative-260 architecture and slice plan, then the actual code the slice touches
(`providers/openai/{agent,translation,provider}.py`, `core/models.py`, the slice-261 tool
API, and the existing openai test harness) before designing.

Three findings from reading the code shaped the design beyond what the slice-plan entry
specified:

**The agent never receives `allowed_tools` or `cwd`.** `OpenAICompatibleAgent.__init__` takes
only `name`, `client`, `model`, `system_prompt` — the config fields stop at
`OpenAICompatibleProvider.create_agent`. Threading them through the constructor is part of
this slice, not an assumed precondition. Both new params are keyword-only with defaults so
existing construction sites are unaffected.

**Shipped review templates would crash the loop (D1).** All seven templates in
`data/templates/` declare Claude vocabulary (`[Read, Glob, Grep, Bash]`); `review_client.py`
already passes `template.allowed_tools` and `cwd` into `AgentConfig`. Activating the non-SDK
consumer of that field would make `registry.materialize` raise `ToolNotRegisteredError` on
every non-SDK review — turning a working tool-less review into a hard failure until slice 265
migrates the vocabulary. Design decision: the agent pre-filters names through
`registry.lookup`, dropping unknown ones with a WARNING that names each dropped name and the
registered vocabulary. Loud and observable, not a silent fallback; surviving behavior equals
today's. `materialize`'s fail-fast contract is unchanged — it is right for a caller that
controls its own name list. Load-time validation belongs where names are declared (263 for
pipeline YAML, 265 for templates).

**`_call_api` cannot be reused as-is.** It interleaves the request, delta aggregation, and
`translation.build_messages`. A loop needs turns 1..n-1 aggregated but not translated. Design
splits out `_stream_turn` as a single-turn primitive returning raw `TurnResult`; the
no-tools path and every loop iteration share it, and exactly one code path translates a turn
into caller Messages — which makes "intermediate turns are never yielded" structural rather
than conventional.

Also decided: materialize once at construction rather than per message (`cwd` is fixed for an
agent's lifetime); max-iterations raises `ProviderError` rather than returning partial
intermediate text (a plausible-looking non-answer); the history-budget guard warns and
continues once rather than terminating, leaving `max_iterations` as the hard stop; loop limits
live in a new `providers/openai/limits.py` following the slice-261 module-attribute pattern so
monkeypatched tests see patched values at call time. `dispatch.py` hardcodes `cwd=None`, so
the design specifies an explicit INFO-logged `Path.cwd()` fallback rather than leaving the
jail root undefined.

**Revised after review (D7):** the two loop limits moved from source constants to
registered config keys (`agent.max_tool_iterations`, `agent.max_history_chars`),
following the existing `review.max_file_size_bytes` precedent in `config/keys.py`. PM runs
non-SDK (OpenRouter) reviews frequently across models with very different context windows,
so a source-baked cap would need a code edit to tune. Read once at loop start so a mid-run
config change cannot alter termination behavior halfway through. PM accepted the D1 warning
window; sequencing stays 262 then 265.

Slice-plan entry 2 updated with the design pointer. No code changes.

### Slice 261: Code Review Findings Addressed (Phase 6)

Review `261-review.code...md` (verdict CONCERNS, claude-sonnet-5, reviewedSha `a64b741`):
2 pass, 2 concerns, 1 note. All three actionable findings verified valid and fixed.

**F001 — blocking syscalls on the event loop.** `_resolve_in_jail` calls
`Path.resolve(strict=False)`, which stats every existing path component; `write_file` also
called `is_dir()` and `exists()` synchronously. The reads and writes were correctly pushed
into `asyncio.to_thread`, but the syscalls *gating* them were not, violating
`rules/python.md` ("synchronous code inside an async def must run in <1ms worst case"). Both
executors now do all blocking work — resolve, stat, and the read/write — inside a single
`to_thread` call, which also drops a thread hop.

**F002 — no hang protection on the file tools.** The serious one, and worse than the review
stated. A FIFO inside the jail is legal input (the jail admits any path under the working
directory), and `read_bytes()` on it blocks forever. The reproducer did not merely stall the
loop: wrapping it in `asyncio.wait_for(timeout=3)` did **not** rescue the process, because
`asyncio.to_thread` workers cannot be cancelled — `wait_for` abandoned the coroutine and the
interpreter then hung joining the stuck thread at shutdown. A caller-side timeout is therefore
not a defense; refusing before `open()` is. Added `_reject_special_file`, which returns an
INFO-logged error result for anything that exists and is neither a regular file nor a
directory (directories keep their own specific message). The reproducer now returns in 0.002s.
Three new tests cover it, including the log-level assertion.

**F003 — redundant parent jail check in `write_file`.** Verified empirically across accepted
and rejected paths: the second `_resolve_in_jail(cwd, str(target.parent))` never rejects
anything the first check accepted, because `resolve()` de-symlinks every existing component,
so a target inside the jail always has a parent inside it. The check was dead code whose
comment claimed TOCTOU protection it did not provide. Removed, with a comment recording why a
second check cannot add coverage — `test_path_whose_parent_resolves_outside_the_jail_is_rejected`
is satisfied by the first check and still passes.

Walkthrough output is byte-identical to the pre-fix run, so the changes are behavior-preserving
on the documented paths. 57 tools tests (up from 54); full suite 3078 passed, 2 skipped.

### Slice 261: Tool Registry and Core Tools Implemented (Phase 6)

New package `src/squadron/tools/` — the tool abstraction boundary for the rest of initiative
260. Six modules: `limits.py` (the single home for every tool limit), `errors.py`, `models.py`
(pure data types), `registry.py`, `builtin.py` (the three tools), `__init__.py` (public API).

**Types.** `ToolResult(content, is_error=False)` and `ToolDescriptor(name, description,
parameters, factory)`, both frozen dataclasses, plus the `ToolExecutor` / `ToolFactory`
aliases. No `Protocol` — design decision D2: one shape, one implementer, no polymorphism to
justify the indirection. Errors are values, never exceptions: an executor returns
`is_error=True` rather than raising to its caller.

**Registry.** Module-level dict and free functions, mirroring `providers/registry.py`, with
one deliberate divergence — a duplicate `register` raises `ValueError` instead of silently
overwriting. A tool name is a security-relevant surface, so two definitions of it must fail
fast rather than resolve by import order. `materialize(names, cwd)` resolves `cwd` exactly
once and hands the same resolved path to every factory; an unknown name raises
`ToolNotRegisteredError` naming the offender and listing what is registered.

**Jail rule.** `(cwd / path).resolve(strict=False).is_relative_to(cwd)`. One expression covers
relative input, absolute input, and `..` traversal, because `Path.__truediv__` with an
absolute right-hand operand yields that absolute path; `resolve()` follows symlinks first, so
a link pointing out of the jail is rejected too. String prefix comparison is explicitly not
used — `/tmp/jail_evil` starts with `/tmp/jail` but is not inside it, and `tests/tools/
test_jail.py` pins exactly that case as a regression test. `write_file` jail-checks the parent
directory *before* creating anything, so a rejected write never leaves a directory behind
outside the jail; the tests assert the rejection is effective, not merely reported.

**Logging contract** (not a suggestion — asserted by `caplog` tests on all three tools):
WARNING for jail violations and bash timeouts, INFO for every other `is_error=True` result
(missing file, permission denied, non-zero exit, truncation), ERROR only for the
unexpected-exception catch-all via `logger.exception`. The INFO cases are routine
model-probing outcomes the model itself reacts to; elevating them would train operators to
ignore warnings.

**Tools.** `read_file` (byte-truncated at `MAX_READ_BYTES` with a visible trailing marker —
truncation is never silent), `write_file` (creates parent dirs, reports created-vs-overwritten
plus byte count), `bash` (spawned with `start_new_session=True` so the timeout path can
`os.killpg` the whole group, labeled stdout/stderr each truncated at `MAX_OUTPUT_BYTES`,
non-zero exit carries the captured output back because the model needs it to react).
Blocking filesystem work goes through `asyncio.to_thread`.

Limits are read as module attributes at call time, never captured at import — that is what
makes the monkeypatched-constant tests work, and it kept the bash timeout test at 0.5s instead
of hanging for the real 120s. Verified separately that the process-group kill leaves no
orphan: a command backgrounding a child dies whole.

**Nothing consumes tools yet** — that is 262. `git diff --stat main..HEAD` touches only
`src/squadron/tools/` and `tests/tools/`, 1088 insertions, 0 deletions, so behavior-neutrality
holds by construction rather than by inspection. 54 new tests; full suite 3075 passed, 2
skipped, no regression. Whole-repo pyright reports 1752 errors both before and after this
branch, none of them in `squadron/tools/`, which is strict-clean on its own.

Committed per task group (8 commits) rather than once at the end, per review finding F003.

### Slice 261: Task Review Findings Addressed (Phase 5)

Review `261-review.tasks...md` (verdict CONCERNS, claude-sonnet-5, reviewedSha `94348c8`):
2 pass, 1 concern, 2 notes. Both actionable findings addressed.

**F003 (concern) — all commits batched at the end.** Correct call, and it violated the project's
own rule ("git add and commit from project root at least once per task"). The original breakdown
had exactly one commit checkpoint, at Task 8.6, after all eight groups were implemented; an
interruption after Task 5 would have left nothing to resume from or bisect against. Fixed by
distributing commits: new **Task 0** creates the slice branch (previously conflated into 8.6,
which no longer makes sense once commits are spread out), groups 1–7 each end with a commit step
naming its own semantic message, and 8.6 commits only the close-out documentation. A "Commit
cadence" note under Task 0 states the invariant every commit must hold — `pytest tests/tools/ -q`
passes — which the group ordering already makes achievable.

**F005 (note) — jail helper had no task-local test.** Its stated success criterion was
annotation/pyright-clean only, with behavioral coverage borrowed entirely from the `read_file` and
`write_file` test tasks. Added **Task 3.1a**, testing the helper in isolation. Beyond mirroring the
tool-level cases it adds two the tool tests do not cover: a path whose *parent* resolves outside
the jail (the case `write_file` depends on before creating directories), and a sibling directory
sharing a string prefix with the jail root (`…/jail` vs `…/jail_evil`) — the direct regression test
for 3.1's "do not use `startswith`" instruction, since that is exactly the case prefix comparison
gets wrong and `is_relative_to` gets right. A jail regression now names the jail instead of
surfacing as two confusing tool-test failures.

**F004 (note) — no load-test/CI-gating criterion.** Confirmed out of scope, no change: the byte
limits and `BASH_TIMEOUT_S` are correctness/safety bounds verified by unit tests with monkeypatched
constants, not a performance SLA.

Also corrected while in the file: Task 3.2's success criterion claimed the wrapper "is used by all
three tools", which is unverifiable at that point in the sequence — no tool exists yet. It now
points at Task 8.3's full gate as the place that confirmation actually happens.

Task file grew 426 → 498 lines. Over the 450 target but within the ~100-line overrun allowance, so
it stays one file.

---

### Slice 261: Task Breakdown Complete (Phase 5)

**Tasks written** to `261-tasks.tool-registry-descriptor-protocol-and-core-tool-implementations.md`
(426 lines, 8 task groups, 20 subtasks, test-with pattern throughout — each implementation task
immediately followed by its test task).

**Sequencing:** package skeleton + pure types (1) → registry (2) → shared jail/wrapper plumbing (3)
→ `read_file` (4) → `write_file` (5) → `bash` (6) → package wiring (7) → verification and close-out
(8). This follows the design's suggested order, with the path-jail helper and shared executor
wrapper pulled forward into their own group so both file tools consume one implementation rather
than duplicating the check.

**Anchors traced on `b05fadc`** and recorded in the task file's Context Summary, so the
implementing agent does not have to rediscover them:

- `src/squadron/tools/` does not exist; `src/squadron/mcp/` is an empty package.
- `asyncio_mode = "auto"` in pytest config — `async def` tests need no decorator.
- Ruff selects `BLE`, so the design's justified catch-all needs `# noqa: BLE001`; the established
  idiom is at `pipeline/emit.py:157` and `pipeline/sdk_session.py:108`.
- Pyright runs `strict` over `src`, so the new package must be fully annotated and must narrow
  `dict[str, object]` values before use.
- Async subprocess idiom mirrors `events/builtin/frontmatter_gate.py:46`.

**Three constraints added that the design implies but does not state:** the `noqa` requirement
above; pyright-strict narrowing; and `caplog.set_level(logging.INFO)` being necessary for the
INFO-level logging assertions the design's F003 fix requires (caplog propagates at WARNING by
default, so those assertions would silently pass-by-absence without it).

**Two implementation hazards called out in the tasks:**

- The registry is module-level and the built-ins register at import, so registry tests need a
  snapshot/restore fixture or test doubles leak across modules.
- The bash timeout test monkeypatches `BASH_TIMEOUT_S`; if the executor captures the constant at
  import rather than reading the module attribute at call time, the monkeypatch is inert and the
  test hangs for the full 120 s. The task instructs changing the code, not the test.

**Verification group (8)** enforces the slice's behavior-neutrality guarantee explicitly: a grep
proving no limit literal escapes `limits.py`, a grep proving nothing outside the package imports
`squadron.tools`, and a `git status` check that no file outside `src/squadron/tools/` and
`tests/tools/` was modified.

**Next:** Phase 6 — implementation on branch
`261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations`, forked from `main`.

---

## 20260825

### Slice 261: Tool Registry, Descriptor Protocol, and Core Tools — Design Complete (Phase 4)

**Design written** to `261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md`.
Foundation slice for initiative 260 (non-SDK agent tool use): `ToolDescriptor` (frozen dataclass —
one shape, no Protocol), `ToolResult`, a process-level registry mirroring `providers/registry.py`,
and three core tools (`read_file`, `write_file`, `bash`) in a new `src/squadron/tools/` package —
sibling to `providers/`, diverging from the arch doc's tentative `core/tools/` to keep `core/` from
accreting. No agent, executor, or pipeline change; after landing, tools exist fully tested with no
behavior change anywhere.

Decisions of note: registry `register()` rejects duplicate names (unlike the provider registry's
silent overwrite — a tool collision is a security-relevant surface); `materialize()` raises
`ToolNotRegisteredError` for unknown names (caller config error; model-requested-unknown is 262's
concern); `cwd` is closure-bound by factories and never appears in a tool's JSON schema; all limits
(`MAX_READ_BYTES`, `MAX_OUTPUT_BYTES`, `BASH_TIMEOUT_S`) live in one `limits.py`; bash gets a
process-group kill on timeout so a hung command cannot hang 262's future loop. Names registered
here start the canonical tool vocabulary (templates migrate to it in 265).

Effort 2/5, `status: not_started`, slice-plan entry updated with design pointer.

---

## 20260824

### Slice 365: Overview Command — Design Complete (Phase 4)

**Design written** to `365-slice.overview-command.md`. Capability (b) of the Document Intelligence
initiative: `/sq:overview` as a first-party command reading the initiative plan (required) and
concept (optional), writing `{index}-analysis.overview.md` for a non-engineering reader. One file
added — `commands/sq/overview.md`. No Python, no installer change; `install.py:48-55` copies
`commands/sq/*.md` wholesale, so the file's presence is its registration.

**Central decision: the command file is self-contained and does not reference the analysis pack.**
`commands/analysis/understand.md:344` already anticipated 365 reusing its provenance-block shape, but
"reuse" here means restating the conventions in this file, not cross-referencing. The reason is an
install-path fact: `install-commands` puts `overview.md` in `~/.claude/commands/sq/` unconditionally,
while `understand.md` arrives only via the opt-in `sq skills install analysis`. A user with squadron
installed and no analysis pack would have a reference resolving to nothing — and the failure would be
a silently degraded document, not a loud error. Accepted consequence: the convention statement
(gap markers, provenance lines, frontmatter, index selection) exists in two files. Four intended
divergences are enumerated in the design; a parity check is carried into the walkthrough. A shared
fragment was rejected because it needs the installer change this initiative has committed not to make.

**Degradation is per field, across a range of incompleteness — not per document.** The governing rule
is: produce as much useful output as the inputs actually support, and state plainly what could not be
produced and why. Incompleteness is the normal condition of a real project, not an error state. Seven
input conditions are enumerated (concept absent; headings unmatched; section present but empty; plan
without dependencies, without non-goals, of one-line stubs, without statuses), each degrading only the
fields it feeds. A section that exists but is empty behaves exactly as an absent one — the failure to
guard against is a field rendering blank or getting filled with plausible prose because *something*
was technically read.

**Two hard stops, both about the required input:** a missing or unreadable initiative plan, and a plan
present but yielding no parseable initiatives. The second is new — five of nine fields source from the
plan, and a document that is mostly markers is a report that the project has not been planned, so
saying that directly beats emitting a hollow document. Everything short of those produces a document.

**Purpose is the one field with a real fallback rather than a marker.** With no concept it derives
from the initiative plan and states that fallback in place. Problem, Audience, and Approach get no
such fallback — the initiative plan describes what is being built, not whose problem it solves, and
inferring the latter from the former is exactly the invention the sourced-or-gapped rule forbids.

**No confirmation gate**, unlike 364. An overview renders artifacts that already exist and asserts no
new commitment; inputs are read-only and the index rule never overwrites, so an unwanted run costs one
deletable file. 364's gate exists because adopting a candidate *is* a commitment.

**Squadron is a sample, not the baseline.** An earlier draft fitted the design to squadron's
particular shape of incompleteness (concept absent, plan complete), which is one point in the range
above. Verification instead runs constructed fixtures spanning all seven conditions, with squadron
included as one real-world instance — valuable there for scale, since thirteen initiatives of real
prose exercise the translation rules in a way a synthetic fixture cannot. This also relocates the
usefulness question: accurate and complete degradation is now verifiable *here*, rather than deferred
to a hypothetical repo, while stakeholder usefulness of a heavily gap-marked document stays a
non-criterion.

**Graph-derived artifacts are not read, even when present** — not the knowledge graph, the
comprehension analyses, or the candidates document. The graph describes code structure, not intent;
the candidates document is explicitly advisory, and rendering unadopted machine proposals as a
roadmap is the overstates-progress failure the translation rules exist to prevent. But this does
*not* cut inherited projects off from a good overview: the chain runs understand → generate concept
and candidates → **human reviews and adopts** → overview reads the resulting planning documents
normally. The overview never touches the graph; the generated artifacts arrive as reviewed planning
documents. The human adoption step is load-bearing and deliberate. Whether those generated documents
are good enough to adopt is genuinely open — 364 deferred that judgment itself — so the path is
architecturally sound with unproven output quality, recorded as such rather than assumed.

**Topic argument dropped.** The naming convention still permits `overview.{topic}`, but nothing asks
for it and an unused argument is an untested path. The command takes no arguments.

**Shared conventions fragment: deferred, not rejected.** An earlier draft asserted a shared fragment
would need installer work; that is unverified, and both install paths already copy directories of
markdown, so it might need no code change at all. Recorded as an open structural option to be
answered with evidence when someone next touches either file. Until then, drift control is a manual
parity diff — process, not machinery, and named as the honest weakness.

Fourteen success criteria, a thirteen-step draft walkthrough, and two non-blocking Phase 6 questions
(concept heading-match leniency, now testable via fixtures rather than blocked on a real concept; and
Benefits granularity). Relative effort 3/5, matching the slice plan. Next: Phase 5 task breakdown.

---

## 20260823

### Slice 364: Initiative Candidates — Implementation Complete

**Phase 6 complete.** All ten task groups executed; all ten success criteria verified per the
Verification Walkthrough. Everything is markdown — `commands/analysis/understand.md` gained a third
sibling flow section (Flow: Initiative Candidates), plus the two cross-reference sentence fixes the
task file anticipated. No Python, no test added.

**Invocation-syntax correction found during the walkthrough.** The design's draft walkthrough used
`/sq:analysis understand candidates`, but `/sq:analysis` only recognizes `tech-debt-audit` today —
dispatcher routing for `understand` is slice 366, not yet built. The skill's actual present-day
invocation is `/understand <argument>` per its own frontmatter. All walkthrough steps were executed
by tracing the skill's protocol text directly. Doesn't affect any success criterion; corrected in the
reconciled walkthrough so a future reader isn't sent looking for a command that doesn't exist yet.

**Full run against squadron's real graph derived 8 candidates**, one per layer carrying at least one
`complex` file-level node — matching the count the design's own Rationale section predicted. No
concept document exists at the concept path, so ordering was signal-strength-only, as expected on
this repo. Declined once (Task 8.2: nothing written, `git status` clean, every candidate verified
traceable to the graph) then confirmed once (Task 8.3: written to
`945-analysis.initiative-candidates.md`, `cf validate frontmatter` clean, all hand-checks passed).
Node-id resolution, one independent dependency recount (24, matching exactly), and the initiative-plan
untouched check (Task 8.4–8.6) all passed.

**All three concept-ordering states exercised (Task 8.7)**, the engagement-informed and
both-declined cases on scratch copies outside the repo entirely — never in `project-guides/`. The
archived concept's Q1 answer ("take over maintenance, and modernize it") shifted the Shared
Foundation candidate up, with the reason declared on the candidate per the design's rule. The
zero-candidate path (Task 8.8) was simulated against a synthetic one-layer fixture rather than
executed as a real write, since PM confirmed a fixture graph doesn't warrant a real `analysis/` file.

**Four decisions the design deferred to Phase 6 are now recorded** (in the reconciled Verification
Walkthrough): the layer-boundary candidacy threshold (resolved as complexity-cluster-only for this
run — layer-boundary candidates weren't derived, since the design gave no numeric cutoff for when a
layer boundary alone is "defensible"), per-candidate ordering-influence phrasing (a fixed
structural-fact → engagement-framing → conclusion shape), scope-statement length (settled at 3–5
sentences), and node-ID list rendering (a Markdown bullet list per candidate, directly greppable for
the resolution check).

**Close-out states the slice is mechanically verified, usefulness unjudged** — the non-criterion from
Phase 4 design is repeated explicitly so a green walkthrough here is never later read as evidence the
8 real candidates are worth adopting.

Guards green: `ruff format --check .` (446 files), `pytest tests/skills/` (62 passed).

**Commits:** `cf40bd3` flow selector · `a0fe779` preconditions · `3a351b3` derivation model ·
`3305f99` record shape and dependencies · `f38a325` concept read · `04daf32` write confirmation ·
`7115147` output conventions · `071890d` walkthrough proof artifact (`945-analysis.initiative-candidates.md`)
· `7d0da0f` walkthrough reconciliation · `f8257e5` slice complete.

**Next:** slice 365 (Overview Command, independent) or slice 366 (Dispatcher Routing and
Documentation, last — also where `/sq:analysis understand candidates` becomes real). Issue #68
(review `allowed_tools` silently ignored by non-SDK providers) remains open and unsized.

### Slice 364: Initiative Candidates — Task Breakdown Complete

**Phase 5 complete.** `364-tasks.initiative-candidates.md` — 440 lines, ten task groups (0–9),
test-with pattern throughout: every authoring task is followed by its verification task before the
next section begins.

**Slice review passed first time.** Five findings, all `severity: pass`, nothing to resolve —
architectural alignment across derivation, the initiative-plan boundary, the optional concept read,
read discipline, and output conventions.

**Anchors re-traced at write time** (`88e299e`), and two diverged from the design's measurements in
ways worth recording:

- **The graph is now 56 commits behind HEAD**, up from 45 at 363's walkthrough. Same
  `gitCommitHash` `1bfbca1`, so the derivation figures are unchanged; preflight warns and proceeds.
  Recorded as an expected observation rather than a blocker.
- **Two `candidates` references in the skill, not one.** Line 399 is the flow-selection exclusion
  note; line 649 is a cross-reference inside the comprehension flow saying initiative candidates
  are slice 364. Both need updating — 363 hit the same shape and fixed only the equivalent single
  sentence. Task 1.2 exists specifically for the second one, with a search-for-`364` check so a
  third reference cannot hide.

Next free analysis index is **945** (`940`–`944` taken).

**Task-file decisions:**

- **Task 0.2 carries a STOP condition** on the layer and complexity figures. The design's reasoning
  about candidate count and ordering was measured against those numbers; if the graph is
  re-analyzed before implementation, the reasoning needs re-checking rather than the tasks being
  run anyway.
- **The removal in Task 1.1 is "remove, do not amend."** An amended exclusion note still reads as a
  live exclusion.
- **362's mechanics are cited, never restated** — repeated as an instruction in Tasks 3.1, 5.2,
  7.3, and checked in the verify tasks. A restated rule drifts from its original.
- **Walkthrough Task 8.7 covers all three concept states** — degraded (the default on this repo),
  engagement-informed, and both-questions-declined — with an explicit prohibition on restoring the
  archived concept into the real tree. Scratch copies only; it is `docType: notes` /
  `status: deprecated` and was archived deliberately.
- **Task 9.2 requires the close-out to state "mechanically verified, usefulness unjudged."** The
  non-criterion is only useful if it survives into the record; without it a green walkthrough reads
  later as evidence the candidates are good.
- **Task 9.1 records the four decisions Phase 4 deferred** — layer-boundary candidacy threshold,
  per-candidate ordering-influence phrasing, scope-statement length discipline, node-ID list
  rendering — so they land in the design rather than only in the implementation.

No Python; no test added (`tests/skills/` runs as a regression guard only).

---

## 20260823

### Slice 364: Initiative Candidates — Design Complete

**Phase 4 complete.** `364-slice.initiative-candidates.md` written; both open questions the slice
plan recorded at planning time are resolved and the two disagreeing documents reconciled.

**Does 364 read the concept? Yes — as an optional input.** The slice plan said graph-only
(dependencies [361], [362]); 363's Integration Points said 364 consumes Q1's engagement answer via
the written concept. Settled: the flow reads `000-concept.{project}.md` when one exists and degrades
to structure-only when it does not. The concept affects **ordering only** — it never creates,
suppresses, or supplies a candidate the graph does not support, which is what keeps the no-padding
rule enforceable. Hard dependencies stay [361] and [362]; the concept is an input, not a dependency,
so the graph-only path every repo has on day one still runs.

The reasoning is grounded in the real graph: ten layers, and `complex` file-level nodes distributed
14/9/7/7/3/1/1/1 across eight of them. That is roughly eight defensible candidates with no ordering
principle among them. Q1 ("take over maintenance and modernize" vs "audit it") is the only available
input that orders the identical set. A both-questions-declined concept is recorded distinctly from a
missing one — the interview happening and returning nothing is a different fact.

**Where candidate quality gets judged.** Mechanical correctness — signal named, node IDs resolve,
dependencies counted from `edges[]`, nothing written without confirmation — verifies against
squadron and the walkthrough does exactly that. Usefulness does not: squadron's initiative plan is
hand-written, so a proposal cannot be told apart from a restatement of already-scoped work. Recorded
as an **explicit non-criterion** so a green walkthrough here is not read as evidence the suggestions
are good.

**Design decisions beyond the two questions:**

- **One signal per candidate**, never two. A candidate citing both a layer boundary and a complexity
  cluster is checkable against neither.
- **Node IDs are cited, not summarized.** "Several files in Pipeline Orchestration" is not checkable
  by someone deciding whether to adopt the proposal.
- **Dependencies are directional edge counts, not sequencing claims.** The document says "27 imports
  into Candidate 1's layers"; inferring order from that belongs to the human.
- **The confirmation defaults to not writing** — the opposite of 363's, which never stalls. 363
  writes a Phase 0 entry point a repo has no other way to obtain; this writes an advisory list that
  costs nothing to regenerate.
- **Zero candidates still asks, and still writes.** A negative result is a real finding about the
  graph; suppressing it would make it indistinguishable from a failed run.
- **`[INFERRED]` is not used in this flow**, stated explicitly so the absence reads as a decision. A
  claim not traceable to a cited signal or node id has no place in the document at all.
- **362's mechanics are cited, never restated** — file-level definition, `nodeIds | length` counting
  with type breakdown, ordinal `complexity` handling, drift rule, edge endpoint string-parse.

**Documents corrected:** slice plan entry 4 (both "Open at design time" blocks replaced by the
resolutions, ordering success criterion and optional-read interface added); 363's Integration Points
line for 364 qualified with *when a concept exists*.

No Python. `cf validate frontmatter` passes on all three touched documents.

---

## 20260822

### Slice 363: Concept Generation — Implementation Complete

**Phase 6 complete.** `commands/analysis/understand.md` grows from 669 to 1017 lines with a sibling
**Flow: Concept Generation** section plus a shared flow selector. No Python; the only changed
non-document file is the skill itself.

**What landed.** A four-case flow selector (none/`comprehension` → comprehension flow, `concept` →
the new flow, anything else stops; `candidates` stays unrecognized until 364), explicit-argument-only
with preflight unchanged for both flows. Three preconditions with two terminal stops and the
`/cf:onboard` boundary. The three-source extraction model — graph (structure, reading strictly less
than the comprehension flow), root README (intent, cited by file, quoted not paraphrased), and a
closed filesystem checklist (development practice, where absence is an observation rather than a
gap). The binding seven-row per-section mapping table with the dropped-topics rule and Solution
Approach's coverage boundary. The two fixed engagement questions, byte-identical to the design, plus
the single confirm-or-correct. The User-Provided Concept write-time contract and re-run semantics.
`[INFERRED]` governance, output conventions, and the concept provenance block.

**Walkthrough outcomes.** The happy path ran live with the PM: both questions answered, and the
derived description **corrected** on two points — the server surface is expected to move to amoeba,
and pipelines drive the context-forge state machine rather than orchestrating agents generically.
The correction landed in the body with provenance `extracted-and-corrected`, exercising that outcome
as the design intended. `cf validate frontmatter` passes. The dropped-topics check found zero
occurrences as content **and** zero as gap markers. The two-direction `[INFERRED]` audit passed: two
marked sentences, both derived from `tour[]` ordering and `layers[]` counts, both listed in
provenance; every unmarked sentence restates a field, cites a file, or reports an observed signal.

The decline path, all three contract/precondition failure cases (renamed section, guide file absent,
guide tree absent), and augment re-run semantics were exercised on scratch copies — the real guide
was never edited and the repo was clean after each. Default stop proved non-mutating against the real
document (identical hash, clean diff); augment refilled exactly the emptied and gap-marked sections,
appended under a dated subheading, and left populated sections byte-identical.

**Generated artifact — archived, not adopted.** The walkthrough wrote
`000-concept.squadron.md` with the filename from the cf project name and the `squadron-ai` graph
divergence stated in the Overview. It now lives at `user/archive/000-concept.squadron.md` as
`docType: notes` / `status: deprecated`. It is **not** squadron's concept document: the engagement
answers were fixtures given to exercise the interview, and squadron is under active development
rather than a maintenance takeover. Kept because the extraction quality — and specifically the two
places it needed correcting — is the data for tuning the flow.

**Flow refinements from the walkthrough.** Three findings, all fixed in the same branch:

1. **README precedence.** The Overview drew on `project.description` and the README lead with no
   rule for disagreement. The graph's description was 45 commits stale and described an earlier,
   narrower squadron. The flow now states that **the README wins** — it is author-maintained and
   travels with the code, while `project.description` describes the repo as it stood when the graph
   was built.
2. **Disagreement is a finding, not noise.** Where the two sources describe the project as different
   *kinds of thing*, the flow now surfaces that at the confirmation instead of blending them into an
   averaged paragraph. A scope that moved without the graph following is worth telling the operator.
3. **The Overview read only the two top-level summaries.** The context-forge correction was
   initially recorded as unreachable intent. That was wrong, and the PM caught it: squadron has
   driven the context-forge state machine since long before the graph was built, and the graph says
   so — `context-forge` appears in **two** layer descriptions and in
   `src/squadron/integrations/context_forge.py`. It was in scope and the draft missed it, because
   the Overview drew only on `project.description` and the README lead, both of which are summaries
   and both of which drop the specific systems a project integrates with. The Overview row now reads
   `layers[]` descriptions too (no extra read — already loaded for Solution Approach), with a
   checkable rule: a system named in two or more layer descriptions and absent from the Overview
   belongs there. Verified against this graph, the check selects exactly `context-forge`.
4. **Decided-but-unbuilt intent is invisible to all three sources.** This holds for **one** of the
   two corrections: the server surface moving to amoeba is a decision that exists nowhere in the
   code. The confirmation carries one bounded, skippable prompt for that class of fact — **part of
   the confirmation, not a third interview question**, so SC2's two-question limit is intact, and a
   skipped answer adds nothing to the document. It is explicitly **not** a substitute for reading
   the sources properly: a fact already present in `layers[]` or a module name is an extraction
   failure when the operator has to supply it.

**Deviations.** One beyond the task file: a second stale forward-reference at the comprehension
flow's Project identity section ("in slice 363") was corrected alongside Task 7.4's, since it was the
same class of defect. Task 8's `[INFERRED]` audit and augment case were run as scripted checks over
the real and scratch documents rather than by eye, which is what makes them re-runnable by an
external agent.

### Slice 363: Concept Generation — Task Breakdown Complete

**Phase 5 complete.** `user/tasks/363-tasks.concept-generation.md` (375 lines, frontmatter gate
clean) converts the redesigned slice into 10 task groups: branch + premise re-verification (with
STOP condition against the design's Verified-facts table), flow selector, preconditions and the
`/cf:onboard` boundary, the three-source extraction model (graph / root README / filesystem
signals), the binding per-section mapping table, the two-question engagement interview and single
confirmation (byte-identical wording verification — an improvised question is a defect against
SC2), the User-Provided Concept contract with re-run semantics, `[INFERRED]` governance + output
conventions + provenance, the 6-step verification walkthrough (happy path with PM live, decline
path, contract failure on a scratch guide copy, re-run, flow selection, discipline/scope), and
slice close. Verification is paired with each authoring task per test-with; commits are
distributed at seven checkpoints. Anchors re-traced today on `main` at `dfce803`: graph `1bfbca1`
unchanged, README/tests/CI/config signals present, concept guide holds `## User-Provided Concept`
exactly once, no existing `000-concept.*`. Task file carries an explicit PM-interaction notice:
walkthrough 8.1 needs the PM live, framed before any question is asked, plain text only. Stale cf
`slice`/`tasks` fields (still naming the deleted `-with-interview` documents) corrected to
`363-slice.concept-generation` / `363-tasks.concept-generation`. Awaiting PM approval of the
breakdown before Phase 6 (branch `363-slice.concept-generation` from `main`).

### Slice 363: Design Rejected and Redesigned — Concept Generation

The PM rejected the original 363 design at the start of its Phase 6 verification walkthrough: the
six fixed interview questions ("what problem does this solve and for whom?", "why now?", audience
evolution, methodology preferences) are generic product-discovery boilerplate with no value for an
existing codebase — the answers either sit in the repo's own artifacts or do not matter. The slice
was reset to Phase 4; the task file and both reviews were deleted (`4628f18`), the slice branch and
its one implementation commit deleted, and the design rewritten.

**Root defect:** the architecture treated the graph as the only machine-readable source, so every
graph gap defaulted to interviewing the human. Two measured facts expose it: squadron's README lead
answers "what is this, what problem, who reaches it" directly (the old flow would have asked the PM
while the answer sat in README line 3), and the filesystem carries `tests/`, `.github/workflows/`,
and ruff/pytest config even though the graph has zero test/CI nodes — the old design made
Development Approach interview-primary because it only looked at the graph.

**Redesign** (`363-slice.concept-generation.md`, replacing
`363-slice.concept-generation-with-interview.md`): three extraction sources — graph (structure),
root README (intent, cited by file), filesystem signals (development practice, closed checklist) —
all read before any human contact. Interview reduced to two skippable engagement-context questions
(what the operator needs to do with the codebase; unwritten constraints), answers verbatim into
User-Provided Concept. One confirm-or-correct on the derived description before write. Why-now and
audience questions are dropped entirely, not gap-marked. Retained from the old design: flow
selection, the User-Provided Concept cross-repo contract, re-run semantics, `[INFERRED]` governance,
output conventions, read discipline.

**Architecture amended in place** (PM-sanctioned): Flow steps 3–5 now read prose/signals before a
two-question interview; the Interview scope section carries the new source model and per-section
table; the settled open question on interview wording is removed. Slice plan entry 3 rewritten to
match — risk drops to Low, effort 4/5 → 3/5. New precondition made explicit: the ai-project-guide
must be installed (`/cf:onboard` owns setup and the greenfield conversational path; this flow owns
brownfield artifact-derived drafting — complementary, not overlapping).

### Slice 363: Phase 5 Task Breakdown Complete — Concept Generation with Interview

> **Superseded same day** — this design was rejected at Phase 6 entry; see the redesign entry above.

Design review landed PASS (z-ai/glm-5.2, 6 pass-severity findings, no CONCERNS to carry into
implementation) before task breakdown began. Converted the design into
`363-tasks.concept-generation-with-interview.md`, 394 lines, ten task groups mirroring 362's proven
shape: branch/premise verification, then one group per major design decision (flow selection,
extract-then-ask procedure and decision table, interview questions, User-Provided Concept contract,
re-run semantics, `[INFERRED]` governance and declines, output conventions, verification
walkthrough, close-out), test-with cadence throughout.

**Task 0 re-measures the same three graph facts the design rests on** — `project.name` vs the
squadron project name, non-empty `languages`/`frameworks`, and zero test/CI nodes — as a stated STOP
condition before any implementation task runs, since the per-section decision table was built
directly on those numbers.

**The cross-repo contract check (Task 4) is tested both directions on a scratch copy only** — the
real `guide.ai-project.000-concept.md` is never mutated, matching the design's own terminal-failure
framing for that check.

**All 15 success criteria mapped to specific tasks** with no gaps: flow selection (1) → Task 1;
extract-then-ask scoping (2) → Task 2; question wording (3) → Task 3; declines (4) → Task 6;
User-Provided Concept verbatim/preserve/fail-loud (5, 6) → Task 4; re-run non-destructiveness (7) →
Task 5; frontmatter and gate (8) → Task 7; provenance shape (9) → Task 7; `[INFERRED]` governance
(10) → Task 6; filename vs `project.name` (11) → Task 7; coverage boundary (12) → Task 8; read
discipline and scope (13, 15) → Task 8; PM-usable output (14) → Task 8.

---

## 20260820

### Slice 363: Phase 4 Slice Design Complete — Concept Generation with Interview

Design written for the interview-driven half of capability (a): produce `000-concept.{project}.md`
for a codebase that has no concept document. Markdown only — a sibling flow section in
`commands/analysis/understand.md`, no Python, no change to `src/squadron/` and none to the
ai-project-guide.

**Three measurements against the real graph changed the design.** `project.name` is `squadron-ai`,
the distribution name — deriving the output filename from it would write
`000-concept.squadron-ai.md`, which no `cf` introspection would find, so the filename's `{project}`
is the squadron project name and the graph's value is reported in provenance instead.
`project.description` is upstream prose generated at `1bfbca1` that still calls squadron "a
template-driven code review framework", so Overview is confirm-or-correct with `lastAnalyzedAt`
shown at the moment of judgment rather than extract-and-accept. And `.understandignore` excludes
`/tests/`, `.github/`, `/commands/`, `project-documents/`, and all `*.md`, leaving zero test nodes
and zero CI nodes — so the architecture's "test/CI config nodes as weak evidence" for Development
Approach does not hold here, and that section is interview-primary with the attempt still coded for
differently-configured repos.

**Interview wording and ordering settled** — the parent architecture's first open question. Six
fixed questions, asked before any extracted content is shown. Intent first, for two reasons: a PM
shown a machine's description answers in the machine's vocabulary, and intent questions are the ones
a PM may decline, so declining early costs nothing. Question 6 is an open catch so the fixed set does
not silently bound what the PM can contribute. Nothing structural is asked. Answers to 1–4 serve both
as the verbatim User-Provided Concept content and as the source for the matching Refined Concept
sections, which is the concept guide's own model.

**`[INFERRED]` governance, deferred here by 362, is settled.** The concept flow uses it where the
comprehension flow does not: a sentence carries the marker when it is derived from a named graph
field but asserts something the field does not literally state, carries no marker when it restates
the field, and does not belong in the document at all when no field is behind it. A PM-confirmed
inference stays marked — the marker describes provenance, not confidence.

**The concept is the initiative's one non-idempotent output.** Every other document takes a fresh
index per run; this one has a fixed path, so a re-run necessarily meets an existing document. It is
never overwritten. Augmenting appends to User-Provided Concept under a dated subheading and fills
only Refined Concept sections that are empty or hold a gap marker — mechanically distinguishable,
since a section whose body is exactly a `[GAP: ...]` marker is machine-written.

**The cross-repo contract is verified at write time, and its failure is terminal, not a gap
marker.** A missing or renamed **User-Provided Concept** section means the document cannot be
correctly written at all, which is a different thing from a document missing something.

---

## 20260819

### Slice 362: Comprehension Analysis and Graph Extraction — Implementation Complete

**Phase 6 complete** on branch `362-slice.comprehension-analysis-and-graph-extraction` (7 commits, unmerged — merge is PM-gated). All ten task groups done; walkthrough executed in full with every step passing.

**Both STOP gates cleared before any edit.** Premise re-measurement returned 238/238/238 with layer compositions matching the design exactly (Packaged Declarative Content 34 `config:13 file:1 pipeline:20`, Project Configuration 6 `config:4 file:2`). The id-prefix contract held at `ok:true, n:925`, zero filePaths containing a colon, zero edges with an absent endpoint — so endpoint resolution is a pure string parse and no function/class node is ever read.

**Three 361-contract corrections landed, each verified against the real graph before its commit:**

- **Correction 1 (`4e1ec80`)** — layer count is `nodeIds | length` with a type breakdown where mixed, plus a drift cross-check that reports rather than filters. Verified: 34, 6, sum 238, zero drift on both the type check and the filePath check.
- **Correction 2 (`2aafe86`)** — file-level selector widened to `select(.type != "function" and .type != "class")`. Verified 238, reconciling exactly with `meta.json` `analyzedFiles`; zero survivors lack `filePath`. The old allow-list form yields 201, losing 17 `config` and 20 `pipeline` nodes.
- **Correction 3 (`1204380`)** — the `fingerprints.json` churn note now names the two actual writers. Confirmed against the installed plugin's own `hooks/hooks.json`: the post-commit hook is gated on `"autoUpdate".*true` in `config.json` and the plugin's default is `autoUpdate: false`, so on this repo (which sets only `outputLanguage`) it never fires. Reading a graph never writes fingerprints — later confirmed empirically, see below.

**Skill now carries the full seven-section contract**: the extraction mapping table (verified byte-identical to design lines 241–249), three new sections (project identity, entry points, coverage/scope limits — closing all three 361 deferrals), four deepened sections with explicit ordering rules and fallbacks, the `[INFERRED]`-is-a-defect governance with its mechanical closing-observation test, and the `analyze-codebase-prompt.md` decision (two conventions adopted, no structure, document retained unchanged).

**Generated sample 944** (`user/analysis/944-analysis.codebase-comprehension.md`): seven sections in mapping order, Provenance under the H1, seven inline `From ...` lead sentences satisfying SC1, `grep -c INFERRED` = 0, frontmatter gate clean with a real model id. 943 not overwritten.

**Two numbers changed from the design's measurements — both consequences of correction 2, not premise failures:**

- **Entry points are 28, not 27.** The design counted `type == "file"` only; the corrected selector adds `pyproject.toml`, a `config`-type node genuinely carrying the `entry-point` tag and declaring the `sq` console script. The narrow selector was silently dropping a real entry point — the correction proving itself on its first use.
- **Complexity distribution is 43/89/106 across 238**, where 943 reported 42/76/83 across 201. Same cause; both are internally consistent with their own selector. 943 deliberately retains the pre-correction numbers as the historical record.

**Walkthrough outcomes.** Gap-marker paths (empty `tour`, no `entry-point` tag, absent `meta.json`) each degrade exactly one section and complete. Induced unresolvable endpoints both detected and named — dangling target reported `UNRESOLVED`, malformed source reported `MALFORMED` — with the control run on the unmodified graph returning 0, which is what makes the positives meaningful rather than a check that always fires. Coverage discrepancy reports both numbers (999 vs 238) preferring neither. Full-slice: no `src/` diff, 446 files formatted, 62 skills tests pass.

**One spot-check reported rather than reconciled.** The CLI Surface layer `description` says "27 `sq` sub-commands"; `app.py` registers 23 top-level entries (15 commands + 8 sub-groups) and `cli/commands/` holds 26 non-`__init__` modules. Layer descriptions are upstream-generated prose quoted verbatim, so this is recorded as a caveat in the generated document; the layer's computed node count (29) is unaffected. Numbers embedded in upstream prose carry upstream's authority, not the document's.

**Read discipline held throughout and is now empirically demonstrated.** Every graph access was a field-scoped `jq` selection; no `cat`, `head`, or Read tool call targeted `knowledge-graph.json`, and `git status` on `.understand-anything/` reports no modification — `fingerprints.json` included, which is direct evidence for correction 3's claim.

The design's Verification Walkthrough was updated in place with actual commands, results, and a per-step outcome table, so an external agent can re-run it. Awaiting PM review and merge authorization.

### Slice 362: Comprehension Analysis and Graph Extraction — Task Breakdown Complete

**Phase 5 complete.** Task file at `user/tasks/362-tasks.comprehension-analysis-and-graph-extraction.md` (378 lines, status not_started). Committed to `main` (planning work, no branch). Ten task groups: branch + premise re-verification (with the design's two STOP conditions promoted to explicit gate tasks 0.2/0.3), the three 361-contract corrections each paired with its own verification and commit, the extraction mapping table, the three new sections and four deepened sections as separate per-component subtasks with test-with verification, recorded decisions + cross-reference line, the full eight-step walkthrough (including induced unresolvable-endpoint and coverage-discrepancy paths), and slice close.

**One recorded deviation from the design:** Implementation Notes step 1 says re-run the flow immediately after corrections 1–2. The breakdown instead verifies corrections by executing the corrected skill's own `jq` selections (deterministic, zero tokens, same 34/6/238 evidence) and runs the full flow once at the walkthrough — an interim LLM run would write a throwaway numbered sample at 944 and displace the walkthrough's expected index. Flagged in the task file with the literal-fidelity alternative (walkthrough doc at 945) if the PM prefers.

**Anchors re-verified at breakdown time on `837ff73`:** skill file present (388 lines), graph unchanged since design (`gitCommitHash` `1bfbca1`), next analysis index 944, `.gitignore` trash-only scope already in place (so correction 3 touches only the skill's note text).

Awaiting PM approval of the task breakdown before Phase 6.

## 20260818

### Slice 361: Phase 6 Implementation Complete — Graph Contract and Provenance

Foundation slice of initiative 360 delivered. Everything is markdown authoring: the only new
non-document file is `commands/analysis/understand.md`. No Python was added, `src/squadron/` is
untouched, and the full suite is green at 3021 passed / 2 skipped (both skips pre-existing).

**The contract lives inside the skill file, not a fragment.** `_install_prefix()` globs every pack
`*.md` and installs each as its own skill, so a `graph-contract.md` fragment would have surfaced to
users as a bogus installable command. Slices 362-364 extend this same file; 365 copies the
conventions instead, since a first-party `commands/sq/` command cannot assume the analysis pack is
installed.

**Two divergences from the design, both found by running against a real graph rather than reading
about one.**

The first is the one worth carrying forward: `complexity` is an **ordinal string** — `simple` (83),
`moderate` (76), `complex` (42) across 201 file-level nodes — not the numeric sort key the design
assumed. `sort_by(-.complexity)` fails outright with `string ("simple") cannot be negated`, which is
at least a loud failure rather than a silent miscount. The Complexity hotspots section now selects
the top tier. Per Task 0.1's stop-and-escalate rule this was assessed as a contract question, and it
is a **narrowing, not a break**: the field's name and presence match the architecture's documented
shape, so no escalation was required. Recorded for 362.

The second: `layers[].nodeIds` mixes file, function, and class nodes, so a file count requires
intersecting with `type == "file"`. Taking `nodeIds | length` would have reported node counts as
file counts — wrong by roughly 4x, and wrong in a way that reads as plausible.

**Upstream contract drift remains the initiative's standing risk, and this slice is the mitigation
working as intended.** Both divergences were caught in minutes because validation runs before every
read and because verification used real data. Neither would have been caught by authoring alone.

**Staleness during implementation is expected, not a defect.** Each commit moves HEAD past the
graph's `gitCommitHash`, so runs late in the slice legitimately report "N commits behind HEAD". The
943 sample records the drift, notes that the intervening commits touched only the skill file and
`.gitignore`, and logs proceeding as a deliberate choice — which is precisely the behavior the
provenance block exists to produce.

**Environment caveat worth knowing.** A globally installed `sq` (uv tool at `~/.local/bin/sq`)
resolves its bundled pack from its own snapshot and reports `1 file(s)`, silently ignoring the
working tree. `uv run sq skills install analysis` reports `2 file(s)` and is what exercises the
working-tree installer. This cost a diagnostic detour; the walkthrough now names it.

Verification produced `project-documents/user/analysis/943-analysis.codebase-comprehension.md`, whose
two spot-checked claims both held against the real repo: the CLI Surface layer's "27 sq sub-commands"
matches exactly 27 modules in `src/squadron/cli/commands/`, and `pipeline/sdk_session.py`'s `complex`
rating matches a real 288-line SDK-session wrapper. The design's Verification Walkthrough has been
rewritten with actual commands and observed output so an external agent can re-run it.

**Next:** slice 362 (Comprehension Analysis and Graph Extraction), which deepens this flow and
inherits three deferrals — `config.json` / `.understandignore` coverage limits, `meta.json`'s
`analyzedFiles`, and governance of `[INFERRED]` in deeper analysis.

---


### Initiative 360: Phase 3 Slice Planning Complete — Document Intelligence

Slice plan written to `project-documents/user/architecture/360-slices.document-intelligence.md`.
Six slices across foundation, feature, and integration work, breaking down the two capabilities the
parent architecture describes.

**Slice boundaries follow the dependency structure, not the capability split.** The obvious cut —
one slice per capability — would have produced a 4/5-effort monolith for (a) and hidden the fact
that its three outputs share exactly one thing: the graph-reading contract. That contract is the
only foundation work here, so it became slice 361 with the comprehension analysis as its proving
consumer. The remaining (a) outputs (362 extraction, 363 concept+interview, 364 candidates) are
ordered by how much human input they need, cheapest first, so extraction quality is verifiable
before interview complexity lands on top.

**Capability (b) is genuinely independent and the plan says so.** Slice 365 reads no graph and has
no external dependency. It is numbered last for coherence but explicitly insertable anywhere —
including first, if a client-facing artifact is wanted sooner, or when the marketplace plugin is
unavailable. Stating that in the implementation order matters more than the number.

**Risk ordering put the upstream contract first.** 361 leads because it is the only place this
initiative can be broken by someone else's release — the `understand-anything` plugin is actively
developed and its output shape is observed, not guaranteed. Proving the contract against a real
graph early surfaces that risk before three skills depend on it. It is also the only Medium-risk
slice besides 363, whose risk is interview quality rather than external change.

**Both of the parent's open questions were assigned rather than left floating** — interview wording
to 363, `analyze-codebase-prompt.md` reuse to 362. Gap-marker syntax, which surfaced during the
architecture review, is settled in 361 because the first generated artifact needs it. No open
question remains unowned.

**No slice adds Python.** Every one is markdown skill content plus, in 366, three edits to an
existing dispatcher. `sq install-commands` copies `commands/sq/*.md` wholesale and
`_install_prefix()` copies all `*.md` from `commands/analysis/`, so registration is free for both
capabilities. The plan records this as a tripwire: a slice design concluding otherwise means scope
has drifted from the architecture.

Four items went to Future Work, notably the 900-band index re-cut — the band now carries reviews,
analyses, maintenance tasks, and generated documents in 100 slots, with 940-949 overflowing by
design. That touches `file-naming-conventions.md` and therefore every project on the guide, so it
belongs in 900-band maintenance, not here.

---

### Slice 362: Comprehension Analysis and Graph Extraction — Slice Design Complete

**Phase 4 complete.** Design at `user/slices/362-slice.comprehension-analysis-and-graph-extraction.md`; the slice plan entry already carried the (362) index. Committed to `main` (planning work, no branch).

**Two corrections to the shipped 361 contract, both found by probing the real v2.8.1 graph while writing this design.** These make the slice a defect fix rather than a purely additive one:

- **`layers[].nodeIds` does not mix function and class nodes.** The 361 skill says it does and instructs intersecting with `type == "file"` to get a file count. Measured: all 238 `nodeIds` entries across all 10 layers resolve to `file` (201), `config` (17), or `pipeline` (20) — zero function or class. The intersect instruction therefore **undercounts** two layers: Packaged Declarative Content reports 1 file instead of **34**, Project Configuration 2 instead of **6**. The generated `943` sample carries both wrong numbers. Fix is `nodeIds | length` plus a cross-check that every entry resolves to a node carrying `filePath` — a `function`/`class` entry is reported as upstream drift, not silently filtered, which keeps the simplification safe on graphs nobody has measured.
- **"File-level" means "carries a `filePath`", not `type == "file"`.** The architecture names nine file-level types; 361 collapsed that to one, silently dropping 37 real analyzed files — every review template, every pipeline definition, `pyproject.toml`. Selector becomes `select(.type != "function" and .type != "class")`, stated as an exclusion so a future tenth upstream type is included automatically rather than dropped. This also repairs the coverage arithmetic: 238 file-level nodes reconciles exactly with `meta.json`'s `analyzedFiles` (238), which is what makes the new coverage section verifiable instead of decorative.

Neither is an upstream contract change — the graph matches what the architecture documented, and the 361 skill text is what diverged. No escalation.

**Extraction mapping is the core deliverable:** seven sections, each binding a source-field list, an ordering rule, and a fallback. Order is identity → structure → detail → caveats. The fallback column has no third option — every section resolves to sourced content or a gap marker, never a silent omission.

**Three new sections** the corrected reading makes sourceable: project identity (`project.name/.description/.languages/.frameworks`, none read by 361), entry points (the `entry-point` tag, 27 nodes — the architecture required these and 361 did not deliver them), and coverage/scope limits, which closes all three 361 deferrals (`analyzedFiles`, `config.json`, `.understandignore`) in one place.

**Both open questions settled:**
- **`[INFERRED]`** — defined but not used by this flow; its appearance in a comprehension document is a defect. Every claim traces to a named field, so a gap marker is the correct output where inference would go. The marker stays documented for 363's interview path, which genuinely needs it.
- **`analyze-codebase-prompt.md` reuse** — adopt its fact/inference discipline and its say-so-explicitly rule; adopt none of its ten-part template, which is built for a probe+Repomix backend supplying CI configs, dependency versions, and source text the graph does not have. Adopting it would yield a document that is mostly gap markers. The document is retained unchanged in `user/reference/` and gains only a cross-reference line.

**Also recorded:** the architecture documents `config.json` as carrying `autoUpdate` and `outputLanguage`; the real file carries only `outputLanguage`. Section 7 therefore reports what is present rather than checking for expected keys.

The walkthrough opens with a re-measurement step — if layer sum, `analyzedFiles`, and the file-level node count do not all agree at 238, implementation stops rather than proceeding on a stale premise. The 943 sample is deliberately left unedited; 944 will be the corrected sample and the divergence is evidence the fix landed.

**Design review — CONCERNS** (`362-review.slice...md`, deepseek/deepseek-v4-flash-0731, 7 findings: 4 pass / 3 concern). All three concerns addressed in the design; no escalation.

- **F001 (function/class endpoint resolution contradicts the "not read" rule)** — **valid, and it was a real contradiction.** Success Criterion 9 said no function/class node is read while Section detail item 6 said their edge endpoints are "resolved to their owning file's layer". Resolved better than any of the three options the reviewer offered: node `id` is `<type>:<filePath>[:<name>]`, and measurement shows the second colon field equals `filePath` for **all 925 nodes**, with no `filePath` containing a colon. Endpoint resolution is therefore a string parse of the edge's own `source`/`target` — **no node is read at all**, so both statements are now true simultaneously. Also measured the stakes: only **16 of 610** `imports`/`depends_on` edges touch a function/class endpoint (2.6%), so this is a correctness guarantee for a small tail, and the design now names the file-level-only fallback if the id contract ever fails.
- **F002 (no failure path for unresolvable edge endpoints)** — **valid.** The fallback covenant said "no third option" and the dependency row had a hole. Added: an endpoint that fails to parse, or that resolves to no file-level node, is excluded from the tally and **reported as drift naming the id**, with the excluded count carried as a `[GAP: ...]` when non-zero. Zero of 2184 edges hit this in the real graph, but that is one graph. Walkthrough step 5b induces both variants against scratch copies and states that a silent-looking pass is a failure of the step.
- **F003 (three sections beyond the architecture's declared four)** — **partly valid, and the specifics were right.** The architecture does list exactly four (line 163) and does assign `project.languages`/`frameworks` to the *concept* doc (line 220). Added a **Section count vs the architecture** subsection grounding each: reading order is **inherited from 361**, not new; coverage is an **architecture-sanctioned slot** (line 89 calls `.understandignore` the reference for "explaining coverage gaps"); project identity is the **one genuine extension**, justified because until 363 lands no artifact anywhere states what the project is — and explicitly marked as the section to drop if the PM disagrees, since nothing depends on it.

Also corrected a stale line while in the file: `.understandignore` was described as "all-comments" while reporting 17 active lines.

**Next:** Phase 5 task breakdown for 362.

### Slice 361: Graph Contract and Provenance — Task Breakdown Complete

**Phase 5 complete.** Tasks at `user/tasks/361-tasks.graph-contract-and-provenance.md` (349 lines, within guideline). Design review came back **PASS** (`361-review.slice.graph-contract-and-provenance.md`, minimax/minimax-m3, 15 findings: 12 pass / 3 note, zero concerns).

**Review notes dispositioned in Task 1.1, no design change:**
- **F013** (`model:` frontmatter field novel, may need schema validation) — **resolved empirically**. The gate delegates to `cf validate frontmatter` ([frontmatter_gate.py:44](src/squadron/events/builtin/frontmatter_gate.py#L44)); squadron owns no schema. Ran `cf validate frontmatter` against `942-analysis.tech-debt-audit.md`, which already carries `model:` — passes. Recorded as a verified fact in the task file rather than left as an assumption.
- **F011** (`config.json`, `.understandignore` unaddressed) and **F012** (`meta.json` `analyzedFiles` unused) — correctly out of scope at 361's proving depth; forwarded to 362 as an in-skill note so that author sees the deferral instead of rediscovering it.

**One deviation from the design, promoted to a blocking task.** The design's walkthrough opens with "Prerequisite: a real graph." Verified at task-authoring time: `.understand-anything/` **does not exist** in this repo. Every verification task depends on it, and generating it runs a marketplace plugin over the whole repo (token cost, writes to the working tree), so it became **Task 0.1** — PM-gated, not unattended. Task 0.1 also carries the stop-and-escalate rule: if the real graph's shape differs from the architecture's documented contract, stop rather than adapt, since upstream drift is this initiative's standing risk.

**Structure:** 8 task groups, 17 tasks, test-with ordering throughout (2.1 author → 2.3 verify, 3.1 → 3.2, 4.1 → 4.2, 6.1 → 6.2/6.3). Five commit checkpoints rather than a single terminal commit. Also verified `.gitignore` currently has no `understand`/`trash` entry, so Task 4.2's first case exercises the create-and-append path rather than the already-present path.

**Task review — PASS**, 10 findings (8 pass / 2 note), zero concerns. Both notes addressed in place (357 lines, still within guideline):

- **F009 (`model:` population not explicit)** — genuine gap, not cosmetic. Task 5.3 listed `model` among the fields but never said it must hold the *generating* model's id, and `cf validate frontmatter` is permissive enough to pass on a placeholder. Tightened 5.3 to require a real id and added a matching check to Task 6.2's success criteria, since the gate cannot catch it. Also wrote the instruction to avoid a hallucination trap: no example model id appears near the requirement, and a model that cannot determine its own id must say so rather than reach for the nearest plausible token.
- **F010 (deferral note owned by 1.1, authored in 2.1)** — reworded 1.1 so it plainly produces a decision rather than skill text, and named Task 2.1 as the authoring owner. A linear reader can no longer mistake 1.1 for incomplete.

**Next:** Phase 6 implementation on branch `361-slice.graph-contract-and-provenance`, starting with the PM-gated Task 0.1.

### Slice 361: Graph Contract and Provenance — Slice Design Complete

**Phase 4 complete.** Design at `user/slices/361-slice.graph-contract-and-provenance.md`; slice plan entry already carried the (361) index. Committed to `main` (planning work, no branch).

Key decisions settled in the design:
- The graph contract lives as named sections **inside** `commands/analysis/understand.md`, not a separate fragment file — `_install_prefix()` installs every pack `*.md` as its own skill, so a fragment would surface as a bogus installable command. Slices 362-364 extend the same file; 365 copies the conventions (no runtime dependency on the pack).
- Three distinct preflight failures with distinct messages: absent graph (points at `/understand`), unparseable JSON, malformed shape (names each bad key + graph version identity). Empty `tour` warns and proceeds; empty `nodes`/`edges`/`layers` reject.
- `.gitignore` idempotency is tested semantically via `git check-ignore -q .understand-anything/.trash-probe/` rather than pattern-grepping, so any equivalent broader ignore satisfies it.
- Gap-marker syntax settled: `[GAP: {what is missing} — {which input would supply it}]`, sibling to the retained `[INFERRED]` convention; markers appear in the body at the point of absence and are listed in provenance.
- Provenance block format specified line-by-line (`## Provenance` directly under the title); generated doc frontmatter matches the 940-series shape (`topic:`, `model:` fields), index = lowest unused ≥ 940.
- All graph reads are field-scoped `jq` selections; missing `jq` stops the run rather than falling back to whole-file reads. No Python added.

**Next:** Phase 5 task breakdown for 361.

## 20260817

### Slice 914: Phase 4 Design Complete — Strict Type Checking Over the Test Suite

Design written to
`project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md`.
Closes the fourth and final step of issue #50 by widening
`[tool.pyright] include` from `["src"]` to `["src", "tests"]` under the existing
`typeCheckingMode = "strict"`.

**Re-measured the baseline rather than trusting the plan's numbers.** Set the
include, ran `pyright --outputjson`, reverted. Result: **905 errors across 104
files**, against the plan's "868 across 234 test files." Both figures were off —
the count drifted up by 37 as slices 909–915 added tests, and 234 was the number
of files *analyzed*, not the number containing errors. The real shape is
concentrated, not broad: the top 10 files carry 45% of all errors and the top 50
carry 90%. That concentration is what made per-directory landing the right call.

**All three open design questions resolved on evidence, two of them against the
assumption in the question:**

- **`MagicMock` noise (D1) — premise is false.** The plan asked whether
  `reportUnknownMemberType` noise on mocks warranted a narrower rule set for
  `tests/`. Of 362 `reportUnknown*` errors, exactly **2** mention `Mock`. The
  unknown-type errors are ordinary missing annotations — untyped lambda params
  (68), unannotated locals (57), unannotated helper signatures (55). A
  per-directory relaxation would have suppressed real annotation debt to solve a
  problem that does not exist. `tests/` runs full strict, no rule overrides.
- **One sweep vs. per-directory (D2) — per-directory.** `include` widens in the
  first commit with `exclude` seeded with every still-erroring test directory;
  each subsequent commit fixes one directory and deletes its line. Pyright
  passes at *every* commit, not just the last — the same principle as 913's D7
  applied to a config key. Ordered cheapest-signal-first: providers/server →
  cli → pipeline → remainder, with `tests/pipeline` (382 errors, 46 files) last
  because it is where the judgment calls live.
- **Fixture factories vs. annotations (D5) — neither, as posed.** A general
  fixture-factory rewrite is a refactor disguised as a type-checking slice, and
  is out of scope. Instead, two helpers identified from the error data erase 110
  errors mechanically. The larger one is a self-inflicted bug: 12 test modules
  wrap `CliRunner.invoke`, and `test_dispatch_run.py:17` annotates the wrapper
  `-> object`, discarding the properly typed `Result` — that single annotation
  causes **all 42** `reportAttributeAccessIssue` errors
  (`Cannot access attribute "exit_code" for class "object"`).

**Two findings that changed the slice's risk profile.** `reportPrivateUsage` is
the second-largest rule at 172 errors — tests importing underscore-prefixed
production symbols (`_execute_summary` ×16, `_write_atomic` ×11,
`_run_pipeline_sdk` ×10, `_REGISTRY` ×9). Pyright has no honest inline
suppression for this; the rule is asking a design question (is this symbol part
of the module's contract?), so D3 resolves each site by re-export/rename with
justified single-line suppression as the fallback. **That means the slice edits
`src`**, and the plan's recorded basis of "test-only; no production code
changes" is stale — risk corrected from Low to **Low-Medium** and effort from
3/5 to **4/5** in the plan entry alongside this design.

Separately, 11 of the 23 `reportUnusedFunction` errors sit on
`@pytest.fixture(autouse=True)` functions — a genuine pyright/pytest idiom
conflict that gets a justified suppression (D4). The other 12 are inspected
individually and deleted if genuinely dead, not suppressed by association.

`reportArgumentType` (175, the largest rule) gets no shortcut: only 9 have the
`monkeypatch.setattr` overload shape, and the other 166 are real mismatches
between what a test passes and what production declares — the errors most likely
to be actual findings. D6 requires any wrong *production* signature discovered
there to be recorded in the completion notes, and records zero if zero: the
slice's value claim is falsifiable rather than assumed.

Verification walkthrough guards the failure mode that matters — a config typo
matching nothing also reports 0 errors, so the walkthrough checks pyright's
`filesAnalyzed` (~444, not ~210) and plants a deliberate type error to prove the
test tree is really being checked.

**Next:** Phase 5 task breakdown for 914. No implementation started; working tree
carries only the design doc and the plan-entry update.

### Slice 913: Complete — Ruff Rule-Set Adoption (`B`, `ASYNC`, `BLE`)

Implemented across three commits, one per rule set, each enabling its rule in
`select` in the same commit that zeroes its violations (design D7) — no commit
in history has a rule live and failing. Branch
`913-slice.ruff-rule-set-adoption-b-async-ble`, merged into `main`.
`pyproject.toml`'s `select` now reads the Python guide's baseline verbatim:
`["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`.

**Part A — `B`.** Added the `B008` `per-file-ignores` entry, then proved it
didn't disable `B` wholesale for the CLI by planting a real `B006` (mutable
default) and confirming it still fired while `B008` stayed silent. Fixed all 54
`B904` sites — 53 with `raise ... from None` (the CLI print-then-`typer.Exit`
pattern, where a chained traceback would be noise on an already-explained exit)
and 1 with `raise ... from exc` (`pipeline/emit.py`, a data-parsing function
that re-raises a different `ValueError` with no user-facing message first).
Fixed the three stragglers (`B905` `zip(strict=True)`, `B007` renamed unused
loop var, `B017` narrowed a blind `pytest.raises(Exception)`).

**Part B — `ASYNC`.** Moved four blocking calls off the event loop via stdlib
`asyncio.to_thread` — the daemon client's `Path.exists()` socket probe
(production I/O path), two test files' `subprocess.run` calls, and a test
mock's `write_text`. Added direct test coverage for both of `_get_client`'s
socket-detection branches, since the existing suite only exercised the
socket-absent path implicitly through a fixture. `sq doctor` confirmed the
daemon client still behaves correctly end-to-end after the change.

**Part C — `BLE`.** The substantive part. Exempted
`project-documents/**/*.py` from `BLE001` only (not `extend-exclude`, per the
design review's D3 narrowing) — verified the glob drops `BLE` from 28 to
exactly the 23 `src` sites while `E,F,W,I,UP` stay enforced on the tree.

Every other site got one of three outcomes. Two matched **issue #49's own
shape exactly** and were fixed as real bugs rather than narrowed or logged:

- `prompt_renderer.py`'s dispatch and summary model-resolution fallbacks
  (`except Exception: model_id = alias; profile = None`) silently reinterpreted
  an unresolvable model alias as a literal model id with no profile — since
  `profile` controls SDK-vs-non-SDK dispatch routing in both call sites, a
  resolver failure could misroute the dispatch. Removed the catch entirely for
  both; a `pool:` misconfiguration (the only way `resolve()` can actually raise
  here, since both callers guarantee a non-`None` alias) now propagates instead
  of silently degrading. `_render_review`'s equivalent site stayed
  caught-and-logged rather than propagated, since there the resolved value is
  display-only — the real dispatch command uses the raw alias independently.
- `cf_op.py`'s `--embed` detection — the exact site issue #49 was filed
  against — was still unfixed. Narrowed to the resolver's actual raisable set
  (`ModelResolutionError`, `ModelPoolNotImplemented`, `PoolNotFoundError`),
  added `logger.exception`, kept the plain-build fallback but made it
  auditable. Fixing this surfaced a second, independent bug: the test
  fixture's mock resolver had no `.resolve.return_value` configured, so it
  silently unpacked to a `ValueError` the old bare `except` had been
  swallowing — the tests had never actually exercised the embed-detection
  branch. Fixed the fixture and added a dedicated resolution-failure test.

`executor.py`'s two fan_out broad catches (branch-model resolution, branch
gather) stayed broad by design — the raisable set is genuinely open-ended
(any exception any branch's step execution can raise) and an invalid
branch-model spec must become a reported `FAILED` step, not a crash — but both
were previously silent on failure; added `logger.exception` to each so a
programming error surfaced this way is still diagnosable. The remaining sites
split roughly evenly between narrowing (7: `client/http.py`, `loader.py`,
`state.py` ×2, `doctor_checks.py`, plus the two above) and justified
keep-broad (13 `# noqa: BLE001`, down from 28 pre-slice violations) — mostly
SDK/subprocess teardown boundaries (`sdk_session.py`, both provider agents'
`shutdown()`) and CLI process boundaries wrapping provider/daemon calls. Every
retained `noqa` was individually read and confirmed to carry both a comment
naming why the boundary must not let anything escape and a nearby
`logger.exception`/`logger.warning(exc_info=True)` call (Task 3.6 audit).

Acceptance test: reintroduced `except Exception: pass` in `pipeline/`,
confirmed `ruff check` failed with `BLE001`, reverted. The failure mode that
produced #49 is now caught mechanically by CI rather than by review — the
actual point of this slice.

Test count grew from the 3016/2-skipped baseline to 3021/2-skipped across the
three parts (new coverage: both `_get_client` branches, the two `BLE`-flagged
sites' resolution-failure paths, and a `state.py` narrowing's previously
untested missing-field path). `ruff check`, `ruff format --check`, `pyright`
(0 errors), and `pytest -q` all pass at each part's gate and at the final
whole-tree check.

Closes steps 1–3 of issue #50 (comment posted). Step 4 (pyright strict over
`tests`, 868 errors / 234 files) remains open as slice 914, sequenced after
this one for review-cost reasons only — the two sweeps are independent.

## 20260815

### Slice 913: Phase 4 Design Complete — Ruff Rule-Set Adoption (`B`, `ASYNC`, `BLE`)

Design written to
`user/slices/913-slice.ruff-rule-set-adoption-b-async-ble.md`. Re-measured every
count against the current tree rather than trusting issue #50's figures, and two
of the drifts changed the design rather than just the arithmetic.

**`B904` is a CLI-shaped problem.** 53 of 54 sites are in
`src/squadron/cli/commands/` — 25 in `run.py` alone — with one straggler in
`pipeline/emit.py`. The plan describes Part A as a codebase-wide mechanical
pass; it is a single-directory pass that happens to touch the same directory as
the `B008` ignore. Far more reviewable than the raw count implies.

**`BLE` is 28, not 23.** The 23-in-`src` figure is correct as far as it goes,
but CI runs `ruff check` with no path argument, so it also lints the tracked
`project-documents/user/reference/codebase-probe.py` — five more sites in a
one-off analysis script that is not packaged, not imported, and appropriately
best-effort. D3 exempts the documents tree from `BLE001` rather than applying
the production exception policy to a document-tree scratch script. Called out
explicitly in both the design and the plan entry: it is the only part of this
slice that narrows what CI enforces instead of widening it.

Decisions worth recording: `B008` gets a directory-scoped `per-file-ignores`
rather than 14 rewrites of the standard Typer idiom (D1), and the verification
walkthrough proves the ignore didn't disable `B` wholesale for the CLI by
planting a real `B006` and confirming it still fails. `B904` picks `from exc`
vs. `from None` per site rather than uniformly (D2) — `ruff --fix` doesn't fix
`B904`, so all 54 are hand-touched regardless and choosing correctly is free.
`ASYNC240` in `client/http.py:42` is fixed with stdlib `asyncio.to_thread`, not
the `anyio.Path`/`trio.Path` the rule message suggests — the project is
asyncio-native and adding a dependency to satisfy a lint message is the wrong
trade (D4). Test-side `ASYNC221` gets the same treatment rather than a `tests/`
exemption, since those tests are what future tests get copied from (D5).

Part C's `BLE` sites get a forced three-way choice — narrow, or keep-broad with
`logger.exception` + justified `# noqa`, or fix a real bug — with "leave it
broad without comment" explicitly excluded (D6). Two sites already look like
#49's shape: `prompt_renderer.py:158` swallows a `resolver.resolve` failure into
`model_id = action_model, profile = None`, silently degrading an unresolvable
model into a wrong-but-plausible dispatch; and `executor.py:1603` converts any
exception — including a programming error inside the `try` — into a `FAILED`
StepResult with a bare message and no traceback. D6 caps the blast radius: a
genuine bug of more than trivial size gets filed and fixed in its own slice, not
absorbed under a lint banner.

Rule sets are enabled one part at a time (D7), each in the commit that zeroes
it, so no part leaves the build red and `git bisect` stays meaningful. The
acceptance test for the slice is reintroducing #49's shape and watching CI catch
it.

### Slice 913: Design Review — PASS, D3 narrowed in response

Review at `user/reviews/913-review.slice.ruff-rule-set-adoption-b-async-ble.md`
(minimax/minimax-m3, reviewed `df47148`): **PASS**, eight pass findings and two
notes, no blockers.

**F009 acted on.** D3 originally read `extend-exclude = ["project-documents/"]`,
dropping the whole tree from ruff. The reviewer's objection is correct and
sharper than the tradeoff I recorded in the design: excluding the directory
discards `E`/`F`/`W`/`I`/`UP` on a file that passes them today, not merely on
hypothetical future scripts — a coverage reduction well past the problem, which
was five `BLE001` sites in a best-effort probe. Narrowed to a rule-scoped
`per-file-ignores` entry (`"project-documents/**/*.py" = ["BLE001"]`), which
gives up only the rule that does not fit and keeps everything else live.
Verified against the tree before committing rather than assuming the glob
resolves: with the entry applied, `BLE` drops from 28 to exactly the 23 `src`
sites and `ruff check --select E,F,W,I,UP project-documents/` still passes. The
rejected alternative is recorded in D3 so it is not re-litigated at
implementation. Success criteria gained an explicit "no `extend-exclude` is
added" check and the walkthrough a step proving the tree kept its other
coverage.

**F010 accepted without change.** Document weight is high against the
architecture's "lighter-weight given the maintenance nature" guidance, and the
reviewer allows the complexity is defensible — the density sits in D6 and the
re-measured baseline, which are the two things that caught real problems. Noted
as a calibration point, not an alignment failure.

One review defect, not verdict-affecting: F008's `location` points at the
success criteria, but the "reintroduce #49's shape" step it praises is in the
verification walkthrough. Body text names the right section; only the field is
off.

### Slice 913: Phase 5 Task Breakdown Complete

Tasks at `user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md` — 386
lines, no split needed. Fifteen tasks across the three parts plus a final
verification group, sequenced A → B → C with each part's `select` change landing
in the same task that zeroes its rule (D7), so no commit in history has a rule
enabled and failing.

Sized the mechanical work against per-file counts rather than totals, which
changes how Part A is executed: Task 1.3 works largest-file-first —
`run.py` (25 of the 54 `B904`), then `skills.py` and `dispatch_run.py` (4 each),
down to six single-site files. A 54-site diff is unreviewable; a 25-site diff in
one CLI module is not.

Two tasks exist purely to prove a suppression didn't overreach, both derived
from decisions the design made rather than from the rule counts. Task 1.2 plants
a genuine `B006` in a CLI module and requires it to fire, proving the D1 `B008`
ignore didn't disable `B` wholesale for that directory. Task 4.2 inventories the
final suppression set and asserts `extend-exclude` appears nowhere — the F009
narrowing is easy to silently undo at implementation time by reaching for the
simpler form when the glob looks fiddly.

Part C's task split follows blast radius, not file count. Task 3.2 isolates the
two sites already identified as issue-#49-shaped
(`prompt_renderer.py:158`'s silent degradation to a wrong-but-plausible
dispatch, `executor.py:1603`'s tracebackless failure conversion), and Task 3.3
is the only new-test task in the slice — those two are the sites where behavior
actually changes. The remaining 21 are narrowings covered by the existing suite,
split by subsystem (3.4 pipeline, 3.5 CLI/provider/client/core/events). Task 3.6
gates on reading every retained `noqa` before `BLE` is enabled, since a
`noqa` without justification is a failed criterion rather than a passing one
with a note.

Task 3.4 carries a specific instruction to read issue #49 before touching
`actions/cf_op.py` — it is the module that defect lived in, and its remaining
broad catch should be confirmed not to be a second instance of the same bug.

Task 4.1 is the slice's acceptance test: reintroduce `except Exception: pass` in
`pipeline/`, confirm `ruff check` fails, revert. If that step doesn't fail, the
slice didn't deliver what it claims regardless of the violation count.

Also carried into the tasks: the frontmatter gate rejects hyphenated status
values (`not-started` failed the pre-commit hook when the design was first
written), so Task 4.3 names the accepted set explicitly.

### Slice 913: Task Breakdown Review — CONCERNS, three acted on

Review at `user/reviews/913-review.tasks.ruff-rule-set-adoption-b-async-ble.md`
(minimax/minimax-m3, reviewed `7174524`): **CONCERNS** — six pass, five concerns,
two notes. Three concerns acted on, two declined with reasons.

**F011 acted on** — the sharpest of the five. Task 1.3 spans 13 files, and
nothing told the implementer not to commit partway through; doing so would leave
a commit with the `B904` fixes but without `B` in `select`, the exact inverse of
D7's contract. Added an explicit "do not commit here, Part A lands as one commit
at Task 1.5" bullet naming 1.1/1.2/1.4 as well.

**F008 acted on.** Task 3.2's scope guard was judgmental ("if it turns out to be
a larger fix"), which is not a usable stopping rule for someone who has not read
the resolver. Replaced with three observable triggers — the fix needs a file
outside the two named modules, it changes a signature or return type, or the
raisable set is not determinable from the resolver and its direct callees. Also
stated that taking the guard is a *passing* outcome, not a failure, since an
implementer who reads a stopping rule as an admission of defeat will push
through it.

**F007 acted on, but not as suggested.** The concern is real: Tasks 3.4/3.5
narrow ~18 sites and lean on "the existing suite", and a narrowing that changes
an untested path passes the suite by construction. The reviewer's proposed fix —
review `--tb=long` output during the gate — does not address it, since that shows
tracebacks for failing tests and these paths are silent when they change. Fixed
instead by extending Task 3.6 into a per-site audit: for every narrowed site,
record what now escapes and where it lands, and name the existing test covering
that failure path or add one. Retitled and re-rated 1/5 → 2/5.

**F009 declined.** The reviewer notes `extend-exclude` is mentioned repeatedly
but never installed, and self-resolves it in the same paragraph ("no action
needed... flagging only because a reviewer scanning for scope items might
miscount"). The repetition is deliberate: it is the F009 narrowing from the
*design* review, and the negative assertions in Tasks 3.1 and 4.2 exist so the
simpler rejected form is not reached for at implementation time.

**F010 declined.** Suggests the acceptance probe also exercise `B904` and an
`async` variant. Task 4.1 tests one specific claim — that #49's shape is now
caught mechanically — and `except Exception: pass` is exactly that shape. `B`
and `ASYNC` are already gated by their own zero-violation checks at Tasks 1.5
and 2.5; re-probing them in 4.1 tests ruff rather than the slice. Declining keeps
the acceptance test pointed at the thing the slice claims.

F012 (Part C is the largest commit) and F013 (no load test needed) were
informational and need no change.

---

## 20260813

### Slice 915: Complete — Loop Checkpoint-Pause Resume Correctness

Phase 6 complete, three commits landed as separable parts per the design's
bisect requirement. **Part A** (`6a0db23`): `first_unfinished_step` filters on
status (`PAUSED`/`FAILED` via `_RESUMABLE_STATUSES`, never string literals)
instead of mere presence, so resume returns *to* a paused or failed step
rather than past it — fixing both the loop-abandonment bug and the identical
`FAILED`-step skip in one predicate change. `resume_iteration_for` gives
`StepState.iteration` its first reader. Audited the two non-resume callers of
the changed predicate the design hadn't accounted for (`run.py`'s prompt-only
`--next` finalizer and `--step-done`'s next-step lookup) — neither needed
adjustment, since `completed_steps` was already append-only with no
uniqueness assumption. Two integration tests asserted the pre-fix step count;
updated from 10 to 11 since the resumed step now legitimately re-executes and
is recorded twice.

**Part C** (`3f4a84f`): a loop that short-circuits on an inner pause now logs
a WARNING — pipeline, step, paused round, rounds not run — from one shared
helper covering both loop shapes (`_execute_loop_step` single-action,
`_execute_loop_body` multi-step), so the signal that would have made #48
self-reporting instead of silent is single-sourced rather than duplicated.

**Part B** (`04f4a7e`): `execute_pipeline` gains `start_from_iteration`,
threaded only to the `start_from` step's loop; both loop executors gain
`start_iteration`, replacing the hardcoded `range(1, max+1)`. A resume
request above the loop's `max:` (only reachable from malformed state) fails
loudly with a WARNING rather than silently reporting `COMPLETED` for zero
rounds run — re-creating the exact defect class this slice fixes was the one
thing to avoid here. Both resume paths in `run.py` (`--resume` and implicit
paused-run detection) now read the round through one shared helper. End-to-end
coverage proves the `max:` counting rule directly: a loop paused at round 2 of
3 resumes at round 2, not round 1, and runs at most rounds 2–3.

Verification followed 910's precedent exactly rather than a live `sq run`:
copied all 22 new/updated tests into a `git worktree` at the pre-fix commit
and confirmed every one fails there, proving they'd have caught the original
bug. `--validate`/`--dry-run` (no live model calls) were run against the
operator's real `p45b.yaml` as a sanity check; live pause/resume against
actual Claude dispatch/review calls was declined — real API cost and writes
to the operator's real run state for evidence the test suite already covers
more precisely. Corrected the design doc's line citations to match the
implemented code (several drifted when the Part A audit finding and small
resume-path helpers landed).

Filed #59 for the known limitation this slice records rather than fixes:
`each:`/`fan_out:` steps return no `iteration`, so Part A stops them being
silently skipped on resume but they still restart from the top rather than
re-entering mid-branch — a per-branch completion record is a larger
data-model change than the single integer `loop:` needed. Documented the
resume contract (round counting, empty `prior_iteration_step_outputs` on
re-entry, the WARNING/INFO signals, the `each`/`fan_out` limitation) in
`docs/PIPELINES.md`'s `loop` section. Closes #48.

---

## 20260812

### Loop Backlog Triage; Slice 915 Designed

Went to address the four open "loop bugs" and found three of them were
already fixed. Slices 910 and 911 shipped in v0.9.0 and closed only #44 at
merge time — #42 (findings feedback between iterations), #43 (ambiguous
`until:` with multiple verdict-bearing actions), and #45 (`--dry-run` loop
expansion) stayed open despite their fixes being live. Verified each against
`main` before closing: `running_prior` threading in `_execute_loop_body`,
`_validate_verdict_count` in `LoopStepType`, and the loop-expansion branch in
`--dry-run` rendering are all present. Closed all three with pointers to the
implementing commits. Housekeeping gap, not a code gap — worth noting that
merge-time issue closure is manual and was missed for a whole slice.

That left **#48** as the only real remaining loop defect, and it is not small:
a checkpoint firing inside a loop body pauses the run, the loop step is
recorded as *completed* anyway, and resume skips it — silently dropping every
remaining round. `on-concerns` fires on CONCERNS/FAIL/UNKNOWN, so a retry loop
that pauses for human review hits this on its first non-passing round, which
is precisely the case the checkpoint exists to serve.

Traced the mechanism end-to-end against `main` (the issue's line citations had
drifted since 305 and 173 landed). Four points confirmed: the loop
short-circuits on inner `PAUSED` (preserving `iteration`), `on_step_complete`
runs two lines *before* the `PAUSED` early-return, `_append_step` appends
unconditionally, and `first_unfinished_step` builds its completed-set from
step *names* without ever inspecting status. Two findings shaped the design:
`StepState.iteration` is written and never read anywhere in the repo — the
re-entry coordinate is already persisted, just unused — and `start_from` is
step-name granular, with no notion of resuming *into* a step at a round.

Designed slice **915** (`900` plan, sequenced after 910/911) with three parts:
status-aware `first_unfinished_step` (also fixes the identical `FAILED`-step
skip), a `start_from_iteration` coordinate threaded to the loop's range, and a
WARNING when a loop abandons rounds. Answered the issue's open question rather
than deferring it again (910/911 precedent): **a checkpoint-paused loop is
re-enterable** — `until:` is the loop's contract and a pause is not a verdict,
`checkpoint: continue` already means "keep going," and "a human takes over"
already has a spelling in `Exit`. Rejected making it configurable; the knob
would double the resume test surface for a mode nobody asked for.

Recorded one known limitation rather than conflating it: `each:`/`fan_out:`
return no `iteration`, so Part A stops them being skipped but they resume by
restart, not re-entry.

---

## 20260811

### Slice 173: Complete — User-Definable Actions on Supported Events

Phase 6 complete. Built `squadron/events/` (types, contexts, protocol,
namespaced registry, `events.yaml` manifest loader, declared-import plugin
discovery, dispatcher) and migrated the hardcoded 909 dispatch-artifact
post-condition and 911 revision-number stamp off `executor.py` onto it as
`squadron.dispatch-artifact` and `squadron.revision-stamp` — the acceptance
test — with zero assertion changes in the existing tests (they exercised
`execute_pipeline` end-to-end, never the private helpers by dotted path, so
no patch-target strings needed to move). `squadron.frontmatter-gate`
refactors 172's bespoke installer-driven gate onto the mechanism as a
`COMMIT`-bound built-in. `sq events fire` / `sq events list` ship as a Typer
sub-app; `.githooks/pre-commit` and `setup_install.py`'s `PRE_COMMIT_HOOK`
repoint from `cf validate frontmatter` to `sq events fire commit`, byte-
identity test intact. `sq run --step-done` now runs `POST_ACTION` bindings
before recording a step done, closing the prompt-only parity gap from
issue #15 — a bug in that wiring (the `{slice}` placeholder wasn't resolved
against the run's own params before reaching the event context) was found
during the manual verification walkthrough and fixed, with a regression
test asserting the resolved value reaches the dispatcher.

Four commits (Parts A+B combined since `bootstrap_event_actions()` imports
all three built-ins together, forcing `frontmatter-gate` in ahead of its
originally-planned Part C slot; then Part C; then Part D; then docs).
`docs/EVENTS.md` is new; `docs/PIPELINES.md`, `docs/COMMANDS.md`,
`CHANGELOG.md` (two flagged breaking changes), and
`140-arch.pipeline-foundation.md` (deferred-171 section replaced with what
173 actually built) are updated. Full suite: 2991 passed, 2 skipped;
pyright strict and ruff clean throughout. Slice marked complete; slice-plan
entry 28 checked.

---

### Slice 173: Task Breakdown — User-Definable Actions on Supported Events

Phase 5 complete. Task file at
`user/tasks/173-tasks.user-definable-actions-on-supported-events.md` (284
lines, 24 tasks in five parts, test-with ordering, commit checkpoint per
part). Part order preserves the design's reasoning: A events package →
B migrate 909/911 (the acceptance test — T12 instructs STOP if any existing
assertion needs changing) → C frontmatter gate + `sq events` CLI + hook
repoint → D prompt-only `--step-done` parity → E docs/closeout. Slice is
ready for Phase 6 implementation on branch
`173-slice.user-definable-actions-on-supported-events` pending PM approval.

---

## 20260809

### Slice 173: Design — User-Definable Actions on Supported Events

Phase 4 complete. Design at
`user/slices/173-slice.user-definable-actions-on-supported-events.md`;
slice-plan entry 28 marked Design Complete. Supersedes deferred 171, whose
authority/failure-mode/ordering contracts carry forward cited.

The one open question from the overview — `ActionContext` vs. a narrower
event context — resolved for the narrower context (D1): `ActionContext`
demands `resolver`, `run_id`, `step_index`, `prior_outputs`, none of which a
commit has, and lacks the staged paths it does have; reusing it would mean
placeholder values, which the no-silent-fallback rule bans. Event actions get
an event-typed context family (`CommitContext`, `PostActionContext` — the
latter is 171's `HookContext` renamed) while sharing `ActionResult`,
`ValidationError`, and the registry idiom. The pipeline `Action` protocol and
registry are untouched; the events registry is the third instance of the
established Protocol-plus-registry pattern, alongside actions and gate
policies.

Other decisions: closed `EventType` enum (D2); mandatory dotted namespacing
with collision/reserved-prefix guards (D3); observe/fail/mutate authority with
no severity axis — the revision stamp's never-fail contract is its own
behavior, not a runner clamp (D4); coarse attributed failure handling, hard
exit, never skip (D5); `events.yaml` manifest project → user first-found with
in-code `DEFAULT_BINDINGS` and a `disable:` list (D6); declared-import
discovery, no scanning (D7); `sq events fire commit` as the process entry
point, with the 172 hook and installer repointed onto it (D8); prompt-only
`--step-done` parity carried from 171 unchanged (D9). Migration of the
hardcoded 909/911 executor checks onto the mechanism is the acceptance test —
no assertion in their existing tests may change, only patch targets.

---

### Slice 172 Part 10: Retire the Parallel Validator, Install the Gate Everywhere

Context Forge 0.12.0 shipped `cf validate frontmatter` (cf#72/#73), unblocking
Part 10 (T27–T32). Slice 172 is now complete.

**Retired.** `documents/validate.py`, `cli/commands/validate.py`, their tests,
and the `validate.docs_root` config key are deleted; `sq validate` is gone.
`schema.py` is reduced to the values squadron writes (dropped the
required-field tuples and the managed-marker constant; kept the enums, aliases,
and machine-artifact docTypes — all still imported by writers or the
literal-scan test).

**The gate.** `.githooks/pre-commit` runs `cf validate frontmatter` on staged
`.md` files; `cf` missing on PATH is a hard exit 1, and cf exit 2 (invocation
error, e.g. an unregistered cf project) gets its own message pointing at
`cf init`. `sq setup` now installs the gate without prompting: `setup_install.py`
carries the hook as `PRE_COMMIT_HOOK` (byte-identity with the tracked copy is
test-pinned), `_install_git_hook` writes it and sets `core.hooksPath` —
refusing to overwrite a foreign hooksPath — and `AUTO_INSTALL_CHECKS` marks it
as run-without-asking (D11). `check_git_hooks` now takes `cf_available`; an
installed hook without `cf` reports WARN "gate cannot run" in `sq doctor`, and
`sq setup` now resolves and passes the hooksPath (it previously never saw the
hook check at all).

**Drift test repointed at cf.** `test_schema_drift.py` no longer parses
`file-naming-conventions.md`; it writes fixtures into the document root and
runs `cf validate frontmatter --json`, asserting `filesChecked` on every call
because cf silently skips out-of-root paths (exit 0, 0 checked — a naive test
would false-pass). Probing cf's schema showed it validates only 8 of the 15
spec docTypes (`guide`, `reference`, `slice`, `notes`, `template`,
`intro-guide`, `migration` fall through unvalidated), so the status assertions
run against `review` — the one docType squadron writes, which cf does
validate. The machine-artifact test pins that cf requires neither `status` nor
`dateUpdated` for `review-resolution`/`gate-evidence`/`devlog` (T32, landed in
cf under #73).

---

## 20260804

### Slice 172: Implementation — `sq validate docs` Mechanical Frontmatter Enforcement

Implemented all 26 tasks across 10 parts on branch
`172-slice.sq-validate-docs-mechanical-frontmatter-enforcement`, in 12 commits
that follow the design's ordering constraints (writer fix before cleanup,
cleanup before CI).

**The validator.** `documents/schema.py` defines `DocumentStatus`, `DocType`,
and the machine-artifact docType set in one place; a drift test fails (never
skips) if they disagree with `file-naming-conventions.md`. `documents/validate.py`
implements the eight `FM001`–`FM008` checks as a pure function —
`validate_document`/`validate_paths` return `list[Violation]`, no printing, no
`sys.exit` — wired into `sq validate docs` via a new `validate.docs_root`
config key (default `project-documents/user`).

**The writer fix and the hardening.** `review/persistence.py:222` now quotes
`location` through `yaml_escape`, closing the exact defect that corrupted five
review artifacts. `documents/frontmatter.py`'s `update_frontmatter` and
`render_frontmatter_block` now raise on a present-and-invalid top-level
`status`, and `update_frontmatter` gained a required `today=` keyword that
stamps `dateUpdated` on every call — squadron's only in-place document edit
(`executor.py`'s `revision_number` stamp) now keeps that date current, and the
devlog stub and append path were brought in line with the same rule.

**Cleanup, gate, and CI.** All 27 pre-existing violations were fixed in one
commit, separate from the feature work: the five corrupted reviews (quote
`location`), six non-canonical `status` values (three mechanical, three judged
from document content — e.g. `superseded` on a design replaced by a later
slice became `deprecated`, not left as-is), three missing `status` fields on
fully-checked-off task files (`complete`), eleven `task-breakdown`/`slice-tasks`
docTypes (`tasks`, confirmed unread by any source), and two documents with no
frontmatter block. `.githooks/pre-commit` ships tracked and executable;
`sq doctor` reports whether `core.hooksPath` is set to it. CI gained
`submodules: true` and a `sq validate docs` step, landing only after the
cleanup commit so the branch's own CI history is never red between two
commits of the same slice.

**T21's cross-check found a real bug, not a hypothetical one.** Running
`cf check --fix` against this repo (not just re-reading its source) showed one
of context-forge's thirteen `update-frontmatter` fix actions writing
`status: in-progress` — hyphenated, disagreeing with `VALID_STATUSES` — into
`900-arch.maintenance-and-refactoring.md`. Root cause: `introspection/types.ts`'s
`STATUS.InProgress`/`STATUS.NotStarted` constants are hyphenated while
`schema/frontmatterSchema.ts`'s `VALID_STATUSES` (and the spec) are
underscored — two enums for the same values, and at least 6 of 13 fix actions
reference the wrong one. `FM005` caught it correctly; the bad write was
hand-corrected and filed as
[context-forge#72](https://github.com/ecorkran/context-forge/issues/72),
distinct from #71 (the `dateUpdated`-stamp gap, already tracked). Two of
`cf check --fix`'s other proposed changes were declined outright — marking
this slice's own parent architecture (140) complete mid-implementation, and
marking a slice (344) complete when its own frontmatter says `deprecated` and
its body says "DEPRECATED / DESCOPED, not merged."

**Full verification:** `uv run ruff check`, `uv run ruff format --check`,
`uv run pyright`, `uv run pytest` (2960 passed, 2 skipped), and
`uv run sq validate docs` (413 documents, 0 violations) all clean. All nine
Verification Walkthrough steps run in order and matched the design, with two
corrections folded back into it: the `update_frontmatter` probe command needed
`today=`, and D8a's `cf check --fix` claim was updated from "verified by
reading source" to "verified by running it, with one exception found and
filed."

---

### Slice 172: Date-Field Audit — `dateCreated` Everywhere, `dateUpdated` on Every Write

Audited how `dateCreated` and `dateUpdated` are produced across squadron and
Context Forge, and folded the result into the 172 design and tasks. The rule
being enforced: `dateCreated` belongs on every created file; `dateUpdated`
belongs on every file edited after creation, and its absence means "never
edited."

**Measurement first.** All 413 documents under `project-documents/user/` were
scanned: zero missing `dateCreated`, zero missing `dateUpdated`, zero with
`dateUpdated` earlier than `dateCreated`. The authored side complies in full.
Also corrected an earlier miscount — a `grep` for `resolution`/`gate.` had
matched *slice names*, not artifacts. There are **zero** `review-resolution`
and **zero** `gate-evidence` files in the corpus, so the emitter fixes below
carry no cleanup and no back-compatibility constraint.

**The split that decides the validator's shape.** `dateCreated` is checkable
from a single file. `dateUpdated` presence is not — no tool reading one file
can know whether that file was ever edited. So the validator requires
`dateCreated` of both document classes and never requires `dateUpdated`; the
second half is a writer-side obligation. This also corrects D2, which had
described the machine artifacts as a blanket exemption from date fields. The
right classification is per-artifact, by whether the thing is ever rewritten:
`review-resolution` is append-only and already correct, `gate-evidence` needs
`dateCreated`, and `devlog` is the only artifact rewritten in place.

**Three squadron write paths did not stamp.** `gate_evidence_frontmatter`
emits no date at all; the devlog stub emits only `docType`; and
`executor.py:269` — the only in-place document edit squadron performs —
stamps `revision_number` into slice and task documents while leaving the dates
untouched. D8 now puts the stamp inside `update_frontmatter` itself, taking
`today` as a required keyword rather than calling a clock inline. Placing it
there rather than at the call site is what makes the rule hold for callers
that do not exist yet. The evidence that a hand-maintained convention does not
survive: this file's own frontmatter read `dateUpdated: 20260803` while
carrying a `20260804` entry.

**Context Forge boundary, written down as D8a.** Both tools validate
frontmatter in the same tree, so the division of labor is now stated rather
than assumed. `cf check` owns per-`docType` schemas (eight docTypes; unknown
ones pass through at `frontmatterSchema.ts:210`) and cross-document
consistency; `sq validate docs` owns structural integrity and universal
fields, for every docType including squadron's own. Three conflict surfaces
were checked and are clear: all thirteen `update-frontmatter` fix actions in
`ConsistencyChecker.ts` write only `status`, from the same five canonical
values `FM005` accepts; CF's `FILENAME_PARTS_RE` cannot match
`{index}-resolution.…` or `{index}-gate.…`, and its docType inference fires
only when `docType` is absent, which squadron's emitters never leave it. The
load-bearing consequence is negative: `FM004` must **not** require
`dateUpdated`, because CF requires it and backfills it from `dateCreated`
(`frontmatterSchema.ts:224`) — requiring it here too would make squadron's
hook *block* commits on documents CF considers valid and fixable.

CF has the mirror-image gap: `updateFrontmatterField`
(`markdownWriter.ts:52`) writes one key and leaves `dateUpdated` alone. Filed
as [context-forge#71](https://github.com/ecorkran/context-forge/issues/71).
Tracked, not a dependency — 172 fixes only squadron's half.

**Changes.** Design: D2 rewritten per-artifact with the date rule and an
emitter table; D8 extended with the stamp; D8a added for the CF boundary;
components list extended by three files; criteria 21–24 added; the
`dateUpdated < dateCreated` ordering check recorded as Future Work rather than
added as a ninth code, since it has zero violations today and would enforce
nothing on arrival. Tasks: T1 gains
`MACHINE_ARTIFACT_REQUIRED_FIELDS` and an explicit prohibition on requiring
`dateUpdated`; new Part 5A (T23–T26) covers the stamp, the emitters, and a
test that squadron's own rendered output validates clean; T21 gains a
`cf check --fix` then `sq validate docs` cross-check. Task numbers are
append-only — renumbering T1–T22 would invalidate every reference in the
design, the reviews, and this log.

---

### Slice 172: Task Review Resolved — CONCERNS, Both Findings Real

Reviewed by `minimax/minimax-m3`:
[172-review.tasks.…md](project-documents/user/reviews/172-review.tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md).
Verdict CONCERNS on two findings, six passes, two notes. Both concerns were
right, and the first one turned out to be hiding a worse problem than the
review described.

**F001 — success criterion 6 had no implementing task.** Correct: SC6 says no
status or docType literal survives outside the enum module, T21's close-out
greps for it, and nothing in between actually removed any. There are five such
sites — `review/persistence.py:187` (`"docType: review"`) and `:195`
(`"status: complete"`), plus the three machine-artifact constants in
`resolution_artifact.py:25`, `evidence.py:26`, and `devlog.py:104`.

Writing the fix exposed the real defect. T1 said to *source* the
machine-artifact docTypes from those three modules — `documents/schema.py`
importing from `review/` and `pipeline/`. That inverts the layering
(`documents/` is the shared primitives package) and, once T13 makes
`frontmatter.py` import `schema.py` for the status check, it is a literal
import cycle: `documents.frontmatter` → `documents.schema` →
`review.resolution_artifact` → `documents.frontmatter`. Reversed: `schema.py`
defines all three values and the emitting modules import them. That is also
what makes SC6 true rather than aspirational.

Rather than renumber 22 tasks to insert a sweep, each literal now lands in the
task that already owns its file — the three constants in T1, the two
`persistence.py` lines in T11, which is already editing that function. And SC6
gets teeth: T12 adds a test that greps `src/**/*.py` for the enum members,
driven by the enum so a value added later is covered without editing the test.
A criterion enforced only by a grep in a close-out checklist is one that
silently rots.

**F002 — function-name mismatch between SC8 and T5.** Real mismatch, but the
review's recommended direction was backwards. It proposed changing SC8 to
match T5; both function pairs exist (`render_gate_evidence` /
`gate_evidence_frontmatter`, `render_resolution` / `resolution_frontmatter`),
and SC8 named the better ones. The validator reads *files*, so the test must
render the whole document — fence included — not just the frontmatter mapping.
T5 now uses the full-document renderers, with a line saying why.

**F008/F009 (notes)** — no action. T4's size is cohesive (one function, one
acceptance condition), and T19's manual walkthrough is deliberate: a git hook
is not meaningfully testable without actually attempting a commit.

---

## 20260803

### Slice 172: Task Breakdown Complete

[172-tasks.…md](project-documents/user/tasks/172-tasks.sq-validate-docs-mechanical-frontmatter-enforcement.md)
— 22 tasks across 9 parts, 402 lines, test-with throughout.

**Sequencing is the one thing this breakdown adds that the design left
implicit.** Three orderings are load-bearing and each is called out in the
task file rather than left to be discovered:

1. The review-writer fix (Part 4) lands *before* the cleanup (Part 6).
   Reversed, a single review written between the two commits reintroduces the
   corruption the cleanup just removed.
2. The cleanup lands *before* CI (Part 8). Reversed, `main` is red between two
   commits of the same slice.
3. `schema.py` and its drift test come first, because every later part imports
   the values and the whole slice is an argument about defining them once.

Two implementation details worth pinning down now rather than during Phase 6.
`sq doctor`'s hook check must stay pure — `doctor_checks.py`'s docstring
promises no subprocesses — so the resolved `core.hooksPath` is obtained in
`doctor.py` via the existing `run_git` (`review/git_utils.py:19`) and passed
in. And the cleanup task deliberately refuses to carry a transcribed list of
the 24 violations: it says to run the validator and use its output, then
compare. A work list copied into a document is stale the moment something else
touches the tree.

The `FM002` fixture is specified as the real defect string
(`location: Slice design: Implementation Details`) rather than a synthetic
colon, per the project rule that a parser's test fixture must include the
format it will actually consume.

---

### Slice 172: Design Review Resolved — PASS, One Pass Finding and Six Notes

Reviewed by `minimax/minimax-m3`:
[172-review.slice.…md](project-documents/user/reviews/172-review.slice.sq-validate-docs-mechanical-frontmatter-enforcement.md).
Verdict PASS. Three of the six notes were worth acting on; all three turned out
to be about the *architecture* being stale, not the slice being wrong.

- **F001 (pass)** — the slice's positioning against deferred 171 reads correctly.
  No action.
- **F002 (note) — planned module names.** The architecture reserved
  `documents/status.py` (DocumentStatus) and `documents/paths.py`
  (`USER_DOCS_ROOT`), both marked "171 — DEFERRED." 172 builds `schema.py`
  instead (status *and* docType *and* the machine-artifact set belong together)
  and replaces `USER_DOCS_ROOT` with the `validate.docs_root` config key — a
  module constant is the wrong shape for a value that differs per project.
  Fixed at the source: the architecture's package structure now names
  `schema.py` and `validate.py`. Leaving two placeholder filenames in place
  would have set a revived 171 up to define a second `DocumentStatus`, which is
  precisely the drift this slice exists to prevent.
- **F003 (note) — "CI/CD integration" is listed out of scope.** The reviewer's
  own reading is right: that bullet sits among GUI-for-pipeline-monitoring,
  cross-slice parallelism, and pipeline marketplace — it means *running
  pipelines as CI jobs*, not "squadron's repo may not have CI steps," which
  would be a strange thing for a document to say about a repo that already runs
  ruff, pyright, and pytest in CI. Narrowed the bullet's wording so nobody
  re-litigates it.
- **F004 (note) — cross-package edit to `review/persistence.py`.** Accepted, no
  change. The `documents/` package owns the primitives; `review/` owns its own
  rendering, and the fix is a one-line change to a `review/` file that produces
  invalid documents today. The boundary-respecting version — render that block
  through `render_frontmatter_block` — is already recorded as Future Work, held
  up by test coupling to the exact rendered text, not by the boundary.
- **F005 (note) — the architecture's own example teaches the bug.** Correct and
  worth fixing. Its structured-findings sample quotes `summary` and leaves
  `location` bare, the exact asymmetry D9 removes. The sample values happen not
  to contain a colon-space so it is valid YAML, which is the problem: it looks
  fine and reproduces the pattern. Both example locations are now quoted, with
  a comment saying why.
- **F006 (note)** — no NFRs apply. No action.
- **F007 (note) — implicit edge cases in the exit-code contract.** The real
  gap. Added `FM008` (file under the root not decodable as UTF-8) and rewrote
  the exit-code paragraph around *who is wrong*: exit 2 means the command was
  called incorrectly and no validation happened (missing root, missing named
  path, permission/IO fault); anything about a document's content, including
  undecodable bytes, is a violation on exit 1. Success criterion 10 now
  enumerates the cases a CLI test must cover, and criterion 4 counts eight
  check classes.

One aside worth recording: this review artifact is itself another instance of
the unquoted `location:` render — its seven finding locations are bare scalars
carrying `.md#anchor` values. It parses (verified: 7 findings, verdict PASS)
only because no anchor happens to contain a colon-space. The corruption class
is not historical; it is one review away, in every review squadron writes.

---

### Slice 172: `sq validate docs` — Slice Design Complete

Phase 4 design for the replacement 171 made room for:
[172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md](project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md).
Five pieces — the validator, a tracked pre-commit hook, a CI backstop with a
one-time cleanup, status validation on squadron's own frontmatter writers, and
a fix to the review writer. Effort holds at 1/5.

**The design was written against a scan, not against a hunch.** All 409
markdown documents under `project-documents/user/` were checked: 24 violate the
spec. Six carry a non-canonical `status` (`active`, `draft` ×2, `in-progress`,
`not-started`, `superseded`), three are missing `status` entirely, eleven use a
`docType` outside the canonical list (`task-breakdown` ×10, `slice-tasks`), and
two have no frontmatter block.

**The fifth class was invisible and is the most interesting.** Five review
artifacts have frontmatter that *looks* correct and does not parse — a finding's
`location:` value carries a colon-space (`location: Slice design:
Implementation Details`), which YAML reads as a nested mapping. `read_frontmatter`
returns `None` for a YAML error exactly as it does for a file with no block at
all, so nothing distinguished "no metadata" from "corrupted metadata" until a
scan asked directly. The consequence is a hard failure at a distance:
`metrology/identity.py:180` raises `MetrologyTargetError` and
`review/resolution_evidence.py:132` raises `ResolutionError`, so
`sq metrology capture` and `sq review resolve` cannot process those five files.

The producer is squadron. `review/persistence.py:222` renders that line as an
unquoted f-string while its neighbor on line 220 quotes `summary` through
`yaml_escape` — the two fields carrying model-authored free text, one guarded
and one not. The slice quotes `location` and repairs the five artifacts. The
larger fix (render the whole block through `render_frontmatter_block`, as gate
evidence and resolution artifacts already do) is recorded as future work: it is
correct, and several test modules assert on the exact rendered text, so it is
its own unit.

**Decisions worth their own line.** Scope is a configured document root
(`validate.docs_root`, default `project-documents/user`), because a repo-wide
sweep would flag `README.md`, `CLAUDE.md`, `docs/*`, `commands/sq/*.md`, and
`.claude/agents/*.md` — all correctly frontmatter-free. Paths given on the
command line are *filtered* against that root rather than trusted, which is what
lets the hook hand over the entire staged file list without knowing anything
about document conventions. Squadron's own machine artifacts (`review-resolution`,
`gate-evidence`, `devlog`) land inside the root and legitimately carry no
`status`, so they are a recognized second document class — a gate that fires on
its own tool's correct output is how people learn to use `--no-verify`. Seven
check classes, each with exactly one mechanical fix; no `--fix` mode, since
`draft` and `superseded` have no unambiguous target and a hook that silently
rewrites staged documents is worse than one that stops.

Drift against the spec — the risk that ended 171's frontmatter consumer — is
handled by a test that parses `file-naming-conventions.md` and compares it to
the enums, failing (never skipping) when the submodule is absent. That needs
`submodules: true` on the CI checkout; `ecorkran/ai-project-guide` is public, so
no token.

Slice plan entry 29 updated with the design link and the corruption finding.

---

### Slice 171: Deferred — No Third Consumer

Deferred immediately after a passing design review and before any
implementation. **The design is not the reason.** It reviewed at CONCERNS with
all findings resolved, and it stands as written.

The slice rests on one load-bearing argument: the executor has accreted two
hardcoded post-action checks (909's dispatch artifact post-condition, 911's
`revision_number` stamp), so a third means editing the executor again — the
open/closed violation the project's own review rules name. That argument is
worth 3/5 effort only if a third consumer exists. Asked directly, there isn't
one.

And the nominal *first* consumer does not survive scrutiny. A frontmatter
`status:` validator is better served by a `sq validate docs` command: it
catches every document rather than only those touched during a pipeline run,
it can go in CI where it actually blocks, and it is a fraction of the work.
It also arguably is not squadron's job — `cf check` exists and Context Forge
owns `file-naming-conventions.md`, which defines the canonical set. The
design's own "accepted drift risk" note about mirroring another project's
spec in a squadron enum was the tell, written down and then walked past.

Building a mechanism to hold two checks that already work, for a consumer
better served elsewhere, is speculative generality — which the project rules
ban. The two checks stay hardcoded. A third is cheaper to add in place than
this mechanism is to build.

**Un-defers on:** naming a consumer that must run *inside* a pipeline and
*block* it, i.e. one that cannot wait for CI or a manual command.

Two reworks surfaced in discussion after the review and are recorded in the
slice design's Deferral section rather than folded into the body:

1. **Authoring flow.** As designed, adding a hook means editing squadron —
   a module under `hooks/builtin/` plus a bootstrap line. No project-level
   hook file exists. A feature that is a pain to use will not get used.
   Likely shape if revived: a `.squadron/hooks/*.py` convention imported at
   bootstrap, registering through the already-public
   `register_post_action_hook`. The `conftest.py` pattern — in-repo, typed,
   no shell door opened.
2. **The watermark is wrong, and duplicate suppression is its symptom.**
   `frontmatter-status` scopes to documents with mtime `>= run_started_at` —
   a *run*-level watermark, so a document written in step 1 keeps matching
   after every later action, which is the only reason the design needed a
   dedup component at all. Correct shape: the runner computes the
   changed-document set once per action (delta since the *previous* action)
   and passes it in `HookContext`. A hook with nothing to do gets an empty
   set and returns PASS; each document is validated once, when written; the
   scan is shared across hooks; dedup disappears. Rejected alternative:
   actions self-reporting what they wrote — `dispatch` cannot know, since an
   agent writes files out of band, which is the whole premise of the 909 bug.

Also unresolved and worth knowing before any revival: hook records would land
in `ActionResult.metadata` (persisted free via `dataclasses.asdict` at
`state.py:291`), but only at **step** completion, and prompt-only
`record_step_done` builds an `action_results` list only when `--verdict` is
passed — so there is nowhere to hang them. And the design recorded only
non-`PASS` outcomes, making "ran and passed" indistinguishable from "never
fired." The "no silent path" rule was applied to failures and not to the
silence that actually bites.

Documents updated: slice design `status: deferred` with a Deferral section at
the top; slice-plan entry 28 marked DEFERRED with a Notes entry; the
architecture's Post-Action Hooks section, component diagram, package
structure, and YAML grammar all marked designed-not-built so the architecture
does not read as describing shipped behavior.

---

### Slice 171: Design Review — Resolved

`171-review.slice...md` returned **CONCERNS** — two concerns, two notes, four
PASS. All four acted on.

- **F001** — frontmatter `dependencies` omitted 911, which the Prerequisites
  section, the migration plan, and success criteria #13/#17 all lean on.
  Now `[142, 149, 909, 911]`.
- **F002** — the slice introduces architecture-level surface (a third
  registry, a new pipeline-YAML block, two config keys) at slice level. Chose
  to update the parent architecture rather than record a deferral:
  `140-arch.pipeline-foundation.md` gains the hook registry in its Component
  Architecture diagram and Package Structure, the `hooks:` block in its
  Grammar, and a "Post-Action Hooks" section under Action Extensibility
  carrying the authority model — trigger, severity as a single axis, the
  clamp, chain-stop, and the `result.outputs` bar. Initiative 180's
  convergence strategies need to know this extension point exists and what
  authority it holds. Slice design gained success criterion #24 so the
  architecture update is a deliverable, not a courtesy.
- **F003** — recorded the trigger condition for widening the config type
  system: a **third** list-valued config key. Two keys do not justify
  touching a shared type system; three do. Fixing it on a count rather than
  on irritation.
- **F004** — the dedup set's lifetime is the process, not the run, and those
  coincide only under the in-process executor. In prompt-only mode each
  `--step-done` is a fresh process, so a recurring warning surfaces once per
  invocation. That is right for a mode whose steps are separated by human
  turns — a warning suppressed in a process the user has walked away from is
  a warning lost — but "once per run" was not true as written. Success
  criterion #10 restated in per-process terms so it is testable.

Also corrected `status: in-progress` → `in_progress` in both the 140 slice
plan and the 140 architecture frontmatter. Outside the canonical set, and
precisely what this slice's `frontmatter-status` hook is being built to catch.

---

### Slice 171: Post-Action Hooks — Phase 4 Slice Design Complete

Design written for slice 171 (initiative 140, Pipeline Foundation), issue #52.
Provider-independent post-action hooks: the equivalent of Claude Code's
`PostToolUse` at the layer squadron owns, since Claude hooks reach exactly one
of the seven provider profiles squadron runs.

Framed as a generalization, not a new mechanism. Squadron already has two
hardcoded post-action hooks sitting below the single action-execution site at
`executor.py:1124` — the 909 dispatch artifact post-condition (which can fail
an action) and the 911 `revision_number` stamp (which must never fail one).
Migrating both onto the mechanism is the acceptance test, with the binding
constraint that **no assertion in an existing 909/911 test may change** —
only mock target paths move, the same discipline slice 306 used when
relocating `run_git`.

Contracts settled:

- **What a hook is** — a registered Python callable behind a
  `runtime_checkable` Protocol, mirroring the `Action` registry and
  `bootstrap_step_types()` idiom. Not arbitrary shell: that is what makes
  Claude's hooks a security surface, and it can be added later but not
  removed later. `check()` is `async` so `asyncio.wait_for` is the timeout
  mechanism.
- **What a hook may do** — `PASS` / `WARN` / `FAIL`, on **one** declared
  severity axis that governs both the outcome and the breakage case. The
  runner clamps a `WARN`-severity hook that returns `FAIL`, which is what
  keeps the revision stamp from ever failing a converging loop. Hooks may
  write files; they may not otherwise mutate `ActionResult`.
- **Trigger granularity** — `HookTrigger` carries action types and
  success-only, and deliberately cannot express pipeline structure. Step-derived
  facts (`expected_artifact_kind`, `run_started_at`, `iteration`) go into
  `HookContext` and the hook self-selects — which is today's `expected_kind is
  not None` guard relocated to the hook that cares.
- **Ordering** — registration order, stated in one place; a `FAIL` stops the
  chain, which expresses the existing stamp-after-post-condition dependency
  as ordering rather than an `elif`.
- **Activation** — `hooks.disabled` (str, comma-separated; the config type
  system supports only `int`/`str`) unioned with a per-pipeline YAML
  `hooks: {disable: [...]}` block. No re-enable override, so no precedence
  puzzle.
- **Failure modes** — raise, timeout, disabled, clamp, chain-stop each have a
  defined outcome and an observable signal; every non-`PASS` outcome lands in
  `result.metadata["hooks"]` and logs at WARNING+.

Two decisions worth recording because they were not in the issue:

**Prompt-only parity is closed, not inherited.** The 909 post-condition runs
only in the in-process executor today — prompt-only mode has no post-action
moment, so a `/sq:run` P4 whose dispatch wrote no design advances anyway. The
design runs the same hooks at `sq run --step-done`, and a `FAIL` there refuses
to record the step and exits non-zero. That is a real break in a scripted
command's exit-code contract, flagged for CHANGELOG. It is also why hooks are
barred from reading `result.outputs` — there are none in prompt-only, so a
hook depending on them would work in one mode and silently no-op in the other,
which is the exact failure this slice exists to remove.

**The frontmatter status validator is `WARN`, not `FAIL`.** A bad `status:`
is a metadata defect, not a broken artifact; failing an action over it would
block work on a pre-existing bad file the run did not create. Escalating later
is a one-line change, de-escalating after it has blocked a pipeline is a bug
report. The validator needs a mechanical definition of the canonical set,
which squadron does not have — so the slice adds `DocumentStatus(StrEnum)`,
mirroring the prose in `file-naming-conventions.md` with the drift risk stated
rather than hidden.

Slice-plan entry 28 marked Design Complete. No code written; Phase 4 only.

---

### Slice 306: Code Review — Resolved

`306-review.code...md` returned **PASS** — four PASS findings, six notes, no CONCERN+. Four of the six notes were acted on; two were not, for stated reasons.

**F009 was the one worth having.** `_save_and_report` catches the archive guard's `OSError`, prints the refusal, and returned — so a review that ran, displayed, and then could not be written exited 0. Downstream readers gate on the file, not on terminal output, so that is a silent failure of exactly the class Part D exists to prevent. Save failures now exit 1, with a `FAIL` verdict keeping its more specific exit 2; the tasks command still saves every part before exiting, since the reviews have already been paid for. Documented in the exit-code table.

**F007 was more than cosmetic.** `_render_findings` promises the judge one finding per line, but finding text is model-authored and arrives through YAML, where a block scalar carries real newlines — and `records_from_frontmatter` does not strip them. A multi-line summary would not merely look untidy: it would present as an extra finding, and a line shaped like `F002: addressed` would read as a status. Every field is now collapsed to one line at render time, which is the seam that owns the format.

**F006** renamed `exceeds_injection_cap` → `injection_cap_if_exceeded`; the old name promised a boolean and the function returns the cap value, which the caller needs in order to name it in the warning.

**F005/F010** added CLI-layer tests for `--since` (including a bad ref, which must be a named git failure rather than a crash), `--model`/`--profile` passthrough asserted at the transport, and `-v`'s note column.

**F008 left as-is.** `resolution.py` is 384 lines against a ~300 guideline the project states as "where practical"; the reviewer called it an observation rather than a violation, and the file is already the second half of a split made during implementation. Splitting again would trade one over-long orchestrator for three modules whose seams are less obvious than the first cut's.

---

### Slice 306: Review Resolution — Implementation (Phase 6)

Both task files complete on `306-slice.review-resolution-recording-that-findings-were-addressed`. `sq review resolve <n> [TYPE]` ships, `reviewedSha:` is stamped at review-authoring time, and re-running a review no longer destroys the previous one.

**The dependency-direction problem Part 0 was built to solve turned out to reach further than the design anticipated.** Design review F002 barred `review/` from importing `pipeline/`, and the relocation moved models, parsing, verification, and the judge transport into `review/addressed/` accordingly. But two of the moved modules annotate `RoundDiff`, which the design left in the pipeline package as loop-specific machinery — resolved in file 1 with `TYPE_CHECKING` imports, which held only because the uses were annotations. T21 needs to *construct* one, and `TYPE_CHECKING` cannot launder that.

Resolved by splitting the screens on the criterion the design itself states — what needs loop context stays. `RoundDiff`, the git measurement, `ScreenResult`, `screen_byte_identical`, and `screen_git_failure` need none of it and moved to `review/addressed/screens.py`; screen 0 (needs an iteration number) and screen 2 (needs a fresh review) stayed. The two `TYPE_CHECKING` shims became plain imports. 305's gate tests pass with only mock-target relocation — no assertion changed.

The measurement itself unified along the way. `compute_round_diff` and the new base-parameterized diff are the same function: `git diff <base>` with a single commit argument spans base→working tree, so `compute_round_diff` is `compute_diff_since("HEAD")` and the gate's failed-command string is unchanged.

**Two gaps the task file did not anticipate, both found by running the thing.** First: a review file is written *after* the commit its own `reviewedSha` names, so it always appears in its own diff — the empty-diff screen would have been unreachable, and every stale review would have gone to the judge with the review itself as its only evidence. The reviews directory is now excluded from the measurement. Second: `review/git_utils` already owns the name `resolve_diff_base` for a different question (which branch slice work forks from), and the conftest patches it autouse; the new one is `resolve_review_diff_base`.

**T25's injection cap.** 305 enforces `review.max_total_injection_bytes` on file injections but does not apply it to the judge's change-set input. Per T25's instruction, the check was added on this path only; the gap in 305 is logged as issue #53 (low priority) rather than silently fixed here. 305's gate measures a round against `HEAD`, so its change set is bounded in practice — the resolve path's `--since` is what makes the cap load-bearing.

Scope notes. T13's guard grew to both persistence paths with PM approval (file 1). `_yaml_safe` and the `safe_dump` pattern were promoted out of `evidence.py` into `documents/frontmatter.py` as `yaml_safe`/`render_frontmatter_block`, both call sites updated; `evidence.py`'s duplicate reviews-dir constant now points at `persistence.REVIEWS_DIR`. `resolution.py` hit 613 lines and was split at the evidence/decision seam into `resolution_evidence.py` (locate, load, diff base, measure, screens) and `resolution.py` (decide, orchestrate), with `resolution_artifact.py` holding render and the versioned writer. T31/T32 landed inside T29/T30's commit rather than their own — the writer was needed to lint the module it lives in.

Still open: T39's Context Forge coordination note has no agreed delivery mechanism (issue, message, or shared doc) — a question for the PM, not something to guess at.

---

### Slice 306: Task Breakdown Review (Part 2) — Resolved

File 2's task-breakdown review returned CONCERNS — three concerns, two notes. All fixed. One of the three concerns (F005, the Phase 5 cf-archive-scanning checklist item) turned out to already be resolved: this reviewer flagged it as unconfirmable from file 2 alone ("I can only review file 2"), and file 1's own review had independently caught the same gap as its F002 and fixed it before this review was read — both reviewers converged on the same real gap from different files.

The other two concerns were genuine coverage holes. F004: `metrology/capture.py` has its own index-scoped review-discovery glob, distinct from `discover_judge_results` — confirmed by reading the source — and T32 only tested the latter; SC11's own wording says "and," so both now get asserted separately. F006: T33's "no swallowed WARNING/ERROR" requirement had no test anywhere; T34 gained a `caplog` assertion using the file-history-fallback WARNING as a convenient, already-set-up case.

File 2 is now 502 lines, 52 over the ~450 guideline — inside the "don't split under ~100 overrun" threshold, left as one file.

---

### Slice 306: Task Breakdown Review (Part 1) — Resolved

File 1's task-breakdown review (306-review.tasks...part-1.md) returned CONCERNS — four concerns, three notes, no fails. All fixed in the task file, no scope or numbering left inconsistent.

The structural fix (F002) reordered Part D: the cf-archive-scanning checkpoint is now T12, placed *before* the archive-guard implementation and its test (renumbered T13/T14) rather than after with a "don't mark done until" note — the reviewer's point was that a forward-referencing gate is fragile in practice, and reordering makes it structural instead. The two coverage gaps (F001: the read-back-verification-fails branch had no test distinct from copy-cannot-be-created; F004: no task confirmed `format_review_markdown`'s findings shape survives the `reviewedSha` addition, which file 2's frontmatter reader depends on) both got dedicated test bullets rather than being folded into existing ones. F003 added explicit NOTEs to T2/T4/T6 clarifying that Part 0's intermediate verification steps are focused subsets, not the full-suite gate — T8 remains that gate.

---

### Slice 306: Review Resolution — Task Breakdown (Phase 5)

Task breakdown complete: `user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md` (Parts 0/A/D, T1–T14) and `-2.md` (Parts B/C + Closeout, T15–T40), 306 and 461 lines — split at the natural infrastructure/feature seam rather than a mechanical line-count cut, since Part B's every task imports from what Part 0 relocates. Slice design's `status:` moved to `in_progress`; no branch created yet.

40 tasks, each paired with its test task per the test-with rule. Three sequencing notes worth keeping in mind at Phase 6: **Part 0 (the `review/addressed/` relocation) must land first** — every task in file 2 imports from the new location, and it is verified purely by re-running 305's existing suite unchanged, with no new tests written for code that only moved. **Part D (the overwrite guard) is independent of Part B** and fixes a live data-loss bug on its own, so it does not need to wait on the interactive command; T14's cf-archive-scanning check (design review F005) gates T12's completion in practice, even though it is numbered after it — the task file says so explicitly rather than relying on numbering to imply it. **Three design-review-added failure-closed rules got their own dedicated task pairs** rather than being folded into general error handling: the verdict-consistency screen (T23/T24, F001 — an empty CONCERN+ set against a FAIL/CONCERNS verdict is inconsistent evidence, not a pass, citing issue #28's parser-drop lineage directly in the task text), the judge-leg failure modes and injection cap (T25/T26, F004), and the archive-copy failure path (T12/T13, F003).

One judgment call surfaced while breaking down T25: 305's architecture states an injection-cap constraint, but the breakdown does not know whether 305 enforces it in code today. Rather than assume and rather than silently expanding this slice's scope to add the check to 305 if it's missing there too, T25 instructs whoever implements it to add the same check on this path and separately flag the gap to the Project Manager if 305 turns out not to enforce it — scope stays bounded to 306, the fact surfaces either way.

---

## 20260802

### Slice 306: Review Resolution — Slice Design (Phase 4)

Design complete at `user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md`; slice plan entry 7 updated with the pointer. Issue #51.

The design holds the constraint that motivated the issue: agents stay barred from editing `verdict:`, and nothing one word an agent can write may unblock a gate. Resolution is a *second assertion* in a *second artifact* — `{index}-resolution.{type}.{name}-r{n}.md`, `docType: review-resolution`, top-level field `resolution: ADDRESSED|UNADDRESSED|UNKNOWN` (deliberately not `verdict:`), derived by 305's discipline: screens first, judge over what remains, `verify_outcomes` downgrading unsupportable claims, UNKNOWN evaluated before failure.

Four parts. **A:** `reviewedSha` stamped into review frontmatter at authoring time by both persistence paths — the anchor for "what changed since the review"; file-history fallback with WARNING for legacy reviews, `--since` override. **B:** `sq review resolve <index>` in a new `review/resolution.py`, reusing 305's building blocks with the judge transport extracted context-free (`judge_residue` becomes a thin ActionContext wrapper; 305's tests must pass unchanged). Known asymmetry stated rather than hidden: no fresh review exists on this path, so 305's exact-match screen cannot run — the judge sees all CONCERN+ findings when the diff is non-empty, and `MOVED` always downgrades. **C:** the frontmatter schema as the cf coordination seam (review-gating lives in cf; squadron writes the record, cf owns the gate), plus the interim PM procedure — verdict edits stay manual, now citing machine-derived evidence. **D:** `save_review_file` archives the prior content and warns before overwriting, closing the data-loss hazard found during scoping (a re-review silently destroyed hand-written Resolution sections).

Effort 3/5 (B dominates). Not in scope: cf code changes, running a fresh review inside `resolve`, any squadron-side verdict edit.

---

### Slice 305: Code Review Resolution

Code review returned FAIL with one fail, five concerns and three notes. All nine addressed on `305-slice.findings-addressed-gate`; suite 2832 passed / 2 skipped, ruff and pyright clean.

**The FAIL was real and total.** `CONCERN_PLUS_SEVERITIES` is built from `Severity.CONCERN`/`Severity.FAIL` — uppercase — but `ReviewResult.structured_findings` emits `f.severity.value.lower()`, so the membership test in `concern_plus` was always `False`. Every gate handed `prior_findings=[]` to the screens, took the "prior round raised no CONCERN+ findings" PASS, never ran Screens 1–2, never consulted the judge, and reduced to the fresh review's verdict. The policy was inert on its happy path from the day it shipped. Fixed by normalizing at the boundary (`_as_severity` in `read_findings`) rather than lowercasing the constant, so the constant stays tied to the enum and cannot drift when a producer changes case.

**It survived a full slice because no test used the production shape.** Every fixture wrote `{"severity": "CONCERN", ...}` by hand — exactly the trap CLAUDE.md names. The e2e fixtures now build a `ReviewResult` and take `.structured_findings`, which also means the `F00n` ids come from the property that assigns them rather than from a literal. Two of the e2e round-2 assertions now fail without the fix.

**Loop-body step outputs are scoped to their iteration.** Part A published inner-step results into the run-wide `step_outputs`, which nothing cleared: a round whose review failed left round N-1's result standing under the same name, and the fresh leg read it as this round's evidence with no round stamp to tell them apart. Each iteration now gets a fresh view — a copy of the pre-loop outputs plus its own body steps — and the run-wide dict is left alone. That also closes two effects the review noted in passing: an inner step can no longer overwrite a same-named top-level step, and body step names stop resolving after the loop exits.

**Screen 0 was conflating two states.** `prior_result is None` fires both for a legitimate first round and for a round whose predecessor's review crashed or emitted no verdict — and returned an annotated PASS for both. It now branches on `iteration`: ≤ 1 is the first round (PASS), > 1 is an evidence gap (UNKNOWN, `deciding_screen` unset, WARNING naming the missing step), matching the module's own contract that a check which could not run is UNKNOWN.

**Frontmatter is serialized, not formatted.** `_yaml_scalar` was `str(value)` with no quoting, and notes interpolate finding locations, which `review/parsers.py` returns "stripped, unchanged" — arbitrary model text. `location: src/foo.py: line 45` produced a mapping-value error inside the block. Now built as a dict and dumped with `yaml.safe_dump`, with enum members coerced first (SafeDumper dispatches on exact type, so a `StrEnum` member raises).

**The ordering rule became policy-agnostic.** `_validate_verdict_count`'s consumed-name exclusion assumes `_last_with_verdict` lands on the gate, which holds only if the gate follows the steps it names — but only `findings-addressed` gates were ordering-checked. `[gate(most-severe, review_from: r), review r]` validated while `until:` gated on the review and the gate was discarded. `_validate_gate_ordering` now checks every gate in a body. A referenced name that matches no body step is left alone: it may name a pre-loop step, which consumes nothing.

**Notes.** Judge status parsing switched to `finditer` per line with first-wins accumulation, so several statuses on one line are all read and later prose cannot overwrite an answer already given. `review/parsers._location_path` was promoted to public `location_path` and the copy in `verification` deleted; `screens._match_key` was left alone, since matching on the full location string is a deliberate 911 constraint rather than a third copy of the same rule.

**Not adopted: the lint/type config gap (F009).** The Python guide's baseline also selects `B`, `BLE`, `ASYNC` and includes `tests` in pyright. Measured: 70 `B`, 23 `BLE`, 6 `ASYNC` violations and 868 pyright-strict errors, essentially all pre-existing in modules unrelated to any current slice, and `BLE`/`ASYNC` remediation means narrowing exception types and moving blocking calls off the event loop — behavior changes, not formatting. `W` (zero violations) is enabled; the rest is recorded with its counts in `pyproject.toml` and tracked as issue #50, with a suggested sequencing (B008 per-file-ignores for the Typer CLI modules → B → ASYNC → BLE → pyright sweep). Note that 13 of the 70 `B` violations are `typer.Option` in signature defaults — the standard Typer idiom, not debt.

---

### Slice 305: Findings-Addressed Gate Policy — Implemented

Phase 6, branch `305-slice.findings-addressed-gate`, seven commits — one per part, each with its own tests green before the next began.

**The two loop-executor defects Phase 5 found are fixed, and the fix stands alone (`59944b6`).** `_execute_loop_body` now writes each inner step's verdict-bearing result into `step_outputs` under its step name, using the same `_last_with_verdict` rule the top-level walk uses — so a gate inside a loop resolves its named legs for *every* policy, including 304's `most-severe`, which had been emitting `UNKNOWN` every round since it shipped. `ActionContext` gained `prior_iteration_step_outputs`, scoped to the loop body's own steps and empty on iteration 1, so a policy comparing rounds cannot read its own round through a positional key that the current iteration has already overwritten. Both changes are additive; the full suite passed unchanged.

**Policy config is now per-policy, from one table.** `GatePolicy` (StrEnum) plus `GATE_POLICY_CONTRACTS` — required fields, forbidden fields, and whether the policy has a model layer — is the single source consumed by `steps/gate.py`, `loader.py`, and `steps/loop.py`. `most-severe` requires both legs and rejects a `judge:` block; `findings-addressed` requires `review_from`, rejects `judge_from`, and accepts `judge: {model:}`. `GateAction` now dispatches to a registered `GatePolicyImplementation` instead of reducing unconditionally; a valid policy with no registered implementation fails closed with an explicit error rather than silently borrowing another policy's answer.

**Loop validation counts unconsumed verdicts.** A step named by a gate in the same body is that gate's input, not a competing answer, so `[dispatch, review, gate]` validates while `[review, review]` still rejects with 910 Part B's original message. Two loop-scoped rejections were added for `findings-addressed`, both at validation time per design decision 8: no per-round commit source (the evidence is absent by configuration), and a `review_from` naming no earlier step in the body (the loader cannot see inside a body, so this is where the reference is resolvable).

**The policy is a package**, not a module — `models`, `screens`, `parsing`, `judge`, `verification`, `evidence`, `policy` — because the single file the design named ran to ~400 lines before the judge leg existed. Layer order: Screen 0 (no prior round → annotated PASS, decided before any git call), Screen 1 (empty working-tree diff against `HEAD` *and* empty `git status --porcelain` → every prior finding unaddressed, leg FAIL), Screen 2 (exact `location`+`category` match, `unverified` locations excluded), then a judge over the residue only. A git failure is the one condition that earns `UNKNOWN`, and the log names the exact failed command.

**Derived, not declared, end to end.** The bundled `judge.findings-addressed` template carries no `judge:` block — deliberately, since `is_judge` derives from it and metrology sweeps `*-review.*` for judge samples. Its output is parsed leniently into per-finding statuses; a finding the judge said nothing about is `disputed`, not dropped. `moved` without a successor present in the fresh findings, and `addressed` over a file the round never touched, are downgraded to `disputed` with a WARNING. The verdict is computed from the surviving statuses with `UNKNOWN` evaluated before `FAIL`, so a check that could not run never reads as a check that ran and failed.

**Evidence artifact:** `{index}-gate.{policy}.{name}-r{revision}.md` under `project-documents/user/reviews/`, `docType: gate-evidence`, written before the round's commit so it lands in that round's history. One `GateEvidence` object backs both the file and `ActionResult.metadata` — the facts are never assembled twice. `discover_judge_results` over a directory containing one returns it in no sample set; that is asserted in `tests/metrology/` against the real discovery function, not against the glob.

**What is recordable, and what is not.** The prior round's SHA (`HEAD` at gate time) plus `revision_number`. Round N's own SHA is not: the artifact is written before the commit that contains it. Round N's commit is discoverable afterwards as the commit containing the artifact.

T28's resume finding is now pinned by a test in `test_state.py`: a paused loop step is appended to `completed_steps` and resume continues past it, so no execution path reaches the gate with a prior round missing — the policy contains no resume branch. Issue #48 (whether a checkpoint-paused loop *should* be re-enterable) is untouched and still open; the fail-closed end-to-end test asserts the pause, not a resumed loop.

End-to-end coverage runs the target shape over a real git repository with only the model call stubbed: round 1 annotated, round 2's recurring finding failing the gate, round 3 judged-addressed and exiting — one transport call across three rounds. Byte-identical rounds and judge-transport failure have their own end-to-end tests.

---

### Slice 305: Findings-Addressed Gate Policy — In Progress

Phase 5 task breakdown. Design (Phase 4) and its slice review were completed and resolved earlier the same day; commits `0917dae`, `2e2c94c`, `534c689`, `84121df`, `221b8c7`, all on `main`, all planning documents. This session produced `305-tasks.findings-addressed-gate-1.md` (Parts A–C, T1–T11) and `-2.md` (Parts D–G, T12–T30) — split because the single file ran 608 lines against a ~450 target.

**Breakdown found two pre-existing loop-executor defects, both verified on disk.** Neither is a 305 concern; 305 is just the first consumer to walk into them.

1. **`step_outputs` is never populated for steps inside a loop body, so any gate in a loop is broken today.** The only writer is `executor.py:959`, in the top-level step walk; `_execute_loop_body` passes the dict through but never writes it. `GateAction` is its only reader anywhere in the codebase (`actions/gate.py:95-96`), so a gate in a loop resolves neither leg and emits `UNKNOWN` every round. 304's plain `most-severe` gate fails exactly the same way — this is not specific to the new policy.
2. **`prior_outputs` means "prior round" or "current round" depending on where a step sits in the body.** `running_prior` keys are positional (`executor.py:1400-1402`) and overwrite each iteration. 910's findings-feedback is correct only because dispatch happens to run first; reorder the body and it silently feeds the current round's findings back into itself. The gate sits late, so it cannot read the prior round this way at all.

Plus one ordering fact the design had backwards: round N has no commit SHA at gate time, because `commit_each_iteration` commits after all inner steps (`executor.py:1417-1440`). The design's Screen 1 signal (`committed: False`) describes round N-1 vs N-2, one round stale.

The correction is simpler than what the design specified: populate `step_outputs` for inner steps, carry the prior iteration's step outputs on a new `ActionContext` field, and detect a byte-identical round as an empty working-tree diff against `HEAD` — which *is* the prior round's commit at that moment, so the screen needs no SHA plumbing at all. Both executor changes are additive and cannot alter existing behavior: nothing but the gate reads `step_outputs`, and nothing but the new policy reads the new field. Part A carries them; they add `pipeline/executor.py` and `pipeline/models.py` beyond the design's Files Touched table.

Task ordering follows the design's stated sequence with the plumbing prepended: A (executor evidence) → B (validator refinement) → C (policy config surface) → D (deterministic screens) → E (judge residue) → F (evidence artifact) → G (integration, docs, close-out).

Design decision 5's resume caveat was closed during breakdown rather than carried into Phase 6: findings do survive state persistence (`state.py:291`, `:417-434`), and squadron has no mid-loop resume — a paused loop step is appended to `completed_steps` (`state.py:304-309`) and `first_unfinished_step` skips past it, so the loop is never re-entered. The policy gets no resume special case; T27 pins the behavior with a test instead. Whether a checkpoint-paused loop *should* be re-enterable is a real pipeline-foundation question and deliberately not this slice's.

No code written; no branch created.

---

## 20260801

### Slice 911: Loop Iteration Versioning and Review Evidence — Implementation Complete

**Phase 6 complete.** Branch `911-slice.loop-iteration-versioning-and-review-evidence` off `main`. All three parts landed in the design's A1 → B → A2/A3 → C order, one commit per sub-part (`ad5d97b` through `412839c`).

- **A1 (`ad5d97b`):** `ActionContext.iteration: int = 0` added and threaded through `_execute_step_once`; `CommitAction` appends ` (iteration N)` to a composed message when `iteration >= 1`, leaving an explicit `message:` param verbatim.
- **B (`07db9f1`, `443a2ce`):** new `src/squadron/documents/frontmatter.py` (lenient read/update, byte-preserving body, named exception on malformed input); `read_review_frontmatter` delegates its parse to it. Dispatch's post-condition stamps `revision_number` (n+1 or 1) on the artifact when `expected_kind is not None` and `iteration >= 1`; `format_review_markdown` emits the same field on review files when supplied.
- **A2/A3 (`36f64ad`, `f330517`, `80a725e`):** `commit_each_iteration: true` validated on `LoopStepType` (rejects a body that already commits, reusing `_validate_verdict_count`'s traversal rather than a second walk); `_execute_loop_body` appends one commit per iteration before the `until:` check; a clean-tree commit inside a loop now logs a WARNING naming the iteration.
- **C (`ac25cdf`, `412839c`):** `--dry-run` shows `commit_each_iteration` when set; `docs/PIPELINES.md`'s "no per-iteration commit" section replaced with the opt-in contract and the `revision_number` field contract.

**Full validation gate:** `ruff format`/`ruff check` clean, `pyright` strict 0 errors, full `tests/` suite 2745 passed / 2 skipped vs. a `main`-baseline of 2698 passed / 2 skipped (a separate worktree checkout) — the +47 delta is exactly the new tests added across T3/T5/T7/T9/T11/T13/T15/T17/T19, no regressions, no new skips.

**Live smoke test, and what it actually showed.** Ran `commit_each_iteration: true` end-to-end in a disposable scratch repo (`~/source/repos/manta/temp/squadron-smoke-911`, outside this repo, since `sq run`'s SDK-mode dispatch refuses to execute nested inside a Claude Code session — this session couldn't run it itself). Confirmed real: one commit per iteration with a distinguishable message (`chore: loop-{name} (iteration N)`), and a non-empty `git diff HEAD~1 HEAD -- <path>` between rounds. One apparent anomaly — two commits both reading "iteration 1" — was traced to two separate un-resumed `sq run loop-smoke` invocations 28 seconds apart (confirmed via distinct `run_id`s in `~/.config/squadron/runs/`), not a defect: each fresh run numbers its own iterations from 1. Separately, and not a squadron defect: the smoke fixture's dispatch prompt asked the model to write a throwaway `calc.py`, but the coding agent went off-task and copied this repo's own `CLAUDE.md`/`.claude/` scaffolding into the scratch project instead — a smoke-test-prompt problem to note if reused, not something this slice's code caused. The mechanism itself (not this one fixture's prompt-following) is independently covered by `tests/pipeline/test_executor_loop_body.py` and `tests/pipeline/actions/test_commit.py`.

**ai-project-guide issue #14** (registering `revision_number` in the canonical frontmatter schema) is still open with no comments as of close-out — no rename needed; `revision_number` ships as designed.

**Slice marked complete.** Entry 9 in `900-slices.maintenance-and-refactoring.md` checked off. Issue #44 to be closed on merge, not before.

**Next:** slice 912 (Review Evidence — Prior-Version Access) needs its own design conversation before Phase 4.

### Slice 911: Loop Iteration Versioning and Review Evidence — Review Resolution

**Verdict CONCERNS**, 5 concerns / 4 pass / 3 note across 13 findings. Verified each concern against the actual code rather than taking the review at face value:

- **F002 (FIXED):** `_stamp_revision_number` caught only `(ValueError, TypeError)` around `_expected_artifact_paths`, but `cf_client` is duck-typed and the real `ContextForgeCLI` raises `ContextForgeError`/`ContextForgeNotAvailable`/`KeyError` on a CF hiccup — none caught. Confirmed this would have propagated uncaught through `_execute_step_once`, violating the function's own "must not fail a converging loop" contract. Widened to `Exception` with a comment tying it to that contract; new test drives the real `ContextForgeError` path via a two-call `side_effect` (post-condition succeeds, stamp call raises).
- **F004 (FIXED):** confirmed the sibling post-condition function already warns on an empty `_expected_artifact_paths()` result but the stamp function silently no-opped on the same condition. Added the matching WARNING; new test forces an empty-but-non-raising resolution distinct from the post-condition's own call.
- **F013 (FIXED):** closed by the same fix/test as F002 — the new test exercises the previously-untested non-`FrontmatterError` exception path.
- **F003 (ACKNOWLEDGED):** the `revision_number` vs. loop-iteration naming tension is the exact tradeoff the design's Field Contract table already decided with the PM — no action.
- **F001 (ACKNOWLEDGED):** the review's own prose downgrades this to a NOTE; no action.
- **F005-F012:** pass/note, no action.

Full gate re-run after the fix: 2747 passed / 2 skipped (up from 2745 — the two new regression tests), no regressions. Resolution appended to `911-review.code.loop-iteration-versioning-and-review-evidence.md`.

## 20260731

### Slice 910: Loop Convergence Correctness — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/910-slice.loop-convergence-correctness.md` on branch `main` (planning work, no slice branch), from the slice-plan entry in `900-slices.maintenance-and-refactoring.md`. Three defects on the `loop:` execution path bundled into one slice because Parts A and B share `_execute_loop_body` and one test file: Part A findings-feedback gap (#42, High), Part B ambiguous multi-review `until:` gating (#43, High), Part C `--dry-run` loop-body expansion (#45, Low).

**Grounded every anchor against on-disk code, extending the scoping already done in the slice-plan entry:**
- **Part A:** re-confirmed `_execute_loop_body` (`executor.py:1298-1321`) passes the outer `prior_outputs` unchanged into every iteration, and that `DispatchAction._resolve_prompt_from_prior_review` (`dispatch.py:258-291`) is a complete, already-shipped consumer waiting on real data. Added a design-time decision the plan entry left open: keep the existing `{action_type}-{action_index}` key scheme for the accumulated `prior_outputs` (letting a later iteration's same-key write overwrite the earlier one) rather than folding the iteration number into the key, since the consumer only ever wants the *most recent* review, not a full history — full history is 911's job.
- **Part B:** traced which step types can actually produce a verdict-bearing action, since the fix counts them at validation time. Confirmed it's not just `StepTypeName.REVIEW` — `PhaseStepType.expand()` (`phase.py:156-169`) appends a `review` action from an inline `review:` sub-field, and `gate` (`actions/gate.py`) also produces a `verdict`. A loop body with two `phase:` steps each carrying inline `review:` is ambiguous under #43 even though neither inner step is literally type `review` — the validation check must expand inner steps and count actions, not pattern-match step-type names. Placed the check inside `LoopStepType.validate()` (`loop.py:30-115`) alongside the existing nested-loop ban, reusing the already-imported `unpack_inner_steps` helper. Flagged a fallback (raw-config inspection instead of calling `expand()`) in case any inner step type's `expand()` isn't side-effect-free.
- **Part C:** confirmed the exact one-line render site (`run.py:983`) and scoped the fix to a single `if step.step_type == "loop"` branch reusing `unpack_inner_steps` for the indented inner-step listing — no new rendering abstraction, matching Parts A/B's no-new-machinery bar.

**Also recorded, not fixed:** the `on_exhaust: skip` fall-through gap the plan entry already flagged as deferred (verified present at `executor.py:873/881`, `SKIPPED` absent from the run loop's early-return checks) is carried into the slice design as an explicit Known Issue, out of scope for all three parts, unchanged from the plan-entry framing.

**Sequencing:** Part B before Part A (establishes the one-verdict-per-body invariant Part A's tests assert against); Part C independent, any order.

**Next:** Phase 5 (Task Breakdown) for slice 910, not yet started.

### Slice 910: Loop Convergence Correctness — Review Resolution

**Review verdict PASS with one CONCERN (F001)**, raised against the three items the design deferred to implementation: Part A's `prior_outputs` key scheme, Part A's `step_outputs` interaction, and Part B's reliance on `expand()` purity. Traced all three against the actual code instead of leaving them open:

- **Key naming:** the plain `{action_type}-{action_index}` scheme (no iteration number folded in, same-key overwrite across iterations) is safe by construction, not just convenient — `action_type` carries no inner-step identity, so a same-key collision within one iteration can only happen if two inner steps produce the same action type, which is exactly the shape Part B's validation bans. Once Part B lands first, the collision case cannot occur.
- **`step_outputs`:** confirmed it's a disjoint mechanism from `prior_outputs` — created once per run, threaded by reference (never copied), written exactly once per top-level step after that step fully returns. Part A's fix never touches it.
- **`expand()` purity:** read every `expand()` implementation reachable inside a loop body (`compact`, `devlog`, `dispatch`, `gate`, `phase`, `review`, `summary`) — each is a pure dict transform with no I/O. Confirmed safe to call at validation time.

Updated the slice design in place (Part A and Part B sections rewritten from "confirm during implementation" to "resolved, not deferred" / "resolved, purity confirmed"), removed the Risk Assessment section since no open risk remained, and appended a Resolution block to the review file (F001 ACCEPTED, F002 ACKNOWLEDGED, F003/F004 no action) following the same pattern slice 909's review used.

### Slice 910: Loop Convergence Correctness — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/910-tasks.loop-convergence-correctness.md` (13 tasks, 269 lines) from the reviewed slice design. Order: Part B (T1-T4) → Part A (T5-T8) → Part C (T9-T12) → final validation (T13), matching the design's sequencing rationale.

**Found and resolved a design-document defect before writing tasks, not silently:** the slice design's Success Criteria and Verification Walkthrough for Parts B and C repeatedly cite `p45b.yaml` as an existing shipped pipeline demonstrating the two-loop-sequence pattern (design→review, then tasks→review). A full repo search found no such file — `src/squadron/data/pipelines/` contains only `judge-cycle.yaml` and `test-loop.yaml`, both single-loop, neither matching the two-loop shape the design describes. Rather than substitute a different pipeline or silently drop the walkthrough steps, raised this to the PM (AskUserQuestion) per the "stop and request clarifying information" rule in the Phase 5 guide and the project's "don't guess, ask" instruction. **Resolved:** `p45b.yaml` is real, provided directly by the PM, and confirmed present at `~/.config/squadron/pipelines/p45b.yaml` — squadron's user pipeline directory (`_USER_DIR`, `loader.py:23`), which `load_pipeline`/`sq run` already discover automatically. No task creates or moves it; Part B's T3 and Part C's T11 reference it by bare name exactly as the design's walkthrough specifies, and its actual two-sequential-single-review-loop shape is the precedent Part B's validation check is designed to keep valid.

**Test-with applied throughout:** T1 (validation check) → T2 (unit tests in `test_loop.py` + `test_loop_validation.py`) → T3 (manual confirm against real `p45b.yaml`); T5 (accumulate `prior_outputs`) → T6 (loop-body integration test) → T7 (end-to-end prompt-content assertion, closing the gap between "data is threaded" and "the consumer actually uses it"); T9 (`--dry-run` expansion) → T10 (CLI test) → T11 (manual confirm against real `p45b.yaml`). Each part's implementation task is immediately followed by its test task, per the guide.

**Next:** Phase 6 (Implementation) for slice 910, not yet started.

### Slice 910: Loop Convergence Correctness — Implementation Complete

**Phase 6 complete.** Branch `910-slice.loop-convergence-correctness` off `main` (`git.integration_branch` unset). All three parts landed in the design's B → A → C order, one commit per part, each preceded by tests confirmed to fail against pre-fix code and pass after.

- **Part B (`4f62163`, #43):** `LoopStepType.validate()` gained `_validate_verdict_count`, gated on `until_val is not None`, which expands every inner step via its registered `StepType.expand()` and counts `"review"`/`"gate"` actions across the full body. **One deviation from the design worth flagging:** the design's sketch called `expand()` on every inner step unconditionally; in practice an inner step whose own config is invalid (e.g. a bare `{"review": {}}` with no `template:`) makes `expand()` raise `KeyError`, because `validate_pipeline()` has never validated inner loop-body steps and never guaranteed they're well-formed before `expand()` assumes they are. Added a guard: skip verdict-counting for an inner step that fails its own `.validate()` first — its own error is a separate, more specific problem than "how many verdicts does this contribute." 23 new/updated tests across `test_loop.py` and `test_loop_validation.py`.
- **Part A (`31c0164`, #42):** `_execute_loop_body` now threads a `running_prior` snapshot (seeded from `prior_outputs`, updated after each inner step with `f"{action_type}-{action_index}"` keys) into each iteration instead of the static outer `prior_outputs` — exactly the design's sketch, no deviations. Two new tests in `test_executor_loop_body.py` prove both halves of the design's Success Criteria separately: `prior_outputs` actually contains the prior iteration's review result, and the resolved prompt text (via `DispatchAction._resolve_prompt_from_prior_review`) contains the prior finding's summary. Both confirmed to fail pre-fix via `git stash`.
- **Part C (`d4fb644`, #45):** single `if step.step_type == "loop"` branch in `run.py`'s `--dry-run` render loop, reusing `unpack_inner_steps` — matches the design exactly. Two new tests in `test_run.py`.

**Verification Walkthrough executed against real artifacts, not just unit tests** (results written into the slice design in place): `sq run --validate p45b` (bare name, no `.yaml`) exits 0 both before and after Part B lands, confirming the existing two-sequential-single-review-loop pipeline is unaffected; a throwaway ambiguous fixture (two `review:` steps + `until:` in one loop body) exits 1 naming both offending steps; `sq run --dry-run p45b 999` (a `slice` target arg is required — the design's walkthrough commands omitted it) shows both loops fully expanded with `max`/`until`/`on_exhaust` and their inner `design`/`tasks` steps.

**Corrections folded back into the slice design's Verification Walkthrough section**, since the original commands as drafted don't work against the real CLI: pipeline names passed to `sq run` omit the `.yaml` extension (the loader appends it), and `p45b.yaml` requires a trailing `slice` target argument.

**Full validation gate:** `ruff format --check .` (397 files, all formatted), `ruff check .` (all checks passed), `pyright` full-project strict (0 errors), full `tests/` suite (2697 passed, 2 skipped, 0 failed — no regressions from any of the three parts).

Slice marked complete: frontmatter `status: complete` in the slice design, slice-plan entry (`900-slices.maintenance-and-refactoring.md` item 8) checked off with completion date. Issues #42, #43, #45 to be closed on merge per the task file's final-validation step.

**Next:** merge `910-slice.loop-convergence-correctness` into `main`. Slice 911 (Loop Iteration Versioning and Review Evidence) is scoped-only and depends on this slice's Part A, now landed — ready to move into Phase 4 (Slice Design) when picked up.

### Slice 911: Loop Iteration Versioning and Review Evidence — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/911-slice.loop-iteration-versioning-and-review-evidence.md` on `main` (planning work, no slice branch), from slice-plan entry 9 in `900-slices.maintenance-and-refactoring.md`. Three parts: A per-iteration commits (#44), B `revision_number:` frontmatter on the artifact, C the round contract.

**Part D split out to a new slice 912**, per PM decision and on the plan entry's own instruction ("if it grows, split it rather than expanding the slice"). Part D — may a reviewer see the prior version, and do findings carry forward — is the prerequisite *consumer* of 911's output, not part of it: it needs per-iteration commits to diff against and `revision_number:` to name the round it is judging. Added as slice-plan entry 10 with the original framing (anchoring risk, the #32 failure shape, the clean-eyes-plus-addressed-check candidate resolution) preserved verbatim, and the "needs a design conversation before its Phase 4 design is written" flag carried over.

**Corrected the plan entry's central factual premise.** Part A's scoping said "a `commit` step type already exists, so the machinery is present." It does not exist: `commit` is an *action* (`ActionType.COMMIT`), absent from `StepTypeName`, emitted only by phase-step expansion (`phase.py:176`), and `docs/PIPELINES.md` documents "Constraint: no per-iteration commit" as a hard rule. Consequences, verified on disk and now driving the design:
- A loop whose body is **phase steps** (`p45b.yaml`) **already commits every iteration** — issue #44's premise is false for that shape. The real gap there is that all three rounds emit the identical message `chore: phase-4 slice {n}`, so `git log` cannot tell them apart.
- A loop whose body is a bare **`dispatch:`** (`judge-cycle.yaml`, `test-loop.yaml`) commits nothing, which is #44 as written.
- `CommitAction` no-ops on a clean tree, returning `success=True, outputs={"committed": False}` (`commit.py:37-42`). So #44's hoped-for "empty commit is a useful signal" does not happen today — a byte-identical round leaves *no* trace at all. Part A makes that a WARNING, since it is exactly the #42 symptom.

Part A therefore splits three ways: A1 iteration-qualified commit messages (add `iteration` to `ActionContext`, which `_execute_step_once` already receives), A2 opt-in `commit_each_iteration: true` on `loop:` with validation that **rejects** it when the body already commits (mirroring 910 Part B's reject-the-ambiguity stance rather than tolerating a silent double-commit), A3 the no-change WARNING.

**Part B hooks onto 909 Part A's machinery**, which was the useful find: `_expected_artifact_paths()` (`executor.py:109-121`) and the dispatch artifact post-condition (`executor.py:1064-1082`) already resolve and confirm the file a phase-step dispatch was supposed to write. Squadron stamps `revision_number:` immediately after that check passes, so it only ever writes into a file it has confirmed exists from this run. Squadron never authors slice designs or task files itself — `DispatchAction` has no file-write code — so agent-side stamping was rejected as unreliable (a missed stamp is indistinguishable from a pre-field artifact). Also confirmed **no generic frontmatter read/modify/write utility exists**; `read_review_frontmatter` (`metrology/identity.py:162`) is lenient but review-scoped and declares itself the only reader of a persisted review. New `documents/frontmatter.py` provides the general primitive and `read_review_frontmatter` delegates its parse to it, so there is one lenient parser rather than two.

**Part C decisions:** clean regeneration (a round regenerates; `revision_number:` is the only carryover; round history lives in git, not in the document), and absent `revision_number:` means "never stamped by squadron" — explicitly *not* round 1, so readers must not default it. `revision_number:` is monotonic across runs (read prior, write n+1), not the loop's iteration index, since "which revision am I looking at" is the question it answers.

**Cross-repo seam recorded, not crossed.** `project-documents/ai-project-guide` is a git submodule (`ecorkran/ai-project-guide`); its `file-naming-conventions.md` is the canonical frontmatter schema Context Forge also reads. Per PM decision the slice is squadron-side only; registering `revision_number:` in that schema is a follow-up in the guide repo, and whether CF's own frontmatter consumers tolerate an unregistered key must be confirmed before it is proposed. `docs/PIPELINES.md` also needs its "no per-iteration commit" section replaced, tracked as a Part C task.

**Field named `revision_number`, not `version` (PM decision, same day).** The design initially proposed `version:`. PM raised that registering a field makes it *usable* — other agents will read it and some will write it — so its semantics have to ship with it rather than after it. Two responses: (1) added a **Field contract** table to Part C stating what the field counts, that squadron alone writes it, that absent means *no information* rather than round 1, which docTypes it is defined for, and that nothing may branch on its value; (2) renamed it. `version` invites the semver misreading; `revision` alone still leaves room to treat the value as a label; `revision_number` cannot be read as anything but an integer counter, so nothing downstream can reinterpret it as a draft state or stage name.

**Also corrected during review of the design: the p45b commit account.** The first draft said a phase-bodied loop "already commits once per iteration." True only conditionally. The commit is the *last* action in the phase expansion `[cf-op ×3, dispatch, review, checkpoint, commit]`, and `_execute_step_once` returns immediately on any action failure (`executor.py:1116-1124`) or on a checkpoint `Exit` (`executor.py:1104-1111`). A review action returns `success=True` regardless of verdict (`review.py:288`), so a FAIL alone does not skip the commit — but `checkpoint: on-fail` fires on FAIL *and* UNKNOWN (`checkpoint.py:23`) and sits one line before the commit (`phase.py:174-176`). Choosing Exit at that prompt discards the round entirely: no commit, loop short-circuits to PAUSED. So the rounds most worth keeping are the ones most likely to be dropped, and every round that *is* kept emits the byte-identical message `chore: phase-4 slice {n}` — three indistinguishable `git log` lines.

**Sequencing:** A1 → B → A2/A3 → C. A1 first because both Part A's messages and Part B's review-file stamping depend on `ActionContext.iteration`; B second because it is the only genuinely new code and the only part carrying a document-corruption risk worth isolating in its own commit.

**Next:** Phase 5 (Task Breakdown) for slice 911, not yet started. Slice 912 needs its design conversation before Phase 4.

### Slice 911: Loop Iteration Versioning and Review Evidence — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/911-tasks.loop-iteration-versioning-and-review-evidence.md` on `main` — 21 tasks across four groups (A1, B, A2/A3, C), 346 lines, no split needed. Test-with throughout: every implementation task is immediately followed by its test task, and T3's tests gate the start of Part B.

**One design correction found while writing the breakdown, and it was worth the pass.** The design specified `ActionContext.iteration: int | None = None`. The executor already declares `iteration: int = 0` on `_execute_step_once` (`executor.py:995`), and only the two loop paths pass it (`_execute_loop_step` `:1201`, `_execute_loop_body` `:1309`) — the top-level, `each`, and `fan_out` callers take the default. Adding an `int | None` alongside it would have created a second sentinel for the same concept and forced a conversion at the one place they meet. Changed the design to `iteration: int = 0` with `0` meaning "not inside a loop", and rewrote the three gating conditions (A1's message suffix, A3's no-change warning, Part B's stamp gate) from `is not None` to `>= 1`.

Same pass tightened the interface-parity note: there are **two** paths that emit no `revision_number:` key — a review action running outside a loop (`iteration == 0`) and a CLI-invoked `sq review` (never goes through the action at all). The design had only recorded the CLI one.

**Two places where the breakdown deliberately constrains the implementer rather than leaving a choice:**
- **T12** must factor out and reuse the traversal inside `_validate_verdict_count` (`loop.py:165-213`) instead of writing a second inner-step walk. That helper skips any inner step failing its own `validate()` before calling `expand()` (`loop.py:186-190`) because `expand()` raises `KeyError` on an incomplete config — a fix landed during slice 910 implementation. An independent walk would reintroduce that crash, so T13 carries an explicit regression guard for it.
- **T14** must keep the loop-appended commit's staging identical to the phase-emitted one (`git add -A`). Scoped staging is tempting, but applying it to one of two commit paths is worse than the sweep it avoids; noted in the design's Risk section as a follow-up, not a change to make inconsistently.

**T21 carries a live external dependency:** re-check ai-project-guide issue #14 before close-out. If it settles on a name other than `revision_number`, rename during Phase 6 rather than shipping a name that needs migrating afterward. The task file also tells the implementer not to change the field name on their own initiative.

**Next:** Phase 6 (Implementation) for slice 911 — branch `911-slice.loop-iteration-versioning-and-review-evidence` off `main`, not yet created.

---

## 20260730

### `/sq:summary --restore <key>` — reaching a specific saved summary (#7)

`--restore` picked the most recent summary by mtime, unconditionally, so once a newer summary was written the older one could not be reached at all — even though the multi-summary picker was already listing it by key. Added an optional `--key` that filters on the same key the picker displays.

Key matching is case-insensitive, so the same argument resolves identically on case-sensitive and case-insensitive filesystems. Key derivation is shared between the picker listing and the filter rather than implemented twice, so the naming rule lives in one place. Bare `--restore` is unchanged — most recent still wins. An unknown key exits 1 and lists what is available; the one behavior deliberately not implemented is falling back to the most recent, which would restore a summary the user did not ask for and give no sign of it.

Closes #7 part (a). Part (b) — interactive runs also writing to the restorable summaries location — remains open in the 140 future-work list.

---

## 20260729

### `sq review code` computed the diff against the wrong base

`resolve_slice_diff_range` hardcoded `main` as the merge-base ref. On a repo with `git.integration_branch` set — or any repo where earlier band work had already been promoted to main — the three-dot diff returned the entire accumulated band rather than the slice's own changes. The consequence is worse than a noisy diff: the reviewer fanned out over dozens of already-merged, already-reviewed files and converged on PASS, reporting a confident verdict on code that nothing had actually reviewed. A review that examines the wrong input and passes is indistinguishable from one that examined the right input and passed.

Reproduced on a scratch repo before fixing: a slice branch forked from `dev/erik` returns 2 files against `main` (including an unrelated integration-branch commit) and 1 file against `dev/erik`.

`ContextForgeClient.get_config(key)` reads `cf config get <key> --json`; `resolve_diff_base()` resolves `git.integration_branch` and **degrades to `main`** when the key is unset, when cf is absent, or when the read fails — `sq review --diff` has to keep working with no Context Forge installed, so this path never raises. `resolve_slice_diff_range` gained `base=None` (resolve from config) so both existing callers pick up the fix without changing. `_find_merge_commit` searches base first, then main: reachability means a slice merged before the integration branch was adopted is normally still found on base, and the fallback covers the rest.

---

## 20260728

**Fixed the new-user install path (#29). Released v0.8.1.**

Started from a real report: install via `uv`, discover you have `sq` but no `cf`, and nothing tells you. Issue #29 had it filed. Investigating turned up worse than what was reported.

**The instructions pointed at a package that does not exist.** Every shipped reference — `doctor_checks.py`, `install.sh`, two tests — said `npm i -g @manta-digital/context-forge`. That 404s. Anyone following our own output hit a dead package.

Finding the right name needed care rather than a guess. The obvious candidate, `@context-forge/core`, is **wrong**: it declares no `bin` at all, so installing it leaves the user with no `cf`. The unscoped `context-forge` on npm is an unrelated third party's project — "correcting" to it would install someone else's software. The answer is `@context-forge/cli`, which declares `bin: {cf}` and pulls `core` in transitively; verified by installing into a clean sandbox and running the binary, not by reading metadata.

**`sq doctor` hid the remedy it already knew.** `doctor.py:67` read `fix_hint and status != WARN or (fix_hint and verbose)`. `and` binds tighter than `or`, so a WARN row without `--verbose` printed the problem and swallowed the fix. Missing `cf` was a WARN. The clause was also dead: line 58 already skips WARN rows unless verbose, so any row reaching line 67 should show its hint unconditionally. Simplified to `if row.fix_hint`.

**All seven remediation anchors were dead**, not the one #29 reported — they pointed at `step-N-...` headings that never existed in QUICKSTART. Slug-matched every entry against real headings and added a test that fails if any stops resolving. The provider entries deliberately share one anchor: QUICKSTART documents providers in a table, not per-provider subsections, so giving each its own would recreate the same dead link.

**`sq setup` now installs rather than advises.** It had no execution path at all — 218 lines of renderer, zero `subprocess` calls. It printed `sq install-commands` and `npm i -g ...` and trusted you to run them. Now Enter runs them: `/sq:` commands in-process, `cf` via npm, then `cf install-commands` for `/cf:`. Scope is deliberately narrow — provider credentials stay advisory, because those need a human decision or a secret.

**`cf init` is deliberately not automated.** It writes guides and IDE config *into the current directory*, so it belongs to a project the user picked, not to a global setup pass that might be running anywhere. Setup ends by pointing at it. Verified `cf install-commands` is standalone and user-global (installs all 9 `/cf:*` into a clean fake HOME with no project and no `cf init`) and idempotent, so a later `cf init` cannot conflict.

`cf` also changed from optional to required: Squadron assembles every dispatch prompt through it, so an install without it is broken, not reduced. That reclassification alone would have unhidden the fix hint, since the precedence bug only suppressed WARN.

---

**Released v0.8.0.** First tag since v0.7.0 on 20260714 — 179 commits over two weeks.

The headline is **initiative 320 (Judge Calibration & Quality Metrology) landing whole**: all five slices, from the metrology store and blind human-sample capture (320), through agreement/dispersion/trend reporting (321) and the calibration-to-threshold feedback loop (322), to the tech-debt-audit oracle's data half (323) and its intervention (324). Alongside it: the `gate` step, the `judge-cycle` reference pipeline, substantial provider rate-limit handling, and a long run of review-correctness fixes (#18-#24).

Minor bump rather than major: everything is additive. No CLI surface was removed or renamed, and pipelines that don't opt into the new steps behave exactly as before — the 324 work in particular was built so that a pipeline without `pre_emption_fragment` produces a byte-identical prompt.

**CHANGELOG housekeeping.** The `[Unreleased]` section had accumulated *two* separate `### Fixed` blocks from incremental appends across the initiative; merged into one under `[0.8.0]`. Three user-facing items had also never been written up despite shipping: the rate-limit backoff work, audit liveness reporting, and the new model aliases (Fable 5, Opus/Sonnet 5, Kimi K2.7, GLM 5.2, MiniMax M3, Trinity). Added. `docs/COMMANDS.md` gained the `metrology.preemption_fragment_dir` row it was missing.

**Known gaps carried into the release**, none blocking: 324's live `audit delta` was never run end-to-end (the audit harness spawns the Claude Code CLI, which refuses to nest inside a Claude Code session) and is covered by fixture plus stubbed-harness tests; two pre-existing failures in `tests/review/test_content_injection.py` are unrelated and reproduce with all 324 work stashed; slice 344 remains `deprecated` with its plan entry checked; and the 322 review verdict still parses as `UNKNOWN` (issue #28).

---

**Slice 324 implemented — pre-emption prompt & delta measurement. Initiative 320 closed.**

The audit oracle's intervention half, and the last of initiative 320's five anticipated slices.

**What shipped.** `squadron.metrology.preemption` renders a project's stored 323 baseline into a static guidance fragment from a fixed, human-authored `CATEGORY_GUIDANCE` table (one line per `AuditCategory`) — deliberately not model-generated prose, which would reintroduce the per-run non-determinism 323 spent the slice normalizing away. `audit_delta.py` compares a fresh run to the baseline against the floor's *observed spread* (`max - min`), never a derived confidence interval. `sq metrology preempt generate [--check]` and `sq metrology audit delta` are the surfaces; they live in `cli/commands/metrology_preemption.py` because `metrology.py` had already reached ~1000 lines, and mount onto the existing apps so the command surface is unchanged.

**The injection point.** `DispatchAction._apply_pre_emption_fragment` prepends *after* `_apply_override`, so a checkpoint override stays innermost and nearest the task. `pre_emption_fragment` threads through `DispatchStepType.expand()` and `PhaseStepType.expand()` conditionally, matching the existing `if "prompt" in cfg:` idiom — all 32 pre-existing exact-dict-equality `expand()` assertions pass unmodified, which was the design's stated criterion for the field being genuinely additive.

**Three-state, not boolean.** `within_floor` is `True`/`False`/`None`, where `None` means no floor was measured. An unmeasured floor licenses no claim in either direction, and `False` would read as "measured, and significant." Same discipline in the fragment reader: missing, unreadable, and malformed/empty each degrade to a skipped prepend plus a *distinguishable* WARNING — never a dispatch failure. That asymmetry with 323's audit-run handling (which must persist nothing) is deliberate: a missing fragment has no measurement to poison.

**One model change.** `ProjectBaseline` gained a required `measured_at`, populated from `run.measured_at` at its single construction site. T2/T3 required the fragment to stamp the baseline's timestamp, but `ProjectBaseline` carried only `run_id`; the alternative was re-fetching the `AuditRun` by id — redundant I/O to recover a field `baseline_report` already had in hand. PM approved.

**Two things real data taught us.** The multi-instrument guard fired on the first live attempt: `migratory-viewer` spans two audit instruments, so the fragment refuses rather than silently picking one (a project audited at several commits under *one* instrument is fine — most recent wins). And the live `audit delta` run failed with `Claude Code cannot be launched inside another Claude Code session` — the audit harness spawns the Claude Code CLI and the implementation session ran inside Claude Code. The guard was not bypassed; unsetting `CLAUDECODE` risks crashing active sessions. That failure did verify the refusal path for free: `the audit run failed (stream_error) — no delta computed`, exit 1, no partial delta. The end-to-end delta render remains outstanding and is recorded as such in the slice's Verification Walkthrough rather than quietly marked done.

**Also noted.** Two pre-existing failures in `tests/review/test_content_injection.py` (truncation tests) are unrelated to 324 — confirmed by stashing all 324 work and reproducing them identically. Issue #40 (empty system prompt on one-shot dispatch) stayed out of scope as planned.

---

### Slice 324 task breakdown (Phase 5) — 13 tasks, closes initiative 320 on completion

Created `324-tasks.pre-emption-prompt-delta-measurement.md` (228 lines) from
the Phase 4 design, verified against current code rather than re-derived
from the design's prose alone: confirmed `_apply_override`,
`DispatchStepType.expand()`/`PhaseStepType.expand()`'s conditional-forward
idiom, and `audit_report.baseline_report`/`ProjectBaseline`/`BaselineCell`
signatures all still match what the design cites, and that
`metrology.preemption_fragment_dir` is not yet registered in
`config/keys.py`.

**Sequencing:** fragment/delta Pydantic models (T1) → fragment generator
and its fixed `CATEGORY_GUIDANCE` mapping (T2-T4, test-with) → delta
computation (T5-T6, test-with) → the one new config key (T7, ordered before
anything reads it) → the dispatch injection point itself, extending
`_apply_override`'s prepend with full failure-mode handling (T8) → threading
`pre_emption_fragment` through both `expand()` methods (T9) → tests proving
every pre-existing exact-dict-equality `expand()` assertion still passes
unmodified (T10) → CLI shells for `preempt generate [--check]` and `audit
delta` (T11-T12) → end-to-end verification (T13).

**Notes carried into the task file, not to be re-litigated:** the injection
point is `DispatchAction._resolve_prompt`, strictly after `_apply_override`,
never touching `cf_op.py`; `expand()` stays a pure dict transformation with
no new file I/O; a broken/missing/malformed fragment file always degrades
to a skipped prepend plus a `WARNING`, never a dispatch failure; issue #40
(empty system prompt) stays out of scope.

T13, once complete, is where 324's own frontmatter status and the 320
slice plan both get marked complete — closing initiative 320's fifth and
final anticipated slice. Not done yet; tasks are `not_started`.

**Next:** Phase 6 implementation of `324-tasks.pre-emption-prompt-delta-measurement.md`.

---

### Slice 324 designed: pre-emption prompt & delta measurement (Phase 4) — closes the 320 slice plan

Created `324-slice.pre-emption-prompt-delta-measurement.md`, the fifth and
last anticipated slice of initiative 320. Depends on 323 (complete,
20260727): the persisted baseline and its measured noise floor are what
324's fragment and delta report consume.

**The substantial design question was the injection point, not the delta
math.** The slice plan left "pre-emption fragment format and regeneration
cadence" explicitly open. Investigation (two rounds of Explore-agent
research plus direct verification) found **no static-prompt-injection
point exists anywhere in dispatch today**: `AgentConfig.system_prompt`
exists on `DispatchAction` but is never populated by any current
`expand()` — dead wiring, always resolving to `""`. The production
design/tasks/implement prompt is assembled entirely by an external `cf
build` subprocess (`cf_op.py:95-111`), passed through byte-for-byte; the
only point in squadron's own code that already concatenates onto an
assembled prompt is `DispatchAction._apply_override` (`dispatch.py:291-302`,
the checkpoint-override prepend). Decision: extend that same prepend
pattern with a new opt-in `pre_emption_fragment` param, threaded through
`DispatchStepType.expand()`/`PhaseStepType.expand()` only when a pipeline
explicitly sets it — additive by construction, verified safe against the
existing exact-dict-equality `expand()` tests, and never touching
`cf_op.py` or context-forge.

**A pre-existing bug surfaced and was filed separately, not folded in.**
Tracing `system_prompt`'s dead wiring found that `one_shot_dispatch`
always sends `instructions=""` (not `None`), which per `AgentConfig`'s own
docstring sends a literal empty `--system-prompt ""` to the Claude Code
CLI — stripping the CLI's default tool-use discipline on every one-shot
dispatch today, independent of 324. Further verified this has no
equivalent fix for non-SDK providers: `use_default_system_prompt` is read
only by `sdk/provider.py`; the `openai`-backed profiles (`openrouter`,
`gemini`, `local`, plain `openai`) and `codex` never read it at all, and
have no analogous "use your own default persona" concept to fall back to.
Filed as [#40](https://github.com/ecorkran/squadron/issues/40), split
into the fixable SDK-profile case and the genuinely open non-SDK-provider
design question — not addressed in 324's scope.

**What the design commits to:** a fixed (not model-generated) ten-line
category-to-guidance mapping rendered from 323's `ProjectBaseline.cells`,
written to a static file by an explicit `sq metrology preempt generate`
command (never auto-regenerated), with a `--check` freshness mode
comparing the fragment's recorded `audit_prompt_hash` against the current
baseline. The delta report (`sq metrology audit delta`) re-runs one audit
(not a variance series) and compares to the stored baseline, flagging any
delta smaller than the floor's observed spread as indistinguishable from
noise, with a fixed observational/non-causal disclaimer on every report.
No new store record type — the delta is computed on demand from existing
`AuditRun` records, not persisted.

Updated `320-slices...md` (324 entry annotated `*(designed — see
...)*`) and `320-reference...md` (status table and glossary — also
corrected 323's row, which still read "not started" despite being
`status: complete` since 20260727; the reference doc's own stated
authority rule is the slice design's frontmatter wins over this table).

**Next:** Phase 6 implementation of 324, the initiative's terminal slice.

---

## 20260727

### Slice 323: Phase 6 Implementation and First Noise Floor

**T1-T21 complete; T22 complete for two projects, two deferred.** Three measurable results.

**The dispersion is a property of the instrument, not a model.**

| Instrument | Runs | Mean | Spread | % of mean |
|---|---|---|---|---|
| Opus, hash `d17ac6bf` | 22, 25, 27, 30 | 26.0 | 8 | 31% |
| Sonnet 5, hash `a5bc5b31` | 19, 22, 27 | 22.7 | 8 | 35% |

Two models, two sessions, two prompt hashes, the same absolute spread of 8 findings — a claim neither series could support alone.

**It widens with codebase size, worse than proportionally.**

| Project | LOC | Runs | Mean | Spread | % of mean |
|---|---|---|---|---|---|
| migratory-viewer | 3.2k | 19, 22, 27 | 22.7 | 8 | 35% |
| migratory | 44.4k | 49, 60, 82 | 63.7 | 33 | **52%** |
| squadron | large | 17, 79, 71 | 55.7 | 62 | **111%** |

On squadron the spread **exceeds its own mean** — 17 findings on one run, 79 on another, same unchanged commit. `migratory` clears the fan-out condition (44,359 LOC, 9 top-level dirs — the condition is >50k LOC *or* >5 modules) and run 1 made **360 tool calls** against 60-80 for a viewer run. This confirms the design's stated risk that fan-out is itself a variance source and can vary *within* a series, since the threshold is a prompt instruction rather than enforced code. It is also the concrete justification for the per-project floor decision: a single global threshold would understate large repos badly.

Two cautions on reading these numbers. Squadron's mean (55.7) is *lower* than the smaller `migratory` (63.7) only because one run drew 17 — with n=3, a single low draw moves the mean more than the codebases differ. And the floors themselves are correspondingly imprecise: three runs demonstrate that dispersion is large and size-dependent, but do not pin any one project's floor tightly. `metrology.audit_variance_runs` exists to raise that where a tighter floor is worth the cost.

**Per-category dispersion is where the usable signal is.** `architectural-decay` was the most stable category on both projects — 7-7 (sd 0) on viewer, 8-11 on a 14x larger codebase with fan-out — while `type-contract-debt` tripled (1-3 → 4-12). Some categories are plausibly gate-worthy today; totals are not. That distinction is what 324 needs and could not have been guessed from the totals.

The category vocabulary held across both: `other` was 0/22 and 2/49 (~4%).

**Deliberate deviation from the task text.** `AuditCategory`/`AuditSeverity`/`AuditEffort`/`AuditFinding`/`FloorStat`/`AuditRun`/`AuditNoiseFloor` all live in `metrology/models.py`, not `audit_models.py`. `AuditRun.findings` and `AuditNoiseFloor.per_category` embed them, so defining them separately would reintroduce the circular import the 322 layering correction removed. `audit_models.py` re-exports the full set.

#### Defects found by running it, not by testing it

Nine defects surfaced in T22 that fixture tests could not have caught. In rough order of how much they cost:

1. **`rate_limit_event` is not a throttle.** The CLI's own schema describes it as "emitted when rate limit info changes" — a usage-meter status event whose `rate_limit_info.status` is `allowed | allowed_warning | rejected` — and the CLI's own SDK adapter ignores the type outright (`[sdkMessageAdapter] Ignoring rate_limit_event message`). Squadron substring-matched `"rate_limit"` and slept. On a heavily-used account these fire constantly, so every audit paused and restarted its stream on each usage tick. Every "Rate limited (attempt N/10)" line before `72bbcb3` was a meter update; the account was never throttled. Measured payloads confirmed it: 12 events in a healthy 471s run, all `status: allowed`.
2. **A parse failure kills the stream permanently, so the old skip never worked.** The SDK calls `parse_message` *inside* the `async for` driving its message generator (`_internal/client.py:141`), so a raised `MessageParseError` terminates that generator — every later `__anext__` raises `StopAsyncIteration`. `_skip_unparseable` caught and `continue`d on a corpse. Short runs ended quietly with partial output, which is why this went unnoticed until an audit long enough to span a meter update. Fixed by absorbing informational events in the parser itself (`install_rate_limit_parser_shim`) so nothing raises. Two SDK call sites needed patching — client mode imports at call time, query mode binds at module scope — verified rather than assumed after patching one left the other broken.
3. **The whole skill file was being sent as the prompt.** `build_audit_prompt` sent all 17KB including YAML frontmatter (`disable-model-invocation: true`) and 6.5KB of human installation docs. The model read it as a document and returned ~2KB of acknowledgement. `extract_audit_protocol` now strips both halves: 17430 → 10975 bytes.
4. **The findings were being read from the response stream.** The design's own recorded ground truth said the skill writes a file and does not return findings; the harness parsed the stream anyway. `find_audit_file` now locates the file, mtime-restricted so a stale audit cannot persist under a new run id.
5. **Wrong artifact path, twice.** Output goes to `project-documents/user/analysis/`, not `analysis/`, because the skill cites `file-naming-conventions`. Also git collapses a wholly-untracked tree to its *shallowest* ancestor (`?? project-documents/`), so every prefix of both locations must match the dirty-worktree exemption.
6. **The variance series refused its own output file** — would have produced zero floors campaign-wide (`5340c0f`).
7. **No `Write`/`Edit` in the allowed-tools list** while the audit's entire product is a file. It did not fail loudly: the model routed around it via Bash heredocs.
8. **Zero-delay retry loops.** Both carried a comment claiming "the CLI handles the backoff delay" and slept for nothing — measured at 11 attempts in 0.1ms. Also present on the pipeline path (`sdk_session.py`), so it affected review and dispatch equally, not just audits.
9. **The retry budget never reset.** Initialised outside the loop, so it bounded throttles-per-run rather than consecutive failures; a long run exhausted it while still making progress.

#### Instrument provenance was unpinned in three ways

All three were invisible in the stored record, and all three can drift:

- **Model.** Squadron sent no `--model`, so the CLI chose its own — measured as `claude-opus-4-6[1m]`, the most expensive option available. The record stored the literal `"sdk"` and so could not say what ran. Fixed by `metrology.audit_model` (`aee96b2`), which also writes the resolved model onto the record.
- **Effort and thinking.** Squadron sends neither `--effort` nor `--thinking`; `AgentConfig` has no fields for them, so they are structurally unreachable rather than merely unset. The CLI's default for these is *undocumented and unreported*. Filed as #33.
- **The skill's own output.** Now required to carry a `model:` frontmatter field (canonical fork `bf94c72`, vendored in sync). This moved `audit_prompt_hash` `d17ac6bf` → `a5bc5b31`, closing the Opus generation — accepted deliberately rather than reverted.

#### Open, filed, not fixed

- **#34: squadron draws ~3x the session budget of the same skill run interactively.** Same model, same repo, same commit: ~1% manual vs ~3% squadron. Model is eliminated as a cause. Tool-call counts (60-80) against a raw-CLI baseline of 63 do not obviously explain it either.
- **#30: the SDK pin is now blocking, not hygiene.** Squadron runs the SDK's *bundled* CLI 2.1.47 (July 8) while interactive sessions run 2.1.220 — ~170 versions apart. This invalidated every squadron-vs-manual comparison attempted during the session until it was found, and it is why the parser lacks a `rate_limit_event` case at all.
- **#33/#36: token and cost capture.** `ResultMessage` carries full usage accounting; `translate_sdk_message` discards all of it. One measured audit: 2.17M cache-read, 137k cache-creation, 15k output, $2.37. Note for whoever implements it — **do not sum per-message `usage`**, it repeats a snapshot within a turn (7.08M summed vs 2.17M authoritative, while understating output 2,174 vs 15,231).
- **#35: alternative providers.** Cross-model agreement is a stronger quality signal than one model's repeat rate, and unreachable while the harness is Anthropic-only.
- **#38: SDK teardown leaks an unretrieved task exception.** A successful squadron run printed a raw `ProcessError: exit code -15` traceback mid-campaign. Exit -15 is SIGTERM from the SDK's own `close()`; the run had already completed and persisted. `shutdown()` catches `disconnect()` errors but this one is raised in the SDK's background reader task, which nothing awaits. Cosmetic for data, but it cost real diagnostic time — it was initially mistaken for a truncated run — and a *genuine* teardown failure would look identical.
- **#37: the skill emits inline YAML scalars for prose.** `migratory` run 1 needed `_quote_prose_scalars` repair before parsing (`mapping values are not allowed here`). The retry recovered a complete 82-finding audit rather than discarding it, so the fallback works — but block scalars at the source would remove the failure mode. Deliberately not fixed during the campaign: it changes the skill and therefore `audit_prompt_hash`.

#### Process note

The branch convention slipped: 34 implementation commits went to `main` instead of a `323-slice.*` branch. Caught late, and by then 24 were already pushed. Left as-is at the PM's call. The check belongs at the *first* implementation commit, not partway through.

---

## 20260726

### Slice 322 implemented: calibration-to-threshold feedback (Phase 6) — slice complete, initiative 320 human-oracle chain closed

Implemented all 18 tasks (T1-T18) of `322-tasks.calibration-to-threshold-feedback.md`
directly on `main` (no slice branch existed yet at session start; work proceeded
under the same working tree conventions as the prior planning phases). Full
suite green throughout, strict pyright and ruff clean on every commit. This
is the terminal slice of the human-oracle chain 320 -> 321 -> 322; the 320
slice-plan's `(322)` entry is now `[x]`.

**What shipped**, mirroring the LLD's component structure:
- `identity.py` — `_template_content_hash` (renamed public
  `template_content_hash` during T18, see below) narrowed to exclude the
  `judge:` threshold block, fixing the self-defeating loop: acting on a
  `GRADUATE` recommendation no longer re-keys the config and resets
  accumulated evidence to zero. One-time, deliberate historical re-key.
- `models.py` — `EvidenceSnapshot` and `GraduatedConfig` (version-scoped:
  carries the full `JudgeConfigId` including `template_content_hash`, not
  just `template_name`+`model`), plus `RECORD_TYPE_GRADUATED_CONFIG` and a
  `MetrologyRecord.graduated_config` field behind the existing envelope, no
  store migration. Landed here rather than `calibration_models.py` (T3's
  original location) to avoid a circular import — confirmed with PM mid-T11.
- `calibration_models.py` — `RecommendationDirection`, `ThresholdTarget`,
  `ThresholdRecommendation`, `RecommendationReport`, `OfferTarget`.
- `calibration.py` — surface-agnostic core: `classify_direction` (the
  asymmetric bands — loosening floor-gated, tightening not, precedence
  fixed per the tasks-review F001 finding), `read_current_thresholds`
  (degrades a malformed `judge:` block to `None`+WARNING rather than
  letting `resolve_thresholds`' bare `float()` cast raise — a deviation
  from the task's original wording, confirmed with PM during T7),
  `recommend_thresholds` (the full per-cell report, no-mutation verified by
  test), and `read_current_template_content_hash` (added during T18, see
  below).
- `graduation.py` — `write_graduation`/`find_graduation`/`list_graduations`
  (exact-identity matching, idempotent re-graduate updates in place) and
  `select_residual_offers` (the non-empty-offers architecture guarantee;
  lapsed-graduation detection deferred to the CLI layer per the task's own
  stated allowance).
- `discovery.py` — `discover_judge_results`, a new whole-project judge-result
  enumeration surface that 320 never built (confirmed gap, not a runtime
  choice — resolved at task-breakdown time per tasks-review F003).
  `capture.py`'s `_REVIEWS_SUBDIR` promoted to public `REVIEWS_SUBDIR` so
  both modules share one definition.
- `config/keys.py` — `metrology.graduate_match_rate` (0.9),
  `metrology.tighten_match_rate` (0.6), `metrology.residual_sample_rate`
  (0.1); `metrology.min_evidence_n` reused from 321, not redefined.
- `cli/commands/metrology.py` — `sq metrology recommend`/`graduate`/`offers`,
  thin Typer shells matching the `sample`/`list`/`report` conventions.

**Two correctness gaps found and fixed during T18's verification walkthrough**
(neither caught by unit/CLI tests, which register templates in-process and
never exercise the real load path):
1. **Templates never loaded in the metrology CLI.** `sq review`'s commands
   call `load_all_templates()`; `sq metrology`'s never did. In a real
   separate-process invocation this meant `get_template` always returned
   `None`, every record resolved `unversioned`, and `GRADUATE` was
   permanently unreachable — the walkthrough's very first `report agreement`
   run showed 1 excluded/unversioned sample where 0 was expected, which is
   what surfaced it. Fixed by calling `load_all_templates()` at the top of
   `sample`/`recommend`/`graduate`/`offers`. Exposed `identity`'s hash
   function publicly (`template_content_hash`) since `calibration.py` now
   needed cross-module access. Added a `tests/metrology/conftest.py`
   autouse fixture clearing the template registry around every test, since
   the fix meant `load_all_templates()` now genuinely fires from
   CLI-invoking tests and would otherwise leak the real built-in
   `judge.slice-vs-arch` template across test files that use that same name
   as a hand-built fixture.
2. **`graduate` cell selection was ambiguous across a prompt edit.** It
   filtered only on `(template_name, model, level)` and took the first
   match; when evidence spans a prompt edit (walkthrough steps 5-7's exact
   scenario), two cells can share that triple while differing in
   `template_content_hash`, and the wrong (stale) instrument's evidence
   could be silently graduated. Fixed by filtering to the cell matching the
   template's currently-resolvable hash (new
   `read_current_template_content_hash`), refusing with a clear message if
   none match. Covered by a dedicated regression test
   (`test_calibration_cli.py::TestGraduateCellDisambiguation`).

Both fixes were confirmed with the Project Manager before implementation
(neither was in the task list; both were discovered live during the
walkthrough) rather than patched around silently.

**Verification walkthrough**: all nine steps executed end-to-end against a
scratch repo with an isolated `metrology.store_dir`; actual commands and
output pasted into the slice design. Full suite 2392 passed / 2 skipped
(pre-existing, unrelated) after the two fixes above; pyright and ruff clean
across the whole repo.

**Deferred, correctly absent**: automatic threshold mutation, a new gating
mechanism, the coordinated 300 write-path version field (320-plan Future
Work #1, still open), judge-verdict persistence on the sample (321 Future
Work #2), audit-oracle work (323/324).

### Task Breakdown 323: Tech-Debt-Audit Baseline Harness — Phase 5 Complete

**Phase 5 complete.** Created `user/tasks/323-tasks.tech-debt-audit-baseline-harness.md` — 22 tasks, 370 lines (under the 450 target, no split). Test tasks sit immediately after their implementation task throughout, per the test-with pattern.

**Ordering is driven by one constraint: the instrument must be stable before anything measures with it.** So the fork edits come first (T1-T3: findings block → category vocabulary + independent-run mode → vendor into squadron), with the CI sync guard at T4. Everything downstream hashes the vendored copy, so an unstable instrument early would poison every later comparison.

Sequence: fork + vendor + sync test (T1-T4) → models + store extension (T5-T8) → parser (T9-T10) → harness with failure handling (T11-T14) → variance reduction (T15-T16) → baseline report (T17-T18) → config keys (T19) → CLI (T20-T21) → end-to-end + the real campaign (T22).

**Deliberate cost shaping.** T22 is the *only* task that spends real tokens at scale (the 12-audit campaign). T1-T21 are all testable on fixtures with a stubbed agent at zero token cost, and the task file says so explicitly so an implementer does not casually burn a campaign mid-development. T14's pre-flight test asserts the agent stub was *never constructed* on a misconfigured project — proving zero spend, not just correct behavior.

**Tasks that encode a correctness trap rather than a feature:**
- **T15 per-category zero-fill** — a category absent from one run counts as 0 for that run, not as missing. Otherwise the spread is computed over the wrong denominator and the floor is silently wrong.
- **T13/T14 persist-nothing-on-failure** — the design's Decision 9 restated as an assertion: each simulated failure persists *zero* records. A partial record would let a hung run masquerade as a low-finding sample and bias the floor downward, the same direction the repeat-run hazard threatened.
- **T9 distinct absent-vs-malformed errors** — not stylistic; T13 logs them differently, and conflating them would hide a model that stopped emitting the block at all behind "parse noise."
- **T8 vocabulary-isolation test** — asserts no `AuditSeverity` value equals any review `Severity` value, so a future edit cannot quietly merge two deliberately disjoint vocabularies.
- **T20/T21 honest campaign summary** — a campaign with failed runs must not exit 0 as though all succeeded.

**Open item carried into implementation:** the `other`-category share per project is a real output of T22, not just a metric — a high share means the 9 dimensions do not fit that codebase, which is information for 324 rather than something to suppress.

**Task review resolved (same day, z-ai/glm-5.2 — a new reviewer model for this project).** Verdict CONCERNS with one **FAIL**, and the FAIL was a real defect I introduced: config-key registration was sequenced *after* the task that reads `metrology.audit_timeout_s`, while that task's own text said "this must precede any code that reads them." A self-contradiction that would have failed at implementation, since `get_config` raises `KeyError` for an unregistered key. Config keys moved to T11 ahead of all `audit.py` work; old T11-T18 renumbered to T12-T19; six internal cross-references updated; an explicit ordering note added so a future edit cannot silently re-break it.

- **F002** — T4 asserted the independent-run *marker* was present but never that T2's rewording of the repeat-run clause landed, leaving the design's success criterion unverified. Assertion added. Higher-stakes than a normal coverage gap: an unconditional repeat-run clause would silently correlate variance runs and bias the floor toward zero.
- **F003 (T14 sizing)** — acknowledged, no change, using the reviewer's own reasoning: splitting would create an artificial seam, because Decision 9 makes failure handling *part of* the execution contract rather than a wrapper. A basic-execution task that persisted before failure handling landed would be a partial-record path — exactly what the design forbids.
- **F004** — explicit push-to-remote step added to T3. Vendoring from an unpushed local fork would satisfy squadron while leaving every other fork consumer on the pre-contract instrument.

Worth noting across the three reviews this slice has now had (kimi-k2.7-code and claude-sonnet-5 on the design, glm-5.2 on the tasks): each model found something the others did not, and glm-5.2 was the only one to catch a hard sequencing error — the kind of defect that is invisible when reading a document for sense and obvious when tracing execution order.

---

### Slice Design 323: Tech-Debt-Audit Baseline Harness — Phase 4 Complete

**Phase 4 complete.** Created `user/slices/323-slice.tech-debt-audit-baseline-harness.md`; marked the 320 slice-plan entry as designed. First slice of the **audit oracle** — reuses the 320 spine (persistence + trend) but at the project/issue-class grain, with no agreement dimension.

**Reconnaissance changed the design's shape.** Three properties of the `tech-debt-audit` skill were verified against the file rather than assumed:
- It writes to a **model-chosen path** (`analysis/nnn-analysis.*.md`, `:62`) — capturing response text gets narration, not the audit.
- **Repeat-run mode** (`:103`) makes run 2 of a variance series read run 1 and emit a diff. This biases a measured noise floor *toward zero* — the worst direction, since it makes every later 324 delta look significant. The unmodified skill is therefore incompatible with the measurement this slice exists to take.
- **Category is free text** (the 9 dimensions at `:40-56` are prose headings), so cross-project comparison at the issue-class grain is impossible without a closed vocabulary.

**Key decision — fix the fork, do not wrap it.** The initial approach was composing a prompt in Python (strip the Deliverable/repeat-run sections, append a squadron-authored output contract). PM noted the "shipped" skill *is* our fork (`github:ecorkran/tech-debt-audit`), already adapted for cf/squadron. That removes the only reason to wrap: with the contract in the skill file, `/analysis:tech-debt-audit` and the harness consume one artifact, so **no drift is possible between what users run and what the baseline measures**. Strictly less machinery. Makes `[340]` a real coupling — 323 modifies a shipped 340-band artifact — recorded as a decision rather than a discovery.

**Other decisions of consequence:**
- **Findings block is fenced YAML**, not a markdown pipe table — reuses the known-good frontmatter reader (`identity.py:162`); no table parser exists in the repo. Emitted *in addition to* the human table, mirroring the review system's serialize-twice precedent (`persistence.py:130-186`).
- **Severity vocabularies stay disjoint.** Audit `Critical/High/Medium/Low` is *not* mapped onto review `PASS/NOTE/CONCERN/FAIL` — different things on different artifacts; a mapping would manufacture equivalence.
- **Locations recorded, not resolved** — deliberately unlike the review parser's `_check_path_existence`. The count and class are the measurement; a fabricated location does not corrupt a count, and re-verifying across N×M runs is I/O the measurement does not need.
- **Floor is per-project at a pinned commit**, 3 runs (`metrology.audit_variance_runs`). A project without a measured floor is marked "no floor measured" and never borrows another's. Dirty worktree or mismatched SHAs across a series is *refused, not averaged* — otherwise "unchanged code" is an assumption rather than a verified precondition.
- **One run = one persisted unit**; series reduction is a separate pure pass. At 12-audit scale, a failure on run 3 must not discard runs 1-2, and the reduction stays unit-testable at zero token cost.
- **`audit_prompt_hash` on every record** — same discipline 322 canonized for judge templates. Since this slice edits the skill, baselines across that edit are not comparable and are grouped, not pooled.

**Variance set chosen for contrast, sized from the actual repos** (not assumed): squadron (py, ~64k LOC), migratory (py+GPU, ~44k), context-forge (TS, ~61k — isolates language from size), migratory-viewer (TS/UI, ~6.2k — order-of-magnitude smaller). All resolve identity from a git remote, so no `metrology.project_id` prerequisite. `trading-data` recorded as a **stretch case in Future Work**, not the committed set — it is the most likely to expose whether the 9 dimensions fit a database-heavy codebase, which is a question about the instrument rather than a gate on this slice. Note squadron/context-forge both exceed the skill's 50k-LOC subagent threshold (`:97`), making fan-out a plausible variance source — measured, not mitigated, which is why the small repo is in the set.

**Cost is stated, not hidden:** 4 projects × 3 runs = 12 full-repo LLM audits, plus one baseline run each. Dominant cost of the slice and the reason the harness is resumable by design.

**Fork sync made explicit scope (PM decision).** The skill has three homes — the standalone fork, squadron's bundled `commands/analysis/` copy, and installed `~/.claude/commands/` copies. **The fork is canonical**; squadron vendors it. Chosen over squadron-canonical because the skill is distributable beyond squadron: if squadron led, other consumers would run the pre-contract instrument, and since `audit_prompt_hash` correctly refuses to pool audits from differing prompts, the symptom would be a **silent measurement gap** (audits that never compare) rather than a loud error. Sync is enforced by the category-match test rather than remembered, and the hash is computed from the vendored copy actually used so divergence is recorded in the data even if it escapes CI.

**Slice-design review resolved (same day).** Two independent reviews ran against the design — kimi-k2.7-code (filed to `user/analysis/` for reference) and claude-sonnet-5 (`user/reviews/`). Both returned CONCERNS and both independently found the failure-mode gap, which is why it was treated as confirmed without further verification. The Sonnet review was materially more thorough (6 findings vs 3) specifically because it cross-referenced the architecture, slice plan, and *sibling slice frontmatter* rather than reviewing the document against itself — which is what surfaced the two structural findings kimi missed.

- **F001 failure modes** — real gap, now fixed. Verifying the premise made it stronger than the finding stated: `run_review_with_profile` has **no** handling to inherit (`review_client.py:134-156` is a bare `async for` with only `finally: shutdown()` — no timeout, no exception handling around the stream; every try/except in that module guards file/git I/O). Tolerable for an interactive review, not for an unattended 12-run campaign against an external cwd with subagent fan-out. Added an eight-mode table with detection/response/signal, anchored on Decision 9: **a run persists a complete `AuditRun` or nothing** — so a hung or truncated run can never masquerade as a low-finding sample and bias the floor downward (the same direction Fact 2 warns about). Plus pre-flight checks before token spend, series-degrade-not-abort, and `metrology.audit_timeout_s` (default 3600).
- **F002 `interfaces: []`** — a genuine bug in my frontmatter, diagnosed exactly right by the reviewer as copy-paste from 322. Verified against siblings (320 → `[321,322,323,324]`, 321 → `[322]`): the field lists *downstream consumers*, 322 is `[]` correctly because it is terminal, but 324 consumes 323's baseline and floor. Corrected to `interfaces: [324]`.
- **F003 340 boundary** — recorded in the parent architecture's Related Work, which had described 340 as read-only ("ships the analysis pack... this component's code-quality oracle runs"). It now states 323 makes it read-write, names the MIT fork as canonical, notes edits reach every consumer of that fork, and records PM approval. The reviewer graded this NOTE and credited the disclosure, correctly — but the sign-off lived only in conversation and the DEVLOG, not where a future reader of the architecture would find it.

**Fan-out on the large repos is expected and deliberately not suppressed.** `:97` dispatches Task subagents above 50k LOC / 5 top-level modules — squadron and context-forge clear it. It is a prompt instruction, not enforced code, so it may vary *within* a series and widen that project's floor. That is correct: it is noise a real user of the skill experiences, so it belongs inside the measured floor rather than engineered out of it.

**One plan-level open question resolved:** finding-normalization schema + repeated-run count (both recorded in the 320 plan Notes). Four Future Work items opened: human-table fallback parser, `trading-data` stretch run, periodic re-audit cadence, project registry.

---

## 20260725

### Slice 321 implemented: agreement & dispersion reporting (Phase 6) — slice complete

Implemented all 17 tasks (T1–T17) of `321-tasks.agreement-dispersion-reporting.md`
on branch `321-slice.agreement-dispersion-reporting`, forked from `main` after
fast-forward-merging the completed 320 keystone branch. Each task committed
separately per its task-file commit marker; full suite green throughout
(2324 passed, 2 pre-existing skips), strict pyright and ruff clean on every
commit.

**What shipped**, mirroring the LLD's component structure:
- `metrology/levels.py` — `ArtifactLevel` enum + `derive_artifact_level`, a
  single module-level dict mapping the review types the code actually
  produces (`judge.tasks-vs-slice`/`tasks`, `judge.slice-vs-arch`/`slice`,
  `arch`) to a level, `UNCLASSIFIED` as the explicit fallthrough.
- `metrology/report_models.py` — the typed Pydantic report shapes 322 will
  consume (`GroupKey`, `AgreementCell`, `ArtifactKey`, `DispersionCell`,
  `ExclusionSummary`, `AgreementReport`/`DispersionReport`/`TrendReport`),
  all JSON round-trip tested.
- `config/keys.py` — `metrology.min_evidence_n` (default 5) and
  `metrology.trend_bucket` (default `month`), added *before* the
  report-computation tasks that read them (slice-review F004).
- `metrology/report.py` — the aggregation core, surface-agnostic, no Typer
  import (asserted by test):
  - `enrich_samples` — the one join pass. Re-reads each sample's referenced
    review file, verifies its `content_hash` against a freshly-derived one,
    and only on a match joins the judge verdict; any mismatch, missing
    file, or unparseable/verdict-less frontmatter marks the sample
    `stale-judge-result` with `judge_verdict=None` — never joined to the
    wrong verdict. The same read yields `sourceDocument` for the dispersion
    key, at no extra I/O cost.
  - `agreement_report` — groups admissible samples by
    `(ArtifactLevel, JudgeConfigId)`; naive percent match rate + n;
    `below_floor` when n is under the configured floor; unversioned records
    (`template_content_hash is None`) segregated into their own cell,
    never pooled with a hash-bearing same-name+model record.
  - `dispersion_report` — groups by **artifact identity**
    `(project_id, source_document, ArtifactLevel)`, per the F001 fix from
    Phase 4; only artifacts graded by ≥2 distinct `JudgeConfigId`s produce a
    cell (the cross-config dispersion the slice ships); the same-config
    repeated-measurement path is structurally supported by the same
    grouping but stays dormant until 300 FW#1 lands.
  - `trend_report` — buckets by `captured_at` (`day`/`week`/`month`) and
    reuses `agreement_report`/`dispersion_report` per bucket — the grain is
    never re-derived.
- `cli/commands/metrology.py` — a `report` sub-group
  (`sq metrology report agreement|dispersion|trend`), thin Typer shells with
  `--project`/`--level`/`--json`/`--cwd` (`--bucket` on `trend`); `--json`
  emits the report model verbatim via `typer.echo` (not `rprint`, which was
  found during T16 to corrupt JSON output by line-wrapping it at terminal
  width — a real bug caught by a CLI round-trip test, not a cosmetic one).

**Bugs found and fixed during implementation** (beyond the planned scope):
- `rprint(report.model_dump_json())` wrapped long JSON lines at the Rich
  console width, invalidating the JSON — `--json` output is machine-facing
  and must never be routed through a wrapping console printer. Switched all
  three report commands to `typer.echo`, matching the convention already
  used by `review.py`/`doctor.py` for JSON output. Caught by
  `test_report_cli.py`'s JSON round-trip assertion, not by a human reading
  the terminal.

**Verification Walkthrough executed end-to-end** (not just read) against a
scratch git repo: captured two levels of agreement evidence, confirmed
per-level rows with n and `below_floor` marking, overwrote a review file and
confirmed `stale-judge-result` exclusion, captured a second judge config
against the same artifact and confirmed one dispersion cell (not two, and
not keyed on the differing `result_ref`s), confirmed the "no multi-config
artifacts yet" honest-empty line on a single-config store, ran `report
trend --bucket month` and confirmed grain preservation, and confirmed
byte-for-byte store/review-file invariance (SHA-1 snapshot before/after)
across all three report commands. The slice design's Verification
Walkthrough section was updated in place with the actual commands and
observed output.

**Full validation (T17):** `uv run pytest` — 2324 passed, 2 pre-existing
skips (unrelated to metrology); `uv run pyright` — 0 errors repo-wide;
`uv run ruff check` / `ruff format --check` — clean. Slice 321 marked
`status: complete` in its slice-design frontmatter; the 320 slice-plan
entry `(321)` checked off; all 17 task-file items checked off via
task-checker.

Relative effort 3/5 (matches the design's estimate). Dependencies: [320]
(complete). Interfaces: [322] — `AgreementReport` (with `below_floor` +
`ExclusionSummary`) is ready to consume. Next: PM review/merge, then 322
(Calibration-to-Threshold Feedback).

---

### Slice Design 322: Calibration-to-Threshold Feedback — Phase 4 Complete

**Phase 4 complete.** Created `user/slices/322-slice.calibration-to-threshold-feedback.md`; materialized `(322)` in the 320 slice plan and marked its entry as designed. Terminal slice of the human-oracle chain (320 → 321 → 322), so `interfaces: []` — 323/324 are the audit oracle and share the 320 *spine*, not this path.

**Three plan-level open questions resolved, all against the actual code rather than the prose:**

1. **Version identity → the content-hash-at-capture fallback ships.** 320's `derive_judge_config_id` already computes `template_content_hash` and 321 already enforces non-blending on it, so no 300 write-path change is taken. The initiative's own *read-side over 300's write path* principle points here. 320-plan Future Work #1 (the 300 version field) and 321 Future Work #2 (judge-verdict persistence, which would ride with it) both stay **open**.

2. **The comparability hash must exclude the `judge:` block — a correctness fix, not a preference.** `identity.py:298` currently hashes `{name, description, system_prompt, model, prompt_template, **judge**}`, and `judge` *is* `pass_floor`/`concerns_floor`. So acting on a graduation recommendation changes the hash → new `JudgeConfigId` → accumulated n resets to 0 → the cell drops below the floor → no further recommendation possible. **The calibration loop would destroy its own evidence every time it worked.** The plan flagged template *editing* as the churn risk; the loop's own success is in fact the dominant source. Fix: narrow the hash to the judged behavior, excluding thresholds — thresholds are the calibration's *output*, not part of the instrument. A judge that scores identically but bands differently is the same instrument with a different readout. Rejected the plan's third framing (a similarity/inherit policy) as more machinery than the actual failure needs. Costs a one-time re-key of historical records, accepted deliberately and documented.

3. **Residual sampling → policy + offer-selection core, CLI-drained.** `capture.py`'s `sample_budget` is a ceiling on *writes*, not offers, and 320 explicitly deferred offer/selection — so the architecture's "continued forced random sampling" commitment needed a selection surface, which 322 adds. Offers are pull-based and non-blocking (nothing in a pipeline/gate/dispatch waits); "forced rate" means offers are *generated* at that rate. Doc-only was rejected: the architecture demands this be *asserted by a test* ("a graduated judge still produces sampled data"), which a documented policy cannot satisfy.

**Other decisions of substance:**
- **Direction bands are asymmetric.** Loosening is floor-gated; **tightening is not** — requiring a large sample before *warning* about a judge that disagrees with the human would suppress the signal most worth having early. Honest reading of the architecture's "refuses to recommend *loosening* below a floor."
- **Recommendations are directions + evidence, never a computed `pass_floor`.** Deriving a specific numeric threshold would imply precision small-n data cannot support and would edge toward the forbidden self-tuning loop. Output shows *currently configured* thresholds (read via `resolve_thresholds`) so the operator sees the delta and picks the magnitude.
- **The (template,model) ↔ (template,step) mismatch is per-recommendation output**, not a footnote — every recommendation carries the note, including the runtime-drawn-model (180 pool) case where the threshold cannot track the drawn model. Making it output is what stops it being ignored at the moment of action.

**Verified against code, not assumed:** two threshold surfaces exist and neither has a model dimension (`judge.py:41-57` merges step override → template default → module constant `75.0`/`50.0`; template blocks live in the judge YAMLs at `pass_floor: 78`/`82`). `GraduatedConfig` persists behind 320's reserved `record_type` discriminator — no store migration.

**Pending.** Frontmatter `status: not-started`. Next: Phase 5 (task breakdown) for 322. Effort 3/5.

### 322 Slice Review — Addressed (F002 valid, F003 declined)

Slice review (`322-review.slice...`, kimi-k2.7-code): 1 PASS, 1 CONCERN, 1 NOTE.

- **F002 (CONCERN, `GraduatedConfig` omits judge-configuration identity) — correct, and the same bug class as the hash-scope issue: an identity missing its version key.** I keyed graduation on `(template_name, model, artifact_level)`, which is **invariant across a prompt edit** — so a graduation earned under one prompt would silently transfer to a rewritten judge, and `select_residual_offers` would keep drawing spot-checks against it. Version-blending at the one point in the initiative where a *trust* decision is recorded rather than a measurement, with residual sampling then verifying an instrument nobody calibrated. Fixed: `GraduatedConfig` carries the full `JudgeConfigId`; offers match that exact identity; added the *Graduation is version-scoped* decision, a lapsed-graduation failure-mode row (empty offers **with** an explanatory line — an operator who edits a prompt learns the graduation lapsed rather than discovering sampling quietly stopped), a success criterion, walkthrough step 7, and test coverage.

  Worth recording how this composes with the hash narrowing: because the hash **excludes** the threshold block, graduation survives the operator acting on it; because it **includes** prompt and model, graduation expires on genuine drift. The two decisions are what make each other safe — either alone is wrong.

- **F003 (NOTE, low-level I/O failure modes) — declined with rationale.** Asked for rows on store lock contention and read timeouts. Checked the code: these paths are local-filesystem with no lock and no timeout-bearing transport; `store.py:177` already skips unreadable siblings on `(OSError, ValueError, SchemaVersionError)` with a WARNING and reports over what loaded, and writes are atomic write-then-rename. Adding rows for mechanisms that don't exist would document fiction. Recorded the actual inherited behavior instead, and noted that an off-filesystem store (280 convergence) would bring its own transport failure modes and its own rows.

### cf config hygiene

`custom.recentEvents` (rendered as "Current Project State" in `/cf:build` output) still pointed at the orchestration-v2 initiative (`100-arch`/`100-slices`) while the authoritative `Architecture:`/`Slice Plan:` fields correctly read 320. Updated to the 320 artifacts so the loaded context stops contradicting itself.

### Slice 322: Calibration-to-Threshold Feedback — Phase 5 Task Breakdown Complete

Created `user/tasks/322-tasks.calibration-to-threshold-feedback.md` — 17 tasks, test-with pattern throughout, following the design's suggested implementation order.

**Sequencing follows the design's own reasoning, not just its task list:** the `identity._template_content_hash` narrowing (T1/T2) comes first because everything downstream — the recommendation core, the graduated-config registry — accumulates evidence under the corrected key; doing it later would mean re-deriving fixtures once the hash changed underneath them. Config keys (`metrology.graduate_match_rate`, `metrology.tighten_match_rate`, `metrology.residual_sample_rate`) land (T5/T6) before the calibration-core tasks that read them (T7-T10), same lesson 321 already applied (its F004) to avoid a task hard-coding a temporary default.

**Direction classification (T7/T8) calls out a precedence subtlety explicitly:** the floor gates *loosening* only. A below-floor cell with a low match rate must still resolve to `TIGHTEN`, not fall through to `INSUFFICIENT_EVIDENCE` — implementing the bands as a naive top-to-bottom if-chain gated uniformly by the floor would silently swallow the "flag a bad judge early" case the design calls out as the asymmetry's whole point. Wrote the task to spell out the precedence order and require a test for exactly this boundary (below-floor + low-match-rate → `TIGHTEN`).

**Graduation registry (T11-T14) carries the slice-review's F002 fix as a first-class regression test, not an afterthought:** T12 requires two `JudgeConfigId`s sharing `template_name`+`model` but differing `template_content_hash` to *not* cross-match in `find_graduation` — the version-blending bug the review caught, now pinned by a test before implementation is written against it.

**One task (T13, offer selection) carries a deliberate escape hatch:** selecting unsampled judge results matching a graduated config's exact identity may need a result-discovery surface 320 doesn't currently expose (list_samples finds *captured* samples, not all persisted judge results). The task instructs against inventing a new file-walk and to flag the gap to the Project Manager if 320's surface doesn't already support it, rather than guessing at an implementation.

**Not re-litigated:** all three plan-level open questions the design resolved (content-hash version identity, the hash-scope correctness fix, residual-sampling-as-policy) are carried into the task file's context summary as settled facts, per the task-breakdown guide's "don't re-guess at task time" instruction — none reopened here.

Task file is 288 lines, well within the ~450-line guideline. Frontmatter `status: not_started`; slice design frontmatter remains `status: not-started` (Phase 6 implementation not yet started). Coverage-checked against the design's Failure Modes table and Success Criteria — all rows traced to a task.

### 322 Task Review — Addressed (F001 fixed, F002/F003 fixed)

Task review (`322-review.tasks...`, kimi-k2.7-code): 1 PASS, 1 CONCERN, 2 NOTEs.

- **F001 (CONCERN, T7 precedence contradicts its own "tightening is not floor-gated" claim) — correct, and a real bug in the task, not just prose.** T7's original numbered precedence checked `n < floor` first, unconditionally, then claimed a few lines later that `TIGHTEN` was "reachable even if `n < floor`." A literal top-to-bottom if-elif of that ordering makes `TIGHTEN` unreachable below the floor — the numbering itself contradicted the design's Direction Bands table it was supposed to encode. Fixed: reordered so unversioned is checked first, then `TIGHTEN` (before the floor applies), then the floor gates only what's left (`GRADUATE`/`HOLD`). The floor now only ever blocks loosening, matching the design exactly.
- **F002 (NOTE, T8 claimed a malformed-judge-block test that wasn't actually listed) — correct.** The Coverage Check asserted this was "exercised in T8" but T8's bullets only covered registered-vs-unregistered templates. Added an explicit T8 bullet: a template with a non-numeric `pass_floor` must not fabricate a threshold, delegating to `resolve_thresholds`' inherited WARNING instead.
- **F003 (NOTE, T13's residual-offer selection leaned on an unverified 320 surface) — correct, and worth resolving rather than deferring further.** Checked `capture.py` directly: `resolve_target` only resolves *one* target given an already-known slice index (`reviews_dir.glob(f"{index}-review.*")`) — there is no whole-project "list every judge review file" surface for residual sampling to diff against. Rather than leave this as a runtime judgment call for whoever implements T13 (my original escape-hatch phrasing), split out a new **T13 (judge-result discovery surface) + T13b (its tests)** ahead of the renumbered offer-selection task (T14), so the gap is resolved at task-breakdown time. Renumbered T13-T17 to T14-T18 throughout, including all cross-references and the Coverage Check.

---

## 20260723

### Slice 321 task breakdown (Phase 5)

Converted the PASS-reviewed 321 slice design into a sequential, test-with task
list: `project-documents/user/tasks/321-tasks.agreement-dispersion-reporting.md`,
`status: not_started`, 17 tasks (T1–T17), 249 lines.

Structure mirrors the 320 task file: front matter + context summary, granular
T-tasks with L1/L2 checkboxes, a per-task success line and commit message, and
a design→tasks coverage check. Test tasks are paired immediately after each
implementation task (levels T1→T2, models T3→T4, enrichment T5→T6, agreement
T7→T8, dispersion T9→T10, trend T11→T12, config T13→T14, CLI T15→T16), with a
final full-suite/read-only-regression gate (T17).

The two load-bearing LLD facts are carried into the tasks so a junior AI can't
re-guess them: `artifact_level` derived **at report time** from `reviewType`
(T1) since 320 leaves it always-None; the judge verdict joined by
**re-reading + content-hash-verifying** the referenced review file (T5/T6),
excluding stale results. The slice-review F001 fix is pinned as an explicit
regression assertion (T10): two configs' review files for one artifact must
share **one** dispersion cell — proving dispersion keys on artifact identity
`(project_id, source_document, artifact_level)`, not per-config `result_ref`.
The no-`fan_out`-import constraint and read-only invariance are both asserted.

**Tasks review: CONCERNS → addressed.** Review (kimi-k2.7-code) returned
CONCERNS: 3 PASS, 3 concerns, 2 notes. Fixed all five actionable findings —
F004 (config-key task T13 was sequenced *after* T7/T11 which read its keys →
moved config keys to T5/T6, before any report computation, renumbering the
rest); F005 (added a malformed/unparseable-frontmatter enrichment test to T8);
F006 (added explicit empty-store honest-render tests across agreement/
dispersion/trend, T10/T12/T14 + CLI T16); F007 (added a corrupt-sibling
store-read regression on the report path, T16); F008 (a slice-design
inconsistency, not a task gap — the design prose claimed report commands take
`--judge-config`; reconciled the design text to the actual API contract where
`--judge-config` is a `list`-command filter, and fixed a stale `result_ref`
dispersion-grouping sentence left over from the earlier F001 fix). Task file
still 17 tasks, within length budget.

Next: PM approval, then Phase 6 implementation on branch
`321-slice.agreement-dispersion-reporting`.

---

## 20260722

### Slice 321 designed: agreement & dispersion reporting (Phase 4)

Low-level design for slice 321 (Agreement & Dispersion Reporting) — the human
oracle's headline analysis over the sample 320 accumulates. Written to
`project-documents/user/slices/321-slice.agreement-dispersion-reporting.md`,
`status: not_started`, awaiting PM approval.

**What the slice designs:** a pure read-and-aggregate layer over 320's
`MetrologyStore` — agreement (judge-vs-human), dispersion (judge-vs-judge),
and trend, always at the per-artifact-level / per-judge-configuration grain,
every figure carrying its n. No new store engine, no capture change, no
judging-path change. New surface-agnostic core (`levels.py`, `report.py`,
`report_models.py`) plus `sq metrology report agreement|dispersion|trend`
thin shells; report models are the typed interface 322 consumes.

**Two load-bearing facts verified against the code (not assumed) shaped it:**
- **300 multi-sample judging (FW#1) has NOT shipped** — one `ReviewResult`
  per review file, no repeated same-config judgments exist. So 321 ships
  **cross-configuration** dispersion (distinct model/template on one artifact,
  which the store already holds) and builds/tests the **same-config** path but
  leaves it **inert until 300 FW#1 lands** — no 300 dependency, no 180
  `fan_out` dependency introduced. Recorded as an explicit cross-slice
  coordination point in the slice design and mirrored into the 320 slice-plan
  Future Work list (new item 4), per PM request to track when/where it goes.
- **`SampleVerdict.artifact_level` is a reserved, always-`None` hook** with no
  vocabulary defined. 321 defines an `ArtifactLevel` enum and derives it **at
  report time** from each sample's `reviewType` — backfilling historical
  `None` records with **no store migration**; unmappable types land in an
  explicit `UNCLASSIFIED` bucket.

**Key design decisions:**
- **Store backend: flat-file retained.** 321 is the 320-inherited SQLite-vs-
  flat-file revisit point, but the workload (in-memory group-by over a small
  cross-project sample) does not strain glob-and-filter — keep flat-file, with
  a recorded trip-wire condition for adopting stdlib `sqlite3` later.
- **Agreement metric: naive percent + exposed n**, not a chance-corrected
  coefficient that misbehaves at small n (honest-statistics-at-small-n).
- **Content-verified judge-side join:** agreement re-reads the referenced
  review file and verifies `result_ref.content_hash`; a changed/missing file
  excludes the sample as `stale-judge-result` (counted, never joined to a
  stale verdict). This is the load-bearing correctness point.
- **Comparability enforced:** group on `JudgeConfigId`; unversioned records
  (`template_content_hash` None) are flagged/segregated, never pooled.

**Slice review: FAIL → PASS.** First slice-design review (kimi-k2.7-code)
returned FAIL on F001: dispersion grouped by `result_ref` (a review-file
instance whose path + content hash both vary per judge config), so two
configs on one artifact could never share a dispersion group — making the
cross-config dispersion the slice claims to ship impossible. Fixed by keying
dispersion on **artifact identity** `(project_id, source_document,
artifact_level)` via the review's `sourceDocument` frontmatter (agreement
keeps `result_ref`, correct for its own join). Also narrowed frontmatter
`interfaces` to `[322]` (F002 note) — 323/324 relate via the shared 320
spine, not 321's report path. Re-review returned **PASS** (8/8 findings PASS).

Relative effort 3/5. Dependencies: [320] (complete). Next: PM approval, then
Phase 5 task breakdown for 321.

---

### Slice 320 keystone implemented: metrology data layer & blind sample capture

Implemented the keystone of initiative 320 (Judge Calibration & Quality
Metrology) — the durable, user-level metrology store plus the blind,
non-blocking human-sample capture command. All 16 tasks (T1–T16) landed on
branch `320-slice.metrology-data-layer-sample-capture-keystone`, each with its
own commit; full suite green (**2261 passed, 2 skipped**, 46 new metrology
tests), pyright and ruff clean repo-wide, verification walkthrough executed.

**What shipped:**
- New surface-agnostic `squadron.metrology` package: `errors.py` (three typed
  exceptions under `MetrologyError`), `identity.py` (stable project identity +
  content-addressed judge-result reference + judge-config id), `models.py`
  (Pydantic records + `record_type` envelope), `store.py` (`MetrologyStore`
  modeled on `StateManager` — atomic write, schema version, glob-and-filter,
  no DB), `capture.py` (blind capture core).
- Thin Typer shell `cli/commands/metrology.py`: `sq metrology sample` /
  `sq metrology list`, registered in `app.py` (the `config.py` parity pattern).
- Three config keys: `metrology.store_dir`, `metrology.sample_budget`,
  `metrology.project_id`.

**Design decisions confirmed in code:**
- **Stable project identity** is git-remote-URL-derived (normalized: strip
  credentials/scheme/`.git`, collapse scp-vs-https), `.squadron.toml`
  `metrology.project_id` fallback, explicit `MetrologyIdentityError` if neither
  — never a filesystem path.
- **Content-addressed result ref** `(project_id, relative_review_path,
  content_hash)`: SHA-256 over a canonical projection of the persisted review's
  judge frontmatter. The canonical projection **excludes the positional finding
  id** (F001…) and sorts findings by content, so the same finding set hashes
  identically regardless of serialized order — a correction made when the
  order-independence test exposed that positional ids flip on reorder.
- **Blindness is a data-layer property**: `CapturePayload` structurally holds
  only `review_file`, `artifact_path`, `ground_truth_text` — there is no field
  that could carry judge output. Asserted on the object, not by UI convention.
- **Budget** is enforced as a per-project ceiling on *captures written*
  (offering policy is 321); at/over the ceiling `record_sample` refuses cleanly
  and returns a budget-reached outcome (exit 0, not an error).

**Bugs caught during implementation:**
- The metrology commands must anchor the reviews dir at the **process working
  directory** (`--cwd`, default `.`), *not* the `cwd` config key (which points
  inside `project-documents/user` for the review models' content lookups).
  First CLI smoke produced a doubled path; corrected.
- Review type is resolved from each candidate's `reviewType` **frontmatter**,
  not by splitting the filename — a dotted type (`judge.slice-vs-arch`) is
  unparseable by segment. Caught by the ambiguous-index test.

**Discipline:** the 300 judging path is unmodified; a judge run with no
metrology store present behaves exactly as before. `record_type` discriminator
reserves the `audit_finding` path for 323 with no migration.

**Next:** PM review / merge to `main`; then slice 321 (Agreement & Dispersion
Reporting), the first aggregation workload and the store-backend (SQLite)
revisit point.

---

## 20260718

### 320 Keystone Task Review — Addressed (F001 budget, F008 traceability)

Task review (`320-review.tasks...`, kimi-k2.7-code) returned 6 PASS, 1 CONCERN, 1 NOTE — both actionable, both fixed:
- **F001 (CONCERN, sample budget registered but never enforced/tested):** correct gap — I added `metrology.sample_budget` to config but no task read it. Added budget enforcement to T10's `record_sample` (count prior captures for the `project_id` via `list_samples`; at/over budget → refuse the write, no error, a normal "ceiling reached" outcome), T11 asserts the (N+1)th write refuses per-project, T14 reports budget-exhausted and exits 0, T15 asserts it. **Scope correction made explicit in the task:** this slice enforces a ceiling on *captures written*, not on *offering* — the offer/selection policy is deferred to 321, so there is no offer queue here to gate; the write-ceiling is the enforceable slice of the design's "respects the configured budget" criterion.
- **F008 (NOTE, failure-mode traceability):** Coverage Check mapped all Failure Modes rows to T15, but git-remote-absent is asserted in T3 and malformed-target in T5. Corrected the cross-reference to show T3 + T5 + T15 jointly cover the table.

Task file now 252 lines (within 450). Verdict was CONCERNS; both items resolved in-place.

### Task Breakdown 320: Metrology Keystone — Phase 5 Complete

**Phase 5 complete.** Created `user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md` (247 lines, within the 450 target — no split). 16 tasks (T1–T16), sequentially ordered following the LLD's Development Approach (identity → models/store → capture → CLI/config → e2e), test-with pairing throughout (each impl task immediately followed by its test task), per-task semantic commit lines.

**Ordering rationale:** identity first (T2–T5) because it's the hardest new territory and everything keys on it — the content-addressed result ref and project-id derivation are the two things squadron lacks today. Store (T8/T9) modeled on `StateManager` with the cross-project-query test called out explicitly. Blindness (T10/T11) has its own load-bearing test asserting the capture payload excludes judge output (data-layer enforcement, not UI). All Failure Modes table rows collapse into T15's CLI failure-mode coverage (one assertion per row). T16 is the judging-path regression gate + walkthrough smoke + slice-completion marking.

**Coverage check appended** mapping every design element to tasks and confirming the correct absences (321 reporting, 322 version-keying resolution, 323 audit records, MCP tool, 300 write-path change — all deferred by design, none in this task file).

**Pending.** Frontmatter `status: not_started`. Next: PM approval, then Phase 6 (implementation) on branch `320-slice.metrology-data-layer-sample-capture-keystone` (integration branch unset → forks from and merges to `main`).

### 320 Keystone Slice Review — Addressed (F001, F005)

Slice review (`320-review.slice...`, kimi-k2.7-code) returned 3 PASS on the load-bearing dimensions (scope deferral, architectural commitments, version-keying deferral), 1 CONCERN, 1 NOTE — both actionable, both fixed in the design:
- **F001 (CONCERN, failure-mode enumeration):** design stated "typed errors/actionable messages" without enumerating modes — a direct hit on the project's Failure-Mode Enumeration rule. Added a **Failure Modes** table under Implementation Details covering all new I/O boundaries (git-remote subprocess w/ timeout, project-identity absence, review-file missing/malformed, target zero/multi-match, atomic store-write failure, non-TTY/SIGINT/invalid-input capture), each with an explicit handling decision, an observable signal (typed error at ERROR / clean skip at INFO / no partial record — never silent), and a required test. Introduced three typed exceptions (`MetrologyIdentityError`, `MetrologyTargetError`, `MetrologyStoreError`) so "bad input" is distinguishable from "store broken." Absent git remote is deliberately *not* an error (normal case, defined fallback) but still surfaces loudly if the fallback also yields nothing.
- **F005 (NOTE, CLI consistency):** walkthrough used `--type` but API Contracts didn't document it. Documented the full `sq metrology sample <target> [--type] [--verdict] [--note] [--skip]` signature and clarified target forms (path alone, or bare index + `--type`, required when the index is ambiguous). Walkthrough now consistent.

Added a Technical Requirement that every Failure Modes row has a test asserting its observable signal.

### Slice Design 320: Metrology Data Layer & Sample Capture (keystone) — Phase 4 Complete

**Phase 4 complete for the keystone.** Created `user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md`. Index already materialized as `(320)` in the slice plan (first slice shares the initiative base). Designed against the actual codebase, not assumptions — mapped 300's persistence and squadron infra first.

**Load-bearing reality that shaped the design:** 300 review results are **id-less flat files** (`review/persistence.py` writes `project-documents/user/reviews/{index}-review.{type}.{slice}.{ext}`, overwritten on re-run — no run-id, no DB, no query surface over scores). So the keystone must *introduce* two things that don't exist in squadron today:
- **Stable project identity** — git-remote-URL-derived (normalized), fallback to a recorded `.squadron.toml` `metrology.project_id`; **fails explicitly** if neither exists (never a path fallback, per arch + no-silent-fallback rule). No project identity exists in the codebase today (confirmed).
- **Stable judge-result reference** — content-addressed `(project_id, relative_review_path, content_hash)` over the canonical judge fields, because there is no id to key against and re-runs overwrite the file.

**Store follows the `StateManager` precedent exactly** (`pipeline/state.py`): user-level `~/.config/squadron/metrology/`, Pydantic records at the file boundary, `_SCHEMA_VERSION` + `SchemaVersionError`, atomic write-then-rename, one JSON file per record, glob-and-filter query surface. **No new DB dependency** — matches established squadron convention (config TOML, JSON run state). A `record_type` envelope discriminator (`"sample"` now, `"audit_finding"` reserved) lets 323 add audit records without migration.

**Blindness enforced at the data layer, not the UI:** the capture core builds the presented payload from artifact + ground truth only and never places judge output in it — assertable by a test on the payload, not a fragile render-order convention. Human-load constraints from the prior session's arch amendment are carried through as success criteria (blindness scoped to designated samples; non-blocking; skip records nothing; budget respected as an offered-sample ceiling).

**Parity by shared core:** new `squadron.metrology` package (identity/models/store/capture) is surface-agnostic; `cli/commands/metrology.py` is a thin Typer sub-app delegating to it (the `config.py` pattern). No MCP tool ships (MCP surface is still a stub) — parity is structural, guaranteed when the MCP slice later wraps the same core.

**Command surface:** `sq metrology sample <target>` (blind capture) + `sq metrology list` (inspection aid, not the 321 reporting surface). Config keys added to `CONFIG_KEYS`: `metrology.store_dir`, `metrology.sample_budget`, `metrology.project_id`.

**Deferrals honored:** no agreement/dispersion math (321), no version-keying *resolution* or minimum-evidence floor (322) — this slice records both a template-content hash and the judge-config identity as candidate keys but decides neither; no audit records (323); no judging-path change.

**Pending.** Frontmatter `status: not_started`. Next: Phase 5 (task breakdown) for 320, or design the remaining slices (321–324). Effort 4/5.

### 320 Human-Load Constraints: Blind-Capture Scoping & Sampling Budget

**Concern raised by PM:** the blind-capture design read as "operator must always evaluate before judge output is visible" — an efficiency regression, and incompatible with the Amoeba direction (Amoeba takes over much running of squadron; human only at critical points; concept-stage, but 320's calibrated judges are its prerequisite — uncalibrated judges would make Amoeba's decisions unacceptably unpredictable).

**Evaluation outcome:** architecture direction confirmed correct (calibration is the *exit* from the resident-human loop, not more of it), but the docs left one door open: "which results are offered for sampling" was fully deferred to slice design, and escalation-triggered offering — the tempting cheapest-n choice — would blind every escalated review, strip the judge's assistive value, and bias the sample. Closed that door plus two adjacent ones. Amended 320-arch and 320-slices:

- **Blindness scoped:** attaches only to designated calibration samples, never the escalated-gate review flow. Reviewer-at-gate and calibration-sampler are distinct roles; an escalated verdict (formed after seeing judge output) is anchored and inadmissible as blind agreement data. Escalation may *enqueue* a sample; it is never itself blinded.
- **New arch principle — sampling is pull-based, budgeted, never blocking:** samples queue for the operator to drain at convenience; no pipeline/gate/dispatch waits on a sample verdict; skip is free; human load is a configured budget (rate/ceiling), not emergent from pipeline volume. Slow evidence → slower graduation + honest floor refusal, never more interruptions.
- **Division of labor named:** dispersion + trend (321) and the audit oracle are the human-free *continuous* monitors maintaining graduated judges' standing between samples; rising dispersion flags where the scarce human budget is spent.
- **Template-churn caveat:** version-keying means frequent template edits can perpetually reset n and starve graduation; minor-revision inheritance vs. full re-calibration flagged as a 322 slice-design question.
- Slice 320 gains matching success criteria (blindness scoping, non-blocking capture, budget respected); open questions gain budget representation and churn items.

### Slice Plan 320: Judge Calibration & Quality Metrology — Phase 3 Complete

**Phase 3 complete.** Created `user/architecture/320-slices.judge-calibration-quality-metrology.md` from the reviewed 320-arch. `cf` Slice Plan field already registered as `320-slices.judge-calibration-quality-metrology`.

**Structure: five slices, keystone-first, two oracles on one spine.** Kept the architecture's anticipated-slice count and boundaries — the load-bearing decisions were already resolved in arch, so no slice reopens them.
- **(320) Metrology Data Layer & Sample Capture (keystone, High, 4/5)** — the queryable/joinable user-level store keyed on stable explicit project identity (not a path, no 280 dependency) plus the blind inline human-sample capture surface (judge output withheld until the human commits). Done alone, no reporting, per the architecture.
- **(321) Agreement & Dispersion Reporting (Medium, 3/5)** — human-oracle headline: judge-vs-human agreement + judge-vs-judge dispersion, per artifact level / judge configuration, every figure carrying its n; dispersion sourced from 300's multi-sample (no 180 `fan_out` dependency); refuses to pool across incompatible judge configs.
- **(322) Calibration-to-Threshold Feedback (Medium, 3/5)** — evidence-floored path to 300's threshold config; graduation-is-not-a-one-way-door forced residual sampling; the (template,model)↔(template,step) mismatch inherited as a config-time model+threshold pairing; resolves the version-keying tension (coordinated 300 write-path field vs. content-hash fallback).
- **(323) Tech-Debt-Audit Baseline Harness (Medium, 3/5)** — cross-project audit baseline, normalized findings, and the audit's own run-to-run noise floor measured first (variance-before-baseline).
- **(324) Pre-Emption Prompt & Delta Measurement (Medium, 3/5)** — dispatch-side generated static prompt fragment flowing down-only into dispatch config (dispatch never queries the store at runtime); before/after delta reported against the noise floor as a directional signal, not causal proof; ships only after 323.

**Two ordering constraints honored explicitly.** *Variance, then baseline, then intervention* forces the audit oracle into two slices (323 measures the floor, 324 intervenes after). The keystone is done alone — reporting is a separate slice so storage/join/ergonomics de-risk in isolation. The version-keying tension is resolved in 322 (where the calibration recommendation depends on it), not the keystone; 321 already enforces non-blending on whatever key is present.

**Future Work seeded:** 300 judge-result version/hash field (if 322 takes the preferred path), 280-store convergence (not a dependency), general 180 `fan_out` for dispersion (boundary made explicit, not assumed).

**Pending.** Phase 4 (slice design) not started. Frontmatter `status: not_started`.

### Housekeeping: reconcile `tech-debt-analyze` → `tech-debt-audit` skill-name drift

Surfaced by 320 arch review F011. The shipped analysis-pack skill is `tech-debt-audit` everywhere load-bearing (frontmatter `name:`, file `commands/analysis/tech-debt-audit.md`, live dispatch `/analysis:tech-debt-audit`), but the 340-band planning docs called it `tech-debt-analyze` — a name that never matched what shipped. Blast radius was documentation-only (zero occurrences in `src/` or `commands/`). Fixed all live docs to the canonical name: `340-arch` (4 spots, was also self-inconsistent with its own line 81), `340-slices` (3 spots), `001-initiative-plan` (2 spots in the 340 entry), `340-slice.command-surface-spike` (1 spot, the spike's stub-dispatcher example — skill name only; left the illustrative `tech-debt` dispatch token as prototyped). Historical review artifacts (342/320 reviews) left as-is — they are point-in-time records. Trimmed 320-arch's Related Work note now that 340-arch is correct. No code change.

### Architecture 320: Judge Calibration & Quality Metrology — Design Complete

**Phase 2 complete.** Created `user/architecture/320-arch.judge-calibration-quality-metrology.md` from the initiative-plan entry 10 charter; `cf` arch field already registered as 320. Commit: `39b5f9d` (docs: add 320-arch judge calibration and quality metrology).

**What the component is.** The measurement layer 300 explicitly deferred: judge-vs-human agreement and judge-vs-judge dispersion measured against a **sampled human oracle** (no curated dataset), computed **per artifact level**, feeding 300's escalate-vs-auto-gate threshold config. Second oracle with the same metrology shape: a cross-project **tech-debt-audit code-quality baseline** (skill shipped in 340's analysis pack), with the dispatch-side pre-emption prompt as its first measurable customer.

**Key design decisions recorded in the doc:**
- Principles: human sampled-not-resident (capture ergonomics are first-class), read-side over 300's write path (no judging-path changes), per-artifact-level calibration only (no blended global accuracy number), baseline-before-intervention ordering, honest small-n statistics (every report carries its sample size; minimum-evidence floor before recommending threshold loosening).
- Metrology records are keyed by judge configuration (template identity/version, model) so template/model changes don't silently blend incompatible measurements.
- Cross-project aggregation is a new persistence requirement (300's persistence is per-run/per-project); relation to the not-started 280 shared artifact store flagged as a leading slice-design decision, not assumed.
- Non-goals: no curated dataset, no changes to the judging path, no automatic threshold mutation (calibration informs, operator decides), no general observability platform.
- Anticipated slices (exploratory): metrology data layer & sample capture (keystone), agreement/dispersion reporting, calibration-to-threshold feedback, tech-debt-audit baseline harness, pre-emption prompt & delta measurement.

**Pending.** Phase 3 (slice planning, `320-slices.*`) not started. Frontmatter `status: not_started` matches initiative-plan entry status.

**Arch review response (same day).** Review `320-review.arch.judge-calibration-quality-metrology.md` (claude-fable-5, verdict CONCERNS) returned 8 concerns + 3 notes; all 11 addressed in the arch doc. Every factual claim verified against source first. Substantive additions: two new principles — *Graduation is not a one-way door* (forced residual sampling of auto-gated results survives graduation, F002) and *Blind capture, not anchored* (judge output withheld until the human commits an independent verdict, F003); principle *Baseline before intervention* rewritten to *Variance, then baseline, then intervention* (measure the audit's run-to-run noise floor before any delta, F008); new consideration committing pre-emption data to flow **down** as a generated static prompt fragment — dispatch never queries the metrology store at runtime (F007, avoids a 140→320 dependency inversion); the metrology-store consideration now fixes three load-bearing commitments — stable explicit project identity, user-level/central locality, no hard 280 dependency (F006); the template-version consideration now names the read-side/no-version-field unsatisfiability and resolves it (coordinated 300 write-path field preferred, capture-time content-hash fallback, F001). Corrections: `fan_out` re-attributed from 140 to 180 and dispersion scoped to 300's multi-sample only, preserving the plan's "Independent of 180" (F004); `340` added to frontmatter `dependencies` (F005). Notes F009 (per-model calibration resolves to operator config-time choice) and F010 (shared "spine" not "one report path") folded in. **F011 verified inverted:** the shipped skill is genuinely `tech-debt-audit` (frontmatter name, file, live `/analysis:tech-debt-audit` dispatch); `tech-debt-analyze` is 340-arch's stale drift — kept the correct name, flagged 340-arch for reconciliation rather than adopting the wrong identifier. Response recorded in the review file. Dependencies `[100, 140, 300, 340]` all complete.

### Slice 304: Gate Composition — Implementation Complete

**Phase 6 complete.** Branch `304-slice.gate-composition` created from `main` (integration branch unset). All 13 tasks (T1–T13, including T2c/T4c/T7b/T8c) implemented, tested, and verified in dependency order across four bisectable commits. Initiative 300 (eval-actions-llm-as-judge-scoring) is now fully closed — slices 300–304 are all complete.

**T1–T2c: pure reduction core.** `src/squadron/pipeline/actions/gate.py` defines the severity ranking once as an `IntEnum` (`PASS < CONCERNS < FAIL < UNKNOWN`, `UNKNOWN` highest/most-severe) and a pure `reduce_verdicts(a, b) -> str` that normalizes `None → "UNKNOWN"` before ranking and returns `max(severity_a, severity_b).name`. `Provenance.COMPOSED` added to the existing `Provenance` `StrEnum` in `actions/judge.py`. 27 tests cover the full 4×4 cross-product (all 16 pairs incl. the 4 diagonal ties) plus all `None`-leg cases.

**T3–T4c: the 140-adjacent executor touch, confirmed pure and signed off.** Added `ActionContext.step_outputs: dict[str, ActionResult]` (`models.py`) — a step-name-keyed view populated in `execute_pipeline`'s top-level loop (`executor.py`), mirroring exactly how `prior_outputs` itself is accumulated, using the existing `_last_with_verdict` helper to pick each step's most recent verdict-bearing result. Required threading the new field through all 5 nested step-execution paths (`_execute_step_once`, `_execute_loop_step`, `_execute_loop_body`, `_execute_each_step`, `_execute_fan_out_step`) and their 9 call sites — more mechanical surface area than the design's grounding notes implied (they named one `ActionContext` construction site; the executor's loop/each/fan_out helpers each pass `prior_outputs` through independently). **140 sign-off obtained from the Project Manager before implementing**, per the STOP-gate: confirmed as a pure additive read view, no change to `prior_outputs` semantics, no checkpoint code touched. Verified: the full pre-existing pipeline suite (999 tests) passed unmodified both before and after the change, and a dedicated regression test (`TestStepOutputsRegression`) pins that the `review-0` key-collision behavior in `prior_outputs` is byte-for-byte unchanged. The sign-off is recorded in the T4c commit body per the task's requirement.

**T5–T8c: `gate` action + step + loader validation.** `GateAction` resolves `judge_from`/`review_from` (step names) against `context.step_outputs`, reduces via `reduce_verdicts`, and returns `provenance=COMPOSED` with both raw verdicts (and scores/criteria, unreduced) on `metadata`. An unresolved source step or a source with `verdict=None` logs WARNING+ and normalizes to `UNKNOWN` — no silent path. `GateStepType` expands to `[gate]` or `[gate, checkpoint]` (mirroring `ReviewStepType`), with its own `validate()` checking only presence/type of its own config, per the `StepType.validate(config)` protocol's own-config-only scope. **F005 (loader cross-step check):** added `_validate_gate_references` in `loader.py`'s `validate_pipeline`, tracking `prior_step_names` across the existing step loop and requiring `judge_from`/`review_from` to each name a step that appears *earlier* — a misspelled or forward-referencing name now fails at load time, distinct from the action's execute-time `UNKNOWN` fallback. 28 additional tests (action + step type + loader validation, incl. nonexistent-step, later-step, and param-placeholder-skip cases).

**T9–T11: example pipeline, end-to-end checkpoint-driving tests, and the escalation boundary.** `compose-gate-example.yaml` composes a `judge.slice-vs-arch` leg and a `slice`-template review leg into one `gate` step with `checkpoint: on-concerns` — validates clean via `sq run compose-gate-example --validate`. `TestDrivesCheckpoint` proves the *reduced* verdict, not either raw leg, fires the checkpoint: (PASS, CONCERNS) fires, (PASS, PASS) doesn't, (UNKNOWN, PASS) fires (no-silent-pass), and — closing the F003 tasks-review gap — a `None`-leg case runs the full normalize→reduce→checkpoint-fires→WARNING-logged path end-to-end, not just at the action level. `test_boundary_requires_140` encodes escalation condition (3) directly: two gate results with identical reduced verdicts (`FAIL`) but opposite raw legs (judge-FAIL-review-PASS vs. judge-PASS-review-FAIL) prove the checkpoint's read path (`_find_review_verdict`, which reads only `.verdict`) cannot distinguish *which* leg failed — that requires extending the checkpoint itself (option b), which this slice does not do.

**T12: authoring guide.** Added "Composing a judge and a review at one gate" to `docs/PIPELINES.md` as a sibling to 303's "Judge-Gated Cycles" section (cross-linked both ways), plus a `### gate` step-type entry (fields table) and Action Type Catalog row. Documents the composition shape, the most-severe-wins rule with `UNKNOWN`-most-severe and `None → UNKNOWN` rationale, the same-step checkpoint requirement, the 140 boundary (with the "which leg failed" example), and the gate-vs-fan-in distinction so authors don't reach for a gate where a fan-in reducer belongs.

**T13: full-suite gate.** `uv run pytest` (2198 passed, 2 pre-existing/unrelated skips), `uv run pyright` (0 errors, strict), `uv run ruff check` (clean) — all green. Verification Walkthrough re-run against actual output and corrected in the slice design: two of the design's draft `-k` filter strings (`drives_checkpoint`, `unknown_dominates`) didn't match the actual test names/classes written in Phase 6 (`TestDrivesCheckpoint`, `test_judge_unknown_review_pass_fires`) — corrected in place with a caveat note, all 7 walkthrough steps now reproducible verbatim.

**Code review (`moonshotai/kimi-k2.7-code`, CONCERNS) addressed.** 2 concerns, 3 passes, 1 note. **F001:** `GateStepType` validated and forwarded a `policy` field that `GateAction.execute` silently ignored — fixed by having the action read `context.params["policy"]`, fall back to the default with a WARNING+ log on an unrecognized value, and record the resolved policy on the result's `metadata` for auditability. The valid-policy set is now centralized once in `actions/gate.py` (`VALID_GATE_POLICIES`/`DEFAULT_GATE_POLICY`, public rather than private so `steps/gate.py` can import it under pyright strict) instead of duplicated across both files. **F002:** the ~720-line `tests/pipeline/test_gate.py` (over the project's ~300-line guideline) was split into four focused files by concern — `test_gate_reduce.py` (pure reduction core), `test_gate_action.py` (GateAction, now including 3 new policy tests), `test_gate_step.py` (GateStepType + loader cross-step validation), `test_gate_executor.py` (step_outputs read surface, end-to-end checkpoint-driving, escalation boundary). **F006** (note, addressed): added an inline comment on `GateAction.execute`'s `success=True` explaining it reports execution health, not verdict outcome, mirroring `CheckpointAction`. F003–F005 were PASS (fail-closed ranking, additive `step_outputs`, load-time cross-step validation) — no change needed. Full suite re-verified green after the split (2201 passed, up from 2198 net of the 3 new tests).

**Housekeeping:** removed a pre-existing stray line of unrelated content (referencing a different slice, "162") that had contaminated the top of `304-slice.gate-composition.md` since its Phase-4 creation commit, ahead of the frontmatter delimiter — confirmed with the PM before removing, out of caution since it predated this session. Slice design and task file frontmatter both updated to `status: complete`, `dateUpdated: 20260717`; slice-plan checkbox (#5, gate composition) in `300-slices.eval-actions-llm-as-judge-scoring.md` checked off, and the plan's own frontmatter status moved `in_progress` → `complete` (confirmed with PM — all 5 core slices done, remaining items are the separate, explicitly-deferred Future Work section). Future Work item 3 (checkpoint multi-verdict support, 140) remains legitimately unscheduled — the escalation boundary never fired, so option (a) shipped as sufficient and (b) stays future work, not superseded. A `workflow_check --fix` pass also corrected unrelated pre-existing drift project-wide (confirmed with PM before keeping): slice 344's checkbox/frontmatter, and architecture status fields for 140, 300, and 900 — none touch slice 304's own scope.

**Initiative 300 status:** all five slices (300 scoring foundation, 301 threshold enforcement, 302 judge templates, 303 judge-gated cycles, 304 gate composition) are complete; the slice plan's frontmatter now reflects `status: complete`. The one deferred coordination — Future Work 3, checkpoint multi-verdict support — remains a 140 dependency to be picked up only if a future required case needs it.

---

## 20260716

### Issue #14: code review pipeline misfiled findings against a prior slice's merged code (3x across 2 slices)

Traced the root cause to `resolve_slice_diff_range()`'s third fallback
path, `_find_commit_range()`
([src/squadron/review/git_utils.py](src/squadron/review/git_utils.py),
now removed). It ran `git log --all --grep=\b{N}\b` — an unscoped
word-boundary search over commit-message *prose*, across all refs —
whenever both the local slice branch and a `--merges` merge commit
could not be found. Path 2 (`_find_merge_commit`) only matches true
two-parent merge commits, so any project using squash-merge (GitHub's
default PR button) never produces one, making path 3 the de facto
primary fallback the moment a slice branch is cleaned up post-merge.

Verified the collision live against squadron's own history:
`--grep='\b124\b'` matched not just slice-124 implementation commits
but unrelated ones like "docs: mark slice 124 as superseded" and a
reindexing commit — some **older** than slice 124's real work. Since
the function took the oldest match as the range start, a stray older
collision silently widened the "diff" to include everything committed
since, including an entirely different slice's already-merged code —
exactly the reported symptom (F001-F006 in the issue's slice-124
occurrence cited files last touched by slice 122, not present in slice
124's actual diff).

Erik confirmed with a real commit-history excerpt that no regex over
commit-message text can safely distinguish real slice-work commits
from incidental mentions (e.g. `fd2469d docs: reconcile 300 initiative
status to in_progress` — a bare number in an unrelated docs commit).
Considered narrowing the grep pattern (e.g. matching the branch-name
convention `{N}-slice` as a message substring) but disproved it against
the same excerpt: commit messages don't echo branch names literally
("slice 301", not "301-slice."), so a narrower pattern would just
trade false positives for false negatives.

Also confirmed with Erik that slice branches are not normally deleted
before review completes in his workflow — so path 1 (`_find_slice_branch`)
should fire in the healthy case. Why the reported slice-124 occurrence
fell through to path 3 despite a branch reportedly existing at review
time could not be confirmed from squadron's own repo — noted as an open
verification item requiring the actual `grizcam_mobile_ios` repo state
at review time, not blocking this fix.

Fix: removed `_find_commit_range()` and path 3 entirely. When no local
branch and no merge commit can be resolved,
`resolve_slice_diff_range()` now raises `DiffRangeUnresolvedError`
(new, in `git_utils.py`) instead of silently guessing or falling back
to bare `--diff main`. Wired at both call sites: the CLI
(`review.py:663`) catches it and reports via the existing
`rprint("[red]Error: ...[/red]")` + `typer.Exit(code=1)` pattern used
throughout that file; the pipeline action
(`pipeline/actions/review.py`) added it to the existing named-exception
tuple in `execute()`'s top-level handler (alongside `KeyError`), so it
surfaces as a proper failed `ActionResult` with a `_logger.warning`
instead of falling through to the generic `except Exception` catch-all.

Updated `tests/review/test_git_utils.py`: removed `TestFindCommitRange`
and `TestResolveSliceDiffRangeWithCommitGrep` (dead code coverage),
replaced the old fallback-to-`"main"` test with one asserting
`DiffRangeUnresolvedError` is raised. Verified live: direct call with
an unresolvable slice number raises with a clear, actionable message.
Full gate: 2133 tests passed (net -9: -14 dead, +1 new, plus 2 tests
folded into fewer assertions), pyright strict 0 errors (project-wide
run — a per-file pyright invocation on the test file alone showed
pre-existing `reportPrivateUsage` noise unrelated to this change,
confirmed present before this fix too), ruff clean. Closes #14.

### Slice 304: Gate Composition — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/304-tasks.gate-composition.md` (312 lines, within target) from the review-addressed design. 13 tasks in dependency order, each impl task followed immediately by its test (test-with pattern): reduction core (T1–T2) → executor read surface (T3–T4) → gate action (T5–T6) → gate step (T7–T8) → example pipeline + drives-checkpoint + boundary tests (T9–T11) → authoring guide (T12) → commit (T13).

**Grounded every code anchor against on-disk source before writing tasks, so the junior AI does not re-derive them.** Verified and carried into the task file's grounding notes: the `Action`/`StepType` protocol method sets (`actions/protocol.py`, `steps/protocol.py` — both confirmed present); `register_action`/`register_step_type` signatures; the `ActionType`/`StepTypeName`/`Provenance` `StrEnum`s that each need a new `GATE`/`COMPOSED` member; and — the load-bearing one — that `StepResult` (`executor.py:244`) carries `step_name` + `action_results` and the executor already accumulates a `step_results` list, but `ActionContext` (`models.py:54`) exposes **only** the lossy action-keyed `prior_outputs`, no step-keyed view. That gap is exactly what T3 fills.

**T3 (the F002-flagged executor touch) is written as a STOP-gated task, not a normal one.** It carries an explicit stop-gate: the step-keyed read surface must be a *pure additive* field on `ActionContext` populated from the already-accumulated `step_results`, changing no `prior_outputs` semantics and touching no checkpoint code, and it needs up-front 140 sign-off because `prior_outputs` is 140-owned. If a pure addition proves impossible, the task says STOP and escalate to option (b) per the design's escalation boundary — the task cannot silently absorb a checkpoint change. This mirrors the F002 resolution: the executor touch is 140-adjacent, not in-scope-by-default.

**F001 (None-verdict) is pinned across three tasks:** `reduce_verdicts` normalizes `None → UNKNOWN` before ranking (T1), the 4×4 cross-product plus all `None` cases are required tests (T2), and the gate action's WARNING+ log on a `None`/unresolved leg is asserted via `caplog` (T6). The escalation-to-140 boundary test (T11) is a first-class required task encoding boundary condition (3) — a policy needing the checkpoint to see both raw verdicts distinctly is asserted *not* expressible via the single reduced gate and documented as a 140 concern.

**Real-path corrections while grounding:** the authoring-guide target is `docs/PIPELINES.md` (slice 152's guide, where 303's `Judge-Gated Cycles` section already lives) — T12 names it and cross-links, rather than pointing at a vague "same doc as 303." Verification section maps each task back to the slice's FR1–FR4 and F001/F002 so the coverage is auditable.

**Task-breakdown review (`moonshotai/kimi-k2.6`, CONCERNS) addressed — 2 PASS (test-with pattern, F002 STOP-gate scoping), 3 concerns resolved.** **F003 (no end-to-end `None`→checkpoint test):** added a `None`-leg case to T10 — normalizes to `UNKNOWN`, reduces to `UNKNOWN`, fires the same-step checkpoint, WARNING+ logged on that path; closes the T6 (action-level) ↔ T10 (checkpoint firing) gap. **F004 (commits batched at end):** distributed commits across the four deliverables — T2c (reduction), T4c (read surface, with mandatory 140-sign-off note in the body), T8c (gate action+step+loader validation), T13 (example+docs+full-suite gate); branch now reads as four bisectable commits. **F005 (gate step omits prior-step existence check):** the fix was right but its locus was not — `StepType.validate(config)` sees only its own config (verified `steps/protocol.py`), so it *cannot* check sibling steps; the cross-reference belongs in the loader's `validate_pipeline` (`loader.py:147`), which iterates all steps and already validates review-template refs the same way (`loader.py:210`). Added T7b (loader validates `judge_from`/`review_from` name real *prior* steps, fail-fast at load) and clarified T7's own `validate` as own-config-only; T8 asserts the load-time failure distinct from T5's execute-time `UNKNOWN` defense-in-depth. Task file 314 → 398 lines (within target). Review dispositioned per-finding; `reviewsAddressed` added to task frontmatter.

**Next:** Phase 6 (implementation) for slice 304 — create branch `304-slice.gate-composition` from the target (integration branch unset → `main`), start T1. Design and tasks are both review-addressed; the one open coordination is the T3 140 sign-off, to be obtained at implementation (T4c holds the commit until it lands).

---

### Slice 304: Gate Composition — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/304-slice.gate-composition.md` from the slice-plan entry (#5) in `300-slices.eval-actions-llm-as-judge-scoring.md`. This is the initiative's integration slice: resolve how a judge result and a standard review result compose into a single checkpoint gate. The architecture prescribed the *decision procedure* (prefer option a, upstream reduction, additive; escalate option b, checkpoint multi-verdict, as a 140 dependency if a is insufficient) but not the answer. The design **commits to option (a)** and proves it sufficient, grounded against the real machinery rather than the architecture's prose.

**The decisive constraint was verified in code, not assumed.** The checkpoint is single-verdict-per-step for a *mechanical* reason: (1) the executor accumulates results as `prior_outputs[f"{action_type}-{idx}"]` with `idx` resetting per step (`executor.py:880-883`), and a `review` step expands to exactly one review action (`steps/review.py:69-76`) — so *every* standalone review step, judge or standard, writes the same key `review-0` and later steps **overwrite** earlier ones in the global map; (2) `_find_review_verdict` returns the *first* non-`None` verdict in reverse insertion order (`checkpoint.py:28-37`). Both a judge result (threshold-derived verdict) and a standard review (model verdict) carry a non-`None` verdict, so the checkpoint picks exactly one — whichever ran last — and structurally cannot combine two separately-stepped results. This is precisely why combining two *separate* steps' verdicts is option (b)/140 territory: it requires the checkpoint to look past a single key. Option (a) sidesteps it by reducing to one verdict *upstream*, in the same step as the checkpoint.

**Design: a `gate` reduce action + `gate` step (both additive registrations).** The gate step names its two source steps (`judge_from` / `review_from`), the gate action reduces their verdicts by a documented **most-severe-wins** rule (`UNKNOWN > FAIL > CONCERNS > PASS`, `UNKNOWN` ranked most severe deliberately to preserve the no-silent-pass NFR — a broken judge leg must dominate a passing review leg), and the gate step expands to `[gate, checkpoint?]` so the reduced verdict and the checkpoint land in the **same step** — the one place a checkpoint can read the gate's output via the unchanged `_find_review_verdict`. New `Provenance.COMPOSED` value; both raw verdicts preserved on the gate result's metadata for auditability. `_find_review_verdict` and the checkpoint are **not modified** — that is the whole point of option (a), and any need to modify them is the escalation signal.

**The escalation boundary (a → b) is a stated, checkable rule, not a mid-Phase-6 judgment call.** Option (a) is declared insufficient and (b) escalated to 140 iff, in implementation: (1) exposing per-step results to the gate action can't be done as a pure additive read surface without altering the checkpoint's single-verdict contract; (2) a required case needs the checkpoint itself (not an upstream action) to weigh two verdicts; or (3) the reduction can't be a pure function of the two verdicts because a policy needs the checkpoint to branch on *which* leg produced the severity. None holding → (a) stands, 140 untouched (the default, shipped outcome). The required **escalation-to-140 boundary test** encodes condition (3): it asserts a policy needing both raw verdicts seen distinctly is *not* expressible via the single reduced gate and is documented as a 140 concern — so the slice recognizes its own edge rather than silently overreaching.

**The one additive executor touch is named as the risk.** The gate needs source results keyed by *step*, which the lossy action-keyed `prior_outputs` does not preserve (both legs clobbered `review-0`). Adding a step-keyed read view is the single place the slice reaches into the executor; if it can't be a pure read-surface addition, the escalation boundary fires. This is the architecture's anticipated edge, handled by the prescribed escalation.

**Verification Walkthrough is a Phase-4 draft** (marked as such) — the 4×4 reduction cross-product, drives-checkpoint, unknown-dominates, boundary-requires-140, and non-composed-unchanged tests are specified; actual commands/output to be confirmed in Phase 6.

**Two refinements after PM review.** (1) **Tie behavior made explicit:** two same-severity legs (e.g. `CONCERNS`+`CONCERNS`) reduce to that shared value — most-severe-wins is idempotent on equal ranks, so there is no tie-break to decide (the reduction returns a *rank*, not a chosen *leg*); the 4×4 cross-product's four diagonal ties are now called out as required test cases, and the stale "scores for tie-context" phrasing was removed (ties need no score context). Raw per-leg verdicts stay on `metadata`, so a same-rank tie remains auditable. (2) **Fan-out/fan-in relationship pinned as a distinct-but-co-evolving concern.** The codebase already has a `FanInReducer` protocol + registry (`intelligence/fan_in/reducers.py`, slice 182; `collect`/`first_pass`, with `merge_findings`/`unanimous` planned in 189). The gate reduces **2 heterogeneous** judgments of one artifact (judge verdict *and* review verdict); fan-in converges **N homogeneous** samples (same review across many models). Orthogonal today — multi-sample judging (300 FW1) is explicitly a *fan-in* job, not a gate one, so the gate grows no sample count. But both are "reduce a set of results to one verdict," and the gate's most-severe rule is arguably a special case of a `FanInReducer`; a comparison table and an evolution note are now in the design flagging a likely future unification (gate-as-reducer) as *unscheduled direction*, so a later slice unifies them knowingly rather than by accident. Not attempted now — no caller, and forcing the gate through the fan-out branch model would add complexity nothing needs (project rule).

**Slice-design review (`z-ai/glm-5.2`, CONCERNS) addressed — both concerns dispositioned in the design.** **F001 (missing `None`-verdict failure mode):** the reduction now normalizes a `None` source verdict to `UNKNOWN` *before* ranking — fail-closed, deliberately diverging from `_find_review_verdict`'s skip-`None` behavior, because a gate must not let a verdict-less source vanish and silently advance the other leg. Added the rule, a failure-mode-table row, a required WARNING+-logged unit test, and prose distinguishing it from the *authoring-time* missing-source-name case (which stays fail-fast validation). **F002 (executor read-surface boundary ambiguity):** re-framed the per-step read-surface touch from "in-scope unless downstream escalation fires" to **140-adjacent, requiring up-front 140 sign-off regardless** (`prior_outputs` is 140-owned) — two explicit outcomes (confirmed pure addition → proceed with sign-off, expected default; can't stay pure → escalate to (b), condition 1), with the slice explicitly disclaiming unilateral authority to modify executor result accumulation under 300's additive banner. F003 was a PASS (architectural alignment), no change. Review file updated with per-finding `resolution:` and a Resolution section; `reviewsAddressed` added to the design frontmatter. Verdict left `CONCERNS` as the historical record; a Phase-6 re-review should confirm the commitments hold in code.

**Slice status:** design is `not-started` (Phase 4 artifact exists, review-addressed; implementation not begun). This slice completes the 300 initiative's gating story once implemented — 300/301/302/303 are all `complete`.

**Next:** Phase 5 (task breakdown) for slice 304, or PM direction. No branch created (planning work commits to the current target per the git rules).

---

## 20260715

### Issue #21: `{keep_section}`/`{summarize_section}` never resolved by `_summary-instructions`

Confirmed the issue's own diagnosis against current source: two independent
render paths existed for compaction templates —
`compaction_templates.render_instructions()`
([src/squadron/pipeline/compaction_templates.py:83-116](src/squadron/pipeline/compaction_templates.py#L83-L116)),
which computes `keep_section`/`summarize_section` from `keep`/`summarize`
args, and `summary_render.resolve_template_instructions()`
([src/squadron/pipeline/summary_render.py:22-41](src/squadron/pipeline/summary_render.py#L22-L41)),
used by the `_summary-instructions` CLI command, which called
`render_with_params()` directly and never computed those two placeholders
at all — they fell through `LenientDict`'s missing-key handling and leaked
into output as literal `{keep_section}` text.

Checked `summary_instructions.py`'s CLI signature: no `--keep`/`--summarize`
flags exist on this entry point, so `keep`/`summarize` can only ever be
their defaults (empty list / `False`) here — ruling out "add CLI flags" as
the fix and confirming the issue's own suggested direction (route through
`render_instructions()`) was correct. Weighed against computing the two
placeholders locally in `summary_render.py`: routing through
`render_instructions()` keeps a single source of truth for which derived
placeholders a compaction template can reference, at the cost of two unused
`keep`/`summarize` parameters at this call site — preferred over
duplicating the placeholder names in two files.

Fix: `resolve_template_instructions()` now calls
`render_instructions(template, pipeline_params=params)` instead of
`render_with_params(template.instructions, params)` directly. Added
`test_keep_section_placeholder_resolved_not_leaked` to
`tests/pipeline/test_summary_render.py`, asserting `minimal-sdk.yaml`'s
`{keep_section}` reference resolves rather than leaking. Verified live via
`sq _summary-instructions minimal-sdk` — no leaked placeholders. Full gate:
2142 tests passed (+1), pyright strict 0 errors, ruff clean. Closes #21.

### Issue #23: SDKExecutionSession.dispatch had the same no-separator/no-filter join as #22

Same root-cause pattern as #22 (fixed earlier today for `review_client.py`
and `summary_oneshot.py`), found in a third location while fixing #22:
`SDKExecutionSession.dispatch()`
([src/squadron/pipeline/sdk_session.py:143-166](src/squadron/pipeline/sdk_session.py#L143-L166))
accumulated every translated SDK message's content — including
`tool_use` ("Using tool: Bash") and `tool_result` (command stdout) —
via bare list-append + `"".join()`, mixing tool-call narration into the
dispatch response with no separator.

Traced the two real consumers before fixing, resolving the issue's own
open question ("is this cosmetic-only?"): `_dispatch_via_session` in
[src/squadron/pipeline/actions/dispatch.py:191-200](src/squadron/pipeline/actions/dispatch.py#L191-L200)
passes the joined string to `_check_cli_error` (prefix check only, low
risk) and stores it as `outputs={"response": response_text}` — which
persists into `prior_outputs`, read by later steps including the F001
fix from earlier today (`_resolve_prompt_from_prior_review` scans
`prior_outputs` for review findings). A corrupted response string here
can therefore leak tool-call noise into what a later dispatch step's
prompt is built from — not cosmetic.

Fix: filter `sdk_type in (SDK_RESULT_TYPE, "tool_use", "tool_result")`
before appending to `response_parts` (session_id capture still runs for
every translated message, unchanged), and join with `"\n"` instead of
`""`. Mirrors the #22 fix exactly. Added
`test_dispatch_excludes_tool_call_noise` to
`tests/pipeline/test_sdk_session.py`, using `AssistantMessage` with
mixed `TextBlock`/`ToolUseBlock` content plus a top-level
`ToolResultBlock` SDK message to match how `translate_sdk_message`
actually produces these types. Full gate clean: 2141 tests passed,
pyright strict 0 errors, ruff clean. Closes #23.

### Issue #24: `sq review code` sent its template rules to the model twice

`review_code()` ([src/squadron/cli/commands/review.py:704-711](src/squadron/cli/commands/review.py#L704-L711))
already fully assembles `rules_content` via `load_review_rules("code",
resolved_rules_dir, file_paths=..., manual_rules_content=manual_content)`
— template rules (`review-code.md`) + language auto-detection + any
explicit `--rules` override, one copy of template rules. It then passed
both that assembled `rules_content` *and* `rules_dir=resolved_rules_dir`
into `_run_review_command`, whose own `if rules_dir is not None` guard
([review.py:322-329](src/squadron/cli/commands/review.py#L322-L329))
unconditionally re-ran `load_review_rules`, prepending `review-code.md`
a second time onto content that already had it. `review_slice`/`arch`/
`tasks` never hit this because they don't pre-assemble — they resolve
only `rules_dir` and let `_run_review_command` do the one and only
`load_review_rules` call for those templates.

Fix: `review_code` now passes `rules_dir=None` to `_run_review_command`,
since its `rules_content` is already complete — the existing guard then
correctly skips the redundant call for this caller only. Added
`test_review_code_template_rules_not_duplicated` to
`tests/review/test_cli_review.py`'s `TestRulesWiring` class, asserting
the template rules string appears exactly once in the `rules_content`
actually passed to `run_review_with_profile`. Full gate clean: 2140
tests passed, pyright strict 0 errors, ruff clean. Closes #24.

### Slice 303 re-review F001: judge-cycle's fix step never saw the judge's findings

Re-verified a finding from an earlier, never-filed comparison-review
artifact (`project-documents/user/analysis/303-review.code.judge-gated-cycle-conventions-sonnet5.md`,
run via `/code-review`) before fixing, per this session's ongoing effort
to eliminate false review findings — confirmed against current source
rather than taken on faith.

`judge-cycle.yaml`'s loop `dispatch` step had a static hardcoded
`prompt:`, and `dispatch.py`'s `_resolve_prompt` only scans
`prior_outputs` for a prompt when no explicit `prompt` param is set —
so that scan never ran, and the fix step repeated the same generic
instruction every iteration regardless of what the judge flagged.
Root cause was actually two-layered: even with the hardcoded prompt
removed, `_resolve_prompt` had no branch at all for a prior `review`
action's output — it only knew how to pull `stdout` from a prior
`cf-op(build_context)` result. Fixed both: removed the YAML's
hardcoded `prompt:` ([judge-cycle.yaml](src/squadron/data/pipelines/judge-cycle.yaml)),
and added `_resolve_prompt_from_prior_review`
([dispatch.py](src/squadron/pipeline/actions/dispatch.py)) — a new
fallback tier that scans `prior_outputs` for the most recent `review`
action, formats its structured findings (severity/summary/location)
into a fix prompt, or falls back to "perform an initial improvement
pass" when the prior review had no findings (e.g. iteration 1, or a
clean PASS). Verified `prior_outputs` does thread across loop
iterations by reference (`executor.py:713-714`, `1013`), so this
actually reaches the fix step on iteration 2+.

Added `TestDispatchPriorReviewFallback` (4 tests) to
`tests/pipeline/test_dispatch.py`: explicit `prompt:` still wins over
a prior review (only steps that omit it fall through), prior-review
findings become the prompt, a findings-less prior review yields the
initial-pass message, and no prompt/build_context/review anywhere
still raises `KeyError`.

### Slice 303 re-review F002: `template.model` fallback invisible to the classification pre-scan

The T7 fix in `ReviewAction._review` (`review.py:120-125`) retries
model resolution against a review template's own `model:` default
when the standard 5-level cascade is empty — but that retry is local
to `_review` and never goes through `ModelResolver.cascade_candidates()`,
which the slice-243 classification pre-scan (`classification.py`)
treats as the single source of truth for what the cascade will
resolve to. A pipeline relying solely on a template's default model
(no CLI/action/step/pipeline/config override) got a false
`ClassificationError` before the pipeline even started, even though
runtime resolution would have succeeded.

Considered making `template.model` a real 6th tier inside
`ModelResolver` itself, but that would require teaching the generic
resolver (shared by dispatch/summary/compact, none of which have
templates) about review templates specifically. Asked Erik, who
confirmed the surgical option: mirror the exact fallback locally in
`classification.py` instead. Added `_review_template_model_fallback()`,
called from both `classify_pipeline`'s top-level action loop and
`_classify_container_inner` (the loop/each/fan_out inner-step path —
the one `judge-cycle.yaml` actually exercises) when the cascade comes
back empty for a `review` action. Loads the template via the same
`get_template()`/`load_all_templates()` used at runtime; confirmed
this doesn't violate the module's documented side-effect-freeness
contract (`test_classification_is_idempotent_and_side_effect_free`
only asserts idempotency and zero `pool.select()` calls, both
preserved by a deterministic template load).

Added 3 tests to `tests/pipeline/test_classification.py`: a top-level
review step with no cascade model falls back to the template's
default, still raises when the template also has no model, and the
loop-container inner-step path specifically (matching
`judge-cycle.yaml`'s actual shape).

### Slice 303 re-review F003: malformed judge threshold silently discarded a completed review

Fixing "judge reviews always persist as UNKNOWN" required moving
judge-verdict computation (`resolve_thresholds`/`enforce_judge`)
before persistence in `ReviewAction._review`, so the derived verdict
could be passed into `verdict_override`. But `resolve_thresholds`
calls unguarded `float()` on `pass_floor`/`concerns_floor` — a
malformed step-level `judge:` override (e.g. a non-numeric
`pass_floor`) now raised *before* persistence's own try/except
(`review.py:230`) was ever reached, discarding a review whose model
call had already succeeded, with no file written at all. Previously
persistence ran first in its own non-fatal try/except, so the
artifact was always saved regardless.

Wrapped the threshold resolution/enforcement in its own narrow
`try/except (TypeError, ValueError)` that logs a WARNING and degrades
to `verdict="UNKNOWN"`/`provenance=judge` — matching the existing
"no score / out-of-range score → UNKNOWN" behavior already inside
`enforce_judge` for a different failure mode. Persistence below still
runs either way.

Added `test_malformed_threshold_override_degrades_to_unknown_and_still_persists`
to `tests/pipeline/actions/test_review_action.py`, asserting
`success=True`, `verdict=UNKNOWN`, a WARNING log, and that
`save_review_file`/`format_review_markdown` were still called.

### Slice 303 re-review F004 (PLAUSIBLE): `as_json` persistence never received `verdict_override`

`save_review_result`'s `as_json=True` branch called `result.to_dict()`
directly, bypassing `verdict_override` entirely — the docstring said
as much ("Ignored for `as_json` output"). A judge review persisted as
JSON would show `UNKNOWN` while the markdown persistence of the
identical run showed the correct threshold-derived verdict. Dormant
today (no live caller passes both `as_json=True` and a judge
template), but real.

Gave `ReviewResult.to_dict()` an optional `verdict_override` parameter
(mirroring `format_review_markdown`'s existing signature) and threaded
it through from `save_review_result`. Added 2 tests to
`tests/review/test_models.py` (`to_dict(verdict_override=...)` in
isolation) and 1 to `tests/cli/test_review_save.py` (the full
`save_review_result(as_json=True, verdict_override=...)` path writing
real JSON to a `tmp_path`).

Full gate (2139 tests, pyright strict, ruff) clean before commit.
None of F001-F004 were filed as GitHub issues — Erik preferred to fix
directly since all four were confirmed against current source.

---

### Issue #22: Verified Against Real SDK Run; Issue #24 Filed (Rules Sent Twice)

Erik ran the fixed build in a real terminal (`uv run sq run`, local
unpublished build — an earlier attempt using the globally-installed
version predictably still hit the old bug) against `claude-sonnet-5`,
producing `project-documents/user/reviews/303-review.code.judge-gated-cycle-conventions.md`.
Checked the saved review for validity: raw output is clean prose
throughout — no `Using tool:` fragments, no run-on lines, well-formed
`### [SEVERITY]`/`location:`/`category:` structure. All six findings
(4 PASS, 2 NOTE) traced against real source and verified accurate — no
hallucinated paths, lines, or symbols. Confirms the #22 fix (commit
`2032cf0`) holds against actual Claude Agent SDK message shapes, not
just the hand-constructed mocks in `test_review_client.py`/
`test_summary_oneshot.py`. Closed #22.

**New finding surfaced during verification, filed as #24 (not fixed
this session):** the saved review's debug appendix showed the
"Design Principles" / SOLID rules content duplicated — once in the
`### System Prompt` section and again in `### Rules Injected`, and
duplicated *within* the system prompt section itself. Traced to
confirm this is a real double-send to the model, not just a debug
display artifact:

- `review_code` ([cli/commands/review.py:707-711](src/squadron/cli/commands/review.py#L707-L711))
  calls `load_review_rules("code", resolved_rules_dir, file_paths=...,
  manual_rules_content=manual_content)` — correctly assembles template
  rules (`review-code.md`) + auto-detected language rules (`python.md`)
  + any explicit override. One copy of template rules.
- It then calls `_run_review_command` ([lines 721-729](src/squadron/cli/commands/review.py#L721-L729)),
  passing **both** this already-assembled `rules_content` *and*
  `rules_dir=resolved_rules_dir`.
- `_run_review_command` ([lines 322-329](src/squadron/cli/commands/review.py#L322-L329))
  unconditionally re-runs `load_review_rules` whenever `rules_dir is
  not None`, prepending `review-code.md`'s content a **second time**
  onto content that already has it.
- `review_client.py:78-82` bakes the resulting doubled `rules_content`
  into `AgentConfig.instructions` — the actual system prompt sent to
  the model. Confirmed this is real, not cosmetic: every `sq review
  code` run with a rules dir configured (the common case) sends
  `review-code.md`'s content twice, inflating prompt size and token
  cost on every call.
- `slice`/`arch`/`tasks` review commands don't have this bug — they
  never pre-assemble `rules_content` themselves, so `_run_review_
  command`'s single internal `load_review_rules` call is the only one
  that ever runs for those paths. `_run_review_command`'s own comment
  ("Language auto-detection is handled by the caller... `_run_review_
  command` only sees the template [rules]") is stale — `review_code`
  now does its own full `load_review_rules` call including template
  rules, not just auto-detection, so the comment's assumed division of
  labor no longer holds.

Not fixed this session — needs its own change (likely: `review_code`
passes `rules_dir=None` once it has fully assembled `rules_content`
itself, relying on the existing `if rules_dir is not None` guard to
skip the redundant call) plus a regression test asserting `review-
code.md` content appears exactly once in the final system prompt.

Also committed (`477db4f`): the verification review file itself, and
the untracked `303-review.code.judge-gated-cycle-conventions-kimi26.md`
comparison-run artifact from the original #19 size-cap investigation
(previously referenced but never committed).

### Issue #22: SDK Tool-Call Noise No Longer Corrupts Review/Summary Raw Output

Noticed while investigating #20 (fabricated review findings): the fixed
`sonnet-fail.md` artifact's raw response contained an unreadable run-on
line — `Using tool: BashUsing tool: BashUsing tool: Read...Clean. Now
let's run the relevant test suite...` — prose and tool-call narration mashed
together with no whitespace between them at all.

**Root cause:** `providers/sdk/translation.py` correctly translates each SDK
content block into its own `Message` — a `TextBlock` (the model's actual
prose, `sdk_type: assistant_text`) and each `ToolUseBlock` (a tool
invocation, rendered as `content=f"Using tool: {block.name}"`, `sdk_type:
tool_use`) are distinct, well-formed messages. The bug was downstream, in
how callers reassembled them: both `review_client.py:150`
(`raw_output += response.content`) and `pipeline/summary_oneshot.py:78`
(identical pattern) accumulated every yielded message — prose, tool-use
markers, and tool-result content (command stdout / file contents,
`sdk_type: tool_result`) alike — via bare string concatenation with no
separator and no type filtering. Whenever a model's turn alternated prose
and tool calls (normal for any review or summary that reads files or runs
commands before responding), the result was one run-on line with tool
narration interleaved mid-sentence.

**Why this isn't just cosmetic:** the corrupted text is exactly what
`parse_review_output` parses for `## Summary` / `### [SEVERITY] Title`
structure, and what gets written verbatim into the saved review file body
and the `-vv`/mismatch debug log. A tool-use marker landing between two
lines that were meant to be separate can break the very structural patterns
the parser depends on — plausibly a contributing cause of #20's fabrication
trigger, independent of #20's own (already-fixed) fallback-extraction bug.

**Fix:** both call sites now filter out `sdk_type in ("tool_use",
"tool_result")` messages entirely (alongside the pre-existing
`SDK_RESULT_TYPE` duplicate-content filter) and join the remaining
assistant-text chunks with `"\n"` instead of bare `+=`. Non-SDK providers
never set `sdk_type` and are unaffected — the filter only ever excludes
messages that explicitly opt in to the `tool_use`/`tool_result` marker.
Updated `test_summary_oneshot.py`'s multi-chunk test to expect newline
joining instead of the old bare-concatenation shape; added
`test_capture_summary_filters_tool_messages` and (in
`test_review_client.py`) `test_raw_output_excludes_tool_call_noise`, both
asserting tool-call content never reaches the accumulated output.

**Scope note:** `pipeline/sdk_session.py:166` (the main dispatch path for
design/tasks/implement steps) has the identical pattern
(`"".join(response_parts)`, no tool-message filtering) but was left
untouched — it's a different subsystem (dispatch artifacts are mostly
written by the agent's own file tools, not parsed from the returned string)
that needs its own look at actual downstream impact before applying the
same fix blind. Filed as [#23](https://github.com/ecorkran/squadron/issues/23).

**Not yet verified against a real SDK run** — all coverage above is via
mocked `handle_message` iterators. Real-terminal `sq review code` runs
against `claude-sonnet-5` (or another SDK profile) are still needed to
confirm the fix holds against actual Claude Agent SDK message shapes, not
just the mocked translation this repo's tests construct by hand.

Full gate: `uv run pytest` (2128 passed, 2 skipped), `uv run pyright` (0
errors), `uv run ruff check`/`format` (clean). Committed directly to `main`
(non-slice bugfix, no feature branch). Closes
[#22](https://github.com/ecorkran/squadron/issues/22).

### Issue #20: Parser No Longer Fabricates Findings From Unstructured Prose

Follow-up from slice 303's comparison code-review testing (same batch as
#19, below). A `sq review code 303 -vv --model claude-sonnet-5` run produced
a persisted review whose frontmatter `findings` were verifiably garbage:
truncated mid-sentence fragments lifted from the model's own tool-use
narration (`"**What's solid:** ruff and pyright are clean..."`) and a
numbered "Gaps found" list item, each dressed up with an invented severity
and a fabricated `F001`/`F002` id. Structurally valid-looking, semantically
meaningless.

**Root cause:** `parsers.py`'s `_extract_findings` correctly requires a real
structural marker (`### [SEVERITY] Title`, `**[SEVERITY]** Title`, or
`- [SEVERITY] Title` — five formats total after slice 122's widening). When
a model's response has a CONCERNS/FAIL verdict but doesn't emit any of those
markers, the parser fell through to `_lenient_extract_findings`, whose
`_LENIENT_RE` regex matched on the bare presence of `NOTE`/`CONCERN`/`FAIL`
*anywhere in a line*, with no structural anchor — the opposite of what
`_extract_findings` requires. Confirmed via the affected review's own raw
output: the model wrote free-form prose, and the keyword-anywhere regex
grabbed sentence fragments after it, truncated to 120 chars, as if they were
independent findings.

**History check (before fixing):** this fallback path is genuinely old
(`c0c697f`, 2026-03-25, slice 122 "Review Context Enrichment") and was
solving a real, documented problem at the time — `minimax` returning a
CONCERNS verdict with the saved review showing "No specific findings" at
all, silently dropping real concerns the model had raised. Slice 122's
design doc (Layer 2/Layer 3 split) conflated two different fixes under one
"fallback" umbrella: Layer 3 (widening `_FINDING_RE` to accept colon
separators, bold brackets, bullets — still requiring a real marker) is
sound and unchanged. Layer 2 (`_lenient_extract_findings` +
`_synthesize_fallback_finding`, no structural anchor) is what actually
fabricates. Confirmed via `git log` that nothing in the review subsystem
changed in the days immediately before this bug was noticed — the parser
gap is ~4 months old; it was model-response variance (this specific
`sonnet5` run's prose shape) that exposed it now, not a regression.

**Fix:** removed `_lenient_extract_findings` and
`_synthesize_fallback_finding` entirely, along with `_LENIENT_RE`. When a
CONCERNS/FAIL verdict has zero structured findings, `parse_review_output`
now logs a WARNING (template, model, verdict) and leaves `findings` empty —
the same "honest empty" shape already used for PASS. Nothing is silently
lost: `ReviewResult.raw_output` (and the saved review file body) always
carries the model's full raw response regardless of findings, so a human
can still read what the model actually said; it's just no longer disguised
as structured findings. `fallback_used` keeps its existing meaning
("verdict/findings mismatch was detected") for telemetry/debug-log
purposes. Updated `tests/review/test_parsers.py`'s `TestFallbackParsing`
class to assert the new empty-findings-plus-warning behavior instead of
the old synthesized-finding shape; added `test_mismatch_preserves_raw_output`
and `test_mismatch_logs_warning`.

Full gate: `uv run pytest` (2126 passed, 2 skipped), `uv run pyright` (0
errors), `uv run ruff check`/`format` (clean). Committed directly to `main`
(non-slice bugfix, no feature branch — `git.integration_branch` unset).
Closes [#20](https://github.com/ecorkran/squadron/issues/20).

### Issue #19: Review File-Injection Size Caps Are Now Configurable

Also from slice 303's comparison code-review testing: a `kimi26` review run
truncated a 136,191-byte diff because `review_client.py`'s file-injection
limits (`_MAX_FILE_SIZE` = 100KB, `_MAX_TOTAL_INJECTION` = 500KB) were
hardcoded module constants with no way to raise them for a model with a
larger context window.

**Fix:** added two typed config keys, `review.max_file_size_bytes` (default
100,000) and `review.max_total_injection_bytes` (default 500,000), to
`config/keys.py` following the existing `ConfigKey` pattern. Removed the
hardcoded constants from `review_client.py`; `_inject_file_contents` now
resolves both via `get_config(key, cwd=...)` at call time, scoped to the
review's `cwd`, with `isinstance` narrowing and an explicit `TypeError` on
type mismatch (fail-fast per CLAUDE.md, since `_coerce_value` guarantees the
stored type is always `int` — a mismatch here is genuinely exceptional, not
a normal missing-config case). `_truncate` now takes `max_file_size` as an
explicit parameter instead of reading a module constant. No additional
wiring needed for `sq config get/set/unset/list` — those subcommands
already operate generically over `CONFIG_KEYS`, so the new keys were live
immediately; verified with `sq config list` and `sq config get
review.max_file_size_bytes`.

New test `test_max_file_size_config_override` proves a raised config value
actually lets larger content through untruncated. Full gate: `uv run
pytest` (2125 passed, 2 skipped), `uv run pyright` (0 errors, after fixing
a `reportArgumentType` regression from passing untyped `object` to `int()`
— resolved with the same `isinstance` narrowing pattern already used in
`cli/commands/review.py:_resolve_verbosity`), `uv run ruff check`/`format`
(clean). Committed directly to `main` (`71d8524`, non-slice bugfix, no
feature branch). Closes [#19](https://github.com/ecorkran/squadron/issues/19).

**Note:** this fix does not address #20 (above) — the `sonnet5` review
artifact that motivated #20 had a diff well under the size cap; its failure
is 100% attributable to the parser-fabrication bug, unrelated to injection
truncation.

### Slice 303: Judge-Gated Cycle Conventions — Complete

Phase 6 implementation complete, T0–T8. Delivered `judge-cycle.yaml` (built-in
reference pipeline: fix-first `loop [dispatch, review]`, `max: 3`,
`until: review.pass`, `on_exhaust: checkpoint`, review step templated on
`judge.slice-vs-arch`), a structural test in `test_loader_integration.py`,
three control-flow tests in a new `tests/pipeline/test_judge_cycle.py`
(auto-advance, escalate-at-max, advisory-always-escalates — all driving the
real `ReviewAction`/loop/`enforce_judge` path with only
`run_review_with_profile`/persistence/`resolve_slice_info` mocked), and a
"Judge-Gated Cycles" section plus missing `### loop`/bare-`dispatch` catalog
entries in `docs/PIPELINES.md`.

**Live validation (T7) surfaced two pre-existing bugs, both fixed:**

1. `judge-cycle.yaml` initially left the review step's `model:` unset,
   relying on an implicit fallback — inconsistent with every other built-in
   pipeline's convention (`P4.yaml`, `slice.yaml`: named `model`/
   `review-model` params, referenced via placeholders). Rewrote
   `judge-cycle.yaml` to match: `params: {model: sonnet, review-model:
   minimax}`, both steps reference their param via `"{...}"`.
2. Independent of (1), `ReviewAction`'s model-resolution cascade (CLI →
   action → step → pipeline → config) never consulted a review template's
   own `model:` default — unlike `sq review`'s CLI-side cascade, which
   falls back to `template.model` as its last resort
   (`cli/commands/review.py:_resolve_model`). A pipeline `review:` step with
   no model anywhere always raised `ModelResolutionError`, even for a judge
   template that declares a sensible default (`judge.slice-vs-arch`:
   `opus`). Fixed in `pipeline/actions/review.py`: on `ModelResolutionError`
   from the standard cascade, retry once against `template.model` before
   giving up. New tests in `test_review_action.py` cover both the rescue
   path and the case where no template default exists (error still
   propagates unchanged).
3. Also surfaced live: the persisted review file's `verdict:` field came
   from the raw `ReviewResult.verdict`, always `UNKNOWN` for judge templates
   by design (`judge-slice-vs-arch.yaml`'s prompt explicitly forbids
   emitting a verdict line — the score is the source of truth). A human
   reading the file saw `UNKNOWN` next to a score that clearly passed.
   Fixed: `format_review_markdown`/`save_review_result`
   (`review/persistence.py`) now accept an optional `verdict_override`;
   `ReviewAction._review` computes the `enforce_judge`-derived verdict
   *before* persistence (previously persistence ran first) and supplies it
   for judge templates. New tests in both `test_review_action.py` and
   `test_persistence.py` cover the override and the unchanged
   non-override/non-judge paths.

All three fixes are small, additive parameter/reordering changes to
*existing* functions — no new step type, action, selector, or executor
branch, so FR6 ("no new constructs") holds — but they are a deviation from
the slice's stricter "zero engine code" framing, noted directly in the LLD's
Success Criteria section rather than glossed over.

**T7 final live run** (`sq run judge-cycle 302`, no manual `--model`,
minimax via the new param defaults): judge scored slice 302's design at 98
against its architecture doc, cleared `pass_floor` (82), loop exited on
iteration 1, pipeline reported `completed`/`PASS`. Persisted file
(`302-review.judge.slice-vs-arch.design-phase-judge-templates.md`) now shows
`verdict: PASS` end-to-end. An earlier iteration of this same live run (fix
leg, score below the floor) genuinely improved
`302-slice.design-phase-judge-templates.md`'s anchoring-mitigation
rationale — committed as real design-doc value, not test residue.

**Known gap, not fixed (out of scope):** `LoopStepType.expand()` deliberately
returns `[]` (iteration is owned by the executor's `_execute_loop_body`, not
the flat action-list path) — so `--prompt-only` mode cannot drive any `loop`
step at all, including `judge-cycle`. `sq run` inside a Claude Code session
also refuses direct SDK execution. A `loop`-based pipeline is therefore only
runnable from a standalone terminal today. Not filed as a separate GitHub
issue; noted here and in the slice's Verification Walkthrough for whoever
picks up prompt-only/loop support next.

Full gate: `uv run pytest` (2124 passed, 2 skipped), `uv run pyright` (0
errors), `uv run ruff check` (clean). Slice 303 marked complete in its own
frontmatter and in `300-slices.eval-actions-llm-as-judge-scoring.md`.
Branch `303-slice.judge-gated-cycle-conventions` ready to merge to `main`.

## 20260714

### Slice 303: Judge-Gated Cycle Conventions — In Progress

Phase 5 (task breakdown) complete: created
`user/tasks/303-tasks.judge-gated-cycle-conventions.md` (T0–T8) from the
approved LLD. The slice is data + docs + tests only — no engine change:
`judge-cycle.yaml` reference pipeline (fix-first `loop [dispatch, judge]`,
`max: 3`, `until: review.pass`, `on_exhaust: checkpoint`), structural test in
`test_loader_integration.py`, three control-flow tests (auto-advance,
escalate-at-max, advisory-always-escalates) in a new
`tests/pipeline/test_judge_cycle.py`, authoring docs in `docs/PIPELINES.md`,
and one live unattended validation run.

Two findings surfaced during breakdown, folded into the tasks:
- `docs/PIPELINES.md` has no `### loop` (or bare-`dispatch`) Step Type
  Catalog entry — the convention section is unfollowable without them; T6
  adds both alongside the judge-gated-cycles section.
- The issue-#18 guard (`4564471`, shipped after the 303 design) makes a
  missing `input`/`against` file a hard error in `ReviewAction._review`, so
  the control-flow tests cannot mock `run_review_with_profile` alone — T3's
  harness must provide real tmp input/against files or patch the slice-input
  resolution seam, while keeping `resolve_thresholds`/`enforce_judge` and the
  loop evaluation real.

Pending: Phase 6 implementation on branch
`303-slice.judge-gated-cycle-conventions` (T0). Resume point: T0/T1.

### Fixed issue #18: review input/against existence guard

`missing_input_files()` (new, `review/template_inputs.py`) returns the
`input`/`against` keys whose values name no real file — checked against both
the process cwd (how non-SDK content injection resolves paths) and
`inputs["cwd"]` (how SDK review agents resolve them), so a path valid under
either provider semantics is accepted. Both review boundaries now hard-fail
on a non-empty result before any model call: `_run_review_command` (covers
`sq review slice|tasks|arch|code`) exits 1 with `Error: {key} file not
found: {path}`; `ReviewAction._review` raises the same KeyError shape as its
existing required-inputs check, so judge-awareness (verdict=UNKNOWN) and
step-failure routing are preserved. Defense-in-depth: `_inject_file_contents`
now logs a WARNING when it skips a missing `input`/`against` (it previously
skipped silently — the asymmetry with its logged `OSError` branch was the
original #18 observation); other keys still skip silently by design since
they may hold non-path values.

Tests: 11 new (helper unit tests, CLI guard via CliRunner, pipeline action
guard, injection-warning + no-noise cases). 13 existing tests updated —
they passed fabricated paths (`slice.md`, `a.md`, `f.md`) to mocked review
clients and now use real tmp files, which the guard correctly rejected.
Full gate: ruff clean, format clean, pyright 0 errors, pytest 2112 passed /
2 skipped.

**Correction to 20260714 (1) below:** its claim that no `143-tasks.*.md`
existed on disk was a stale snapshot — the file was created minutes later
by a parallel agent working the same repo, and the review it sourced was
genuine (verified via timestamps and finding-ID cross-references). Issue
#18's "observed in the wild" example was retracted on the issue; the code
gap itself was real regardless and is what this entry fixes. Lesson
recorded: filesystem facts from earlier in a session decay — re-verify at
the moment of use, especially before publishing claims.

### Diagnosed field bug: 909 dispatch-artifact fix never released to PyPI

`sq run p5a <slice>` failed in a client repo (grizcam_mobile_ios) at the
`review template=tasks` step with `missing required input(s): input,
against` — the exact pre-909 symptom, on a repo confirmed to have current
guides and no CF-side formatting issue.

**Investigation ruled out, in order:** (1) `p5a.yaml`/`p4.yaml` custom
pipeline definitions — both correctly use `tasks:`/`design:` phase-step
shorthand, not raw `dispatch:`, so they get the full 909 post-condition
guard; (2) context-forge slice-plan parsing — slice 143's checklist line
(`4. [ ] **(143) ...** — desc`) matches `PLAN_INDEXED_RE` cleanly, confirmed
by testing the actual line against the regex; (3) CF worktree scoping — not
in use in the affected repo; (4) a race between the two `resolve_slice_info`
calls (dispatch's post-condition check and the review step's input
resolution) — ruled out, `cf list tasks --json` does a live filesystem scan
with no caching on either side.

**Root cause:** the installed `sq` was `squadron-ai 0.6.2` via `uv tool
install` — a real PyPI release, not a dev/editable checkout. Confirmed by
grepping the installed wheel's `executor.py` directly: zero references to
`_check_dispatch_artifact_written` / `expected_artifact_kind`. The 909 fix
(commit `49b8522`) merged to `main` on 20260710 but `pyproject.toml`'s
`version` was never bumped past `0.6.2` and no release was cut — so every
consulting client running `squadron-ai` from PyPI has been on pre-909
squadron the entire time, including this session's own local install
(chalked up as "we should release 0.6.2 anyway" rather than investigated
further, since the fix and its tests are confirmed correct on `main`).

Slice 143 itself is legitimately `needs-design`/`not-started` — no
`143-tasks.*.md` exists on disk, consistent with a dispatch agent turn that
ended without writing the file (same failure shape as the original 303
repro that motivated 909). On a release containing 49b8522, this would now
fail loudly at the dispatch step with an accurate message instead of
surfacing one step later at review.

**Action:** prepared a 0.7.0 release (see below) rather than a 0.6.3 patch
— `[Unreleased]` already contained a full minor's worth of shipped-but-
unreleased feature work (judge templates, judge enforcement) alongside the
three bug fixes, so a minor bump is correct per semver even though this
investigation only needed the fix half.

### Prepared release 0.7.0

Bumped `pyproject.toml` version `0.6.2` → `0.7.0`, re-ran `uv lock` to sync
`uv.lock`, converted `CHANGELOG.md`'s `[Unreleased]` section to `## [0.7.0]
- 20260714` (left a fresh empty `[Unreleased]` above it). Verified `uv
build` produces a clean sdist/wheel and that the built wheel actually
contains the 909 fix (`unzip -p ... | grep _check_dispatch_artifact_written`
→ 2 matches). Full test suite green: 2101 passed, 2 skipped, 0 failed — no
regressions since the last recorded baseline. Committed and tagged `v0.7.0`;
`pypi` publish deliberately deferred as a separate, explicit step.

## 20260712

### Slice 906: Quickstart and Onboarding Documentation — Complete

New `docs/QUICKSTART.md`, plus two additive links from `README.md`. Docs-only
slice; no code changes. Branch `906-slice.quickstart-and-onboarding-documentation`
merges to `main` on completion, `codeReview: none` (no-code slice, gate
bypassed via `cf check --set-review-none 906`).

**Design history — two corrections, both discovered by re-verifying live
state instead of trusting the prior draft:**

1. The original design (20260513) assumed a manual multi-step install
   narrative (npm → `cf init` → pipx → `sq install-commands` → provider auth)
   that slice 908 (`sq setup`) has since superseded. Rebuilt 20260711 to lead
   with `install.sh` → `sq setup` as the canonical path.
2. That rebuild *itself* turned out to misdescribe the current README: it
   assumed README's Install section still needed the `curl | sh` one-liner
   added (908 had already landed it) and that Quickstart needed replacing
   with an install-pointer (Quickstart is actually a different, already-good
   section — SDK auth, review-a-design, review-tasks-then-code — unrelated to
   install steps). Corrected 20260711 after actually reading the live README
   top to bottom rather than reasoning from the stale design.
3. During Phase 6 itself, Task 1's re-verification step (built into the task
   file specifically to catch further drift) found a third error: the design
   claimed `sq run` was undocumented anywhere in README. It is documented —
   a `## Pipelines (sq run)` section already exists. "Your first pipeline
   run" was written as a short bridge/pointer (matching the "Your first
   review" section's treatment), not as net-new content.

**What QUICKSTART actually covers** (the real, narrower gap after all three
corrections): how to read `sq doctor`/`sq setup --check-only` output
(undocumented anywhere before this), the full six-profile provider matrix
(README's existing Quickstart only documents `sdk` auth), and pointers to
README/`docs/PIPELINES.md` for review and pipeline walkthroughs rather than
duplicating them.

**Verification (20260712):** `sq doctor -v`, `sq setup --check-only`,
`sq run --help`, and `BUILT_IN_PROFILES` all captured live and used verbatim
in QUICKSTART rather than reconstructed from memory. `sq run slice 906
--dry-run` confirmed QUICKSTART's example command resolves correctly.
`git diff README.md` confirmed additive-only (two insertions, zero
deletions). Full gate: ruff clean, pyright 0 errors, pytest 2101 passed / 2
skipped / 0 failed — matches pre-slice baseline (docs-only change).

**Takeaway for future doc slices:** a slice design's claims about "what's
currently documented" or "what's currently missing" are load-bearing facts
that decay fast — this slice needed re-verification at three separate
points (initial rebuild, second rebuild, and again inside Phase 6's own
task list) before its scope was actually correct. Building an explicit
"re-verify live state" phase into the task file (rather than trusting the
design as ground truth) is what caught the third error; worth carrying that
pattern into future docs-only slices.

---

## 20260710

### Slice 909: Pipeline Phase-Step Correctness — Implementation Complete

**Phase 6 complete.** All 18 tasks implemented across three commits, C → B → A: `85f2e03` (Part C, review-code scope guard, #17), `ac01838` (Part B, review frontmatter project name, #16), `49b8522` (Part A, dispatch artifact post-condition, #15). Full suite passes (2101 passed, 2 skipped), ruff clean, pyright clean.

**Part A surfaced a real pre-existing bug while wiring T12/T13, not a design flaw.** `PhaseStepType.expand()` (`steps/phase.py`) hardcoded a bare `"{slice}"` placeholder into the `cf-op(set_slice)` and `review` action tuples. That's correct for ordinary single-slice pipelines, but for `each`-loop pipelines (`design-batch.yaml`, `app.yaml`) the loop's `as: slice` binding puts the *whole slice record* into that variable — so `"{slice}"` resolved to a stringified Python dict instead of the numeric index. This silently corrupted `cf-op(set_slice)` (caught downstream as a `ContextForgeError`) and crashed the `review` action's `int(str(slice_param))` call outright — the identical crash my new post-condition hit immediately, since it reads `slice` on every dispatch rather than only when a review happens to run. Traced this live with the PM (three rounds of investigate-then-report, no guessing) before fixing: root cause was `expand()` receiving the step's *unresolved* config and never reading its own `slice:` key (both `design-batch.yaml` and `app.yaml` already wrote `slice: "{slice.index}"`, correctly anticipating this — it just was never consulted). Fix: `expand()` now uses `cfg.get("slice", "{slice}")` so a step-level override flows into every action tuple that references a slice, resolved later via the pre-existing (and already-correct) dotted-placeholder mechanism. Zero regression for the common case (no `slice` key in step config → identical `"{slice}"` fallback as before).

**Also fixed while chasing test fallout: `execute_pipeline()` never accepted a `runs_dir` parameter.** Any internal `StateManager()` call (the pre-existing SDK-resume-seed code, and my new post-condition) silently read from the *default* runs directory regardless of what the caller configured — a second latent bug, invisible before because the SDK-resume path is rarely hit in tests and never combined with an artifact check. Threaded `runs_dir` through `execute_pipeline` and its loop/each/fan-out helpers; updated the CLI (`run.py`) and 12 pre-existing integration tests across 4 files that broke as a direct, expected consequence of the new post-condition (their mocked dispatch actions never wrote real files, and their `cf_client` mocks couldn't resolve real slices — both now genuinely required).

**A real `sq review code 909 -v` run (not fabricated — this is the fixed Part C path) found four legitimate issues, addressed before closing the slice:** an unhandled `ValueError` in the post-condition's `int()` conversion (now caught, tested with a new case simulating an unresolved `"{slice.index}"` placeholder reaching the check); a swallowed exception in `review_arch`'s project-name resolution with no logging (now logged at WARNING per the exception-handling convention); a DRY violation — `_phase_artifact_cf_client`/`_artifact_writing_action` duplicated verbatim across 4 test files (extracted to `tests/pipeline/conftest.py`); and a scattered `"project-documents/user/tasks/"` magic-string prefix across 3 source files (extracted to a new `TASKS_DIR` constant in `squadron.review.persistence`). One flagged finding (a supposedly misleading error message in `review_code`'s scope guard) was investigated and determined to be a false positive — the code path it described is unreachable, since `_resolve_slice_number` already exits earlier with its own correct "no slice with index N" message.

**Verification Walkthrough updated in the slice design** with actual commands run and real output (not the placeholder command text from Phase 4) — see `909-slice.pipeline-phase-step-correctness.md`. Part A's live-agent repro was not re-run interactively (would require a real dispatch); the automated `TestDispatchArtifactPostCondition` suite (9 cases) exercises the identical code path with mocked dispatch actions standing in, which is documented as the verification tier used, with an explicit note on what a fully-live re-verification would look like.

**Next:** merge slice 909 to main; close issues #15, #16, #17. Then resume slice 303 Phase 5 past its original failure point — the fix that unblocks it (Part A's post-condition) is now in place.

---

## 20260709

### Slice 909: Pipeline Phase-Step Correctness — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/909-tasks.pipeline-phase-step-correctness.md` (18 tasks after task review, 274 lines) from the review-addressed design. Tasks ordered C → B → A per the design's cheapest-first sequencing, with test-with pairing throughout and a commit task closing each part.

**Grounding a trace before writing Part A tasks changed Part A's mechanics — and the design.** Before authoring tasks I traced the executor to answer "where does the artifact post-condition actually fire?" The design said "the phase step verifies after dispatch completes." The trace proved that's not mechanically possible: `PhaseStepType.expand()` (`steps/phase.py:96`) returns a flat action list and is **never consulted again** — the phase step has no post-expansion runtime hook. The only seam that runs right after a phase step's `dispatch` action is the per-action tail of `_execute_step_once` (`executor.py` ~898-943). So the honest split is: `expected_artifact_kind` is a **property on `PhaseStepType`** (declaration of what the phase owns — legitimately phase-step knowledge), but the **check runs in the executor**, keyed on `action_type == "dispatch"`, reading that property. Reconciled the design accordingly (Approach, chosen-home decision, Part A files list now name `executor.py` as a modified file, not just `phase.py`) so the two documents don't contradict.

**Two more grounded facts the tasks now carry (no guessing left for the junior AI):**
- **Run-start timestamp** for the stale-artifact mtime check is NOT on `ActionContext`; it lives in `RunState.started_at` (`state.py:126`), loadable via `StateManager().load(run_id).started_at` (precedent: `executor.py:603-606`). T12 makes this an explicit task.
- **Expected-path resolution** reuses `resolve_slice_info(context.cf_client, int(slice)).task_files` / `.design_file` — the exact call the review action already makes at `review.py:264`; `ActionContext` exposes `cwd`, `params["slice"]`, and `cf_client` (a `CfClientProtocol` with the three methods `resolve_slice_info` needs).

**Test-with coverage of the failure-mode table:** T14 enumerates all six Part A cases (present+fresh → pass, absent → fail, stale-mtime → fail, unresolvable-path → fail+WARNING, OSError → fail+log, `implement`/kind-`None` → skipped) plus a "generic dispatch unaffected" assertion. Part B's T5/T8 use real-shaped `cf get --json` fixtures (must include `name`) per the fixture-realism rule; Part C's T2 asserts the review client is **not called** for missing/malformed scope — proving the fabricated-review path is closed.

**Next:** Phase 6 (Implementation) for slice 909, not yet started. Then resume slice 303 Phase 5 past its original failure point.

---

### Slice 909: Pipeline Phase-Step Correctness — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/909-slice.pipeline-phase-step-correctness.md` on branch `909-slice.pipeline-phase-step-correctness`, from the slice-plan entry in `900-slices.maintenance-and-refactoring.md`. Three independent bugs bundled into one maintenance slice (all surfaced during slice 303 planning; all share a silent-success failure signature): Part A dispatch artifact post-condition (#15, Medium), Part B review-frontmatter project literal (#16, Low), Part C review-code scope guard (#17, Medium).

**Grounded every anchor against on-disk code before designing, not the issue text alone:**
- **Part A:** confirmed `PhaseStepType.expand()` (`steps/phase.py:96`) emits a bare `("dispatch", {"model": model})` with **no** expected-output attached — so the memory-carried claim "the phase step knows the expected artifact" is *aspirational*: the phase→artifact mapping is conceptually known but materialized nowhere. Confirmed both dispatch success paths (`dispatch.py:198`, `:284`) return `success=True` with only a `_check_cli_error` text scan — no artifact post-condition. Design decision recorded: the post-condition belongs on `PhaseStepType` (which *does* know its phase produces an artifact), NOT in generic `DispatchAction` (must stay usable for bare dispatch steps that write nothing) — rejecting the generic-dispatch home on SRP grounds.
- **Part B:** verified live that `cf get --json` actually returns `"name": "squadron"` — so the fix has a real source, not a hallucinated one. Confirmed `ProjectInfo` (`context_forge.py:52`) has no `name` field, and that `resolve_slice_info` (`persistence.py:66`) *already* calls `get_project()` and merely discards everything but `arch_file`. Confirmed both review write paths (pipeline `save_review_result` → `actions/review.py:193`; CLI `persistence.py:268`) converge on `format_review_markdown`, so a single-point fix there satisfies interface-parity by construction. The `"project: squadron"` literal (`persistence.py:119`) sits directly beside `slice_name`/`slice_index`, which *are* already data-driven with an `"unknown"` fallback — the literal is the lone inconsistency.
- **Part C:** confirmed the guard at `review.py:641` is `if slice_number is not None and slice_number.isdigit()`, so a **malformed non-digit** argument falls through identically to a missing one — the fix must cover both, not just the missing case. Confirmed `review_slice`/`review_tasks` already hard-guard (`if not against: raise typer.Exit(code=1)` at `review.py:408-410`, `551-553`); Part C mirrors that exact pattern. Confirmed `--model glm51` → `z-ai/glm-5.1` resolves correctly and is NOT part of the bug.

**Cross-check carried from prior 303 work:** re-confirmed `StepTypeName` has no `COMMIT` member (design/tasks/implement/dispatch/compact/summary/review/each/fan_out/loop/devlog) — `commit` is an action, not a step type, consistent with the 303 loop-body finding.

**Suggested implementation order (in the design):** Part C (isolated CLI guard, mirrors existing pattern) → Part B (small data-threading through a verified source) → Part A (the genuine design work: post-condition home + unattended-question routing) last, so the two easy wins land regardless of Part A's depth.

**Next:** Phase 5 (Task Breakdown) for slice 909, not yet started. Then resume slice 303 Phase 5 past its original failure point.

---

## 20260706

### Slice 303: Judge-Gated Cycle Conventions — Slice Design (Phase 4) Complete

Design document authored at `user/slices/303-slice.judge-gated-cycle-conventions.md`
on branch `300-planning.judge-gated-cycle-conventions`.

**Central finding:** the judge-gated review→fix→re-review cycle is expressible
today with **zero new code** — it is `loop` + a judge `review` step + `dispatch`
+ `checkpoint`, all pre-existing. Verified against the real constructs:
- `LoopCondition.REVIEW_PASS` / `REVIEW_CONCERNS_OR_BETTER` (`executor.py:215`)
  evaluate the last verdict — and a judge's verdict is the score's threshold
  projection (slice 301). So "gate on the score" needs no score-aware loop
  condition.
- `ExhaustBehavior.CHECKPOINT` (`executor.py:257`) → `PAUSED` StepResult is the
  observable escalation path when the bound (`loop.max`) is hit without clearing.
- The `review` step already accepts a step-level `judge:` threshold override
  (`steps/review.py`) — so **advisory-only = `pass_floor > 100`**, a value not a
  flag. No new "always-escalate" field.
- `test-loop.yaml` already ships the exact `loop [dispatch, review] until:
  review.pass` shape with a *standard* review; the delta to a judge cycle is the
  template name and `on_exhaust: checkpoint` — data only.

**Deliverables the slice defines (for Phase 6):**
- `data/pipelines/judge-cycle.yaml` — worked reference pipeline (judge-first
  shape: pre-loop judge, then `loop [fix, judge]`, `until: review.pass`,
  `on_exhaust: checkpoint`), gating on `judge.slice-vs-arch`.
- Structural + three control-flow tests (auto-advance, escalate-at-max,
  advisory-always-escalates) with a mocked judge score to prove the flow
  deterministically; one live unattended run to validate the fix prompt.
- Authoring-guide section covering the bound, exit condition, escalation, the
  two gating modes, and the optional `commit` body step.

**Scope boundaries recorded:** gate composition (judge + review verdict) is
slice 304; multi-sample judging is Future Work 1; new `each` sources are out of
scope (only `cf.unfinished_slices` is registered).

**Branch:** `300-planning.judge-gated-cycle-conventions` (created from `main`).

**Next:** Phase 5 (Task Breakdown) for slice 303, then Phase 6 implementation on
`303-slice.judge-gated-cycle-conventions`.

---

## 20260705

### Slice 302: Design-Phase Judge Templates — Implementation Complete

All 11 tasks (T1–T11) implemented on branch `300-planning.design-phase-judge-templates`.

**What was built:**
- `data/templates/judge-tasks-vs-slice.yaml` — judge variant of `tasks.yaml`; reuses its evaluation criteria verbatim, swaps the output contract to score+rationale+findings, forbids a verdict summary. `judge: {pass_floor: 78, concerns_floor: 55}`.
- `data/templates/judge-slice-vs-arch.yaml` — judge variant of `slice.yaml`, same pattern. `judge: {pass_floor: 82, concerns_floor: 60}` (higher floor — architecture alignment is more interpretive ground truth than a concrete task list).
- `review/template_inputs.py` — two new `TEMPLATE_INPUTS` entries (`judge.tasks-vs-slice`, `judge.slice-vs-arch`), reusing the existing `_tasks_input`/`_design_file`/`_arch_file` source functions unchanged. No prefix-stripping fallback (rejected in the slice design as reintroducing naming-convention dispatch).

**No engine/parser/action changes** — both templates run through the unmodified `ReviewAction._review()` → `run_review_with_profile()` → parser → `enforce_judge()` path built in slice 301/300.

**Tests:** 8 new/extended tests across `test_templates.py` (load + is_judge + threshold differentiation regression guard), `test_template_inputs.py` (resolution + exact-keyset regression), and `test_review_action.py` (T7: rogue model-emitted verdict discarded — confirms `enforce_judge()` never reads `result.verdict`; T8: `TEMPLATE_INPUTS` resolution failure surfaces as `UNKNOWN`/`provenance=judge` via the existing exception handler, not a silent skip). Both new-to-this-slice failure modes needed no new handling code — only new test coverage confirming slice 301's mechanisms already cover them.

**Live-provider verification (T9/T10):** ran both templates against real in-repo artifact pairs via `run_review_with_profile()` directly (openrouter profile, `anthropic/claude-opus-4.5` — the `sdk` profile can't launch from inside an active Claude Code session). `judge.tasks-vs-slice` scored 91.0 reviewing this slice's own task file against its slice design; `judge.slice-vs-arch` scored 86.0 reviewing this slice's design against its architecture doc. Neither run emitted a `## Summary`/verdict line; both produced well-formed `criteria` maps and findings. No prompt revision needed. The slice-vs-arch score (clears `pass_floor=82`) is consistent with the design's already-fixed review findings — the committed human review's `CONCERNS` verdict predates the `d69ee7e` fixes to failure-mode enumeration.

**Full validation:** 2080 passed / 2 skipped (pre-existing, unrelated), `pyright` 0 errors, `ruff check`/`format` clean, `sq review list` shows all 6 templates, no `template_name.startswith("judge.")`-style dispatch found in non-test code.

**Unblocks:** slice 303 (judge-gated cycle conventions) now has two real judges to compose into a pipeline.

---

### Slice 302: Design-Phase Judge Templates — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/302-tasks.design-phase-judge-templates.md` (11 tasks, 318 lines) from the reviewed slice design.

**Found and fixed a defect in the reviewed slice design before writing tasks:** the LLD's Success Criteria #3 and Verification Walkthrough step 3 assumed `sq review <judge-template-name>` was invokable from the CLI. Checked the actual CLI (`src/squadron/cli/commands/review.py`): `sq review` exposes exactly four Typer subcommands (`slice`/`arch`/`tasks`/`code`), each hardcoded to its own template name — there is no generic template-name argument. Judge templates are reachable today only via the pipeline `review` step (arbitrary `template:` config) or by calling `run_review_with_profile()` directly. Raised this to the PM (AskUserQuestion) rather than silently patching it; PM chose to drop the CLI claim from scope and correct the walkthrough to invoke the review client directly instead of a nonexistent CLI form. Both fixes committed to the slice design (`00d14ed`) before task breakdown began.

**Task structure:** author `judge-tasks-vs-slice.yaml` (T1) → test (T2) → author `judge-slice-vs-arch.yaml` (T3) → test (T4) → `TEMPLATE_INPUTS` registry entries for both (T5) → test, including updating the existing exact-keyset regression test (T6) → two tests for the failure modes newly introduced by this slice: rogue model-emitted verdict discarded (T7) and `TEMPLATE_INPUTS` resolution failure → `UNKNOWN` (T8), both confirming slice 301's existing enforcement/exception paths cover these cases with no new code → live-provider verification runs for each template (T9, T10), per the Risk Assessment's flagged prompt-quality-is-unverifiable-by-unit-test-alone risk → full validation gate (T11).

**Key discipline carried from the LLD:** judge templates reuse their standard counterpart's evaluation criteria verbatim — only the output contract changes (score+rationale+findings, no verdict). Default thresholds are deliberately different per template (`tasks-vs-slice`: 78/55; `slice-vs-arch`: 82/60, harder to auto-pass — weaker/more interpretive ground truth). `is_judge` and the `TEMPLATE_INPUTS` dict remain the only dispatch signals; the `judge.` name prefix is human-readable only (T11 greps the diff to confirm no naming-convention dispatch leaked in).

**Next:** Phase 6 (Implementation) for slice 302, not yet started.

---

### Slice 302: Design-Phase Judge Templates — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/302-slice.design-phase-judge-templates.md` on planning branch `300-planning.design-phase-judge-templates`, following the slice plan entry in `300-slices.eval-actions-llm-as-judge-scoring.md`.

**Grounded in real code, not the plan's sketch alone:** read `templates/__init__.py` (YAML loader, `judge:`/`is_judge` from 301), `data/templates/{slice,tasks}.yaml` (the two standard templates being adapted), `template_inputs.py` (`TEMPLATE_INPUTS` registry — keyed by exact template name, so judge templates need their own entries), `parsers.py` (`_extract_score`/`_extract_criteria` — confirmed these are lenient markdown-line regexes, not a JSON/schema mechanism; `_extract_criteria`'s docstring explicitly flags "the structured-output/JSON variant is slice 302" — but no schema-enforcement mechanism exists in the engine, so the architecture's "structured-output constraint" is realized at the prompt level only), and `review_client.py` (500KB injection cap, unaffected by single-artifact judging).

**Design:** two new built-in template YAML files (`judge-slice-vs-arch.yaml`, `judge-tasks-vs-slice.yaml`) reusing each standard template's evaluation criteria verbatim, swapping the output contract to score+rationale+findings (via the existing `criteria:` block, no new parser target) and explicitly forbidding a verdict summary. Plus two new `TEMPLATE_INPUTS` entries reusing the existing `_design_file`/`_arch_file`/`_tasks_input` source functions unchanged. No engine, parser, or action changes — matches the architecture's "no new engine changes" commitment for this slice.

**Key decisions:** `judge.` name prefix is human-readable only, never a dispatch signal (`is_judge`/`judge:` block presence remains the only signal, per 301's precedent and the project's no-label-as-structure rule); differentiated default thresholds per ground-truth strength (`tasks-vs-slice`: pass_floor=78/concerns_floor=55, stronger ground truth; `slice-vs-arch`: pass_floor=82/concerns_floor=60, more interpretive, escalates more readily), consistent with the architecture's "bubble up the hard calls" principle; rejected a judge→standard template-name-stripping fallback in `TEMPLATE_INPUTS` as reintroducing naming-convention dispatch.

**Flagged risk:** prompt quality (does the model actually skip the verdict, does score-with-rationale reduce anchoring) is unverifiable by unit test alone — walkthrough step 3 and the Risk Assessment call for at least one live-provider run per template during implementation, not just mocked tests.

**Next:** Phase 5 (Task Breakdown) for slice 302, not yet started.

---

### Slice 301: Judge Enforcement Layer — Implementation Complete

**Phase 6 complete.** Implemented all 13 tasks from `301-tasks.judge-enforcement-layer.md` on branch `301-slice.judge-enforcement-layer` (created from `main` after merging the planning branch).

**What shipped:** `ReviewTemplate.judge: dict | None` + `is_judge` property (identified by `judge:` YAML block presence, not naming convention); new `pipeline/actions/judge.py` — `Provenance` StrEnum (`judge`/`review`), `JudgeThresholds` dataclass with `derive_verdict()`, `resolve_thresholds()` (per-key merge: step override → template default → module constant, conservative defaults `pass_floor=75.0`/`concerns_floor=50.0`), and `enforce_judge()` (pure function — logger passed in, never reads `result.verdict`, returns `UNKNOWN` + WARNING log for absent/out-of-range score); `judge:` step-level override passthrough in `ReviewStepType.expand()`; enforcement wired into `ReviewAction._review()` for the success path and into both of `execute()`'s exception handlers (via a best-effort template re-lookup so a judge-template failure still surfaces as `verdict="UNKNOWN", provenance="judge"` rather than silently passing).

**Caveat found during T11/T12:** existing `MagicMock(spec=ReviewTemplate)` test helpers in `test_review_action.py`/`test_review_action_integration.py` auto-mocked `is_judge` (a real `@property` on the spec) as a truthy `Mock`, silently turning every pre-existing review-action test into a "judge" test. Fixed by explicitly setting `mock.judge = None; mock.is_judge = False` on the shared helper. One pre-301 assertion (`provenance is None`) was updated to `"review"`, since this slice makes provenance non-`None` universally, not just for judges.

**Validation:** full suite 2066 passed/2 skipped, `pyright` 0 errors, `ruff check`/`format --check` clean, all 5 LLD walkthrough commands verified against real output, checkpoint `_TRIGGER_THRESHOLDS` confirmed to already include `UNKNOWN` in both `ON_CONCERNS`/`ON_FAIL` (no change needed), grep for naming-convention dispatch leaks found none.

**Slice 301 marked `complete`** in both its own slice-design frontmatter and the initiative slice-plan checklist. CHANGELOG entry added under `[Unreleased]`.

**Next:** slice 302 (Design-Phase Judge Templates) — first real judge YAML templates against this enforcement contract; no engine changes expected.

---

## 20260704

### Slice 301: Judge Enforcement Layer — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/301-tasks.judge-enforcement-layer.md` (225 lines, 13 tasks) from `301-slice.judge-enforcement-layer.md`.

**Task structure:** `ReviewTemplate.judge`/`is_judge` (T1–T2) → new `pipeline/actions/judge.py` module built incrementally — `Provenance`/`JudgeThresholds` (T3–T4), `resolve_thresholds` (T5–T6), `enforce_judge` (T7–T8) — each paired immediately with its test task → step-level `judge:` passthrough in `ReviewStepType.expand()` (T9–T10) → enforcement wired into `ReviewAction._review()` including the judge-exception path (T11–T12) → full validation gate (T13). Test-with pattern applied throughout; `judge.py`'s three functions are each independently tested before `ReviewAction` integration.

**Key discipline carried from the LLD:** `enforce_judge()` must stay a pure function (logger passed in, no global state); it never reads `result.verdict` — T8 explicitly tests a mismatched-verdict `ReviewResult` to prove score wins. `is_judge` is the only judge-detection signal (T13 greps the diff for naming-convention dispatch). Threshold resolution is per-key (step → template → module constant), not all-or-nothing.

**Branch:** `300-planning.judge-enforcement-layer` (Phase 5 planning work under initiative 300, per branch-naming rules).

**State:** Task breakdown ready for Project Manager approval. Next: Phase 6 implementation of slice 301 on branch `301-slice.judge-enforcement-layer`.

---

## 20260628

### Slice 344: Add `understand-anything` to Analysis Pack — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/344-tasks.add-understand-anything-to-analysis-pack.md` (147 lines, 18 tasks).

**Task structure:** Pre-work (branch + fork) → skill file (extract, adapt, verify, commit) → dispatcher update (3 targeted edits, verify, commit) → verification gate (test suite, live install/routing, required user real-repo run) → cleanup. Test-with pattern applied: install verification (T8) immediately follows skill file addition (T7); dispatcher verification (T13) immediately follows each dispatcher change.

**Key gate:** T17 (user runs skill on real repo) is a required merge gate — slice is not done until knowledge-graph build and incremental update are both confirmed live.

---

### Slice 344: Add `understand-anything` to Analysis Pack — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/344-slice.add-understand-anything-to-analysis-pack.md`.

**Design summary:** Content-only slice (effort 1/5, no Python code changes). Forks `github:Egonex-AI/Understand-Anything` (MIT) to `ecorkran/understand-anything`, extracts `understand-anything-plugin/skills/understand/SKILL.md`, prepends attribution, audits and patches instructional `/understand` self-references → `/analysis:understand-anything`, adds as `commands/analysis/understand-anything.md`, and updates the `sq:analysis` dispatcher. The existing installer's `_install_prefix()` glob picks up the new file automatically. Verification requires a user-run knowledge-graph build on a real repo before merge.

---

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Implementation Complete

**Completed:** Phase 6 implementation of slice 343. All 17 tasks done; slice marked complete.

**What shipped:**
- `InstallReceipt` model + `SurfaceType` StrEnum in `skills/models.py`
- `skills/receipts.py` — `write_receipt` / `read_receipt` (TOML via `tomli-w`, already a dependency; manual-TOML fallback not needed). Malformed/invalid receipts raise `ValueError` with path context; absent receipt returns `None`.
- `installer.install_pack()` — new `receipts_dir` param; writes a receipt after every successful install. Receipt-write failure logs WARNING, never fails the install.
- `sq skills uninstall <pack>` — reads receipt, removes exactly the files install wrote, drops the prefix dir only when empty, deletes the receipt. Graceful exit-1 with message when no receipt. Added `--receipts-dir` to `install` too.
- `doctor_checks.check_skill_packs()` + `SECTION_SKILLS`; wired into `doctor.py` `_SECTION_ORDER` and `run_all_checks()`. Uninstalled packs → WARN with `sq skills install <name>` fix hint. Present in `--json`.

**Tests:** receipts round-trip, installer receipt-writing (incl. failure-does-not-fail-install), uninstall CLI round-trip / unrelated-file-preserved / not-installed / idempotent, `check_skill_packs` installed/not-installed/no-manifest, doctor section + JSON. Full suite: 2036 passed, 2 skipped. `pyright --strict` clean, `ruff` clean.

**Verification walkthrough:** all 8 steps executed against a live dev install; output recorded in the slice design. One caveat: `tomli-w` writes `files_written` as a multi-line TOML array (cosmetic; `read_receipt` parses both forms).

**Baseline fixes (pre-existing slice-342 debt surfaced by the strict gate):**
- `tests/cli/test_install_commands.py` — expected `analysis.md` (9 sq dispatch files, was 8).
- `tests/skills/test_manifest.py` — annotated `_manifest` packs param for strict pyright.
- `tests/skills/test_cli_skills.py` — `TestInstallLocalPack` now passes `--receipts-dir` so install tests don't write a real receipt into `~/.config/squadron/receipts/`.

**State:** Slice 343 complete. Next: slice 344 (add `understand-anything` to analysis pack), no dependency on 343.

---

## 20260626

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Task Breakdown Complete

**Completed:** Phase 5 task breakdown for slice 343.

**Artifact created:**
- `user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md` — 17 tasks, 154 lines

**Task structure summary (test-with pattern):**
- T1: Branch + prereqs
- T2–T3: `InstallReceipt` model + tests
- T4–T5: `receipts.py` helpers (`write_receipt` / `read_receipt`) + tests
- T6–T7: Extend `installer.py` to write receipt + tests
- T8: Commit checkpoint — receipt infrastructure
- T9–T10: `uninstall` subcommand in `skills.py` + tests (round-trip, unrelated-file-preserved, graceful-failure cases)
- T11: Commit checkpoint — uninstall command
- T12–T13: `check_skill_packs()` + `SECTION_SKILLS` in `doctor_checks.py` + tests
- T14–T15: Wire into `doctor.py` + tests for output
- T16: Full validation pass + CLI smoke test (verification walkthrough)
- T17: Final commit + slice status updates

**State:** Ready for Phase 6 (implementation). No open questions.

---

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Design Complete

**Completed:** Phase 4 slice design for slice 343.

**Artifact created:**
- `user/slices/343-slice.sq-skills-uninstall-and-sq-doctor-integration.md`

**Key design decisions:**
- **Install receipt** — `installer.py` writes `~/.config/squadron/receipts/<pack>.toml` after each successful install. Contains `pack_name`, `surface`, `destination`, `files_written`. Uninstall reads this rather than re-resolving the source, making uninstall correct for all source types (including `github:`) and independent of source availability.
- **No orphan detection** — `sq doctor` reports only packs declared in the effective manifest; it does not scan for installed files absent from the manifest. Deferred indefinitely.
- **WARN (not MISSING) for uninstalled packs** — skill packs are optional; absence is notable but not blocking. Matches the pattern for `check_slash_commands`.
- **Injected `receipts_dir`** — both `install_pack` and `uninstall` accept `receipts_dir` as an optional parameter for testability; defaults to the standard path.

**New/modified files at implementation time:**
- `src/squadron/skills/models.py` — add `InstallReceipt` model
- `src/squadron/skills/installer.py` — write receipt after successful install
- `src/squadron/cli/commands/skills.py` — add `uninstall` subcommand
- `src/squadron/cli/commands/doctor_checks.py` — add `SECTION_SKILLS`, `check_skill_packs()`
- `src/squadron/cli/commands/doctor.py` — add `SECTION_SKILLS` to `_SECTION_ORDER`
- New tests in `tests/skills/` and `tests/cli/`

**State:** Slice 343 is ready for Phase 5 (task breakdown) and Phase 6 (implementation). No open design questions.

---

### Initiative 340 — Slice 342 (Analysis Pack Bundled): Complete

**Completed:** Phase 6 implementation of slice 342. Analysis pack is now shipped with squadron and installable in one command with no network access.

**Key changes:**
- `src/squadron/data/skills.toml` — shipped default manifest; declares the `analysis` pack with `source="bundled"`
- `src/squadron/skills/manifest.py` — `load_effective()` now loads the shipped default as a base layer (lowest priority); `SHIPPED_DEFAULT_ORIGIN = "default"` constant added; `_load_shipped_default()` helper added
- `src/squadron/skills/resolver.py` — `_resolve_bundled()` gains a dev-mode fallback: walks up from `src/squadron/` to find the project-root `commands/` directory, enabling `sq skills install analysis` in editable installs (wheel installs use `importlib.resources` directly)
- `commands/analysis/tech-debt-audit.md` — analysis skill file (previously created on planning branch)
- `commands/sq/analysis.md` — dispatcher: `/sq:analysis tech-debt-audit` routes to the tech-debt-audit skill
- Tests: `TestLoadEffectiveWithDefault` in `test_manifest.py`, `TestBundledAnalysisPack` in `test_installer.py`, updated `TestListNoManifest` in `test_cli_skills.py` (44 skills tests, all passing)

**Notable implementation decision:** The `force-include` rule maps `commands/` into the wheel as `squadron/commands/`, but editable installs expose `src/squadron/` with no `commands/` subdirectory. Added a dev fallback in `_resolve_bundled()` to resolve via the project root. This is correct behavior: the fallback only fires when `importlib.resources` doesn't find `squadron/commands/<pack>`, which only happens in editable installs.

**Artifacts updated:**
- `user/slices/342-slice.analysis-pack-bundled.md` — Verification Walkthrough updated with actual output and dev-mode caveat; status: complete
- `user/tasks/342-tasks.analysis-pack-bundled.md` — all tasks checked, status: complete
- `user/architecture/340-slices.skill-pack-infrastructure.md` — slice 342 entry checked `[x]`
- `CHANGELOG.md` — added analysis pack, `/sq:analysis` dispatcher, and shipped default manifest entries

**State:** Branch `342-slice.analysis-pack-bundled` is 3 commits ahead of `340-planning.skill-pack-infrastructure`. Ready for merge.

**Next step:** Merge `342-slice.analysis-pack-bundled` to main; then begin slice 343 (`sq skills uninstall` and `sq doctor` integration).

---

## 20260625

### Slice 342: Analysis Pack (Bundled) — Task Breakdown Complete

Authored `342-tasks.analysis-pack-bundled.md` (12 tasks, 122 lines).

Task sequence: branch/prereq check → data package + skills.toml → extend `load_effective()` → tests → commands/analysis/ + commands/sq/analysis.md → commit checkpoint → two CLI smoke tests → integration test → full validation → final commit.

**Pending unblock:** `tech-debt-analyze.md` skill content needed from Project Manager (T5); placeholder acceptable to unblock T6–T12.

---

### Slice 342: Analysis Pack (Bundled) — Design Complete

Authored `342-slice.analysis-pack-bundled.md`.

**Key decisions:**
- Shipped default `skills.toml` at `src/squadron/data/skills.toml` acts as base layer in `load_effective()` — users see the `analysis` pack in `sq skills list` with no manual manifest setup.
- `commands/analysis/` covered automatically by the existing `force-include` wheel rule; no `pyproject.toml` changes needed for commands.
- `src/squadron/data/` package added via `__init__.py` for `importlib.resources` resolution.
- `commands/sq/analysis.md` dispatcher wired into the existing `sq install-commands` path (not `sq skills install`) for `/sq:analysis <skill>` dispatch.
- `tech-debt-analyze.md` content is an external input (existing forked skill); placeholder acceptable to unblock packaging.

**Only code change:** `manifest.py`'s `load_effective()` gains a base-layer step to load the shipped default. Everything else is new files.

**Pending:** Project Manager to supply or confirm `tech-debt-analyze.md` skill content before implementation begins.

---

### Slice 341: Manifest Format and `sq skills install/list` — Implementation Complete

All 14 tasks implemented on branch `341-slice.manifest-format-and-sq-skills-install-list`.

**What was built:**
- `squadron/skills/models.py` — `PackEntry` (Pydantic, validates exactly-one-surface), `InstallResult` (dataclass), `SkillSourceError`
- `squadron/skills/manifest.py` — `load()`, `merge()`, `load_effective()`; `ValidationError` from malformed pack entries is caught and re-raised as `ValueError` with path context
- `squadron/skills/resolver.py` — `resolve_source()`: bundled (importlib.resources), absolute/relative path, `github:` (shallow clone via subprocess+git)
- `squadron/skills/installer.py` — `install_pack()`: copies `.md` files to `commands_dir/<prefix>/` or `commands_dir/sq/<dispatch_file>.md`
- `cli/commands/skills.py` — `skills_app` Typer sub-app with `install` and `list` commands; Rich table for list; catches `SkillSourceError` and `ValueError` at CLI boundary
- `app.py` — wired `skills_app` via `add_typer`

**Tests:** 35 tests in `tests/skills/` (models, manifest, resolver, installer, CLI). All pass. 1 network-gated test (GitHub clone) skipped by default.

**One design correction during implementation:** `_USER_MANIFEST` and `_PROJECT_MANIFEST_NAME` renamed to public `USER_MANIFEST` / `PROJECT_MANIFEST_NAME` (pyright strict rejects cross-module use of private names).

**Commits:** `cdeb3a1` (subpackage foundation) + `b60ecd5` (installer, CLI, wiring).

---

### Slice 341: Manifest Format and `sq skills install/list` — Task Breakdown Complete

Authored `341-tasks.manifest-format-and-sq-skills-install-list.md` (14 tasks, 130 lines).

**Task sequence summary:**
- T1–T2: `skills/models.py` (`PackEntry`, `InstallResult`, `SkillSourceError`) + tests
- T3–T4: `skills/manifest.py` (`load`, `merge`, `load_effective`) + tests
- T5–T6: `skills/resolver.py` (bundled / local / github source resolution) + tests
- T7: Commit checkpoint — subpackage foundation
- T8–T9: `skills/installer.py` (file-copy install for prefix and dispatch_file) + tests
- T10–T11: `cli/commands/skills.py` (Typer `install`/`list` sub-app) + wire into `app.py`
- T12: CLI integration tests via Typer CliRunner
- T13–T14: Full validation pass + final commit

**Pending:** PM approval, then Phase 6 implementation.

### Slice 341: Manifest Format and `sq skills install/list` — Design Complete

Authored `341-slice.manifest-format-and-sq-skills-install-list.md`. Slice plan entry updated with materialized index and doc link.

**Design decisions committed:**

- **Manifest location:** User-level at `~/.config/squadron/skills.toml`; project-level at `<cwd>/.squadron/skills.toml`. Merge rule: additive union — project-level entries extend user-level; same-named pack in project-level wins.
- **Schema:** Each pack entry has `source` (one of `"bundled"`, absolute/relative path, `"github:<org>/<repo>"`) and exactly one of `prefix` or `dispatch_file`. Both or neither is a validation error at load time.
- **Source resolution:** `"bundled"` → `importlib.resources` (same pattern as `_get_commands_source()`); local path → direct; `github:` → shallow `git clone --depth=1` to temp dir, copy `.md` files, discard. No version pinning in v1.
- **Install semantics:** Additive within a pack's prefix directory (no deletion of pre-existing files not from the pack — that is `uninstall`'s job). Idempotent: second install overwrites files, reports success, no error.
- **No manifest auto-creation:** Missing `skills.toml` produces an actionable message; we do not silently create a default file.
- **Component structure:** New `squadron/skills/` subpackage (`manifest.py`, `resolver.py`, `installer.py`, `models.py`) with thin Typer layer at `cli/commands/skills.py`. `skills_app` added to `app.py` via `add_typer`.
- **Pydantic for manifest model**; `tomllib` (stdlib) for parsing; `subprocess` + `git` for GitHub fetch; no new third-party dependencies.

**Pending:** Phase 5 task breakdown, then Phase 6 implementation.

---

### Initiative 340 — Slice 340 (Command Surface Spike): Complete

**Completed:** Phase 6 implementation of the command surface spike.

**Decision:** Dispatch model is reliable. All four test cases passed — routing fired correctly, `<skill-args>` arrived intact, listing rendered cleanly, unknown-skill error was clear. Verdict: dispatch reliable.

**Artifacts updated:**
- `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md` — Spike Results filled, status: complete
- `user/architecture/340-arch.skill-pack-infrastructure.md` — "Open dispatch question" principle and technical consideration updated to reflect adopted dispatch model
- `user/architecture/340-slices.skill-pack-infrastructure.md` — Slice 340 checked off

**Next step:** Slice 341 slice design — manifest format + `sq skills install/list` (supports both `dispatch_file` and `prefix` options per the spike outcome).

---

### Initiative 340 — Slice 340 (Command Surface Spike): Phase 5 Task Breakdown Complete

**Completed:** Task breakdown for the spike slice.

**Shipped:** `user/tasks/340-tasks.command-surface-spike-dispatch-vs-prefix.md` — 8 tasks, 105 lines.

**Task summary:** T1–T2 create the dispatcher and two stub files; T3 installs them; T4 runs the four prescribed test invocations; T5 records the decision in the slice design; T6 updates the arch doc; T7 removes spike files and re-syncs; T8 marks complete and commits.

**Next step:** Phase 6 implementation — run the spike (T1–T8 above).

---

### Initiative 340 — Slice 340 (Command Surface Spike): Phase 4 Slice Design Complete

**Completed:** Slice design written for the command surface spike.

**Shipped:** `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md`

**Design summary:** A time-boxed spike. Builds a minimal dispatcher markdown file (`analysis.md`) and two stub skill files, installs them via the existing `sq install-commands` path, and runs four test invocations to determine whether Claude Code reliably passes arguments through a dispatch file. Records findings in a `## Spike Results` section appended to the slice design doc. Updates `340-arch` with the closed decision. Stub files are removed after the decision is recorded. The spike has no persistent code deliverable — its output is a decision and an arch doc update that unblocks slice 341.

**Next step:** Run the spike (Phase 6 implementation is just running four commands and recording observations), then move to slice 341 slice design.

---

### Initiative 340 — Skill Pack Infrastructure: Slice Plan Complete

**Completed:** Slice plan written at `user/architecture/340-slices.skill-pack-infrastructure.md`. Four slices across Foundation, Feature, and Integration sections.

**Slice summary:**
- **(340) Command Surface Spike** — Closes the dispatch-vs-prefix open question empirically. Time-boxed; outcome updates the arch doc. Effort 1/5.
- **(341) Manifest Format + `sq skills install/list`** — Core mechanism: `skills.toml` schema, source resolution (bundled/local/git), file-copy installer. Effort 3/5.
- **(342) Analysis Pack (Bundled)** — Ships `tech-debt-analyze` (and others) as `commands/analysis/` in the wheel; one-command install via `sq skills install analysis`. Effort 2/5.
- **(343) `sq skills uninstall` + `sq doctor` integration** — Completes the CLI surface; `sq doctor` gains a Skill Packs section. Effort 1/5.

**Next step:** Spike slice 340 when ready to begin implementation.

---

### Initiative 340 — Skill Pack Infrastructure: Architecture Complete

**Completed:** Initiative 340 added to the initiative plan and architecture document written.

**Context:** Squadron's growing use for analysis of existing codebases surfaced a gap — useful external skills (tech-debt-analyze, understand-anything, etc.) have no principled install path alongside first-party commands. This initiative adds a thin, opt-in skill pack mechanism: a TOML manifest + `sq skills install/list` that copies external skill markdown files into `~/.claude/commands/<prefix>/`, exactly mirroring the existing `install-commands` pattern.

**Key decisions captured in arch:**
- Prefix-per-pack model (`/analysis:tech-debt`) keeps `/sq:*` clean; open question is whether a dispatch router (`/sq:analysis <skill>`) is a viable UX alternative — resolved by a planned spike slice.
- File copy is the delivery primitive; no runtime indirection, no loader, no daemon involvement.
- Analysis pack ships bundled in the wheel (parallel to `commands/sq/`); external sources (local path, git ref) supported by manifest format.
- Squadron owns the analysis pack; third-party packs are supported by format but not hosted.

**Shipped:** `user/architecture/340-arch.skill-pack-infrastructure.md`, initiative entry in `001-initiative-plan.squadron.md` (index 340, cross-dep entry added).

**Next step:** Slice plan (`340-slices.skill-pack-infrastructure.md`) with spike slice as first entry.

---

## 20260617

### Slice 301: Judge Enforcement Layer — Design Complete

Authored `301-slice.judge-enforcement-layer.md`. No commits (design-only phase).

**Design decisions committed:**
- Judge templates identified by presence of a `judge:` YAML block (not naming convention — project rule forbids string dispatch). Block carries default `pass_floor`/`concerns_floor` thresholds.
- `ReviewTemplate.judge: dict[str, object] | None` + `is_judge` property; `JudgeThresholds` and enforcement logic live in a new `pipeline/actions/judge.py`, keeping the template model a thin data carrier.
- `enforce_judge()` is a pure function (logger injected); independently testable without action context.
- Provenance set for ALL results from this slice forward: `"judge"` for judge templates, `"review"` for standard templates — completing the self-describing guarantee from 300.
- Exception path (provider down, missing inputs) for judge templates returns `verdict="UNKNOWN"` rather than `verdict=None`, so checkpoints fire correctly.
- Conservative defaults: `pass_floor=75`, `concerns_floor=50` (constants in `judge.py`).
- Step-level override via `judge: {pass_floor: N}` in pipeline YAML; passed through from `ReviewStepType.expand()` to action params.

**Pending:** PM review of design before task breakdown (Phase 5).

---

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 6 Implementation Complete

**Completed:** Phase 6 implementation of the keystone slice 300. All 13 tasks (T1→T13) implemented, tested, and committed one-per-task on branch `300-slice.numeric-scoring-foundation`. The slice is the additive, judging-free foundation every later 300 slice composes on.

**Shipped (six source modules, additive only):**
- `review/models.py` — `ReviewResult.score` / `.criteria` / `.provenance` (all `float|dict|str | None`, default `None`); `to_dict()` emits the three keys.
- `pipeline/models.py` — `ActionResult.score` / `.criteria` / `.provenance`, mirroring `verdict`; picked up automatically by `dataclasses.asdict`.
- `review/parsers.py` — new `_extract_score` / `_extract_criteria` helpers + a shared `_parse_finite_float`; wired into `parse_review_output`. Lenient and judging-unaware: absent/malformed → `None`, never raises, never range-checks, first `score:` wins, `inf`/`nan` rejected as non-finite. Criteria parsed from the indented YAML-map block, whole-map-to-`None` on any malformed entry.
- `pipeline/actions/review.py` — threads `result.score` / `.criteria` into the returned `ActionResult` (`provenance` left `None`).
- `review/persistence.py` — `format_review_markdown` emits a top-level `score:` line and a `criteria:` block when present; score-less output is byte-for-byte unchanged.
- `pipeline/state.py` — `StepState.score` + a score hoist in `_append_step` mirroring the verdict hoist.

**Tests:** new coverage in `tests/review/test_models.py`, `tests/review/test_parsers.py` (incl. the full failure-mode table + real score-less / score-bearing / criteria-bearing fixtures), `tests/review/test_persistence.py`, `tests/pipeline/test_models.py`, `tests/pipeline/test_state.py` (incl. backward-compat: old run-state JSON without `score` loads), `tests/pipeline/actions/test_review_action.py`. Full suite: **1969 passed, 2 skipped**; `pyright` 0 errors; `ruff check` + `ruff format --check` clean.

**Notable during implementation:**
- One real bug found and fixed in `_extract_criteria`: the `$`-in-MULTILINE label match left the slice starting at the trailing newline, so `splitlines()[0]` was empty and the block ended immediately — fixed by lstripping the leading newline. Caught by an inline probe before the test task.
- No-judging-logic-leak gate (T13): grepped the slice diff — `provenance` appears only as field declarations, comments, and the `to_dict()` serialization key; zero range checks, zero verdict-from-score derivation. Confirmed clean.
- Verification Walkthrough updated with actual commands/output; interactive steps 4–5 replaced with equivalent non-interactive probes (plus a caveat) so an external agent can run them verbatim.

**Process:** `cf:check` (workflow_check) slice 300 — clean after auto-fixing the slice-plan checkbox; slice design + task frontmatter set to `status: complete` / `dateUpdated: 20260617`; CHANGELOG `[Unreleased]` updated.

**Next step:** Phase 4 design for slice 301 (Judge Enforcement Layer) — populates `provenance`, validates the score, derives the verdict by thresholding. No model re-open needed (the shape is settled here).

---

## 20260607

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 5 Task Breakdown Complete

**Completed:** Phase 5 task breakdown for the keystone slice 300. Task file created from the (review-revised) slice design.

**Shipped:** `project-documents/user/tasks/300-tasks.numeric-scoring-foundation.md` — 13 tasks, ~225 lines (well under the 450 cap, single file). Test-with ordering: each implementation task (T1/T3/T5/T7/T9/T11) is immediately followed by its test task (T2/T4/T6/T8/T10/T12); T13 is the full-suite + static-analysis + no-judging-logic-leaked validation pass. One commit per task. Closes with a coverage table mapping every LLD change to its task(s).

**Decisions/notes:**
- Tasks made authoritative on the **full three-field set** (`score`/`criteria`/`provenance`) on both `ReviewResult` and `ActionResult` — the LLD's component-summary table lagged on `provenance` in two rows, but the LLD body is explicit, so tasks follow the body. Provenance is field-only (T1/T3 add it; T13 verifies nothing populates/reads it).
- Verified all referenced test-file paths against the real tree; corrected `test_review.py` → `tests/pipeline/actions/test_review_action.py` (the others — review test_models/test_parsers/test_persistence, pipeline test_models/test_state — all exist).
- Parser failure-mode table (non-numeric/inf/nan/multi-line/malformed-criteria → `None`, no raise) is its own dedicated test task (T6).
- `cf:check` for slice 300: clean (the prior "design but no task file" info is resolved).

**Task review (glm-5.1, verdict PASS):** coverage/sequencing/test-with/sizing/commits/failure-mode-coverage all PASS. One CONCERN (F003): `_extract_criteria`'s recognized text format was underspecified — `score:` was pinned but `criteria:` was not, leaving T5/T6 without a positive-fixture anchor. **Fixed** in both LLD and task file: pinned `criteria` to the minimal YAML-map shape (top-level `criteria:` + indented `key: <number>` lines — the same idiom T9 emits), whole-map-to-`None` on any malformed value; added a criteria-bearing fixture to T6. Also fixed the LLD component-table + data-flow-diagram lag on `provenance` (body was already explicit).

**Next step:** Phase 6 implementation of slice 300, following T1→T13. After 300 lands, Phase 4 design for slice 301 (Judge Enforcement Layer).

---

## 20260605

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 4 Slice Design Complete

**Completed:** Phase 4 low-level design for the keystone slice 300, the numeric-scoring foundation. Design grounded in the actual code (read `review/models.py`, `pipeline/models.py`, `review/parsers.py`, `pipeline/actions/review.py`, `review/persistence.py`, `pipeline/state.py`).

**Shipped:** `project-documents/user/slices/300-slice.numeric-scoring-foundation.md` — additive `score: float | None` + reserved `criteria: dict[str,float] | None` on `ReviewResult` and `ActionResult`; lenient, judging-unaware optional extraction in `parse_review_output`; threading through the review action's `ReviewResult → ActionResult` map; persistence on two surfaces.

**Key design decisions:**
- **"Queryable, first-class, not opaque" resolved against real code:** squadron has no SQL DB. The two queryable surfaces are (a) review-file YAML frontmatter — `score:` as a top-level key beside `verdict:`; and (b) run-state JSON — a new top-level `StepState.score` hoisted in `_append_step` from the last non-`None` action score, exactly mirroring the existing `verdict` hoist (state.py:267–286). Resolves the open question "storage representation for the queryable score."
- **Field type `float | None`** (not int, not a sentinel): float holds integer scores and future multi-sample medians; `None` is the only "absent" representation — no `0`/`-1` fallback (project no-silent-fallback rule, and a correctness prerequisite for 301's required-ness check).
- **Parser stays lenient and judging-unaware:** extracts when present, silent on absence, **no validation/range-check/thresholding.** Out-of-range values (e.g. `150`) are extracted as-is; validation → `UNKNOWN` is 301's job at the judge use. This is the parser side of the architecture's two-layer split.
- **Real-fixture tests on both paths** (score-less regression fixture + score-bearing fixture in the judge-template shape) per the project "test the parser on real input" rule.

**Scope boundary held:** no judging *logic* in this slice — required-ness, validation, thresholding, and verdict derivation are all 301.

**Design review (glm-5.1, verdict CONCERNS) — both concerns addressed:**
- **F001 (provenance):** the architecture commits the provenance field to the *result model*, and 300 is the keystone "settle the model shape once" slice — so deferring provenance entirely to 301 would force 301 to re-open the models. **Fix:** add `provenance: str | None = None` as a *latent reserved field* in 300 (mirrors how `criteria` is reserved), unpopulated/unread here; 301 supplies only its meaning and use. No model re-open downstream.
- **F002 (parser failure modes):** added an explicit failure-mode enumeration table for the new score/criteria extraction path (non-numeric value → `None`; `inf`/`nan` → `None`; multiple score lines → first wins; malformed criteria → whole map `None`) — never raises, never fabricates a number. Observable-WARNING-on-required-absence stays 301's job (firing it in the parser would trigger on every ordinary score-less review). Satisfies the project Failure-Mode Enumeration rule.
- F003 (note): structured-output parser shape correctly deferred to 302 — no change.

**Next step:** Phase 5 task breakdown for slice 300, then Phase 6 implementation. After 300 lands, Phase 4 design for slice 301 (Judge Enforcement Layer).

---

## 20260604

### Initiative 300 (Intrinsic LLM Judging & Scoring): Phase 3 Slice Planning Complete

**Completed:** Phase 3 slice planning for initiative 300. Slice plan created from the reviewed architecture document; architecture marked `complete`.

**Shipped:**
- `project-documents/user/architecture/300-slices.eval-actions-llm-as-judge-scoring.md`: five slices in dependency/implementation order — (300) Numeric Scoring Foundation [keystone, foundation, done alone], (301) Judge Enforcement Layer, (302) Design-Phase Judge Templates, (303) Judge-Gated Cycle Conventions, (304) Gate Composition [integration]. Plus a Future Work backlog: multi-sample judging, on-demand ground-truth fetching, checkpoint multi-verdict support (140).
- `300-arch.eval-actions-llm-as-judge-scoring.md`: status `reviewed` → `complete`, dateUpdated 20260604.

**Key planning decisions:**
- Keystone (300) ordered first and done alone, per the architecture — the only Medium-risk cross-cutting model/parser/persistence change; everything composes on it.
- Refined the architecture's four anticipated slices into five by splitting the judge **enforcement layer** (301: required-ness, 0–100 validation, score→verdict thresholding, provenance) from the judge **templates** (302). The two-layer parser/action split is an explicit architectural commitment, the enforcement is independently testable, and no template is gateable until it exists.
- Every slice is additive and leaves the system in a working state; existing verdict-gating pipelines unchanged throughout.
- Gate composition (304) carries the architecture's explicit boundary: prefer upstream reduction (additive, in-scope 300); if insufficient, escalate checkpoint multi-verdict support as a coordinated 140 dependency, not a silent absorption.

**Open questions deferred to slice design (Phase 4):** provenance field name/enum, threshold band values + config keys, queryable-score storage representation, which design-phase judge templates to author first.

**Next step:** Phase 4 slice design for slice 300 (numeric scoring foundation), the keystone.

---

## 20260531

### Initiative 300 scope reduction + Initiative 320 + orchestrator Future Work — Design

Major rethink after a review (GLM-5.1, CONCERNS) and an extended PM/architect design conversation. The 300 arch doc had spiraled toward over-engineering; pulled it back to what's actually needed, and split the rest into a sibling initiative and a far-future Future Work entry.

**The "why" (captured for future context — this is the motivation behind 300/320 and the orchestrator):**
Squadron is an excellent *deterministic workflow engine* running a *non-deterministic process*. High accuracy, decent-but-variable code quality, and an external quality standard now exists to measure against (a forked MIT `tech-debt-audit` Claude skill, adapted for squadron projects, which surfaces plenty of issues). In return for high accuracy it demands human-in-loop at too many gates — rarely at code, sometimes extensively at *design* — heavy enough that simple projects aren't worth the overhead. The automation breaks precisely at the **decision points**, because those are non-deterministic. LLM judgment at those points is the missing piece. (Origin: the CCA training + two interviews surfaced the eval gap; adding it makes squadron feel "complete"/legit — a workflow engine without eval is a car without a speedometer.)

**Determinism/leverage ladder (the framing that resolved where agentic loops belong):**
1. Now — high-accuracy, high-effort workflow engine (human at every gate).
2. 300/320 — judge-at-decision-points; trade some accuracy for far less effort; variability accepted but kept minimal.
3. Future — an orchestrator agent driving CF+squadron, human consulted only on hard calls; another leverage jump.
Organism metaphor: CF structures = stable skeleton; LLM judges/orchestrator = nervous system (joints absorbing variability, making local decisions); human = consulted only where it matters. **Agentic loops belong ONLY at rung 3, above the engine — never inside a pipeline action.** The doc kept spiraling because it tried to put a rung-3 turn-loop inside a rung-2 action (the read-file capability). Removing that dissolved the circularity.

**Initiative 300 — reduced and renamed → "Intrinsic LLM Judging & Scoring".**
Now two reuse-first capabilities only: (1) an optional 0–100 numeric **score** added additively to result models/parser/persistence (keystone slice, done first), verdict *derived from* score by threshold (score = source of truth, verdict = its projection for `--step-done --verdict`), optional `criteria` map reserved from the start; (2) an **intrinsic judge** = the *existing* `review` action with a judge system-prompt emitting score+findings, composing with *existing* `each`/`loop`/`commit` for unattended review→fix→re-review. Ground truth is **in-repo** (parent doc, rules, code, phase criteria) — no external answer key. Prioritize design-phase gates (slice-vs-arch, tasks-vs-slice). **Dropped from 300:** the `eval:judge` action (duplicative of `review`), reference datasets, per-case dataset loop, read-file/turn-loop, fan-in aggregation. Arch doc fully rewritten; `status: not_started` (needs fresh review against reduced scope). Second-review findings re-dispositioned: F001/F002/F006/F007 fixed & carried forward, F003/F004/F005 removed from scope, F008 retained as a slice-design caveat.

**Reference datasets — ruled out (not deferred scope, a different product).** Curated input/expected pairs to grade a model in the abstract. Poor fit here: prompts are complex, outputs non-deterministic (valid solutions vary), and ground-truth strength is a *gradient* — strong for tasks-vs-slice, minimal for arch-concept-vs-initiative-blurb. Squadron's judging needs none of it; its ground truth is the project's own documents.

**Initiative 320 (new) — "Judge Calibration & Quality Metrology".** Answers "how good are the judges themselves?" Ground truth = **the human, sampled**: operator spot-checks a sample of judge verdicts; system reports judge-vs-human agreement + judge-vs-judge dispersion ("does model X overreach while Y rubber-stamps?"). Trust is per-artifact-level (scales with in-repo ground-truth strength) and feeds 300's escalate-vs-auto-gate decision. Includes the **tech-debt-audit code-quality baseline** + a dispatch-side **prompt-chaining pre-emption** prompt (chained because the current one is already complex) as the first measurable customer (audit-findings-per-project should drop). Two oracles, same metrology shape: tech-debt-audit (code), human-sampled agreement (design). Depends on [100, 140, 300]. Overview/rough-concept captured in the initiative-plan entry; full design in coming weeks.

**Orchestrator — Future Work entry.** The rung-3 organism; named to keep its agentic loop from being smuggled back into 300-band components. Promote to a full initiative when pursued.

**Index spacing:** initiatives now spaced by 20 (300, 320). 310 intentionally skipped.

**Delivered:** rewrote `300-arch.eval-actions-llm-as-judge-scoring.md`; updated `001-initiative-plan.squadron.md` (300 entry slimmed, 320 added, Future Work section added, cross-deps + dateUpdated); re-dispositioned `300-review.arch...md`.

**Pending:** fresh review of slimmed 300; `/cf:prompt get add-initiative-overview` already applied to capture 320 as a plan entry — a standalone 320 concept doc was not created (project has no concept-doc convention; the plan entry + this DEVLOG are the durable capture). All planning edits remain uncommitted on branch `908-sq-setup-one-call-install-orchestrator`.

---

## 20260530

### Initiative 300: Eval Actions (LLM-as-Judge & Scoring) — Design Complete

Stood up a new initiative and authored its architecture document. Adds an `eval` action family that gives squadron's deterministic executor a judgment-and-measurement layer.

**Delivered:**
- Initiative 300 entry added to `001-initiative-plan.squadron.md` (index 300, after 280; dependencies [100, 140]); cross-initiative dependency entry and `dateUpdated` refreshed.
- `300-arch.eval-actions-llm-as-judge-scoring.md` created and registered (`cf set arch 300`).

**Component shape.** `eval:judge` is LLM-as-judge: reuses the existing provider-agnostic review engine (`run_review_with_profile`) with a judge system-prompt and reference-dataset inputs, emitting a **0–100 scalar score + verdict + findings**. The verdict drops into the existing `sq run --step-done --verdict` checkpoint machinery with no new plumbing.

**Key decisions:**
- **Initiative, not a single slice** — because numeric scoring is a cross-cutting change to result models every pipeline depends on, reference-dataset eval is new infrastructure, and eval/review gate composition is an open arch question.
- **Keystone slice first:** numeric scoring foundation (add `score` *alongside* verdict, additive/backward-compatible, verdict stays authoritative at summary level). Isolated and done first to de-risk the model migration.
- **Scalar summarizes a latent criterion vector** — scalar consumed now, vector recorded but not surfaced.
- **Read-file-on-request tool** for non-SDK judges is owned by this initiative (the canonical minimal one), but is a **secondary, later slice** — explicitly *not* dependent on 260's full agentic loop (260 may consume it later).

**Grounding (verified against source this session):** action registry is open (`register_action`); `ActionResult` already carries `verdict`/`findings`; verdict enum `PASS|CONCERNS|FAIL|UNKNOWN` is exactly what `--step-done --verdict` consumes; provider/model support comes from the profile registry; the 500KB injection cap is the binding constraint on non-file-reading judge models.

**Pending / open (for slice design):** dataset format & location convention; scalar score range vs. per-criterion schema detail; eval/review gate-composition policy (combined / separate / per-review-type).

**Note:** these are planning-doc edits made on branch `908-sq-setup-one-call-install-orchestrator`; not yet committed.

---

## 20260520

### Slice 908: `sq setup` — Phase 6 Implementation Complete

**Completed:** Phase 6 implementation for slice 908. Slice is complete.

**Shipped:**
- `src/squadron/cli/commands/setup_steps.py` (~220 lines): pure conversion layer (`CheckResult → SetupStep`). `StepKind` StrEnum, `SetupStep` frozen dataclass, `_RECHECK_MAP`, `_classify`, `build_steps` with profile filtering, `_DOCS_ANCHOR`, `_EXPLANATION`, synthesised per-profile recheck lambdas.
- `src/squadron/cli/commands/setup.py` (~120 lines): Typer command with `--non-interactive`, `--check-only`, `--profile`, `--verbose` flags. Rendering functions `_render_check_only`, `_render_non_interactive`, `_run_interactive` (re-prompt cap=5, `q` exits 2).
- `src/squadron/cli/app.py`: `app.command("setup")(setup)` registration.
- `scripts/install.sh` (~100 lines): bash bootstrap with `set -euo pipefail`, interactive prompts, `uv`/`pipx` detection, `npm` detection, `--yes`/`--help` flags, `exec sq setup` handoff.
- `tests/cli/test_setup_steps.py`: 20 tests covering T3, T6, T10, T11, T12.
- `tests/cli/test_setup.py`: 10 tests covering T18a, T18b, T19, T20, T21, T22, T23, T24.
- `tests/scripts/test_install_sh.sh` + `test_install_sh.py`: idempotency smoke test (T26).
- README: "Fresh install (one liner)" section added (T27).
- CHANGELOG: `sq setup` and `scripts/install.sh` entries added.

**Deviations from design:** None. All design decisions implemented as specified.
- T28 (QUICKSTART callout) skipped — `docs/QUICKSTART.md` does not exist yet (slice 906 not merged). DEVLOG follow-up noted.
- Aggregate "at least one provider OK" suppression optimisation deferred per design decision (initial release shows all profile rows).

**Test results (final gate):**
- `pytest tests/cli/test_setup.py tests/cli/test_setup_steps.py tests/scripts/test_install_sh.py -q`: **31 passed**
- `pytest -q` (full suite): **1936 passed, 2 skipped**
- `ruff check && ruff format --check && pyright`: **all clean**

**Exit codes verified:** 0 (all OK), 1 (MISSING present), 2 (user quit), 3 (internal error), 64 (unknown profile).

**Follow-up:** When slice 906 merges and `docs/QUICKSTART.md` exists, add the `sq setup` callout under Step 5 / Troubleshooting (T28).

**Branch:** `908-sq-setup-one-call-install-orchestrator`.

---

## 20260519

### Slice 908: `sq setup` One-Call Install Orchestrator — Phase 4 Slice Design Complete

**Completed:** Phase 4 low-level design for slice 908.

**Document created:**
- `project-documents/user/slices/908-slice.sq-setup-one-call-install-orchestrator.md` — full slice design (status: `not_started`)

**Slice plan updated:** `900-slices.maintenance-and-refactoring.md` entry 7 now references the materialized design path.

**Design highlights:**
- `sq setup` is a *renderer* over slice 905's `run_all_checks()` — no new check logic. Conversion layer maps each `CheckResult` to a `SetupStep` with kind `ALREADY_DONE` / `INSTALL` / `CONFIGURE` / `OPTIONAL`.
- Three modes: interactive (default, one prompt per missing step with `enter/s/q`), `--non-interactive` (emit all steps without prompts; pipe-to-file friendly), `--check-only` (one-liner per step, exits with `sq doctor`'s code).
- `--profile <name>` filters Provider-section steps to a single profile.
- Per-step re-check via a local "check-name → function" map inside `setup_steps.py`. Degrades to "press enter when done" if 905 adds checks we haven't mapped.
- Companion `scripts/install.sh` (bash) handles only the pre-Squadron bootstrap (pipx/uv → `pipx install squadron-ai` → `npm i -g @manta-digital/context-forge` → handoff to `sq setup`). No automatic shell execution from Python.
- Distribution via GitHub raw URL: `curl -sSL <raw URL> | sh`. Pinning to a tag is a follow-up.
- Idempotency contract: setup is re-runnable, install.sh is re-runnable; both detect existing state and skip done steps.

**Cross-slice contract:**
- Strict consumer of slice 905's `CheckResult`, `CheckStatus`, `run_all_checks()`. No API changes requested upstream.
- References slice 906 (QUICKSTART) anchors for `docs_anchor`. If 906 ships later, anchors degrade gracefully to plain section names.

**Branch:** `908-sq-setup-one-call-install-orchestrator` (created from `main`).

**Next:** Phase 5 task breakdown — `task-checker`-friendly checklist derived from this design.

---

### Slice 908: `sq setup` — Phase 5 Task Breakdown Complete

**Completed:** Phase 5 task breakdown for slice 908.

**Document created:**
- `project-documents/user/tasks/908-tasks.sq-setup-one-call-install-orchestrator.md` — 32 tasks (T1–T32) across seven phases (status: `not_started`).

**Phase shape (test-with-pattern preserved throughout):**
- **A. Setup and data model** — branch confirmation, skeleton files, `StepKind` / `SetupStep` dataclass, baseline tests.
- **B. `build_steps` conversion layer (pure)** — recheck-function map, `_classify`, `build_steps`, docs-anchor map, explanation strings; each implementation immediately followed by its tests.
- **C. `setup.py` Typer command and rendering** — command skeleton with all flags, `--check-only` / `--non-interactive` / interactive renderers, registration in `cli/app.py`.
- **D. Tests for `setup.py`** — `CliRunner`-based coverage of every flag combination, profile filter, `q`-quit, recheck loop, and the internal-error fallback.
- **E. `install.sh` bootstrap** — bash script with `set -euo pipefail`, explicit prompts before each install, plus a `pytest`-wrapped idempotency smoke test using PATH-shimmed stubs.
- **F. Documentation** — README one-liner pointer; optional QUICKSTART callout gated on slice 906 merge order.
- **G. Final gate** — full `pytest` / `ruff` / `pyright` gate, verification walkthrough recording into the slice design, slice-plan checkbox flip, DEVLOG closeout.

**Notable design constraints carried into tasks:**
- No automatic shell execution from Python beyond `install_commands()` with explicit consent.
- Per-step re-check cap = 5 (prevents infinite loops in scripted stdin).
- `q` exits 2 (user-aborted), distinct from 1 (`sq doctor` reports missing) and 3 (internal error).
- `_DOCS_ANCHOR` and `_EXPLANATION` maps are local to `setup_steps.py` — no upstream API changes to slice 905.

**Review note:** Phase 4 review flagged 908 as "new feature under maintenance arch" (F001). PM decision was to leave categorisation alone — 905/906/908 form a cohesive onboarding trio that has historically lived under the 900 maintenance architecture. No design changes resulted.

**Task file size:** 259 lines (well under 450-line target; no split needed).

**Branch:** `908-sq-setup-one-call-install-orchestrator`.

**Next:** Phase 6 implementation following T1–T32 in order.

---

## 20260518

### Slice 907: Optional Dependency Split — Task Breakdown Complete

**Completed:** Phase 5 task breakdown. Task file created at `user/tasks/907-tasks.optional-dependency-split-serve-and-codex-extras.md` (173 lines, 8 task groups, 31 checklist items).

**Task structure:**
- T1: Branch setup
- T2: `pyproject.toml` — remove fastapi/uvicorn from deps, add `[serve]` and `[codex]` extras
- T3: Extract `src/squadron/server/pid.py` (DaemonConfig + PID helpers); update `daemon.py` to import from it; update `tests/server/test_daemon.py`
- T4: Update `serve.py` — top-level imports switch to `pid.py`; `start_server`/`SquadronEngine` deferred into `_start_daemon()` after import guard
- T5: Codex binary guard in `provider.py` — `create_agent()` raises `ProviderError` (not `ProviderAuthError`) when binary absent
- T6: Full test suite + static analysis (ruff, pyright, pytest)
- T7: Clean-venv verification walkthrough
- T8: Commit

**Status:** Ready for Phase 6 (Implementation).

---

## 20260514

### Initiative 200: Multi-Agent Communication — Architecture Rewrite

Rewrote `200-arch.multi-agent-communication.md` and `200-slices.multi-agent-communication.md` to reflect a fundamentally different model from the original pub/sub message bus design.

**Why:** IDE plugins (Claude Code, Codex) and interactive sessions are reactive — they cannot receive async push. The original bus model assumed agents could be woken up; they can't. The new model is pull-based: a shared SQLite task store owned by the daemon, agents poll for work, claim atomically, complete via daemon socket.

**New model summary:**
- Daemon (`sq serve`) owns `workspace.db` (SQLite, WAL mode), listens on Unix socket
- `sq run` posts tasks via socket, polls DB read-only for results — no more SDK session spawning from CLI
- Claude Code IDE participates via `/sq:work` slash command + MCP tools
- Codex IDE plugin: same poll/claim/complete loop, capability-routed
- Hermes (remote machine): connects to local daemon via SSH tunnel, same socket protocol
- Project isolation via `project_path` column — one daemon, one DB, multiple projects

**Dropped from original 200-series:** Supervisor (OTP restart patterns), Message Bus Core, Multi-Agent Message Routing, Human-in-the-Loop as bus participant, Communication Topologies, ADK Integration, REST+WebSocket, Subprocess Agent Support.

**Retained/adapted:** 203 (Anthropic API Provider, standalone, unchanged), 208→224 (MCP tools, repurposed for poll/claim), 210 (Ensemble Review, unchanged), 212→228 (E2E testing, rescoped).

**New slices:** 221 (Task Store schema), 222 (Daemon Socket Server), 223 (Pipeline Executor Integration), 224 (MCP Tools), 225 (/sq:work slash command), 226 (Capability Routing), 227 (sq work Hermes worker CLI).

**June 15 relevance noted:** Slices 203 + 223 together eliminate the Agent SDK credit dependency for `sq run` pipeline steps. Prioritized in implementation order notes.

### Slice 907: Optional Dependency Split — Design Complete

**Completed:**
- Created `user/slices/907-slice.optional-dependency-split-serve-and-codex-extras.md`

**Key Design Decisions:**
- `fastapi` and `uvicorn` move from `[project.dependencies]` to a new `[serve]` optional extra.
- `[codex]` extra is declared empty (PyPI rejects direct URL refs); a comment block carries the GitHub install command.
- `sq serve` start guard lives inside `_start_daemon()` — `--status` and `--stop` remain usable without `[serve]`.
- `start_server` and `SquadronEngine` imports deferred into `_start_daemon` after the guard; `DaemonConfig`/PID helpers stay top-level (verify they don't transitively pull fastapi; extract to `server/pid.py` if they do).
- `CodexProvider.create_agent()` gains an early binary check (`resolve_codex_binary is None` → `ProviderAuthError` with `npm i -g @openai/codex`). SDK import guard already present in `_run_prompt`; no change needed there.

**Status:**
- Design ready for Phase 5 (Task Breakdown).

---

## 20260513

### Slice 906: Quickstart and Onboarding Documentation — Phase 4 Slice Design

Authored `user/slices/906-slice.quickstart-and-onboarding-documentation.md`.

Scope: docs-only. Two deliverables — new `docs/QUICKSTART.md` (step-by-step from
zero to working `sq run`) and targeted README edits (Quickstart → pointer, Install →
keep global-install block only).

Key design decisions:
- QUICKSTART is structured as numbered install steps matching the `sq doctor` fix-hint
  contract: every hint emitted by doctor maps to a named QUICKSTART section. This
  mapping is documented in the slice design as a stable interface.
- Provider matrix table derived from `BUILT_IN_PROFILES` — covers sdk, openai,
  openrouter, gemini, local, openai-oauth (experimental), and Anthropic API (planned,
  slice 203).
- README Quickstart section replaced with ~3 lines + link; dev-install block moves
  to QUICKSTART under a contributing subsection.
- No code changes. Effort 1/5.

### Slice 905: `sq doctor` — Phase 6 Implementation Complete

Completed full implementation of `sq doctor` in a single session across 35 tasks.

Two new files: `src/squadron/cli/commands/doctor_checks.py` (~280 lines, pure check
functions + `run_all_checks()`) and `src/squadron/cli/commands/doctor.py` (~120 lines,
Typer command + Rich/JSON rendering). One edit to `cli/app.py` to register the command.

Key implementation decisions:
- Module-level imports for `get_all_profiles`, `providers_toml_path`, `models_toml_path`
  (not lazy inside functions) — required for test patching to work correctly.
- `Console(soft_wrap=True)` for path-heavy detail strings that exceed terminal width.
- `_API_KEY_ONLY_PROFILES` fixture in integration tests because `sdk`, `local`,
  `openai-oauth` profiles return `is_valid()=True` unconditionally — a fresh-system
  env var wipe doesn't actually leave zero valid providers. The fixture simulates
  a minimal env with only API-key-based profiles for the "fresh-system → exit 1" scenario.
- Scenario 3 (broken providers.toml) produces two error signals: `get_all_profiles()` 
  raises before per-profile checks run (process-boundary handler emits WARN), then 
  `check_providers_toml()` independently emits the MISSING row. Both correct; both informative.

Tests: 35 doctor tests added; full suite 1904 passing, 2 skipped (pre-existing). Ruff/pyright clean.

Branch: `905-sq-doctor-environment-diagnostic-command`. Not yet merged.

### Slice 905: `sq doctor` — Phase 5 Task Breakdown

Authored `user/tasks/905-tasks.sq-doctor-environment-diagnostic-command.md`
(35 tasks across four phases: setup/data-model, individual checks,
orchestration/rendering, final integration).

Test-with pattern applied throughout — every implementation task is
immediately followed by its test task (T4→T5, T6→T7, T8→T9, etc.), no
batched test phase. Each check function gets its own implementation +
test pair so failures surface against a small surface area.

Phase A (T1–T3) bootstraps the branch, skeleton files, and the
`CheckResult`/`CheckStatus` data model. Phase B (T4–T23) implements the
10 individual check functions. Phase C (T24–T30) wires orchestration,
Rich + JSON rendering, the Typer command, and 6 CliRunner integration
tests. Phase D (T31–T35) is the gate (pytest/ruff/pyright), manual
scenario verification mirroring 904's recorded-outcomes pattern,
CHANGELOG, commit, and slice closure.

Notable choices:

- Provider profile tests use real `monkeypatch.setenv` against the real
  auth registry — not mocked `resolve_auth_strategy_for_profile`. We're
  testing integration with the actual auth strategies, not a fake.
- TOML config checks distinguish absent (informational OK) from
  malformed (MISSING). Repairing the file is the fix hint.
- Process-boundary catch in `run_all_checks()` wraps each check call;
  one broken check emits a synthetic WARN row instead of aborting.
- Top-level command body raises `typer.Exit(exit_code)`. Exit 1 iff any
  MISSING row exists; WARN never affects exit code.

Status: not_started · 35 tasks · 219 lines.

---

### Slice 905: `sq doctor` Environment Diagnostic — Phase 4 Slice Design

Authored `user/slices/905-slice.sq-doctor-environment-diagnostic-command.md`.
Design covers a read-only `sq doctor` subcommand that orchestrates pure
check functions over existing inspection targets — `get_all_profiles()`,
`resolve_auth_strategy_for_profile()`, `providers_toml_path()`,
`models_toml_path()`, `shutil.which("cf"|"codex")`, Claude Code env-var
presence — and renders a Rich table (default) or JSON (`--json`).

Key decisions:

- Two new files: `cli/commands/doctor.py` (Typer command + rendering) and
  `cli/commands/doctor_checks.py` (pure synchronous check functions
  returning a `CheckResult` dataclass). Separation keeps checks unit-
  testable without Typer.
- "Apparent intent" inference is deferred. Required checks are only those
  that block all Squadron use (the package itself, at-least-one provider
  authenticated, parseability of any user-supplied `providers.toml` /
  `models.toml`). Provider-specific and integration-specific rows are
  WARN. Exit 1 iff any MISSING row.
- WARN rows are hidden by default; surface via `-v`. JSON output always
  includes all rows.
- No network calls. Auth correctness against the wire remains
  `sq auth login`'s job. Doctor reports "authenticated locally" — not
  "will work."
- Failure-mode enumeration is explicit for every I/O point (malformed
  TOML, missing HOME, stale `which` results, unexpected profile shape,
  `PackageNotFoundError` for dev installs). Every catch logs at WARNING
  per project rules.

Pairs with slice 906 (Quickstart docs) — `fix_hint` strings are the
contract 906 will reference verbatim.

Status: not_started · Effort: 2/5 · Risk: Low · Dependencies: none.

---

## 20260510

### Slice 250: Container Step Classification — Implementation Complete

**Completed:** Phase 6 implementation. Slice 250 is complete.

**Summary of changes (commit 91f8ccd):**
- New `src/squadron/pipeline/steps/utils.py` — `unpack_inner_steps` extracted from `executor.py` to eliminate circular import
- `executor.py` — replaced local `_unpack_inner_steps` with imported utility
- `EachStepType.inner_steps()`, `LoopStepType.inner_steps()` — parse `steps:` list, return `StepConfig` objects
- `FanOutStepType.inner_steps()` — returns one synthetic `_fan_out_aggregate` sentinel carrying the `models:` value
- `classification.py` — added `_classify_alias_set` (shared alias-set aggregator), `_classify_container_inner` (classifies a single inner step / handles `_fan_out_aggregate` sentinel), extended main step loop to descend into containers when `expand()` returns `[]`; added `container_path: str | None = None` field to `StepClassification`
- `run.py` — `_render_explain` emits dim container header rows and `↳ {inner_name}` indented inner-step rows
- 27 new tests across `test_inner_steps.py`, `test_classification.py`, `test_run.py`
- Full suite: 1869 passed, 2 pre-existing failures (compact compose integration)

**Notable implementation decisions:**
- Used `getattr(step_impl, "inner_steps", None)` instead of a lambda to avoid pyright `Unknown` errors
- Rich wraps cell content in narrow test terminals — `↳` assertions check for the symbol presence rather than `"↳ name"` substring
- `_classify_pool_step` refactored to a thin wrapper over `_classify_alias_set` preserving `pool_name`

---

### Slice 250: Container Step Classification — Task Breakdown Complete

**Completed:** Phase 5 task breakdown.

**Documents created:**
- `project-documents/user/tasks/250-tasks.container-step-classification-each-loop-fan-out.md` — 12 tasks, 321 lines

**Task structure:**
- T1: Branch setup
- T2: Extract `_unpack_inner_steps` → `steps/utils.py` (removes circular import); update executor call sites
- T3: `EachStepType.inner_steps()` + tests
- T4: `LoopStepType.inner_steps()` + tests
- T5: `FanOutStepType.inner_steps()` returning sentinel `_fan_out_aggregate` + tests
- T6: Extract `_classify_alias_set` from `_classify_pool_step`; regression test
- T7: Add `container_path: str | None = None` to `StepClassification`; regression test
- T8: Core classifier extension — `_classify_container_inner` helper + modified step loop; 9 new classification tests
- T9: `_render_explain` container rendering (header row + `↳` indent) + 3 rendering tests
- T10: ruff format/check, pyright, full pytest gate
- T11: Implementation commit
- T12: Slice closeout (status, slice plan, CHANGELOG, DEVLOG, docs commit)

**Key task notes:**
- T2 is the prerequisite for T3/T4 (circular import blocker). T5 is independent of T3/T4.
- T6 must precede T8 (T8 calls `_classify_alias_set`).
- T7 must precede T8 and T9 (both use `container_path`).
- T8's `_classify_container_inner` asserts `inner.step_type != "_fan_out_aggregate"` before `get_step_type()`, enforcing the sentinel invariant.

**Status:** Ready for Phase 6 (Implementation).

---

### Slice 250: Container Step Classification — Design Complete

**Completed:** Phase 4 slice design.

**Documents created/updated:**
- `project-documents/user/slices/250-slice.container-step-classification-each-loop-fan-out.md` — full LLD
- `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md` — slice 250 entry updated with design link and today's date

**Key design decisions:**
- `inner_steps(config)` added as an optional extension method on step types (detected via `hasattr`, not a required protocol method) — avoids touching all existing step type files.
- `_unpack_inner_steps` extracted from `executor.py` to a shared location so `EachStepType` and `LoopStepType` can reuse it in `inner_steps()` without a circular import.
- `fan_out` returns one synthetic sentinel `StepConfig` (`step_type="_fan_out_aggregate"`) encoding the `models:` field. The classifier detects the sentinel and routes to pool-classify or alias-list-classify accordingly.
- `_classify_alias_set` extracted from `_classify_pool_step` as a shared helper — both the pool path and the fan_out literal-list path call the same aggregation rule.
- `StepClassification` gains `container_path: str | None = None` (backward-compatible, defaults to `None`).
- `--explain` rendering uses `  ↳` indent in the Step column rather than a new column — keeps table width manageable.
- Parent step attribution: inner-step `StepClassification` rows carry the container's `step_name` and `step_index`, not the inner step's own name (which goes in `container_path`).
- No executor changes in scope.

**Status:** Ready for Phase 5 (Task Breakdown).

---

## 20260507

### Slice 243 follow-up: classify_pipeline missed phase-step dispatches (commit aef3b41)

Discovered while testing slice 246's `--explain` against P4: the classifier
returned a single non-SDK row (the summary step), reporting P4 as
Claude-free even though P4's `design` step dispatches with the default
`model: sonnet` (SDK).

**Root cause:** `_MODEL_DISPATCHING_STEP_TYPES` in `classification.py`
gated on raw step-type names (`dispatch`/`review`/`summary`/`compact`).
Phase step types (`design`/`tasks`/`implement`) expand into those
actions via `StepType.expand()` but their step-type name doesn't match,
so the classifier silently skipped them. The same gap also affected the
embedded review block under a phase step.

**Fix:** Classifier now walks `StepType.expand()` and classifies each
emitted model-dispatching action. Action configs run through
`resolve_placeholders` against pipeline-default params so `{model}`-style
templates resolve to their concrete alias before cascade lookup. Two test
fixtures for standalone review steps were updated to include the required
`template` field.

**Known limitation (out of scope here):** `each`, `loop`, and `fan_out`
step types return `[]` from `expand()` — their inner model dispatches are
still uncovered by classification. These are handled directly by the
executor; a future slice should either teach those step types to surface
their inner dispatches, or extend the classifier to introspect them.

---

## 20260506

### Slice 246: Auth-Classification Diagnostics CLI — Complete (commit ec72fab)

All 9 tasks implemented in a single pass on branch `246-slice.auth-classification-diagnostics-cli`.

**Changes:**
- `src/squadron/cli/commands/run.py` — Added `--explain` flag, `_render_explain`, `_handle_explain`, `_extract_model_override`, `_SHAPE_LABELS` constant, `_STEP_CLASS_COLORS` constant, mutual-exclusivity guards (5 incompatible options), and dispatch branch. All confined to this file; no new modules.
- `tests/cli/commands/test_run.py` — Added `TestExplainMutualExclusivity` (5 tests) and `TestExplainCommand` (8 tests). Total test count: 1863 passing.

**Verification findings:**
- `uv run sq run p6 --explain` and `uv run sq run implement --explain` work correctly.
- `test-compact-compose` has a misconfigured `summary-2` step with no model at any cascade level — `--explain` correctly raises `ClassificationError` for it. Verification walkthrough updated to use `p6` and `implement` instead.
- Pre-existing integration test failures (2 in `test_compact_compose_integration.py`) are unrelated and present on `main` before this branch.

**Quality gates:** ruff format ✓, ruff check ✓, pyright ✓ (3 pre-existing errors), pytest 1863 passed.

---

### Slice 246: Auth-Classification Diagnostics CLI — Task Breakdown Complete

No commits (planning-only phase).

Created `project-documents/user/tasks/246-tasks.auth-classification-diagnostics-cli.md` (173 lines, 9 tasks).

**Task sequence:** Flag declaration (T1) → mutual-exclusivity guard (T2) → guard tests (T3) → `_render_explain` renderer (T4) → `_handle_explain` handler (T5) → wire dispatch branch (T6) → happy-path tests (T7) → error-path tests (T8) → quality gates + commit (T9).

All changes confined to `src/squadron/cli/commands/run.py` and `tests/cli/commands/test_run.py`. No new modules. Dependencies (classify_pipeline, PipelineClassification, all related enums) fully stable.

**Ready for Phase 6 (Implementation).**

---

## 20260505

### Slice 246: Auth-Classification Diagnostics CLI — Design Complete

No commits (design-only phase).

Created `project-documents/user/slices/246-slice.auth-classification-diagnostics-cli.md`. Updated slice plan entry (240-slices) to reference the design document and pin the flag name as `--explain`.

**Decisions:**
- Flag name `--explain` (over `--classify`, `--auth-check`) — most natural for the "explain to me why this needs Claude auth" user intent.
- No new module; all changes land in `cli/commands/run.py`: new `--explain` flag, `_handle_explain`, and `_render_explain`.
- `--explain` accepts `--model`, `--param`, `--strict`, and `--verbose`; rejected alongside execution options (`--resume`, `--dry-run`, `--from`, `--prompt-only`, `--validate`).
- Resolver construction duplicates `_run_pipeline_sdk`'s `_classify_resolver` block intentionally — deferred to a `_build_classification_resolver` helper only when a third call site appears.
- No `--json` output in this slice; trivial to add as a maintenance task later.
- Rich table for per-step output (matches existing CLI conventions); summary panel below.

**Ready for Phase 5 (Task Breakdown) and implementation.**

---

### Initiative 260: Non-SDK Agent Tool Use — Architecture and Slice Plan Complete

Commits `0d94d7b` (arch + slice plan), `0c19515` (arch review).

**Context:** Triggered by observing that `test-p4.yaml` with `model: kimi25` fails silently — the model emits raw tool-call XML into the response stream because `OpenAICompatibleAgent` never passes `tools` to the API and has no execution loop. Confirmed via code audit that `allowed_tools`, `permission_mode`, and all tool-related `AgentConfig` fields are silently ignored by non-SDK providers.

**Architecture (`260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`):** Agentic loop inside `OpenAICompatibleAgent._run_agentic_loop` (structured for future lift-out). Tool descriptor protocol: name, description, JSON Schema parameters, `cwd`-injecting factory, async executor returning `ToolResult(content, is_error)`. Process-level tool registry (`register`/`lookup`/`materialize`). Core tools: `read_file`, `write_file` (CWD-scoped), `bash` (CWD working directory; network/env/fork unrestricted at this stage — documented scope). Reuses existing `AgentConfig.allowed_tools` field with non-SDK semantics; empty by default, opt-in per pipeline step. Max-iterations guard + character-count token-budget threshold. Streaming contract: intermediate turns DEBUG-logged only; final turn streams normally. Arch review (GLM-5.1, CONCERNS) addressed in same session: F001 false "no network" claim fixed; F002–F008 covered by new Technical Considerations subsections (descriptor protocol, cwd injection, async-first interface, token budget, streaming contract, content+tool_calls co-occurrence).

**Slice plan (`260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`):** 5 slices. Critical path: 261 (tool registry + core tools, Effort 2/5) → 262 (agentic loop, Effort 3/5) → 263 (dispatch wiring + YAML surface, Effort 2/5). Deferred: 264 (CF MCP bridge), 265 (review/summary coverage).

**Decision:** Initiative 260 shelved pending completion of initiative 240 (4 slices remaining: 246–249). Will resume 260 after 240 is closed.

## 20260504

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Complete

Commit `be0138c`. 10 files changed, 947 insertions.

**Delivered:**
- `PoolClassificationPolicy` enum (`LAZY`/`STRICT`) in `classification.py`; `PipelineClassification` stores policy; `needs_persistent_session` evaluates `POOL_UNCERTAIN` against policy — LAZY skips it, STRICT counts it.
- `classify_pipeline()` gains optional `policy=PoolClassificationPolicy.LAZY` param.
- `PipelineDefinition.auth_policy: str | None` and `PipelineSchema.auth_policy` with validator (accepts `"lazy"`, `"strict"`, or `None`).
- `execute_pipeline()` gains `pool_policy` param; mid-run lazy hook connects `SDKExecutionSession` just before the first step whose candidate statically resolves to an SDK alias. `_step_needs_sdk()` and `_connect_lazy_session()` are private helpers.
- `LazySessionConnectError` exception carries step name; caught in `_run_pipeline_sdk` which prints a user-facing red message with `--strict` guidance and raises `typer.Exit(1)`.
- `DispatchAction._dispatch` guard: when `sdk_session is None` and the resolved alias has an explicit `'sdk'` profile (pool selected an SDK alias at runtime), returns FAILED with `--strict` hint. `None` alias_profile (no explicit profile) still routes through the one-shot agent safely.
- `sq run --strict` flag; YAML `auth_policy: strict` support; policy resolution precedence: LAZY → YAML strict → CLI `--strict`.
- `PERSISTENT_SESSION_STEP_TYPES` renamed public (was `_PERSISTENT_SESSION_STEP_TYPES`) to avoid pyright `reportPrivateUsage`.

**Tests:** `tests/cli/commands/test_run_pipeline_lazy.py` (new, 18 tests); expanded `test_classification.py` (+12 tests); `test_schema.py` (+4 tests); `test_dispatch.py` (1 updated). 1836 total passing, 0 new failures. ruff/pyright clean (3 pre-existing pyright errors from slice 244 unchanged).

**Key design decision (implementation):** Dispatch guard uses `alias_profile == ProfileName.SDK` (not `is_sdk_profile(alias_profile)`) because `is_sdk_profile(None)` returns True but `None` profile means "one-shot agent, safe without session". Only an explicit `'sdk'` profile signals that a pool selected a true SDK alias requiring a persistent session.

### Slice 243: Resolution Pre-Scan — Phase 6 Implementation Complete

Commit `e838898`. Changed files: `src/squadron/pipeline/classification.py` (new, 235 lines), `src/squadron/pipeline/resolver.py` (added `cascade_candidates()`; refactored `resolve()` to consume it), `tests/pipeline/test_classification.py` (new, 28 tests).

**`ModelResolver.cascade_candidates(action_model, step_model) -> tuple[str | None, ...]`** — returns the ordered cascade inputs (cli_override, action_model, step_model, pipeline_model, config_default) with no alias resolution and no pool selection. `resolve()` now iterates `cascade_candidates()` internally, making cascade ordering single-source. Existing 11 resolver tests pass unchanged.

**`classification.py`** — `classify_pipeline(definition, resolver, pool_backend) -> PipelineClassification`. Walks `definition.steps`; for each model-dispatching step (`dispatch`, `review`, `summary`, `compact`), calls `resolver.cascade_candidates()`, picks first non-None, then dispatches: non-pool candidate → `resolve_model_alias()` + `is_sdk_profile()` → `SDK_REQUIRED` or `NON_SDK`; pool candidate → walks `pool.models` statically → all-SDK collapses to `SDK_REQUIRED`, all-non-SDK to `NON_SDK`, mixed → `POOL_UNCERTAIN`. Non-model steps skipped; `step_index` preserves original pipeline position. Two failure modes raise `ClassificationError` explicitly: empty cascade and pool candidate without backend. `PipelineClassification` derives `needs_persistent_session` (dispatch/summary/compact SDK or pool-uncertain), `needs_one_shot_claude` (review SDK or pool-uncertain), and `shape` (`claude_required_persistent`, `claude_required_one_shot`, `claude_free`).

**Test coverage (28 tests):** spy-backend verification (T1), cascade ordering and resolve-consumes-candidates patch guard (T3), all 7 property isolation tests (T5), 9 non-pool path tests including step-index and F002 regression guards (T7), 5 pool path tests with zero-select assertions (T9), idempotency/side-effect-freeness regression (T10). ruff/pyright clean; full suite +28 new passing tests.

No executor changes. Pre-existing 2 failures in `test_compact_compose_integration` are unrelated and pre-date this slice.

### Slice 243: Resolution Pre-Scan — Phase 5 Task Breakdown Complete

Created [243-tasks.resolution-pre-scan.md](project-documents/user/tasks/243-tasks.resolution-pre-scan.md) (267 lines, 12 tasks). Task sequence: T1 creates test infrastructure (`SpyPoolBackend`, definition/resolver builders) before any implementation. T2 adds `ModelResolver.cascade_candidates()` and refactors `resolve()` to consume it (single-source cascade, resolves review F001). T3 tests `cascade_candidates` and the resolver refactor. T4 defines the dataclasses (`StepClass`, `PipelineShape`, `ClassificationError`, `StepClassification`, `PipelineClassification`) with the three `@property` methods. T5 tests the properties in isolation — includes direct F002 regression guard (`test_needs_one_shot_claude_false_for_sdk_dispatch_only`). T6–T7 implement and test the non-pool path. T8–T9 implement and test the pool path (pool-collapsing logic + `SpyPoolBackend` zero-select assertions). T10 adds the idempotency/side-effect-freeness regression test. T11 is the quality-gate and commit task. T12 closes the slice. No open questions; design is unambiguous.

### Slice 243: Resolution Pre-Scan — Phase 4 Slice Design Revision (review CONCERNS addressed)

Slice review at [243-review.slice.resolution-pre-scan.md](project-documents/user/reviews/243-review.slice.resolution-pre-scan.md) returned `CONCERNS` with two findings; both addressed in-place in the slice design (frontmatter `reviewIteration: 2`, `dateUpdated: 20260504`). **F001 (cascade duplication):** earlier draft proposed three read-only properties (`cli_override`, `pipeline_model`, `config_default`) on `ModelResolver` and reproduced the cascade ordering inside the classifier — leaving cascade logic in two places with a known divergence risk. Replaced with a single `ModelResolver.cascade_candidates(action_model, step_model) -> tuple[str | None, ...]` method returning the ordered cascade *inputs* (no alias resolution, no pool selection). `resolve()` is refactored in the same change to consume the new method internally so the two paths cannot drift; added `test_cascade_candidates_returns_ordered_inputs` and `test_resolve_consumes_cascade_candidates` regression guards. The "Resolver attribute coupling" risk is dropped (resolved by design). Non-goal updated: "no new *selection-performing* resolver entrypoint" (the side-effect-free accessor is permitted; selection is the prohibition). **F002 (`needs_one_shot_claude` semantics drift):** earlier draft defined the predicate as "any SDK-resolved or pool-uncertain step" — broader than arch §Envisioned State point 2, which scopes it to steps that route through the provider registry's one-shot ClaudeSDKAgent path. Tightened to: SDK-resolved review steps ∪ SDK-resolved dispatch-via-agent steps (the second set is empty in practice post-slice-242, included for arch-correctness). Added two new tests — `test_one_shot_excludes_persistent_session_steps` (dispatch+summary all Claude → `needs_one_shot_claude=False`, the direct F002 regression guard) and `test_one_shot_excludes_non_sdk_review`. Success criterion #4 expanded with explicit mixed-pipeline rows. Test count moved from ~14 to ~16. Five PASS findings (side-effect contract documentation, conservative pool default, failure-mode enumeration, scope discipline, 180-band boundary) acknowledged; no design changes for those.

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Task Breakdown Complete

**Completed:** Phase 5 task breakdown.

**Documents created:**
- `project-documents/user/tasks/245-tasks.pool-resolution-classification-policy-and-mid-run-session-construction.md` — 19 tasks across: enum addition, `PipelineClassification` policy field, `classify_pipeline` default change, `auth_policy` YAML field (`PipelineSchema` + `PipelineDefinition`), `execute_pipeline` mid-run hook + helpers, connect-failure UX, `--strict` CLI flag, policy resolution, existing test audit, build/format, and closeout.

**Key task notes:**
- T7: `PipelineSchema` has `extra="forbid"` — `auth_policy` must be added as a declared field; validator rejects anything other than `None`/`"lazy"`/`"strict"`.
- T9: `_step_needs_sdk` ignores pool candidates (returns `False`) — hook fires only on statically confirmed SDK steps.
- T11: connect failure → run state `failed` + re-raise → `_run_pipeline_sdk` catches and prints red message.
- T15: existing pool-uncertain tests relied on the old conservative default; they need `policy=STRICT` annotations or assertion updates.

**Pending:** Phase 6 (implementation). No open questions.

---

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Design Complete

**Completed:** Phase 4 slice design.

**Documents created/updated:**
- `project-documents/user/slices/245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md` — slice design
- `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md` — slice plan entry 5 updated with design link and revised policy framing

**Design summary:**
- **Lazy is the default.** Session not constructed at startup for pool-uncertain pipelines. `--strict` CLI flag (and `auth_policy: strict` pipeline config key) opts into eager upfront connection.
- `PoolClassificationPolicy` enum (`lazy` / `strict`) in `pipeline/classification.py`; default is `LAZY`.
- `classify_pipeline` gains optional `policy` parameter (default `LAZY`); `PipelineClassification` stores the policy used.
- `needs_persistent_session`: under `LAZY`, `POOL_UNCERTAIN` does not force session construction; only statically-confirmed `SDK_REQUIRED` steps do.
- Mid-run hook in `execute_pipeline` (arch §5a): fires on first confirmed-SDK step when `sdk_session is None`; all subsequent steps reuse the same session. Hook is policy-agnostic (dead path under strict mode since session is pre-constructed).
- Auth-failure UX: connect failure mid-run → `failed` run state + clear message; runtime pool selects SDK with no session → `FAILED` step result with `--strict` remediation hint.
- 12 new tests planned across `test_run_pipeline_lazy.py` and `test_classification.py`. Existing pool-uncertain tests need policy annotation update.

**Pending:** Phase 5 (task breakdown) and Phase 6 (implementation). No open questions; design is self-contained.

---

### Slice 244: Conditional Persistent Session Construction — Implementation Complete

**Completed:** Phase 6 implementation (commit c939fb2, branch `244-slice.conditional-persistent-session-construction`)

**Files changed:**
- `src/squadron/cli/commands/run.py` — Added `pool_backend: PoolBackend | None = None` param to `_run_pipeline`; added guard replacing unconditional `DefaultPoolBackend()`. In `_run_pipeline_sdk`: lifted `DefaultPoolBackend()` construction, added `_classify_resolver` (no `on_pool_selection`), added `classify_pipeline` call with `ClassificationError` handler, added INFO/DEBUG logging of classification shape, added session gate (`if classification.needs_persistent_session`). Added `_logger = logging.getLogger(__name__)`.
- `tests/cli/commands/test_run_pipeline_sdk.py` — New test file: 11 tests covering T3 (fallback), T6 (classification gate: all 6 scenarios), T7 (resume path: 2 scenarios).
- `tests/pipeline/test_sdk_wiring.py` — Updated 2 tests to mock `classify_pipeline`/`DefaultPoolBackend`/`ModelResolver` for `needs_persistent_session=True` (tests verify connect/disconnect lifecycle; mock classification is correct because those tests are about lifecycle, not classification).

**Design decisions confirmed during implementation:**
- `on_pool_selection` callback needs `state_mgr`/`_run_id` (initialized inside `_run_pipeline`), so the classification resolver `_classify_resolver` is built without a callback — classification is side-effect-free and never calls `pool_backend.select()`.
- `typer.Exit` raises `click.exceptions.Exit`, not `SystemExit` — tests use `pytest.raises(typer.Exit)` with `exc_info.value.exit_code == 1`.
- Tests run inside Claude Code session (`CLAUDECODE` env var set), so all `_run_pipeline_sdk` tests patch `_resolve_execution_mode` to bypass the session guard.
- Pre-existing failures: `tests/pipeline/test_compact_compose_integration.py` (2 tests) were already failing on main before this slice; not introduced here.

**Audit (T9):** `sdk_session=None` guards confirmed present in `compact.py:62`, `summary.py:149`, `summary.py:218`. No changes needed.

**Test results:** 1806 passing, 2 pre-existing failures (compact compose, unrelated), 0 new failures.

---

### Slice 244: Conditional Persistent Session Construction — Task Breakdown Complete

**Completed:**
- Created `user/tasks/244-tasks.conditional-persistent-session-construction.md` (11 tasks, 192 lines)

**Task structure:**
- T1: Branch setup
- T2: Add optional `resolver`/`pool_backend` params to `_run_pipeline` (backward-compatible)
- T3: Test fallback path (no params supplied)
- T4: Lift `pool_backend`/`resolver` construction into `_run_pipeline_sdk`; wire `on_pool_selection`
- T5: Add `classify_pipeline` call and session gate in `_run_pipeline_sdk`
- T6: Tests for classification gate (T1–T5, T8 from design — non-SDK, SDK, pool-uncertain, ClassificationError, connect failure)
- T7: Tests for resume path (T6, T7 from design)
- T8: Intermediate commit (ruff + pyright + pytest gate)
- T9: Audit `sdk_session=None` correctness for summary/compact (belt-and-suspenders verification)
- T10: Final validation and commit
- T11: Documentation and slice closeout

**Key design note in tasks:** `on_pool_selection` callback depends on `state_mgr`/`_run_id`, which are initialized inside `_run_pipeline`. T4 explicitly flags that the callback must be attached after `state_mgr` is known — implementer must set `resolver._on_pool_selection` inside `_run_pipeline` when `resolver is not None`, or add a setter. Classification never fires pool selection (side-effect-free), so the callback is safe to attach late.

**Status:**
- Task breakdown complete and ready for Phase 6 (Implementation).

---

### Slice 244: Conditional Persistent Session Construction — Design Complete

**Completed:**
- Created `user/slices/244-slice.conditional-persistent-session-construction.md`
- Updated slice plan entry 244 in `240-slices.pipeline-auth-boundary-flexibility.md` with design link

**Key design decisions:**
- Classification runs inside `_run_pipeline_sdk` after `definition` is loaded and `resolver` is constructed — before any session work.
- `pool_backend` and `resolver` are constructed in `_run_pipeline_sdk` and threaded into `_run_pipeline` as optional params; `_run_pipeline`'s internal fallback construction is preserved for callers that don't supply them.
- `POOL_UNCERTAIN` steps take the conservative-pessimistic path (session constructed); lazy opt-in is slice 245.
- `ClassificationError` → `typer.Exit(1)` with a clear message; not an unhandled exception.
- Resume re-classifies from current YAML + alias state; seeding path unchanged (runs only when `sdk_session is not None`).
- Three observable shapes fully established: `claude_required_persistent`, `claude_required_one_shot`, `claude_free`.

**Status:**
- Design ready for Phase 5 (Task Breakdown).

---

## 20260503

### Slice 243: Resolution Pre-Scan — Phase 4 Slice Design Complete

Authored design at [243-slice.resolution-pre-scan.md](project-documents/user/slices/243-slice.resolution-pre-scan.md). Slice introduces a new `src/squadron/pipeline/classification.py` module exposing `classify_pipeline(definition, resolver, pool_backend) -> PipelineClassification`. The classifier walks `PipelineDefinition.steps`, reproduces the resolver's five-tier cascade in read-only form (so it can inspect candidates *before* selection commits), and emits a `StepClassification` per model-dispatching step (`dispatch`, `review`, `summary`, `compact`). Non-pool candidates resolve via `resolve_model_alias` (pure dict lookup); pool candidates classify structurally by walking `ModelPool.models` and applying `is_sdk_profile` to each — never invokes `pool_backend.select()`, never advances 180-band selection state. Two pipeline-level booleans derived per arch §Envisioned State point 2: `needs_persistent_session` (union over `dispatch`/`summary`/`compact` SDK-resolved steps, *excluding* reviews — they route through one-shot ClaudeSDKAgent), and `needs_one_shot_claude` (informational, any-step union). Three pipeline shapes surface: claude_required_persistent, claude_required_one_shot, claude_free. Conservative pool-uncertain default hard-coded for this slice; lazy policy is slice 245's job. Adds three read-only properties on `ModelResolver` (`cli_override`, `pipeline_model`, `config_default`) so the classifier reads via clean public surface, not name-mangled attrs. Failure modes: misconfigured step (cascade yields no candidate) raises `ClassificationError` at planning time; pool candidate without backend likewise. Side-effect-freeness contract documented and asserted by a spy-backend test (zero `select()` calls for double classification). Slice ships the classifier and 14 unit tests only — no executor wiring; slice 244 will gate `SDKExecutionSession` construction on `classification.needs_persistent_session`. Slice-plan entry now carries the design pointer; slice plan `status` advanced to `in_progress`. Risk: Low; Effort: 2/5.

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 6 Implementation Complete

Commit `0dbe41a`. Changed files: `src/squadron/pipeline/actions/dispatch.py`, `tests/pipeline/actions/test_dispatch_routing.py`, `tests/pipeline/actions/test_dispatch_session.py`.

**What changed:**
- `dispatch.py`: Added `is_sdk_profile` import from `squadron.providers.profiles`. Added `_resolve_model(context)` helper that extracts the `action_model / step_model / resolver.resolve(...)` cascade. Rewrote `_dispatch` with three-branch profile-aware routing: no session → agent path; session + non-SDK profile → agent path; session + SDK or None profile → session path. `_dispatch_via_session` and `_dispatch_via_agent` retain their own inline resolve cascade unchanged.
- `test_dispatch_routing.py` (new): Five routing tests (T5a–T5e): session+non-SDK→agent, session+None→session, session+sdk→session, no-session→agent, mixed-pipeline-per-step. All pass.
- `test_dispatch_session.py`: Updated one assertion from `assert_called_once_with` to `assert_any_call` to reflect the documented double-resolve (routing call in `_dispatch`, then branch call in `_dispatch_via_session`).

**T10 verification walkthrough:** Unit tests T5a–T5e verify routing logic in isolation. Live end-to-end steps (Step 1 minimax via pure-CLI, Step 2 default Claude regression, Step 3 mixed pipeline) require a configured minimax alias and Claude auth; these are environment-dependent and were not executed in this session. Steps should be run manually before tagging a release. Step 4 (IDE axis unchanged) is covered by existing slice-170 tests.

**Quality gates:** ruff format clean, ruff check clean, pyright 0 errors. Full suite: 1769 passed (baseline 1764 + 5 new).

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 5 Task Breakdown Complete

Created [242-tasks.profile-aware-dispatch-router-pure-cli.md](project-documents/user/tasks/242-tasks.profile-aware-dispatch-router-pure-cli.md) (222 lines, 10 tasks). Three implementation tasks: T1 adds the `is_sdk_profile` import, T2 extracts the `_resolve_model` helper, T3 rewrites `_dispatch` with the profile-aware three-branch routing. T4 verifies existing tests stay green. T5 creates a new dedicated `tests/pipeline/actions/test_dispatch_routing.py` with five routing cases (session+non-SDK→agent, session+None-profile→session, session+explicit-sdk→session, no-session→agent, mixed-pipeline per-step); `test_dispatch.py` at 412 lines would be too large for 5 additional tests. T6–T8 are quality gates (targeted test run, ruff+pyright, full suite expecting 1769+ passed). T9 commits; T10 closes out the slice. No open questions; design is unambiguous.

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 4 Slice Design Complete

Authored design at [242-slice.profile-aware-dispatch-router-pure-cli.md](project-documents/user/slices/242-slice.profile-aware-dispatch-router-pure-cli.md). The slice closes the pure-CLI mirror of slice 170: when `sq run … --param model=<non-sdk>` runs through `_run_pipeline_sdk`, today's `DispatchAction._dispatch` routes purely on `context.sdk_session is not None` and silently misroutes non-SDK aliases to `session.set_model(...)` on a Claude session — the prompt is dispatched to Claude under the non-SDK model id. Design extracts a small `_resolve_model(context)` helper, branches on `is_sdk_profile(alias_profile)` (now imported from `squadron.providers.profiles` per slice 241), and routes non-SDK profiles to `_dispatch_via_agent` even when a persistent session exists. Default Claude path (profile `None` per the slice-241 `None → True` contract) and explicit `sdk` profiles continue through `_dispatch_via_session` unchanged. No session-construction changes — the persistent session still connects at startup; conditional construction is slice 244. Test plan covers five routing cases (session+non-SDK → agent, session+default-None → session, session+explicit-sdk → session, no-session → agent, mixed-pipeline per-step). Risk: Low; Effort: 2/5. Slice-plan entry materialized with the (242) index and design pointer; frontmatter dateUpdated bumped.

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 6 Implementation Complete

Mechanical refactor landed in commit 393af52: `is_sdk_profile()` now lives in `src/squadron/providers/profiles.py` (alongside `get_profile()`), with `__all__` updated to export it. Two production callers (`pipeline/prompt_renderer.py:23`, `pipeline/actions/summary.py:11`) and one test (`tests/providers/test_profiles.py`) import from the new home; the old definition and its predicate-test are deleted from `pipeline/summary_oneshot.py` and `tests/pipeline/test_summary_oneshot.py`. The 9-case parametric test (None, "sdk", 5 registered non-SDK profiles, "unknown-profile", "") covers the documented contract; `None` → `True` semantics preserved per arch iteration 3 (renderer/summary call sites depend on this; pre-scan layer in slice 243 will operate only on resolved profiles and never pass `None`). All 4 grep sentinels green: zero hits for the old import path, zero residual references in `summary_oneshot.py`, expected hits at the new home. Quality gates: ruff format clean, ruff check clean, pyright zero errors, full suite 1764 passed (one net-new test). Verification walkthrough re-run end-to-end against the landed commit; observed output matches documented expectations across steps 1–5 and 7. Foundation in place for slices 242–248. Note: the slice-plan summary line at `240-slices.pipeline-auth-boundary-flexibility.md:35` still narrates the original `None` → `False` contract; appended a pointer to the arch iteration-3 contract rather than rewriting the plan body.

---

## 20260502

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 5 Task Breakdown

Task file created at `user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md` (10 tasks, 158 lines). Sequenced as: T1 add predicate to `providers/profiles.py` → T2 add parametric test at new home → T3 update `prompt_renderer.py` import → T4 update `actions/summary.py` import → T5 remove predicate from `test_summary_oneshot.py` → T6 delete old definition from `summary_oneshot.py` → T7 grep sentinel verification → T8 quality gates → T9 commit → T10 slice closeout. Investigation confirmed `tests/providers/test_profiles.py` already exists (no `is_sdk_profile` tests yet) and `tests/providers/` directory is present — no `__init__.py` creation needed.

---

## 20260501

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 4 Slice Design

Drafted slice design at [241-slice.is-sdk-profile-predicate-re-homing.md](project-documents/user/slices/241-slice.is-sdk-profile-predicate-re-homing.md). Foundation slice for the 240-band initiative: promotes `is_sdk_profile()` from [pipeline/summary_oneshot.py:19-24](src/squadron/pipeline/summary_oneshot.py#L19-L24) to [providers/profiles.py](src/squadron/providers/profiles.py) with an explicit contract (returns `True` for `None` or `"sdk"`, `False` for every other registered profile and unknown strings; no I/O, no auth probe, pure read of the profile-name enum). Investigation found only **2 production importers** (not 3 as the slice plan estimated) — slice 170 added the predicate to the dispatch *renderer* but not the dispatch *router* (router branch is slice 242's work). 6-file mechanical refactor: new definition + new test file + 2 caller import updates + old definition removal + old test removal. No re-export shim — all callers update in the same PR. Slice plan entry updated with design-complete pointer.

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 3 Slice Plan

Drafted slice plan at [240-slices.pipeline-auth-boundary-flexibility.md](project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md). 8 slices in two groups: 1 foundation (241 predicate re-homing) + 7 features (242 dispatch router pure-CLI fix, 243 resolution pre-scan, 244 conditional persistent session construction, 245 pool-resolution policy + mid-run construction, 246 `sq run --explain` diagnostics CLI, 247 documentation, 248 adversarial test matrix). Each slice maps directly to addressed-CONCERN territory from the iteration-2 arch review: 241 → F006 ownership, 243 → F003/F004/F005 pre-scan correctness, 244 → F001 split classification + F007 resume policy, 245 → F002 mid-run mechanism. Conservative shipping order: 241 → 242 → 243 → 244 → 245 → 246 → 248 → 247. Aggressive parallel order with {242, 243} and {244, 246} as parallelizable groups also documented.

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 6 Implementation Complete

All 15 tasks (T1–T15) implemented and committed. 1763 tests passing, zero ruff/pyright errors.

**What changed:**

- **`_render_dispatch` branches on resolved profile** (`prompt_renderer.py`): SDK/None profiles keep the current in-session path (`model_switch`, no command). Non-SDK profiles emit a `sq _dispatch-run` command with `--prompt-file {tmp_path}`, `--model`, `--profile`, and any non-internal params forwarded as `--param` flags. `model_switch` and `command` are mutually exclusive.
- **`one_shot_dispatch` helper extracted** (`dispatch.py`): Factored the agent-spawn sequence out of `_dispatch_via_agent` into a public module-level async function. `_dispatch_via_agent` becomes a thin caller. Token metadata was not consumed downstream and was dropped in the refactor.
- **`sq _dispatch-run` hidden subcommand added** (`cli/commands/dispatch_run.py`, `app.py`): Reads prompt from `--prompt-file`, resolves profile via `ModelResolver` if `--profile` omitted, calls `one_shot_dispatch`, prints to stdout. Errors always go to stderr before exit 1. Hidden from `sq --help`.
- **`commands/sq/run.md` dispatch section updated**: Branched on `command` field presence — non-SDK path writes temp file, replaces `{tmp_path}`, runs via Bash, cleans up. SDK/in-session path is the else branch (unchanged wording).
- **SDK synthetic-error fix** (`sdk_session.py`): In `SDKExecutionSession.dispatch`, after `translate_sdk_message`, checks `isinstance(sdk_msg, ResultMessage) and sdk_msg.is_error` before appending content. Raises `ProviderAPIError("SDK reported is_error=True: ...")` on the error path. Existing `_CLI_ERROR_PREFIX` text check in `_check_cli_error` preserved as backstop.

**Key decision:** `_one_shot_dispatch` renamed to `one_shot_dispatch` (no leading underscore) because pyright strict mode treats leading-underscore module-level names as private and the function is intentionally cross-module.

**Commits:** `9942161` refactor, `6000c42` feat renderer, `062191e` feat subcommand, `7545a7e` feat run.md, `32bc7f6` fix sdk error

**Issues logged:** None.

**Next:** Initiative 240 slice plan (pipeline auth-boundary flexibility), or Phase 6 on any pending slice.
Format: `## YYYYMMDD` followed by brief notes (1-3 lines per session).  This file differs from
CHANGELOG.md, in that this file is written from implementor perspective where CHANGELOG.md is
written from user perspective.

---

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 5 Task Breakdown

Task file created at `user/tasks/170-tasks.profile-aware-dispatch-model-routing.md` (15 tasks, 360 lines).
Tasks cover: `_one_shot_dispatch` extraction from `_dispatch_via_agent`, `_render_dispatch` profile
branch fix, new hidden `sq _dispatch-run` subcommand, `commands/sq/run.md` dispatch-section update,
SDK `is_error` synthetic-error detection fix, full suite + type-check, verification walkthrough, and
slice closeout. Inline `--prompt` intentionally omitted from `_dispatch-run`; file-only via
`--prompt-file` matching the established convention for multi-KB assembled context.

---

## 20260428

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 2 Architecture (review iteration 2)

Reviewed via slice-style review at [240-review.arch.pipeline-auth-boundary-flexibility.md](project-documents/user/reviews/240-review.arch.pipeline-auth-boundary-flexibility.md) (verdict CONCERNS, 6 concerns + 1 note). All addressed in arch doc revision: classification split into two distinct properties (`needs_persistent_session` vs `needs_one_shot_claude`) so review-only-with-SDK-reviews pipelines no longer pay persistent-session connect cost (F001); mid-run lazy-connect mechanism sketched in Envisioned State step 5a after verifying `ActionContext` is constructed per-action in `pipeline/executor.py:785` (F002); pre-scan pool handling clarified as static structural query against pool's alias list with no 180 API dependency (F003); pre-scan resolver instance must match runtime cascade including `--param` overrides (F004); resolver side-effect-freedom verified by inspection of `models/aliases.py:resolve_model_alias` and stated as documented contract (F005); `is_sdk_profile()` ownership promoted to `providers/profiles.py` with explicit contract (F006); resume policy under changed pipeline definitions stated explicitly — current resolution wins (F007).

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 2 Architecture

Drafted [240-arch.pipeline-auth-boundary-flexibility.md](project-documents/user/architecture/240-arch.pipeline-auth-boundary-flexibility.md). Promoted from in-flight slice-170 work after recognising the actual scope: today's pipeline executor unconditionally constructs a `ClaudeSDKClient` at startup regardless of pipeline content, and the dispatch router has no profile branch — together these mean (a) any `sq run` from pure CLI requires Claude auth, (b) `sq run … --param model=<non-sdk>` for a dispatch step silently fails. Architecture names two distinct SDK-touching paths (persistent `SDKExecutionSession` vs. registry-spawned one-shot `ClaudeSDKAgent`) and treats them as separate auth surfaces, both intentional. Initiative owns: per-step auth classification via resolution pre-scan, conditional persistent-session construction, profile-aware dispatch routing in pure-CLI mode, pool-resolution classification policy (conservative-vs-lazy), and diagnostic CLI surface. Explicit non-goals: until-loop convergence, fan-out/fan-in aggregation, intra-loop compaction policy, conversation-vs-override-instruction routing for findings — all 180-band. One-shot Claude subprocess pooling documented as known cost, not optimised. Anticipated 6–10 slices. Initiative entry added to [001-initiative-plan.squadron.md](project-documents/user/project-guides/001-initiative-plan.squadron.md) at index 240; cross-initiative dependency line added.

## 20260427

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 4 Design

Drafted slice design at [170-slice.profile-aware-dispatch-model-routing.md](project-documents/user/slices/170-slice.profile-aware-dispatch-model-routing.md). Mirrors slice 164's profile-aware fix on the dispatch axis: `_render_dispatch` will branch on resolved profile and emit a runnable `sq dispatch …` command for non-SDK profiles (currently emits "in-session work" regardless of profile, so `/sq:run … --param model=minimax` from inside Claude Code silently runs the dispatch in the IDE session instead of routing to minimax). New `sq dispatch` CLI surface factored from `_dispatch_via_agent`. Independent in-scope fix: `_dispatch_via_session` will surface SDK `is_error=True` messages as `ProviderAPIError` instead of returning the error JSON as response text. Slice plan entry added to [140-slices.pipeline-foundation.md](project-documents/user/architecture/140-slices.pipeline-foundation.md) at index 170 (Feature Slices, after 166); plan `dateUpdated` bumped.

### Slice 904: Review-Finding Location Required — Complete

Resolves [issue #10](https://github.com/ecorkran/squadron/issues/10): review findings inconsistently cite a `location:` field, especially on PASS findings. The field is the dedup key for upcoming ensemble review (slices 182, 189), so it has to land first.

**Four coordinated changes:**

1. **Template prompts** (`src/squadron/data/templates/{code,slice,arch,tasks}.yaml`). All four review templates now require `location:` on every finding (PASS included), with a per-template precedence ladder (e.g. code: `path:line` → `path:start-end` → `path#symbol` → `path` → `unverified`). The explicit `unverified` token is the "I don't know" escape hatch — the prompt tells the model that hallucinated paths are worse than `unverified`. Commit `88bf32e`.

2. **Soft-fail parser normalization** (`src/squadron/review/parsers.py`). New `_normalize_location()` helper: missing locations and placeholder values (`-`, `global`, `n/a`, `none`, empty) become `"unverified"` with a WARNING that names the finding ID, title, template, and verdict. Tightened `_CATEGORY_RE` and `_LOCATION_RE` to `[ \t]*` (was `\s*`) so an empty value tag cannot bleed onto the next body line. Threaded `verdict` and `template_name` through `_extract_findings`, `_lenient_extract_findings`, and the synthesized fallback for consistent triage signals. Commit `059818a`.

3. **Diff-membership check** (code reviews only). `_check_diff_membership()` runs after extraction; for each finding citing a path, WARN if the path is not in the diff under review. Skips `UNVERIFIED_LOCATION` findings. Wired up in `review_client.py` via a new `_run_git_diff_filenames()` helper that calls `git diff --name-only` with the same exclude-pattern handling as `_run_git_diff()`. Commit `846a8a1`.

4. **Path-existence check** (all template types). `_check_path_existence()` runs after extraction; for each finding citing a path and a `cwd`, WARN if `(cwd / path).exists()` is false. Cheap defense against hallucinated filenames in arch/slice/tasks reviews where there's no diff. Same commit as (3).

**Hallucination defense, three layers, all WARNING-only:** prompt-side `unverified` token (self-documenting in rendered review); path-existence (catches made-up filenames everywhere); diff-membership (stricter check where we have an authoritative file set). Hard-rejection deferred until real-world false-positive data is available.

**Tests:** 11 new soft-fail tests (`TestLocationSoftFail`) + 6 diff/path tests (`TestLocationDiffMembershipAndPathExistence`). One existing test (`test_no_location_returns_none`) renamed/updated — the old `None` behavior is now `"unverified"` by design. Full review suite: 315 passing. Full project: 1742 passing.

**T11/T12 manual verification with `minimax/minimax-m2.7`:**
- T11 code review against the slice 902 diff (commit `a4679b6`): 8 PASS findings, 8/8 had `location:` populated with real `path:line-range` values. Zero `unverified`, zero hallucinations, zero parser WARNINGs. Saved to [902-review.code.pipeline-verbosity-passthrough-v-vv.md](project-documents/user/reviews/902-review.code.pipeline-verbosity-passthrough-v-vv.md).
- T12 arch review against `900-arch.maintenance-and-refactoring.md`: 5 findings (3 CONCERN, 2 NOTE), 5/5 had `location:` populated. **All 5 fired path-existence WARNINGs** because the model emitted bare filenames (`900-arch.maintenance-and-refactoring.md`) without the `project-documents/user/architecture/` prefix. The check did exactly its job — the cited paths really don't exist relative to `cwd`. The arch prompt could be tightened later to require project-relative paths; for slice 904 the WARNING is the correct surfacing.

**Caveat captured:** the code prompt does not require `category:` (only arch.yaml does), so code-review findings still fall back to `category: uncategorized` in structured output. Pre-existing, not a 904 regression. If/when ensemble review needs category-based dedup, that's a follow-up.

## 20260426

**slice: devlog-9**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: PASS)
- checkpoint-5: PASS
- commit-6: PASS
- summary-0: PASS
- compact-0: PASS

### Slice 902: Pipeline Verbosity Passthrough — Complete
- Commits: `69aefbf` fix(pipeline): thread verbosity through render_step_instructions; `4c1c011` fix(sq:run): peel -v/-vv flags from arguments, pass to sq run.
- `_render_review` now accepts `verbosity: int = 0` (keyword-only). Hard-coded `-v` replaced with conditional: nothing at 0, `-v` at 1, `-vv` at ≥2.
- `_build_action_instruction` and `render_step_instructions` forward `verbosity`. Both `_handle_prompt_only_init` and `_handle_prompt_only_next` in `run.py` pass `verbose` count from typer option.
- `/sq:run` slash command updated: three-step peel (scan → capture → remove) for `-v`/`-vv`/`--verbose`; Step 0 template includes `<verbose_flags>`.
- Tests: existing assertion updated (no `-v` at default); 3 new parametrized verbosity tests added. Full gate: 1723 passed, ruff+pyright clean.
- Verification walkthrough updated with actual output and `command: null` gotcha (use `a.get('command') or ''`).

### Slice 902: Pipeline Verbosity Passthrough — Task Breakdown Complete
- Created `902-tasks.pipeline-verbosity-passthrough-v-vv.md` (12 tasks, 105 lines).
- Tasks cover: `_render_review` verbosity param + conditional emit, test update + new parametrized tests, `_build_action_instruction` forwarding, `render_step_instructions` param, two `run.py` call sites, slash command peel in `run.md`, two commits, final gate.

### Slice 902: Pipeline Verbosity Passthrough — Design Complete
- Created slice design for issue #9: pipeline review commands hard-code `-v`, `/sq:run` swallows trailing flags.
- Two changes: thread `verbosity` param through `render_step_instructions` → `_render_review` (replacing hard-coded `-v`), and update `/sq:run` slash command to peel `-v`/`-vv` from `$ARGUMENTS`.
- Default changes from implicit `-v` to silent (0); `-v`/`-vv` opt in explicitly.

## 20260425

### Slice 901: Pipeline Code-Review Diff Injection — Implementation Complete

Shipped three coordinated fixes for issue #11 (pipeline code reviews silently UNKNOWN).

**UNKNOWN fails closed** (`checkpoint.py`): Added `"UNKNOWN"` to `ON_FAIL` and `ON_CONCERNS`
threshold sets. `verdict is None` (no prior review) is unchanged — only the
parsed-but-unparseable case fails closed. 8 new unit tests in `test_checkpoint.py`.

**`slice` forwarded through `expand()`** (`phase.py`, `review.py`): `PhaseStepType.expand()` and
`ReviewStepType.expand()` now include `"slice"` in the emitted review action dict. Phase steps
use `"{slice}"` placeholder; review steps forward `cfg.get("slice")`. 4 new tests.

**Declarative template-input registry** (`src/squadron/review/template_inputs.py`): New module
with `TemplateInputSpec` dataclass and `TEMPLATE_INPUTS` dict covering `slice`, `tasks`, `arch`,
and `code` templates. `code` entry calls `resolve_slice_diff_range` to inject `inputs["diff"]`.
`_resolve_slice_inputs` in `pipeline/actions/review.py` rewritten to delegate entirely to
`resolve_template_inputs`. 9 registry tests + 6 `_resolve_slice_inputs` regression tests + 2
end-to-end integration tests.

Gates: 1719 tests pass, ruff clean, pyright 0 errors.

### Slice 901: Pipeline Code-Review Diff Injection — Task Breakdown Complete

Task file created at `user/tasks/901-tasks.pipeline-code-review-diff-injection.md`
(13 tasks, test-with pattern, 4 commits). Covers three coordinated fixes for
issue #11: UNKNOWN fails closed in checkpoint thresholds; `slice` forwarded
explicitly through `PhaseStepType.expand()` and `ReviewStepType.expand()`; and
the per-template `match` in `_resolve_slice_inputs` replaced by a declarative
`TEMPLATE_INPUTS` registry that auto-injects `inputs["diff"]` for the `code`
template via `resolve_slice_diff_range`.

**P6: devlog-2**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: UNKNOWN)
- checkpoint-5: PASS
- commit-6: PASS
- compact-0: PASS

### Slice 194: Loop Step Type for Multi-Step Bodies — Implementation Complete

Shipped `LoopStepType` in `src/squadron/pipeline/steps/loop.py` with full `validate()` (7 rules, nested-loop ban on both sub-field and step-type forms) and `expand()` returning `[]`. Added `_execute_loop_body` to `executor.py` and wired it as the `StepTypeName.LOOP` dispatch branch (ahead of the existing `loop:` sub-field else branch). Reused all slice-149 machinery unchanged: `_parse_loop_config`, `LoopCondition`, `ExhaustBehavior`, `evaluate_condition`, `_unpack_inner_steps`, `_execute_step_once`. Strategy field parsed but stubbed with same warning as the single-step path — slice 184 will implement convergence strategies for both forms simultaneously. Added 25 new tests across three test files; fixed 11 pre-existing integration-test failures caused by `slice.yaml` having grown from 6 to 10 steps in a prior commit. All 1690 tests pass, pyright zero errors.

## 20260424

### Slice 194: Loop Step Type for Multi-Step Bodies — Phase 4 Slice Design Complete

Added new slice 194 to `180-slices.pipeline-intelligence.md` (Feature Slices) and authored slice design at `project-documents/user/slices/194-slice.loop-step-type-for-multi-step-bodies.md`. Top-level `loop:` step type with a `steps:` body, symmetric with `each:`. Reuses existing `LoopConfig` / `LoopCondition` / `evaluate_condition` / `ExhaustBehavior` from slice 149's executor — no new loop semantics. v1 bans both nested-loop forms (sub-field on inner step, and inner `loop:` step type) at validation time. Existing single-step `loop:` sub-field unchanged; inline `review:` sub-field on phase steps stays as phase-only sugar. Prerequisite for slice 184 to drive realistic dispatch-then-review convergence rather than re-asking the same review against an unchanged artifact. Effort 2/5. Status: not-started, ready for Phase 5 (task design).

### Slice 194: Loop Step Type for Multi-Step Bodies — Phase 5 Task Breakdown Complete

Authored `project-documents/user/tasks/194-tasks.loop-step-type-for-multi-step-bodies.md` (275 lines, 21 tasks). Tasks follow the test-with pattern — each implementation task is paired with its test task before moving on. Sequence: enum addition → test stub → `LoopStepType` (validate + expand) → validation tests → expand/registration tests → `_execute_loop_body` executor branch → dispatch wiring → registration import → six integration tests covering pass-on-iteration-1, retry-to-PASS-on-N, three exhaustion modes, transient inner failure, checkpoint short-circuit, nested-loop ban (both forms) → regression check on existing single-step loop suite → authoring example in `example.yaml` → schema/loader smoke test → final lint/types/test gate → slice completion + DEVLOG entry. Slice review (verdict FAIL from kimi-k2.6) addressed: F001 rejected on slice-182 precedent (same registry-mediated step-type addition pattern, shipped in same 180 plan); F002 accepted via new "Deferred Interactions with 184/185/188" section that punts multi-step convergence/escalation/persistence cross-product to those downstream slices. Status: in-review, ready for Phase 6 implementation.

### Slice 167: Per-Action Model Override Convention — Design Complete

**Completed:**
- Created `user/slices/167-slice.per-action-model-override-convention.md`
- Enhanced existing stub with full design: data flow, cascade position, code
  change, YAML/params interaction (no loader change required), test list,
  verification walkthrough, and documentation target
- Key technical decision: `params["review_model"]` is a separate params channel
  from `params["model"]`; step-level `review.model: X` wires into `params["model"]`
  (unchanged), while `--param review_model=Y` writes to the new key — no conflict
- `docs/PIPELINES.md` Model Resolution section is the documentation target
- First adopter: `ReviewAction` only; future actions adopt independently

**Design decisions recorded:**
- `review_model` (underscore) is the canonical convention key matching Python dict
  and `--param` syntax; existing `review-model` (hyphen) YAML param continues to
  work via step-level wiring unchanged
- No loader change needed — the two channels are naturally separate by how params
  merge in the executor

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

### Slice 154: Prompt-Only Loops — Design Complete

**Completed:**
- Verified `user/slices/154-slice.prompt-only-loops.md` against current codebase — all technical assumptions confirmed accurate
- Codebase verification: all 5 executor functions to be reused (`_parse_source`, `_SOURCE_REGISTRY`, `resolve_placeholders`, `_unpack_inner_steps`, `_resolve_str`) exist and are module-level; all 3 CLI handlers exist; `ExecutionMode` enum, `EachStepType`, `StepTypeName.EACH` in place
- Schema v4 confirmed current; design's v4→v5 bump plan is correct
- Implementation targets confirmed absent (as expected): `LoopContext` model, `loop_context` field on `RunState` and `StepInstructions`
- Updated frontmatter status from `not_started` to `in_progress`
- Note: Phase 5 task file (`154-tasks.prompt-only-loops.md`) was created in a prior session (20260410) but reverted (`39c575d`) — Phase 5 needs to be re-executed

**Status:**
- Phase 4 complete. Design verified and current. Ready for Phase 5 (task breakdown).

---

### Slice 154: Prompt-Only Loops — Phase 4 Design Refreshed

**Completed:**
- Refreshed `user/slices/154-slice.prompt-only-loops.md` against current codebase state (post slices 153–169)
- Updated data models to use Pydantic `BaseModel` (matching `RunState` pattern, was dataclass)
- Schema version bump: v4 → v5 (was v1 → v2 in original design; actual codebase is now at v4)
- Clarified `StateManager` interaction: `first_unfinished_step` remains loop-unaware; loop logic lives in CLI handlers (`_handle_prompt_only_init`, `_handle_prompt_only_next`, `_handle_step_done`)
- Added `LoopContext` model with cached `items` list for deterministic resume
- Documented reuse of executor internals: `_SOURCE_REGISTRY`, `_parse_source`, `resolve_placeholders`, `_unpack_inner_steps`
- Updated out-of-scope references to reflect completed slices (160 checkpoints, 169 compact dispatch)
- Updated slice plan entry from "Design preserved" to "Design Complete"

**Design decisions (unchanged from original, validated against current code):**
- Loop iterations flattened into instruction stream — callers are loop-unaware
- Step names follow `{inner_step_name}-each-{item_index}` pattern
- Flattened step names go into `completed_steps`; parent `each` step recorded on loop completion
- Source items cached in LoopContext for deterministic resume

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

## 20260422

### Slice 169: Compact Action — SDK Capability Dispatch — Implementation Complete

Implemented `CompactAction` end-to-end as a dedicated pipeline action (separate from `SummaryAction`).
`CompactStepType.expand()` now emits `("compact", ...)` instead of `("summary", emit=[rotate])`.
Two execution branches: when `context.sdk_session is not None`, delegates to existing
`SDKExecutionSession.compact()` rotate flow (unchanged); when None, dispatches `/compact` via
`claude_agent_sdk.query()` and awaits `SystemMessage(subtype="compact_boundary")`, logging
`pre_tokens`/`trigger`/`compacted_at` to `ActionResult.outputs`. Default 120s timeout.
`SummaryAction` gained `restore: true` mode — reads most recent prior `summary` result from
`prior_outputs` and seeds it into the SDK session via `seed_context()`.

**Design simplification during implementation:** T2 (SessionCapabilities), T3 (capability probe),
and T4 (/model investigation) were dropped after PM discussion. The original design called for
reading `slash_commands` from the SDK init message and branching on capability presence. Simplified
to: assume `/compact` is available (SDK v0.0.20+ guarantees it); branch on `sdk_session` presence
instead. `SessionCapabilities` dataclass and `ActionContext.capabilities` field were not added.

**Added:** `src/squadron/pipeline/actions/compact.py` (CompactAction, ~165 lines);
`src/squadron/data/pipelines/test-compact-compose.yaml`; `_render_compact` builder in
`prompt_renderer.py` (emits `trigger: "/compact"` for prompt-only). **Modified:**
`CompactStepType` (new config surface: `model`, `instructions`); `SummaryAction._execute_restore`;
`ActionType` enum (added `COMPACT`); executor imports `actions.compact` to trigger registration;
existing integration test registries gained `"compact": action` entries.

**Tests:** 16 new in `test_compact.py` (action unit); 12 rewritten in `steps/test_compact.py`
(StepType); 3 new in `test_compact_compose_integration.py` (prompt-only + true-CLI compose,
dead-slash-text regression); 6 new restore-mode tests in `test_summary.py`; 1 new registry
integration assertion. **Total: 1665 passing, pyright clean, ruff clean.**

**Docs:** `docs/PIPELINES.md` — compact step section rewritten with environment matrix and
compose pattern; summary section documents `restore: true`; actions table updated.
`CHANGELOG.md` — `[Unreleased]` section describes added capability, restore mode, and
migration note for pipelines that relied on compact's implicit summary. No existing pipeline
YAMLs required migration (audit in T9 found all `compact:` uses were pure context-reduction,
not summary-capture dependencies).

**Commits:** `126a0bf` (CompactAction + step wiring), `e988261` (summary restore mode),
`b5ac797` (compose integration tests + pipeline YAML), `6293ff0` (docs).

---

## 20260415

### Slice 182: Fan-Out / Fan-In Step Type — Implementation Complete

Implemented `fan_out` step type end-to-end. New files: `src/squadron/pipeline/steps/fan_out.py`,
`src/squadron/pipeline/intelligence/fan_in/{__init__,protocol,reducers}.py`. Executor changes:
`_execute_fan_out_step` added to `executor.py`, dispatch branch wired after `each` in
`execute_pipeline`, import triggers added for `fan_out` module and `fan_in.reducers`.
29 new tests (15 step/integration + 14 reducer); 1635 total passing. Pyright and ruff clean.
SDK-session guard wording matches user-facing contract exactly. Slice 189 can register
`merge_findings` reducer at import time with no fan-out infra changes.

**Commits:** `1e138a7` (reducers), `25fff72` (FanOutStepType), `fc60e7b` (executor), `812f2a2` (cleanup)

---

### Slice 182: Fan-Out / Fan-In Step Type — Design + Tasks Complete

Created slice design `user/slices/182-slice.fan-out-fan-in-step-type.md` and task file
`user/tasks/182-tasks.fan-out-fan-in-step-type.md` (14 tasks, 202 lines). Design covers
`FanOutStepType`, `_execute_fan_out_step` in executor, `FanInReducer` protocol, and
`collect`/`first_pass` built-in reducers. Key decisions: reuse `resolver.resolve()` N times
for pool multi-select (no new `PoolBackend` method needed), explicit SDK-session guard (raise
error rather than silently interleave), failure fast-fail before reducer. Unblocks slice 189
(Ensemble Review). Ready for Phase 6 (Implementation).

---

### Slice 168: `sq review code` — Slice Implementation Review — Complete

Added commit-message grep as step 3 in `resolve_slice_diff_range` (`src/squadron/review/git_utils.py`). `sq review code <N>` now resolves a useful diff range for slices merged directly to main with no surviving branch. Single-commit edge case handled via `{sha}^!` syntax. `--fan N` flag added to `sq review code` as a placeholder for slice 182 fan-out; warns and proceeds. 12 new tests (1598 total). All passing, pyright clean.

**Commit:** `b5df568` feat: resolve slice impl diff via commit grep

---

## 20260414

### Slice 181: Pool Resolver Integration and CLI — Implementation Complete

Wired the slice 180 pool infrastructure into the resolver, state, and CLI. Key implementation
decisions: `PoolBackend` protocol and `DefaultPoolBackend` added to new `backend.py` (slice 180
shipped only module-level functions); resolver construction sites are in `run.py` (not
`executor.py`, which accepts a pre-built resolver as a param); `state.py` `_load_raw` uses a
`_SUPPORTED_SCHEMA_VERSIONS = {3, 4}` set to accept both v3 (back-compat) and v4 (new). At
SDK-mode call site, resolver must be built after `init_run` so `run_id` is in scope for the
`on_pool_selection` closure. Pre-existing schema v1 run files produce harmless
"Skipping unreadable state file" log warnings from `list_runs()` — expected, not a bug.
1589 tests passing; 5 commits.

Refactor: consolidated `sq pools show <name>` into `sq pools list [name]` — optional name arg
produces detail view (members + recent selections). Pattern matches `sq models list`. 949 tests
passing; 6 commits. Bump to 0.4.0 — start of significant new functionality (pool-based model
selection).

---

## 20260413

### Slice 180: Model Pool Infrastructure and Strategies — Implementation Complete

Implemented full pool infrastructure in `src/squadron/pipeline/intelligence/pools/`:
5 source files (`models.py`, `protocol.py`, `strategies.py`, `loader.py`, `__init__.py`),
`src/squadron/data/pools.toml` (3 built-in pools), 5 test files (71 new tests, all green).
One bug found during implementation: `tomli_w.dumps()` returns `str` not `bytes` — fixed
with `write_text()` instead of `write_bytes()`. No regressions in the 1478 existing tests.
Patch order for `get_all_aliases` in tests: must patch `squadron.models.aliases.get_all_aliases`
(the source) since loader imports it lazily inside functions.

### Slice 180: Model Pool Infrastructure and Strategies — Design Complete (Phase 5)

Task breakdown complete at `project-documents/user/tasks/180-tasks.model-pool-infrastructure-and-strategies.md`
(28 tasks, 420 lines). Covers: package scaffolding, test infrastructure, data models (`ModelPool`,
`SelectionContext`, `PoolState`), `PoolStrategy` protocol, four built-in strategies (`random`,
`round-robin`, `cheapest`, `weighted-random`), strategy registry, round-robin state persistence,
built-in `pools.toml`, pool loader with alias validation, `select_from_pool` wrapper, and public
API surface. Test-with pattern applied throughout; 5 intermediate commits defined.
Implementation is slice 181's blocker for pool resolver integration.

---

## 20260412

### Slice 191: Dispatch Summary Context Injection — Complete (Phase 6)

Fixed the root cause of empty/hallucinated non-SDK summary output: one-shot
models received only the compaction template instructions with zero pipeline
context. Added `src/squadron/pipeline/summary_context.py` — a pure function
`assemble_dispatch_context` that iterates `prior_outputs` and assembles prior
dispatch responses, review verdicts/findings, and `build_context` stdout into
a delimited context block prepended to non-SDK summary instructions. SDK path
(has session history) is completely unmodified. 13 unit tests, 2 integration
tests, all 623 pipeline tests green, ruff clean. Verified with a live minimax
run: model correctly summarized the dispatch response and accurately reported
it had no slice 191 content (the test pipeline used an unrelated prompt).

Also added `dispatch` as a first-class YAML step type (previously only an
internal `ActionType`). Accepts optional `prompt` and `model`; expands to a
single dispatch action. Required to make Verification Walkthrough scenarios
runnable directly. 8 new tests.

Fixed a `/sq:summary --restore` hallucination bug (v0.3.13): CLI only emitted
the selected filename to stderr in the multi-match case; single-match was
silent, causing the model to use the nearby example value verbatim. Always emit
`Using: {name}` to stderr; slash command now parses it explicitly and errors if
absent. Added "Hallucination traps in prompts" rule to CLAUDE.md.

---

### Slice 191: Dispatch Summary Context Injection — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/191-tasks.dispatch-summary-context-injection.md` (171 lines, 7 tasks)
- Tasks cover: new `summary_context.py` module (T1), unit tests for assembler (T2),
  integration into `_execute_summary()` (T3), integration tests (T4), full verification
  and commit (T5), end-to-end verification (T6), slice completion (T7)
- Implementation note captured: `ActionType` has no `COMPACT` entry; compact steps
  expand to `"summary"` action type — the `match/case` only needs `ActionType.SUMMARY`

**Status:**
- Phase 5 complete. Ready for Phase 6 (implementation).

---

### Slice 191: Dispatch Summary Context Injection — Phase 4 Design Complete

**Completed:**
- Created `user/slices/191-slice.dispatch-summary-context-injection.md`
- New module `pipeline/summary_context.py` with `assemble_dispatch_context()` — pure function that extracts content from `prior_outputs` by action type (dispatch responses, review findings, build_context text, prior summaries) and assembles a delimited context block
- Integration point: `_execute_summary()` prepends context block to instructions for non-SDK profiles only; SDK path unchanged
- Dependencies: slices 161 (summary step) and 164 (profile-aware routing), both complete

**Design decisions:**
- Context prepended to instructions (not a separate system message) — keeps `capture_summary_via_profile` interface unchanged across providers
- Full artifact contents injected, not metadata summaries — the summary model's job is to summarize
- No YAML configuration — context injection is unconditional for non-SDK profiles
- `match/case` on `ActionType` enum for extraction dispatch, not string labels

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

## 20260411

### Slice 166: Compact and Summary Unification — Complete (Phase 6)

Completed the runtime unification of `compact` and `summary`. Deleted
`CompactAction`, `ActionType.COMPACT`, `_render_compact`, and both
compact action test files (~780 lines net deleted). Moved template
helpers (`CompactionTemplate`, `load_compaction_template`,
`render_instructions`, `_parse_template`) from `actions/compact.py`
into a new `src/squadron/pipeline/compaction_templates.py` module;
updated all five consumers to import from the new home.

Rewrote `CompactStepType.expand()` to return `("summary", {...,
"emit": ["rotate"]})` instead of `("compact", ...)`. Rewrote
`StateManager._maybe_record_compact_summaries` gate to fire on
`action_type="summary"` with a successful rotate emit entry in
`emit_results` — the one real risk in the slice. Removed the
`### compact` section from `commands/sq/run.md` and refreshed the
installed copy.

Prompt-only smoke test confirmed: `compact-1` step in P6 now renders
as `action_type="summary"`, `emit=["rotate"]`, no `/compact [` in
any command field. All 1455 tests green, pyright clean, ruff clean.

No surprises. Pipeline YAML files (P6, slice, tasks, app, example)
all validate cleanly — `compact:` keyword still parses.

### Slice 166: Compact and Summary Unification — Task Breakdown Complete (Phase 5)

Broke slice 166 into a single task file at
`project-documents/user/tasks/166-tasks.compact-and-summary-unification.md`
(26 tasks, 6 commit checkpoints, ~510 lines). Kept it as one file after
weighing against the 450-line guideline — splitting added more friction
than it solved for this size.

Task groups follow the migration order from the slice doc's
Implementation Notes: (1) survey call sites, (2) extract template
helpers into a new `compaction_templates.py` module and update every
import before touching runtime code, (3) rewrite
`CompactStepType.expand()` and the `_maybe_record_compact_summaries`
gate with paired tests, (4) delete `_render_compact` and add a
prompt-only renderer smoke test, (5) delete `CompactAction`,
`ActionType.COMPACT`, and compact-specific tests, (6) clean up
`commands/sq/run.md`, (7) pipeline validation + E2E smoke tests in
both prompt-only and SDK modes + grep verification + full quality
gate, (8) arch doc verification and slice/DEVLOG wrapup.

Test-with pairing honored throughout: each rewrite (step expand,
state gate, `_render_compact` removal) has its tests as the immediate
successor task. The state gate test specifically covers the slice's
one real risk — summary action with rotate emit must still populate
`RunState.compact_summaries` for resume-with-reinjection.

Next: Phase 6 implementation.

### Slice 166: Compact and Summary Unification — Review PASS (1 concern addressed)

Review verdict PASS (glm5). Eight findings: seven pass, one note, one concern.

Concern F004 (documentation-sync): `140-arch.pipeline-foundation.md` lists
compact as a distinct action type in two places flagged by the reviewer, plus
two additional locations I found when auditing: action registry table (line
106), detailed compact-action subsection (lines ~246-251), action type diagram
(line 514), and `actions/compact.py` package entry (line ~549). Addressed by
adding a new §"Architecture Document Updates" section to the slice design with
a concrete change checklist and explicit out-of-scope list (compaction as
concept, `compact:` YAML examples, and step-type-layer references all stay).
Arch doc updates land during Phase 6 implementation alongside the code changes,
keeping doc and code in sync rather than drifting during the implementation
window. New success criterion #11 verifies the arch doc is updated.

Review: `project-documents/user/reviews/166-review.slice.compact-and-summary-unification.md`.

### Slice 166: Compact and Summary Unification — Design Complete

Added slice 166 to `140-slices.pipeline-foundation.md` and designed it at
`project-documents/user/slices/166-slice.compact-and-summary-unification.md`.

Finishes the abandoned refactor from slice 161. Today compact and summary are
two half-merged code paths: SDK mode already delegates compact to summary
internally, but prompt-only mode still renders a broken `/compact [...]` slash
command string. This breaks P6 and every pipeline using `compact:`.

Design: rewrite `CompactStepType.expand()` to emit a summary action with
`emit=[rotate]` instead of a compact action. Delete `CompactAction`,
`ActionType.COMPACT`, `_render_compact`, the compact test class, and the compact
section of `commands/sq/run.md`. `compact:` YAML continues to parse — it becomes
a pure two-word alias with no unique code below the step-expansion layer.

One real risk: `state.py::_maybe_record_compact_summaries` is gated on
`ar.action_type == "compact"`. After the refactor no action is compact-typed, so
the gate must switch to "summary action whose emit includes rotate" to preserve
resume-with-reinjection. Called out explicitly in the design with its own
targeted integration test. No schema version bump — field names and shapes
unchanged.

Template helper functions (`load_compaction_template`, `render_instructions`)
must be moved out of `actions/compact.py` before the file can be deleted, since
the summary action imports them.

Priority: implement before continuing 180-band work — P6 is currently broken in
prompt-only mode.

Marked slice plan 140 frontmatter `status: in_progress` (was `complete`). Slice
plan entry numbering updated: 166 added as item 23, Integration Work item 152
bumped from 23 to 24.

---

### Slice 181: Pool Resolver Integration and CLI — Design Complete

Created `project-documents/user/slices/181-slice.pool-resolver-integration-and-cli.md`.

Design extends `ModelResolver` with `pool_backend` and `on_pool_selection` callback params.
`_resolve_pool()` delegates to `PoolBackend.select()` (slice 180), then resolves the returned
alias through the existing alias registry — transparent to all action handlers. `RunState` gains
`pool_selections: list[dict]` with schema version bump to 4 (backwards-compatible). New
`sq pools` CLI (list / show / reset) follows the `sq models` pattern. Executor wires up
`PoolLoader.load()` and the logging callback when building `ModelResolver`.

---

### Slice 160: Interactive Checkpoint Resolution — Implementation Complete

Phase 6 complete. Three files changed:

- `executor.py`: Added `CheckpointResolution(StrEnum)`, `CheckpointDecision` dataclass,
  `_is_interactive()`, `_prompt_checkpoint_interactive()`. Modified `_execute_step_once`
  checkpoint detection block to call the handler; EXIT path returns PAUSED (unchanged),
  Accept/Override inject `override_instructions` into `merged_params` and continue.
- `actions/dispatch.py`: `_resolve_prompt` now reads `override_instructions` from
  `context.params` and prepends a delimited block when present.
- `prompt_renderer.py`: `_render_checkpoint` now describes all three options per trigger
  type. `run_id` injected into `render_params` so the resume command is correct.

All 1477 tests pass. `pyright` clean. No `RunState` schema change (stays v3).

---

### Slice 160: Interactive Checkpoint Resolution — Design Complete

Created `project-documents/user/slices/160-slice.interactive-checkpoint-resolution.md`.

Design confines the change to three files: `executor.py` (interactive handler +
`CheckpointResolution`/`CheckpointDecision` types), `actions/dispatch.py` (pick up
`override_instructions` from params), and `prompt_renderer.py` (enhanced checkpoint
instruction text). The Accept/Override path injects instructions into `merged_params` and
continues in-place; the Exit path is unchanged. No `RunState` schema bump required.
Updated slice plan entry 18 with Design Complete pointer.

---

### CHANGELOG rewrite — user perspective

Rewrote all CHANGELOG entries to answer "what can I do / what bug is fixed"
rather than listing internal class names, module paths, and slice refs.
Net: 338 lines removed, changelog is now readable without source context.

---

### Slice 164 implementation complete: profile-aware summary model routing

**Slice 164 — Phase 6 complete.**

- **What changed:**
  - New module `src/squadron/pipeline/summary_oneshot.py`:
    `is_sdk_profile()` predicate and `capture_summary_via_profile()` —
    near-copy of the ~40 relevant lines from `run_review_with_profile()`,
    review-specific paths stripped.
  - `_execute_summary()` now branches on resolved profile: SDK path
    (profile `None` or `"sdk"`) keeps `sdk_session.capture_summary()`;
    non-SDK path dispatches through the provider registry via
    `capture_summary_via_profile()`.
  - Rotation emit + non-SDK profile fails fast with a descriptive error
    at execution time (resolver not available at schema-validation time).
  - `_render_summary()` in `prompt_renderer.py` emits `model_switch` for
    SDK profiles and `command` (runnable `sq _summary-run …`) for
    non-SDK profiles.
  - New hidden CLI subcommand `sq _summary-run` (registered alongside
    `sq _summary-instructions`) as the CLI surface for prompt-only
    non-SDK summary execution.
  - `CompactAction` inherits the fix for free via the shared
    `_execute_summary()` helper.
  - 1452 tests pass; pyright and ruff clean.

- **OQ1 resolved:** Option A — new hidden `sq _summary-run` subcommand,
  matching the `_summary-instructions` naming convention. The subcommand
  name uses leading underscore (`_summary-run`) per project convention.

- **Surprises:**
  - `compact.py` imports `_execute_summary` inside the method body
    (deferred import), so tests must patch
    `squadron.pipeline.actions.summary._execute_summary`, not
    `squadron.pipeline.actions.compact._execute_summary`.
  - `--validate` in `sq run` only calls schema-level `validate()` — the
    rotate+non-SDK profile check fires at execution time, not validation
    time (resolver is execution-time only). Slice doc updated with
    caveat.

- **Pipelines unblocked:** Any pipeline summary step can now use cheap
  external models (minimax, gemini-flash, local) via their respective
  profiles. The only restriction is `emit: [rotate]`, which remains
  SDK-only.

---

### Slice 164 design + tasks; CI fix; phase pipelines now write summary files

**v0.3.8 release.**

- **Slice 164 (Profile-Aware Summary Model Routing)** — Phase 4 design
  and Phase 5 task breakdown complete via `/sq:run P4 164` and
  `/sq:run P5 164`. Both phases reviewed PASS by minimax-m2.7. Slice
  routes the summary action through the provider registry for non-SDK
  profiles, mirroring `run_review_with_profile()`. New module
  `summary_oneshot.py` houses `capture_summary_via_profile()` and the
  `is_sdk_profile()` predicate. 17 implementation tasks in
  `164-tasks.profile-aware-summary-model-routing.md`. Implementation
  deferred (Phase 6 not yet started).
- **CI fix** — `prompt_renderer.py:270` had a `dict[str, object]`
  narrow that pyright couldn't infer through; added
  `cast(list[object], emit_raw)` after the `isinstance(list)` check.
  Seven consecutive `main` builds had been red on this same error.
- **Phase pipelines now write summary files** — after re-running
  `sq install-commands` to refresh stale `summary.md` and `run.md`
  skills, discovered that all five phase pipelines (P1, P2, P4, P5, P6)
  emit only `[stdout, clipboard]` and never `[file]` — so slice 163's
  default-file-path branch had nothing to write to. Added `file` to
  every P*.yaml emit list. `/sq:summary --restore` now works
  end-to-end after any phase pipeline run.

**Commits:**
- `5d7ab9d` docs: add slice 164 profile-aware summary model routing design
- `32fc9e7` fix: cast emit list to satisfy pyright in _render_summary
- `f8c887a` docs: add slice 164 task breakdown
- (this commit) feat: emit pipeline summaries to file + bump to v0.3.8

## 20260410

### Slice 163: Pipeline Run Summary Persistence and Restore — Complete

**Phase 6 (implementation) complete.**

- Closes the "run pipeline in CLI terminal, restore context in VS Code" workflow gap
- Three implementation sites: `emit.py` (default file path), `executor.py` (_project injection), `summary_instructions.py` (--restore), `commands/sq/summary.md` (--restore branch), `commands/sq/run.md` (file-write step)
- Key decision: bare `"file"` in `emit:` YAML list now produces `EmitDestination(kind=FILE, arg=None)` rather than raising; default path is `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`
- `_project` threaded into `ActionContext.params` via `gather_cf_params()` at pipeline init in `executor.py`; falls back to `"unknown"` when CF unavailable; caller-supplied `_project` not overwritten
- 31 new tests added (28 in test_emit.py, 3 in test_executor.py, 5 in test_summary_instructions.py)

**Commits:**
- `51a3342` feat: add default summaries path to emit and thread _project into ActionContext
- `1d6281f` feat: add --restore to /sq:summary and write summary to conventional path in run.md


**tasks: devlog-4**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: UNKNOWN)
- checkpoint-5: PASS
- commit-6: PASS
- compact-0: PASS

### Slice 152: Pipeline Documentation and Authoring Guide — Complete

**Deliverables created:**
- `docs/PIPELINES.md` — authoritative pipeline authoring guide (Quick Start, YAML Grammar, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Custom Pipeline Walkthrough, Prompt-Only Mode)
- `README.md` — added `## Pipelines (sq run)` section with quick-start and link to guide

**Discrepancies found during T1 verification (documented, not propagated from slice design):**
- `slice` pipeline has 2 params (`slice`, `review-model`); slice design table listed only `slice`
- `tasks`, `P5`, `P6` each have 3 params including `model`; design table showed 2
- `example.yaml` inline comment shows stale project path (`.squadron/pipelines/`); loader uses `project-documents/user/pipelines/` — guide uses loader path
- `app.yaml` is a WIP pipeline (same description as design-batch, has TODO comment) — excluded from docs

**Commits:**
- `4056c7b` docs: add pipeline authoring guide
- `5460177` docs: add sq run section to README

### Slice 163: Pipeline Run Summary Persistence and Restore — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/163-tasks.pipeline-run-summary-persistence-and-restore.md` (158 lines, 14 tasks)
- Tasks cover: source verification (T1), emit.py changes (T2–T4), _project threading (T5–T6), commit (T7), summary_instructions --restore (T8–T9), summary.md --restore branch (T10), run.md alignment (T11), commit (T12), verification (T13), slice completion (T14)
- Test-with pattern: T4 follows T3, T6 follows T5, T9 follows T8
- Review: PASS (minimax). One NOTE addressed: T11 updated to remove stale `_precompact-hook` reference (removed in slice 162); uses `cf status` for project name resolution instead

**Status:**
- Phase 5 complete. Ready for Phase 6 (implementation).

---

### Slice 163: Pipeline Run Summary Persistence and Restore — Phase 4 Design Complete

**Completed:**
- Created slice design at `user/slices/163-slice.pipeline-run-summary-persistence-and-restore.md`
- Added slice overview to `140-slices.pipeline-foundation.md` as entry 23 (index 163)
- Fixed `run.md` clipboard bug: summary action handler now uses `pbcopy`/`xclip`/`wl-copy` via Bash instead of telling the user to copy manually

**Design decisions:**
- Default `emit: [file]` path: `~/.config/squadron/runs/summaries/{project}-{pipeline}.md` (latest-only overwrite)
- Restore via `/sq:summary --restore` — reads most recent summary for current project, no run-id needed
- Project name resolved from CF via `gather_cf_params()` (existing helper)
- Prompt-only `run.md` handler writes to same conventional path via Bash
- `_project` threaded as internal param through `ActionContext` during pipeline init

**Status:**
- Phase 4 complete. Ready for review, then Phase 5 (task breakdown).

---

### Slice 152: Pipeline Documentation and Authoring Guide — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/152-tasks.pipeline-documentation-and-authoring-guide.md` (172 lines, 14 tasks)
- Tasks cover: source artifact verification, `docs/PIPELINES.md` creation (Quick Start, YAML Grammar, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Custom Pipeline, Prompt-Only Mode), README.md update, final verification walkthrough, and DEVLOG
- Verification tasks follow each major section (T1 verifies source before writing; T12 runs the full design walkthrough; T13 verifies README)
- No code changes in this slice — documentation only

**Key notes:**
- T1 (source verification) must be completed before writing documentation — particularly to confirm ActionType enum, registered step types, and built-in pipeline file list match the slice design
- The YAML quoting footgun for parameter placeholders must be prominent in the grammar section
- `test-pipeline.yaml` and `app.yaml` in pipelines/ are not for user documentation; exclude from the built-in pipelines table

**Status:**
- Phase 5 complete. Ready for Phase 6 (Slice Execution).

---

### Slice 154: Prompt-Only Loops — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/154-tasks.prompt-only-loops.md` (260 lines, 19 tasks)
- Tasks follow test-with pattern: each implementation task is immediately followed by its tests before the next implementation task
- Commit checkpoints placed after coherent logical units (state model, state manager methods, render function, each CLI handler, integration test, closeout)
- No schema version bump needed — `LoopContext` additive with `None` default on `RunState`
- Key implementation sequence: `LoopContext` model → `StateManager` loop methods → `LoopInstructionContext` + `render_each_step_instructions()` → `executor.py` rename → `_handle_prompt_only_init` → `_handle_prompt_only_next` → `_handle_step_done` → integration test → verification walkthrough

**Status:**
- Phase 5 complete. Ready for Phase 6 (Slice Execution).

---

### Slice 154: Prompt-Only Loops — Design Complete (Refreshed)

**Completed:**
- Recreated slice design document at `user/slices/154-slice.prompt-only-loops.md` (previous version was deleted from working tree)
- Design refreshed to reflect current codebase state: schema v3 (no version bump needed — `LoopContext` is additive with `None` default), existing `CompactSummary` pattern, `ExecutionMode` enum
- Core design unchanged from original: flatten `each` loop iterations into prompt-only instruction stream via `LoopContext` state tracking
- Key implementation points: `LoopContext` Pydantic model on `RunState`, `render_each_step_instructions()` in prompt renderer, loop-aware `--step-done` advancement, cached collection items in state for deterministic resume
- Slice plan entry at `140-slices.pipeline-foundation.md` already has materialized index (154) and design-complete link

**Status:**
- Design complete. Ready for Phase 5 (Task Breakdown).

---

## 20260409

### Slice 162: /sq:summary — Clipboard Summary for Manual Context Reset

**Phase 4 (design) + Phase 5 (task breakdown) + Phase 6 (implementation) complete.**

- Motivated by unreliable `/compact [with instructions]` — user wants deterministic "clear with custom summary" using templates already built for pipeline compaction (slices 157/158)
- Design: slash command `/sq:summary [template]` + hidden `sq _summary-instructions` CLI. Current CC session generates the summary inline; squadron supplies template instructions + clipboard sink.
- Created `pipeline/summary_render.py` with `resolve_template_instructions()` and `gather_cf_params()` — logic salvaged from dead `precompact_hook.py`
- Removed `precompact_hook.py`, `install_settings.py`, and all PreCompact hook install/uninstall logic (dead code since 0.3.3)
- Reuses `compact.template` config key — no new config surface
- Clipboard via shell chain: `pbcopy` → `xclip` → `wl-copy` (Windows deferred)
- All 1400 tests pass, ruff clean, pyright clean
- Post-implementation: removed misleading "do not print to chat" instruction from summary.md — summary appearing in chat is correct and lets user verify before `/clear`; bumped to v0.3.4

## 20260408

**v0.3.3 release — merge, tag, PyPI publish**

- Caught that dispatch fix landed on `test-161-pipeline` instead of `161`; cherry-picked `07881d5` → `210950d`
- Bumped version 0.3.2 → 0.3.3, merged `161-slice.summary-step-with-emit-destinations` → main, tagged `v0.3.3`
- CI: both push and tag runs triggered; `publish` job succeeded; `squadron-ai==0.3.3` live on PyPI
- Verified full pipeline smoke test end-to-end (design → tasks → summary:rotate → design again) on separate branch; discarded test branch
- CHANGELOG restructured: collapsed duplicate `[Unreleased]` sections into proper versioned entries; fixed orphaned `## [Unreleased]` mid-file (was 0.2.7-era content); made entries more concise for human readers
- **Latent bug fixed:** `DispatchAction` — Claude CLI surfaces API errors (e.g. 500) as assistant text with `"API Error:"` prefix; dispatch was returning `success=True`, allowing review/checkpoint to run against a non-existent output file. Added `_check_cli_error()` detection in both session and agent paths.

### Slice 161: Summary Step with Emit Destinations — Complete

**Commits (8 slice commits):**
- `877f1e6` chore: add pyperclip dependency for summary clipboard emit
- `2bbbcb7` feat: add SDKExecutionSession.capture_summary() method
- `1a953ae` feat: add summary= overload to SDKExecutionSession.compact()
- `6f78e1e` feat: add emit destination registry and types
- `76b0e65` feat: add SummaryAction with config validation
- `9b043a7` feat: implement _execute_summary shared helper
- `c613422` feat: wire SummaryAction.execute to shared helper
- `7293394` feat: add SummaryStepType, register summary action+step, validate emit, update test-pipeline

**Delivered:**
- `SDKExecutionSession.capture_summary()` — captures summary without rotating session
- `SDKExecutionSession.compact(summary=...)` — `summary=` overload skips capture phase for reuse
- `emit.py` — `EmitKind` registry with stdout, file, clipboard (pyperclip), rotate destinations
- `actions/summary.py` — `SummaryAction` + `_execute_summary()` shared helper; single capture, multi-destination dispatch; rotate failures fail the action, others log warning
- `CompactAction` SDK path refactored to delegate into `_execute_summary()` with `emit=[rotate]`; `action_type` kept as `"compact"` — state persistence unaffected
- `SummaryStepType` with `emit` validation and `checkpoint:` shorthand (expands to summary + checkpoint action pair)
- `test-pipeline.yaml` updated to use `summary:emit:[rotate]` in place of `compact:`
- 1429 tests passing; pyright clean; ruff clean

**Pending / deferred:**
- T15 manual smoke test (`sq run test-pipeline 154 -vv`) deferred — requires live Claude SDK session; no blockers
- `clear` follow-up (rotate without seeding) not yet filed as a slice; design open question from 161 slice doc

---

## 20260407

**Slices 158, 159: Pipeline plan additions**
Added two new feature slices to `140-slices.pipeline-foundation.md`. Slice 158 (Pipeline Fan-Out / Fan-In Step Type) — general parallel branch infrastructure with pluggable fan-in reducer; ships with identity reducer, consensus reducer is a stub for 160; demonstrates with N>1 reviews against multiple models; foundational for consensus review infrastructure. Slice 159 (Interactive Checkpoint Resolution) — replace pause-and-exit with interactive prompt offering accept/override/exit options; first two avoid the full resume cycle. Both slices need design (Phase 4) before implementation.

**Slice 157: SDK Session Management and Compaction — Design Updated (Phase 4 revision)**
Revised `157-slice.sdk-session-management-and-compaction.md` to address two review concerns: (1) checkpoint resume after compact loses the summary because the previous process's session is gone — fixed by persisting compact summaries in a new keyed `compact_summaries` dict on `RunState` (schema bump v2 → v3); (2) executor-owned re-injection on resume via a new `seed_context()` session method. Keying scheme `{step_index}:{step_name}` is forward-compatible with slice 158 fan-out branches (will extend with `#branch{n}` suffix). Added `CompactSummary` dataclass, `record_compact_summary` state manager method, and `active_compact_summary_for_resume` helper. Re-reviewed task breakdown follows in same session.

**Slice 157: SDK Session Management and Compaction — Task Breakdown Updated (Phase 5 revision)**
Expanded `157-tasks.sdk-session-management-and-compaction.md` from 11 tasks to 18 to cover the design revision: T2/T3 add `CompactSummary` dataclass, schema v3 bump, state manager persistence and lookup helpers; T7 adds `seed_context()` method; T11 wires the compact summary persistence via the executor's `on_step_complete` callback (action stays free of state-manager coupling); T12 implements executor resume injection; T14 adds an automated integration test for the full session rotate flow; T15 adds an automated test specifically for resume-after-compact. T13 (PreCompact hook) retains its investigation-first note. Test-with pattern throughout; 452 lines.

### Slice 157: PreCompact Hook for Interactive Claude Code — Phase 6 Implementation Complete

**Completed:**
- All 15 tasks (T1–T15) in `user/tasks/157-tasks.precompact-hook-for-interactive-claude-code.md` implemented and marked complete.
- New shared module `src/squadron/pipeline/compact_render.py` with `LenientDict` + `render_with_params`, extracted from `actions/compact.py`. Both the compact action and the PreCompact hook consume it.
- New hidden Typer subcommand `sq _precompact-hook` (registered on the top-level app with `hidden=True`). Not listed in `sq --help`; direct invocation still works. Emits the Claude Code `PreCompact` payload on stdout, always exits 0.
- New module `src/squadron/cli/commands/install_settings.py` with `settings_json_path`, `_load_settings`, `_save_settings`, `write_precompact_hook`, `remove_precompact_hook`, and `_is_squadron_entry`. Squadron owns its entry in `.claude/settings.json` via a `_managed_by: "squadron"` marker; third-party hooks are preserved on both install and uninstall.
- `sq install-commands` / `sq uninstall-commands` extended with `--hook-target` option (default `./.claude/settings.json`). Installation is idempotent; uninstall tidies `hooks.PreCompact` and `hooks` keys when they become empty.
- Two new config keys: `compact.template` (default `"minimal"`) and `compact.instructions` (default `None`). Literal wins at resolve time.
- `_gather_params` uses best-effort `ContextForgeClient()` with `os.chdir` context management (the CF client has no `cwd` kwarg — task file's pseudocode was updated in practice to match the real API). Catches `ContextForgeError`, `ContextForgeNotAvailable`, `FileNotFoundError`, `OSError`.
- Empty CF values (e.g. `slice=""` as the current squadron project reports) are **omitted** from params so `{slice}` renders as a literal placeholder rather than empty text — discovered during smoke testing and fixed in T14.
- README updated with "Interactive `/compact` for Claude Code" section.
- Full test suite: 1315 passed, 0 failures. Pyright: 0 errors. Ruff: clean.

**Commits on `157-slice.precompact-hook-for-interactive-claude-code` branch:**
- `feat: add compact.template and compact.instructions config keys`
- `refactor: extract LenientDict and render_with_params to compact_render module`
- `feat: add hidden _precompact-hook subcommand for interactive Claude Code`
- `feat: add settings.json merge helpers for PreCompact hook install`
- `feat: install PreCompact hook entry during sq install-commands`
- `docs: document PreCompact hook and compact config keys`
- `chore: rename hook helpers to public names to satisfy pyright`
- `fix: omit empty CF params so PreCompact hook preserves placeholders`
- `docs: mark slice 157 PreCompact hook for interactive Claude Code complete` (pending)

**Deviations from task file:**
- Renamed module-public helpers from `_write_precompact_hook` / `_remove_precompact_hook` / `_settings_json_path` to non-underscored names because pyright's `reportPrivateUsage` flagged cross-module usage with leading underscores. Functionally identical; names reflect convention more accurately.
- Tests for T3/T4/T5 and the module file itself were combined into one commit because all three helpers live in the same file; splitting would have been artificial.
- Test T14 revealed the CF empty-string behavior, which was fixed in `_gather_params` with a tiny non-destructive change: only populate `slice` and `phase` when truthy.
- Also moved the `patch_config_paths` fixture from `tests/config/conftest.py` up to `tests/conftest.py` so CLI command tests can reuse it.

**Smoke tested (automatable parts):**
- `sq install-commands` writes the expected `.claude/settings.json` shape.
- `sq _precompact-hook` emits valid JSON with `hookEventName == "PreCompact"`.
- `{slice}` placeholder preserved when CF reports empty slice.
- Literal `compact.instructions` override wins over template.
- `sq --help` hides the command; `sq _precompact-hook --help` still works.
- `sq uninstall-commands` cleanly removes the entry.

**Not verified (requires human in the loop):**
- Step 6 of the verification walkthrough: real `/compact` in an interactive VS Code Claude Code session or `claude` CLI. Flagged in the slice design for follow-up. The hook payload schema (`hookSpecificOutput.additionalContext`) is based on Claude Code docs; if it turns out to differ, the fix is a single line in `precompact_hook.py` plus one test update.

**Status:**
- Slice 157 complete. Slice plan `140-slices.pipeline-foundation.md` slot 157 checked off.
- Branch: `157-slice.precompact-hook-for-interactive-claude-code` — ready for merge to `main` pending the human-driven `/compact` smoke test.

---

## 20260406

**Slice 157: SDK Session Management and Compaction — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/157-tasks.sdk-session-management-and-compaction.md`. 11 tasks (T1–T11): capture `session_id` from `ResultMessage` in translation (T1); add `session_id` and `options` fields to `SDKExecutionSession` (T2); pass options into session from `_run_pipeline_sdk` (T3); implement `compact()` session rotate method (T4); remove `configure_compaction()` stub (T5); add `model` field to compact step YAML (T6); wire compact action to call `session.compact()` (T7); register `PreCompact` hook for interactive instruction injection (T8); end-to-end smoke test via test-pipeline (T9); lint/type-check/full suite (T10); closeout (T11). Test-with pattern throughout; commits after each implementation+test pair. Note: T8 includes verification-before-implement note for the `PreCompact` hook return format as that API detail needs confirmation.

**Slice 157: SDK Session Management and Compaction — Design Complete (Phase 4)**
Created `project-documents/user/slices/157-slice.sdk-session-management-and-compaction.md`. Core approach: session rotate compaction at pipeline step boundaries. When compact step executes, switch model to cheap summarizer (e.g. haiku) in the *current* session, query with compact template instructions, capture summary, disconnect, start fresh session seeded with summary. Key insight: summarize in the live session (model has full context) rather than resuming in a new process (loads entire context just to read it). Also wires `PreCompact` hook for interactive `/compact` instruction injection. Adds optional `model` field to compact YAML. Removes unconnected `configure_compaction()` stub from slice 155. Agent SDK investigation confirmed: no `context_management`, no `compaction_control`, no threshold control — session rotate is the only deterministic compaction path. Dependencies: [155, 156]. Effort: 3/5.

## 20260405

**Fix: validate pipeline before execution, not just `--validate`**
`_run_pipeline` now calls `validate_pipeline()` before `execute_pipeline()`, so invalid action parameters (e.g. `checkpoint: concerns` instead of `on-concerns`) are caught with a clear error before execution begins. Previously validation only ran for `--validate` and `--dry-run`. Also added defense-in-depth in `CheckpointAction.execute()` — invalid trigger values now return `ActionResult(success=False)` instead of an unhandled `ValueError`. 1253 tests pass.

**Slice 154: Prompt-Only Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/154-slice.prompt-only-loops.md`. Slice extends slice 153's prompt-only mode to transparently support `each`/collection loops. Core design: `EachLoopState` dataclass tracks iteration context (current item index, inner step name, cached source query results) persisted in `RunState`; `render_each_step_instructions()` resolves CF source queries on first entry; placeholder resolution enhanced to support `{param.field}` dot-path syntax for item binding; `StateManager` methods `first_unfinished_step()` and `advance_iteration()` handle navigation within/across iterations. To the caller, loops are transparent — each `--next` returns the next instruction in flattened execution order, whether it's a new step or next iteration. Model switching is informational only (slash command handles manually). Technical decisions documented: transparent iteration, params-based item binding, single-depth loops (nesting deferred to 160), convergence strategies stubbed (160 scope). Data flows, state persistence format, and integration points detailed. Ready for Phase 5 (task breakdown) and Phase 6 (implementation). Effort: 2/5, risk: low.

**Slice 156: Pipeline Executor Hardening — Implementation Complete (Phase 6)**
Implemented all 14 tasks. `ExecutionMode` StrEnum added to `state.py`; `RunState` schema bumped to v2 with `execution_mode` field (default `SDK` for forward-compat with v1 files); `init_run` gains `execution_mode` param and `pipeline_name.lower()` normalisation. `_run_pipeline` gains `run_id` param (skips `init_run` when provided); `_run_pipeline_sdk` gains `run_id` param and forwards with `execution_mode=SDK`. Both `--resume` and implicit resume paths rewritten to dispatch via `match state.execution_mode:` — no string literals. `_handle_prompt_only_init` records `PROMPT_ONLY`. `load_pipeline` and `discover_pipelines` normalise names to lowercase; CLI `run()` normalises at `--validate`, `--dry-run`, `--prompt-only`, and standard execution entry points. `--status` output includes `Mode:` line. 1251 tests pass; pyright zero errors; ruff clean. Branch: `156-slice.pipeline-executor-hardening`.

### Slice 154: Prompt-Only Loops — Design Complete

**Completed:**
- Created comprehensive slice design document at `user/slices/154-slice.prompt-only-loops.md`
- Detailed design for extending prompt-only executor (slice 153) with collection loop support
- State schema extension: `RunState` with `LoopContext` field for tracking loop progress across `--next` calls
- Loop iteration tracking: Inner steps within `each` blocks named with iteration index (e.g., `design-each-0`, `tasks-each-1`)
- Successive iteration as instruction stream: Caller doesn't need loop awareness, just calls `--next` repeatedly
- Step instruction output format extended: JSON includes `loop_context` with current item data and loop position
- State persistence for loop resume: Saved loop state allows resuming mid-iteration without re-querying collection
- Verification walkthrough with concrete examples: 6-step scenario (3 items × 2 inner steps)
- Integration: Slash command (`/sq:run`) automatically compatible with loops (no changes needed)

**Status:**
- Design complete and ready for Phase 5 (Task Breakdown)
- Slice plan entry updated: `140-slices.pipeline-foundation.md` now marks slice 154 complete with link to design

**Key Design Decisions:**
- **Loop iterations flattened into instruction stream:** Progressive `--next` calls return successive iteration steps as if sequential. Caller logic unchanged.
- **LoopContext in RunState:** Tracks current item, item index, completed items, total items. Allows mid-loop resume without re-execution or re-querying.
- **Step naming with iteration index:** `{step_name}-each-{item_index}` ensures uniqueness and traceability across iterations.
- **Prompt-only loop output includes item data:** JSON `loop_context` field contains the bound item's resolved fields (e.g., `slice.index: "151"`).
- **No convergence strategies in prompt-only mode:** Falls back to basic max-iteration (inherited from slice 149). Convergence is SDK executor (slice 155) scope.
- **Variables resolved at instruction-generation time:** Bound item fields like `{slice.index}` are replaced in instruction JSON, not left as placeholders.
- **Collection items persisted in state:** Avoids re-querying CF mid-loop. Enables fast resume and deterministic iteration order.

**Dependencies:**
- Slice 153 (Prompt-Only Pipeline Executor) — prerequisite, extends `render_step_instructions()` and state model
- Slice 149 (Pipeline Executor and Loops) — loop execution logic reference; prompt-only mirrors this behavior
- Slice 150 (Pipeline State and Resume) — extended `RunState` schema with loop context
- Slice 126 (CF Integration) — collection sources (`cf.unfinished_slices()`)

**Architecture Overview:**
- No new modules; extends existing `prompt_renderer.py` with loop awareness
- `LoopContext` dataclass added to `models.py` for state tracking
- `StepInstructions` output extended with `loop_context` field (JSON-serializable)
- `StateManager.record_step_done()` enhanced to detect iteration-pattern step names and update `loop_context.completed_items`
- State file schema versioned; v1 (pre-loop) files backward compatible with `loop_context: null`

**Implementation Notes:**
- Effort: 2/5 (low complexity; leverages existing slice 153 patterns and slice 149 loop logic)
- Test strategy: Mock CF queries, verify iteration progression, validate step naming, test state serialization
- No changes needed to `/sq:run` slash command (works transparently with loop iterations)
- Convergence loop strategies generate warning and fall back to max-iteration (same as executor in 149)

## 20260404

**Slice 156: Pipeline Executor Hardening — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/156-tasks.pipeline-executor-hardening.md`. 14 tasks (T1–T14): `ExecutionMode` StrEnum in state.py (T1); schema v2 with `execution_mode` field on `RunState` (T2); `init_run` gains `execution_mode` param and lowercase normalisation (T3); `_run_pipeline` gains `run_id` and `execution_mode` params (T4); `_run_pipeline_sdk` gains `run_id` param (T5); fix `--resume` dispatch via `match state.execution_mode` (T6); fix implicit resume dispatch (T7); `_handle_prompt_only_init` records `PROMPT_ONLY` (T8); lowercase normalisation in `load_pipeline` (T9) and `discover_pipelines` (T10); CLI input normalisation (T11); display `execution_mode` in `--status` (T12); lint/type-check/full suite (T13); closeout (T14). Test-with pattern throughout; 6 commit checkpoints.

**Slice 156: Pipeline Executor Hardening — Design Complete (Phase 4)**
Diagnosed resume failure: both `--resume` and implicit resume paths bypass `_run_pipeline_sdk`, so `sdk_session` is `None` on resume; compact action falls through to `cf compact --instructions ...` which does not exist. Fix scope: (1) `ExecutionMode` StrEnum added to `state.py`; (2) `RunState.execution_mode` field (schema v2); (3) both resume paths dispatch by enum match to the correct runner; (4) `_run_pipeline_sdk` accepts `run_id` for resume-in-place; (5) pipeline name normalised to lowercase at load and CLI input boundary. Design created at `project-documents/user/slices/156-slice.pipeline-executor-hardening.md`.

**Slice 154: Prompt-Only Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/154-slice.prompt-only-loops.md` and `project-documents/user/tasks/154-tasks.prompt-only-loops.md`. Slice extends prompt-only mode to transparently support `each`/collection loops — executor expands loops internally, returns successive iteration instructions via `--next` calls. To the caller, a loop appears as a sequence of steps. Enables design-batch pipelines (multi-slice batch operations) in interactive prompt-only mode. Architecture: loop state tracking (iteration count, bound item) in StateManager; placeholder resolution (`{slice.index}` → actual value from item); query source executor for CF `cf.unfinished_slices(plan)` integration; loop expansion in executor's `next_step()` / advancement in `step_done()`. Convergence loop syntax acknowledged in YAML but stubbed (strategies are 155/160 scope). 20 implementation tasks; test-with pattern throughout. No design blockers; ready for implementation.

**Slice 155: SDK Pipeline Executor — Implementation Complete (Phase 6)**
Implemented all 20 tasks (T1–T20). Created `src/squadron/pipeline/sdk_session.py`: `SDKExecutionSession` dataclass wrapping `ClaudeSDKClient` with `set_model()` (skips if unchanged), `dispatch()` (rate-limit retry, error translation), `configure_compaction()` (stores config), `connect()`/`disconnect()` lifecycle. Extended `ActionContext` with `sdk_session: SDKExecutionSession | None = None`. Dispatch action gains `_dispatch_via_session()` path; routing checks `context.sdk_session`. Compact action gains SDK path that calls `session.configure_compaction()` instead of CF. Environment detection via `_resolve_execution_mode()` raises `typer.Exit(1)` for `CLAUDECODE` env var. CLI wiring: `_run_pipeline_sdk()` async helper creates session, connects, calls `_run_pipeline()`, disconnects in `finally`. Executor propagates `sdk_session` through all `_execute_step_once()`/loop/each call chains. 38 new tests across 5 test files. Full suite: 1228 tests pass, zero regressions. Slice 155 marked complete.

**Slice 155: SDK Pipeline Executor — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/155-tasks.sdk-pipeline-executor.md`. 20 tasks (T1–T20): SDKExecutionSession module with persistent client lifecycle and set_model()/dispatch()/configure_compaction() methods (T1-T3), ActionContext extension with sdk_session field (T4), dispatch action session path with model switching (T5-T7), compact action SDK compaction path via context_management API (T8-T10), environment detection for CLAUDECODE rejection (T11-T13), CLI wiring and executor propagation (T14-T17), integration test with full pipeline cycle (T18-T19), lint/verify/closeout (T20). Test-with pattern throughout; 7 commit checkpoints.

**Slice 155: SDK Pipeline Executor — Design Complete (Phase 4)**
Created `project-documents/user/slices/155-slice.sdk-pipeline-executor.md`. Full pipeline automation via `ClaudeSDKClient` with persistent session, per-step model switching via `set_model()`, and server-side compaction via `context_management` API (`compact_20260112` beta). Slice review (glm-5) raised FAIL on persistent session violating 140's "stateless steps" principle. Resolved by updating `140-arch.pipeline-foundation.md` to distinguish SDK session persistence (runtime optimization, 140 scope) from conversation persistence (semantic dependency, 160 scope). Architecture updated: "Interaction with Conversations" section clarified, dependency notes updated.

**Slice 153: Verification and Pipeline Testing**
Ran prompt-only pipeline end-to-end in IDE extension, Claude Code CLI, and straight CLI. Findings: (1) reviews blocked inside Claude Code sessions ("no nested Claude Code") regardless of model — review dispatch goes through SDK subprocess; (2) `/model` and `/compact` slash commands cannot be automated — only user can issue slash commands; (3) checkpoint `always` trigger required stronger prompt language to enforce. Fixed: review command now uses model alias (not resolved ID) to preserve profile resolution; removed invalid `--template` flag; strengthened checkpoint/compact instructions in `/sq:run`. Added `test-pipeline.yaml` for low-cost pipeline testing. Added slice 155 to slice plan, updated slice 154 scope (loops only, model switching informational).

**Slice 153: Prompt-Only Pipeline Executor — Implementation Complete (Phase 6)**
Implemented all 17 tasks (T1–T17). Created `src/squadron/pipeline/prompt_renderer.py`: `StepInstructions`, `ActionInstruction`, `CompletionResult` dataclasses, per-action-type builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog), `render_step_instructions()` entry point. Added `StateManager.record_step_done()` public method. CLI: `--prompt-only`, `--next`, `--step-done`, `--verdict` flags on `sq run`. `/sq:run` slash command rewritten to consume prompt-only output. 30 unit tests, 4 integration tests, 12 CLI tests. Full verification walkthrough passed: all 6 slice pipeline steps cycle correctly, model aliases resolve, compact params resolve `{slice}` → target. 1193 total tests pass, zero regressions. Slice 153 complete.

## 20260403

**Slice 153: Prompt-Only Pipeline Executor — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/153-tasks.prompt-only-pipeline-executor.md`. 17 tasks (T1–T17): data models (`StepInstructions`, `ActionInstruction`, `CompletionResult`), per-action-type instruction builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog), `render_step_instructions()` entry point, `StateManager.record_step_done()` public method, CLI flags (`--prompt-only`, `--next`, `--step-done`), integration test (full prompt-only cycle), `/sq:run` slash command rewrite to consume executor output, lint/verify, closeout. Test-with pattern throughout; 7 commit checkpoints. No blockers.

**Slice 153: Prompt-Only Pipeline Executor — Design Complete (Phase 4)**
Created `project-documents/user/slices/153-slice.prompt-only-pipeline-executor.md`. Adds `--prompt-only --next` mode to `sq run` that outputs one step's structured instructions (JSON) at a time without dispatching to LLMs. Each call advances state via existing `StateManager`. `--step-done <run-id> [--verdict V]` feeds back completion/verdict for checkpoint evaluation. New `prompt_renderer.py` module: pure function that expands step types via existing `expand()`, resolves models via `ModelResolver`, renders compact templates with pipeline params — produces `StepInstructions` dataclass. `/sq:run` slash command rewritten to consume executor output instead of hardcoding workflow. Added slice overview to `140-slices.pipeline-foundation.md` (item 13). Added future work item for external model dispatch to non-Claude-Code LLMs. Dependencies: [151].

**Slice 151: CLI Integration and End-to-End Validation — Implementation Complete (Phase 6)**
Implemented all tasks T1–T21. Created `src/squadron/cli/commands/run.py` (~300 lines): `run()` Typer command with positional `pipeline`/`target` args, `--model`, `--param key=value`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`. `_resolve_target()` maps positional target to pipeline's first required param at runtime. `_assemble_params()` combines target, `--param`, and model. `_check_cf()` pre-flight verifies CF availability. `_run_pipeline()` async helper: load → validate → init_run → execute → finalize. `--resume` loads state, finds next step, re-executes. Implicit resume detection via `find_matching_run()` + `typer.confirm()`. Keyboard interrupt handling saves state and prints resume instructions. Rich output: Table for `--list`, Panel for `--status`, colored summary for execution results. Registered in `app.py`. 38 unit tests (`tests/cli/commands/test_run.py`), 5 integration tests (`tests/pipeline/test_cli_integration.py`). pyright 0 errors; ruff clean. Slice 151 marked complete — completes Pipeline Foundation initiative (140).

**Slice 151: CLI Integration and End-to-End Validation — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/151-tasks.cli-integration-and-end-to-end-validation.md`. 21 tasks (T1–T21): command skeleton + registration, Typer argument signatures, mutual exclusivity validation, `--list`, `--validate`, `--status` (with `"latest"` sentinel), `--dry-run`, parameter assembly helper, CF pre-flight check, core execution flow (`_run_pipeline` async helper + `asyncio.run` bridge), `--resume` flow, implicit resume detection (`find_matching_run` + `typer.confirm`), `--from` mid-process adoption, keyboard interrupt handling, 4 integration tests (full run, resume, from-step, dry-run no state file), exports/lint/pyright, verification and closeout. Test-with pattern throughout; 5 commit checkpoints. No blockers.

**Slice 151: CLI Integration and End-to-End Validation — Design Complete (Phase 4)**
Created `project-documents/user/slices/151-slice.cli-integration-and-end-to-end-validation.md`. Typer `sq run` command surface wiring executor, state manager, and pipeline loader into the CLI presentation layer. Options: `--slice`, `--model`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`. Implicit resume detection when paused run matches pipeline+params. Rich terminal output for all display modes. Integration tests with mock action registries. Async executor bridged via `asyncio.run()`. Pre-flight CF check to avoid orphan state files. Dependencies: [148, 149, 150]. Completes the Pipeline Foundation initiative (140).

**Slice 150: Pipeline State and Resume — Implementation Complete (Phase 6)**
Implemented all tasks T1–T26. Created `src/squadron/pipeline/state.py` (~280 lines): Pydantic models (`RunState`, `StepState`, `CheckpointState`), `SchemaVersionError`, and `StateManager` with full public interface (10 methods). Atomic write via `.tmp` sibling + rename; `init_run` generates `run-{YYYYMMDD}-{slug}-{hash8}` IDs and auto-prunes; `make_step_callback` returns executor-ready closure; `_append_step` extracts verdict (last non-None) and outputs (last action); paused steps set `status="paused"` + `checkpoint` field; `finalize` writes terminal status; `load` validates schema version; `load_prior_outputs` reconstructs `dict[str, ActionResult]` defensively; `first_unfinished_step` scans definition in order; `list_runs` globs+filters+sorts; `find_matching_run` exact params match; `prune` skips paused runs. 43 unit tests + 2 integration tests (full run + resume) all pass. pyright 0 errors; ruff clean. Slice 150 marked complete.

**Slice 150: Pipeline State and Resume — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/150-tasks.pipeline-state-and-resume.md`. 26 tasks (T1–T26): test infrastructure (conftest fixtures), Pydantic models (`RunState`/`StepState`/`CheckpointState`/`SchemaVersionError`), `StateManager.__init__` + atomic write helper, `init_run`, `make_step_callback` + `_append_step`, `finalize`, `load` + `SchemaVersionError` check, `load_prior_outputs`, `first_unfinished_step`, `list_runs`, `find_matching_run`, `prune`, integration tests (full run + resume), exports/lint, closeout. Test-with pattern throughout; 3 commit checkpoints. No blockers.

**Slice 150: Pipeline State and Resume — Design Complete (Phase 4)**
Created `project-documents/user/slices/150-slice.pipeline-state-and-resume.md`. `StateManager` persists `RunState` JSON to `~/.config/squadron/runs/` after every completed step via `on_step_complete` callback. Pydantic models: `RunState`, `StepState`, `CheckpointState`. Atomic write pattern for corruption safety. `load_prior_outputs` reconstructs `dict[str, ActionResult]` from stored `action_results`. `find_matching_run` enables implicit resume detection. `prune(keep=10)` per-pipeline auto-prune on `init_run`. `SchemaVersionError` for forward-compatibility. Provides `StateManager` interface to slice 151 (CLI). Dependencies: [149]. Status: not_started.

**Slice 149: Pipeline Executor and Loops — Implementation Complete (Phase 6)**
Implemented all tasks T1–T10. Created `src/squadron/pipeline/executor.py` (~570 lines): `ExecutionStatus`/`StepResult`/`PipelineResult` result types; `resolve_placeholders` with dotted-path traversal; `LoopCondition`/`evaluate_condition` with closed 3-value enum; `ExhaustBehavior`/`LoopConfig`; `_cf_unfinished_slices` source fn + `_SOURCE_REGISTRY`; `_parse_source` with regex validation; `execute_pipeline` async core with sequential steps, `start_from` skip, checkpoint and failure propagation, `each` branch via `_execute_each_step`, and loop wrapping via `_execute_loop_step`. Replaced `steps/collection.py` stub with `EachStepType` (structural validation, empty `expand()`). Added `collection` import to `validate_pipeline` in `loader.py`. 52 unit tests in `test_executor.py`, 6 integration tests in `test_executor_integration.py`. 296 total pipeline tests pass; pyright 0 errors; ruff clean. Slice 149 marked complete.

**Slice 149: Pipeline Executor and Loops — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/149-tasks.pipeline-executor-and-loops.md`. 10 tasks (T1–T10): test infrastructure, result types (`ExecutionStatus`, `StepResult`, `PipelineResult`), placeholder resolution, loop condition grammar (`LoopCondition` enum + `evaluate_condition`), core sequential executor with checkpoint/failure handling, retry loop execution (`LoopConfig`, `ExhaustBehavior`), `EachStepType` implementation, source registry + `each` execution branch, integration tests, verification and closeout. Test-with pattern throughout; 3 commit checkpoints. No blockers.

**Slice 149: Pipeline Executor and Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/149-slice.pipeline-executor-and-loops.md`. Async executor engine takes validated `PipelineDefinition`, expands step types into action sequences, resolves `{param}` placeholders, and executes actions sequentially. Retry loops (`loop: {max, until, on_exhaust}`) with closed condition grammar (`review.pass`, `review.concerns_or_better`, `action.success`). `each` collection loop step type with source query dispatch (`cf.unfinished_slices`) and dot-path item binding (`{slice.index}`). Convergence loop strategy field acknowledged but stubbed (160 scope). Checkpoint pausing and action failure propagation. `on_step_complete` callback for state manager/CLI integration. Dependencies: [147, 148]. Unblocks slices 150 (State/Resume) and 151 (CLI).

## 20260402

**Slice 148: Pipeline Definitions and Loader — Implementation Complete (Phase 6)**
Implemented all 13 tasks (T1–T13). Created `schema.py` with `PipelineSchema` and `StepSchema` Pydantic v2 models — `@model_validator(mode="before")` unpacks YAML step grammar, scalar shorthand expansion (`devlog: auto` → `{"mode": "auto"}`), `to_definition()` converts to existing dataclasses. Created `loader.py` with `load_pipeline()` (path or name with project→user→built-in search), `discover_pipelines()` (scan+merge with source attribution), and `validate_pipeline()` (step type registry, model alias resolution, review template existence, param placeholder declaration checks). Four built-in pipeline YAMLs: slice-lifecycle (5 steps), review-only (1), implementation-only (2), design-batch (1 `each`). 43 new tests (12 schema + 11 loader + 9 validation + 11 integration), 995 total pass, pyright 0 errors, ruff clean. Slice 148 marked complete.

**Slice 148: Pipeline Definitions and Loader — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/148-tasks.pipeline-definitions-and-loader.md`. 13 tasks (T1–T13): Pydantic schema models + tests, four built-in pipeline YAML files, pipeline loader with 3-source discovery + tests, `discover_pipelines` + tests, semantic validation (`validate_pipeline`) + tests, integration tests for all built-ins, two commit checkpoints, closeout. Test-with pattern throughout. No blockers.

**Slice 148: Pipeline Definitions and Loader — Design Complete (Phase 4)**
Created `project-documents/user/slices/148-slice.pipeline-definitions-and-loader.md`. YAML pipeline grammar with Pydantic v2 schema validation (`schema.py`), loader with 3-source discovery (built-in → user → project), four built-in pipelines (slice-lifecycle, review-only, implementation-only, design-batch), and semantic validation (step types, model aliases, review templates, param references). Pydantic validates at boundary, converts to existing `PipelineDefinition`/`StepConfig` dataclasses. Dependencies: [147]. Unblocks slice 149 (Executor) and 151 (CLI).

**Slice 147: Compact Action and Step Types — Implementation Complete (Phase 6)**
Implemented all 13 tasks (T1–T13). Created compaction instruction template (`data/compaction/default.yaml`) with loader supporting user overrides from `~/.config/squadron/compaction/`. Implemented `CompactAction` with template-based CF instructions, `keep`/`summarize` params, and optional CF summarize call. Implemented four step types: `PhaseStepType` (3 registrations, 6-action expansion with optional review/checkpoint), `CompactStepType` (single compact action passthrough), `ReviewStepType` (review + optional checkpoint), `DevlogStepType` (single devlog with auto/explicit mode). 76 new tests (17 compact action + 17 phase + 7 compact step + 8 review step + 9 devlog step + 17 registry integration + 1 init), 952 total pass, pyright 0 errors, ruff clean. Slice 147 marked complete.

**Slice 147: Compact Action and Step Types — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/147-tasks.compact-action-and-step-types.md`. 13 tasks (T1–T13): compaction instruction template + loader, CompactAction implementation + tests, PhaseStepType (3-phase registration) + tests, CompactStepType + tests, ReviewStepType + tests, DevlogStepType + tests, registry integration tests, verification and closeout. Test-with pattern throughout. No blockers.

**Slice 147: Compact Action and Step Types — Design Complete (Phase 4)**
Created `project-documents/user/slices/147-slice.compact-action-and-step-types.md`. Compact action issues parameterized compaction instructions to CF with configurable `keep`/`summarize` params. Four step types: phase (cf-op→dispatch→review→checkpoint→commit), compact (single compact action), review (review + optional checkpoint), devlog (single devlog action). Step types are pure data transformers — `expand()` returns `(action_type, action_config)` tuples for the executor. Dependencies: [144, 145, 146]. Unblocks slice 148 (Pipeline Definitions) and 149 (Executor).

**Slice 146: Review and Checkpoint Actions — Implementation Complete (Phase 6)**
Implemented all 8 tasks (T1–T8). Extracted review persistence to shared `review/persistence.py` (`format_review_markdown`, `save_review_file`, `yaml_escape`, `SliceInfo`). Implemented `CheckpointAction` with `CheckpointTrigger` enum and trigger×verdict evaluation matrix. Implemented `ReviewAction` delegating to `run_review_with_profile()` with model/profile resolution, template input passthrough, review file persistence (non-fatal), and verdict/findings mapping. 57 new tests (13 persistence + 21 checkpoint + 21 review + 2 registry), 884 total pass, pyright 0 errors, ruff clean. Slice 146 marked complete.

---

## 20260331

**Slice 146: Review and Checkpoint Actions — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/146-tasks.review-and-checkpoint-actions.md`. 8 tasks (T1–T8): review persistence extraction + tests, CheckpointAction implementation + tests, ReviewAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 146: Review and Checkpoint Actions — Design Complete (Phase 4)**
Created `project-documents/user/slices/146-slice.review-and-checkpoint-actions.md`. Two actions: ReviewAction delegates to `run_review_with_profile()`, populates `ActionResult.verdict` and `ActionResult.findings` from structured findings (slice 143), persists review files. CheckpointAction evaluates trigger (always, on-concerns, on-fail, never) against prior review verdict, returns paused/skipped result for executor interpretation. Includes persistence extraction from CLI to shared `review/persistence.py`. Dependencies: [143, 145]. Unblocks slices 147, 149, 150.

**Slice 145: Dispatch Action — Implementation Complete (Phase 6)**
Implemented all 6 tasks (T1–T6). Extracted `_ensure_provider_loaded` from `review_client.py` to shared `providers/loader.py`. Implemented `DispatchAction` with 5-level model resolution, profile resolution (explicit override > alias > SDK default), one-shot agent lifecycle, SDK response deduplication, token metadata passthrough, and comprehensive error handling (never raises). 26 new tests (17 dispatch + 9 loader), 827 total pass, pyright 0 errors, ruff clean. Slice 145 marked complete.

**Slice 145: Dispatch Action — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/145-tasks.dispatch-action.md`. 6 tasks (T1–T6): provider loader extraction + tests, DispatchAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 145: Dispatch Action — Design Complete (Phase 4)**
Created `project-documents/user/slices/145-slice.dispatch-action.md`. Dispatch action resolves model alias via 5-level cascade (`ModelResolver`), creates one-shot agent through provider registry, sends prompt via `handle_message()`, captures response and token metadata. Follows review system's proven dispatch pattern. Includes provider loader extraction from `review_client.py` to shared location. Dependencies: [142, 102]. Unblocks slices 146, 147.

**Slice 144: Utility Actions — Implementation Complete (Phase 6)**
Implemented all 8 tasks (T1–T8). `CfOpAction` delegates to `cf_client._run()` with `pyright: ignore[reportPrivateUsage]` per project convention. `CommitAction` uses `subprocess.run()` with real `git init` test repos via `tmp_path`. `DevlogAction` handles DEVLOG insertion with date header deduplication and auto-generation from `prior_outputs`. All three actions satisfy `Action` protocol and auto-register at import time. 39 new tests, 800 total pass, pyright 0 errors, ruff clean. Slice 144 marked complete.

**Slice 144: Utility Actions — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/144-tasks.utility-actions.md`. 8 tasks (T1–T8): CfOpAction implementation + tests, CommitAction implementation + tests, DevlogAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 144: Utility Actions — Design Complete (Phase 4)**
Created `project-documents/user/slices/144-slice.utility-actions.md`. Three action implementations: CfOpAction (set_phase, build_context, summarize via ContextForgeClient), CommitAction (git commit with semantic messages, no-op on clean tree), DevlogAction (structured DEVLOG entries auto-generated from pipeline state or explicit content). Each action auto-registers at import time. Mock I/O boundaries for testing. Unblocks slice 147 (step types).

---

## 20260330

**Slice 143: Structured Review Findings — Implementation Complete (Phase 6)**
Implemented all 10 tasks (T1–T10). Added `StructuredFinding` dataclass and `NOTE` severity to `review/models.py`. Extended parser with NOTE support, `category:` and `location:` tag extraction from finding blocks. Extended frontmatter formatter to emit `findings:` YAML array with structured entries. Extended `to_dict()` with `structured_findings` and `category`/`location` on findings. Injected structured output instructions into all review template system prompts via `review_client.py`. 761 tests pass (0 pre-existing failures), pyright 0 errors, ruff clean. Slice 143 marked complete.

**Slice 143: Structured Review Findings — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/143-tasks.structured-review-findings.md`. 10 tasks (T1–T10): models (StructuredFinding + NOTE severity), parser extensions (category/location extraction), frontmatter formatter, JSON serialization, prompt enhancement, full verification. Test-with pattern throughout. No blockers.

**Slice 143: Structured Review Findings — Design Complete (Phase 4)**
Created `project-documents/user/slices/143-slice.structured-review-findings.md`. Extends review output with machine-readable structured findings in YAML frontmatter. Adds `StructuredFinding` dataclass (id, severity, category, summary, location), `NOTE` severity level, parser extensions for category extraction, and prompt enhancement for all review templates. Single-file format: frontmatter is the programmatic index, prose body unchanged. Absorbs former slice 123 scope. Designed for slice 160 cross-iteration identity matching via (category, location) fingerprint.

**Slice 142: Pipeline Core Models and Action Protocol — Implementation Complete (Phase 6)**
Implemented full `src/squadron/pipeline/` package: 5 dataclasses in `models.py`, `Action` protocol + `ActionType` StrEnum + action registry, `StepType` protocol + `StepTypeName` StrEnum + step-type registry, `ModelResolver` (5-level cascade, pool: stub), stub modules for 7 actions and 5 step types, public `__init__` surface. 26 new tests across 3 test files — all pass. Pyright: 0 errors. Full repo: 707 passed, 8 pre-existing failures (unrelated). Slice 142 marked complete.

**Slice 142: Pipeline Core Models and Action Protocol — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/142-tasks.pipeline-core-models-and-action-protocol.md`. 14 tasks (T1–T14): package skeleton + stubs, data models, Action protocol + registry, StepType protocol + registry, ModelResolver (5-level cascade, pool: stub), pipeline `__init__` public surface, full test/pyright pass, verification walkthrough and closeout. Tests interleaved after each implementation group. No blockers.

**Slice 142: Pipeline Core Models and Action Protocol — Design Complete (Phase 4)**
Created `project-documents/user/slices/142-slice.pipeline-core-models-and-action-protocol.md`. Defines `ActionContext`, `ActionResult`, `PipelineDefinition`, `StepConfig`, `ValidationError` dataclasses; `Action` and `StepType` protocols; action/step-type registries; `ModelResolver` with 5-level cascade chain and `pool:` prefix error stub. Full `src/squadron/pipeline/` package layout with stub modules for all future action and step type files. No blockers — all design decisions resolved by architecture.

---

## 20260329

**Slice 141: Configuration Externalization — Implementation Complete (Phase 6)**
Created `src/squadron/data/` package with `data_dir()` two-path fallback. Transcribed 18 built-in model aliases to `data/models.toml`. Moved review templates to `data/templates/`. Refactored `aliases.py` (extracted `_load_aliases_from_file`, removed `BUILT_IN_ALIASES`). Updated `review/templates/__init__.py` to use `data_dir()`. Updated `pyproject.toml` force-include. Deleted `review/templates/builtin/`. Updated all tests referencing old paths. 681 tests pass (8 pre-existing failures unrelated to this slice). Slice 141 marked complete.

---

## 20260328

### Slice 141: Configuration Externalization — Task Breakdown Complete (Phase 5)
- Task file created: `project-documents/user/tasks/141-tasks.configuration-externalization.md`
- 11 tasks (T1–T11): create data/ package, copy templates, transcribe models.toml, refactor aliases.py, update template loader, update pyproject.toml, delete builtin/, verify, commit
- Test tasks interleaved after each implementation task (T5 after T4, T7 after T6)
- No blockers — straightforward reorganization, all design decisions resolved

### Slice 141: Configuration Externalization — Design Complete (Phase 4)
- Slice design created: `project-documents/user/slices/141-slice.configuration-externalization.md`
- Scope: move `BUILT_IN_ALIASES` Python dict → `src/squadron/data/models.toml`; move `review/templates/builtin/*.yaml` → `src/squadron/data/templates/`; add `DataLoader.data_dir()` utility; reserve `data/pipelines/` for slice 148
- Key decision: `data_dir()` uses same two-path fallback pattern as `install.py`'s `_get_commands_source()`
- Public APIs unchanged; merge precedence (built-ins → user overrides) preserved
- Slice plan entry already had (141) index materialized — no update needed

### Slice 140: Command Surface Parity — Task Breakdown (Phase 5) [revised]
- 11 tasks: create review.md (4 subcommands), create auth.md, delete 4 old files, handle run-slice, fix installer stale removal, smoke-test, close
- install.py gets stale-file cleanup (source-authoritative deletion, same pattern as CF daec117)
- Revised after design correction: consolidated dispatch pattern replaces per-subcommand files

### Slice 140: Command Surface Parity — Slice Design (Phase 4)
- Designed slash command parity: add `/sq:review arch`, deprecate `/sq:run-slice`
- Naming convention formalized: `commands/sq/{parent}-{child}.md` maps to `sq {parent} {child}`
- Existing names already follow convention — primary work is adding `review-arch.md` and deprecation banner
- Effort: 1/5 — markdown files and settings only, no Python changes

## 20260327

### Slice 128: Review Transport Unification — Implementation Complete (Phase 6)
- Reviews unified through `Agent.handle_message()` via provider registry — one code path for all profiles
- `runner.py` deleted (net -700 lines), `AsyncOpenAI` removed from review module
- `ProviderCapabilities` on all providers; file injection conditional on `can_read_files`
- `ProviderType`, `ProfileName`, `AuthType` enums — all identifiers defined once
- `OAuthFileStrategy` + `CodexProvider`/`CodexAgent` via MCP transport
- Profile renamed `codex` → `openai-oauth`; auth type `codex` → `oauth`
- `SDKAgent` → `ClaudeSDKAgent`; auth dispatch via `from_config` factory
- 687 tests pass; ruff/pyright clean

## 20260326

### Slice 124: Codex Agent Integration — Rewound
- Implementation completed but discovered fundamental architecture gap: review system bypasses Agent/AgentProvider Protocols entirely, tightly coupled to AsyncOpenAI and ClaudeSDKClient
- Codex subscription auth (OAuth token from `~/.codex/auth.json`) can't call Chat Completions API directly — must route through Codex runtime. But review system can't use non-OpenAI transports
- String-based dispatch (`if profile == "sdk"`, `if auth_type == "codex"`) throughout codebase
- Branch rewound to main. Slice superseded by 128

### Slice 128: Review Transport Unification — Slice Design Complete (Phase 4)
- Reviews use `Agent.handle_message()` via provider registry instead of bespoke transport implementations
- `ProviderCapabilities` dataclass: `can_read_files`, `supports_system_prompt`, `supports_streaming`
- Auth strategy dispatch via registry (eliminate if/elif chains), `"codex"` auth type → `"oauth"`
- `SDKAgent` → `ClaudeSDKAgent`, `runner.py` deleted (absorbed into agent)
- Enables Codex subscription reviews and future Anthropic API without review system changes

### Slice 128: Review Transport Unification — Task Breakdown Complete (Phase 5)
- 19 tasks: capabilities, auth refactor, OAuth strategy, SDK rename, Codex provider, runner.py migration, review_client unification, CLI auth cleanup, model aliases, validation, docs
- Test-with pattern throughout; 9 commit checkpoints
- Key sequence: capabilities first → auth cleanup → providers → review client unification → CLI cleanup

## 20260325

### Initiative Plan & 900-Band Maintenance Initiative
- Created `001-initiative-plan.squadron.md` retroactively documenting all initiatives (100, 140, 160, 200, 900)
- Created `900-arch.maintenance-and-refactoring.md` and `900-slices.maintenance-and-refactoring.md` as cross-cutting maintenance home

### Slice 124: Codex Agent Integration — Task Breakdown Complete (Phase 5)
- 12 tasks: transport evaluation, CodexAuthStrategy + tests, CodexAgent + tests, CodexProvider + tests, registration/profile + tests, model aliases, validation, documentation
- Test-with pattern throughout; 7 commit checkpoints
- Key design: Codex models already work for reviews via `openai` profile (Chat Completions API) — no review system changes; agentic provider is for spawn/task workflows only

### Slice 124: Codex Agent Integration — Slice Design Complete (Phase 4)
- Codex integration via MCP server path (`codex mcp-server`), not TypeScript SDK
- `CodexProvider`/`CodexAgent` implementing existing Protocols via MCP stdio client
- `CodexAuthStrategy` checks `~/.codex/auth.json` or `OPENAI_API_KEY`
- Review system gets third path: `_run_codex_review()` alongside SDK and non-SDK paths
- Lazy subprocess start, read-only sandbox for reviews

### Slice 127: Scoped Code Review & Prompt Logging — Implementation Complete (Phase 6)

- `git_utils.py`: `_find_slice_branch()`, `_find_merge_commit()`, `resolve_slice_diff_range()` — three-tier resolution (branch → merge commit → fallback to main)
- Prompt log: `_write_prompt_log()` writes `review-prompt-{ts}.md` at `-vvv`; prompt fields on `ReviewResult` populated at `-vv`
- `review_code()` uses `resolve_slice_diff_range()` instead of `diff = "main"` when slice number provided; `--diff` flag overrides
- Debug appendix `## Debug: Prompt & Response` appended to saved review markdown when prompt fields present
- 637 tests pass; 6 semantic commits on branch `127-slice.scoped-code-review-prompt-logging`

### Slice 127: Scoped Code Review & Prompt Logging — Task Breakdown Complete (Phase 5)

- 16 tasks: git_utils.py (branch/merge resolution + tests), ReviewResult prompt fields + tests, prompt log writer + tests, scoped diff wiring + tests, debug appendix + tests, validation pass, documentation
- Test-with pattern throughout; 6 commit checkpoints

### Slice 127: Scoped Code Review & Prompt Logging — Slice Design Complete (Phase 4)

- Scoped diff resolution: `sq review code 122` auto-resolves to slice branch's commits via merge-base or merge-commit detection, falls back to `--diff main`
- Prompt log persistence: `-vvv` writes full prompt to `~/.config/squadron/logs/review-prompt-{ts}.md`; `-vv` embeds debug appendix in saved review file
- New `git_utils.py` module; optional fields on `ReviewResult` for prompt/response capture

### Slice 122: Review Context Enrichment — Implementation Complete (Phase 6)

- Expanded `_FINDING_RE` to 5 formats; lenient fallback + synthesized finding when verdict/findings mismatch; `fallback_used` flag on `ReviewResult`; debug log at `~/.config/squadron/logs/review-debug.jsonl`
- CRITICAL consistency block added to all three builtin templates; `rules.py` module: `resolve_rules_dir()`, language detection, glob matching, template rules injection
- `review code` auto-detects language rules from diff paths; `--rules-dir`/`--no-rules` flags on review commands; template rules prepended from `rules/review.md` + `rules/review-{template}.md`
- Review file YAML aligned: `layer`, `sourceDocument`, `aiModel` (resolved ID), `status: complete`; `-vvv` debug output shows system/user prompt + injected rules
- 609 tests pass; 4 semantic commits on branch `122-slice.review-context-enrichment`

### Slice 122: Review Context Enrichment — Task Breakdown Complete (Phase 5)

- 19 tasks across: parser hardening (lenient parsing + fallback + debug log), template prompt hardening, `rules.py` auto-detection module, review CLI wiring (`--rules-dir`, `--no-rules`), review file YAML alignment, prompt debug output (`-vvv`)
- Slice design updated: added Section 5 (YAML alignment), Section 6 (prompt debug), prompt hardening renames to Section 7
- v0.2.6 tagged and published (slice 126 complete — `ContextForgeClient`)

---

## 20260324

### Slice 126: Context Forge Integration Layer — Implementation Complete

- `ContextForgeClient` implemented in `src/squadron/integrations/context_forge.py` with typed methods: `list_slices()`, `list_tasks()`, `get_project()`, `is_available()`
- `review.py` migrated: `_run_cf()` removed, `_resolve_slice_number()` uses `ContextForgeClient`
- Custom exceptions (`ContextForgeNotAvailable`, `ContextForgeError`) replace inline `typer.Exit`
- 16 unit tests for client, 3 new CLI error path tests, 7 existing resolve tests updated
- Markdown command files updated to CF's new command surface (`cf list slices`, `cf list tasks`)
- All 556 tests pass, pyright 0 errors, ruff clean

### Slice 126: Context Forge Integration Layer — Task Breakdown Complete

Task file at `project-documents/user/tasks/126-tasks.context-forge-integration-layer.md` (14 tasks: T1-T14). Three workstreams: client implementation with typed dataclasses (T1-T9), review.py migration (T10-T11), markdown command file updates and validation (T12-T14). Test-with pattern throughout.

### Slice 126: Context Forge Integration Layer — Design Complete

- Created `project-documents/user/slices/126-slice.context-forge-integration-layer.md`
- `ContextForgeClient` class in `src/squadron/integrations/context_forge.py` — typed methods replacing scattered `subprocess.run(["cf", ...])` calls
- Typed return dataclasses: `SliceEntry`, `TaskEntry`, `ProjectInfo`
- Custom exceptions (`ContextForgeNotAvailable`, `ContextForgeError`) separated from CLI layer
- Adapts to CF's new command surface (`cf list slices --json` replacing `cf slice list --json`)
- Markdown command files updated to reference new CF command names
- Scope limited to abstraction and migration — MCP transport, command aliasing deferred

### Slice 122: Review Context Enrichment — Design Complete

- Created `project-documents/user/slices/122-slice.review-context-enrichment.md`
- Two-pronged scope: (1) fix verdict/findings inconsistency (issue #5) via prompt hardening + parser post-processing guard, (2) auto-detect and inject language-specific rules for code reviews
- Language detection from diff file paths or glob matches, matched against rules files' `paths` frontmatter globs
- Rules directory resolution: `--rules-dir` flag > config `rules_dir` > `{cwd}/rules/` > `{cwd}/.claude/rules/`
- Slice/task reviews inject `rules/general.md` if present
- `--no-rules` flag to suppress all rule injection
- Legacy P0-P3 priorities extracted as optional copyable rules file, not baked into templates

## 20260323

### .env support for API keys

Added `python-dotenv` dependency. `load_dotenv()` runs at CLI startup (`cli/app.py`), so API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, etc.) can be set in a `.env` file instead of exported in the shell. `.env` already gitignored.

### Slice 121: Model Alias Metadata — Implementation Complete

- All 12 tasks (T1-T12) complete. 537 tests pass, pyright/ruff/format clean.
- `ModelPricing` TypedDict (input, output, cache_read, cache_write — USD per 1M tokens)
- `ModelAlias` extended with `private`, `cost_tier`, `notes`, `pricing` — all optional via inheritance pattern (`_ModelAliasRequired` base + `total=False`)
- All 12 `BUILT_IN_ALIASES` populated with curated metadata and pricing
- `load_user_aliases()` extracts metadata and pricing from TOML (inline and sub-table formats)
- `estimate_cost()` utility: alias name + token counts → USD float or None
- `sq models` compact by default; `sq models -v` shows Private, Cost, In $/1M, Out $/1M, Notes columns
- 21 new tests across T4 (3), T6 (6), T8 (6), T10 (6)

## 20260322

### Slice 121: Model Alias Metadata — Task Breakdown Complete

Task file at `project-documents/user/tasks/121-tasks.model-alias-metadata.md` (12 tasks: T1-T12). Three workstreams: type extensions with built-in metadata (T1-T4), TOML parsing and cost estimation (T5-T8), display updates and validation (T9-T12). Test-with pattern: each implementation task followed immediately by its test task.

### Slice 121: Model Alias Metadata — Design Complete

- Created `project-documents/user/slices/121-slice.model-alias-metadata.md`
- Extends `ModelAlias` TypedDict with optional `private` (bool), `cost_tier` (str), `notes` (str), `pricing` (ModelPricing) fields
- `ModelPricing` TypedDict: `input`, `output`, `cache_read`, `cache_write` (USD per 1M tokens)
- `total=False` on TypedDict for backward-compatible optional fields
- `cost_tier` values: free, cheap, moderate, expensive, subscription (new — for Max sub models)
- `estimate_cost()` utility: pure function, alias name + token counts → USD or None
- `sq models` gains Private, Cost, In $/1M, Out $/1M, Notes columns with compact mode
- Curated metadata and pricing for all 12 built-in aliases
- Also in this session: slice plan refactored (100-series trimmed, 160-series created for multi-agent), reindexing (161-172, 121-125), test fixes, template clarification, architecture docs updated to squadron naming

## 20260321

### Slice 120: Model Alias Registry — Implementation Complete

- All 22 tasks (T1-T22) complete. 514 tests pass, pyright/ruff clean.
- `review arch` renamed to `review slice` with backward-compat hidden alias + deprecation notice
- `src/squadron/models/aliases.py`: `resolve_model_alias()` with built-in defaults (opus, sonnet, haiku, gpt4o, o3, o1) and user `~/.config/squadron/models.toml` override
- `_infer_profile_from_model()` removed — alias registry handles all model→profile inference
- `_inject_file_contents()` in `review_client.py`: reads file contents and appends to prompt for non-SDK reviews; handles git diff and glob patterns for code reviews; size limits (100KB/file, 500KB total)
- `sq model list` command showing built-in + user aliases in a rich table
- 5 commits on branch `120-model-alias-registry`
- Post-impl live tests remain for PM (alias resolution, content injection, diff injection)

### Slice 120: Model Alias Registry — Task Breakdown Complete

Task file at `project-documents/user/tasks/120-tasks.model-alias-registry.md` (22 tasks: T1-T22). Three workstreams: rename review arch→slice (T1-T5), model alias registry with wiring (T6-T10), content injection for non-SDK reviews including code review diff/files (T11-T16), plus model list CLI (T17-T19) and slash command updates (T20-T22). Post-impl: live tests with OpenRouter, alias customization, diff injection.

### Slice 120: Model Alias Registry — Design Complete

- Slice design at `project-documents/user/slices/120-slice.model-alias-registry.md`
- Two problems addressed: (1) hardcoded model inference replaced by data-driven alias registry in `models.toml`, (2) non-SDK reviews fail because prompts contain file paths but models can't read files — content injection adds file contents to prompt for non-SDK path
- Ships built-in aliases (opus, sonnet, gpt4o, etc.) + user `~/.config/squadron/models.toml`
- Content injection: auto-reads files from `inputs` dict, appends to prompt; handles git diff for code reviews; 100KB/file, 500KB total limits
- New `sq model list` command

### Slice 119: Review Provider & Model Selection — Implementation Complete

- All 20 implementation tasks (T1-T20) complete. 491 tests pass.
- New `review_client.py` with `run_review_with_profile()` — SDK delegation or OpenAI-compatible API path
- `--profile` flag on all `sq review` commands (arch, tasks, code)
- `_resolve_profile()`: CLI flag → model inference → template → config → sdk fallback
- `_infer_profile_from_model()`: opus→sdk, gpt-4o→openai, slash→openrouter
- `load_all_templates()` loads from built-in + `~/.config/squadron/templates/` (user override by name)
- `default_review_profile` config key added
- Slash commands updated with `--profile` documentation
- Slice 120 (Model Alias Registry) added to slice plan as next priority
- Post-impl live tests remain for PM

### Slice 119: Review Provider & Model Selection — Task Breakdown Complete

Task file created at `project-documents/user/tasks/119-tasks.review-provider-model-selection.md` (20 tasks: T1-T20). Key task groups: template profile field (T1-T2), config key + profile resolution (T3-T7), review client with provider routing (T9-T10), CLI `--profile` flag (T12-T13), user template loading (T15-T16), slash command updates (T18), validation (T19-T20). Post-impl: live tests with OpenRouter, OpenAI, user templates, config defaults.

### Slice 119: Review Provider & Model Selection — Design Complete

- Slice design created at `project-documents/user/slices/119-slice.review-provider-model-selection.md`
- Scope: decouple review execution from hardcoded Claude SDK. Add `--profile` flag, `profile` field in templates, user-customizable templates from `~/.config/squadron/templates/`, config default `default_review_profile`, model-to-profile inference
- Key decision: SDK path preserved exactly (delegation), non-SDK path uses `AsyncOpenAI` directly via existing profile/auth infrastructure
- Known limitation: non-SDK reviews have no tool access (prompt-only)
- Slice plan updated: new slice 119 inserted, old 119 (Conversation Persistence) re-indexed to 134

---

## 20260320

### Slice 118: Claude Code Commands — Composed Workflows — In Progress

- Implementation complete (T1-T9 checked off). Remaining items are PM manual tests.
- Commits:
  - `a2058c9` feat: add /sq:run-slice command, update review commands with number shorthand
  - `f31cd44` test: update install tests for 9 command files
- What works: all 448 tests pass, ruff/pyright clean, wheel bundles `run-slice.md`, install produces 9 commands
- Scope expanded from original design:
  - Updated `review-tasks.md`, `review-code.md`, `review-arch.md` with bare number shorthand (e.g., `/sq:review-tasks 191`)
  - Path resolution via `cf slice list --json` / `cf task list --json` — worktree-aware, CF owns conventions
  - `review-arch` performs holistic check: slice design vs. architecture doc + slice plan entry
  - Review file persistence to `project-documents/user/reviews/` with YAML frontmatter
  - DEVLOG entry step added to `run-slice` pipeline (Step 5)
- Pending: PM live tests (`/sq:run-slice` on real slice, `/sq:review-tasks {nnn}` shorthand), prompt iteration

---

## 20260317

### Slice 118: Claude Code Commands — Composed Workflows — Task Breakdown Complete

Task file created at `project-documents/user/tasks/118-tasks.claude-code-commands-composed-workflows.md` (6 tasks: T1-T6). T1 create `run-slice.md` command file with full pipeline prompt. T2 update install tests (8→9 expected files). T3 commit. T4 validation pass. T5 commit. T6 verify wheel bundling. Post-impl: live test on a real slice, iterate on prompt.

### Slice 118: Claude Code Commands — Composed Workflows — Design Complete

Slice design created at `project-documents/user/slices/118-slice.claude-code-commands-composed-workflows.md`.

Scope: Single `/sq:run-slice` command that automates the full slice lifecycle — phase 4 (design) → phase 5 (task breakdown + review) → compact → phase 6 (implementation + code review). Chains `cf set/build` with `sq review tasks/code` and `/compact`. Review gates: PASS proceeds, FAIL stops for human input. Smart resume (skip completed phases) documented as future enhancement. Lives in existing `sq/` namespace — no new directories or Python code.

---

## 20260307

### Slice 117: PyPI Publishing & Global Install — Task Breakdown Complete

Task file created at `project-documents/user/tasks/117-tasks.pypi.md` (13 tasks: T1-T13). T1-T2 version flag + test, T3 commit. T4-T5 metadata polish + wheel verification, T6 commit. T7-T8 GitHub Actions CI (test + publish jobs), T9 commit. T10 README install section, T11 commit. T12-T13 validation pass + commit. Post-implementation section documents manual PM steps (PyPI account, first publish, smoke test).

---

## 20260306

### Slice 117: PyPI Publishing & Global Install — Design Complete

Slice design created at `project-documents/user/slices/117-slice.pypi.md`.

Scope: Publish `squadron` to PyPI for global install via `pipx install squadron` / `uv tool install squadron`. SemVer versioning (start at 0.1.0, single-sourced in pyproject.toml). `sq --version` via `importlib.metadata`. pyproject.toml metadata polish (classifiers, license, project-urls). GitHub Actions CI workflow (lint+test on push, publish to TestPyPI+PyPI on version tag). README install instructions.

Key decisions: SemVer over CalVer, tag-driven manual releases, `pypa/gh-action-pypi-publish` with OIDC trusted publisher preferred, TestPyPI dry-run before real publish, `astral-sh/setup-uv` for CI.

### Slice 116: Claude Code Commands — Implementation Complete

All 15 tasks complete. Eight command files in `commands/sq/` (`spawn.md`, `task.md`, `list.md`, `shutdown.md`, `review-arch.md`, `review-tasks.md`, `review-code.md`, `auth-status.md`). `pyproject.toml` updated with `force-include` for wheel bundling. `install.py` with `install_commands`/`uninstall_commands` wired into Typer app. 11 tests (8 install/uninstall + 3 source verification). 446 total tests pass, pyright clean, ruff clean.

---

## 20260305

### Slice 116: Claude Code Commands — sq Wrappers — Design Complete

Slice design created at `project-documents/user/slices/116-slice.sq-slash-command.md`.

Scope: Eight Claude Code slash command files (`/sq:spawn`, `/sq:task`, `/sq:list`, `/sq:shutdown`, `/sq:review-arch`, `/sq:review-tasks`, `/sq:review-code`, `/sq:auth-status`) in `commands/sq/`. Install/uninstall CLI commands (`sq install-commands`, `sq uninstall-commands`). Command files bundled in package wheel via `pyproject.toml`. Commands are thin prompts that instruct Claude to execute the corresponding `sq` CLI command via Bash.

### Slice 116: Claude Code Commands — Task Breakdown Complete

Task file created at `project-documents/user/tasks/116-tasks.sq-slash-command.md` (15 tasks). T1 directory setup, T2-T9 command file authoring (one per command), T10 package bundling, T11-T12 install/uninstall CLI, T13-T14 tests, T15 validation.

---

### Slice 115: Project Rename — orchestration → squadron — Complete

- Renamed `src/orchestration/` → `src/squadron/`, updated pyproject.toml (name, dual entry points: `sq` + `squadron`)
- Updated all imports across 127 .py files (61 src + 66 tests)
- Config paths: `~/.config/squadron/`, `.squadron.toml`, `~/.squadron/` for daemon
- Added config migration logic in `config/manager.py` — copies old config dir on first run, writes `MIGRATED.txt`
- Renamed `OrchestrationEngine` → `SquadronEngine`
- Updated README.md, docs/COMMANDS.md, docs/TEMPLATES.md
- 435 tests pass, `sq --help` and `squadron --help` both work

---

## 20260301

### Slice 114: Auth Strategy & Credential Management — Implementation Complete

Implemented all 18 tasks for slice 114. Added `AuthStrategy` protocol and `ApiKeyStrategy` in `providers/auth.py` — direct extraction of existing credential resolution from `OpenAICompatibleProvider`, same behavior. Added `resolve_auth_strategy()` factory and `AUTH_STRATEGIES` registry. Extended `ProviderProfile` with `auth_type` field (default `"api_key"`). Refactored `OpenAICompatibleProvider.create_agent()` to delegate to the strategy. Added `orchestration auth login <profile>` and `orchestration auth status` CLI commands. 435 tests pass; pyright and ruff clean.

New files: `src/orchestration/providers/auth.py`, `src/orchestration/cli/commands/auth.py`, `tests/providers/test_auth.py`, `tests/providers/test_auth_resolution.py`, `tests/cli/test_auth.py`.

---

### Slice 114: Auth Strategy & Credential Management — Design Complete

Research into OpenAI OAuth revealed the API has no general OAuth2 flow — authentication is purely key-based (project-scoped, service account). OAuth exists only for Codex subscription access (browser-based, ChatGPT Plus/Pro/Teams). This finding reshaped slice 114 from "implement OAuth" to "formalize auth strategy abstraction with API key as concrete implementation."

Documents created:
- `project-documents/user/slices/114-slice.oauth-advanced-auth.md` — slice design
- Updated `100-slices.orchestration-v2.md` — revised slice 114 entry, new slice 116 (Codex Agent Integration)

Key decisions:
- `AuthStrategy` protocol with `get_credentials()`, `refresh_if_needed()`, `is_valid()`
- `ApiKeyStrategy` as direct extraction of existing provider credential resolution
- `auth_type` field on `ProviderProfile` for strategy dispatch
- CLI `auth login`/`auth status` commands for credential validation
- Codex agent integration (OAuth) deferred to new slice 116

Scope: `AuthStrategy` protocol, `ApiKeyStrategy`, `ProviderProfile.auth_type`, CLI auth commands, provider refactor

| Hash | Description |
|------|-------------|
| `156d78f` | docs: add slice 114 design (auth strategy) and slice 116 entry (codex) |

---

### Slice 113: Provider Variants & Registry — Post-Merge Fix

Live testing with OpenRouter/Kimi revealed `credentials` dropped at daemon boundary. `SpawnRequest` was missing the field; fixed in `server/models.py` and `routes/agents.py`. Verified working end-to-end with OpenRouter profile.

| Hash | Description |
|------|-------------|
| `146ed4b` | fix: pass credentials through SpawnRequest to AgentConfig |

---

## 20260228

### Slice 113: Provider Variants & Registry — Complete

All 15 tasks implemented across 4 groups. 408 tests passing (31 new). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `b1831c0` | feat: add provider profile model and TOML loading |
| `7eb9eff` | feat: enhance credential resolution and default headers support |
| `45ec6b8` | feat: add --profile flag to spawn and models command |

**What works:**
- `ProviderProfile` frozen dataclass with 4 built-ins: `openai`, `openrouter`, `local`, `gemini`
- TOML loading from `~/.config/orchestration/providers.toml`; user profiles override built-ins
- Credential resolution chain: `config.api_key` → profile env var → `OPENAI_API_KEY` → localhost placeholder
- OpenRouter `default_headers` via `AsyncOpenAI(default_headers=...)` constructor
- `orchestration spawn --profile openrouter --model x` fully functional
- `orchestration models --profile local` for model discovery (direct HTTP, no daemon)

**Key decisions:**
- Profiles are data (frozen dataclass), not subclasses — all three variants reuse `OpenAICompatibleProvider`
- Localhost placeholder: `"not-needed"` when no API key and `base_url` starts with `http://localhost` or `http://127.0.0.1`
- `models` command calls `/v1/models` directly via `httpx`, bypassing daemon

**Next:** Slice 114 (OAuth & Advanced Auth)

---

### Slice 113: Provider Variants & Registry — Phase 4 Design Complete

Slice design created at `project-documents/user/slices/113-slice.provider-variants.md`.

Key design decisions:
- **Profiles, not subclasses**: All three variants (OpenRouter, local, Gemini) are configurations of `OpenAICompatibleProvider`, bundled as named `ProviderProfile` entries.
- **Separate `providers.toml`**: Structured profile data lives in its own file (`~/.config/orchestration/providers.toml`), not in the flat `config.toml`.
- **`--profile` CLI flag**: New flag on spawn command, separate from `--provider`. Profile provides defaults; CLI flags override.
- **Localhost auth bypass**: Local model servers get a placeholder API key (`"not-needed"`) instead of raising `ProviderAuthError`.
- **`models` command**: Direct HTTP query to `/v1/models` for model discovery, bypasses daemon.

| Hash | Description |
|------|-------------|
| `e399e5f` | docs: add slice 113 design |

### Slice 112: Local Server & CLI Client — Phase 7 Implementation Complete

All 27 tasks (T1-T27) implemented. 35 new tests (377 total project tests passing). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `e8350b2` | chore: add httpx dependency |
| `46c4380` | feat: add test infrastructure for server and client (T2) |
| `ae55e8b` | feat: implement OrchestrationEngine (T3) |
| `5301aa5` | test: add OrchestrationEngine tests (T4) |
| `d0591f6` | feat: add server models and health route (T5) |
| `73acbd8` | feat: add agent CRUD and messaging routes (T6) |
| `4a0dccb` | feat: add app factory and route tests (T7, T8) |
| `51b6f3d` | feat: add daemon module with PID management (T9) |
| `f6c74af` | feat: server core checkpoint (T11) |
| `48a5068` | feat: add DaemonClient (T12-T14) |
| `1733974` | feat: add serve command (T15-T16) |
| `c908121` | refactor: CLI commands use DaemonClient (T17-T20) |
| `2079bfd` | feat: add message and history commands (T21-T23) |
| `1de8866` | feat: validation pass and format fixes (T25) |
| `ca8b1f5` | test: add daemon integration test (T26-T27) |

**New modules:**
- `src/orchestration/server/engine.py` — OrchestrationEngine with agent lifecycle and conversation history
- `src/orchestration/server/models.py` — Pydantic request/response schemas
- `src/orchestration/server/routes/` — FastAPI agent CRUD, messaging, and health routes
- `src/orchestration/server/app.py` — Application factory
- `src/orchestration/server/daemon.py` — PID management, signal handling, dual-transport server
- `src/orchestration/client/http.py` — DaemonClient with Unix socket / HTTP transport
- `src/orchestration/cli/commands/serve.py` — `orchestration serve` with --status/--stop
- `src/orchestration/cli/commands/message.py` — `orchestration message`
- `src/orchestration/cli/commands/history.py` — `orchestration history` with --limit

**Refactored modules:**
- `spawn.py`, `list.py`, `task.py`, `shutdown.py` — all use DaemonClient instead of direct registry

**Next:** Slice 113 (Provider Variants & Registry).

---

### Slice 112: Local Server & CLI Client — Slice Design Complete

**Documents created:**
- `user/slices/112-slice.local-daemon.md` — slice design
- `user/slices/112-slice.local-daemon-agent-brief.md` — technical brief from PM

**Scope:** Persistent daemon process (`orchestration serve`) holding agent registry, agent instances, and conversation history in memory. CLI commands become thin clients communicating with daemon via Unix domain socket (primary) or localhost HTTP (secondary). New `OrchestrationEngine` composes existing `AgentRegistry` and adds conversation history tracking. FastAPI app serves both transports. New commands: `serve`, `message`, `history`. Existing commands (`spawn`, `list`, `task`, `shutdown`) refactored to use `DaemonClient`.

**Key design decisions:**
- `OrchestrationEngine` composes `AgentRegistry` (not subclass/replace) — registry manages lifecycle, engine adds history and coordination
- Dual transport: Unix socket (`~/.orchestration/daemon.sock`) for CLI, HTTP (`127.0.0.1:7862`) for external consumers — same FastAPI app serves both via two uvicorn instances
- `httpx.AsyncHTTPTransport(uds=path)` for CLI→daemon Unix socket communication
- Explicit `orchestration serve` — no auto-start magic, predictable daemon lifecycle
- All agent commands route through daemon — one execution path, enables future observability
- Conversation history at engine level (not just agent-internal) — provider-agnostic, supports `history` command
- Agent lifecycle categories: ephemeral (task) and session (spawn+message) — behavioral patterns, not formal types
- PID file + socket file in `~/.orchestration/` — stale file detection on startup
- `review` and `config` commands left unchanged for now (review uses SDK directly, config is stateless)

**Commit:** `dcab7a9` docs: add slice 112 design for local daemon & CLI client

**Next:** Phase 5 (Task Breakdown) on slice 112.

---

## 20260226

### Slice 111: OpenAI-Compatible Provider Core — Phase 7 Implementation Complete

All 17 tasks (T1-T17) implemented. 41 new tests (342 total project tests passing). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `3965380` | chore: add openai>=1.0.0 dependency |
| `b4d1da9` | feat: add OpenAI provider translation module with tests |
| `c53c64c` | feat: add OpenAICompatibleProvider with tests |
| `fba88e6` | feat: implement OpenAICompatibleAgent with tests |
| `ab12531` | feat: add OpenAI-compatible provider |
| `4c547c7` | feat: add provider auto-loader and --base-url to spawn command |

**What was added:**
- `providers/openai/` package: `translation.py`, `provider.py`, `agent.py`, `__init__.py`
- `OpenAICompatibleProvider`: API key resolution (config → env → ProviderAuthError), `AsyncOpenAI` client construction, `base_url` pass-through, explicit `ProviderError` on missing model
- `OpenAICompatibleAgent`: conversation history, streaming accumulation, tool call reconstruction by chunk index, full error mapping (AuthenticationError→ProviderAuthError, RateLimitError→ProviderAPIError(429), APIStatusError→ProviderAPIError(status_code), APIConnectionError→ProviderError, APITimeoutError→ProviderTimeoutError)
- `translation.py`: `build_text_message`, `build_tool_call_message`, `build_messages` — pure functions, independently testable
- Auto-registration: `get_provider("openai")` available after import
- `_load_provider(name)` auto-loader in `spawn.py` — lazy `importlib.import_module` triggers provider registration; silent `ImportError` catch; benefits all providers retroactively
- `--base-url` flag on `spawn` command — passed through to `AgentConfig.base_url`

**Architecture note:** Per-agent `AsyncOpenAI` client (not per-provider) — credentials and `base_url` are per-agent concerns. Accumulate full stream then yield complete `Message` objects to preserve `AsyncIterator[Message]` Protocol contract. Validated that `AgentProvider` Protocol generalizes beyond Anthropic with zero core engine changes.

**Issues logged:** None.

**Next:** Slice 112 (Provider Variants & Registry — OpenRouter, local, Gemini configs + model alias profiles).

### Slice 111: OpenAI-Compatible Provider Core — Slice Design Complete

**Documents created:**
- `user/slices/111-slice.openai-provider-core.md` — slice design (410 lines)

**Scope:** `OpenAICompatibleProvider` and `OpenAICompatibleAgent` using the `openai` Python SDK's `AsyncOpenAI` client with `base_url` override. Single implementation covers OpenAI, OpenRouter, Ollama/vLLM, and Gemini-compatible endpoints. Validates that `AgentProvider` Protocol generalizes beyond Anthropic with no core engine changes. Also fixes provider auto-loader gap in `spawn.py` and adds `--base-url` CLI flag.

**Key design decisions:**
- Per-agent `AsyncOpenAI` client (not per-provider) — credentials and `base_url` are per-agent concerns
- Accumulate full stream response before yielding `Message` objects — preserves `AsyncIterator[Message]` Protocol contract; streaming-through deferred as future evolution
- No silent model default — `ProviderError` if `config.model` is None (billing concern)
- Tool calls surfaced as `system` Messages with metadata; no execution (needs message bus + executor, future slice)
- `_load_provider(name)` auto-loader via `importlib.import_module` in `spawn.py` — silent `ImportError` catch; benefits all current and future providers retroactively
- Model alias / provider profile registry (`codex_53` → openai + model + base_url) deferred to slice 112

**Commit:** `864ed9c` docs: add slice design for 111-openai-provider-core

### Slice 111: OpenAI-Compatible Provider Core — Task Breakdown Complete

Task file created at `project-documents/user/tasks/111-tasks.openai-provider-core.md` (169 lines, 17 tasks). Test-with pattern applied; two commit checkpoints (T11 after providers/openai, T17 after CLI changes).

**Tasks overview:** T1 add dependency → T2 test infra → T3-T4 translation.py → T5-T6 provider.py → T7-T8 agent.py → T9-T10 `__init__.py` registration → T11 commit → T12-T13 auto-loader → T14-T15 `--base-url` flag → T16 full validation → T17 commit.

**Commit:** `5f4a7be` docs: add task breakdown for 111-openai-provider-core

---

## 20260223

### Model selection support (Issue #2)

Added `--model` flag to all review commands and spawn. Model threads through the full pipeline: config key (`default_model`) → ReviewTemplate YAML field → runner → `ClaudeAgentOptions`. Precedence: CLI flag → config → template default → None (SDK default). Template defaults: `opus` for arch/tasks, `sonnet` for code. Model shown in review output panel header at all verbosity levels. 17 new tests (298 total).

**Commit:** `9eae0f7` feat: add model selection support to review and spawn commands

### Rate limit handling fix (Issue #1)

Replaced the retry-entire-session loop (3 retries, 10s delay each) with a `receive_response()` restart on the same session. The SDK's `MessageParseError` (not publicly exported) fires on `rate_limit_event` messages the CLI emits while handling API rate limits internally. Fix catches `ClaudeSDKError` (public parent) with string match, restarts the async generator on the same connected session (anyio channel survives generator death), circuit breaker at 10 retries. Eliminates ~10-20s unnecessary delay. 3 new tests (301 total).

### Post-implementation: code review findings and fixes

Ran `orchestration review code` against its own codebase. Addressed three findings from the review:

1. **`_coerce_value` guard** — added explicit `str` check and `ValueError` for unsupported types (was silently falling through)
2. **Unknown config key warnings** — `load_config` now logs warnings for unrecognized keys in TOML files (catches typos)
3. **Double template loading** — `_execute_review` now accepts `ReviewTemplate` directly instead of re-loading by name
4. **CLAUDE.md exception** — documented that public-facing docs (`docs/`, root `README.md`) are exempt from YAML frontmatter rule

Also added rate-limit retry (3 attempts, 10s delay) in runner and friendlier CLI error message.

**Deferred findings** (logged for future work):
- Duplicated `cli_runner` fixture across 6 test files → promote to root `conftest.py`
- `_resolve_verbosity` can't override config back to 0 from CLI → consider `--quiet` flag

---

## 20260222

### Slice 106: M1 Polish & Publish — Phase 7 Implementation Complete

All 22 tasks (T1-T22) implemented. 49 new tests (28 config + 12 verbosity + 6 rules + 3 cwd), 281 total project tests passing. Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `9034843` | feat: add persistent config system with TOML storage |
| `196f03f` | feat: add config CLI commands (set, get, list, path) |
| `b002801` | feat: add verbosity levels and improve text colors |
| `b945fb4` | feat: add --rules flag, config-based cwd, and rules injection |
| `85c953e` | chore: format and fix pyright issues in slice 106 code |
| `eb44cef` | docs: add README, COMMANDS, and TEMPLATES documentation |

**What was added:**
- `config/` package: typed key definitions, TOML load/merge/persist manager, user + project config with precedence
- Config CLI: `config set/get/list/path` commands
- Verbosity levels (0/1/2) with `-v`/`-vv` flags on all review commands
- Text color improvements: bright severity badges, white headings, default foreground body text
- `--rules` flag on `review code` with config-based `default_rules`
- Config-based `--cwd` resolution across all review commands
- Documentation: `docs/README.md`, `docs/COMMANDS.md`, `docs/TEMPLATES.md`

**Architecture note:** `config.py` restructured to `config/__init__.py` package (same pattern as templates in slice 105) to coexist with `keys.py` and `manager.py`. TOML reading via stdlib `tomllib`, writing via `tomli-w`.

### Slice 106: M1 Polish & Publish — Phase 5 Task Breakdown Complete

Task file created at `project-documents/user/tasks/106-tasks.m1-polish-and-publish.md` (219 lines, 22 tasks).

**Commit:** `09a69cd` docs: add slice 106 task breakdown (m1-polish-and-publish)

### Slice 105: Review Workflow Templates — Phase 7 Implementation Complete

All 22 tasks (T1-T22) implemented. 76 review-specific tests, 226 total project tests passing. Zero pyright/ruff errors. Build succeeds.

**Key commits:**
| Hash | Description |
|------|-------------|
| `29c53e2` | feat: add pyyaml dependency |
| `dc8a4a4` | feat: add review result models |
| `fad9109` | feat: add ReviewTemplate, YAML loader, and registry |
| `1d29679` | refactor: restructure templates as package with builtin directory |
| `ea5839d` | feat: add built-in review templates (arch, tasks, code) |
| `a430358` | feat: add review result parser |
| `bff53a0` | feat: add review runner |
| `2feca18` | feat: add review CLI subcommand |
| `74eca88` | chore: review slice 105 final validation pass |

**Architecture note:** `templates.py` moved to `templates/__init__.py` package to coexist with `templates/builtin/` YAML directory. SDK literal types handled via `type: ignore` comments since template values are dynamic from YAML.

### Slice 105: Review Workflow Templates — Phase 5 Task Breakdown Complete

Task file created at `project-documents/user/tasks/105-tasks.review-workflow-templates.md` (210 lines, 22 tasks). Covers result models, YAML loader/registry, three built-in templates (arch, tasks, code), result parser, review runner, and CLI subcommand. Test-with ordering applied throughout; commit checkpoints after each stable milestone. Merge conflict in slice frontmatter resolved by PM prior to task creation.

---

## 20260220

### Slice 103: CLI Foundation & SDK Agent Tasks — Implementation Complete

**Commits:**
| Hash | Description |
|------|-------------|
| `8e76a6d` | feat: add Typer app scaffolding and pyproject.toml entry point |
| `4a4a478` | feat: implement CLI commands (spawn, list, task, shutdown) and test infra |
| `faaa5cc` | feat: refactor CLI commands to plain functions + add command tests |
| `b58d539` | feat: add integration smoke test + fix lint/type issues |

**What works:**
- 150 tests passing (22 new + 128 existing), ruff clean, pyright zero errors on src/ and tests/cli/
- `orchestration spawn --name NAME [--type sdk] [--provider P] [--cwd PATH] [--system-prompt TEXT] [--permission-mode MODE]`
- `orchestration list [--state STATE] [--provider P]` — rich table with color-coded state
- `orchestration task AGENT PROMPT` — `handle_message` async bridge, displays text and tool-use summaries
- `orchestration shutdown AGENT` / `orchestration shutdown --all` — individual and bulk with `ShutdownReport`
- `pyproject.toml` entry point registered; `orchestration --help` works
- All commands use `asyncio.run()` bridge pattern (sync Typer → async registry/agent)
- Unit tests: mocked registry via `patch_registry` fixture; integration smoke test: real registry + mock provider

**Key decisions:**
- Commands registered as plain functions via `app.command("name")(fn)` — not sub-typers. Sub-typers created nested groups (`spawn spawn --name`) rather than flat commands (`spawn --name`).
- `task` command uses `agent.handle_message(message)` (the actual Agent Protocol method), not a hypothetical `query()` method referenced in the task design
- `asyncio.run()` per command invocation — no persistent event loop, clean for CLI use
- Integration test patches the provider registry (not the agent registry) to use a mock SDK provider

**Issues logged:** None.

**Next:** Slice 5 (SDK Client Warm Pool).

---

## 20260219

### Slice 103: CLI Foundation & SDK Agent Tasks — Design and Task Breakdown Complete

**Documents created:**
- `user/slices/103-slice.cli-foundation.md` — slice design
- `user/tasks/103-tasks.cli-foundation.md` — 11 tasks, test-with pattern

**Scope:** Typer CLI with four commands (`spawn`, `list`, `task`, `shutdown`) wiring the full path from terminal through Agent Registry and SDK Agent Provider to Claude execution. Async bridge via `asyncio.run()`. Rich output formatting (tables for `list`, styled text for responses). User-friendly error handling for all known failure modes. `pyproject.toml` script entry point. Integration smoke test (spawn → list → task → shutdown). **Completes Milestone 1.**

**Next:** Phase 7 (Implementation) on slice 103.

---

### Slice 102: Agent Registry & Lifecycle — Implementation Complete

**Commits:**
| Hash | Description |
|------|-------------|
| `23747c4` | feat: add AgentRegistry core with models, errors, spawn, and lookup |
| `9a40ff3` | feat: add list_agents filtering and individual shutdown to AgentRegistry |
| `26f61b4` | feat: add bulk shutdown and singleton accessor to AgentRegistry |
| `16d2a8a` | chore: fix linting, formatting, and type errors for agent registry |
| `a045636` | docs: mark slice 102 (Agent Registry & Lifecycle) as complete |

**What works:**
- 127 tests passing (26 new + 101 existing), ruff clean, pyright zero errors on src/ and new test file
- `AgentInfo` and `ShutdownReport` Pydantic models in `core/models.py`
- `AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError` error hierarchy
- `AgentRegistry.spawn()`: resolves provider, creates agent, tracks by unique name
- `AgentRegistry.get()`, `has()`: lookup by name with proper error raising
- `AgentRegistry.list_agents()`: returns `AgentInfo` summaries with optional state/provider filtering
- `AgentRegistry.shutdown_agent()`: always-remove semantics (agent removed even if shutdown raises)
- `AgentRegistry.shutdown_all()`: best-effort bulk shutdown returning `ShutdownReport`
- `get_registry()` / `reset_registry()` singleton accessor

**Key decisions:**
- Imports moved above error class definitions (ruff E402) — error classes placed after imports, not before
- `AgentInfo.provider` sourced from stored `AgentConfig`, not from the agent object (registry owns this mapping)
- `shutdown_agent()` uses try/finally to guarantee removal regardless of shutdown errors
- `shutdown_all()` collects errors per-agent without aborting — returns structured `ShutdownReport`
- MockAgent uses `set_state()` method instead of direct `_state` access to satisfy pyright's `reportPrivateUsage`

**Issues logged:** None.

**Next:** Slice 4 (CLI Foundation & SDK Agent Tasks).

---

### Slice 102: Agent Registry & Lifecycle — Design and Task Breakdown Complete

**Documents created:**
- `user/slices/102-slice.agent-registry.md` — slice design
- `user/tasks/102-tasks.agent-registry.md` — 14 tasks, test-with pattern

**Scope:** `AgentRegistry` class in `core/agent_registry.py` — spawn, get, has, list_agents (with state/provider filtering), shutdown_agent, shutdown_all. Registry errors (`AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError`). `AgentInfo` and `ShutdownReport` models added to `core/models.py`. Module-level `get_registry()` singleton. All tests use mock providers.

**Next:** Phase 7 (Implementation) on slice 102.

---

### Slice 101: SDK Agent Provider — Complete

**Objective:** Implement the first concrete provider — `SDKAgentProvider` and `SDKAgent` wrapping `claude-agent-sdk` for one-shot and multi-turn agent execution.

**Commits:**
| Hash | Description |
|------|-------------|
| `b44914a` | feat: implement SDK message translation module with tests |
| `f7d15e0` | feat: implement SDKAgentProvider with options mapping and tests |
| `3055fcf` | feat: implement SDKAgent with query and client modes |
| `83611a5` | feat: auto-register SDK provider and add integration tests |
| `8743255` | chore: fix linting, formatting, and type errors |

**What works:**
- 96 tests passing (51 new + 45 foundation), ruff clean, pyright strict zero errors
- `translation.py`: Converts SDK message types (AssistantMessage, ToolUseBlock, ToolResultBlock, ResultMessage) to orchestration Messages
- `SDKAgentProvider`: Maps `AgentConfig` to `ClaudeAgentOptions`, defaults `permission_mode` to `"acceptEdits"`, reads mode from `credentials` dict
- `SDKAgent` query mode: One-shot via `sdk_query()`, translates and yields response messages
- `SDKAgent` client mode: Multi-turn via `ClaudeSDKClient` (create once, reuse), `shutdown()` disconnects
- Error mapping: All 5 SDK exception types → orchestration `ProviderError` hierarchy
- Auto-registration: Importing `orchestration.providers.sdk` registers `"sdk"` in the provider registry
- `validate_credentials()` returns bool without throwing

**Key decisions:**
- `translate_sdk_message` returns `list[Message]` (not `Message | None`) — `AssistantMessage` with multiple blocks produces multiple Messages, empty list for unknown types
- Deferred import of `SDKAgent` in `provider.py` to avoid stub-state issues at module load
- ruff requires `query as sdk_query` alias in a separate import block from other `claude_agent_sdk` imports (isort rule)
- Used `__import__("claude_agent_sdk")` in `validate_credentials` to satisfy pyright's `reportUnusedImport`
- Real SDK dataclasses used for test fixtures (no MagicMock — `TextBlock`, `AssistantMessage`, etc. are simple dataclasses)

**Issues logged:** None.

**Next:** Slice 3 (Agent Registry & Lifecycle) or slice 4 (CLI Foundation).

---

### Slice 100: Foundation Migration — Complete

**Objective:** Migrate foundation from v1 (LLMProvider-based) to v2 (dual-provider Agent/AgentProvider architecture) per `100-arch.orchestration-v2.md`.

**Commits:**
| Hash | Description |
|------|-------------|
| `7200b4e` | feat: add claude-agent-sdk dependency |
| `b6e1264` | feat: add SDK and Anthropic provider subdirectories with stubs |
| `6a389a5` | feat: add shared provider error hierarchy |
| `9700bed` | refactor: rename Agent to AgentConfig, remove ProviderConfig |
| `5ebf6cb` | test: update model tests for AgentConfig migration |
| `2433494` | refactor: replace LLMProvider with Agent and AgentProvider Protocols |
| `0b4302e` | refactor: retype provider registry for AgentProvider instances |
| `90dd38b` | test: update provider tests for AgentProvider instances and error hierarchy |
| `cb1d56c` | refactor: update Settings for dual-provider architecture |
| `0d3da45` | test: update config tests for new Settings fields |
| `f944f02` | docs: update .env.example for dual-provider architecture |
| `fd45a0d` | docs: update stub docstrings with correct slice numbers |
| `f189dc2` | fix: type checking — zero pyright errors |
| `5aaf718` | docs: mark foundation migration tasks and slice complete |

**What works:**
- 45 tests passing, ruff check clean, ruff format clean, pyright strict zero errors
- `AgentConfig` model with SDK-specific fields (cwd, setting_sources, allowed_tools, permission_mode) and API fields (model, api_key, auth_token, base_url)
- `Agent` and `AgentProvider` Protocols (runtime_checkable, structural typing)
- Provider registry maps type names to `AgentProvider` instances
- Shared error hierarchy: `ProviderError` → `ProviderAuthError`, `ProviderAPIError`, `ProviderTimeoutError`
- Settings with `default_provider="sdk"`, `default_agent_type="sdk"`, auth token and base URL support
- Provider subdirectories: `providers/sdk/` and `providers/anthropic/` with stubs
- All stub docstrings updated to correct slice numbers per v2 plan

**Key decisions:**
- `handle_message` in Agent Protocol is a sync method signature (not `async def`) — implementations are async generators, callers use `async for` directly without `await`
- `ProviderTimeoutError` chosen over `ProviderConfigError` — config errors caught at Pydantic validation time; timeout is the real operational concern
- `sdk_default_cwd` kept off Settings (per-agent config via AgentConfig, not global)
- `claude-agent-sdk` imports as `claude_agent_sdk` (module name differs from package name)

**Issues logged:** None.

**Next:** Slice 2 (SDK Agent Provider) or slice 101 (Anthropic Provider) — both can proceed in parallel as they only depend on foundation.

---

## 20260218

### Slice 101: Anthropic Provider — Design Complete

**Documents created:**
- `user/slices/101-slice.anthropic-provider.md` — slice design

**Key design decisions:**
- **API key auth only**: The official Anthropic Python SDK supports `api_key` / `ANTHROPIC_API_KEY` exclusively. No native `auth_token` parameter exists. Claude Max / OAuth bearer token usage requires external gateways (e.g., LiteLLM) — out of scope for this slice but extensible via `ProviderConfig.extra["base_url"]` in future.
- **Async-only client**: `AsyncAnthropic` exclusively — no sync path needed given async framework.
- **SDK streaming helper**: Uses `client.messages.stream()` context manager (not raw `stream=True`) for typed text_stream iterator and automatic cleanup.
- **Minimal error hierarchy**: `ProviderError` → `ProviderAuthError`, `ProviderAPIError`. SDK exceptions mapped to provider-level errors at boundaries.
- **No custom retry**: SDK built-in retry (2 retries, exponential backoff) is sufficient.
- **Default max_tokens=4096**: Required by Anthropic API, configurable via `ProviderConfig.extra`.

**Scope summary:**
- `AnthropicProvider` class satisfying `LLMProvider` Protocol (send_message, stream_message, validate)
- Message conversion: `orchestration.Message` → Anthropic dict format (role mapping, system extraction, consecutive role merging)
- API key resolution: `ProviderConfig.api_key` → `Settings.anthropic_api_key` → explicit error
- Auto-registration in provider registry via `providers/__init__.py`
- Full mock-based test suite (no real API calls)

**Commits:**
- `3c418e0` docs: add slice 101 design (Anthropic Provider)

**Next:** Phase 5 (Task Breakdown) on slice 101, then Phase 7 (Implementation).

### Slice 100: Foundation — Design and Task Creation Complete

**Documents created:**
- `user/slices/100-slice.foundation.md` — slice design (project setup, package structure, core Pydantic models, config, logging, provider protocol, test infrastructure)
- `user/tasks/100-tasks.foundation.md` — 19 granular tasks, sequentially ordered

**Key design decisions:**
- **Test-with ordering**: Tasks are structured so each implementation unit (models, providers, config, logging) is immediately followed by its tests, catching contract issues early rather than batching tests at the end
- **All dependencies installed up front**: `pyproject.toml` includes all project dependencies (anthropic, typer, fastapi, google-adk, mcp, etc.) so later slices just import and use
- **Protocol over ABC**: `LLMProvider` defined as a `Protocol` for structural typing, better ADK compatibility later
- **Stdlib logging only**: No third-party logging library; JSON formatter on stdlib `logging` keeps dependencies minimal

**Scope summary:**
- Project init with `uv`, `src/orchestration/` package layout matching HLD 4-layer architecture
- Pydantic models: Agent, Message, ProviderConfig, TopologyConfig (with StrEnum types)
- Pydantic Settings for env-based config (`ORCH_` prefix), `.env.example`
- LLMProvider Protocol + dict-based provider registry
- Structured logging (JSON + text formats)
- Full test infrastructure and validation pass

**Commits:**
- `007b02f` planning: slice 100 foundation — design and task breakdown complete

**Next:** Phase 6 (Task Expansion) on `100-tasks.foundation.md`, or proceed directly to Phase 7 (implementation) if PM approves skipping expansion for this low-complexity slice.
