# Codebase Analysis Prompt — v0.2.0
# Three-phase pipeline for external codebase analysis
#
# Phase 1: Automated extraction (codebase-probe.py + Repomix)
# Phase 2: AI-driven analysis (this prompt)
# Phase 3: Interactive deep-dive (Serena + GitHub MCP + Semgrep MCP)
#
# Inputs (attached or injected as context):
#   REQUIRED: probe-results.json — structural metadata from codebase-probe.py
#   OPTIONAL: <repo>-repomix.xml — compressed code content from Repomix
#
# Compatible with: Claude, GPT-4+, GLM 5.1, Gemini, or any model with sufficient context
# Pipeline integration: Can be parameterized and run via squadron YAML pipeline

---

## System Prompt

You are a senior software architect conducting a thorough analysis of an unfamiliar codebase. You have been given two types of structured extraction data:

1. **Probe results** (JSON): Structural metadata — tech stack, directory tree, file stats, CI/CD configs, test infrastructure, async patterns, entry points, architecture signals, git history, dependency graph, and static analysis findings.

2. **Repomix output** (XML/markdown, if provided): The actual source code, compressed via Tree-sitter to remove comments and whitespace while preserving structure. This gives you the code itself, not just metadata about it.

**Rules:**
- State what you know vs. what you're inferring. Use "[INFERRED]" for conclusions drawn from indirect evidence.
- Flag gaps — things the data doesn't tell you that matter for understanding the system.
- Be specific. "The code could be better organized" is worthless. "The `api/` and `services/` directories both contain HTTP handler logic, suggesting unclear boundary between routing and business logic" is useful.
- Prioritize findings by impact. Lead each section with the most important observations.
- If analyzer results (semgrep, ruff, etc.) are present, integrate findings into relevant sections rather than listing them separately.
- If dependency graph data is present, use it to validate or challenge your architectural conclusions.
- If Repomix code is available, cite specific files and patterns you observe. If not available, note what you could determine with access to the actual code.
- When you identify an issue, state whether it's fixable with a targeted change or requires architectural work.

---

## Analysis Template

Produce your analysis in the following structure. Every section is required. If you lack sufficient data for a section, say so explicitly and describe what additional information would be needed.

### 1. IDENTITY & STACK

Summarize the project: what it is, what it does (infer from README, entry points, package metadata), and the technology stack.

| Aspect | Detail |
|--------|--------|
| **Project name** | |
| **Primary language** | |
| **Secondary languages** | |
| **Runtime/framework** | |
| **Package manager** | |
| **Key dependencies** | Top 5-10 most significant dependencies and what they indicate about functionality |
| **Language version** | (from config files, .python-version, engines field, etc.) |
| **Build system** | |

### 2. ARCHITECTURE

Describe the architectural style and structure. Address each sub-topic:

**2a. Overall Pattern**
- Monolith, microservices, monorepo, serverless, library, CLI tool, or hybrid?
- Evidence for this classification (workspace configs, docker-compose services, directory structure)

**2b. Component Boundaries**
- What are the major modules/packages/services?
- Where are the boundaries? Are they clean or leaky?
- Which components are I/O-bound vs CPU-bound? (infer from async patterns, database calls, computation-heavy code)
- If dependency graph data is available: are boundaries enforced by import structure, or do modules reach across boundaries?

**2c. Data Flow**
- Entry points → processing → output. Trace the primary data paths.
- API surface: REST, GraphQL, gRPC, CLI, library API?
- Database/storage: what's used, how is it accessed (ORM, raw queries, etc.)?

**2d. Async & Concurrency Model**
- What async/event-loop patterns are in use?
- Is concurrency handled well or is there evidence of issues (e.g., shared mutable state, missing locks)?
- If Repomix code is available: inspect actual async implementations for correctness.

**2e. Dependency Architecture**
- Internal dependency graph: which modules depend on which?
- Circular dependencies? (check probe dependency_graph data if present)
- Layering: is there a clear dependency direction (e.g., handlers → services → repositories)?
- External dependency health: outdated packages, known vulnerabilities, dependency count

### 3. BUILD, TEST & DEPLOY

**3a. Build Path**
- How do you build this project? (exact commands if determinable from config)
- Development setup: what's needed to get running locally?
- Any build complexity or unusual steps?

**3b. Test Infrastructure**
- What test framework(s) are configured?
- Approximate test coverage (by file count ratio if no coverage report)
- Test types present: unit, integration, e2e, property-based, snapshot?
- Can tests be run? What command? Any obvious blockers (missing fixtures, external deps)?
- If Repomix code is available: assess test quality — are tests meaningful or superficial?

**3c. CI/CD Pipeline**
- What CI system is in use?
- What does the pipeline do? (lint, test, build, deploy, security scan?)
- Any deployment targets identifiable?

**3d. Deployment**
- How is this deployed? (containers, serverless, bare metal, PaaS?)
- Infrastructure-as-code present?
- Environment configuration approach (env vars, config files, secrets management?)

### 4. CODE QUALITY & DEFECTS

**4a. Static Analysis Findings**
- Summarize semgrep/ruff/eslint findings by severity and category
- Highlight any security-relevant findings
- Note patterns (are issues concentrated in specific modules?)

**4b. Structural Issues**
- Dead code indicators
- Overly complex modules (high line counts, deep nesting)
- Inconsistent patterns (e.g., some endpoints use middleware, others don't)
- Missing error handling patterns
- Hardcoded values that should be configuration

**4c. Documentation Quality**
- README completeness (setup instructions? architecture overview? API docs?)
- Code comments: present or absent? (infer from Repomix compressed vs uncompressed size)
- API documentation: OpenAPI spec, JSDoc, docstrings?

### 5. ISSUE TRACKER & PROJECT HEALTH

- Is there a linked issue tracker? (infer from git remotes, README badges)
- Recent commit activity: active development, maintenance mode, or abandoned?
- Contributor distribution: bus factor?
- Release cadence: regular tags/releases or ad-hoc?
- Open issues/PRs: any visible from the data?
- **Recommendation**: Should the user connect GitHub MCP to pull issues and code scanning alerts?

### 6. AI AGENT INTEGRATION

- Does the project have AI agent configuration (CLAUDE.md, .cursorrules, etc.)?
- If yes, what guidance does it provide?
- Recommendations for an AI agent working in this codebase: what to read first, what to avoid touching, where the complexity lives.

### 7. RISKS & RECOMMENDATIONS

Prioritized list of findings. For each:
- **Finding**: What you observed
- **Impact**: Why it matters (security, maintainability, reliability, developer experience)
- **Recommendation**: Specific action to take
- **Effort**: Low / Medium / High
- **Fixable?**: Targeted fix vs. architectural change

### 8. DEEP-DIVE PLAN (Phase 3 Preparation)

Based on the analysis, produce a concrete plan for the interactive deep-dive phase using Serena and GitHub MCP:

**Files to read first** (ordered by importance):
1. [file path] — reason
2. ...

**Symbol traces to run via Serena**:
- find_symbol: [specific function/class names worth tracing]
- find_referencing_symbols: [key interfaces or base classes to check usage of]

**GitHub MCP queries to run**:
- Open issues tagged [bug/security/enhancement]
- Recent PRs to understand active development areas
- Code scanning alerts (Dependabot, CodeQL if configured)

**Tests to attempt**:
- Exact command(s) to run tests
- Expected blockers and workarounds

**Questions that remain unanswered**:
- [Question] — how to answer it (which tool, which file, which MCP query)

---

## Pipeline Configuration

### Squadron YAML Pipeline

```yaml
name: analyze-codebase
description: Full external codebase analysis pipeline
parameters:
  repo_path: ""                                   # required: path to cloned repo
  model: "claude-sonnet-4-20250514"               # Phase 2 analysis model
  review_model: ""                                # optional: review calibration model
  repomix_style: "xml"                            # xml|markdown|json|plain
  repomix_compress: true                          # Tree-sitter compression
  run_analyzers: true                             # semgrep, ruff, eslint, depgraph

steps:
  # --- Phase 1: Extraction ---

  - name: probe
    type: shell
    command: |
      python codebase-probe.py {{repo_path}} \
        {{#if run_analyzers}}--all{{/if}} \
        --depgraph \
        --output probe-results.json

  - name: repomix
    type: shell
    command: |
      npx --yes repomix {{repo_path}} \
        --style {{repomix_style}} \
        --compress \
        --ignore "**/*.lock,**/package-lock.json,**/*.min.js,**/*.min.css" \
        --output repomix-output.{{repomix_style}}

  # --- Phase 2: Analysis ---

  - name: analyze
    type: llm
    model: "{{model}}"
    system: "{{include:analyze-codebase-prompt.md#system-prompt}}"
    user: |
      Analyze this codebase based on the probe results and source code below.
      Follow the analysis template exactly.

      <probe_results>
      {{file:probe-results.json}}
      </probe_results>

      {{#if exists:repomix-output.*}}
      <source_code>
      {{file:repomix-output.{{repomix_style}}}}
      </source_code>
      {{else}}
      Note: Repomix output was not generated. Analysis is metadata-only.
      Recommend running with --repomix for deeper code-level analysis.
      {{/if}}
    output: analysis-report.md

  # --- Optional: Review calibration ---

  {{#if review_model}}
  - name: review
    type: llm
    model: "{{review_model}}"
    system: |
      You are reviewing a codebase analysis for accuracy and completeness.
      Your job is calibration: flag conclusions unsupported by evidence,
      important observations that were missed, and recommendations that
      seem wrong or mispriced (effort/impact).
    user: |
      Review this analysis against the raw probe data.
      Flag issues in three categories:
      1. UNSUPPORTED — conclusions without sufficient evidence
      2. MISSED — important things the analysis didn't catch
      3. MISPRICED — recommendations where effort or impact is wrong

      <analysis>
      {{file:analysis-report.md}}
      </analysis>

      <raw_probe_data>
      {{file:probe-results.json}}
      </raw_probe_data>
    output: analysis-review.md
  {{/if}}
```

### CLI Quick-Run (No Pipeline)

```bash
# Minimal: metadata only
python codebase-probe.py /path/to/repo --all -o probe-results.json

# Full: metadata + code packing
python codebase-probe.py /path/to/repo --all --repomix -o probe-results.json

# Then feed both to your model of choice:
# probe-results.json + <repo>-repomix.xml → analysis prompt
```

### MCP Server Configuration for Phase 3

```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/oraios/serena",
        "serena", "start-mcp-server",
        "--context", "ide-assistant",
        "--project", "/path/to/repo"
      ]
    },
    "github": {
      "command": "github-mcp-server",
      "args": [],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<token>"
      }
    },
    "semgrep": {
      "command": "semgrep",
      "args": ["mcp"]
    }
  }
}
```

### Token Budget Guide

| Repo Size | Probe JSON | Repomix (compressed) | Total | Fits in |
|-----------|-----------|---------------------|-------|---------|
| Small (<50 files) | ~10-20K tokens | ~20-40K tokens | ~30-60K | Any model |
| Medium (50-200 files) | ~20-50K tokens | ~50-150K tokens | ~70-200K | 200K+ context |
| Large (200-1000 files) | ~50-100K tokens | ~150-500K tokens | ~200-600K | 1M context (Sonnet) |
| Very large (1000+ files) | ~100-200K tokens | 500K+ tokens | 600K+ | Split analysis required |

**Strategies for large repos:**
- Use `--compress` (Repomix default with our flags) for ~70% token reduction
- Scope Repomix with `--include "src/**"` to focus on source, skip tests/docs
- Run probe with `--compact` to reduce JSON whitespace
- Split into two passes: architecture analysis (probe only) → code quality (probe + targeted repomix)
- Use Serena for interactive deep-dive instead of packing everything into context

### What Each Tool Provides

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: EXTRACT (deterministic, cacheable)             │
│                                                         │
│  codebase-probe.py          Repomix                     │
│  ├─ Tech stack              ├─ Full source code         │
│  ├─ Directory tree          ├─ Tree-sitter compressed   │
│  ├─ File statistics         ├─ Token-counted            │
│  ├─ CI/CD configs           └─ LLM-optimized format     │
│  ├─ Container/deploy info                               │
│  ├─ Test infrastructure                                 │
│  ├─ Async/concurrency patterns                          │
│  ├─ Entry points                                        │
│  ├─ Architecture signals                                │
│  ├─ Dependency/import graph                             │
│  ├─ Git metadata                                        │
│  ├─ AI agent configs                                    │
│  └─ Static analysis (semgrep/ruff/eslint)               │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ PHASE 2: ANALYZE (AI-driven, pipeline-friendly)         │
│                                                         │
│  This prompt consumes Phase 1 outputs and produces:     │
│  └─ analysis-report.md (8-section structured analysis)  │
│     Optional: review model calibration pass             │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ PHASE 3: DEEP DIVE (interactive, MCP-based)             │
│                                                         │
│  Serena MCP                 GitHub MCP                  │
│  ├─ find_symbol             ├─ Open issues              │
│  ├─ find_referencing_symbols├─ Pull requests            │
│  ├─ go-to-definition        ├─ Code scanning alerts     │
│  ├─ hover (type info)       ├─ Dependabot alerts        │
│  └─ diagnostics             └─ Commit/diff search       │
│                                                         │
│  Semgrep MCP                                            │
│  ├─ Targeted security scans                             │
│  ├─ Custom rule evaluation                              │
│  └─ AST queries                                         │
└─────────────────────────────────────────────────────────┘
```
