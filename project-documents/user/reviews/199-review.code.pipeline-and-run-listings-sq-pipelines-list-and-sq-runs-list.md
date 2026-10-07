---
docType: review
layer: project
reviewType: code
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: e608394646513be0f9bf8224ba958a9f6e791634
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 42
diffTruncated: false
turns: 20
promptTokens: 2085635
cachedTokens: 1771520
completionTokens: 101286
reasoningTokens: 96340
durationSeconds: 522.6
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: dry
    summary: "The `_load_raw` raisable set is written twice"
    location: "src/squadron/pipeline/run_wait.py:55"
  - id: F002
    severity: concern
    category: documentation
    summary: "`docs/PIPELINES.md` still documents the deleted `sq run --list` flag"
    location: "docs/PIPELINES.md:14"
  - id: F003
    severity: note
    category: dry
    summary: "Duplicated `_warned` helper in two new test modules"
    location: "tests/pipeline/test_run_wait.py#_warned"
  - id: F004
    severity: note
    category: design
    summary: "`_Definitions` caches exceptions in a `PipelineDefinition | Exception` dict"
    location: "src/squadron/pipeline/run_listing.py#_Definitions"
  - id: F005
    severity: note
    category: style
    summary: "`sq agents list` message wrapped in two modules but not the third"
    location: "src/squadron/cli/commands/shutdown.py:41"
  - id: F006
    severity: pass
    category: design
    summary: "`render_run_status` now takes `RunState` instead of `object`"
    location: "src/squadron/cli/run_views.py#render_run_status"
  - id: F007
    severity: pass
    category: design
    summary: "Item-resume eligibility is defined once and the parity is tested"
    location: "src/squadron/pipeline/item_eligibility.py"
  - id: F008
    severity: pass
    category: error-handling
    summary: "`sq runs wait` failure modes are enumerated, bounded and observable"
    location: "src/squadron/pipeline/run_wait.py#wait_for_run"
---

# Review: code — slice 199

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] The `_load_raw` raisable set is written twice

`_STATE_READ_ERRORS` in `run_wait.py` is `(OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaVersionError, ValidationError)` with the comment "as in StateManager.list_runs" — an explicit acknowledgement that this is a second copy. The original lives inline in `StateManager.list_runs` (`src/squadron/pipeline/state.py`, in the `except (OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaVersionError, ValidationError):` clause). Both encode the same contract: exactly what `StateManager._load_raw` may raise for a present state file. The project rule is to define such a set once and reference it everywhere; if `_load_raw`'s raisable set changes (e.g. a new pydantic error, or a schema-version path split), one of the two copies will silently fall out of date and either a run is reported `UNREADABLE` for an exception nobody anticipated or an exception escapes the poll loop as a traceback. Define it once next to `_load_raw` in `state.py` and import it in `run_wait.py` and `list_runs`.

### [CONCERN] `docs/PIPELINES.md` still documents the deleted `sq run --list` flag

The diff removes `--list`/`-l` from `sq run` (`src/squadron/cli/commands/run.py`) and CHANGELOG.md records it ("`sq run --list` (and `-l`). Use `sq pipelines list`"), but `docs/PIPELINES.md:14` still reads:

```
sq run example --list     # list all available pipelines
```

and `docs/PIPELINES.md:346` still reads `sq run example --validate` — that one is fine — but line 14 now fails with "No such option: --list". The Quick Start a few lines below (line 14 vs the `sq pipelines list` block) was updated, so this is one missed line rather than an untouched page. Worth fixing in this slice since the flag removal is the slice's own change.

### [NOTE] Duplicated `_warned` helper in two new test modules

`tests/pipeline/test_run_wait.py` and `tests/pipeline/test_run_listing.py` each define a byte-identical `_warned(caplog, *fragments)` predicate, differing only in the `_LOGGER` constant they close over (and that constant differs by one string). Since both modules already share `tests/pipeline/run_listing_support.py`, a single `warned(caplog, logger, *fragments)` helper there would remove the copy. Minor, but this is the third `run_listing`-related test module in the slice, so future ones will copy it again.

### [NOTE] `_Definitions` caches exceptions in a `PipelineDefinition | Exception` dict

Storing the caught exception as the value and then re-testing `isinstance(loaded, Exception)` on every `get()` works, but it makes the cache value's type depend on a runtime check and forces a `BaseException` into a container typed as data. A small frozen result (`_Loaded(definition=None, error=str|None)`) or a sentinel would keep the union out of the dict and make the "tried once, failure remembered" behaviour readable in the type. This is a readability issue only — the caching, the once-per-pipeline guarantee and the WARNING are all correct and tested (`test_two_runs_of_one_pipeline_load_once`, `test_unloadable_pipeline_is_unavailable_and_tried_once`).

### [NOTE] `sq agents list` message wrapped in two modules but not the third

`message.py` and `task.py` were re-wrapped onto two lines for the longer `agent_name` variable (which would exceed the 104-column limit); `shutdown.py` keeps the same message on one line using `name`. The resulting line is exactly 104 characters, so it is within the configured limit and will not trip `E501` — this is consistency, not a lint failure. Worth noting only because the three messages are meant to read as one string.

### [PASS] `render_run_status` now takes `RunState` instead of `object`

The moved function drops the old `isinstance(state, RunState)` guard that silently returned for any other input — the exact "silent fallback masking caller bugs" defect recorded as tech-debt item F037 (`project-documents/user/analysis/940-analysis.tech-debt-audit.md:74`, `.../theory 941-analysis...`). The parameter is now typed `RunState`, every interpolated value is `escape()`d, and `tests/cli/test_run_views.py::test_status_panel_escapes_markup_in_run_values` pins the escaping of a bracketed param and pause reason. `run.py` and `runs.py` both reach it through the same import, so the panel is identical between `sq run --status` and `sq runs wait`.

### [PASS] Item-resume eligibility is defined once and the parity is tested

`item_decisions` and `RESUMABLE_OUTCOMES` are now the only statement of which items resume and with which decisions; `item_resume._check_record` delegates to them (`request.decision not in decisions`) instead of restating the outcome/flag-kind conditions, and `single_each_step` replaces `item_resume`'s private copy. `tests/pipeline/test_item_eligibility.py::test_check_record_agrees_with_item_decisions` exercises `_check_record` against `item_decisions` across every `ItemOutcome` × `FlagKind` × `ItemDecision` combination, and `tests/pipeline/test_run_listing.py::test_listing_counts_match_what_item_resume_accepts` does the same at the listing level — so the listing cannot drift from what `--item` actually accepts. The refusal message is unchanged for the cases that reach it (only `ACCEPT` can be absent from a non-empty decision set), so this is behaviour-preserving.

### [PASS] `sq runs wait` failure modes are enumerated, bounded and observable

Each failure mode has a distinct outcome and exit code (`NOT_FOUND` 5, `UNREADABLE` 6, `TIMED_OUT` 4, `UNKNOWN_STATUS` 7), every non-`COMPLETED` termination logs at WARNING, and the CLI prints one stderr line naming the run and outcome for any non-zero exit. The one unobservable hazard — a crashed run staying `running` forever — is surfaced rather than hidden: there is no default timeout, the help text says the wait never ends on its own, and the last sleep is cut to the deadline (`min(poll_interval, deadline - clock())`) so the bound is not overshot. `tests/pipeline/test_run_wait.py` asserts both the sleep count and the warning for each path, and `tests/cli/test_runs_command.py::test_every_outcome_maps_to_its_exit_code` asserts the stderr line appears for exactly the non-zero outcomes.

## Response (20261007)

Checked against the code. F001–F004 are fixed in `5c987c01`.

- **F001: accepted.** `state.STATE_READ_ERRORS` is the single statement of what reading a present run-state file can raise. `StateManager.list_runs` and `run_wait._poll` both catch it.
- **F002: accepted.** `docs/PIPELINES.md:14` now reads `sq pipelines list`. The first doc sweep searched for `run --list` and missed `sq run example --list`. A wider sweep (`sq run … --list|-l`, `sq list`) over README, docs, commands, src and tests now finds nothing.
- **F003: accepted.** `warned(caplog, logger, *fragments)` lives in `tests/pipeline/run_listing_support.py`, and both test modules use it.
- **F004: accepted.** `_Definitions` keeps loaded definitions and failure messages in two typed dicts, so no exception is stored in the cache. The behaviour is unchanged and covered by the same tests.
- **F005: no change.** As the finding says, the `shutdown.py` line is within the 104-column limit, and the formatter owns line breaks.

### Run Digest

- Response length: 7342 chars
- Response is newline-free: no
- Tool calls made: 42
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 366370
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2085635 / 1771520 / 101286 / 96340
- Duration: 522.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
