---
docType: review
layer: project
reviewType: code
slice: everyday-cli-fixes
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/940-slice.everyday-cli-fixes.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261009
dateUpdated: 20261009
reviewedSha: 13f58ace56daed23e2cdc95be79a5f4b90e70a4e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 55
diffTruncated: false
turns: 20
promptTokens: 3370880
cachedTokens: 2977280
completionTokens: 171394
reasoningTokens: 164915
durationSeconds: 923.3
runId: run-20261010-p6-71f18cf9
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "The escape sweep leaves user-supplied CLI arguments unescaped, and the guard test cannot flag them"
    location: "src/squadron/cli/commands/task.py:37"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Code-host errors interpolate user-typed targets into unescaped Rich markup"
    location: "src/squadron/cli/commands/pr.py:120"
  - id: F003
    severity: concern
    category: correctness
    summary: "`_normalize_pipeline_arg` is bypassed by `--prompt-only` and `--explain`, which still lowercase a path argument"
    location: "src/squadron/cli/commands/run.py:1111"
  - id: F004
    severity: concern
    category: error-handling
    summary: "`_load_run_definition` misses `OSError` and `UnicodeDecodeError` from an existing-but-unreadable recorded path"
    location: "src/squadron/cli/commands/run.py:194-203"
  - id: F005
    severity: concern
    category: consistency
    summary: "`aiProfile` reaches markdown frontmatter but never JSON, unlike every field beside it"
    location: "src/squadron/review/models.py#ReviewResult.to_dict"
  - id: F006
    severity: note
    category: maintainability
    summary: "The starter header hardcodes a path that `models_toml_path()` already owns"
    location: "src/squadron/cli/commands/models_init.py#_HEADER"
  - id: F007
    severity: note
    category: style
    summary: "`escape()` inside a width format spec can overrun the column and break alignment"
    location: "src/squadron/cli/commands/config.py#config_list"
  - id: F008
    severity: pass
    category: error-handling
    summary: "`write_new_file` handles both write modes' failure modes deliberately"
    location: "src/squadron/core/file_write.py"
  - id: F009
    severity: pass
    category: testing
    summary: "Run-record identity is covered at every entry point that matters"
    location: "tests/cli/commands/test_run_record_identity.py"
---

# Review: code — slice 940

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] The escape sweep leaves user-supplied CLI arguments unescaped, and the guard test cannot flag them

D5 states "Every CLI print that interpolates exception text **or user-supplied text**" is escaped. The parameter-bound sites were not swept, and the new guard deliberately only flags names bound by `except ... as <name>`, so `tests/cli/test_rich_escape_guard.py` passes while these remain:

- `src/squadron/cli/commands/task.py:37` and `src/squadron/cli/commands/message.py:34` interpolate `agent_name` — a **required CLI argument** — into a Rich print. The identical message in `src/squadron/cli/commands/shutdown.py:43` *was* escaped in this same diff, so the inconsistency is introduced here, not pre-existing.
- `src/squadron/cli/commands/install.py:196` — `rprint(f"  {name}")` for installed command names.
- `src/squadron/cli/commands/review.py:419` — `Saved review to {path}`; `src/squadron/cli/commands/review_pr.py:502` escapes the same value, so the two save paths now render differently.
- `src/squadron/cli/commands/run.py:698,706,755,895` — pipeline/run names and `definition.name`, the remaining unescaped siblings of the sites this diff did fix (e.g. `run.py:1142,1148`).
- `src/squadron/cli/commands/history.py:44` — `sender` and `content` are escaped, `timestamp` is not.
- `src/squadron/cli/commands/metrology.py:172` — `rprint(payload.ground_truth_text)` prints a document read from disk as markup, directly under the `Artifact:` line this diff fixed at `metrology.py:169`. Document text containing `[` is silently altered or raises `MarkupError`.

A guard whose stated limit is "it can't tell user-supplied text that never passed through an exception" is fine as a design; the gap is that the acknowledged follow-up (those sites "get escaped as part of the sweep") was not completed, so the guard's green result now reads as broader assurance than it delivers.

### [CONCERN] Code-host errors interpolate user-typed targets into unescaped Rich markup

`render_code_host_error` prints `errors.print(f"[red]{exc}[/red]")` with no `escape`, and the diff touched this file (lines 266, 270, 343, 360, 439 were fixed) without fixing it. This is reachable with user input: `_OWNER_REPO_NUMBER` and `_REPO_NUMBER` in `src/squadron/codehost/targets.py` use `[^/\s#]+` for owner/repository, so a bracket survives parsing, and `_select_explicit` in `src/squadron/codehost/remotes.py` embeds it in the message (`no remote points at {named}; ...`). Remote URLs from `git remote get-url` reach `_describe` the same way via `_URL_REMOTE`/`_SCP_REMOTE`. Since Rich treats `[codex]`-shaped text as markup and drops it, the operator sees a refusal with a mangled repository name — precisely the #177 symptom.

### [CONCERN] `_normalize_pipeline_arg` is bypassed by `--prompt-only` and `--explain`, which still lowercase a path argument

`_normalize_pipeline_arg` (run.py:171) documents itself as the single decision — "A pipeline name is case-insensitive; a file path is not, so it is left as typed" — and is applied at `run.py:1138, 1164, 1267`. But `run.py:1111` calls `_handle_prompt_only_init(pipeline.lower(), ...)` and `run.py:1158` calls `_handle_explain(pipeline.lower(), ...)`.

For `--prompt-only`, `_handle_prompt_only_init` then calls `_run_record_identity(pipeline_name)`, where `pipeline_file_path` tests the *lowercased* string. On a case-sensitive filesystem, `sq run --prompt-only ./X/Foo.yaml` therefore fails to find the file, `load_pipeline` raises `FileNotFoundError`, and — if it did resolve — the run would be recorded as a *name* rather than a path, defeating D4 on the very entry point the `/sq:run` slash command drives. `--explain` has the same shape. The helper's stated purpose is contradicted by two of its four call sites.

### [CONCERN] `_load_run_definition` misses `OSError` and `UnicodeDecodeError` from an existing-but-unreadable recorded path

D8's row for resume is "recorded `pipeline_path` exists but fails to load or validate → `load_pipeline`'s existing error, naming the path, exit 1". `_load_run_definition` catches `FileNotFoundError` and `(ValidationError, yaml.YAMLError)` only. `_load_yaml` opens the file with `open(path, encoding="utf-8")`, so a recorded path that exists but is unreadable (permission denied, or a directory) raises `PermissionError`/`IsADirectoryError`, and a non-UTF-8 file raises `UnicodeDecodeError` — none of which is caught. Those escape as a traceback rather than the one-line error and exit 1 the design specifies. `_DEFINITION_ERRORS` in `src/squadron/pipeline/run_listing.py` already includes `OSError` for the same class of read; the CLI boundary is the weaker of the two.

### [CONCERN] `aiProfile` reaches markdown frontmatter but never JSON, unlike every field beside it

`result.profile` is set in `src/squadron/review/review_client.py:317` and rendered by `_review_frontmatter_lines`, but `ReviewResult.to_dict` emits no `profile` key. Its neighbours in the same file establish the opposite convention explicitly — `effort`, `verdictSource`, `requested_model`, and the diff-coverage trio are all "always present, null when not reported", with comments stating that frontmatter and JSON must agree (SC6). A consumer reading `sq review --json`, or a pipeline step's JSON outputs, has no way to see which profile the review ran through, which is the whole point of D6/#193. `tests/review/test_ai_profile_frontmatter.py` only asserts on frontmatter, so the divergence is untested.

### [NOTE] The starter header hardcodes a path that `models_toml_path()` already owns

`_HEADER` writes `~/.config/squadron/models.toml` as a literal, while `models_toml_path()` (used by the command itself for the write target) returns `Path.home() / ".config" / "squadron" / "models.toml"`. If the path ever changes, the command writes to the new location and the file's own first line points at the old one. Formatting the path in from the single source would keep the two from disagreeing.

### [NOTE] `escape()` inside a width format spec can overrun the column and break alignment

`rprint(f"  {escape(key_name):<{max_key_len}}  {escape(display_val):<40}  ...")` pads to a width computed from the *unescaped* key lengths, but the value being padded is the escaped string. `escape` inserts backslashes, so any key or value containing `[` pads to nothing and pushes the following column right. The same pattern appears at `src/squadron/cli/commands/review.py:1278` (`{escape(t.name):<{max_name_len}}`). Cosmetic only — the current keys and template names carry no brackets — but the padding silently stops working the first time one does.

### [PASS] `write_new_file` handles both write modes' failure modes deliberately

The exclusive-create path opens the handle outside the `try` (so a `FileExistsError` never triggers cleanup of a file this call did not create) and unlinks a partial write in `finally`; the `force` path writes to a same-directory temp and `os.replace`s, cleaning the temp on failure. `tests/core/test_file_write.py` asserts the observable outcome for each — including the two-writer barrier race asserting exactly one winner — which is the right level for this helper. The `.` prefix on the temp name also keeps it out of the `*.yaml` scans the pipelines directory uses.

### [PASS] Run-record identity is covered at every entry point that matters

The tests assert the recorded `pipeline`/`pipeline_path` pair for both fresh paths (SDK and prompt-only) and the absence of a path for named runs, and `tests/cli/commands/test_run_resume_path.py::test_resume_executes_the_recorded_file_not_a_same_named_pipeline` guards the one case that matters most — planning and execution loading the *same* definition rather than a same-named pipeline. `tests/pipeline/test_state.py::TestPipelinePath` covering a legacy v5 file without the field is the right backward-compatibility assertion for an optional schema addition.

### Run Digest

- Response length: 9098 chars
- Response is newline-free: no
- Tool calls made: 55
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 626189
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 3370880 / 2977280 / 171394 / 164915
- Duration: 923.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Response

All findings fixed after the merge, in follow-up commits 3bd4f483..11dfaad0 on `940-slice.everyday-cli-fixes`:

- **Unescaped user-supplied text:** the sites listed (task, message, install, review save, run, history timestamp, metrology ground truth) are escaped. The guard still covers only exception text, which is its stated limit.
- **Code-host errors:** `render_code_host_error` escapes the message and its fix hint. A test covers a bracketed repository name.
- **`--prompt-only` and `--explain` lowercasing a path:** both now go through `_normalize_pipeline_arg`. Tests cover a path keeping its case and a name being lowercased on both entry points.
- **`_load_run_definition` read errors:** it now also catches `OSError` and `UnicodeDecodeError`. Tests cover a directory path and a non-UTF-8 file.
- **`aiProfile` missing from JSON:** `to_dict` always emits `profile`, null when unknown. A test checks that JSON and frontmatter agree.
- **Starter header path:** the header is formatted from `models_toml_path()`.
- **Padding broken by escaping:** the text is padded before it is escaped, in both `config` and `review list`.
