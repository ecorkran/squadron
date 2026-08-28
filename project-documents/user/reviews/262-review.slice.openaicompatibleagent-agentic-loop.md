---
docType: review
layer: project
reviewType: slice
slice: openaicompatibleagent-agentic-loop
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260827
dateUpdated: 20260827
reviewedSha: f576aaf041eeba15a799789b0e4623e55cde09ed
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Loop-level protocol failures are not logged at WARNING+"
    location: "project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md:234-288"
  - id: F002
    severity: concern
    category: error-handling
    summary: "cwd trust-boundary fallback logged at INFO, not WARNING, and defaults rather than failing fast"
    location: "project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md:150-155"
  - id: F003
    severity: pass
    category: alignment
    summary: "Scope, dependency direction, and out-of-scope boundaries match architecture"
    location: "project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md#Technical-Scope"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Bash-hang / tool-execution failure mode already closed at the correct layer"
    location: "project-documents/user/slices/262-slice.openaicompatibleagent-agentic-loop.md:238-247"
---

# Review: slice — slice 262

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Loop-level protocol failures are not logged at WARNING+

The error-surfacing table (lines 234-251) defines two failure modes that originate in the agentic-loop code itself (new in this slice, not delegated to a slice-261 tool): malformed JSON in `arguments`, and a tool name from the model not present in `self._tool_executors`. The logging contract table (lines 276-288) assigns WARNING+ only to "dropped unknown tool names" (D1, construction-time), budget-guard-fired, and max-iterations-reached; the two runtime protocol-error paths fall under "each tool call... and each result (truncated)" at DEBUG only. `.claude/rules/review-code.md`'s Failure-Mode Enumeration principle requires every identified failure mode to be observable "at WARNING+ or metric increment... not silent" — DEBUG does not satisfy that bar. By contrast, the slice-261 tool implementations already log path-escape rejections and bash timeouts at WARNING (`builtin.py`), so this is a real asymmetry: the newly-written loop code is quieter than the tool layer it calls. Success Criteria (lines 351-354) also assert only that these paths "produce an error tool result," not that they emit an observable log signal, so a test suite satisfying the stated criteria would not catch a regression that silently swallowed a model protocol violation.

### [CONCERN] cwd trust-boundary fallback logged at INFO, not WARNING, and defaults rather than failing fast

Architecture explicitly names `cwd` "the trust boundary" for file/bash tool execution (arch §Architectural Principles, "CWD as the trust boundary"). The slice's decision — when `allowed_tools` is non-empty and `cwd` is `None`, silently substitute `Path.cwd()` (the ambient process working directory) rather than raising — is defended as "explicit, observable... not silent" because it logs at INFO. Per project guidelines ("Never use silent fallback values. Fail explicitly with errors or obviously-placeholder values"), an implicit default for a security-relevant sandbox root is exactly the pattern that rule targets; INFO-level logging is also inconsistent with the WARNING level used elsewhere in this same document for other guardrail/default-triggering events (D1 dropped names, budget guard, max-iterations). The doc's own "unreachable in practice today" argument (verified: `dispatch.py:63` hardcodes `cwd=None` and never populates `allowed_tools` until 263) mitigates current risk, but the fallback becomes reachable the moment any future caller (a test harness, a new integration, or an early partial rollout of 263) sets `allowed_tools` without `cwd` — at which point a write/bash operation would silently execute against whatever directory the process happens to be running from, with only an INFO log to notice it. Raising an explicit `ConfigurationError` (or at minimum logging at WARNING) at that call site would better match both the architecture's trust-boundary framing and the project's fail-fast/no-silent-fallback rule.

### [PASS] Scope, dependency direction, and out-of-scope boundaries match architecture

In-scope/out-of-scope lists correctly confine this slice to the agent-side loop (schema construction, `_stream_turn`/`_call_api` split, history accumulation, termination conditions, error surfacing, D1 tolerance), explicitly excluding pipeline YAML (263), review injection-skip and vocabulary migration (265), `tool_use`/`--no-tools` (266), MCP bridging (264), and any SDK/Codex change — all consistent with the architecture's Anticipated Slices breakdown and the slice-plan entry for (262). `dependencies: [261]` and `interfaces: [263, 264, 265, 266]` in the frontmatter correctly reflect the dependency direction (261 → 262 → {263,264,265,266}) stated in the architecture's slice-ordering note.

### [PASS] Bash-hang / tool-execution failure mode already closed at the correct layer

The loop's "executor raises" / "executor returns is_error=True passed through verbatim" handling correctly delegates timeout/hang concerns to the tool layer rather than duplicating them in the loop — consistent with the architecture's "tools own their failure messages" principle. Verified against the shipped slice-261 implementation (`src/squadron/tools/builtin.py`), which already enforces a bash timeout (`BASH_TIMEOUT_S`, `asyncio.wait_for`) and logs at WARNING on timeout/path-escape and via `logger.exception` on unexpected failure, so this slice does not need to re-specify hang handling for bash.
