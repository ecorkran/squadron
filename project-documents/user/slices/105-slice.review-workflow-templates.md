---
docType: slice-design
slice: review-workflow-templates
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [foundation, sdk-agent-provider, cli-foundation]
interfaces: [end-to-end-testing, automated-dev-pipeline]
status: completed
dateCreated: 20260221
dateUpdated: 20260222
---

# Slice Design: Review Workflow Templates

## Overview

Implement predefined review workflow templates and a CLI `review` command that executes them. Each template defines a complete agent configuration — system prompt, allowed tools, permission mode, and prompt construction — for a specific review type. The `review` command creates a `ClaudeSDKClient` session, executes the review, returns structured results, and displays formatted output.

Three initial review types:
- **Architectural review** — evaluate a slice design or plan against an architecture document and stated goals
- **Task plan review** — check a task breakdown against its parent slice design for completeness and feasibility
- **Code review** — review code files against language-specific rules, testing standards, and project conventions

## Value

Direct developer value. Reviews are the highest-frequency interaction with the orchestration system during active development (1-4 per hour during design/implementation cycles). After this slice:

- `orchestration review arch path/to/slice.md --against path/to/arch.md` immediately evaluates whether a slice design aligns with the architecture, flags antipatterns, and identifies gaps — without the developer composing a custom prompt each time.
- `orchestration review tasks path/to/tasks.md --against path/to/slice.md` verifies that a task breakdown covers all success criteria from the slice design.
- `orchestration review code --cwd ./project` runs a code review against CLAUDE.md project conventions and language-specific rules.

Each review that catches a problem before implementation saves significant rework time. These templates encode review expertise that would otherwise be ad-hoc prompt construction.

Pipeline integration value. The review system returns structured `ReviewResult` objects that pipeline executors (such as the Automated Development Pipeline, initiative 160) consume programmatically. Review verdicts drive automated phase transitions: proceed, escalate to a stronger model, or pause for human checkpoint. This composability is designed in from day one — reviews are not terminal operations.

## Technical Scope

### Included

- `ReviewTemplate` dataclass as the runtime representation of a template
- `ReviewResult` and `ReviewFinding` dataclasses for structured review output
- YAML-based template definitions for all built-in templates (`arch`, `tasks`, `code`)
- YAML template loader and template registry
- CLI `review` subcommand with per-template argument handling
- `--output` flag: `terminal` (default), `json`, `file PATH`
- `ClaudeSDKClient` session per review — reviews bypass the agent registry (ephemeral, no persistent agent) but use the full client for future capability access (hooks, interrupts, custom tools)
- Prompt construction from template + user-supplied inputs
- Result parsing: agent text output → structured `ReviewResult`
- `orchestration review list` to show available templates
- Unit tests for template loading, prompt assembly, result parsing, CLI argument parsing, and runner integration

### Excluded

- Hook callbacks for v1 — `ClaudeSDKClient` supports hooks natively, so the `ReviewTemplate` schema includes an optional `hooks` field from day one. No hook callbacks are wired in the initial templates, but adding them later requires zero architectural change (see Tracked Enhancements).
- Custom user-defined templates — built-in templates only for v1. User templates go in `.orchestration/templates/` or a configured directory using the same YAML format. The loader already supports this; the discovery path just needs to be wired.
- Multi-agent reviews (e.g., two reviewers with different perspectives) — requires message bus (M2).
- Interactive review mode (follow-up questions after initial review) — the `ClaudeSDKClient` infrastructure supports this, but the CLI command exits after one exchange for v1. See Tracked Enhancements.

## Dependencies

### Prerequisites

- **Foundation** (complete): `Settings`, logging, error hierarchy
- **SDK Agent Provider** (complete): Validates that the SDK integration works. Note: reviews use `ClaudeSDKClient` directly from `claude-agent-sdk` — they do not go through `SDKAgentProvider` or the agent registry, since reviews are ephemeral single-exchange tasks, not persistent named agents.
- **CLI Foundation** (complete): Typer app entry point for adding the `review` subcommand.

### External Packages

- **claude-agent-sdk** (already in pyproject.toml): `ClaudeSDKClient`, `ClaudeAgentOptions`
- **typer** (already in pyproject.toml): CLI subcommand
- **rich** (transitive via typer): Formatted review output
- **pyyaml** (add to pyproject.toml): Template loading from YAML files

## Technical Decisions

### Why `ClaudeSDKClient` (Not `query()`)

The SDK provides two invocation modes. `query()` is a convenience wrapper that creates a new session per call — simpler but limited. `ClaudeSDKClient` provides explicit lifecycle control with the full feature surface: hooks, custom tools, interrupts, and session continuity.

The complexity difference is minimal — two extra lines with the context manager:

```python
# query() — fire and forget
async for message in query(prompt=prompt, options=options):
    handle(message)

# ClaudeSDKClient — context manager handles connect/disconnect
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt)
    async for message in client.receive_response():
        handle(message)
```

The capability difference is large. Everything the orchestration system will need in the near term — hook-based audit trails, interruptible agents, custom MCP tools for orchestration integration, session caching — requires `ClaudeSDKClient`. Standardizing now avoids a future migration from `query()` to `ClaudeSDKClient` across the review runner, the SDK agent provider, and any other SDK touchpoint.

For reviews specifically: each review creates a fresh `ClaudeSDKClient` instance, uses it for one exchange, and the context manager tears it down. This provides the same session isolation as `query()` while leaving the hooks and custom tools options available from day one.

### Why Direct SDK (Not Agent Registry)

The existing CLI flow for persistent agents is: `spawn` → `task` → `shutdown`. Reviews don't fit this lifecycle. A review is: configure → execute → return result → done. No agent persists between reviews.

Using `ClaudeSDKClient` directly (not through the agent registry):
- Eliminates the spawn/shutdown ceremony for an ephemeral operation
- Each review gets a fresh session with no context leakage between reviews
- Simpler mental model: `orchestration review arch ...` does the complete operation in one command
- No orphaned agents if the process is interrupted

Pipeline integration confirms this decision. The pipeline executor needs to call `run_review()` and get a `ReviewResult`. It does not need reviews to be registered agents with lifecycle management. Reviews as library calls (not agent lifecycle operations) are better for pipeline composability.

### Templates as YAML Files (Not Python Dataclasses)

Templates are defined as YAML files and loaded into `ReviewTemplate` dataclass instances at runtime.

**Why YAML over Python source definitions:**
- Pipeline definitions (ADP, initiative 160) are YAML. One format for all pipeline configuration.
- AI agents within the pipeline can create or modify review templates without touching source code — they write a YAML file.
- Users customize reviews by editing config files, not Python modules.
- Template discovery means scanning a directory, not introspecting Python modules.
- Version control diffs on YAML template changes are cleaner and more reviewable.

**What stays in Python:**
- `ReviewTemplate` dataclass — the runtime representation. Still type-checked in memory.
- `build_prompt()` — prompt construction logic. Most templates use a `prompt_template` string in the YAML with simple `{input}` / `{against}` substitution. Complex templates can specify a `prompt_builder` that names a Python function.
- `ReviewRunner` — SDK session management, result parsing, output formatting.
- Template registry — loading, lookup, listing.

**Built-in templates** ship as YAML files in a `templates/builtin/` resource directory within the package. User templates (future) go in `.orchestration/templates/` or a configured path. The registry scans both locations.

### Prompt Construction: Inline Templates and Python Escape Hatch

Most review templates have straightforward prompt construction — substitute file paths into a template string. The YAML `prompt_template` field handles this directly:

```yaml
prompt_template: |
  Review the document at: {input}
  Against the architecture document at: {against}
  Evaluate alignment and report findings using the severity format.
```

For complex prompt construction (conditional sections, multi-file assembly, dynamic scoping), the YAML specifies a `prompt_builder` — a dotted Python path to a function:

```yaml
prompt_builder: orchestration.review.builders.code_review_prompt
```

The builder function signature:

```python
def code_review_prompt(inputs: dict[str, str]) -> str:
    """Build the code review prompt with conditional sections."""
    ...
```

Rules:
- `prompt_template` and `prompt_builder` are mutually exclusive. Specifying both is a validation error.
- Exactly one must be present.
- The YAML loader resolves `prompt_builder` to a callable at load time (import and verify).

### Structured Review Output

Reviews produce `ReviewResult` objects — structured data that can be displayed to a terminal, serialized to JSON, written to a file, or consumed programmatically by the pipeline executor.

The agent produces text output following a conventional markdown format. The runner parses this text into a `ReviewResult`. If parsing fails (agent deviated from format), the runner falls back to a `ReviewResult` with the raw text and a `UNKNOWN` verdict, allowing the consumer to handle gracefully.

This design separates the agent interaction (text in, text out) from the structured representation (typed data objects). Adding JSON output mode to the SDK via `output_format` is a future optimization that would replace the text parsing step, but the `ReviewResult` interface to consumers stays identical.

### Review-Specific Prompt Construction

Each template defines how to construct its prompt from user-supplied inputs. This is where template-specific logic lives:

- `arch` template: constructs a prompt referencing the input document and context document, with evaluation criteria for architectural alignment
- `tasks` template: constructs a prompt that cross-references task items against slice design success criteria
- `code` template: constructs a prompt that identifies files to review and applies language-specific rules (uses `prompt_builder` for conditional --diff/--files handling)

The prompt tells the agent which files to `Read` — the agent does the actual file reading via tools. The CLI doesn't pre-read files and paste content into the prompt, because the agent needs tool access to navigate the project structure (e.g., following imports, reading referenced files).

### Read-Only by Default, Configurable per Template

All three initial templates restrict tools to read-only operations: `Read`, `Glob`, `Grep`. The `code` template additionally allows `Bash` for git operations (e.g., `git diff`, `git log`) but with `permission_mode="bypassPermissions"` only when the tool set is restricted to safe operations.

Templates define their own tool sets. A future "refactoring review" template could include `Edit` and `Write` tools if the review produces automated fixes.

### Output Format Convention

The agent is instructed via system prompt to produce findings in a consistent markdown format:

```
## Summary
[overall assessment: PASS | CONCERNS | FAIL]

## Findings

### [PASS|CONCERN|FAIL] Finding title
Description of the finding with specific file/line references.
```

This text is parsed by the runner into a `ReviewResult`. The text format is human-readable in the terminal and grep-parseable for basic automation. The structured `ReviewResult` is the canonical representation for programmatic consumers.

## Package Structure

```
src/orchestration/review/
├── __init__.py
├── models.py             # ReviewResult, ReviewFinding, Verdict, Severity
├── templates.py          # ReviewTemplate dataclass, template registry, YAML loader
├── runner.py             # Review execution: build prompt → ClaudeSDKClient → parse → ReviewResult
├── parsers.py            # Parse agent text output into ReviewResult
├── builders/
│   ├── __init__.py
│   └── code.py           # code_review_prompt() — complex prompt builder for code review
└── templates/
    └── builtin/
        ├── arch.yaml     # Architectural review template
        ├── tasks.yaml    # Task plan review template
        └── code.yaml     # Code review template

src/orchestration/cli/commands/
└── review.py             # CLI review subcommand

tests/review/
├── __init__.py
├── test_models.py        # ReviewResult, ReviewFinding construction and serialization
├── test_templates.py     # YAML loading, template construction, registry, validation
├── test_runner.py        # Prompt assembly, SDK integration (mocked), result handling
├── test_parsers.py       # Agent output → ReviewResult parsing, edge cases
├── test_builtin_arch.py  # Arch template prompt construction
├── test_builtin_tasks.py # Tasks template prompt construction
├── test_builtin_code.py  # Code template prompt construction (builder function)
└── test_cli_review.py    # CLI argument parsing, --output modes, command flow
```

## Component Design

### Result Models

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class Verdict(str, Enum):
    PASS = "PASS"
    CONCERNS = "CONCERNS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"  # fallback when agent output can't be parsed


class Severity(str, Enum):
    PASS = "PASS"
    CONCERN = "CONCERN"
    FAIL = "FAIL"


@dataclass
class ReviewFinding:
    """A single finding from a review."""
    severity: Severity
    title: str
    description: str
    file_ref: str | None = None  # file/line reference if applicable


@dataclass
class ReviewResult:
    """Structured output from a review execution."""
    verdict: Verdict
    findings: list[ReviewFinding]
    raw_output: str               # full agent response text
    template_name: str
    input_files: dict[str, str]   # what was reviewed (input keys → paths)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Serialize for JSON output."""
        ...

    @property
    def has_failures(self) -> bool:
        return any(f.severity == Severity.FAIL for f in self.findings)

    @property
    def concern_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CONCERN)
```

### ReviewTemplate Schema

```python
from dataclasses import dataclass
from collections.abc import Callable


@dataclass
class ReviewTemplate:
    """Runtime representation of a review workflow template. Loaded from YAML."""
    name: str                           # Short identifier (e.g., "arch", "tasks", "code")
    description: str                    # Human-readable description for `review list`
    system_prompt: str                  # System prompt for the review agent
    allowed_tools: list[str]            # SDK tools the agent can use
    permission_mode: str                # SDK permission mode
    setting_sources: list[str] | None   # SDK setting sources (e.g., ["project"] for CLAUDE.md)
    required_inputs: list[InputDef]     # Required CLI arguments with descriptions
    optional_inputs: list[InputDef]     # Optional CLI arguments with descriptions and defaults
    hooks: dict | None = None           # Optional SDK hooks — None for v1 templates

    # Prompt construction — exactly one of these is set (validated at load time)
    prompt_template: str | None = None        # Inline template string with {input} substitution
    prompt_builder: Callable | None = None    # Python function for complex prompt construction

    def build_prompt(self, inputs: dict[str, str]) -> str:
        """Construct the review prompt from user-supplied inputs."""
        if self.prompt_builder is not None:
            return self.prompt_builder(inputs)
        if self.prompt_template is not None:
            return self.prompt_template.format(**inputs)
        raise ValueError(f"Template '{self.name}' has neither prompt_template nor prompt_builder")


@dataclass
class InputDef:
    """Definition of a template input (CLI argument)."""
    name: str
    description: str
    default: str | None = None
```

### YAML Template Format

```yaml
# templates/builtin/arch.yaml
name: arch
description: "Architectural review — evaluate document against architecture/HLD"

system_prompt: |
  You are an architectural reviewer. Your task is to evaluate whether a design
  document aligns with a parent architecture document and its stated goals.
  
  Evaluation criteria:
  - Alignment with stated architectural goals and principles
  - Violations of architectural boundaries or layer responsibilities
  - Scope creep beyond what the architecture defines
  - Dependency directions are correct
  - Integration points match what consuming/providing slices expect
  - Common antipatterns: over-engineering, under-specification, hidden dependencies
  
  Report your findings using severity levels:
  
  ## Summary
  [overall assessment: PASS | CONCERNS | FAIL]
  
  ## Findings
  
  ### [PASS|CONCERN|FAIL] Finding title
  Description with specific references.

allowed_tools: [Read, Glob, Grep]
permission_mode: bypassPermissions
setting_sources: null

inputs:
  required:
    - name: input
      description: "Document to review (slice design, plan, spec)"
    - name: against
      description: "Architecture document or HLD to review against"
  optional:
    - name: cwd
      description: "Working directory for file reads"
      default: "."

prompt_template: |
  Review the following document for architectural alignment:
  
  **Input document:** {input}
  **Architecture document:** {against}
  
  Read both documents, then evaluate the input against the architecture.
  Follow referenced files as needed to understand dependencies and integration points.
  Report your findings using the severity format described in your instructions.
```

```yaml
# templates/builtin/code.yaml
name: code
description: "Code review — review code against project conventions and rules"

system_prompt: |
  You are a code reviewer. Review code against language-specific rules, testing
  standards, and project conventions loaded from CLAUDE.md.
  
  Focus areas:
  - Project conventions (from CLAUDE.md)
  - Language-appropriate style and correctness
  - Test coverage patterns (test-with, not test-after)
  - Error handling patterns
  - Security concerns
  - Naming, structure, and documentation quality
  
  Report findings using the severity format.

allowed_tools: [Read, Glob, Grep, Bash]
permission_mode: bypassPermissions
setting_sources: [project]

inputs:
  required: []
  optional:
    - name: cwd
      description: "Project directory to review"
      default: "."
    - name: files
      description: "Glob pattern to scope the review"
    - name: diff
      description: "Git ref to diff against (reviews changed files)"

# Complex prompt construction — delegates to Python
prompt_builder: orchestration.review.builders.code.code_review_prompt
```

### YAML Loader

```python
def load_template(path: Path) -> ReviewTemplate:
    """Load a ReviewTemplate from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    
    # Validate mutually exclusive prompt fields
    has_template = "prompt_template" in data
    has_builder = "prompt_builder" in data
    if has_template == has_builder:  # both or neither
        raise TemplateValidationError(
            f"Template must specify exactly one of prompt_template or prompt_builder"
        )
    
    # Resolve prompt_builder to callable if specified
    builder = None
    if has_builder:
        builder = _resolve_builder(data["prompt_builder"])  # importlib.import_module + getattr
    
    # Parse input definitions
    inputs_data = data.get("inputs", {})
    required = [InputDef(**i) for i in inputs_data.get("required", [])]
    optional = [InputDef(**i) for i in inputs_data.get("optional", [])]
    
    return ReviewTemplate(
        name=data["name"],
        description=data["description"],
        system_prompt=data["system_prompt"],
        allowed_tools=data["allowed_tools"],
        permission_mode=data["permission_mode"],
        setting_sources=data.get("setting_sources"),
        required_inputs=required,
        optional_inputs=optional,
        hooks=data.get("hooks"),
        prompt_template=data.get("prompt_template"),
        prompt_builder=builder,
    )
```

### Template Registry

```python
_TEMPLATES: dict[str, ReviewTemplate] = {}

def register_template(template: ReviewTemplate) -> None: ...
def get_template(name: str) -> ReviewTemplate | None: ...
def list_templates() -> list[ReviewTemplate]: ...

def load_builtin_templates() -> None:
    """Load all YAML templates from the builtin templates directory."""
    builtin_dir = Path(__file__).parent / "templates" / "builtin"
    for yaml_file in builtin_dir.glob("*.yaml"):
        template = load_template(yaml_file)
        register_template(template)
```

### Review Runner

```python
async def run_review(template: ReviewTemplate, inputs: dict[str, str]) -> ReviewResult:
    """Execute a review and return structured results.
    
    This is the primary interface for both CLI and programmatic (pipeline) consumers.
    """
    prompt = template.build_prompt(inputs)
    options = ClaudeAgentOptions(
        system_prompt=template.system_prompt,
        allowed_tools=template.allowed_tools,
        permission_mode=template.permission_mode,
        setting_sources=template.setting_sources,
        cwd=inputs.get("cwd"),
        hooks=template.hooks,
    )
    
    raw_output = ""
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            raw_output += extract_text(message)
    
    # Parse agent output into structured result
    result = parse_review_output(
        raw_output=raw_output,
        template_name=template.name,
        input_files=inputs,
    )
    return result
```

### Result Parser

```python
def parse_review_output(
    raw_output: str,
    template_name: str,
    input_files: dict[str, str],
) -> ReviewResult:
    """Parse agent markdown output into a structured ReviewResult.
    
    Falls back to UNKNOWN verdict if the output doesn't follow the expected format.
    """
    verdict = _extract_verdict(raw_output)  # parse "## Summary" section
    findings = _extract_findings(raw_output)  # parse "### [SEVERITY] Title" blocks
    
    return ReviewResult(
        verdict=verdict,
        findings=findings,
        raw_output=raw_output,
        template_name=template_name,
        input_files=input_files,
    )
```

## CLI `review` Subcommand

### Commands

#### `review arch`

```
orchestration review arch INPUT --against CONTEXT [--cwd DIR] [--output FORMAT]
```

- `INPUT` (positional, required): Path to the document being reviewed (slice design, plan, etc.)
- `--against` (required): Path to the architecture document or HLD to review against
- `--cwd` (optional): Working directory for file reads. Defaults to current directory.
- `--output` (optional): Output format — `terminal` (default), `json`, `file PATH`

Example:
```
orchestration review arch slices/105-slice.review-workflow-templates.md \
  --against architecture/100-arch.orchestration-v2.md
```

#### `review tasks`

```
orchestration review tasks INPUT --against CONTEXT [--cwd DIR] [--output FORMAT]
```

- `INPUT` (positional, required): Path to the task breakdown file
- `--against` (required): Path to the parent slice design
- `--cwd` (optional): Working directory. Defaults to current directory.
- `--output` (optional): Output format — `terminal` (default), `json`, `file PATH`

Example:
```
orchestration review tasks tasks/105-tasks.review-workflow-templates.md \
  --against slices/105-slice.review-workflow-templates.md
```

#### `review code`

```
orchestration review code [--cwd DIR] [--files PATTERN] [--diff REF] [--output FORMAT]
```

- `--cwd` (optional): Project directory to review. Defaults to current directory.
- `--files` (optional): Glob pattern to scope the review (e.g., `"src/**/*.py"`). Without this, the agent determines scope from project structure.
- `--diff` (optional): Git ref to diff against (e.g., `main`, `HEAD~3`). When provided, the review focuses on changed files.
- `--output` (optional): Output format — `terminal` (default), `json`, `file PATH`

Example:
```
orchestration review code --cwd ./orchestration --diff main
```

#### `review list`

```
orchestration review list
```

Displays available templates with name and description. Example output:

```
Available review templates:
  arch    Architectural review — evaluate document against architecture/HLD
  tasks   Task plan review — check task breakdown against slice design
  code    Code review — review code against project conventions and rules
```

### CLI Output Modes

```python
def display_result(result: ReviewResult, output_mode: str, output_path: str | None) -> None:
    """Format and deliver review results based on output mode."""
    match output_mode:
        case "terminal":
            _display_terminal(result)   # Rich-formatted, colored severity, summary line
        case "json":
            _display_json(result)       # result.to_dict() → json.dumps → stdout
        case "file":
            _write_file(result, output_path)  # JSON serialization to file
```

## Built-in Template Details

### `arch` — Architectural Review

**Purpose:** Evaluate whether a design document (slice design, plan, spec) aligns with the parent architecture document and stated goals.

**System prompt core themes:**
- Check alignment with stated architectural goals and principles
- Identify violations of architectural boundaries or layer responsibilities
- Flag scope creep beyond what the architecture defines
- Verify dependency directions are correct
- Check that integration points match what consuming/providing slices expect
- Detect common antipatterns: over-engineering, under-specification, hidden dependencies, template stuffing

**Tools:** `Read`, `Glob`, `Grep` — read-only. The agent reads both documents and any referenced files.

**Prompt construction:** Inline `prompt_template`. Tells the agent: read the input document at `{input}`, read the architecture/context at `{against}`, evaluate alignment, report findings with severity.

### `tasks` — Task Plan Review

**Purpose:** Verify that a task breakdown covers all success criteria from the parent slice design and that tasks are correctly sequenced, properly scoped, and independently completable.

**System prompt core themes:**
- Cross-reference each success criterion from the slice design against tasks
- Identify success criteria with no corresponding task (gaps)
- Identify tasks that don't trace to any success criterion (scope creep)
- Check task sequencing: dependencies respected, no circular deps
- Verify each task is completable by "a junior AI with clear success criteria" (per process guide)
- Flag tasks that are too large (should be split) or too granular (should be merged)

**Tools:** `Read`, `Glob`, `Grep` — read-only.

**Prompt construction:** Inline `prompt_template`. Tells the agent: read the task file at `{input}`, read the slice design at `{against}`, perform cross-reference analysis, report findings.

### `code` — Code Review

**Purpose:** Review code against language-specific rules, testing standards, and project conventions.

**System prompt core themes:**
- Follow project conventions from CLAUDE.md (loaded via `setting_sources=["project"]`)
- Apply language-appropriate style and correctness checks
- Verify test coverage patterns (test-with, not test-after)
- Check error handling patterns
- Flag security concerns
- Evaluate naming, structure, and documentation quality

**Tools:** `Read`, `Glob`, `Grep`, `Bash` — Bash is included for git operations (`git diff`, `git log`, `git show`).

**Permission mode:** `bypassPermissions` — the tool set is already restricted to safe operations.

**Setting sources:** `["project"]` — loads CLAUDE.md from the `cwd`, giving the agent access to project-specific conventions and rules.

**Prompt construction:** Uses `prompt_builder` (Python function). When `--diff` is provided, the prompt tells the agent to run `git diff {ref}` to identify changed files, then review those files. When `--files` is provided, the prompt scopes the review to matching files. When neither is provided, the agent uses Glob/Grep to survey the project and focuses on areas it deems most useful to review.

## Data Flow

### Review Execution (All Templates)

```
User: orchestration review arch slice.md --against arch.md
  │
  ▼
CLI (review command)
  │ resolves template: get_template("arch")
  │ collects inputs: {input: "slice.md", against: "arch.md"}
  │ validates: required inputs present
  ▼
ReviewRunner.run_review(template, inputs) → ReviewResult
  │ prompt = template.build_prompt(inputs)
  │ options = ClaudeAgentOptions(
  │   system_prompt=template.system_prompt,
  │   allowed_tools=["Read", "Glob", "Grep"],
  │   permission_mode="bypassPermissions",
  │   cwd=inputs.get("cwd", "."),
  │   hooks=template.hooks,  # None for v1
  │ )
  ▼
ClaudeSDKClient(options=options) — context manager
  │ connect() → spawns SDK subprocess
  │ client.query(prompt) → sends review request
  │ client.receive_response() → yields messages
  │   Agent reads input file via Read tool
  │   Agent reads context file via Read tool
  │   Agent may Glob/Grep for referenced files
  │   Agent produces review findings (markdown text)
  │ disconnect() → tears down subprocess (automatic via context manager)
  ▼
Result parser: raw text → ReviewResult
  │ Extract verdict from ## Summary section
  │ Extract findings from ### [SEVERITY] blocks
  │ Fallback: UNKNOWN verdict if parsing fails
  ▼
CLI: display_result(result, output_mode)
  │ terminal → Rich-formatted output with colored severity
  │ json → ReviewResult.to_dict() → stdout
  │ file → JSON serialization to specified path

Pipeline executor (alternative consumer):
  │ result = await run_review(template, inputs)
  │ if result.verdict == Verdict.CONCERNS: trigger_checkpoint()
  │ if result.verdict == Verdict.PASS: proceed_to_next_phase()
```

## Integration Points

### Provides to Other Slices

- **End-to-End Testing (slice 17):** Review commands are testable CLI surfaces. Integration tests can verify that a known-bad slice design produces FAIL findings against an architecture doc.
- **Automated Development Pipeline (initiative 160):** `run_review()` returns `ReviewResult` — the pipeline executor consumes this to drive phase transitions, escalation, and checkpoint decisions.

### Consumes from Prior Slices

- **CLI Foundation (slice 103):** Typer app entry point. The `review` subcommand is added to the existing app.
- **Foundation:** `Settings` for configuration, logging for review execution events.

### Does NOT Consume

- **Agent Registry:** Reviews use ephemeral `ClaudeSDKClient` sessions. No agent registration, no lifecycle management.
- **SDK Agent Provider:** Reviews use `ClaudeSDKClient` directly from `claude-agent-sdk`, not through the orchestration provider layer. The provider adds value for persistent agents with orchestration integration. Reviews don't need that.

## Success Criteria

### Functional Requirements

- `orchestration review arch INPUT --against CONTEXT` executes an architectural review and returns structured results
- `orchestration review tasks INPUT --against CONTEXT` executes a task plan review and returns structured results
- `orchestration review code [--cwd DIR] [--files PATTERN] [--diff REF]` executes a code review and returns structured results
- `orchestration review list` displays all available templates with descriptions
- Review output includes a summary verdict (PASS/CONCERNS/FAIL) and individual findings with severity levels as structured `ReviewResult` objects
- CLI `--output terminal` displays Rich-formatted results (default)
- CLI `--output json` outputs `ReviewResult` as JSON to stdout
- CLI `--output file PATH` writes JSON to specified path
- Reviews use read-only tools by default (no file modifications during review)
- Code review loads CLAUDE.md project conventions via `setting_sources=["project"]`
- Code review supports scoping via `--files` glob pattern or `--diff` git ref
- Built-in templates load from YAML files in the package's `templates/builtin/` directory
- Invalid template name produces a clear error listing available templates
- Missing required arguments produce clear usage errors
- SDK errors (CLI not found, process failure) produce user-friendly messages
- YAML validation errors (missing fields, both prompt_template and prompt_builder) produce clear messages

### Technical Requirements

- All tests pass with `ClaudeSDKClient` mocked at the import boundary
- Type checker passes with zero errors
- `ruff check` and `ruff format` pass
- YAML template loading has test coverage (valid files, validation errors, prompt_builder resolution)
- Template construction has test coverage for all three built-in templates
- Prompt assembly has test coverage (correct file paths inserted, optional args handled)
- Result parsing has test coverage (well-formed output, malformed output, UNKNOWN fallback)
- CLI argument parsing has test coverage (required args, optional args, defaults, --output modes)
- Review runner has test coverage (mock ClaudeSDKClient → verify options construction, prompt, and ReviewResult)

## Tracked Enhancements

### Hook Callbacks (Zero Architectural Cost)

The `ReviewTemplate` schema includes a `hooks` field and the runner passes it through to `ClaudeSDKClient`. Adding hook callbacks requires only defining the callback functions and wiring them into template definitions — no structural changes to the runner, CLI, or template schema.

Likely first hooks:
- **Audit logging** (`PostToolUse`): Log which files the review agent read, for traceability.
- **Bash command filtering** (`PreToolUse`, matcher: `"Bash"`): Conditionally block Bash commands based on the command string, rather than relying solely on the coarse `allowed_tools` list.

### User-Defined Templates

Allow users to define custom review templates as YAML files in `.orchestration/templates/` or a configured directory. The YAML loader and template registry already support this format — the enhancement is wiring the discovery path to scan user directories in addition to the builtin directory.

### Structured JSON Output via SDK

Add `output_format` JSON schema to the SDK call, allowing the agent to produce structured JSON directly instead of markdown that gets parsed. This replaces the text parsing step in the runner but the `ReviewResult` interface to consumers stays identical.

### Review Result Persistence

Save `ReviewResult` to a conventional location (e.g., `reviews/` directory) after each review. Enables tracking review history, comparing reviews over time, and auditing review coverage. Trivial to implement since `ReviewResult.to_dict()` provides serialization.

### Interactive Review Mode (Low Cost)

Since the runner already uses `ClaudeSDKClient`, enabling follow-up questions requires only keeping the client session open after the initial review and adding a prompt loop. "Explain finding #3 in more detail" or "How would you fix the issue in section X?" — the session continuity is already there. The main work is the CLI interaction loop and a `--interactive` flag.

## Implementation Notes

### Suggested Implementation Order

1. **Result models** (effort: 0.5/5) — `ReviewResult`, `ReviewFinding`, `Verdict`, `Severity` in `models.py`. Serialization. Tests.
2. **YAML loader + ReviewTemplate + registry** (effort: 1.5/5) — YAML loading, validation (prompt_template vs prompt_builder mutual exclusion), `InputDef` parsing, `prompt_builder` resolution, registry with builtin directory scanning. Tests.
3. **Built-in template YAML files + code prompt builder** (effort: 1/5) — `arch.yaml`, `tasks.yaml`, `code.yaml` in `templates/builtin/`. `code_review_prompt()` builder in `builders/code.py`. The system prompts are the most important design artifact here — they encode the review expertise. Tests for prompt construction.
4. **Result parser** (effort: 1/5) — Parse agent markdown output into `ReviewResult`. Handle well-formed output, malformed output, UNKNOWN fallback. Tests.
5. **Review runner** (effort: 1/5) — `run_review()` function: build prompt, construct `ClaudeAgentOptions`, create `ClaudeSDKClient` session, execute review, parse into `ReviewResult`, return. Tests (mocked SDK).
6. **CLI `review` subcommand** (effort: 1/5) — Typer commands for `review arch`, `review tasks`, `review code`, `review list`. Argument parsing, template lookup, delegation to runner, `display_result()` with `--output` modes. Tests.

### Testing Strategy

All tests mock `ClaudeSDKClient` at the import boundary. The mock's `receive_response()` returns a predefined async iterator of `AssistantMessage` and `ResultMessage` objects.

Test categories:

- **Model tests:** `ReviewResult` construction, serialization (`to_dict()`), properties (`has_failures`, `concern_count`).
- **Template tests:** YAML loading (valid files, validation errors), `build_prompt()` output for various input combinations, registry lookup, `prompt_builder` resolution, `hooks` field passthrough.
- **Parser tests:** Well-formed markdown → correct `ReviewResult`. Malformed markdown → `UNKNOWN` verdict with raw output preserved. Edge cases: missing summary, findings without severity prefix, empty output.
- **Runner tests:** Verify `ClaudeAgentOptions` construction from template fields. Verify `ClaudeSDKClient` instantiated with correct options. Verify `query()` called with built prompt. Verify `ReviewResult` returned.
- **CLI tests:** Argument parsing via Typer's `CliRunner`. Error messages for missing args, invalid template names. `--output` mode routing.
- **Prompt quality tests (optional but valuable):** Snapshot tests for the actual prompt strings produced by each template. If the prompt changes, the snapshot forces a deliberate review.

### System Prompt Development

The system prompts for each template are the most design-sensitive part of this slice. They encode what "a good review" means. Rather than trying to perfect them in this design document, the implementation should:

1. Start with a reasonable initial prompt based on the themes listed in the template details above
2. Test with real documents from this project (the orchestration slice designs and arch doc are perfect test inputs)
3. Iterate based on output quality — the system prompts will likely need 2-3 rounds of refinement

This is an area where the implementing agent should be given latitude to refine prompts through testing rather than being held to a rigid specification.
