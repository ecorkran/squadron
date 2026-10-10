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
reviewedSha: b307ddf765c3d90809b4abdf4db88699257b7997
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 38
diffTruncated: false
turns: 20
promptTokens: 2922713
cachedTokens: 2510464
completionTokens: 136841
reasoningTokens: 132181
durationSeconds: 734.2
runId: run-20261010-p6-71f18cf9
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "D5 escape sweep left live sites the guard cannot see"
    location: "src/squadron/cli/commands/pr.py:120"
  - id: F002
    severity: concern
    category: correctness
    summary: "`--prompt-only` still lowercases a path argument, so D4's fix misses that entry point"
    location: "src/squadron/cli/commands/run.py:1111"
  - id: F003
    severity: concern
    category: error-handling
    summary: "`_load_run_definition` does not catch an unreadable recorded path"
    location: "src/squadron/cli/commands/run.py:189-205"
  - id: F004
    severity: concern
    category: correctness
    summary: "`--force` writes a file with different permissions than the same command without it"
    location: "src/squadron/core/file_write.py:41-47"
  - id: F005
    severity: note
    category: consistency
    summary: "JSON review artifacts still record no profile"
    location: "src/squadron/review/models.py:250"
  - id: F006
    severity: note
    category: correctness
    summary: "The shadow marker names only the immediately-hidden source"
    location: "src/squadron/pipeline/loader.py#discover_pipelines"
  - id: F007
    severity: pass
    category: error-handling
    summary: "`write_new_file`'s exclusive-create and atomic-replace design is correct and tested against its failure modes"
    location: "src/squadron/core/file_write.py:12-23"
---

# Review: code — slice 940

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] D5 escape sweep left live sites the guard cannot see

`render_code_host_error` is the shared renderer for every code-host command, and it interpolates a `CodeHostError` straight into Rich markup:

- `pr.py:120` — `errors.print(f"[red]{exc}[/red]")`
- `pr.py:122` — `errors.print(f"[dim]{exc.fix_hint}[/dim]")`
- `pr.py:333` — `errors.print(f"[dim]base: {selection.base} (source: {selection.source})[/dim]")` (user-supplied branch name)

The same gap exists in the new prompt-only init path: `run.py:698` and `run.py:706` interpolate `pipeline_name` and `definition.name` unescaped. Design D5 requires escaping "exception text **or user-supplied text**" at every CLI print site, and this slice touched `pr.py` (lines 266, 270, 343, 360, 439) without fixing its own error renderer.

The new `tests/cli/test_rich_escape_guard.py:test_no_unescaped_exception_text_in_cli` passes anyway, because `_UnescapedSiteFinder` only flags expressions referring to names bound by an `except ... as <name>`. In `render_code_host_error` the exception arrives as a *parameter*, and in the two `run.py` sites the text is user input. That is the guard's documented limit (design D5), but the sweep was the thing that was supposed to cover the gap, and it did not — so the "77 sites" claim is not fully discharged and the guard now gives false assurance for exactly this class of site.

### [CONCERN] `--prompt-only` still lowercases a path argument, so D4's fix misses that entry point

`_normalize_pipeline_arg` was introduced and applied to `--validate` (line 1138), `--dry-run` (1164), and standard execution (1267). `--prompt-only` init was not converted — it still calls `_handle_prompt_only_init(pipeline.lower(), target, model, param, verbosity=verbose)`, and `--explain` still lowercases at `run.py:1158`.

The consequence is specific: `sq run ./x/Foo.yaml --prompt-only` passes `./x/foo.yaml` down, `pipeline_file_path()` then finds no existing file (on a case-sensitive filesystem), `_run_record_identity` returns `(lowered_path, None)`, and the run is recorded with a lowercased *path* as its name and **no `pipeline_path` at all** — the exact defect #169/D4 exists to eliminate. `init_run` lowercases again on top. `_handle_explain` (`run.py:1158`) has the same mismatch for a path argument.

Compounding this, `tests/cli/commands/test_run_record_identity.py:66-83` passes the raw path directly to `_handle_prompt_only_init`, bypassing the `.lower()` call the command performs. The test asserts `run.pipeline == "bar"` and a populated `pipeline_path` and passes, while the CLI path it is meant to cover still records neither correctly. A test that calls the helper below the call site cannot detect a call-site normalisation bug.

### [CONCERN] `_load_run_definition` does not catch an unreadable recorded path

The helper narrows to `FileNotFoundError` and `(ValidationError, yaml.YAMLError)`. `load_pipeline` → `_load_yaml` opens the file with `with open(path, encoding="utf-8")` (`pipeline/loader.py`), so a `PermissionError` or other `OSError` propagates out of `_load_run_definition` as an unhandled traceback — from `--resume`, `--next`, and `--step-done` alike.

Design D8 enumerates "resume | recorded `pipeline_path` exists but fails to load or validate | `load_pipeline`'s existing error, naming the path, exit 1", and the project's failure-mode rule requires each enumerated failure to produce its own observable signal. `test_recorded_path_that_fails_validation_exits_1_naming_the_path` covers only the validation branch; the unreadable-file row of D8 has no test and no handler.

### [CONCERN] `--force` writes a file with different permissions than the same command without it

`_replace_file` uses `tempfile.mkstemp`, which creates the temporary file with mode `0o600`, then `os.replace`s it over the target. `os.replace` preserves the source's mode, so `sq models init --force` / `sq pipelines copy --force` leave the target at `0600`, whereas the non-force path (`path.open("xb")`, mode `0o666 & ~umask`, typically `0644`) does not. The same command therefore yields different file permissions depending on a flag, and a pre-existing target's own mode is discarded on replace.

The behaviour is otherwise sound and well tested — `test_force_replaces_the_content` asserts content and temp-file cleanup but never checks the mode, which is why this surfaced only on inspection. Fix by `os.chmod`-ing the temp file to the target's existing mode (or `0o666 & ~umask` for a new file) before `os.replace`.

### [NOTE] JSON review artifacts still record no profile

`ReviewResult.profile` is now stamped by `review_client` and by `ReviewAction`, and `_review_frontmatter_lines` emits `aiProfile` for both success and failure markdown. `ReviewResult.to_dict()` does not include `profile`, so an artifact saved through the `--json` path (`save_review_result(as_json=True)`) records no profile at all — the very omission #193 describes, in the sibling artifact format. Every comparable field added in recent slices (`effort`, `run_id`, `requested_model`) is present in `to_dict()`; D6's wording ("one change covers both") is true only of the frontmatter pair.

### [NOTE] The shadow marker names only the immediately-hidden source

`shadows=hidden.source if hidden is not None else None` records only the source that the winning file displaced last in scan order. With all three sources defining a name, a project copy of a user copy of a built-in renders `shadows user`, and the built-in's disappearance from the listing is no longer visible on the row. Design D1's stated purpose for the mark is "Without that mark, the built-in silently drops out of the listing". The single-source form under-delivers on that for the three-way case; the tests cover only the two-source cases (`test_user_copy_of_a_builtin_shadows_built_in`, `test_project_over_user_names_user`).

### [PASS] `write_new_file`'s exclusive-create and atomic-replace design is correct and tested against its failure modes

The helper gets the hard parts right. Without `force`, the existence check and the create are one `open("xb")` call, so two writers cannot both win — `test_two_writers_racing_exactly_one_wins` exercises that with a barrier rather than asserting it in prose. The `FileExistsError` is deliberately raised outside the `try` (with a comment saying why), so a failure that is not ours never unlinks someone else's file, and `test_write_failure_after_create_leaves_no_partial_file` covers the unlink. With `force`, the write goes to a sibling temp file and is moved with `os.replace`, so a failed write leaves the original intact — `test_write_failure_with_force_keeps_the_original_and_no_temp_file` asserts both the content and the absence of a stray temp. Every path cleans up in a `finally` and the single suppress is scoped to `FileNotFoundError` with a justifying comment, consistent with the project's exception-handling rule.

### Run Digest

- Response length: 8018 chars
- Response is newline-free: no
- Tool calls made: 38
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 509785
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2922713 / 2510464 / 136841 / 132181
- Duration: 734.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
