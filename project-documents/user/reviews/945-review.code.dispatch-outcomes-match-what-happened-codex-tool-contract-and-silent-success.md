---
docType: review
layer: project
reviewType: code
slice: dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: 6af743d161e3fd34f1c3793b0b754e30b21e23a4
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 40
diffTruncated: false
turns: 20
promptTokens: 1276976
cachedTokens: 1102464
completionTokens: 35795
reasoningTokens: 31426
durationSeconds: 132.0
squadronVersion: 0.21.7
findings:
  - id: F001
    severity: concern
    category: uncategorized
    summary: "Accepted set is \"anything not a write tool\", so non-read squadron tools pass silently into Codex"
    location: "src/squadron/providers/codex/agent.py:66"
  - id: F002
    severity: concern
    category: uncategorized
    summary: "Refusal message hardcodes `write_file`/`bash` instead of deriving them from `WRITE_TOOL_NAMES`"
    location: "src/squadron/providers/codex/agent.py:31-34"
  - id: F003
    severity: note
    category: uncategorized
    summary: "The new acceptance test states the template list rather than deriving it, and the refusal-ordering test does not prove ordering"
    location: "tests/providers/codex/test_agent.py:165-170"
---

# Review: code — slice 945

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Accepted set is "anything not a write tool", so non-read squadron tools pass silently into Codex

The guard is `config.allowed_tools and not WRITE_TOOL_NAMES.isdisjoint(config.allowed_tools)`, so every name outside `WRITE_TOOL_NAMES` is accepted — not only read tools. `WRITE_TOOL_NAMES` is `frozenset({WRITE_FILE_NAME, BASH_NAME})` (`src/squadron/tools/builtin/_shared.py:24`), while the registry contains more than read tools: `cf_tools.py` registers `cf_set_phase`, `cf_set_slice`, `cf_build_context`, `cf_prompt_get`, `cf_workflow_status`, and `squadron/tools/__init__.py` imports `cf_tools` unconditionally so they are always registered. `validate_allowed_tools` (`pipeline/steps/utils.py:32`) accepts any registered name, so `allowed_tools: [cf_set_phase]` on a Codex step now constructs a `CodexAgent` without complaint — yet the agent never materializes tools (`_run_prompt` calls the SDK directly; there is no `tools.materialize` call in this file), so the grant is a no-op exactly as `write_file` was.

The safety net does not cover this either: `CodexAgent.handle_message` stamps only `{"turns", "usage"}` on the yielded Message (src/squadron/providers/codex/agent.py ~line 94), never `TOOLS_GIVEN_KEY`/`TOOL_CALLS_MADE_KEY`, and `assess_tool_outcome` returns early unless `TOOL_CALLS_MADE_KEY` is present (`pipeline/actions/dispatch_outcome.py:44`). Before this change a declared `cf_set_phase` was refused loudly; now it dispatches and reports success on a grant it never got, which is the failure (#211) this guard exists to prevent. If the intent is "read tools only", that set needs to be named (there is no `READ_TOOL_NAMES` constant anywhere under `src/` — I checked) and the guard should test membership in it rather than the complement of the write set.

### [CONCERN] Refusal message hardcodes `write_file`/`bash` instead of deriving them from `WRITE_TOOL_NAMES`

`_TOOLS_REFUSAL` spells out "remove `write_file`/`bash` from `allowed_tools`" while the trigger is `WRITE_TOOL_NAMES`. Adding a third write-capable tool to `WRITE_TOOL_NAMES` would make the guard refuse that tool while the message names two others — the value that decides the branch and the value shown to the user are two separate sources. The project rule is explicit: "If a value is used in conditionals, switch cases, or lookups, define it once (enum, constant, or config) and reference that definition everywhere." The tests already encode the same duplication independently (`["write_file", "bash"]` at `tests/providers/codex/test_agent.py:154`), so a rename or addition would need three coordinated edits and none of them would fail loudly. Building the message from `sorted(WRITE_TOOL_NAMES)` (or the constants themselves) keeps the default read-only refusal's style of naming the fix without restating the set.

### [NOTE] The new acceptance test states the template list rather than deriving it, and the refusal-ordering test does not prove ordering

`test_review_template_read_tools_accepted` hardcodes `["read_file", "list_files", "grep"]`. That matches all eight shipped templates (verified: `arch.yaml:122`, `code.yaml:57`, `slice.yaml:62`, `tasks.yaml:62`, `judge-*.yaml:50/67/67` each declare exactly `[read_file, list_files, grep]`), so the literal is currently correct — but the docstring says "every review template declares these", and a template that adds or drops a read tool will not fail this test. Loading the real template through `load_all_templates` would make the claim self-checking and would also have surfaced the `cf_*` case above. Separately, `test_allowed_tools_refused_before_the_sandbox_is_checked` (`:173-180`) only asserts the error text; with `requires_writes: True` and no pinned sandbox, the sandbox path resolves to `workspace_write` and would not refuse anyway, so the test cannot distinguish "tools checked first" from "sandbox checked first". The ordering is real in the constructor — it is just not what the test demonstrates.

### Run Digest

- Response length: 4675 chars
- Response is newline-free: no
- Tool calls made: 40
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 126619
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 1276976 / 1102464 / 35795 / 31426
- Duration: 132.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 3
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 3
- Finding-shaped matches — surviving validation: 3

## Response

All three fixed in the commit after 6af743d1.

- **F001** fixed: new `READ_TOOL_NAMES` (`read_file`, `list_files`, `grep`) in `tools/builtin/_shared.py`. Codex accepts only tools in that set and refuses everything else, `cf_*` tools included. Test parametrizes over `WRITE_TOOL_NAMES` plus `cf_set_phase`.
- **F002** fixed: the refusal message is built from `READ_TOOL_NAMES` and from the tools actually refused, so nothing is restated.
- **F003** fixed: the acceptance test loads every shipped review template and constructs a Codex agent with its `allowed_tools`. The ordering test pins the sandbox to `read-only` and sends a message, so both refusals can fire; it fails if the sandbox refusal came first.
