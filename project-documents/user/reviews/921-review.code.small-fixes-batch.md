---
docType: review
layer: project
reviewType: code
slice: small-fixes-batch
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/921-slice.small-fixes-batch.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260919
dateUpdated: 20260919
responseStatus: addressed
reviewedSha: 4ee82710e25ab2bb40b38ebf0fdbc3f0ac5d74c0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
findings:
  - id: F001
    severity: concern
    category: testing
    summary: "New #67 tests depend on the developer's real alias registry and user templates directory"
    location: "tests/cli/test_review_profile.py:290"
  - id: F002
    severity: concern
    category: design
    summary: "Alias-resolution + guard cascade duplicated across the review and judge paths"
    location: "src/squadron/cli/commands/review.py:641"
  - id: F003
    severity: concern
    category: design
    summary: "Sibling-ownership predicate duplicated; partition result discarded in favor of a second ownership path"
    location: "src/squadron/cli/commands/summary_instructions.py:126"
  - id: F004
    severity: concern
    category: error-handling
    summary: "All-excluded error claims no files exist and omits the --key remedy in the single-match case"
    location: "src/squadron/cli/commands/summary_instructions.py:198"
  - id: F005
    severity: note
    category: design
    summary: "Literal model IDs are now rejected without a profile channel — deliberate, but the help text doesn't say so"
    location: "src/squadron/cli/commands/review.py:509"
  - id: F006
    severity: note
    category: documentation
    summary: "`_handle_restore` docstring is stale for the new default-selection behavior"
    location: "src/squadron/cli/commands/summary_instructions.py:149"
  - id: F007
    severity: pass
    category: testing
    summary: "Test discipline matches the hazards the implementation comments warn about"
    location: "tests/cli/commands/test_summary_instructions.py#TestRestoreSiblingExclusion"
---

# Review: code — slice 921

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] New #67 tests depend on the developer's real alias registry and user templates directory

`resolve_model_alias` and `get_all_aliases` are **not** mocked in the new tests — they read `~/.config/squadron/models.toml` via the real `models_toml_path()`. Neither `tests/conftest.py`, `tests/cli/conftest.py`, nor `tests/review/conftest.py` isolates that path (the review conftest isolates only `user_config_path`). So `test_unknown_model_with_no_profile_source_raises` (line 290), `test_unknown_model_with_explicit_profile_passes_through`, and the three `TestUnknownAliasGuard` passthrough tests all hard-require that `llama-3-70b` resolves to no alias — a machine that defines that (quite plausible) user alias fails the suite. The same class of leak exists on the judge path: `_resolve_judge_model` calls the real `load_all_templates()`, which loads user templates from the real `_USER_TEMPLATES_DIR` (`tests/review/test_cli_review_resolve.py:257` fails if a developer's user override of the judge template sets a `profile`, which would legitimately suppress the guard). Recommend patching `models_toml_path` and `_USER_TEMPLATES_DIR` in these tests, mirroring the existing `_isolated_user_config` fixture pattern in `tests/review/conftest.py`.

### [CONCERN] Alias-resolution + guard cascade duplicated across the review and judge paths

The diff adds the same guard call with the same condition and near-identical placement-rationale comments to both `_run_review_command` (lines 639–642) and `_resolve_judge_model` (lines 1214–1217), and `_reject_unknown_alias` (line 509) re-mirrors `_resolve_profile`'s three-channel cascade (flag → template → config) minus the `"sdk"` fallback. Three copies of the "what counts as an explicit profile" decision now exist; a future fourth channel added to `_resolve_profile` will not be picked up by `_reject_unknown_alias`, and a third `resolve_model_alias` call site would need the same hand-placed guard plus the same `None == None` comment. Extracting one helper — e.g. `_resolve_model_and_profile(model_flag, profile_flag, template, template_name) -> tuple[str | None, str]` with the guard inside the `if raw_model is not None:` block — would serve both call sites and make the placement hazard structurally impossible instead of comment-enforced.

### [CONCERN] Sibling-ownership predicate duplicated; partition result discarded in favor of a second ownership path

`owners = {s for s in siblings if not project.startswith(f"{s}-")}` is defined independently in `_partition_by_sibling` (line 126) and `_sibling_owner` (line 139). The selection path uses the former; the picker listing uses the latter — `_partition_by_sibling`'s `excluded` return value is discarded at line 179 (`clean, _excluded = ...`). The two paths also differ in tie-break handling (`_sibling_owner` sorts owners longest-first; `_partition_by_sibling` iterates an unordered set with `any()`), which is harmless today only because the outcome is binary. If either predicate drifts, the listing can mark a file "excluded from default" that is actually selected (or vice versa) with no test catching the disagreement. Compute `owners` once in `_handle_restore`, or have the partition return the owner per path so one code path decides both selection and display — per the project rule that a value used in conditionals should be defined in exactly one place.

### [CONCERN] All-excluded error claims no files exist and omits the --key remedy in the single-match case

When every match is sibling-owned, the error prints "no summary files found for project '{project}'" — factually wrong (files matching the glob exist; they were excluded), and a verbatim duplicate of the genuine no-files message at line 173. Worse, the listing that carries the `use --key '<key>' to restore` remedy only prints when `len(matches) > 1` (line 181), so in the single-match case (exactly the layout in `test_all_matches_excluded_errors_rather_than_falling_back`) the operator gets an incorrect "nothing found" with no path forward. This contradicts the project's own stated convention, applied in `_warn_not_persistable` in `review.py`: a message that reports absence must name the remedy alongside it. Suggest something like: "no summaries for project 'X' (N matching files belong to sibling projects; use --key '<key>' to restore one)".

### [NOTE] Literal model IDs are now rejected without a profile channel — deliberate, but the help text doesn't say so

The guard correctly fails fast per #67 and matches the project's "no silent fallback" principle, with the escape hatch tested. But it is a real behavior change: `--model claude-sonnet-5-20250514` (a literal ID intended for the sdk profile) or a `default_model` config value set to a literal ID with no `default_review_profile` now fails every review/resolve invocation until `--profile` is added. The `--model` option help ("Model override (e.g. opus, sonnet)") doesn't mention that non-alias names require `--profile`; a one-line help update would prevent a round-trip to the error message.

### [NOTE] `_handle_restore` docstring is stale for the new default-selection behavior

The docstring still says "Without ``key``, prints the most recently modified match" — it now prints the most recent *non-sibling-owned* match. `_select_summary`'s docstring was updated correctly; this one was missed. (The "no summary files found" string duplication is covered under the CONCERN above.)

### [PASS] Test discipline matches the hazards the implementation comments warn about

The test additions are written alongside the implementation and cover the failure modes that actually matter: the guard-placement regression (`test_no_model_supplied_does_not_reject` pins the `None == None` hazard the code comments describe), the reversed sibling direction (`test_shorter_sibling_does_not_exclude_own_summaries` documents the load-bearing prefix-continuation qualifier), the `OSError` degradation is asserted to be *observable* (WARNING log via `caplog`, per the failure-mode-enumeration rule), and the `--key` escape hatch is tested end-to-end. The `_isolated_cwd` helper's docstring explains exactly why unpinned `--cwd` would be machine-dependent — the right instinct, applied consistently to every `--restore` invocation in the older tests too.

### Run Digest

- Response length: 7531 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 1
- Stop reason: stop
- Reasoning characters: 85808
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response (20260919)

All 7 findings verified against source before acting. All 4 CONCERNs and both
NOTEs were real and are fixed.

- **F001** (tests read the developer's real alias registry and user templates)
  — confirmed: no conftest isolates `models_toml_path` or `_USER_TEMPLATES_DIR`,
  and `get_all_aliases` re-reads the file on every call (no caching), so the
  guard tests depended on `llama-3-70b` happening to be undefined locally.
  Added autouse `_isolated_model_registry` and `_isolated_user_templates`
  fixtures to `tests/cli/conftest.py` and `tests/review/conftest.py`, mirroring
  the existing `_isolated_user_config` pattern. Verified by temporarily adding
  `[llama-3-70b]` with `profile = "openrouter"` to the real
  `~/.config/squadron/models.toml` — the exact machine the finding described —
  and re-running: 27 passed. The file was restored byte-identical afterward.

- **F002** (alias + guard cascade duplicated across both paths) — confirmed:
  the same guard, condition, and placement-rationale comment appeared at
  review.py:639-642 and :1229-1234, with `_reject_unknown_alias` re-mirroring
  `_resolve_profile`'s cascade as a third copy. Extracted
  `_resolve_model_and_profile(model_flag, profile_flag, template,
  template_name) -> tuple[str | None, str]` holding alias resolution and the
  guard together; both `_run_review_command` and `_resolve_judge_model` now
  call it. The `None == None` placement hazard is structural rather than
  comment-enforced — there is one guard call site, inside the one
  `if raw_model is not None:` branch, so a future third caller cannot
  reintroduce it. `_run_review_command` still reads `model_allows_tools` from
  the pre-resolution name (slice 266's constraint) before delegating.

- **F003** (ownership predicate duplicated; partition result discarded) —
  confirmed: `owners = {...}` was computed independently at
  summary_instructions.py:126 and :139, the two differed in tie-break handling
  (sorted longest-first vs. unordered `any()`), and `_partition_by_sibling`'s
  `excluded` return was discarded at :179 while the listing re-derived
  ownership through `_sibling_owner`. Replaced both with one
  `_owning_siblings(matches, project, siblings) -> dict[Path, str]`; `clean` is
  derived from that same map, so selection and display cannot disagree.
  Longest-owner-first is now the single tie-break rule.

- **F004** (all-excluded error claims no files exist, omits the remedy) —
  confirmed by direct reproduction: with one sibling-owned match, the operator
  got a verbatim copy of the genuine no-files message and, because the picker
  listing only prints for `len(matches) > 1`, no `--key` hint anywhere. The
  message now distinguishes the two absences and names every usable key:
  `no summaries for project 'squadron' selectable by default (1 matching file
  belongs to sibling projects). Restore one explicitly: --key 'pr-p5a'.`
  Pluralization is handled for the multi-match case. Two tests added — one
  asserting the new message and remedy in the single-match case, one pinning
  that a genuinely empty project still gets the original "no summary files
  found" text, so the two cases stay distinguishable.

- **F005** (literal IDs rejected without a profile; help text silent) — the
  behavior is deliberate and stays. The `--model` help string was duplicated
  verbatim at four option definitions, so per the project's one-value-one-place
  rule it is now `_MODEL_OPTION_HELP`, defined once and reading: "Model
  override (e.g. opus, sonnet). A name that is not a known alias is rejected
  unless --profile is also given." Verified rendering via `sq review code --help`.

- **F006** (stale `_handle_restore` docstring) — confirmed and rewritten to
  describe non-sibling-owned default selection, `--key` reaching excluded
  files, the marked listing, and the fourth exit-1 cause.

- **F007** (PASS) — no action.

Gate after fixes: ruff format/check clean, pyright 0 errors, 3988 passed /
4 skipped (was 3987; +2 new F004 tests, -1 for the internal helpers no test
referenced by name). Both fixes re-verified live after the refactor: the #103
case still excludes `squadron-pr-interactive.md` and selects
`squadron-interactive.md`, and the unknown-alias guard still fires on both the
review and judge paths.
