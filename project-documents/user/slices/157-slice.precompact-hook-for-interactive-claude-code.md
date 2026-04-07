---
docType: slice-design
slice: precompact-hook-for-interactive-claude-code
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [141-configuration-externalization]
interfaces: [158-sdk-session-management-and-compaction]
dateCreated: 20260407
dateUpdated: 20260407
status: not_started
---

# Slice Design: PreCompact Hook for Interactive Claude Code

## Overview

When a user types `/compact` (or auto-compaction fires) inside an interactive Claude Code session — VS Code extension or CLI Claude Code — Claude Code looks for a `PreCompact` hook in `.claude/settings.json` and runs the configured shell command before summarizing the conversation. This slice ships that hook for squadron projects, so the compaction summarizer receives project-aware instructions instead of the generic default.

The hook target is a hidden squadron subcommand. The user-facing surface is config only:

```bash
sq install-commands         # also writes the PreCompact hook entry
sq config set compact.template minimal --project
# or
sq config set compact.instructions "Keep slice {slice} design and tasks; drop everything else."
```

This slice is **independent of SDK mode**. The Agent SDK's `ClaudeAgentOptions.hooks` field is unrelated and is not touched. SDK-mode compaction is handled by slice 158 (SDK Session Management and Compaction).

## Value

- **Project-aware `/compact` in interactive Claude Code**: stops users from losing slice context when manual or auto compaction fires inside the IDE / CLI Claude Code.
- **Zero new commands to memorize**: instructions are picked via the existing `sq config` surface; the hook target is invisible.
- **Reuses existing infrastructure**: the same compaction template loader, lenient param renderer, and config layering that pipelines already use.
- **Per-project override**: each squadron project can ship its own template without affecting the user's other projects.

## Technical Scope

### In Scope

1. **Hidden hook subcommand** — A new Typer subcommand registered on the `sq` app with `hidden=True`. Reads config, resolves a template or literal, renders params from the current CF project state, and prints the `PreCompact` hook output JSON to stdout.
2. **Two new config keys** — `compact.template` (template name) and `compact.instructions` (literal string). Mutually exclusive at resolve time. Both honour the existing user vs `--project` layering via `squadron.config.manager`.
3. **Installer extension** — `sq install-commands` writes a `PreCompact` entry to `.claude/settings.json` (project-local, alongside `.claude/commands/`). Non-destructive merge: existing hooks are preserved. `sq uninstall-commands` removes the entry without touching unrelated hooks.
4. **Param rendering** — Reuse the existing `_LenientDict` lenient-format helper from [actions/compact.py:77](src/squadron/pipeline/actions/compact.py#L77). Available params: `{slice}`, `{phase}`, `{project}`. Sourced from `ContextForgeClient.get_project()`. Missing values render as their literal placeholder (existing behavior); the hook **never** errors out, even if CF is unavailable.
5. **Matcher coverage** — Hook entry uses matcher `""` to match both manual `/compact` and auto-compact triggers.
6. **Documentation** — README + the slice 152 authoring guide gain a short "Interactive compaction" section pointing at the two config keys.

### Out of Scope

- **SDK-mode compaction** — handled by slice 158. The two slices share the template loader but otherwise touch different code paths.
- **Multiple templates per project** (e.g. different template per phase) — single `compact.template` value, single `compact.instructions` value. If demand emerges, layer it on later.
- **Modifying Claude Code's compaction behavior itself** — we only inject instructions via the documented hook contract. We do not control trigger thresholds, summarization model choice, or what Claude Code does with the additional context.
- **`PostCompact` hook** — no such hook exists in Claude Code's current hook surface.
- **Cross-platform shell quoting beyond what Typer/JSON already give us** — the hook command is a single argv invocation of `sq`, not a shell pipeline.

## Architecture

### Hook Invocation Flow

```
User types /compact in VS Code or CLI Claude Code
         |
         v
Claude Code reads .claude/settings.json
         |
         v
PreCompact hook command runs:
  sq _precompact-hook                ← hidden subcommand
         |
         v
Subcommand:
  1. Load resolved config (project layered over user)
  2. Pick source: compact.instructions if set, else compact.template
  3. If template → load YAML via load_compaction_template()
  4. Try to read CF project state (best-effort, swallow errors)
  5. Render instructions with _LenientDict({slice, phase, project, ...})
  6. Emit hook JSON to stdout:
       {"hookSpecificOutput": {
          "hookEventName": "PreCompact",
          "additionalContext": "<rendered instructions>"
       }}
  7. Exit 0 (always — never block compaction on error)
         |
         v
Claude Code merges additionalContext into the compaction prompt
```

### Config Keys

Added to [`src/squadron/config/keys.py`](src/squadron/config/keys.py):

```python
"compact.template": ConfigKey(
    name="compact.template",
    type_=str,
    default="minimal",
    description=(
        "Compaction template name for the interactive PreCompact hook. "
        "Resolved against ~/.config/squadron/compaction/ then "
        "src/squadron/data/compaction/."
    ),
),
"compact.instructions": ConfigKey(
    name="compact.instructions",
    type_=str,
    default=None,
    description=(
        "Literal compaction instructions for the interactive PreCompact hook. "
        "If set, overrides compact.template. Param substitution still applies."
    ),
),
```

**Resolution precedence at hook time:**
1. If `compact.instructions` is set (non-empty) → use it verbatim, then run param substitution.
2. Else load template named by `compact.template` (default `minimal`).
3. If neither resolves (template missing on disk, etc.) → emit empty `additionalContext` and exit 0. The hook never breaks compaction.

The **mutual exclusion** is "instructions wins if both are set" rather than a hard error, to keep the hook robust. `sq config set` does not enforce mutual exclusion either — that would couple the config layer to one specific config key relationship. A short note in `sq config list` output (or in docs) covers it.

### Hidden Subcommand

Registered on the top-level `sq` Typer app (not under `sq config` or `sq install-commands`, since this is a runtime hook target, not a user-facing subcommand). Name: `_precompact-hook` (leading underscore + Typer `hidden=True`) so it does not appear in `sq --help`.

```python
# src/squadron/cli/commands/precompact_hook.py
def precompact_hook(
    cwd: str = typer.Option(".", "--cwd", hidden=True),
) -> None:
    """[hidden] Emit PreCompact hook output. Invoked by Claude Code."""
    try:
        instructions = _resolve_instructions(cwd=cwd)
        params = _gather_params(cwd=cwd)
        rendered = _render(instructions, params)
    except Exception:
        rendered = ""  # never break the user's /compact

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreCompact",
            "additionalContext": rendered,
        }
    }
    print(json.dumps(payload))
```

Helpers `_resolve_instructions`, `_gather_params`, `_render` live in the same module. `_render` reuses `_LenientDict` from `actions/compact.py` (extracted to a small shared helper if it isn't already public — see Implementation Details).

The `cwd` option exists so that the hook entry in `.claude/settings.json` can pin invocation to the project directory (Claude Code already runs hooks with the project as cwd, so the option is mostly belt-and-braces and supports tests).

### Param Sourcing

`_gather_params(cwd)` returns a `dict[str, str]` with keys `slice`, `phase`, `project`. Values come from a single best-effort call:

```python
try:
    info = ContextForgeClient(cwd=cwd).get_project()
    return {
        "slice": info.slice or "",
        "phase": info.phase or "",
        "project": _project_name_from_cwd(cwd),
    }
except (ContextForgeError, FileNotFoundError, OSError):
    return {}  # _LenientDict leaves placeholders intact
```

CF unavailability (not installed, not a CF project, command fails) is silently absorbed. The renderer's existing `_LenientDict` then leaves `{slice}` and `{phase}` as literal text in the output. That is acceptable behavior — the summarizer model can still use the instructions, and the user is no worse off than today.

### Installer Changes

[`src/squadron/cli/commands/install.py`](src/squadron/cli/commands/install.py) gains a second responsibility: write the `PreCompact` hook entry into `.claude/settings.json` in addition to copying slash-command files. Two new helpers:

```python
def _settings_json_path(target_root: Path) -> Path:
    return target_root / ".claude" / "settings.json"

def _write_precompact_hook(settings_path: Path) -> None:
    """Add (or refresh) the squadron PreCompact hook entry, preserving others."""

def _remove_precompact_hook(settings_path: Path) -> None:
    """Remove the squadron PreCompact hook entry without touching unrelated hooks."""
```

The new entry shape:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "sq _precompact-hook",
            "_managed_by": "squadron"
          }
        ]
      }
    ]
  }
}
```

The `_managed_by: "squadron"` marker is how `_remove_precompact_hook` identifies its own entry on uninstall (so we never delete a user-authored or third-party hook). On install, if a squadron-managed entry already exists it is replaced; non-squadron entries in the same `PreCompact` array are preserved untouched.

**Install target for the hook entry**: project-local `./.claude/settings.json`, **not** `~/.claude/settings.json`. This matches the project-scoped intent of the config keys — different squadron projects can ship different compact instructions. `sq install-commands --target` already controls where slash commands land; the hook write uses a parallel `--hook-target` option defaulting to `./.claude/settings.json` for symmetry, with the user-level path as an explicit alternative.

**Idempotency**: running `sq install-commands` twice is safe. The second run replaces the squadron-managed entry in place. No duplication.

### Settings.json Merge Strategy

`settings.json` is a Claude Code file we don't own. Rules:

1. If the file does not exist, create it with only the `hooks.PreCompact` section populated.
2. If it exists but has no `hooks` key, add it.
3. If it has a `hooks.PreCompact` array, walk the entries and:
   - Replace any entry whose nested `hooks[*]._managed_by == "squadron"`.
   - Otherwise append a new squadron entry.
4. Pretty-print on write (2-space indent) so user diffs are readable.
5. Preserve any keys we don't recognize at any level — we only touch `hooks.PreCompact[squadron-managed]`.

JSON parse failure (corrupt settings.json) → print a clear error and exit non-zero **without overwriting the file**. This is the one case where we surface a hard failure instead of being lenient, because silently rewriting a corrupt user file would be worse than asking them to fix it.

## Data Flow

```
sq config set compact.template minimal --project
        |
        v
~/.config/squadron/<project>.toml  ← project-layer config

(Later, in interactive Claude Code session)

User: /compact
        |
        v
Claude Code: read .claude/settings.json → find PreCompact hook
        |
        v
spawn: sq _precompact-hook
        |
        v
sq:
  get_config("compact.instructions") → None
  get_config("compact.template")     → "minimal"
  load_compaction_template("minimal")
  ContextForgeClient(cwd=".").get_project()  → ProjectInfo(slice="157", phase="...")
  render with _LenientDict({slice:"157", phase:"...", project:"squadron"})
        |
        v
stdout: {"hookSpecificOutput":{"hookEventName":"PreCompact",
         "additionalContext":"Keep slice design ... for slice 157. ..."}}
        |
        v
Claude Code includes additionalContext in its summarization prompt
        |
        v
Conversation summarized with squadron-aware guidance
```

## Cross-Slice Dependencies and Interfaces

- **Depends on slice 141 (Configuration Externalization)** — uses `data_dir() / "compaction"` and the user override directory pattern. Already in place.
- **Depends on existing config manager** ([`squadron.config.manager`](src/squadron/config/manager.py)) — adds keys, no schema changes.
- **Depends on existing `load_compaction_template` and `_LenientDict`** in [`actions/compact.py`](src/squadron/pipeline/actions/compact.py). The renderer helper (`_LenientDict` and the format-vars wiring) should be lifted into a small shared module (`squadron.pipeline.compact_render` or similar) so the hook subcommand and the compact action both consume it without one importing the other's internals. **Implementation note**, not a separate slice.
- **Interfaces with slice 158 (SDK Session Management and Compaction)** — both will use `load_compaction_template`. No coupling beyond that. 158 does **not** depend on this slice and vice versa.
- **CF dependency** — `ContextForgeClient` is best-effort; CF being absent is not a failure.

## Technical Decisions

### Hidden Subcommand vs Inline Shell Script
A hidden Typer subcommand keeps everything in Python: shared config loading, shared template loader, shared param renderer, shared error handling, easy to test. An inline shell script in `settings.json` would duplicate all of this and be much harder to maintain. The cost of "one more file in `cli/commands/`" is trivial.

### `compact.instructions` Wins Over `compact.template`
Picking one rule and documenting it is simpler than enforcing mutual exclusion at write time. "Literal wins" matches user intuition: if you typed an explicit string into config, you probably meant for it to take effect.

### Project-Local `.claude/settings.json` by Default
Different squadron projects have different priorities. A python project may want different compaction guidance than a TypeScript one. Per-project hook installation matches the per-project config layer.

### Best-Effort CF Lookup
The hook must never break the user's `/compact`. CF being unavailable is the most likely failure mode (CF not installed, not a CF project, transient subprocess error). Swallowing those errors and letting `_LenientDict` leave placeholders intact is the right tradeoff. The instructions are still useful without param substitution.

### Use Existing Compaction Templates Verbatim
The two existing templates ([`minimal.yaml`](src/squadron/data/compaction/minimal.yaml), [`default.yaml`](src/squadron/data/compaction/default.yaml)) are exactly what we want — no new template format, no migration, no breaking changes.

### Don't Enforce Mutual Exclusion at Config-Set Time
Encoding cross-key constraints in `sq config set` couples the config layer to specific keys. Resolution-time precedence is simpler and gives the user flexibility (they can leave both set as a "fallback").

## Success Criteria

1. `sq install-commands` (run from a clean project) creates `.claude/settings.json` with a `PreCompact` hook entry whose command is `sq _precompact-hook` and matcher is `""`. Existing slash-command install behavior is unchanged.
2. Running `sq install-commands` again does not duplicate the entry.
3. `sq install-commands` against a settings.json that already contains an unrelated `PreCompact` hook (no `_managed_by` marker) appends the squadron entry without modifying the existing one.
4. `sq uninstall-commands` removes the squadron-managed entry while leaving other entries intact.
5. `sq uninstall-commands` against a settings.json with no squadron entry is a no-op (success, no error).
6. `sq config set compact.template minimal --project` writes to project config; `sq config get compact.template` resolves to `minimal`.
7. `sq config set compact.instructions "Keep slice {slice}."` writes to user or project config; the literal string is stored as-is.
8. `sq _precompact-hook` (run manually for verification) inside a CF project with active slice `157` emits valid JSON containing `additionalContext` populated from the `minimal` template with `{slice}` resolved to `157`.
9. `sq _precompact-hook` outside a CF project still emits valid JSON; `{slice}`, `{phase}`, `{project}` placeholders are left literal but the rest of the instructions are intact.
10. `sq _precompact-hook` with `compact.instructions` set returns the literal string (with params substituted), not the template content.
11. `sq _precompact-hook` with both keys set returns the `compact.instructions` value (literal wins).
12. `sq _precompact-hook` survives a corrupt or missing template file: emits valid JSON with empty `additionalContext`, exits 0.
13. `sq _precompact-hook` is not listed in `sq --help` output.
14. Real end-to-end smoke: with the hook installed in a real squadron project, typing `/compact` in Claude Code (CLI or VS Code) results in a compaction whose output reflects the squadron-specific instructions (verified by inspecting the post-compaction conversation summary).
15. All existing tests pass; new tests cover settings.json merge cases, hidden subcommand JSON output, config key registration, instructions-vs-template precedence, CF-unavailable fallback, and corrupt-template fallback.

## Verification Walkthrough

### 1. Fresh install, project with CF state

```bash
cd /path/to/squadron
sq install-commands
cat .claude/settings.json | jq .hooks.PreCompact
```

**Expected**:
```json
[
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "sq _precompact-hook",
        "_managed_by": "squadron"
      }
    ]
  }
]
```

### 2. Set a project-specific template

```bash
sq config set compact.template minimal --project
sq config get compact.template
```

**Expected**: `compact.template = minimal  (project)`

### 3. Run the hook manually and inspect output

```bash
sq _precompact-hook | jq .
```

**Expected** (inside a CF project where `cf get` reports `slice: 157`):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "Keep slice design, task breakdown, and any task implementation summaries for slice 157.\nKeep outline of any related architectural or review discussion.\n"
  }
}
```

### 4. Literal instructions override template

```bash
sq config set compact.instructions "Drop everything. Keep only the last 5 messages." --project
sq _precompact-hook | jq -r .hookSpecificOutput.additionalContext
```

**Expected**:
```
Drop everything. Keep only the last 5 messages.
```

### 5. Hidden from help

```bash
sq --help | grep -c precompact
```

**Expected**: `0`

### 6. Real `/compact` in interactive Claude Code

1. Open the project in VS Code with Claude Code extension (or run interactive `claude` from the project directory).
2. Have a brief conversation about slice 157.
3. Type `/compact`.
4. After compaction, ask: "What slice were we discussing?"
5. **Expected**: the model retains slice 157 context because the squadron-aware compaction instructions guided the summarizer to preserve it.

### 7. Uninstall preserves third-party hooks

```bash
# Manually add a fake third-party hook to settings.json:
jq '.hooks.PreCompact += [{"matcher":"","hooks":[{"type":"command","command":"echo other"}]}]' \
  .claude/settings.json > /tmp/s.json && mv /tmp/s.json .claude/settings.json

sq uninstall-commands
jq .hooks.PreCompact .claude/settings.json
```

**Expected**: only the `echo other` entry remains; the squadron entry is gone.

## Implementation Details

### Files Added / Changed

- **New**: `src/squadron/cli/commands/precompact_hook.py` — the hidden subcommand and its helpers (`_resolve_instructions`, `_gather_params`, `_render`).
- **New**: `src/squadron/cli/commands/install_settings.py` — `_settings_json_path`, `_write_precompact_hook`, `_remove_precompact_hook`. Or fold into `install.py` if it stays under ~150 lines.
- **Changed**: `src/squadron/config/keys.py` — register `compact.template` and `compact.instructions`.
- **Changed**: `src/squadron/cli/commands/install.py` — call settings-writer at end of `install_commands`; call settings-remover in `uninstall_commands`. Add `--hook-target` option (default `./.claude/settings.json`).
- **Changed**: `src/squadron/cli/main.py` (or wherever `sq` Typer app is assembled) — register `precompact_hook` with `hidden=True` and the underscore-prefixed name.
- **Changed**: `src/squadron/pipeline/actions/compact.py` — make `_LenientDict` and a tiny `render_with_params(template_text, params)` helper accessible for reuse, either by lifting them into `squadron.pipeline.compact_render` or by exposing them as module-level public symbols. The compact action keeps using them; the hook subcommand imports them.
- **New tests** under `tests/cli/commands/`:
  - `test_precompact_hook.py` — JSON output shape, instructions vs template precedence, CF available vs unavailable, corrupt template fallback, hidden flag.
  - `test_install_settings.py` — fresh-create, idempotent re-run, merge with existing third-party hook, uninstall-preserves-others, corrupt-settings-json refusal.

### Dependency Notes

- No new third-party dependencies. `json` (stdlib), `typer` (already used), `pyyaml` via existing template loader, `ContextForgeClient` (existing).
- The hook command must be on `PATH` when the user types `/compact`. We document the install requirement (`sq` available in the user's shell, which is already true if they ran `sq install-commands`).

### Approach

1. Register the two config keys (small, isolated change). Add tests.
2. Lift `_LenientDict` + the format-vars rendering into a shared helper. Update `actions/compact.py` to import from the new location. No behavior change. Tests stay green.
3. Implement `precompact_hook.py` with `_resolve_instructions`, `_gather_params`, `_render`. Unit-test in isolation with mocked CF client and a temp config dir.
4. Wire the subcommand into the `sq` Typer app with `hidden=True`. Verify `sq --help` does not list it.
5. Implement `_write_precompact_hook` / `_remove_precompact_hook` against an in-memory `dict` of settings JSON. Unit-test merge cases.
6. Wire the writer into `install_commands` and the remover into `uninstall_commands`. Add the `--hook-target` option.
7. Add a small README section ("Interactive `/compact` for VS Code and CLI Claude Code").
8. End-to-end manual smoke in a real Claude Code session.

## Risk Assessment

- **Settings.json merge correctness** — getting the squadron-managed marker and the merge logic right is the highest-risk piece. Mitigated by exhaustive unit tests on merge cases (fresh, existing squadron entry, existing third-party entry, both, empty file, no-hooks-key, no-PreCompact-key, corrupt JSON).
- **Hook output schema** — the exact JSON shape Claude Code expects from `PreCompact` (`hookSpecificOutput.additionalContext` is the most likely candidate based on Claude Code hook docs, but we should verify against the live extension behavior during smoke testing). Mitigation: the manual smoke step at #6 above validates the real interaction; if the schema is different we adjust the single helper that builds the payload.
- **`sq` not on PATH inside the editor's shell** — VS Code and Claude Code CLI may invoke hooks under a non-interactive shell that doesn't source the user's full PATH. Mitigation: document the requirement in the README; if it's a real issue we can fall back to writing the absolute path of `sq` (resolved via `shutil.which("sq")`) into the settings entry at install time.

## Notes

- The hook payload key (`hookSpecificOutput.additionalContext`) is taken from Claude Code's documented `PreCompact` hook contract. The exact field name should be reconfirmed during T1 of implementation against `https://docs.claude.com` hook docs and against a live `/compact` in the VS Code extension.
- This slice intentionally does **not** add a `--user` install target for the hook. If users want a global hook they can manually add the entry to `~/.claude/settings.json`; making it the default risks one project's compaction style leaking into unrelated projects.
- Slice 158 (SDK Session Management and Compaction) is independent and can be designed and implemented in either order. They share only the template loader, which is already extracted and stable.
