# Command Reference

Complete reference for all squadron CLI commands.

## review

Run structured reviews using built-in templates.

### review arch

Run an architectural review comparing a document against an architecture reference.

```
sq review arch <INPUT_FILE> --against <ARCH_DOC> [OPTIONS]
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `INPUT_FILE` | string | yes | — | Document to review |
| `--against` | string | yes | — | Architecture document to review against |
| `--cwd` | string | no | config or `.` | Working directory |
| `--model` | string | no | config or template default | Model override (e.g. `opus`, `sonnet`) |
| `-v`, `--verbose` | count | no | config or `0` | Verbosity level (use `-v` or `-vv`) |
| `--output` | string | no | `terminal` | Output format: `terminal`, `json`, `file` |
| `--output-path` | string | no | — | File path (required when `--output file`) |

```bash
sq review arch slice-design.md --against hld.md -v
sq review arch spec.md --against arch.md --output json
sq review arch spec.md --against arch.md --model sonnet
```

### review tasks

Run a task plan review comparing a task breakdown against its parent slice design.

```
sq review tasks <INPUT_FILE> --against <SLICE_DOC> [OPTIONS]
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `INPUT_FILE` | string | yes | — | Task breakdown file to review |
| `--against` | string | yes | — | Parent slice design to review against |
| `--cwd` | string | no | config or `.` | Working directory |
| `--model` | string | no | config or template default | Model override (e.g. `opus`, `sonnet`) |
| `-v`, `--verbose` | count | no | config or `0` | Verbosity level |
| `--output` | string | no | `terminal` | Output format |
| `--output-path` | string | no | — | File path for `--output file` |

```bash
sq review tasks 105-tasks.md --against 105-slice.md -v
```

### review code

Run a code review against the current project.

```
sq review code [OPTIONS] [SLICE_NUMBER]
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `SLICE_NUMBER` | int | no* | Slice index to review (e.g. `305`); resolves the slice's own diff |

\* Not required by the parser, but at least one of `SLICE_NUMBER`, `--diff`, or `--files` must be given. Without any of them the review has no code to look at and is rejected rather than run unscoped.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--cwd` | string | no | config or `.` | Project directory to review |
| `--files` | string | no | — | Glob pattern to scope the review |
| `--diff` | string | no | — | Git ref to diff against |
| `--rules` | string | no | config `default_rules` | Path to additional rules file |
| `--rules-dir` | string | no | — | Rules directory override |
| `--no-rules` | flag | no | off | Suppress all rule injection |
| `--model` | string | no | config or template default | Model override (e.g. `opus`, `sonnet`) |
| `--profile` | string | no | config | Provider profile (`sdk`, `openrouter`, `openai`, `local`, …) |
| `-v`, `--verbose` | count | no | config or `0` | Verbosity level |
| `--output` | string | no | `terminal` | Output format |
| `--output-path` | string | no | — | File path for `--output file` |
| `--json` | flag | no | off | Output and save as JSON instead of markdown |
| `--no-save` | flag | no | off | Do not write a review file |

```bash
# Review a slice's own changes (the common case)
sq review code 305 -v

# Review changes against an explicit ref
sq review code --diff main -v

# Review specific files with custom rules
sq review code --files "src/**/*.py" --rules rules/python.md -vv

# Output JSON
sq review code --diff main --output json > review.json
```

**How the slice diff is resolved.** With a `SLICE_NUMBER`, squadron finds the slice's merge commit and diffs against a base ref — **`git.integration_branch` from Context Forge when that key is set, otherwise `main`**. If Context Forge is not installed or the key is unset, the base is `main` and everything behaves as before. This matters on repos that promote work through an integration branch: diffing against `main` there returns the whole accumulated band rather than the slice, and a reviewer handed dozens of already-reviewed files will return a confident, meaningless PASS.

**Review files are overwritten in place, but the prior content is archived first.** A second `sq review code 305` replaces `project-documents/user/reviews/305-review.code.<slice>.md` with no revision suffix and no prompt — but before the write, the existing file is copied to `project-documents/user/reviews/archive/` under its original name, the copy is read back and compared byte-for-byte, and only then is the overwrite allowed. If the archive cannot be written or does not verify, the review is **not saved** and the command says so; the original is left untouched. Hand edits therefore survive as an archived copy, not in place.

### review resolve

Record whether a prior review's findings were addressed by the work done since.

```
sq review resolve [OPTIONS] INDEX [REVIEW_TYPE]
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `INDEX` | int | yes | Slice number whose review to resolve (e.g. `305`) |
| `REVIEW_TYPE` | string | no | `code`, `slice`, `tasks`, `arch`. Omit when the index has exactly one review; when several exist the command errors and lists them rather than guessing |

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--cwd` | string | no | config or `.` | Project directory |
| `--model` | string | no | config or template default | Judge model override (e.g. `opus`) |
| `--profile` | string | no | config | Provider profile (`sdk`, `openrouter`, `openai`, `local`, …) |
| `--no-judge` | flag | no | off | Run the deterministic screens only; never consult the judge |
| `--since` | string | no | the review's `reviewedSha` | Git ref to measure from |
| `-v`, `--verbose` | count | no | config or `0` | Verbosity level (`-v` adds the per-finding note column) |

```bash
# Resolve the only review for slice 305
sq review resolve 305 -v

# Disambiguate when both a code and a tasks review exist
sq review resolve 305 code

# Screens only — no model call, no tokens
sq review resolve 305 --no-judge

# Measure from an explicit ref instead of the review's stamp
sq review resolve 305 --since v1.4.0
```

**How the diff base is chosen.** In precedence order: `--since` if given; otherwise the review's own `reviewedSha` frontmatter key, stamped when the review was authored; otherwise the last commit that touched the review file, with a WARNING saying the base is approximate. The reviews directory is excluded from the measurement — a review file is written after the commit its own `reviewedSha` names, so counting it would make every review look like a change to itself.

**What each resolution means.**

| Resolution | Meaning | Exit code |
|------------|---------|-----------|
| `ADDRESSED` | Every CONCERN+ finding was settled as addressed, and each claim survived verification against the diff | 0 |
| `UNADDRESSED` | At least one finding is demonstrably not addressed — commonly, nothing changed since the review | 1 |
| `UNKNOWN` | The check could not run or could not be trusted: a git failure, a judge transport failure, `--no-judge`, a change set over the injection cap, a claim contradicted by the diff, or a review whose verdict and findings disagree | 1 |

`UNKNOWN` is never a soft pass. A resolution that could not be reached exits 1 exactly as a failure does, so `sq review resolve 305 && ...` is safe to compose.

**The resolution artifact.** Each run writes:

```
project-documents/user/reviews/{index}-resolution.{type}.{slice-name}-r{n}.md
```

`{n}` starts at 1 and increments; a resolution is never overwritten, and a name collision raises rather than replacing a record. The name deliberately contains no `-review.` substring, so metrology's review-discovery globs never pick it up.

Frontmatter schema:

| Key | Description |
|-----|-------------|
| `docType` | Always `review-resolution` |
| `reviewFile` | Filename of the review this resolves |
| `reviewType` | The review's type |
| `slice`, `project` | Carried from the review's frontmatter |
| `reviewVerdict` | The review's own verdict, verbatim |
| `resolution` | `ADDRESSED` \| `UNADDRESSED` \| `UNKNOWN` |
| `reviewedSha` | What the review assessed, or null |
| `resolvedSha` | The base the diff actually ran against |
| `shaSource` | `frontmatter` \| `file-history` \| `since` |
| `judgeModel` | Model consulted, or null when no judge ran |
| `dateCreated` | `YYYYMMDD` |
| `findingStatuses` | List of `{id, status, screen, successor?, note?}` |

**This artifact does not affect `verdict:` on the review file.** The review is the reviewer's record and is never edited by this command. The resolution is evidence for a human — or a future tool — to act on.

**Interim procedure for verdict edits.** Until tooling consumes the artifact directly, a maintainer who edits a review's `verdict:` should do so only when an `ADDRESSED` resolution artifact justifies it, and should cite that artifact's filename in the commit message. This is the practice already used for slice 305's own verdict edit, named here as the standing procedure.

### review list

List all available review templates.

```
sq review list
```

No options. Outputs template names and descriptions.

## config

Manage persistent configuration.

### config set

Set a configuration value.

```
sq config set <KEY> <VALUE> [OPTIONS]
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `KEY` | string | yes | — | Config key to set |
| `VALUE` | string | yes | — | Value to set |
| `--project` | flag | no | false | Write to project-level config |
| `--cwd` | string | no | `.` | Working directory (for project config location) |

```bash
sq config set cwd ~/source/repos/myproject
sq config set verbosity 1
sq config set default_rules ./rules/python.md --project
sq config set default_model opus
```

### config get

Show the resolved value of a configuration key and its source.

```
sq config get <KEY> [OPTIONS]
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `KEY` | string | yes | — | Config key to read |
| `--cwd` | string | no | `.` | Working directory |

```bash
$ sq config get cwd
cwd = ~/source/repos/myproject  (user)
```

### config list

Show all configuration keys with their resolved values and sources.

```
sq config list [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--cwd` | string | no | `.` | Working directory |

```bash
$ sq config list
  cwd            ~/source/repos/myproject  (user)
  default_rules  ./rules/python.md         (project)
  verbosity      0                         (default)
```

### config path

Show configuration file locations and whether they exist.

```
sq config path [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--cwd` | string | no | `.` | Working directory |

```bash
$ sq config path
  User:    ~/.config/squadron/config.toml  exists
  Project: ./.squadron.toml                not found
```

### Metrology keys

Settings for judge calibration and the tech-debt audit harness. Run
`sq config list` to see resolved values and their source.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `metrology.store_dir` | string | `~/.config/squadron/metrology` | Where records are written |
| `metrology.project_id` | string | derived from git remote | Overrides the project identity on records |
| `metrology.sample_budget` | int | 20 | Samples retained per judge configuration |
| `metrology.min_evidence_n` | int | 5 | Samples required before a recommendation is offered |
| `metrology.trend_bucket` | string | `month` | Bucket size for trend reporting |
| `metrology.graduate_match_rate` | float | 0.9 | Agreement rate at which a config is offered for graduation |
| `metrology.tighten_match_rate` | float | 0.6 | Agreement rate below which tightening is suggested |
| `metrology.residual_sample_rate` | float | 0.1 | Sampling rate retained after graduation |
| `metrology.audit_profile` | string | review default | Provider profile for audit runs |
| `metrology.audit_model` | string | *(unset)* | **Model for audit runs — see below** |
| `metrology.audit_variance_runs` | int | 3 | Runs per project in a variance series |
| `metrology.audit_timeout_s` | int | 3600 | Wall-clock cap per audit run |
| `metrology.audit_run_cooldown_s` | int | 60 | Pause between runs in a series |
| `metrology.audit_rate_limit_retries` | int | 10 | Retries before a rate-limited run gives up |
| `metrology.audit_rate_limit_cap_s` | int | 60 | Ceiling on exponential rate-limit backoff |
| `metrology.preemption_fragment_dir` | string | `~/.config/squadron/metrology/preemption` | Where `preempt generate` writes fragment files |

#### Pinning the audit model

`metrology.audit_model` is unset by default, which means squadron sends no
model to the CLI and the CLI picks its own — measured as a 1M-context Opus,
the most expensive option available, chosen silently and subject to change
when the CLI updates.

Pin it for two reasons:

- **Cost.** The default is the priciest model, selected without being asked for.
- **Comparability.** Models produce systematically different finding counts on
  identical code. Measured on one unchanged repository: Opus returned 22-30
  findings across four runs, Sonnet 5 returned 12-16. An unpinned model is not
  a fixed instrument, so a noise floor measured today is not comparable to one
  measured after the default shifts.

```bash
sq config set metrology.audit_model claude-sonnet-5 --project
```

An explicit `--model` on the command still overrides the pin. The resolved
model is stored on each record, so an audit can say what produced it.

## spawn

Spawn a new agent instance.

```
sq spawn --name <NAME> [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | string | yes | — | Unique agent name |
| `--type` | string | no | `sdk` | Agent type |
| `--provider` | string | no | `sdk` | Provider to use |
| `--cwd` | string | no | `.` | Working directory |
| `--system-prompt` | string | no | — | System prompt |
| `--permission-mode` | string | no | `acceptEdits` | Permission mode |
| `--model` | string | no | config `default_model` | Model override (e.g. `opus`, `sonnet`) |

## list

List running agents.

```
sq list [OPTIONS]
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--state` | string | no | — | Filter by agent state |
| `--provider` | string | no | — | Filter by provider |

## task

Send a task prompt to an agent.

```
sq task <AGENT_NAME> <PROMPT>
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `AGENT_NAME` | string | yes | Target agent name |
| `PROMPT` | string | yes | Task prompt to send |

## shutdown

Shutdown agents.

```
sq shutdown <AGENT_NAME>
sq shutdown --all
```

| Argument/Option | Type | Required | Description |
|----------------|------|----------|-------------|
| `AGENT_NAME` | string | no | Agent to shut down |
| `--all` | flag | no | Shutdown all agents |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid arguments, missing files, runtime error, unknown config key), or a review that ran but could not be saved |
| 2 | Review verdict is FAIL |

A review whose file could not be written exits 1 even though the review itself ran and was displayed — the artifact is what Context Forge and every other downstream reader gate on, so reporting success with nothing on disk would be a silent failure. A `FAIL` verdict keeps exit 2 in that case: it is the more specific signal, and both codes are non-zero.
