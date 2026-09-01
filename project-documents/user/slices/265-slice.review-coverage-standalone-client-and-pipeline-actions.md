---
docType: slice-design
project: squadron
slice: 265-slice.review-coverage-standalone-client-and-pipeline-actions
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [261, 262, 263]
interfaces: [266]
dateCreated: 20260901
dateUpdated: 20260901
status: complete
---

# Slice Design: Review Coverage — Standalone Client and Pipeline Actions

## Parent Documents

- Architecture: `260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
- Slice Plan: `260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`, entry 5

## Overview

Slices 261–264 built the tool stack and proved it on the `dispatch` path. Reviews were left
behind on two fronts, and merging 264 exposed a third.

**Front 1 — reviews cannot use tools.** `run_review_with_profile` already passes
`template.allowed_tools` into `AgentConfig` ([review_client.py:116](src/squadron/review/review_client.py#L116)),
and slice 262 made the non-SDK agent honor that field. But every shipped review template
declares its tools in *Claude Code* vocabulary (`[Read, Glob, Grep, Bash]`), and the non-SDK
agent looks those names up in the squadron registry, finds nothing, logs a warning, and runs
tool-less ([agent.py:126-133](src/squadron/providers/openai/agent.py#L126-L133)). Issue #68 is
therefore still open in practice even after 262: the plumbing works, the vocabulary does not
line up, and the mismatch degrades silently.

**Front 2 — a tool-enabled reviewer would still get pre-injected files.** The review client
decides injection on `provider.capabilities.can_read_files`
([review_client.py:85](src/squadron/review/review_client.py#L85)), a static per-provider flag
that is `False` for every OpenAI-compatible profile regardless of what tools the run actually
has. A tool-capable non-SDK reviewer would get the whole file corpus stuffed into its prompt
*and* the tools, paying twice for the same context.

**Front 3 — tool use is invisible.** Confirming that slice 264's live run had actually called
tools required reading model prose out of `~/.config/squadron/runs/*.json` and hand-checking
the values against live context-forge state. Nothing in run state or `-v` output records that
tools were offered, let alone that any were called. This was promoted to *primary* acceptance
for this slice on 20260901: a step that was offered tools and used none must be visually
distinct from one that used them, without reading source or run JSON.

This slice closes all three. It is the last correctness slice of initiative 260 — 266 only
adds configuration knobs on top of what lands here.

## Value

- **Reviews gain file access on non-SDK models.** A reviewer running on kimi27 or a local
  model can open the file a diff hunk came from, grep for the other call sites of a changed
  function, and list a directory it was not handed — the same context-discovery loop the SDK
  reviewer has always had via Read+Glob+Grep. Review quality on cheap models stops being
  capped by what fits in a pre-built prompt.
- **One tool vocabulary.** After this slice, `allowed_tools` means squadron registry names
  everywhere it is declared — templates, pipeline YAML, models.toml (266). Providers translate
  at their own edge. A name that is not in the registry fails at load time instead of
  degrading to a tool-less run.
- **Tool use becomes observable.** `sq run <pipeline> <slice> -v` answers "did tool use work"
  on its own, and the answer persists in run state for later comparison.
- **Unblocks 266.** The baseline-vs-tools comparison workflow needs the tools-enabled and
  tool-call-count fields this slice records; without them, two runs of the same model are
  indistinguishable in stored results.

## Technical Scope

### In Scope

1. **Read-only search tools** — `list_files` and `grep` registered in the slice-261 registry
   alongside the existing `read_file`, using the same CWD-jail helpers.
2. **Canonical tool vocabulary** — the seven shipped templates migrate from Claude names to
   squadron names; a single mapping table translates canonical → Claude at the SDK
   config-build edge; unknown canonical names become a load-time error.
3. **Injection decision** — a run-scoped signal replaces the static `can_read_files` check, so
   a tool-enabled review injects the diff but not full file bodies.
4. **Pipeline `review` and `summary` actions** — thread `allowed_tools` the way `dispatch`
   already does.
5. **Tool-use observability** — the agent reports tools-given and tool-calls-made on the final
   message; dispatch/review/summary carry it into `ActionResult.metadata`; the executor prints
   it at `-v`; run state and review persistence store it.

### Out of Scope

- **`tool_use` capability field in models.toml and `sq review --no-tools`** — slice 266.
- **Write or shell tools on the review path.** Reviews get `read_file`, `list_files`, `grep`
  and nothing else. `code.yaml` currently declares `Bash`; the migration drops it rather than
  mapping it (see D6).
- **Streaming intermediate tool turns to the caller.** Unchanged from 262 — the observability
  here is counts and names, not a per-call event feed.
- **Changing what the SDK reviewer does.** The SDK path must behave identically before and
  after the vocabulary migration; that is a success criterion, not a hope.
- **Retiring `_inject_file_contents`.** It stays, and stays the default. Only the tool-enabled
  branch skips it.

## Architecture

### Component map

```
review templates (7 YAML)          pipeline YAML (review/summary steps)
        │ canonical names                    │ canonical names
        ▼                                     ▼
  ReviewTemplate.allowed_tools ──────► ReviewAction / SummaryAction
        │                                     │
        └──────────────┬──────────────────────┘
                       ▼
            run_review_with_profile
                       │
        ┌──────────────┴───────────────┐
        │ effective tools = f(template, provider)
        ▼                              ▼
  tools non-empty                 tools empty
  → inject diff only         → inject diff + file bodies (today's path)
        │                              │
        └──────────────┬───────────────┘
                       ▼
                  AgentConfig.allowed_tools
                       │
        ┌──────────────┴───────────────┐
        ▼                              ▼
  OpenAICompatibleAgent          SDK provider
  (registry lookup, 262 loop)    (canonical → Claude map, config edge)
        │
        ▼
  final Message.metadata {tools_given, tool_calls_made}
        │
        ▼
  ActionResult.metadata ──► executor -v line ──► RunState.action_results
                        └──► ReviewResult ──► persisted review JSON
```

### The capability signal (front 2)

`can_read_files` stays exactly as it is and keeps its current meaning: *this provider reads
files by itself, without squadron handing it tools* — true for SDK and Codex, false for
OpenAI-compatible. It is a provider property and it is correctly static.

What the injection decision actually needs is a different question: *does this run have
file-reading tools?* That is a property of the run, not the provider, so it is computed in the
review client rather than stored on `ProviderCapabilities`:

```
inject_file_bodies = not provider.capabilities.can_read_files
                     and not effective_tools_include_a_reader
```

`effective_tools` is the template's `allowed_tools` filtered to names the registry knows
(non-SDK) or passed through untouched (SDK, which resolves them itself). This adds no field
to `ProviderCapabilities`, encodes no provider identity, and degrades correctly: a template
with no tools, or a provider that cannot use them, injects exactly as it does today.

The arch left this open as "e.g. `supports_tool_use` on `ProviderCapabilities`, or
`can_read_files` made config-dependent — decided in slice design." Both alternatives are
rejected in D1.

### Vocabulary migration (front 1)

Canonical squadron names are the declaration format. The SDK translates at its config-build
edge, [provider.py:56-57](src/squadron/providers/sdk/provider.py#L56-L57), which is the single
place `allowed_tools` reaches `ClaudeAgentOptions`:

| canonical    | Claude Code |
|--------------|-------------|
| `read_file`  | `Read`      |
| `list_files` | `Glob`      |
| `grep`       | `Grep`      |
| `write_file` | `Write`     |
| `bash`       | `Bash`      |

The table lives in one module-level mapping. A canonical name with no mapping is an error at
the point of translation, never a silent drop — and correspondingly, the non-SDK agent's
current warn-and-continue on unknown names ([agent.py:126-133](src/squadron/providers/openai/agent.py#L126-L133))
is tightened to a raise (D3). Both directions of "name I don't recognize" become loud.

`list_files` maps to `Glob` because Glob is what the SDK reviewer actually uses for
directory/pattern discovery; there is no separate SDK "list" tool.

### Observability (front 3)

The agent's only caller-facing surface is the `Message` stream, and every caller concatenates
`.content`. The count rides on `Message.metadata` of the **final** yielded message — the field
already exists ([core/models.py:74](src/squadron/core/models.py#L74)), callers that ignore it
are unaffected, and no protocol or agent-type surface changes:

```python
Message(
    content=final_text,
    metadata={
        "tools_given": ["read_file", "list_files", "grep"],
        "tool_calls_made": 3,
    },
)
```

`tools_given` is emitted whenever the agent was constructed with a non-empty effective tool
set — including when `tool_calls_made` is 0. That zero is the entire point: it distinguishes
"offered tools, used none" from "never offered tools" (`tools_given` absent). Both the
tool-less fast path and the agentic-loop path stamp it, so the two branches of
`handle_message` cannot drift.

From there the value flows outward by the routes each caller already uses:

- **`one_shot_dispatch`** currently discards `response.metadata` while concatenating content.
  It returns a bare `str`; it grows a sibling that returns text plus telemetry so
  `DispatchAction` can populate `ActionResult.metadata`. The existing `str`-returning
  signature is preserved for its other callers.
- **`run_review_with_profile`** carries the counts onto `ReviewResult` as two new optional
  fields, which flow into `to_dict()` and the persisted JSON.
- **`_log_action_result`** ([executor.py:94-107](src/squadron/pipeline/executor.py#L94-L107))
  already renders `verdict=` and `model=` from `result.metadata` into the `-v` line. It gains
  one more extra, so the `-v` output reads:

```
    -> ok (model=kimi27, tools=3/3 calls)     # 3 tools offered, 3 calls made
    -> ok (model=kimi27, tools=3/0 calls)     # offered, never used  ← the distinguishing case
    -> ok (model=kimi27)                       # no tools offered at all
```

`RunState.action_results` is `list[dict[str, object]]` ([state.py:95](src/squadron/pipeline/state.py#L95))
and already receives action metadata, so persistence needs no schema change and no
`schema_version` bump.

## Integration Points

| Surface | File | Change |
|---|---|---|
| Search tools | `tools/builtin.py` | Add `list_files`, `grep` descriptors + registration |
| Tool name map | `providers/sdk/provider.py` (or a new `providers/sdk/tool_names.py`) | Canonical → Claude table, applied at config build |
| Unknown-name policy | `providers/openai/agent.py` | Warn-and-drop → raise |
| Telemetry stamp | `providers/openai/agent.py` | `tools_given` / `tool_calls_made` on final Message |
| Injection decision | `review/review_client.py` | Replace bare `can_read_files` check; accept effective tools |
| Review result fields | `review/models.py` | `tools_given` / `tool_calls_made` on `ReviewResult` + `to_dict` |
| Templates | `data/templates/*.yaml` (7 files) | Claude names → canonical names |
| Dispatch telemetry | `pipeline/actions/dispatch.py` | Capture metadata; remove the slice-265 TODO at line 205 |
| Review action | `pipeline/actions/review.py` | `allowed_tools` passthrough + metadata |
| Summary action | `pipeline/actions/summary.py` | `allowed_tools` passthrough + metadata |
| Schema | `pipeline/schema.py` | `allowed_tools` valid on review/summary steps |
| `-v` line | `pipeline/executor.py` | `tools=given/made` extra |

Dependency note: 263 supplies the dispatch `allowed_tools` path this instruments; 264's
`cf_*` tools register through the same registry and inherit the observability with no work.

## Implementation Details

### `list_files`

Parameters: `path` (string, optional, default `"."` — relative to jail root), `pattern`
(string, optional glob, e.g. `"*.py"`), `recursive` (boolean, optional, default `false`).
Returns newline-joined paths relative to the jail root, directories marked with a trailing
`/`. Reuses `_resolve_in_jail`; a path escaping the jail returns `is_error=True` via the
existing `_jail_violation`. Output is capped by the same truncation limit the other file tools
use, with the same visible truncation marker — an unbounded listing of a large tree would
blow the model's context.

### `grep`

Parameters: `pattern` (string, required, treated as a regex), `path` (string, optional,
default `"."`), `glob` (string, optional file filter), `max_results` (integer, optional).
Returns `path:line:text` per match, via a directory walk rather than shelling out to
`rg`/`grep`: the review path must not depend on a binary that may be absent, and staying
in-process keeps the jail check in one place. Runs under `asyncio.to_thread`. An invalid regex
is a returned `is_error=True` result, not a raise — the model must be able to correct itself.

**Matching is bounded against catastrophic backtracking (D9).** The `pattern` is
model-supplied and runs against arbitrary file content, so a pathological-but-valid pattern is
a realistic hang. The matcher is the `regex` package with its `timeout=` argument, not stdlib
`re`; the bound is `GREP_TIMEOUT_S` in `tools/limits.py`, alongside the existing
`BASH_TIMEOUT_S`. On expiry the tool logs at WARNING (naming the pattern) and returns
`is_error=True` telling the model its pattern was too expensive, mirroring `bash`'s timeout
path ([builtin.py:305-318](src/squadron/tools/builtin.py#L305-L318)). The budget covers the
whole walk, not each file, so a cheap pattern over a huge tree is bounded too. `regex` is a new
runtime dependency.

Both tools follow the established `builtin.py` shape exactly: module-level `NAME` constant,
`_*_factory(cwd)` closure, frozen `ToolDescriptor`, `register(...)` at import.

### Non-SDK unknown-name policy

The current drop-with-warning is replaced with a raised `ProviderError` naming the offending
tool and listing registered names. This is what makes the vocabulary migration safe: had it
been a raise before, front 1 would have been a loud failure instead of a silent one.

### Review client signature

`run_review_with_profile` computes effective tools internally from `template.allowed_tools`
and the resolved provider — no new required parameter, so the existing callers (the pipeline
review action, the `sq review` CLI path) keep working unchanged.

## Success Criteria

**SC1 — Read-only search tools exist.** `list_files` and `grep` are registered; both enforce
the CWD jail (escape attempts return `is_error=True`); both return usable content on the happy
path; both cap their output.

**SC1a — `grep` is bounded and says so.** An invalid regex returns `is_error=True` with a
message the model can act on. A pathological-but-valid pattern (e.g. `(a|a)*$` against a
non-matching run of `a`s) terminates within `GREP_TIMEOUT_S` rather than hanging, logs at
WARNING, and returns `is_error=True`. Both are asserted by test, with the timeout test
monkeypatching `limits.GREP_TIMEOUT_S` down so the suite stays fast.

**SC2 — Templates speak canonical vocabulary.** All seven shipped templates declare squadron
names. No `Read`/`Glob`/`Grep`/`Bash` string remains in `data/templates/*.yaml`.

**SC3 — SDK behavior is unchanged.** An SDK-profile review built from a migrated template
produces the same `ClaudeAgentOptions.allowed_tools` value it produced before the migration
(`["Read", "Glob", "Grep"]` for the templates that declared those three). Asserted directly on
the built config, not inferred. `code.yaml` is the one intended difference: `Bash` is absent
post-migration (D6), which changes the emitted `--allowedTools` string but not the SDK
reviewer's actual capabilities, since `tools`/`--tools` is unset and `permission_mode` is
`bypassPermissions`.

**SC4 — Unknown names fail loudly, both directions.** A canonical name with no SDK mapping
raises at the SDK config edge; a name not in the registry raises in the non-SDK agent. Neither
degrades to a tool-less run.

**SC5 — Tool-enabled reviews skip body injection, keep the diff.** With a tool-capable
provider and a template allowing a reader, the built prompt contains the diff and does **not**
contain injected file bodies. With no allowed tools, the prompt is byte-identical to today's.

**SC6 — Reviews actually call tools.** A review against a mocked OpenAI-compatible endpoint
that returns a `read_file` tool call reads the referenced file mid-review, and the parsed
`ReviewResult` is unchanged in shape (verdict + findings parse as before).

**SC7 — Pipeline review and summary steps accept `allowed_tools`.** Schema validates the field
on both step types against the registry (unknown name → `ValidationError` at load); both
actions thread it into the agent config.

**SC8 — Tool use is visible at `-v`.** For dispatch, review, and summary steps:
`sq run <pipeline> <slice> -v` prints tools-given and tool-calls-made on the step's result
line. A step offered tools that made zero calls is visually distinct from a step offered no
tools. **This is the primary acceptance criterion — a green suite does not satisfy it.**

**SC9 — Telemetry persists.** `tools_given` and `tool_calls_made` appear in
`RunState.action_results` for pipeline steps and in the persisted review JSON for reviews,
without a state `schema_version` bump.

**SC10 — Issue #68 closes on evidence.** A live (non-mocked) non-SDK review demonstrably calls
at least one tool, shown by the `-v` line and the persisted count.

## Design Decisions

**D1 — Injection decision is computed per-run in the review client; `ProviderCapabilities`
gains no field.** The arch offered two alternatives, both rejected. Adding `supports_tool_use`
to `ProviderCapabilities` is wrong because the OpenAI-compatible provider *always* supports
tool use — the flag would be constant `True` and would not answer the question the injection
branch is actually asking, which is whether *this run* has readers. Making `can_read_files`
config-dependent is worse: it overloads a field whose current meaning ("reads files unaided")
is correct and is read elsewhere, and it would make a provider capability vary per template.
The real input is the effective tool set, which is already in hand at the decision point.

**D2 — Canonical → Claude translation lives at the SDK config-build edge, not in the SDK
agent.** [provider.py:56-57](src/squadron/providers/sdk/provider.py#L56-L57) is the only place
`allowed_tools` crosses into `ClaudeAgentOptions`. Translating there keeps the SDK agent
untouched and satisfies the arch's "SDK agent internals unchanged."

**D3 — Unknown tool names raise instead of warning.** Directly against the current
warn-and-drop. A silent drop is what made front 1 invisible: templates have been declaring
tools that never materialized. Fail-fast at the boundary, per the project's Fail Fast rule.

**D4 — Telemetry rides on the final `Message.metadata`.** Chosen over an agent-level accessor
property (would push state onto the `Agent` protocol that all three providers implement, and
force callers to hold the concrete type) and over mid-stream system Messages (reverses 262's
"intermediate turns are not surfaced" contract, and callers concatenate `.content`, so tool
chatter would contaminate response bodies). Metadata on the final message is additive,
ignorable, and works identically for the standalone review client and the pipeline actions.

**D5 — `tools_given` is present with `tool_calls_made: 0` when tools were offered and unused.**
Emitting nothing in that case would collapse it with "no tools offered" — the exact
distinction SC8 requires.

**D6 — `code.yaml` drops `Bash`; this does not restrict the SDK reviewer.** Reviews are a
read-only tool subset per the arch, so `bash` is not carried into the canonical declaration.
The important part is what this does and does not do, because `allowed_tools` means two
different things on the two paths:

- **Non-SDK: a capability gate.** The name in the list is what materializes an executor from
  the registry. Omitting `bash` is precisely what keeps a non-SDK review read-only. This is
  the reason for the decision.
- **SDK: a permission hint, and here an inert one.** `AgentConfig.allowed_tools` becomes
  `ClaudeAgentOptions.allowed_tools` → `--allowedTools`
  ([subprocess_cli.py:195-196](.venv/lib/python3.13/site-packages/claude_agent_sdk/_internal/transport/subprocess_cli.py#L195-L196)),
  which pre-approves tools that would otherwise prompt. Tool *availability* is governed by the
  separate `tools` / `--tools` field, which squadron never sets — so the SDK reviewer receives
  the CLI's default tool set either way. `code.yaml` additionally sets
  `permission_mode: bypassPermissions` ([code.yaml:54](src/squadron/data/templates/code.yaml#L54)),
  which approves everything regardless. Dropping `Bash` there removes a redundant
  pre-approval, under a mode that bypasses approval, for a tool that remains available.

**Net effect on an SDK code review: none.** It could run Bash before this slice and can after.
The read-only subset is real on the non-SDK path and nominal on the SDK path; closing that gap
(via `tools`/`--tools` or `disallowed_tools`) is deliberately out of scope here — it would
change SDK reviewer behavior, which this slice must not do. Tracked as issue #69.

**D7 — `grep` is implemented in Python, not by shelling to `rg`.** No dependency on an
external binary, and the jail check stays in one place rather than being re-expressed as
argument sanitation for a subprocess.

**D8 — No `RunState.schema_version` bump.** `action_results` is untyped
`list[dict[str, object]]`; adding keys is backward-compatible in both directions.

**D9 — `grep` uses the `regex` package for a real timeout; `asyncio.wait_for` around
`to_thread` does not work here.** Raised as F001 in the Phase 4 slice review, whose suggested
fix was a per-call `asyncio.wait_for`. Measured, that does not bound anything: a thread running
C-level `re` code cannot be cancelled, so `wait_for` does not observe its deadline until the
regex finishes on its own. With a 1.0s timeout on `(a+)+$` against `"a"*30 + "b"`, `wait_for`
returned after **72.8s** — it reports the hang after it ends rather than preventing it, and the
worker thread stays burnt either way.

A line-length cap is no better: backtracking is exponential in input length, and the same
pattern needs only 30 characters to reach 73s (20 chars: 0.08s; 24: 1.4s; 26: 4.9s; 28: 20.7s).
No cap that leaves `grep` useful is low enough to bound it.

That leaves running the match where it can actually be stopped. The `regex` package accepts a
`timeout=` and raises `TimeoutError` from inside the matching engine — verified bounding
`(a|a)*$` at 1.02s, the case its optimizer cannot fold away. Subprocess isolation (mirroring
`bash`'s killable process group) would also work but costs a process spawn per call on the
review hot path for no added safety.

Cost: one new runtime dependency (`regex`, a mature C-extension). Accepted over shipping a
tool with an unbounded hang on model-supplied input.


## Risks

- **The vocabulary migration silently changes SDK review behavior.** This is the one change
  that touches a working path. Mitigated by SC3 asserting the built SDK config directly. Note
  that D6 (dropping `Bash` from `code.yaml`) is *not* such a change — it alters the emitted
  `--allowedTools` string without altering SDK reviewer capability; see D6.
- **`regex` is a new runtime dependency.** Justified in D9 — stdlib `re` cannot be bounded
  from outside. It is a mature, widely-used C extension, and the dependency is confined to the
  `grep` tool.
- **A tool-enabled reviewer under-reads.** Skipping body injection is only an improvement if
  the model actually uses its tools; a lazy model reviews from the diff alone. SC10's live run
  is the check, and the `-v` counts make a zero-call review immediately obvious rather than
  silently shallower.

## Verification Walkthrough

Recorded at Phase 6 completion. Every command below was run from the repository root on the
implementation branch; the stated output is what it actually produced. Steps 1-5 and 8-9 are
automated and reproducible by any agent (human or AI); steps 6-7 require a plain terminal and
a live model, and are marked accordingly.

### 1. Search tools honor the jail

```bash
cd /Users/manta/source/repos/manta/squadron
uv run pytest tests/tools/test_list_files.py tests/tools/test_grep.py -q
```

Observed: `24 passed in 0.57s`.

Covers: escape attempts return errors, happy paths return content, output is capped with a
visible marker, an invalid regex returns `is_error=True` rather than raising, and a
pathological pattern trips the timeout with a WARNING instead of hanging.

**Correction from the draft:** the draft named `tests/tools/test_builtin.py`, which does not
exist. Tool tests are one file per tool (`test_read_file.py`, `test_write_file.py`,
`test_bash.py`, `test_jail.py`); the new tools follow that convention with
`test_list_files.py` and `test_grep.py`.

The whole-walk timeout budget also has a load test at the real (non-monkeypatched)
`GREP_TIMEOUT_S`:

```bash
uv run pytest tests/load/test_grep_timeout.py -q
```

Observed: `3 passed in 8.18s`. The runtime is dominated by two deliberate 5s budget
exhaustions running concurrently — that is the bound being measured, not slowness.

### 2. No Claude vocabulary remains in templates

```bash
grep -rn "allowed_tools" src/squadron/data/templates/
```

Observed: all seven files print `allowed_tools: [read_file, list_files, grep]`. No `Read`,
`Glob`, `Grep`, or `Bash` on any `allowed_tools` line.

### 3. SDK path is unchanged

```bash
uv run pytest tests/providers/sdk tests/review/test_template_sdk_regression.py -q
```

Observed: `85 passed in 0.40s`.

`tests/review/test_template_sdk_regression.py` loads each shipped template, builds its
`ClaudeAgentOptions` through the real SDK provider, and asserts the result equals the
pre-migration Claude-name list `["Read", "Glob", "Grep"]`. `code.yaml` is the one intended
difference: `Bash` is absent (design D6 — this changes the emitted `--allowedTools` string,
not the SDK reviewer's actual capability; tracked as issue #69).

### 4. Unknown names fail loudly

```bash
uv run pytest tests/providers/openai tests/providers/sdk -k "unknown or unmapped" -q
```

Observed: `11 passed, 150 deselected in 0.23s`.

Covers both directions: the non-SDK agent raises `ProviderError` naming every unknown tool
and listing the registered ones, and the SDK translation edge raises for an unmapped
canonical name.

**Correction from the draft:** the draft's `-k "unknown_tool"` selector matched nothing after
implementation, because the tests are named for the policy (`unknown_tool_name_raises...`,
`unmapped_canonical_name_raises...`) rather than a bare `unknown_tool` token. The selector
above matches both families.

### 5. Injection skip

```bash
uv run pytest tests/review/test_injection_decision.py -q
```

Observed: `15 passed in 0.29s`.

Covers: a tool-capable run's prompt contains the diff and no file bodies; a no-tools run's
prompt is byte-identical to the pre-slice construction; and an unmigrated template declaring
Claude vocabulary against a non-SDK provider still injects exactly as before.

**Correction from the draft:** the draft named `tests/review/test_review_client.py -k
"inject"`. Injection-decision tests live in the new `test_injection_decision.py`;
`test_review_client.py -k inject` still passes but exercises a different concern.

### 6. The observability demo — primary acceptance (manual, plain terminal)

**Run from a plain terminal, not inside Claude Code.** `sq run` refuses to execute in a Claude
Code session (unconditional `CLAUDECODE` guard,
[run.py:148](src/squadron/cli/commands/run.py#L148)). This step was **not** executed during
Phase 6 implementation for that reason; its automated equivalent is step 8 below.

```bash
cd /Users/manta/source/repos/manta/squadron
sq run <pipeline> <slice> -v
```

Expect on the step result lines: a dispatch/review/summary step given tools prints
`tools=N/M calls`; a step given tools that called none prints `tools=N/0 calls`; a step given
no tools prints neither segment. Construct the zero case deliberately if no natural step
produces it.

Then confirm persistence:

```bash
python -c "import json,sys; d=json.load(open(sys.argv[1])); [print(s['step_name'], [a.get('metadata') for a in s['action_results']]) for s in d['completed_steps']]" \
  ~/.config/squadron/runs/<run>.json
```

Expect `tools_given` and `tool_calls_made` in the metadata of tool-bearing steps.

**Correction from the draft:** the draft's one-liner read `d['action_results']` at the top
level. `RunState` has no such key — action results live per step under
`completed_steps[].action_results[].metadata`. The command above reflects the real shape.

### 7. Live review calls a tool — issue #68 (manual, live model)

```bash
sq review code --slice <n> --model kimi27 -v
```

Expect a non-zero tool-call count in the `-v` output and `tools_given` / `tool_calls_made` in
the persisted review JSON. Not executed during Phase 6 implementation — it requires a live
non-SDK model. Its automated equivalent is step 9 below, which drives the same code path end
to end against a mocked endpoint and asserts the tool actually ran.

### 8. Telemetry observability and persistence — automated (SC8, SC9)

```bash
uv run pytest tests/pipeline/test_tool_telemetry_observability.py -q
```

Observed: `5 passed in 0.23s`.

Covers SC8's distinguishing case directly — `tools=3/0 calls` renders for an offered-but-
unused step while a no-tools step renders no `tools=` segment at all — and SC9's persistence
claim by running a one-step pipeline through the executor with the same
`StateManager.make_step_callback` seam `sq run` uses, then reading `tools_given` /
`tool_calls_made` back out of the run JSON on disk.

### 9. Non-SDK review executes a tool call — automated (SC6)

```bash
uv run pytest tests/review/test_non_sdk_tool_call_integration.py -q
```

Observed: `2 passed in 0.45s`.

Drives `run_review_with_profile` against the migrated `code` template with a non-SDK profile
and a mocked OpenAI-compatible endpoint that calls `read_file` on turn one and returns a
parseable verdict on turn two. Asserts the tool really ran (the real file's body appears in
the second request's tool-result history entry), the parsed `ReviewResult` is unchanged in
shape from a tool-less review, and `tool_calls_made == 1`. This is the automated closure
evidence for issue #68.

### 10. Full gate set

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest -q
```

Observed: `480 files left unchanged`; `All checks passed!`; `0 errors, 0 warnings, 0
informations`; `3292 passed, 2 skipped, 7 warnings in 451.08s`.

`tests/load/` is picked up automatically — `pyproject.toml` sets `testpaths = ["tests"]` and
`.github/workflows/ci.yml` runs plain `uv run pytest` with no path or marker filter, so no
separate load-test invocation or CI wiring was needed.

## Effort

3/5 — small pieces, but spread across four subsystems (tools, providers×2, review, pipeline
actions), and one of them (the template vocabulary migration) modifies a working SDK path
whose behavior must be preserved exactly.
