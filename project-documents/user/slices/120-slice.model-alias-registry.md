---
docType: slice-design
slice: model-alias-registry
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [review-provider-model-selection]
interfaces: []
dateCreated: 20260321
dateUpdated: 20260321
status: complete
---

# Slice Design: Model Alias Registry & Content Injection for Non-SDK Reviews

## Overview

This slice addresses two related usability problems with multi-provider reviews:

1. **Model aliases are hardcoded.** `_infer_profile_from_model()` uses pattern-matching (`opus` → sdk, `gpt-*` → openai). Users can't add custom shorthands (e.g., `kimi25` for a specific Kimi model on OpenRouter). The inference is brittle and not user-extensible.

2. **Non-SDK reviews can't read files.** The prompt templates say "Read both documents" and provide file paths, but non-SDK providers have no tool access. The model receives paths it can't open and returns "I can't read those files." File contents must be injected into the prompt for non-SDK paths.

Both problems share a root cause: the non-SDK review path was designed for routing but not for actual usability. This slice makes non-SDK reviews actually work.

## Value

- **`sq review tasks 118 --model kimi25`** — one flag, no `--profile`, no full model ID
- **Non-SDK reviews produce real results** — file contents injected into the prompt, model reviews actual content
- **User-extensible** — add `kimi25 = { profile = "openrouter", model = "moonshotai/kimi-k2" }` to `~/.config/squadron/models.toml`
- **Prerequisite for Ensemble Review (131)** — multi-model fan-out requires models to be easy to specify and non-SDK reviews to actually work

## Technical Scope

### Included

- Model alias registry: built-in defaults + user `models.toml`
- `resolve_model_alias()` function replacing `_infer_profile_from_model()`
- Content injection for non-SDK review prompts (slice, tasks, code)
- `sq model list` CLI command to show available aliases
- Rename `review arch` → `review slice` (CLI command, slash command, template name)
- Update slash commands to document model aliases and rename

### Excluded

- Anthropic API provider (slice 123 — separate provider implementation)
- `latest` alias semantics (e.g., `opus` always points to newest Opus version) — future enhancement, not enough value vs. complexity right now
- Tool use for non-SDK providers (function calling, multi-turn) — separate scope

## Dependencies

### Prerequisites

- **Review Provider & Model Selection (119)** — complete. Provides `--profile`, `_infer_profile_from_model()`, `run_review_with_profile()`, user templates.

### External Packages

- `tomllib` (stdlib) — for parsing `models.toml`

## Technical Decisions

### Model Alias Registry

#### File Format

```toml
# ~/.config/squadron/models.toml

[aliases]
opus = { profile = "sdk", model = "claude-opus-4-6" }
sonnet = { profile = "sdk", model = "claude-sonnet-4-6" }
haiku = { profile = "sdk", model = "claude-haiku-4-5-20251001" }
gpt4o = { profile = "openai", model = "gpt-4o" }
o3 = { profile = "openai", model = "o3-mini" }
kimi25 = { profile = "openrouter", model = "moonshotai/kimi-k2" }
deepseek = { profile = "openrouter", model = "deepseek/deepseek-chat-v3-0324" }
```

Each alias maps to:
- `profile`: which provider profile to use (from `profiles.py` / `providers.toml`)
- `model`: the full model ID to send to the API

#### Built-in Defaults

Ship a `BUILT_IN_ALIASES` dict in `src/squadron/models/aliases.py` covering:
- Claude family: `opus`, `sonnet`, `haiku` (with current model IDs)
- OpenAI family: `gpt4o`, `o3`, `o1`
- Common shorthand: `gpt-4o` → itself (passthrough for explicit model IDs that happen to match)

User `models.toml` entries override built-in aliases by name.

#### Resolution Function

```python
def resolve_model_alias(
    name: str,
) -> tuple[str, str | None]:
    """Resolve a model alias to (full_model_id, profile_or_none).

    If the name matches a known alias, returns the alias's
    (model, profile). If not, returns (name, None) — treating
    the input as a literal model ID with no profile inference.
    """
```

This replaces `_infer_profile_from_model()` in `review.py`. The resolution chain becomes:

```
--model opus
  → resolve_model_alias("opus")
  → ("claude-opus-4-6", "sdk")
  → _resolve_profile uses "sdk", _resolve_model uses "claude-opus-4-6"
```

When no alias matches, the raw model string passes through unchanged (backward compatible).

#### Module Location

`src/squadron/models/aliases.py` — new module. The `models/` package is a natural home since this is model-level infrastructure, not review-specific. Both review commands and future `sq spawn --model` can use it.

### Rename `review arch` → `review slice`

The current `sq review arch` name implies reviewing an architecture document, but it actually reviews a **slice design** against the architecture. The command name should match the review target:

- `sq review slice` — reviews slice design (against architecture/plan)
- `sq review tasks` — reviews task breakdown (against slice design)
- `sq review code` — reviews code (against standards/rules)

Changes required:
- CLI: rename `review_arch` function to `review_slice`, command name `"arch"` → `"slice"`
- Template: rename `arch.yaml` → `slice.yaml`, update `name: arch` → `name: slice`
- Slash command: rename `commands/sq/review-arch.md` → `commands/sq/review-slice.md`
- Backward compatibility: add a hidden `review arch` alias that delegates to `review slice` with a deprecation notice, so existing scripts/habits don't break immediately
- Update `_save_review_file()` callers: review type changes from `"arch"` to `"slice"`
- Existing review files with `reviewType: arch` remain valid — the parser doesn't check review type
- Update install test expected file count/names
- Update `run-slice.md` references

### Content Injection for Non-SDK Reviews

#### The Problem

Current prompt templates (arch, tasks) contain file paths:

```
**Task file:** {input}
**Slice design:** {against}

Read both documents, then cross-reference...
```

The SDK path works because the SDK agent has Read/Glob/Grep tools. Non-SDK providers receive these paths but can't read local files.

#### The Solution

In `_run_non_sdk_review()` (in `review_client.py`), after building the prompt from the template, inject file contents into the prompt before sending to the API. The injection happens at the review client level, not in the template — templates remain provider-agnostic.

```python
# In _run_non_sdk_review(), after building the prompt:
prompt = template.build_prompt(inputs)
prompt = _inject_file_contents(prompt, inputs)
```

The `_inject_file_contents()` function:
1. Iterates `inputs` dict values, skipping known non-path keys (`cwd`)
2. For each value, checks `Path(value).is_file()` — no regex, no heuristic, just filesystem existence
3. For each existing file, reads the content and appends to a `## File Contents` section with fenced blocks keyed by input name
4. If a file is too large (>100KB), notes it as truncated

The detection is deterministic: `is_file()` returns `True` for real file paths and `False` for everything else (directories, globs, bare strings like `"."`, model names). The `inputs` dict is tightly controlled — it only contains values set by the CLI command handlers, not arbitrary user input.

This approach:
- **Doesn't modify templates** — they remain the same for SDK and non-SDK paths
- **Is deterministic** — `is_file()` check, not pattern matching or heuristics
- **Is safe** — only reads files already in the inputs dict, doesn't traverse directories
- **Handles code reviews** — the `diff` input is a git ref (not a file), handled as a special case

#### Code Review Special Case

For code reviews with `--diff`, the prompt says "Run `git diff {ref}`". Non-SDK models can't run commands. The content injection should:
1. Detect `diff` in inputs
2. Run `git diff {ref}` locally
3. Inject the diff output into the prompt

For code reviews with `--files`, run the glob locally and inject matching file contents (up to reasonable size limits).

#### Size Limits

- Per-file limit: 100KB (most source files are well under this)
- Total injection limit: 500KB (enough for several large files or a substantial diff)
- When limits are hit, truncate with a clear message: `[truncated at 100KB — file too large for API review]`
- Log a warning when truncation occurs

### Integration Points

#### Single-Resolution in `_run_review_command()`

Per arch review feedback: resolve the alias **once** at the top of `_run_review_command()` and thread the result through, rather than calling `resolve_model_alias()` separately in `_resolve_model()` and `_resolve_profile()`.

```python
# In _run_review_command(), before calling _resolve_model/_resolve_profile:
alias_model, alias_profile = resolve_model_alias(model_flag) if model_flag else (None, None)
resolved_model = _resolve_model(alias_model or model_flag, template)
resolved_profile = _resolve_profile(profile_flag or alias_profile, template, resolved_model)
```

This means `_resolve_model()` and `_resolve_profile()` remain unchanged — they don't need to know about aliases. The alias resolution is a pre-processing step that expands shorthands before the existing resolution chain runs. `_infer_profile_from_model()` is removed entirely — the alias registry defaults subsume its logic.

#### `sq model list` Command

New CLI command showing available model aliases:

```
$ sq model list
  opus        sdk         claude-opus-4-6
  sonnet      sdk         claude-sonnet-4-6
  haiku       sdk         claude-haiku-4-5-20251001
  gpt4o       openai      gpt-4o
  o3          openai      o3-mini
  kimi25      openrouter  moonshotai/kimi-k2    (user)
```

The `(user)` tag indicates overrides from `models.toml`.

## Data Flow

### Model Alias Resolution

```
CLI: sq review tasks 118 --model kimi25
  → _run_review_command(model_flag="kimi25")
    → resolve_model_alias("kimi25") → ("moonshotai/kimi-k2", "openrouter")  [once]
    → _resolve_model("moonshotai/kimi-k2", template) → "moonshotai/kimi-k2"
    → _resolve_profile("openrouter", template, "moonshotai/kimi-k2") → "openrouter"
    → _execute_review(model="moonshotai/kimi-k2", profile="openrouter")
```

### Content Injection (Non-SDK)

```
_run_non_sdk_review(template, inputs, profile="openrouter", model="moonshotai/kimi-k2")
  → prompt = template.build_prompt(inputs)  # "Review the following... **Task file:** path/to/tasks.md ..."
  → prompt = _inject_file_contents(prompt, inputs)  # appends actual file contents
  → API call with enriched prompt
  → parse_review_output() → ReviewResult
```

### Content Injection (SDK — unchanged)

```
run_review(template, inputs, ...)
  → SDK agent receives prompt with file paths
  → Agent uses Read tool to access files
  → Streams response
```

## Success Criteria

### Functional Requirements

- `sq review tasks 118 --model kimi25` resolves alias, routes through OpenRouter, injects file contents, returns real review
- `sq review slice 118 --model gpt4o` resolves to `gpt-4o` on OpenAI, injects design + arch doc content
- `sq review code 118 --model gpt4o` injects git diff output into prompt
- `sq review tasks 118 --model opus` continues to work via SDK (no content injection needed)
- `sq model list` shows built-in + user aliases with profile and model ID
- User can add `kimi25 = { profile = "openrouter", model = "moonshotai/kimi-k2" }` to `~/.config/squadron/models.toml`
- User alias overrides built-in by name
- Missing `models.toml` doesn't error (graceful handling)
- `_infer_profile_from_model()` is removed — alias registry handles all inference
- `sq review slice` works, `sq review arch` is a deprecated alias
- `/sq:review-slice` slash command replaces `/sq:review-arch`
- Existing SDK path works identically (regression)

### Technical Requirements

- `src/squadron/models/aliases.py` provides `resolve_model_alias()`, `get_all_aliases()`, built-in defaults
- Content injection in `review_client.py` for non-SDK path only
- Size limits enforced (100KB per file, 500KB total)
- `sq model list` command in CLI
- All existing tests pass
- New tests for alias resolution, content injection, CLI command
- `pyright`, `ruff check`, `ruff format` pass

## Verification Walkthrough

Steps 1-5 and 7 are **live tests** requiring API keys — deferred to post-implementation manual verification (PM tasks).

6. **Model list:** (verified)
   ```bash
   sq model list
   # Output:
   # ┏━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
   # ┃ Alias  ┃ Profile ┃ Model ID                  ┃ Source ┃
   # ┡━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
   # │ gpt4o  │ openai  │ gpt-4o                    │        │
   # │ haiku  │ sdk     │ claude-haiku-4-5-20251001 │        │
   # │ o1     │ openai  │ o1-preview                │        │
   # │ o3     │ openai  │ o3-mini                   │        │
   # │ opus   │ sdk     │ claude-opus-4-6           │        │
   # │ sonnet │ sdk     │ claude-sonnet-4-6         │        │
   # └────────┴─────────┴───────────────────────────┴────────┘
   ```

**Additional verifications performed:**
- `sq review slice --help` — shows "Run a slice design review"
- `sq review arch --help` — shows "(deprecated: use 'review slice')"
- `uv run pytest` — 514 tests pass
- `uv run ruff check` — clean
- `uv run ruff format --check` — clean
- `uv run pyright` — 0 errors

## Implementation Notes

### Suggested Implementation Order

1. **Rename `review arch` → `review slice`** — CLI, template, slash command, backward-compat alias (effort: 1/5)
2. **Create `models/aliases.py`** with `BUILT_IN_ALIASES`, `resolve_model_alias()`, user TOML loading (effort: 1/5)
3. **Wire alias resolution into `_run_review_command()`**, remove `_infer_profile_from_model()` (effort: 1/5)
4. **Add `_inject_file_contents()` to `review_client.py`** for non-SDK path (effort: 2/5)
5. **Handle code review special case** — diff/files injection (effort: 1/5)
6. **Add `sq model list` CLI command** (effort: 0.5/5)
7. **Update slash commands** (effort: 0.5/5)
8. **Tests** (effort: 1.5/5)

### Known Limitations

- **Content injection adds token cost.** Injecting file contents means larger prompts and higher API costs. The size limits (100KB/file, 500KB total) keep this bounded, but users should be aware that non-SDK reviews with large files will use more tokens than SDK reviews where the agent reads selectively.
- **No tool use for non-SDK providers.** Even with content injection, non-SDK models can't explore the codebase beyond what's injected. SDK reviews remain superior for deep code exploration. Content injection makes non-SDK reviews *workable*, not *equivalent*.
- **Code review quality depends on diff size.** Large diffs may be truncated, reducing review quality. For large changes, SDK reviews are preferred.

### Testing Strategy

- **Alias resolution:** unit tests for `resolve_model_alias()` — built-in, user override, unknown alias passthrough
- **Content injection:** unit tests with tmp_path files, verify contents appear in enriched prompt
- **Size limits:** test truncation behavior at limits
- **Code review injection:** mock `subprocess.run` for `git diff`, verify diff output in prompt
- **CLI `model list`:** CliRunner test, verify output format
- **Regression:** existing tests unchanged — SDK path doesn't use content injection
