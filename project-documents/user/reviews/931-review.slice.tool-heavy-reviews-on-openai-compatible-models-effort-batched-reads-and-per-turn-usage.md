---
docType: review
layer: project
reviewType: slice
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260930
dateUpdated: 20260930
reviewedSha: 8920f79b40247fff4fd908bbd418b7c6612a98c1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
effort: low
turns: 2
promptTokens: 21029
cachedTokens: 0
completionTokens: 892
reasoningTokens: 158
durationSeconds: 28.8
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with explicit handling and tests"
    location: "931-slice.tool-heavy-reviews...md#D12 — Failure modes and their signals"
  - id: F002
    severity: pass
    category: scope-alignment
    summary: "Scope mapping to the architecture is argued part-by-part, and exclusions are explicit"
    location: "931-slice.tool-heavy-reviews...md#Initiative fit"
  - id: F003
    severity: pass
    category: dependency-direction
    summary: "Dependency directions are verified and constrained"
    location: "931-slice.tool-heavy-reviews...md#Dependency direction"
  - id: F004
    severity: pass
    category: nfr
    summary: "NFR handling is stated explicitly"
    location: "931-slice.tool-heavy-reviews...md#Special Considerations"
  - id: F005
    severity: note
    category: scope-alignment
    summary: "Three-part bundle tensions the \"small and focused\" guideline but is justified and de-risked"
    location: "931-slice.tool-heavy-reviews...md#Why one slice"
  - id: F006
    severity: note
    category: risk
    summary: "Gemini `stream_options` uncertainty is contained rather than left open"
    location: "931-slice.tool-heavy-reviews...md#Risk Assessment"
---

# Review: slice — slice 931

**Verdict:** PASS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Failure modes are enumerated with explicit handling and tests

The D12 table covers each new I/O path (request failure at stream start, mid-body disconnect, stall, missing usage chunk, non-ProviderError exceptions, hung reads, malformed usage, 400 rejections, batch budget) with a concrete behavior, a signal, and a named test — no TBDs. The hung-read case is explicitly argued as unchanged behavior rather than hidden.

### [PASS] Scope mapping to the architecture is argued part-by-part, and exclusions are explicit

Each of the three parts maps to a "Work that belongs here" line (operational config, tech debt/performance, operational logging + bug fixes), with an honest acknowledgment that A's mapping is weakest and both halves stated. Excluded work (new commands, workflows, `--effort` flag) is listed in "Out of scope", correctly matching the architecture's "does not belong here" clause.

### [PASS] Dependency directions are verified and constrained

The new `review/` → `core.usage` and `providers/*` → `core.usage` edges are argued to be acyclic (`core/usage.py` is a stdlib-only leaf), the existing `review/` → provider-layer import rule is preserved, and two greps in the Technical Requirements enforce it. The `parent` frontmatter correctly points at the slice plan, not the architecture.

### [PASS] NFR handling is stated explicitly

The document states there are no initiative-level NFRs to restate (consistent with the architecture doc, which declares none) and identifies the one per-slice constraint (event-loop non-blocking, <1 ms per-chunk work, single `asyncio.to_thread` hop for batched reads) with a specific target.

### [NOTE] Three-part bundle tensions the "small and focused" guideline but is justified and de-risked

The architecture prefers many small slices; this bundles three. The slice documents the PM decision, argues shared-work justification (all three touch `_stream_turn`/`_run_agentic_loop` and `ReviewResult` rendering), keeps parts independently revertible (C → B → A), and identifies B as cuttable. Acceptable as is; no action needed beyond the recorded rationale.

### [NOTE] Gemini `stream_options` uncertainty is contained rather than left open

The one unverified external fact is handled by shipping the gemini profile with `sends_stream_usage = False` (byte-identical requests today), tracked in #173 with a one-line enable path — no merge precondition, no TBD in a failure path.

### Run Digest

- Response length: 2995 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: stop
- Output budget: backend default
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 621
- Effort: low
- Turns: 2
- Tokens — prompt / cached / completion / reasoning: 21029 / 0 / 892 / 158
- Duration: 28.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

---

## Debug: Prompt & Response

### System Prompt

You are an architectural reviewer. Your task is to evaluate whether a design
document aligns with a parent architecture document and its stated goals.

Evaluation criteria:
- Alignment with stated architectural goals and principles
- Violations of architectural boundaries or layer responsibilities
- Scope creep beyond what the architecture defines
- Dependency directions are correct
- Integration points match what consuming/providing slices expect
- Common antipatterns: over-engineering, under-specification, hidden dependencies
- Failure modes enumerated for each new I/O path or message type (hang, timeout, peer disconnect mid-send) with explicit handling strategy, not "TBD" or implicit
- If the slice touches a path with an NFR stated in the parent architecture document, the NFR is restated in this slice doc with the specific target (latency, throughput, etc.)


Important context:
- The `parent` field in slice frontmatter refers to the slice plan document,
  not the architecture document. Do not flag this as an error.

CRITICAL: Your verdict and findings MUST be consistent.
- If verdict is CONCERNS or FAIL, include at least one finding with that severity.
- If no CONCERN or FAIL findings exist, verdict MUST be PASS.
- Every finding MUST use the exact format: ### [SEVERITY] Title
- Every finding MUST include a `location:` tag on its own line immediately
  after the title. This applies to PASS findings too.

Slice reviews evaluate the slice **design document** (and its parent
architecture/HLD) — not the implementation. Do not cite code paths.
Choose the `location:` value (most specific form you can verify) from
the documents under review:
1. `path:line` or `path:start-end` in the slice doc — preferred when
   you can pin the finding to a specific line or range.
2. `path#section-heading` — when the finding is at a named section but
   a precise line is awkward.
3. `path` — when the finding spans the whole document.
4. `unverified` — the explicit "I don't know" token. Use this when you
   cannot pin the finding to a slice-doc path you are certain of.
   **A hallucinated path is worse than `unverified`** because it looks
   authoritative; the parser will normalize missing/blank/`-`/`global`
   to `unverified` automatically.

Report your findings using severity levels:

Use exactly this structure; do not repeat this block in your response.

```markdown
## Summary
[overall assessment: PASS | CONCERNS | FAIL]

## Findings

### [PASS|CONCERN|FAIL] Finding title
location: <path:line | path:start-end | path#section-heading | path | unverified>
Description with specific references.
```


## Output Structure Requirements

For each finding, include a category tag on the line immediately after the heading:

### [CONCERN] Finding title
category: error-handling

You may also include a location tag:

### [CONCERN] Finding title
category: error-handling
location: src/module.py:45

Valid severity levels: PASS, NOTE, CONCERN, FAIL

Use NOTE for informational observations that don't require action.
Use CONCERN for issues that should be addressed but don't block progress.
Use FAIL for issues that must be fixed before proceeding.


### User Prompt

Review the following document for architectural alignment:

**Input document:**
<slice_document>
project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md
</slice_document>
**Architecture document:**
<architecture_document>
project-documents/user/architecture/900-arch.maintenance-and-refactoring.md
</architecture_document>

Read both documents, then evaluate the input against the architecture.
Follow referenced files as needed to understand dependencies and integration points.
Report your findings using the severity format described in your instructions.


## File Contents

### CLAUDE.md (project conventions)

```
<!-- BEGIN:context-forge -->
### Project Guidelines for Claude

#### Core Principles

- Always resist adding complexity. Ensure it is truly necessary.
- Never use silent fallback values. Fail explicitly with errors or obviously-placeholder values.
- Never use cheap hacks or well-known anti-patterns.
- Never include credentials, API keys, or secrets in source code or comments. Load from environment variables; ensure .env is in .gitignore. Raise an issue if violations are found.
- Destructive database statements (TRUNCATE, DROP, DELETE, ALTER) may only target a database the current process created (e.g. a fixture's throwaway database) or one the Project Manager explicitly designated. Tests never read the production database URL variable. Full rules: `sql.md` ("Production Database Protection") in the modular rules directory.
- When debugging a failure, get the actual error message before attempting any fix. Never apply more than one speculative fix without first obtaining concrete evidence (logs, error text, stack trace) that diagnoses the root cause. If you cannot get the evidence yourself, ask the Project Manager for it.

#### Code Structure

- Keep source files to ~300 lines, functions to ~50 lines (excluding whitespace) where practical.
- Program to interfaces (contracts).  Maintain clear separation between components.
- Do not duplicate logic.  Respect DRY (don't repeat yourself).
- Provide meaningful but concise comments in relevant places.

- Never scatter comparison values across code. If a value is used in conditionals, switch cases, or lookups, define it once (enum, constant, or config) and reference that definition everywhere. Changing a value should require editing exactly one place.
- Do not hard-code magic defaults.  In the example below, the defaults for model and n are both wrong.  If such defaults are needed they should be centralized at the config level.  This applies in all languages.
```python
  async def _model_start(promt:str) -> str {
    model = self._config.model or "gpt-5.3-codex"
    n = self._config.index or 1234
  }
```
- NEVER use user-accessible labels as logical structure.  They are fragile.

##### Exception Handling
- Every try/except must either: (a) re-raise after logging at ERROR level with logger.exception, (b) handle a specific exception with a comment explaining why swallowing is correct (e.g., ConnectionClosed: pass for normal teardown), or (c) be a top-level handler at a process boundary. Bare except: and except Exception: pass are bugs by definition.

#### Source Control and Builds
- Keep commits semantic; build after all changes.
- Git add and commit from project root at least once per task.
- Confirm your current working directory before file/shell commands.

#### Parsing & Pattern Matching
- Prefer lenient parsing over strict matching. A regex that silently fails on valid input (e.g. requiring exact whitespace counts or line-ending positions) is a bug. Parse the semantic content, not the formatting.
- When parsing structured text (YAML, key-value pairs, etc.), handle common format variations (compact vs multi-line, varying indent levels, trailing whitespace) rather than requiring one exact layout.
- When writing a parser, the test fixture must include the actual format that parser will consume in production.  A test that only passes on a format the real data never uses only provides false confidence.
- If a parser returns empty/default on bad input, add at least one test using real-world input (e.g. the actual file it will parse) to catch silent failures.
  
#### Hallucination traps in prompts
If an instruction tells a reader to retrieve a value from some source, and
that source might return empty, do not place a hardcoded example of an
acceptable value nearby. When the source is empty, a model will reach for
the nearest plausible token — and the example is it. This is a
hallucination trap.

##### Bad

    Print the filename (from stderr, e.g. `squadron-P4.md`).

##### Good

    Print the filename. The CLI emits it on a line prefixed with
    `Using: ` on stderr. If no such line is present, stop with an error.


#### Project Navigation
- Follow `guide.ai-project.process` and its links for workflow.
- Follow `file-naming-conventions` for all document naming and metadata.
- Project guides: `project-documents/ai-project-guide/project-guides/`
- Tool guides: `project-documents/ai-project-guide/tool-guides/`
- Modular rules for specific technologies may exist in 
  `project-documents/ai-project-guide/project-guides/rules/`.

#### Document Conventions

- All markdown files must include YAML frontmatter as specified in `file-naming-conventions.md`
- Use checklist format for all task files.  Each item and subitem should have a `[ ]` "checkbox".
- After completing a task or subtask, delegate checklist updates to the `task-checker` agent rather than editing task files inline. This keeps the main agent's context focused on implementation. If task-checker is unavailable, check off tasks directly.
- Preserve sections titled "## User-Provided Concept" exactly as 
  written — never modify or remove.
- Keep success summaries concise and minimal.

#### Git Rules

##### Branch Naming
A branch corresponds to one unit of work: slice implementation (Phase 6). Planning work (Phases 0–5: concept, initiative plan, architecture, slice plan, slice design, task breakdown, and reviews of those artifacts) does not get its own branch — it commits directly to the current integration target (see below).

- **Slice work** → `{index}-slice.{name}`, where `{index}` is the slice's index and `{name}` is the document name without the `.md` extension.

###### Integration branch
A project may configure an **optional** integration branch that work forks from and merges into, instead of `main`. Read it with `cf config get git.integration_branch`. This key is optional and defaults to empty:

- **Unset (default):** no change from plain historical behavior. Work branches fork from `main` and merge into `main`, named exactly `{index}-{type}.{name}` — no prefix.
- **Set** (e.g. `dev/erik`):
  - Work branches are named the same as when unset — `{index}-{type}.{name}` (e.g. `910-slice.foo`), with no prefix.
  - Work branches fork **from** `{integration_branch}`, not `main`.
  - Work branches merge **into** `{integration_branch}`, not `main`.
  - **Hard rule: never merge to `main` when `integration_branch` is set.** Syncing `{integration_branch}` from `main`, and eventually merging `{integration_branch}` into `main`, are PM-only actions outside automation scope — never perform either as part of normal slice/planning workflow, only if the Project Manager explicitly instructs it as a standalone action.

The integration branch affects **git topology only** (fork point and merge target) — not the branch name. It does not move documents or change where artifacts resolve — the `project-documents/user/...` layout under the branch is unchanged. The configured value is relative and contained (never absolute, never `..`, no trailing slash, no Windows drive/`\`); `cf` rejects invalid values when the key is set.

###### Worktrees
The target is a property of the config, never of the checkout. The branch you happen to be on is not evidence of the target — always read it (step 1 below), in the primary tree and in every git worktree.

`git.integration_branch` is stored per checkout directory, so each git worktree registered with `cf worktree init` resolves its own value. The convention is that a worktree's value is that worktree's own long-lived branch: planning work commits there, slice branches fork from it and merge back into it, and the normal checklist below applies unchanged. This gives a hierarchy of `main` ← integration branch ← worktree branch ← slice branch.

- **Agents merge exactly one level:** a slice branch into its target. Merging a worktree's branch into a wider integration branch or into `main`, and refreshing it from either, are PM-only actions, same as the hard rule above.
- **Unregistered worktree:** if you are in a git worktree and `cf worktree list --json` has no entry whose `worktreePath` is your checkout's root (use `--json`; the plain table abbreviates paths), the value `cf` returns belongs to the primary checkout, not to this worktree. STOP and ask the Project Manager.
- **Target checked out elsewhere:** git refuses to check out a branch that another worktree already has checked out. If that happens for the target, STOP and ask the Project Manager. Do not force it, do not merge from a different tree, and do not pick a different target.

Before starting work:
1. read `cf config get git.integration_branch`; call its value (or `main` if empty) the **target**

**If committing planning work (Phases 0–5):**
2. ensure you are on the target. Do not create or switch to a work branch. Commit directly.

**If starting slice implementation (Phase 6):**
2. determine the branch name per the rules above (no prefix, regardless of target)
3. verify you are on the target or the expected slice branch
4. if the expected slice branch does not exist, create it from the target: `git checkout -b {branch-name} {target}`
5. if the branch already exists, switch to it: `git checkout {branch-name}`
6. never start work from another unit's branch unless explicitly instructed
7. if in doubt, STOP and ask the Project Manager

When slice implementation is done, merge the slice branch into the target:
1. re-read the target (step 1 above) — do not infer it from the current branch or from memory
2. `git checkout {target}`, then `git merge {branch-name}`
3. if either command fails, STOP and ask the Project Manager

Do not hold a branch open across units. Do not delete branches unless specifically instructed to do so.

##### Branch Protection
GitHub has two independent mechanisms: classic branch protection and rulesets. A 404 from `repos/{owner}/{repo}/branches/{branch}/protection` means only that no *classic* rule exists.
- Before stating that a branch is or is not protected, also check `gh api repos/{owner}/{repo}/rules/branches/{branch}` — it lists every active rule on the branch, including ones inherited from organization rulesets.
- Report "unprotected" only when both come back empty. If either call fails for a reason other than "not found" (permissions, auth), say so instead of concluding anything.

##### Commit Messages
Use semantic commit prefixes. The goal is a readable `git log --oneline`.

Format: `{type}: {short imperative summary}`

Types:
- `feat` — New functionality or capability
- `fix` — Bug fix
- `refactor` — Code restructuring without behavior change
- `test` — Adding or updating tests
- `style` — Formatting, whitespace, linting (no logic change)
- `guides` - Update or addition to project guides (system/project level)
- `docs` — Update or addition to user/ guides or documentation (slices, readme, etc)
- `review` — Code review, design review, or audit documentation
- `package` - Updates related to packaging, npm, package.json, PyPi, etc
- `chore` — Build config, dependencies, tooling, CI

Actions (optional, use if applicable):
- `update`: primarily update/edit to existing information
- `add`: primarily addition of new code or information
- `extract`: primarily used in refactoring
- `reduce`: if primary work involves reduction or streamlining

##### Guidelines:
- Summary is imperative mood ("add X" not "added X" or "adds X")
- Keep to ~72 characters
- No period at end
- Scope is optional but useful in monorepos: `feat(core): add template variable resolution`

##### Examples:
feat: add context_build MCP tool
fix: update to handle missing template directory gracefully
refactor(core): extract service instantiation into shared helper
docs: add MCP server installation instructions to README
test: add unit tests for prompt_list tool handler
chore: update @modelcontextprotocol/server to v2.1

<!-- END:context-forge -->

```

### Rules Injected

None

### Raw Response

## Summary
PASS

## Findings

### [PASS] Failure modes are enumerated with explicit handling and tests
category: error-handling
location: 931-slice.tool-heavy-reviews...md#D12 — Failure modes and their signals
The D12 table covers each new I/O path (request failure at stream start, mid-body disconnect, stall, missing usage chunk, non-ProviderError exceptions, hung reads, malformed usage, 400 rejections, batch budget) with a concrete behavior, a signal, and a named test — no TBDs. The hung-read case is explicitly argued as unchanged behavior rather than hidden.

### [PASS] Scope mapping to the architecture is argued part-by-part, and exclusions are explicit
category: scope-alignment
location: 931-slice.tool-heavy-reviews...md#Initiative fit
Each of the three parts maps to a "Work that belongs here" line (operational config, tech debt/performance, operational logging + bug fixes), with an honest acknowledgment that A's mapping is weakest and both halves stated. Excluded work (new commands, workflows, `--effort` flag) is listed in "Out of scope", correctly matching the architecture's "does not belong here" clause.

### [PASS] Dependency directions are verified and constrained
category: dependency-direction
location: 931-slice.tool-heavy-reviews...md#Dependency direction
The new `review/` → `core.usage` and `providers/*` → `core.usage` edges are argued to be acyclic (`core/usage.py` is a stdlib-only leaf), the existing `review/` → provider-layer import rule is preserved, and two greps in the Technical Requirements enforce it. The `parent` frontmatter correctly points at the slice plan, not the architecture.

### [PASS] NFR handling is stated explicitly
category: nfr
location: 931-slice.tool-heavy-reviews...md#Special Considerations
The document states there are no initiative-level NFRs to restate (consistent with the architecture doc, which declares none) and identifies the one per-slice constraint (event-loop non-blocking, <1 ms per-chunk work, single `asyncio.to_thread` hop for batched reads) with a specific target.

### [NOTE] Three-part bundle tensions the "small and focused" guideline but is justified and de-risked
category: scope-alignment
location: 931-slice.tool-heavy-reviews...md#Why one slice
The architecture prefers many small slices; this bundles three. The slice documents the PM decision, argues shared-work justification (all three touch `_stream_turn`/`_run_agentic_loop` and `ReviewResult` rendering), keeps parts independently revertible (C → B → A), and identifies B as cuttable. Acceptable as is; no action needed beyond the recorded rationale.

### [NOTE] Gemini `stream_options` uncertainty is contained rather than left open
category: risk
location: 931-slice.tool-heavy-reviews...md#Risk Assessment
The one unverified external fact is handled by shipping the gemini profile with `sends_stream_usage = False` (byte-identical requests today), tracked in #173 with a one-line enable path — no merge precondition, no TBD in a failure path.
